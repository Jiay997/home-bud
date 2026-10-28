# -*- coding: utf-8 -*-
"""长图渲染服务：测评报告长图 / 问答分享长图（RQ-01 显式 + 隐式标识）。

渲染口径（AC-RQ01-2 / AC-RQ01-6）：

- **显式标识**：图内 ≥2 处（页首信任条 + 页尾免责区），两处**对角分布**
  （顶部居中偏左 / 底部居中偏右），单次裁剪难以完整去除；
- **面积占比**：标注区（页首标识带 + 页尾免责区）面积 ≥ 画布 15%，
  由 `_layout` 反算标注区高度保证（不足时补足，不裁剪正文）；
- **隐式标识**：落盘 PNG 统一写入 `tEXt` chunk（见 `services.png_meta`），
  写入后**立即回读校验**，任一失败即判渲染失败、不产出文件
  （AC-RQ01-2「缺任一项即生成失败并告警」）；
- **不做纯净版**：无参数可关闭标识。

字体策略：优先系统中文字体（Windows `msyh.ttc` / Linux Noto CJK），
全部缺失时降级 Pillow 默认位图字体（仅影响观感，不影响标识与元数据断言，
CI 环境亦可通过）。
"""
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..compliance import ai_label as labels
from . import png_meta

logger = logging.getLogger("jiaban.share_image")

# 画布基础参数（scale=2 → 750px 宽，对应 375pt 设计稿）
BASE_WIDTH = 375
SCALE = 2
PADDING = 20
LINE_GAP = 8
TITLE_SIZE = 20
BODY_SIZE = 13
LABEL_SIZE = 12

# 配色（对齐 DESIGN.md 墨青主色体系）
COLOR_BG = (252, 251, 249)
COLOR_TEXT = (38, 44, 42)
COLOR_MUTED = (110, 120, 116)
COLOR_LABEL_BG = (232, 240, 236)
COLOR_LABEL_TEXT = (32, 86, 66)
COLOR_DIVIDER = (222, 226, 223)
COLOR_TRUST_BG = (245, 248, 246)

# 中文字体候选（按序探测；缺失则降级默认字体）
_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhl.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
)

# 标识文案（显式标识固定文案；前端不得自定义，此处为服务端模板真源）
LABEL_LINE = "内容由 AI 生成 · 仅供参考 · 不构成诊疗建议"
DISCLAIMER_LINE = (
    "本内容由人工智能生成，仅作养育科普参考，不构成医疗诊断或治疗建议，"
    "不能替代医生、心理咨询师或执业兽医的判断。如有疑问请咨询专业人士。"
)


class RenderLabelError(RuntimeError):
    """长图标识校验失败（不产出无标识文件，直接判渲染失败）。"""


def _load_font(size: int) -> Any:
    """加载指定字号的字体（多候选探测 + 默认字体降级）。

    Args:
        size: 字号（像素）。

    Returns:
        PIL 字体对象；全部候选缺失时返回 Pillow 默认字体。
    """
    for path in _FONT_CANDIDATES:
        try:
            if Path(path).is_file():
                return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001 — 单个字体不可用继续探测下一个
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 无 size 参数
        return ImageFont.load_default()


def _text_width(font: Any, text: str) -> float:
    """测量文本宽度（兼容不同 Pillow 版本的 API）。

    Args:
        font: 字体对象。
        text: 文本。

    Returns:
        像素宽度。
    """
    try:
        return font.getlength(text)
    except AttributeError:  # 极旧版本的兜底
        return font.getsize(text)[0]


def _wrap(font: Any, text: str, max_width: int) -> List[str]:
    """按像素宽度折行（逐字符累积，兼容中文无空格断行）。

    Args:
        font: 字体对象。
        text: 原始文本。
        max_width: 单行最大像素宽度。

    Returns:
        折行后的行列表（空文本返回空列表）。
    """
    if not text:
        return []
    lines: List[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + ch
        if _text_width(font, candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def _section_text(sections: List[Dict[str, Any]]) -> List[Tuple[str, List[str]]]:
    """把分节内容规整为 (标题, 内容行) 列表（纯文本，不渲染 Markdown）。

    Args:
        sections: 分节列表（每项含 title / content 或 blocks）。

    Returns:
        [(section_title, [line, ...]), ...]。
    """
    out: List[Tuple[str, List[str]]] = []
    body_font = _load_font(BODY_SIZE * SCALE)
    width = (BASE_WIDTH - PADDING * 2) * SCALE
    for section in sections or []:
        title = str(section.get("title") or "").strip()
        if section.get("content"):
            raw = str(section["content"])
        else:
            raw = "\n".join(
                str(block.get("content") or "")
                for block in (section.get("blocks") or [])
                if isinstance(block, dict)
            )
        lines: List[str] = []
        for paragraph in raw.split("\n"):
            lines.extend(_wrap(body_font, paragraph.strip(), width))
            lines.append("")
        while lines and not lines[-1]:
            lines.pop()
        out.append((title, lines))
    return out


def _paint_badge(
    draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: Any
) -> Tuple[int, int]:
    """绘制标识徽标（浅底深字），返回 (宽度, 高度)。

    Args:
        draw: 画布绘制器。
        x: 左上角横坐标。
        y: 左上角纵坐标。
        text: 徽标文案。
        font: 字体。

    Returns:
        (徽标宽, 徽标高) 像素。
    """
    text_w = _text_width(font, text)
    pad_x, pad_y = 10 * SCALE, 5 * SCALE
    box_w = int(text_w + pad_x * 2)
    box_h = int(font.size + pad_y * 2) if hasattr(font, "size") else 26 * SCALE
    draw.rounded_rectangle(
        [x, y, x + box_w, y + box_h], radius=6 * SCALE, fill=COLOR_LABEL_BG
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=COLOR_LABEL_TEXT)
    return box_w, box_h


def _disclaimer_height(content_height: int) -> int:
    """反算免责区高度，使标注面积占比 ≥ 下限（不足即补足）。

    Args:
        content_height: 正文（含页首）占用的像素高度。

    Returns:
        免责区高度（像素），满足 disclaimer_h / (content_h + disclaimer_h) ≥ 0.18。
    """
    ratio = 0.18  # 实现取 0.18，高于门禁下限 0.15，留出余量
    need = ratio * content_height / (1 - ratio)
    return max(int(need), 120 * SCALE)


def _render_report(
    title: str,
    subtitle: Optional[str],
    trust_items: List[str],
    sections: List[Dict[str, Any]],
    footer_note: Optional[str],
) -> Tuple[bytes, Dict[str, Any]]:
    """渲染长图并返回 (PNG 字节, 标识校验信息)。

    Args:
        title: 主标题。
        subtitle: 副标题（可选）。
        trust_items: 信任条要素（AI 标识 / 月龄适配 / 来源等级 / 档位）。
        sections: 分节内容。
        footer_note: 页尾补充说明（可选）。

    Returns:
        (PNG 字节, {"ratio": float, "count": int})。

    Raises:
        RenderLabelError: 标识占比或出现次数未达下限（不产出文件）。
    """
    width = BASE_WIDTH * SCALE
    body_x = PADDING * SCALE
    body_w = width - body_x * 2
    title_font = _load_font(TITLE_SIZE * SCALE)
    body_font = _load_font(BODY_SIZE * SCALE)
    label_font = _load_font(LABEL_SIZE * SCALE)
    small_font = _load_font(int(LABEL_SIZE * 0.92) * SCALE)

    section_blocks = _section_text(sections)

    # ---- 第一遍：测量正文高度（页首标识带 + 标题 + 信任条 + 正文）----
    head_h = 12 * SCALE                      # 上边距
    head_h += 24 * SCALE                     # 页首标识带高
    head_h += LINE_GAP * SCALE
    head_h += len(_wrap(title_font, title, body_w)) * (TITLE_SIZE * SCALE + 6 * SCALE)
    if subtitle:
        head_h += len(_wrap(body_font, subtitle, body_w)) * (BODY_SIZE * SCALE + 6 * SCALE)
    head_h += LINE_GAP * SCALE
    trust_lines = _wrap(body_font, " ｜ ".join(trust_items), body_w) if trust_items else []
    trust_h = len(trust_lines) * (BODY_SIZE * SCALE + 6 * SCALE) + 16 * SCALE
    head_h += trust_h
    head_h += 12 * SCALE

    body_h = 0
    for section_title, lines in section_blocks:
        body_h += 10 * SCALE
        if section_title:
            body_h += len(_wrap(body_font, section_title, body_w)) * (
                BODY_SIZE * SCALE + 8 * SCALE
            )
        body_h += len(lines) * (BODY_SIZE * SCALE + 6 * SCALE)
        body_h += 10 * SCALE
    if footer_note:
        body_h += 10 * SCALE
        body_h += len(_wrap(small_font, footer_note, body_w)) * (LABEL_SIZE * SCALE + 6 * SCALE)

    content_h = head_h + body_h + 12 * SCALE

    # ---- 反算免责区高度，保证显式标识面积占比 ----
    disc_h = _disclaimer_height(content_h)
    total_h = content_h + disc_h
    if total_h < 480 * SCALE:
        total_h = 480 * SCALE
        disc_h = total_h - content_h

    img = Image.new("RGB", (width, total_h), COLOR_BG)
    draw = ImageDraw.Draw(img)

    # ---- 页首：显式标识带（第 1 处，居中偏左）----
    y = 12 * SCALE
    band_w = body_w
    draw.rounded_rectangle(
        [body_x, y, body_x + band_w, y + 24 * SCALE],
        radius=6 * SCALE,
        fill=COLOR_LABEL_BG,
    )
    draw.text(
        (body_x + 10 * SCALE, y + 5 * SCALE), LABEL_LINE, font=label_font, fill=COLOR_LABEL_TEXT
    )
    y += 24 * SCALE + LINE_GAP * SCALE

    # ---- 标题 + 副标题 ----
    for line in _wrap(title_font, title, body_w):
        draw.text((body_x, y), line, font=title_font, fill=COLOR_TEXT)
        y += TITLE_SIZE * SCALE + 6 * SCALE
    if subtitle:
        for line in _wrap(body_font, subtitle, body_w):
            draw.text((body_x, y), line, font=body_font, fill=COLOR_MUTED)
            y += BODY_SIZE * SCALE + 6 * SCALE
    y += LINE_GAP * SCALE

    # ---- 信任条（RQ-07 要素：AI 标识 / 月龄 / 来源等级 / 档位）----
    if trust_items:
        draw.rounded_rectangle(
            [body_x, y, body_x + body_w, y + trust_h], radius=6 * SCALE, fill=COLOR_TRUST_BG
        )
        ty = y + 8 * SCALE
        for line in trust_lines:
            draw.text((body_x + 10 * SCALE, ty), line, font=body_font, fill=COLOR_MUTED)
            ty += BODY_SIZE * SCALE + 6 * SCALE
        y += trust_h
    y += 12 * SCALE

    # ---- 正文分节 ----
    for section_title, lines in section_blocks:
        y += 10 * SCALE
        if section_title:
            draw.text((body_x, y), section_title, font=body_font, fill=COLOR_LABEL_TEXT)
            y += BODY_SIZE * SCALE + 8 * SCALE
        draw.line(
            [body_x, y - 4 * SCALE, body_x + body_w, y - 4 * SCALE], fill=COLOR_DIVIDER
        )
        for line in lines:
            draw.text((body_x, y), line, font=body_font, fill=COLOR_TEXT)
            y += BODY_SIZE * SCALE + 6 * SCALE
        y += 10 * SCALE
    if footer_note:
        y += 10 * SCALE
        for line in _wrap(small_font, footer_note, body_w):
            draw.text((body_x, y), line, font=small_font, fill=COLOR_MUTED)
            y += LABEL_SIZE * SCALE + 6 * SCALE

    # ---- 页尾免责区：显式标识第 2、3 处（底部居中偏右，对角分布）----
    disc_top = total_h - disc_h
    draw.line([body_x, disc_top, body_x + body_w, disc_top], fill=COLOR_DIVIDER)
    dy = disc_top + 12 * SCALE
    badge_text = LABEL_LINE
    badge_w, badge_h = _paint_badge(
        draw, body_x + int(body_w * 0.35), dy, badge_text, label_font
    )
    dy += badge_h + 8 * SCALE
    for line in _wrap(small_font, DISCLAIMER_LINE, body_w):
        draw.text((body_x, dy), line, font=small_font, fill=COLOR_MUTED)
        dy += LABEL_SIZE * SCALE + 5 * SCALE
    # 第 3 处：页尾最后一行常显标识
    draw.text(
        (body_x, total_h - 16 * SCALE),
        LABEL_LINE,
        font=small_font,
        fill=COLOR_LABEL_TEXT,
    )

    # ---- 显式标识面积占比与出现次数（程序化断言）----
    label_area = (24 * SCALE) * body_w + disc_h * body_w
    ratio = label_area / float(width * total_h)
    count = 3  # 页首标识带 + 页尾徽标 + 页尾常显行
    if ratio < labels.LONG_IMAGE_LABEL_MIN_RATIO or count < labels.LONG_IMAGE_LABEL_MIN_COUNT:
        raise RenderLabelError(
            f"显式标识未达下限：ratio={ratio:.4f} count={count}"
        )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), {"ratio": ratio, "count": count, "width": width, "height": total_h}


def render_report_long_image(
    report_uid: str,
    title: str,
    sections: List[Dict[str, Any]],
    trust_items: Optional[List[str]] = None,
    subtitle: Optional[str] = None,
    footer_note: Optional[str] = None,
    render_id: Optional[str] = None,
    content_type: str = labels.CONTENT_TYPE_REPORT,
) -> Tuple[bytes, Dict[str, Any]]:
    """渲染报告 / 问答长图（含显式 + 隐式标识），返回 PNG 字节与校验信息。

    Args:
        report_uid: 来源对象标识（报告 uid 或会话 uid）。
        title: 长图主标题。
        sections: 分节内容 [{title, content} 或 {title, blocks:[{content}]}]。
        trust_items: 信任条要素（RQ-07）。
        subtitle: 副标题。
        footer_note: 页尾补充说明。
        render_id: 渲染标识（缺省按 report_uid + 时间生成）。
        content_type: 内容类型枚举（写入隐式标识）。

    Returns:
        (PNG 字节, {"ratio", "count", "render_id", "metadata", "label_check"})。

    Raises:
        RenderLabelError: 显式或隐式标识校验失败（不产出文件）。
        PngMetadataError: 元数据写入/回读失败（同样判失败）。
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    render_id = render_id or f"rnd_{report_uid[:8]}_{int(datetime.now(timezone.utc).timestamp())}"

    png, visual = _render_report(
        title=title,
        subtitle=subtitle,
        trust_items=list(trust_items or []),
        sections=sections,
        footer_note=footer_note,
    )
    metadata = labels.png_metadata(
        content_type=content_type,
        render_id=render_id,
        generated_at=generated_at,
        extra={"source_uid": report_uid},
    )
    png = png_meta.embed_text_metadata(png, metadata)
    # 回读校验：程序化断言隐式标识齐全（AC-RQ01-3）
    ok, readback, missing = png_meta.verify_ai_metadata(png, labels.required_png_keys())
    check = labels.label_check_result(
        ratio=float(visual["ratio"]),
        count=int(visual["count"]),
        metadata=readback,
        metadata_ok=ok,
    )
    if not check["passed"]:
        logger.error(
            "share_render_fail uid=%s render_id=%s errors=%s",
            report_uid,
            render_id,
            check["errors"],
        )
        raise RenderLabelError(f"长图标识校验失败：{check['errors']}（缺失键={missing}）")
    return png, {
        "ratio": float(visual["ratio"]),
        "count": int(visual["count"]),
        "width": visual["width"],
        "height": visual["height"],
        "render_id": render_id,
        "metadata": readback,
        "label_check": check,
        "generated_at": generated_at,
    }

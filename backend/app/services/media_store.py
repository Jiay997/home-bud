# -*- coding: utf-8 -*-
"""档案媒体存储服务（头像/相册，甲方需求 2026-10-14）。

本地磁盘 MVP 口径：上传图片经 Pillow 规范化（EXIF 旋转 / 限长边 /
JPEG q85）后落在 upload_dir，对外经 /media 静态挂载暴露；文件名 uuid4
不可枚举。生产演进替换为 OSS/签名 URL 时仅改本模块与 config.upload_dir。
"""
import io
import uuid
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageOps

from app.core.config import get_settings

# 允许的上传格式（Pillow 识别结果）与体积上限
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
# 体检报告文档上限（甲方需求 2026-10-15）：PDF 10MB；图片走 save_image 的 8MB
DOCUMENT_MAX_BYTES = 10 * 1024 * 1024
# 规范化后的最长边：头像（圆形小图）/ 相册照片
AVATAR_MAX_SIDE = 512
PHOTO_MAX_SIDE = 1280
JPEG_QUALITY = 85


class MediaValidationError(Exception):
    """图片校验失败（空文件/超限/格式不支持/解码失败），路由层映射 1001。"""


def media_root() -> Path:
    """上传文件根目录（相对路径锚定 backend 目录）。

    Returns:
        绝对路径 Path（不保证已存在，调用方按需 mkdir）。
    """
    root = Path(get_settings().upload_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    return root


def _safe_subdir(subdir: str) -> Path:
    """校验子目录名（仅允许小写字母/数字/下划线/横杠与 / 分层）。

    Args:
        subdir: 相对子目录，如 "children" 或 "photos/pets"。

    Returns:
        校验通过的子目录 Path（未创建）。

    Raises:
        ValueError: 含非法字符（防路径逃逸）。
    """
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-/")
    if not subdir or set(subdir) - allowed or "//" in subdir:
        raise ValueError(f"invalid media subdir: {subdir!r}")
    return Path(subdir)


def save_image(data: bytes, subdir: str, max_side: int) -> Tuple[str, int, int, int]:
    """校验并规范化保存图片。

    EXIF 方向纠正 → 透明底合成白底 → 超限长边等比缩放 → 统一 JPEG q85。

    Args:
        data: 原始上传字节。
        subdir: 相对子目录（经 _safe_subdir 校验）。
        max_side: 规范化后最长边上限（像素）。

    Returns:
        (相对路径, 宽, 高, 字节数)；相对路径即入库的 file_path/avatar_path。

    Raises:
        MediaValidationError: 空文件/超体积/格式不支持/解码失败。
        ValueError: 子目录非法。
    """
    if not data:
        raise MediaValidationError("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise MediaValidationError("file too large")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # noqa: BLE001 — 任意解码失败统一为校验错误
        raise MediaValidationError("decode failed") from exc
    if img.format not in ALLOWED_FORMATS:
        raise MediaValidationError(f"format not allowed: {img.format}")

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    target_dir = media_root() / _safe_subdir(subdir)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    target = target_dir / filename
    img.save(target, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    width, height = img.size
    return f"{subdir}/{filename}", width, height, target.stat().st_size


def save_document(data: bytes, subdir: str, filename: str) -> Tuple[str, int]:
    """校验并保存健康档案报告文档（PDF 原样落盘，图片复用图片规范化）。

    PDF 按 %PDF- 魔数校验（扩展名须一致），原字节直存；jpg/png/webp 委托
    save_image 规范化（长边 1280 / JPEG q85，体积上限 8MB）。统一 uuid
    命名防枚举；原文件名不入盘，由调用方入库仅作展示。

    Args:
        data: 原始上传字节。
        subdir: 相对子目录（经 _safe_subdir 校验，如 "health"）。
        filename: 上传原始文件名（判断扩展名用）。

    Returns:
        (相对路径, 字节数)；相对路径即入库的 file_path。

    Raises:
        MediaValidationError: 空文件/超体积/格式不支持/魔数不符。
        ValueError: 子目录非法。
    """
    if not data:
        raise MediaValidationError("empty upload")
    if len(data) > DOCUMENT_MAX_BYTES:
        raise MediaValidationError("file too large")
    lower = (filename or "").lower()
    if lower.endswith(".pdf") or data[:5] == b"%PDF-":
        if not (lower.endswith(".pdf") and data.startswith(b"%PDF-")):
            raise MediaValidationError("invalid pdf")
        target_dir = media_root() / _safe_subdir(subdir)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}.pdf"
        target = target_dir / name
        target.write_bytes(data)
        return f"{subdir}/{name}", target.stat().st_size
    # 其余按图片处理（save_image 校验 jpeg/png/webp 与 8MB 上限）
    rel, _width, _height, size = save_image(data, subdir, PHOTO_MAX_SIDE)
    return rel, size


def delete_file(rel_path: str) -> bool:
    """删除媒体文件（path traversal 防护）。

    Args:
        rel_path: 入库相对路径（如 "children/xxx.jpg"）。

    Returns:
        True 已删除；False 路径非法或文件不存在（幂等，不抛错）。
    """
    if not rel_path:
        return False
    root = media_root().resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return False
    if target.is_file():
        target.unlink()
        return True
    return False

# -*- coding: utf-8 -*-
"""AI 生成标识合规模块（RQ-01 / NFR-C13）。

职责（三条链路统一口径的唯一真源）：

1. **页面固定位**：服务端在响应契约中下发 `ai_label` 对象，前端只渲染
   `text_id` 对应文案，禁止前端拼装（AC-RQ01-1 / US-RQ01-04）；
2. **分享长图**：渲染层按 `LONG_IMAGE_LABEL_MIN_RATIO`（≥15%）与
   `LONG_IMAGE_LABEL_MIN_COUNT`（≥2 处）强制装配，缺项即生成失败
   （AC-RQ01-2）；
3. **导出文件隐式标识**：PNG `tEXt` chunk 写入 `software` / `ai_generated` /
   `content_type` / `generated_at` / `render_id`，可程序化校验（AC-RQ01-3）。

边界（AC-RQ01-4/6）：标识位不提供后台开关（唯一变更途径为代码发布 +
合规评审）；显式标识图内两处对角分布，不做「纯净版」导出。
"""
from typing import Any, Dict, List, Optional

from ..core.config import get_settings

# 服务端下发的文案 ID（前端只渲染该 ID 对应文案）
AI_LABEL_TEXT_ID = "AI_GEN_LABEL_V1"

# 前端兜底文案（配置缺失时回退 + 上报 ai_label_fallback，绝不出现无标识页面）
AI_LABEL_FALLBACK_TEXT = "内容由 AI 生成，仅供参考，不构成诊疗建议"

# 标识固定位取值：页面顶部 / 页面底部（按页面类型固定，不随内容漂移）
POSITION_TOP = "page_top"
POSITION_BOTTOM = "page_bottom"

# 页面类型 → 固定位（AC-RQ01-1：覆盖 F3/F4/F5/F6/F7/F8/F10）
PAGE_POSITIONS: Dict[str, str] = {
    "home": POSITION_BOTTOM,
    "answer": POSITION_TOP,
    "report": POSITION_TOP,
    "blocked": POSITION_TOP,
    "history": POSITION_TOP,
    "share_image": POSITION_TOP,
}

# 长图标识合规下限（对齐 V3.0 Q-22 渲染规格）
LONG_IMAGE_LABEL_MIN_RATIO = 0.15
LONG_IMAGE_LABEL_MIN_COUNT = 2

# 隐式标识常量（格式常量化；服务端生成端统一实现）
PNG_SOFTWARE = "BabeJiabanAI"
PNG_AI_GENERATED = "1"
CONTENT_TYPE_REPORT = "assessment_report"
CONTENT_TYPE_QA = "qa_answer"
CONTENT_TYPE_SHARE = "share_card"


def filing_no() -> Optional[str]:
    """返回生成式 AI 服务备案号（未配置时返回 None）。

    备案号与显式标识文案一并展示（PRD §3.1.3「监管衔接」）；未配置时
    标识仍完整展示，只是不带备案号后缀。

    Returns:
        备案号字符串或 None。
    """
    value = (get_settings().ai_filing_no or "").strip()
    return value or None


def ai_label(page: str = "answer") -> Dict[str, Any]:
    """构造 `ai_label` 契约对象（页面固定位标识）。

    Args:
        page: 页面类型（home / answer / report / blocked / history / share_image）。

    Returns:
        `{visible, text_id, position, fallback_text, filing_no}` 字典；
        该结构随每个回答 / 报告 / 拦截响应下发。
    """
    return {
        "visible": True,
        "text_id": AI_LABEL_TEXT_ID,
        "position": PAGE_POSITIONS.get(page, POSITION_TOP),
        "fallback_text": AI_LABEL_FALLBACK_TEXT,
        "filing_no": filing_no(),
    }


def png_metadata(
    content_type: str,
    render_id: str,
    generated_at: str,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """构造 PNG 隐式标识元数据字典（键名即 `tEXt` keyword）。

    Args:
        content_type: 内容类型枚举（assessment_report / qa_answer / share_card）。
        render_id: 本次渲染唯一标识（可追溯、可关联 RenderRecord）。
        generated_at: RFC3339 生成时间（UTC）。
        extra: 追加元数据（值必须为 ASCII 安全字符串）。

    Returns:
        元数据字典（键值均为 str）。
    """
    meta: Dict[str, str] = {
        "software": PNG_SOFTWARE,
        "ai_generated": PNG_AI_GENERATED,
        "content_type": content_type,
        "generated_at": generated_at,
        "render_id": render_id,
    }
    for key, value in (extra or {}).items():
        if value is not None:
            meta[str(key)] = str(value)
    return meta


def required_png_keys() -> List[str]:
    """返回隐式标识的必需键（程序化校验清单）。

    Returns:
        必需键名列表。
    """
    return ["software", "ai_generated", "content_type", "generated_at", "render_id"]


def label_check_result(
    ratio: float,
    count: int,
    metadata: Dict[str, str],
    metadata_ok: bool,
) -> Dict[str, Any]:
    """汇总一次长图渲染的标识校验结果（写入 RenderRecord.label_check）。

    Args:
        ratio: 显式标识面积占比。
        count: 显式标识出现次数。
        metadata: 实际写入的隐式标识元数据。
        metadata_ok: 隐式标识回读校验是否通过。

    Returns:
        `{ratio, count, metadata_ok, passed, errors[]}`；`passed=False` 时调用方
        必须判定渲染失败并告警（AC-RQ01-2 / AC-RQ01-4）。
    """
    errors: List[str] = []
    if ratio < LONG_IMAGE_LABEL_MIN_RATIO:
        errors.append(
            f"显式标识面积占比 {ratio:.4f} < 下限 {LONG_IMAGE_LABEL_MIN_RATIO}"
        )
    if count < LONG_IMAGE_LABEL_MIN_COUNT:
        errors.append(f"显式标识出现 {count} 次 < 下限 {LONG_IMAGE_LABEL_MIN_COUNT} 次")
    if not metadata_ok:
        missing = [k for k in required_png_keys() if not metadata.get(k)]
        errors.append(f"隐式标识缺失或不可读：{missing}")
    return {
        "ratio": round(float(ratio), 4),
        "count": int(count),
        "metadata_ok": bool(metadata_ok),
        "passed": not errors,
        "errors": errors,
    }

# -*- coding: utf-8 -*-
"""首答信任条装配服务（RQ-07 §3.7.3 首答信任检查单 10 项）。

信任条要素（AC-RQ07-1，页首依次可见）：

1. AI 生成标识（RQ-01，服务端下发的 `text_id`）；
2. 适用月龄 / 宠龄标识（来自档案派生字段；无档案为「通用区间」）；
3. 来源等级徽标（知识库 `source_level` 渲染，等级规则见 DR-10）；
4. 档位徽标（RQ-06 `triage.level`，无分级场景不展示）。

要素缺失口径（AC-RQ07-6）：**不得静默隐藏要素伪装完整**——缺失要素以
`状态=missing` 出现在 `elements` 中并计入 `missing` 列表，前端显示
「信息待补」态并上报 `trust_bar_missing`。
"""
import logging
from typing import Any, Dict, Iterable, List, Optional

from ..compliance import ai_label as labels
from ..models import KbEntry

logger = logging.getLogger("jiaban.trust")

# 来源等级（DR-10：权威指南 / 学术 / 机构 / 媒体）
SOURCE_LEVELS: Dict[str, Dict[str, str]] = {
    "guide": {"code": "guide", "label": "权威指南", "badge": "A"},
    "academic": {"code": "academic", "label": "学术文献", "badge": "B"},
    "institution": {"code": "institution", "label": "机构资料", "badge": "C"},
    "media": {"code": "media", "label": "媒体科普", "badge": "D"},
}

# source_type → 来源等级 默认映射（KB 编辑未显式指定等级时按此推导）
SOURCE_TYPE_TO_LEVEL: Dict[str, str] = {
    "expert_original": "guide",
    "guideline": "guide",
    "literature_rewrite": "academic",
    "academic": "academic",
    "institution": "institution",
    "official": "institution",
    "media": "media",
    "popular": "media",
}

# 低等级来源判定（DR-10：低等级来源不得单独支撑建议）
LOW_LEVELS = frozenset({"media"})

# 月龄档展示文案（与 profiles_api.calc_age_band 的派生值对应）
AGE_BAND_LABELS: Dict[str, str] = {
    "0-6m": "适用：0–6 月龄",
    "6-12m": "适用：6–12 月龄",
    "1-3y": "适用：1–3 岁",
    "3-6y": "适用：3–6 岁",
}

# 宠龄档展示文案
PET_AGE_LABELS: Dict[str, str] = {
    "junior": "适用：幼年（<1 岁）",
    "adult": "适用：成年（1–7 岁）",
    "senior": "适用：老年（>7 岁）",
}

# 无档案提问时的通用区间标识（AC-RQ07-4）
GENERIC_AGE_LABEL = "适用：通用区间"
GENERIC_AGE_HINT = "建档后可按月龄适配"

# 要素缺失态文案（不静默隐藏）
MISSING_LABEL = "信息待补"

# 信任检查单 10 项（§3.7.3）
CHECKLIST_ITEMS = (
    "ai_label_visible",
    "disclaimer_attached",
    "age_adapted",
    "source_level_visible",
    "triage_badge_consistent",
    "contraindications_pinned",
    "no_deterministic_conclusion",
    "no_anthropomorphic_wording",
    "crisis_channel_from_list",
    "share_export_labeled",
)


def source_level_of(kb_entry: Any) -> Dict[str, str]:
    """解析知识条目的来源等级（显式字段优先，其次按 source_type 推导）。

    Args:
        kb_entry: KbEntry 实例或含 source_level/source_type 的字典。

    Returns:
        来源等级字典（code/label/badge）；无法判定时返回 institution 兜底。
    """
    def _get(name: str) -> Optional[str]:
        """读取属性或字典键（兼容 ORM 与 dict 输入）。"""
        if isinstance(kb_entry, dict):
            return kb_entry.get(name)
        return getattr(kb_entry, name, None)

    level = (_get("source_level") or "").strip().lower()
    if level not in SOURCE_LEVELS:
        level = SOURCE_TYPE_TO_LEVEL.get((_get("source_type") or "").strip().lower(), "")
    return dict(SOURCE_LEVELS.get(level, SOURCE_LEVELS["institution"]))


def age_adaptation(
    profile_bound: bool,
    age_band: Optional[str],
    domain: str = "child",
    age_months: Optional[int] = None,
) -> Dict[str, Any]:
    """构造月龄 / 宠龄适配标识。

    Args:
        profile_bound: 会话是否绑定档案。
        age_band: 档案派生年龄段（0-6m / 6-12m / 1-3y / 3-6y 或 junior/adult/senior）。
        domain: child / pet。
        age_months: 儿童月龄（可选，用于附加精确月龄）。

    Returns:
        `{label, source, band, months, generic}` 字典。
    """
    if not profile_bound or not age_band:
        return {
            "label": GENERIC_AGE_LABEL,
            "hint": GENERIC_AGE_HINT,
            "source": "generic",
            "band": None,
            "months": None,
            "generic": True,
        }
    mapping = PET_AGE_LABELS if domain == "pet" else AGE_BAND_LABELS
    label = mapping.get(age_band) or GENERIC_AGE_LABEL
    if domain == "child" and age_months is not None:
        label = f"{label}（{int(age_months)} 月龄）"
    return {
        "label": label,
        "hint": None,
        "source": f"profile.{'pet' if domain == 'pet' else 'child'}",
        "band": age_band,
        "months": age_months,
        "generic": False,
    }


def build_source_levels(db: Any, kb_refs: Iterable[str], limit: int = 3) -> List[Dict[str, Any]]:
    """装配来源等级徽标列表（点击展示来源摘要，不展示原始链接）。

    Args:
        db: 数据库会话。
        kb_refs: 本次回答引用的知识条目编码。
        limit: 最多展示条数。

    Returns:
        [{kb_id, title, level, level_label, badge, applicable}] 列表；
        条目不存在或缺失等级时以 missing=True 标注，不静默丢弃。
    """
    refs = [str(x) for x in (kb_refs or []) if x]
    if not refs:
        return []
    rows = db.query(KbEntry).filter(KbEntry.kb_id.in_(refs)).all() if db else []
    by_id = {row.kb_id: row for row in rows}
    out: List[Dict[str, Any]] = []
    for kb_id in refs[:limit]:
        row = by_id.get(kb_id)
        if row is None:
            out.append(
                {
                    "kb_id": kb_id,
                    "title": MISSING_LABEL,
                    "level": None,
                    "level_label": MISSING_LABEL,
                    "badge": "-",
                    "missing": True,
                    "applicable": None,
                }
            )
            continue
        level = source_level_of(row)
        explicit = bool(getattr(row, "source_level", None))
        out.append(
            {
                "kb_id": kb_id,
                "title": row.title,
                "level": level["code"],
                "level_label": level["label"],
                "badge": level["badge"],
                # AC-RQ07-3：来源摘要只给适用范围说明，不展示原始链接
                "applicable": (row.preconditions or "")[:60] or None,
                "missing": not explicit,
                "low_level": level["code"] in LOW_LEVELS,
            }
        )
    return out


def build_trust_bar(
    db: Any,
    triage: Optional[Dict[str, Any]],
    kb_refs: Iterable[str],
    profile_bound: bool = False,
    age_band: Optional[str] = None,
    domain: str = "child",
    age_months: Optional[int] = None,
    channels: Optional[List[dict]] = None,
    contraindications: Optional[List[str]] = None,
    text_sample: str = "",
    has_share_label: bool = True,
) -> Dict[str, Any]:
    """装配首答信任条 + 信任检查单结果。

    Args:
        db: 数据库会话（来源等级查询）。
        triage: 分级结果（RQ-06，可为 None）。
        kb_refs: 本次回答引用的知识条目编码。
        profile_bound: 是否绑定档案。
        age_band: 档案年龄段。
        domain: child / pet。
        age_months: 儿童月龄。
        channels: 危机渠道卡片（RJ-03 来源校验）。
        contraindications: 禁忌项列表（AC-RQ07-2 置顶校验）。
        text_sample: 回答正文抽样（确定性结论 / 拟人化表述扫描）。
        has_share_label: 分享 / 导出载体标识是否完整（AC-RQ01）。

    Returns:
        trust_bar 字典（含 elements / missing / checklist / complete）。
    """
    from ..triage import engine as triage_engine

    age_info = age_adaptation(profile_bound, age_band, domain=domain, age_months=age_months)
    sources = build_source_levels(db, kb_refs)
    source_ok = bool(sources) and all(not s.get("missing") for s in sources)

    deterministic_hits = triage_engine.scan_deterministic_phrases(text_sample or "")
    from ..compliance.copy_scan import scan_anthropomorphic

    anthropomorphic_hits = scan_anthropomorphic(text_sample or "")

    channel_missing = False
    if channels:
        # 渠道卡必须来自清单表（有 channel_code 即来自清单；号码为空是占位态）
        channel_missing = any(not item.get("channel_code") for item in channels)

    contraindications = list(contraindications or [])
    if triage:
        contraindications = list(triage.get("contraindications") or []) or contraindications

    elements: Dict[str, Any] = {
        "ai_label": {"status": "present", "position": labels.PAGE_POSITIONS["answer"]},
        "disclaimer": {"status": "present", "text_id": "DISCLAIMER_V1"},
        "age_adaptation": {
            "status": "present" if not age_info["generic"] else "generic",
            "label": age_info["label"],
        },
        "source_level": {
            "status": "present" if source_ok else ("missing" if not sources else "partial"),
            "items": sources,
        },
        "triage_badge": {
            "status": "present" if (triage and triage.get("level")) else "absent",
            "level": (triage or {}).get("level"),
            "label": (triage or {}).get("level_label"),
        },
        "contraindications": {
            "status": "present" if contraindications else "absent",
            "count": len(contraindications),
            "pinned": bool(contraindications),
        },
        "deterministic_scan": {
            "status": "pass" if not deterministic_hits else "fail",
            "hits": deterministic_hits,
        },
        "anthropomorphic_scan": {
            "status": "pass" if not anthropomorphic_hits else "fail",
            "hits": anthropomorphic_hits,
        },
        "crisis_channel": {
            "status": "absent" if not channels else ("missing" if channel_missing else "present"),
            "count": len(channels or []),
        },
        "share_export_label": {"status": "present" if has_share_label else "missing"},
    }
    missing = [
        name for name, value in elements.items() if value.get("status") in ("missing", "partial")
    ]

    checklist = {
        "ai_label_visible": True,
        "disclaimer_attached": True,
        "age_adapted": not age_info["generic"],
        "source_level_visible": source_ok,
        "triage_badge_consistent": elements["triage_badge"]["status"] == "present",
        "contraindications_pinned": elements["contraindications"]["pinned"],
        "no_deterministic_conclusion": not deterministic_hits,
        "no_anthropomorphic_wording": not anthropomorphic_hits,
        "crisis_channel_from_list": not channel_missing,
        "share_export_labeled": has_share_label,
    }
    return {
        "ai_label": labels.ai_label("answer"),
        "age_adaptation": age_info,
        "source_levels": sources,
        "triage_badge": (
            {
                "level": (triage or {}).get("level"),
                "label": (triage or {}).get("level_label"),
                "icon": (triage or {}).get("icon"),
                "color": (triage or {}).get("level_color"),
            }
            if triage and triage.get("level")
            else None
        ),
        "elements": elements,
        "missing": missing,
        "complete": not missing,
        "checklist": checklist,
        "checklist_total": len(CHECKLIST_ITEMS),
        "checklist_passed": sum(1 for value in checklist.values() if value),
    }


def log_missing(trust_bar: Dict[str, Any], session_uid: Optional[str] = None) -> None:
    """记录信任条要素缺失（埋点 `trust_bar_missing` 的服务端留痕）。

    Args:
        trust_bar: 信任条字典。
        session_uid: 会话标识（日志关联用）。
    """
    missing = trust_bar.get("missing") or []
    if missing:
        logger.info("trust_bar_missing session=%s elements=%s", session_uid, missing)

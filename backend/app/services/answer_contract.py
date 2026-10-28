# -*- coding: utf-8 -*-
"""回答交付契约装配（AI 标识 / 免责 / 信任条 / 分级档位）。

为什么单列一个模块：V3.1 起回答载荷新增了三类服务端强制下发的合规要素
（RQ-01 标识、RQ-06 档位、RQ-07 信任条），它们必须**同时**出现在 SSE
`completed` 帧、轮询兜底 `GET /qa/sessions/{uid}`、断线续发与历史详情里，
任何一处缺失都构成「标识或信任要素缺失」的合规缺陷。把装配逻辑收敛到本
模块，四处调用同一函数，避免口径漂移。

契约字段（前端只渲染，不自造文案）：

```
{
  "ai_label": {visible, text_id, position, fallback_text, filing_no},
  "disclaimer_id": "DISCLAIMER_V1",
  "trust_bar": {...},        # RQ-07 四要素 + 检查单
  "triage": {...} | null,    # RQ-06 档位（无分级场景为 null）
  "age_adaptation": {...},
  "source_levels": [...]
}
```
"""
from typing import Any, Dict, List, Optional

from . import trust_service

# 免责文案 ID（服务端下发，前端不得硬编码）
DISCLAIMER_ID = "DISCLAIMER_V1"


def resolve_profile_context(db: Any, session: Any) -> Dict[str, Any]:
    """解析会话绑定档案的上下文（域 / 月龄 / 物种）。

    Args:
        db: 数据库会话。
        session: QaSession 实例（可含 profile_type/profile_id/entry）。

    Returns:
        {domain, profile_bound, age_band, age_months, species, profile_uid} 字典。
    """
    from ..models import ChildProfile, PetProfile

    domain = "pet" if getattr(session, "entry", None) == "pet" else "child"
    profile_type = getattr(session, "profile_type", None)
    profile_id = getattr(session, "profile_id", None)
    ctx: Dict[str, Any] = {
        "domain": domain,
        "profile_bound": False,
        "age_band": None,
        "age_months": None,
        "species": None,
        "profile_uid": None,
    }
    if not profile_id or db is None:
        return ctx
    if profile_type == "child":
        child = (
            db.query(ChildProfile)
            .filter(ChildProfile.id == profile_id, ChildProfile.status == "active")
            .first()
        )
        if child is not None:
            ctx.update(
                {
                    "domain": "child",
                    "profile_bound": True,
                    "age_band": child.age_band,
                    "age_months": int(child.age_months or 0),
                    "profile_uid": child.profile_uid,
                }
            )
    elif profile_type == "pet":
        pet = db.query(PetProfile).filter(PetProfile.id == profile_id).first()
        if pet is not None:
            ctx.update(
                {
                    "domain": "pet",
                    "profile_bound": True,
                    "age_band": pet.age_band,
                    "species": pet.pet_type,
                    "profile_uid": pet.pet_uid,
                }
            )
    return ctx


def build_answer_contract(
    db: Any,
    session: Any,
    triage: Optional[Dict[str, Any]] = None,
    kb_refs: Optional[List[str]] = None,
    channels: Optional[List[dict]] = None,
    text_sample: str = "",
    profile_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """装配回答交付契约（标识 + 免责 + 信任条 + 档位）。

    Args:
        db: 数据库会话。
        session: QaSession 实例。
        triage: 分级结果（RQ-06）。
        kb_refs: 引用知识条目编码。
        channels: 危机渠道卡片。
        text_sample: 回答正文抽样（确定性结论 / 拟人化表述扫描）。
        profile_ctx: 预解析的档案上下文（缺省内部解析）。

    Returns:
        契约字典（见模块 docstring）。
    """
    if profile_ctx is None:
        profile_ctx = resolve_profile_context(db, session)
    trust = trust_service.build_trust_bar(
        db,
        triage=triage,
        kb_refs=kb_refs or [],
        profile_bound=bool(profile_ctx.get("profile_bound")),
        age_band=profile_ctx.get("age_band"),
        domain=profile_ctx.get("domain") or "child",
        age_months=profile_ctx.get("age_months"),
        channels=channels,
        contraindications=(triage or {}).get("contraindications"),
        text_sample=text_sample,
    )
    trust_service.log_missing(trust, getattr(session, "session_uid", None))
    return {
        "ai_label": trust["ai_label"],
        "disclaimer_id": DISCLAIMER_ID,
        "trust_bar": trust,
        "triage": triage,
        "age_adaptation": trust["age_adaptation"],
        "source_levels": trust["source_levels"],
    }


def contract_for_blocked(db: Any, session: Any, channels: Optional[List[dict]] = None) -> Dict[str, Any]:
    """被拦截会话的契约（拦截页同样带 AI 标识与渠道卡，AC-RQ01-1）。

    Args:
        db: 数据库会话。
        session: QaSession 实例。
        channels: 渠道卡片。

    Returns:
        契约字典（triage=None，信任条按无引用装配）。
    """
    from ..compliance import ai_label as labels

    return {
        "ai_label": labels.ai_label("blocked"),
        "disclaimer_id": DISCLAIMER_ID,
        "trust_bar": None,
        "triage": None,
        "channels": channels or [],
    }


def contract_from_stored(
    db: Any,
    session: Any,
    kb_refs: Optional[List[str]] = None,
    sections: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """从已落库会话重建契约（轮询兜底 / 断线续发 / 历史详情用）。

    Args:
        db: 数据库会话。
        session: QaSession 实例（含 triage / kb_refs 列）。
        kb_refs: 引用条目（缺省取会话列）。
        sections: 已落库分节（用于正文抽样扫描）。

    Returns:
        契约字典。
    """
    text_sample = ""
    for section in sections or []:
        for block in section.get("blocks", []) or []:
            content = block.get("content")
            if isinstance(content, str):
                text_sample += content + "\n"
    return build_answer_contract(
        db,
        session,
        triage=getattr(session, "triage", None),
        kb_refs=kb_refs if kb_refs is not None else (getattr(session, "kb_refs", None) or []),
        text_sample=text_sample,
    )

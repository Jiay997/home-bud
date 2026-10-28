# -*- coding: utf-8 -*-
"""分级决策 API 模块（RQ-06）。

端点：

- GET  /triage/decide                 独立分级判定（便于追问 / 复评 / 联调核验）
- POST /qa/sessions/{uid}/triage/recheck  追问后重判并落库（含档位变化提示）

判定由服务端规则引擎完成（毫秒级），模型不参与档位裁决。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser, ChildProfile, PetProfile, QaSession
from ...triage import engine as triage_engine
from .consent_api import require_base_consent

logger = logging.getLogger("jiaban.triage_api")

router = APIRouter(tags=["C端-问答"])


class RecheckBody(BaseModel):
    """追问重判请求体。

    Attributes:
        followup: 追问 / 补充症状原文（与首轮问题拼接后重判）。
        temperature: 体温读数（可选，显式补充读数时优先）。
        mental_state: 精神状态 normal / poor（可选）。
        duration_hours: 持续小时数（可选）。
    """

    followup: str = Field(..., min_length=1, max_length=500, description="追问原文")
    temperature: Optional[float] = Field(None, description="体温（℃）")
    mental_state: Optional[str] = Field(None, description="精神状态 normal/poor")
    duration_hours: Optional[float] = Field(None, description="持续小时数")


def _load_profiles(db: Session, user: AppUser, session: QaSession):
    """按会话绑定加载档案对象（越权为 None）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        session: 问答会话。

    Returns:
        (child, pet) 二元组。
    """
    child = None
    pet = None
    if session.profile_type == "child" and session.profile_id:
        child = (
            db.query(ChildProfile)
            .filter(
                ChildProfile.id == session.profile_id,
                ChildProfile.user_id == user.id,
                ChildProfile.status == "active",
            )
            .first()
        )
    elif session.profile_type == "pet" and session.profile_id:
        pet = (
            db.query(PetProfile)
            .filter(
                PetProfile.id == session.profile_id,
                PetProfile.user_id == user.id,
            )
            .first()
        )
    return child, pet


@router.get(
    "/triage/decide",
    summary="分级判定（独立）",
    description="按问题与档案（月龄/宠龄）执行规则引擎判定，返回红/黄/绿档位与观察项；未命中分级场景返回 triage=null",
)
def decide_triage(
    question: str = Query(..., min_length=1, max_length=500, description="问题原文"),
    domain: str = Query("child", description="child / pet"),
    profile_uid: Optional[str] = Query(None, max_length=64, description="档案 UID"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """执行分级判定（不落库，供联调与复评使用）。

    Args:
        question: 问题原文。
        domain: 领域 child / pet。
        profile_uid: 档案对外标识（可选）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{triage, rule_snapshot}。

    Raises:
        ApiError: 1001 入口域非法 / 1002 档案不存在或越权。
    """
    require_base_consent(db, user.id)
    if domain not in ("child", "pet"):
        raise ApiError(code=1001, message="domain 必须为 child/pet", http_status=422)
    age_months = None
    age_band = None
    species = None
    if profile_uid:
        child = (
            db.query(ChildProfile)
            .filter(
                ChildProfile.profile_uid == profile_uid,
                ChildProfile.user_id == user.id,
                ChildProfile.status == "active",
            )
            .first()
        )
        if child is not None:
            domain = "child"
            age_months = int(child.age_months or 0)
            age_band = child.age_band
        else:
            pet = (
                db.query(PetProfile)
                .filter(
                    PetProfile.pet_uid == profile_uid,
                    PetProfile.user_id == user.id,
                    PetProfile.deleted_at.is_(None),
                )
                .first()
            )
            if pet is None:
                raise ApiError(*ERR_NOT_FOUND)
            domain = "pet"
            species = pet.pet_type
            age_band = pet.age_band
    snapshot = triage_engine.load_rules(db)
    triage = triage_engine.decide(
        question,
        domain=domain,
        age_months=age_months,
        age_band=age_band,
        species=species,
        snapshot=snapshot,
    )
    return ok(
        {
            "triage": triage,
            "rule_snapshot": triage_engine.rule_summary(snapshot),
            "note": (
                "档位由服务端规则引擎判定，模型不得改写；"
                "未命中分级场景时走常规科普回答。"
            ),
        }
    )


@router.post(
    "/qa/sessions/{session_uid}/triage/recheck",
    summary="追问后重判档位",
    description="把追问内容与首轮问题拼接重判；🟢→🔴 时返回置顶强提醒标记",
)
def recheck_triage(
    session_uid: str,
    body: RecheckBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """追问后重判档位（AC-RQ06-5）。

    Args:
        session_uid: 会话标识。
        body: 追问请求体。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{triage, previous_level, level_changed, escalate_banner}。

    Raises:
        ApiError: 1002 会话不存在或无权限；1301 未同意基础协议。
    """
    require_base_consent(db, user.id)
    session = (
        db.query(QaSession).filter(QaSession.session_uid == session_uid).first()
    )
    if session is None or session.user_id != user.id:
        raise ApiError(*ERR_NOT_FOUND)
    from ...core.crypto import decrypt_field

    try:
        original = decrypt_field(session.question_text_enc)
    except Exception:  # noqa: BLE001 — 解密失败时仅按追问判定
        original = ""
    combined = f"{original} {body.followup}".strip()
    # 显式补充的读数优先（用户可能只说「现在 38.9 度」）
    if body.temperature is not None:
        combined = f"{combined} 体温{body.temperature}度"
    if body.mental_state == "poor":
        combined = f"{combined} 精神状态差 嗜睡"
    elif body.mental_state == "normal":
        combined = f"{combined} 精神状态正常"
    if body.duration_hours:
        combined = f"{combined} 持续{body.duration_hours}小时"
    child, pet = _load_profiles(db, user, session)
    triage = triage_engine.decide_for_session(db, combined, session, child=child, pet=pet)
    previous = session.triage_level
    new_level = (triage or {}).get("level")
    escalate = (
        triage_engine.worst_level([previous, new_level]) == "red"
        and previous != "red"
        and new_level == "red"
    )
    session.triage = triage
    session.triage_level = new_level
    db.commit()
    return ok(
        {
            "session_uid": session.session_uid,
            "triage": triage,
            "previous_level": previous,
            "level_changed": previous != new_level,
            "escalate_banner": escalate,
            "banner_text": (
                "档位已升级为「建议立即就医」：请优先线下就医，不要继续等待观察。"
                if escalate
                else None
            ),
        }
    )

# -*- coding: utf-8 -*-
"""风险申诉与危机渠道 API 模块。

端点：
- POST /risk/appeals            提交误报申诉（备注再过一级流水线，上限 2 次/会话）
- GET  /risk/appeals/{appeal_no} 申诉进度查询（限本人；approved 返回放行窗口）
- GET  /risk/channels           危机干预渠道卡列表

申诉状态机：appeal_submitted/pending_review → approved（24h 放行窗口）/
rejected / abandoned（备注命中硬类别不予受理）。
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.crypto import encrypt_field
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND, ERR_PARAM
from ...db import get_db
from ...models import AppUser, QaSession, RiskAppeal, RiskEvent
from ...risk import HARD_CATEGORIES, LexiconSnapshot, first_pass
from ...risk.service import RiskService

router = APIRouter(prefix="/risk", tags=["C端-问答"])

# 同会话同用户申诉次数上限（数据模型 §3.3：上限 2 次）
MAX_APPEALS_PER_SESSION = 2

# 申诉复核 SLA（小时）
SLA_HOURS = 24

# 上海时区（UTC+8 固定偏移）
_TZ_SHANGHAI = timezone(timedelta(hours=8))


class AppealCreateBody(BaseModel):
    """提交申诉请求体。

    Attributes:
        session_uid: 被拦截会话的对外标识。
        appeal_note: 申诉说明（≤500 字，会再过一级风险流水线）。
    """

    session_uid: str = Field(..., min_length=1, max_length=64, description="会话 UID")
    appeal_note: str = Field(
        ..., min_length=1, max_length=500, description="申诉说明"
    )


def _now() -> datetime:
    """当前上海时区时间。

    Returns:
        带时区 datetime。
    """
    return datetime.now(_TZ_SHANGHAI)


@router.post("/appeals", summary="提交误报申诉", description="备注再过一级流水线；同会话上限 2 次，SLA 24h")
def create_appeal(
    body: AppealCreateBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交误报申诉。

    校验链：会话归属 → 风险事件存在 → 次数上限（2）→ 备注过一级流水线
    （命中硬类别 → abandoned 不予受理）→ 建单 pending_review。

    Args:
        body: 申诉请求体。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({"appeal_no", "sla_due_at", "status"})；备注命中硬类别时
        status=abandoned（note_risk_hit=True）。

    Raises:
        ApiError: 1002 会话/事件不存在或无权限；1001 申诉次数已达上限。
    """
    session = (
        db.query(QaSession).filter(QaSession.session_uid == body.session_uid).first()
    )
    # 越权统一按不存在处理（防枚举）
    if session is None or session.user_id != user.id:
        raise ApiError(*ERR_NOT_FOUND)
    event = (
        db.query(RiskEvent).filter(RiskEvent.session_id == session.id).first()
    )
    if event is None:
        raise ApiError(*ERR_NOT_FOUND)
    # 同会话同用户申诉上限
    count = (
        db.query(RiskAppeal)
        .filter(
            RiskAppeal.session_id == session.id,
            RiskAppeal.user_id == user.id,
        )
        .count()
    )
    if count >= MAX_APPEALS_PER_SESSION:
        raise ApiError(code=1001, message="申诉次数已达上限", http_status=400)
    # 申诉备注再过一级流水线（仅规则引擎，不调语义模型）
    snapshot: LexiconSnapshot = RiskService.load_snapshot(db)
    note_hit = first_pass(body.appeal_note, snapshot)
    appeal_no = f"APL{_now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
    if note_hit is not None and note_hit.get("category_code") in HARD_CATEGORIES:
        # 备注命中硬类别：不予受理（留档 abandoned）
        appeal = RiskAppeal(
            appeal_no=appeal_no,
            session_id=session.id,
            user_id=user.id,
            risk_event_id=event.id,
            appeal_note_enc=encrypt_field(body.appeal_note),
            note_risk_hit=True,
            status="abandoned",
            appeal_count=count + 1,
        )
        db.add(appeal)
        db.commit()
        return ok(
            {
                "appeal_no": appeal_no,
                "sla_due_at": None,
                "status": "abandoned",
                "message": "申诉内容未通过安全校验，不予受理",
            }
        )
    # 正常建单：pending_review，SLA 24h
    appeal = RiskAppeal(
        appeal_no=appeal_no,
        session_id=session.id,
        user_id=user.id,
        risk_event_id=event.id,
        appeal_note_enc=encrypt_field(body.appeal_note),
        note_risk_hit=bool(note_hit),
        status="pending_review",
        sla_due_at=_now() + timedelta(hours=SLA_HOURS),
        appeal_count=count + 1,
    )
    db.add(appeal)
    db.commit()
    return ok(
        {
            "appeal_no": appeal_no,
            "sla_due_at": appeal.sla_due_at.isoformat(),
            "status": appeal.status,
        }
    )


@router.get("/appeals/{appeal_no}", summary="查询申诉进度", description="限本人；approved 返回重提放行窗口")
def get_appeal(
    appeal_no: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询申诉进度（限本人）。

    Args:
        appeal_no: 申诉单号。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({appeal_no, status, sla_due_at, review_result,
        resubmit_allowed, allow_expire_at})——approved 时返回放行窗口。

    Raises:
        ApiError: 1002 申诉单不存在或无权限。
    """
    appeal = db.query(RiskAppeal).filter(RiskAppeal.appeal_no == appeal_no).first()
    if appeal is None or appeal.user_id != user.id:
        raise ApiError(*ERR_NOT_FOUND)
    data: dict = {
        "appeal_no": appeal.appeal_no,
        "status": appeal.status,
        "sla_due_at": appeal.sla_due_at.isoformat() if appeal.sla_due_at else None,
        "review_result": appeal.review_result,
    }
    # approved：返回重提放行窗口（前端据此允许重新提问）
    if appeal.status == "approved":
        expired = (
            appeal.allow_expire_at is not None and appeal.allow_expire_at <= _now()
        )
        data["resubmit_allowed"] = not expired
        data["allow_expire_at"] = (
            appeal.allow_expire_at.isoformat() if appeal.allow_expire_at else None
        )
    return ok(data)


@router.get("/channels", summary="危机干预渠道列表", description="按风险类别过滤的渠道卡（服务端下发）")
def list_channels(
    category: Optional[str] = Query(None, description="风险类别过滤"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """危机干预渠道卡列表（按类别过滤）。

    Args:
        category: 风险类别代码（如 animal_bite；空返回全部）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({"channels": [...]})。

    Raises:
        ApiError: 1001 类别参数非法。
    """
    if category is not None and not category:
        raise ApiError(*ERR_PARAM)
    channels = RiskService.get_channels(db, category)
    return ok({"channels": channels})

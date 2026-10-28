# -*- coding: utf-8 -*-
"""分层同意 API 模块。

提供用户协议/儿童信息单独同意的同意与撤回能力：
- GET  /consent/status    各 consent_type 最新同意状态
- POST /consent/agree     同意（幂等；child_personal_info 强制监护人声明留痕）
- POST /consent/withdraw  撤回（撤回儿童信息同意 → 儿童档案全部置 disabled）

业务口径：同意记录合规留档 ≥3 年；同 (user_id, type, version) 唯一，
撤回后重新同意复用原行（清空 withdraw_at 并刷新 agreed_at）；
撤回儿童信息同意不影响宠物模块使用。
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_BASE_CONSENT, raise_err
from ...db import get_db
from ...models import AppUser, ChildProfile, ConsentRecord

router = APIRouter(tags=["C端-认证同意"])

# 本版本支持的同意类型清单（状态查询按此遍历）
CONSENT_TYPES = ("base", "child_personal_info")

# 基础同意类型标识（用户协议 / 免责声明 / AI 标识）
BASE_CONSENT_TYPE = "base"

# 儿童信息单独同意类型标识
CHILD_CONSENT_TYPE = "child_personal_info"

# 监护人声明式核验方法标识（child_personal_info 留痕用）
GUARDIAN_METHOD_DECLARATION = "declaration"


def has_active_consent(db: Session, user_id: int, consent_type: str) -> bool:
    """判断用户某类型同意是否处于有效状态（未撤回）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        consent_type: 同意类型（base / child_personal_info）。

    Returns:
        存在未撤回的同意记录返回 True。
    """
    active = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.withdraw_at.is_(None),
        )
        .first()
    )
    return active is not None


def require_base_consent(db: Session, user_id: int) -> None:
    """前置校验：必须已完成基础同意（用户协议 / 免责声明 / AI 标识）。

    PRD §4.2 N1「同意节点不可跳过」的服务端强制点：问答与测评等核心功能
    入口统一调用本函数，未同意直接 1301，避免「不落库、不进入」被绕过。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        None。

    Raises:
        ApiError: 1301 请先同意用户协议与免责声明（HTTP 403）。
    """
    if not has_active_consent(db, user_id, BASE_CONSENT_TYPE):
        raise_err(ERR_BASE_CONSENT)


class AgreeBody(BaseModel):
    """同意请求体。

    Attributes:
        consent_type: 同意类型（base / child_personal_info）。
        consent_version: 协议版本，默认 V1。
        guardian_name: 监护人声明姓名（儿童信息类型可选填写）。
    """

    consent_type: str = Field(description="同意类型：base / child_personal_info")
    consent_version: Optional[str] = Field(
        default=None, max_length=32, description="协议版本，默认 V1"
    )
    guardian_name: Optional[str] = Field(
        default=None, max_length=64, description="监护人声明姓名（儿童信息类型）"
    )


class WithdrawBody(BaseModel):
    """撤回请求体。

    Attributes:
        consent_type: 撤回的同意类型。
    """

    consent_type: str = Field(description="撤回类型：base / child_personal_info")


def _validate_consent_type(consent_type: str) -> str:
    """校验同意类型合法性与类型标注。

    Args:
        consent_type: 前端传入的同意类型。

    Returns:
        校验通过的同意类型。

    Raises:
        ApiError: 1001 类型不在支持清单中。
    """
    if consent_type not in CONSENT_TYPES:
        raise ApiError(
            code=1001,
            message="consent_type 仅支持 base / child_personal_info",
            http_status=422,
        )
    return consent_type


def _latest_consent(
    db: Session, user_id: int, consent_type: str, only_active: bool = False
) -> Optional[ConsentRecord]:
    """查询用户某类型最新一条同意记录。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        consent_type: 同意类型。
        only_active: True 时仅查未撤回记录。

    Returns:
        ConsentRecord 实例或 None。
    """
    query = db.query(ConsentRecord).filter(
        ConsentRecord.user_id == user_id,
        ConsentRecord.consent_type == consent_type,
    )
    if only_active:
        # 未撤回 = withdraw_at 为空
        query = query.filter(ConsentRecord.withdraw_at.is_(None))
    return query.order_by(ConsentRecord.id.desc()).first()


def _consent_view(record: Optional[ConsentRecord]) -> Dict[str, Any]:
    """构造单类型同意状态视图。

    Args:
        record: 最新同意记录（可为 None 表示从未同意）。

    Returns:
        {agreed, version, agreed_at, withdraw_at} 字典。
    """
    if record is None:
        return {"agreed": False, "version": None, "agreed_at": None, "withdraw_at": None}
    # withdraw_at 非空视为已撤回
    return {
        "agreed": record.withdraw_at is None,
        "version": record.consent_version,
        "agreed_at": record.agreed_at.isoformat() if record.agreed_at else None,
        "withdraw_at": record.withdraw_at.isoformat() if record.withdraw_at else None,
    }


@router.get("/consent/status", summary="查询同意状态", description="各 consent_type 最新同意/撤回状态")
def consent_status(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """查询当前用户各 consent_type 的最新同意状态。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{base: {agreed, version, agreed_at}, child_personal_info: {...}}。
    """
    status = {
        ctype: _consent_view(_latest_consent(db, user.id, ctype))
        for ctype in CONSENT_TYPES
    }
    return ok(status)


@router.post("/consent/agree", summary="同意协议", description="幂等同意；儿童信息类型强制监护人声明留痕")
def agree_consent(
    body: AgreeBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """同意协议（幂等）：同 (user, type, version) 已存在且未撤回直接返回。

    child_personal_info 类型强制 guardian_verified=True、method="declaration"
    留痕；撤回后重新同意时复用原行（清空 withdraw_at、刷新 agreed_at），
    以满足 (user_id, type, version) 唯一约束。

    Args:
        body: {consent_type, consent_version?, guardian_name?}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{consent_type, consent_version, agreed_at, idempotent}。

    Raises:
        ApiError: 1001 consent_type 非法。
    """
    ctype = _validate_consent_type(body.consent_type)
    # 协议版本默认 V1（文案由 /texts 接口按版本下发）
    version = body.consent_version or "V1"
    now = datetime.now(timezone.utc)
    is_child = ctype == "child_personal_info"

    record = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.user_id == user.id,
            ConsentRecord.consent_type == ctype,
            ConsentRecord.consent_version == version,
        )
        .first()
    )
    idempotent = False
    if record is not None and record.withdraw_at is None:
        # 已同意同版本：幂等返回，不重复落库
        idempotent = True
    elif record is not None:
        # 曾撤回：复用原行重新生效（唯一约束不允许新插同版本行）
        record.withdraw_at = None
        record.agreed_at = now
        if is_child:
            record.guardian_verified = True
            record.guardian_verified_method = GUARDIAN_METHOD_DECLARATION
    else:
        record = ConsentRecord(
            user_id=user.id,
            consent_type=ctype,
            consent_version=version,
            # 儿童信息为单独同意：监护人声明式核验留痕
            guardian_verified=is_child,
            guardian_verified_method=GUARDIAN_METHOD_DECLARATION if is_child else None,
            agreed_at=now,
        )
        db.add(record)
        db.flush()
    return ok({
        "consent_type": ctype,
        "consent_version": version,
        "agreed_at": record.agreed_at.isoformat() if record.agreed_at else None,
        "idempotent": idempotent,
    })


@router.post("/consent/withdraw", summary="撤回同意", description="写 withdraw_at；撤回儿童信息同意联动禁用全部儿童档案")
def withdraw_consent(
    body: WithdrawBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """撤回同意：写 withdraw_at；撤回儿童信息同意时联动禁用全部儿童档案。

    宠物模块不受儿童信息撤回影响（响应中明确说明）。

    Args:
        body: {consent_type}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{consent_type, withdrawn, withdrawn_at?, impact?}，
        impact 含被禁用儿童档案数与宠物模块可用性说明。

    Raises:
        ApiError: 1001 consent_type 非法。
    """
    ctype = _validate_consent_type(body.consent_type)
    now = datetime.now(timezone.utc)

    record = _latest_consent(db, user.id, ctype, only_active=True)
    if record is None:
        # 无有效同意记录：幂等返回（撤回是安全侧操作，不报错）
        return ok({"consent_type": ctype, "withdrawn": False})

    # 撤回 = 在原记录上写 withdraw_at（保留原版本与同意时间用于审计）
    record.withdraw_at = now

    impact: Dict[str, Any] = {}
    if ctype == "child_personal_info":
        # 撤回儿童信息同意 → 全部儿童档案置 disabled（数据保留、停止展示与使用）
        disabled_count = (
            db.query(ChildProfile)
            .filter(ChildProfile.user_id == user.id, ChildProfile.status == "active")
            .update({"status": "disabled"}, synchronize_session=False)
        )
        impact = {
            "child_profiles_disabled": disabled_count,
            "pet_module_affected": False,
            "note": "已禁用全部儿童档案；宠物模块不受影响，可继续使用",
        }
    return ok({
        "consent_type": ctype,
        "withdrawn": True,
        "withdrawn_at": now.isoformat(),
        "impact": impact,
    })

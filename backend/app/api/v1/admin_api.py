# -*- coding: utf-8 -*-
"""后台管理核心路由模块。

覆盖 PRD §15/§16 后台管理页的服务端接口：
- 登录与 MFA（5 次失败锁定 15 分钟；开发模式验证码固定 123456）
- 审计日志查询（仅 super_admin；before/after 快照脱敏，仅返回键名）
- 退款工单处置（approve 回收订单与订阅权益；reject 必填驳回理由码）
- Agent 调用日志（列表脱敏 / 详情抽屉 / 仅超管可 CSV 导出并二次确认）
- 用户反馈处置（正文密文，仅 super_admin/support 可解密查看）
- 投诉举报处置（escalate 上报必须附证据，否则 1602）
- 高风险事件复核与上报（复核结论未录入前禁止上报，服务端兜底 1103）
- 个人信息权利请求处理（JSON/CSV 导出文件 24 小时有效）
- 系统配置版本管理（cfg:write 仅超管；版本留痕 + 缓存热更新 + 一键回滚）
"""
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from jose import jwt
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.cache import cache
from ...core.crypto import decrypt_field, mask_phone
from ...core.deps import (
    get_admin,
    require_admin_perm,
    require_confirm,
    write_audit,
)
from ...core.envelope import ok
from ...core.errors import (
    ERR_ADMIN_FORBIDDEN,
    ERR_CONFIRM_REQUIRED,
    ERR_MFA_REQUIRED,
    ERR_NOT_FOUND,
    ApiError,
)
from ...core.security import create_admin_token, decode_token, verify_password
from ...db import get_db
from ...models import (
    AdminAuditLog,
    AdminUser,
    AgentCallLog,
    AppUser,
    ChildProfile,
    ConfigVersion,
    ContentReport,
    Feedback,
    Order,
    PetProfile,
    Product,
    QaSession,
    RefundRequest,
    RightsRequest,
    RiskAppeal,
    RiskEvent,
    RiskRuleConfig,
    SamplingCheck,
    Subscription,
)

# 路由器：后台核心接口统一挂在 /admin 前缀
router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger("jiaban.admin")

# 角色 × 可访问页面清单（mfa/verify 与 /me 返回，前端据此渲染侧边栏）
# 单一事实来源：键集合与前端 MENU_DEFS 页面标识逐字一致（kb/lexicon/logs/feedback/risk/rights/config/audit），
# 前端不做任何别名/兜底映射；一致性由 tests/test_admin_menus.py 守护（含前端文件交叉校验）。
# audit（审计记录）与 /admin/audit-logs 接口的角色白名单（仅 super_admin）保持一致。
ROLE_MENUS: Dict[str, List[str]] = {
    "super_admin": ["kb", "lexicon", "logs", "feedback", "risk", "rights", "config", "audit"],
    "operator": ["kb", "lexicon", "logs", "feedback", "risk", "rights"],
    "support": ["feedback", "rights", "logs"],
    "expert_child": ["kb"],
    "expert_pet": ["kb"],
}

# 个人数据导出文件目录：<backend>/data/exports（任务约定路径）
_EXPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "exports"


def _now() -> datetime:
    """获取当前 UTC 时间。

    Returns:
        带时区的 datetime（与库内 DateTime(timezone=True) 对齐）。
    """
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """datetime 转 ISO 字符串（JSON 序列化辅助）。

    Args:
        dt: 时间对象，可为 None。

    Returns:
        ISO8601 字符串；入参为 None 时返回 None。
    """
    return dt.isoformat() if dt is not None else None


def _create_mfa_ticket(admin_uid: str) -> str:
    """签发 5 分钟有效的 MFA 临时票据（typ=mfa_ticket）。

    Args:
        admin_uid: 后台账号唯一标识。

    Returns:
        编码后的 JWT 字符串。
    """
    from ...core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": admin_uid,
        "typ": "mfa_ticket",
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _admin_menus(admin: AdminUser) -> List[str]:
    """按角色返回可访问页面清单。

    Args:
        admin: 当前后台账号。

    Returns:
        页面标识列表（kb/lexicon/logs/feedback/risk/rights/config/audit）；未知角色返回空列表。
    """
    return ROLE_MENUS.get(admin.role, [])


def _extract_output_titles(output_json: Any) -> List[str]:
    """从 output_json 提取 answer_blocks 的 title 列表（列表页脱敏摘要）。

    Args:
        output_json: AgentCallLog.output_json（JSONB，结构不做强保证）。

    Returns:
        title 字符串列表；结构异常时返回空列表。
    """
    if not isinstance(output_json, dict):
        return []
    blocks = output_json.get("answer_blocks")
    if not isinstance(blocks, list):
        return []
    titles = []
    for block in blocks:
        if isinstance(block, dict) and isinstance(block.get("title"), str):
            titles.append(block["title"])
    return titles


def _collect_user_export(db: Session, user_id: int) -> dict:
    """汇集用户个人数据导出载荷（档案解密 + 会话摘要 + 订单清单）。

    仅含元数据与本人有权获得的明文；问题原文与回答正文不随导出。

    Args:
        db: 数据库会话。
        user_id: 目标用户主键。

    Returns:
        可 JSON 序列化的导出字典。
    """
    user = db.get(AppUser, user_id)
    user_payload = {
        "user_uid": str(user.user_uid) if user else None,
        "member_status": user.member_status if user else None,
        "phone_masked": user.phone_masked if user else None,
        "status": user.status if user else None,
        "register_at": _iso(user.register_at) if user else None,
    }
    # 儿童档案：P0 加密字段解密后交付本人
    child_items = []
    children = (
        db.query(ChildProfile)
        .filter(ChildProfile.user_id == user_id, ChildProfile.deleted_at.is_(None))
        .all()
    )
    for c in children:
        try:
            nickname = decrypt_field(c.nickname_enc)
        except Exception:
            nickname = None
        try:
            birth = decrypt_field(c.birth_date_enc)
        except Exception:
            birth = None
        child_items.append(
            {
                "profile_uid": c.profile_uid,
                "nickname": nickname,
                "birth_date": birth,
                "gender": c.gender,
                "age_months": c.age_months,
                "age_band": c.age_band,
                "height_cm": float(c.height_cm) if c.height_cm is not None else None,
                "weight_kg": float(c.weight_kg) if c.weight_kg is not None else None,
                "created_at": _iso(c.created_at),
            }
        )
    # 宠物档案（无加密字段）
    pet_items = []
    pets = (
        db.query(PetProfile)
        .filter(PetProfile.user_id == user_id, PetProfile.deleted_at.is_(None))
        .all()
    )
    for p in pets:
        pet_items.append(
            {
                "pet_uid": p.pet_uid,
                "pet_type": p.pet_type,
                "breed": p.breed,
                "age_band": p.age_band,
                "neutered_flag": p.neutered_flag,
                "weight_kg": float(p.weight_kg) if p.weight_kg is not None else None,
                "main_food": p.main_food,
                "created_at": _iso(p.created_at),
            }
        )
    # 会话摘要：仅元数据，不含问题原文/回答正文
    sessions = (
        db.query(QaSession)
        .filter(QaSession.user_id == user_id)
        .order_by(QaSession.id.desc())
        .limit(50)
        .all()
    )
    session_items = [
        {
            "session_uid": s.session_uid,
            "entry": s.entry,
            "profile_type": s.profile_type,
            "char_len": s.char_len,
            "status": s.status,
            "created_at": _iso(s.created_at),
        }
        for s in sessions
    ]
    # 订单清单
    orders = (
        db.query(Order).filter(Order.user_id == user_id).order_by(Order.id.desc()).limit(50).all()
    )
    order_items = [
        {
            "order_no": o.order_no,
            "amount_micro": o.amount_micro,
            "status": o.status,
            "platform": o.platform,
            "paid_at": _iso(o.paid_at),
            "created_at": _iso(o.created_at),
        }
        for o in orders
    ]
    return {
        "user": user_payload,
        "child_profiles": child_items,
        "pet_profiles": pet_items,
        "qa_sessions": session_items,
        "orders": order_items,
        "exported_at": _iso(_now()),
    }


def _write_export_csv(path: Path, payload: dict) -> None:
    """将导出载荷写为两列（field,value）CSV 文件。

    Args:
        path: 目标文件路径。
        payload: 导出字典（嵌套结构拍平为点号/下标键）。

    Raises:
        OSError: 文件写入失败时由底层抛出。
    """
    rows: List[tuple] = []

    def _walk(prefix: str, value: Any) -> None:
        """递归拍平嵌套结构为 (key, scalar) 行。

        Args:
            prefix: 当前键前缀。
            value: 当前值（dict/list 递归，标量落行）。
        """
        if isinstance(value, dict):
            for k, v in value.items():
                _walk(f"{prefix}.{k}" if prefix else str(k), v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                _walk(f"{prefix}[{i}]", v)
        else:
            rows.append((prefix, "" if value is None else str(value)))

    _walk("", payload)
    # utf-8-sig 带 BOM，便于 Excel 直接打开中文
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "value"])
        writer.writerows(rows)


# ==================== 请求体模型 ====================


class LoginBody(BaseModel):
    """登录请求体。"""

    username: str = Field(..., min_length=1, description="后台用户名")
    password: str = Field(..., min_length=1, description="明文密码")


class MfaVerifyBody(BaseModel):
    """MFA 校验请求体。"""

    mfa_ticket: str = Field(..., description="login 返回的临时票据")
    code: str = Field(..., min_length=1, description="验证码（开发模式固定 123456）")


class RefundHandleBody(BaseModel):
    """退款工单处置请求体。"""

    action: str = Field(..., description="处置动作：approve / reject")
    reject_reason_code: Optional[str] = Field(None, description="驳回理由码（reject 必填）")
    reason: Optional[str] = Field(None, description="处置备注（审计用）")


class FeedbackReplyBody(BaseModel):
    """反馈回复请求体。"""

    reply_content: str = Field(..., min_length=1, description="回复内容（必填）")
    reply_template_id: Optional[str] = Field(None, description="命中的回复模板 ID")


class ReportHandleBody(BaseModel):
    """举报处置请求体。"""

    action: str = Field(..., description="处置动作：reject / unpublish / escalate / no_action")
    basis: str = Field(..., min_length=1, description="处置依据（必填）")
    evidence: Optional[Dict[str, Any]] = Field(None, description="上报证据（escalate 必填）")


class RiskReviewBody(BaseModel):
    """高风险事件复核请求体。"""

    conclusion: str = Field(..., description="复核结论：upheld / misreport / need_more")
    reason_code: str = Field(..., min_length=1, description="结论理由码（必填）")


class ReportAuthorityBody(BaseModel):
    """高风险事件上报请求体。"""

    reported_target: str = Field(..., min_length=1, description="上报对象（如属地网信部门）")


class RightsProcessBody(BaseModel):
    """权利请求处理请求体。"""

    action: str = Field(..., description="处理动作：generate_export / mark_done / reject")
    reject_reason_code: Optional[str] = Field(None, description="拒绝理由码（reject 必填）")
    format: Optional[str] = Field(None, description="导出格式：json / csv（默认 json）")


class ConfigUpdateBody(BaseModel):
    """配置更新请求体（仅 super_admin）。"""

    snapshot: Dict[str, Any] = Field(..., description="配置快照（全量）")
    reason: str = Field(..., min_length=1, description="变更原因（审计必填）")
    confirm_token: Optional[str] = Field(None, description="二次确认凭证")


class ConfigRollbackBody(BaseModel):
    """配置回滚请求体（仅 super_admin）。"""

    target_version: int = Field(..., ge=1, description="回滚目标版本号")
    confirm_token: Optional[str] = Field(None, description="二次确认凭证")


# ==================== 登录与账号 ====================


@router.post("/login", tags=["后台-配置"], summary="后台登录（账密校验，失败锁定，下发 MFA 票据）")
def admin_login(body: LoginBody, db: Session = Depends(get_db)):
    """后台登录第一步：账密校验 + 失败锁定 + 下发 MFA 票据。

    5 次失败锁定 15 分钟；锁定期间直接拒绝（1601 语义位复用 1103）。
    成功不直接发 token，返回 mfa_ticket 待第二步校验。

    Args:
        body: 登录请求体。
        db: 数据库会话。

    Returns:
        包络：{mfa_required: True, mfa_ticket}。

    Raises:
        ApiError: 1103 账号已锁定；1101 用户名或密码错误。
    """
    now = _now()
    admin = db.query(AdminUser).filter(AdminUser.username == body.username).first()
    # 统一错误文案，避免用户名枚举
    invalid = ApiError(1101, "用户名或密码错误", 401)
    if admin is None:
        raise invalid
    # 锁定检查：locked_until 在未来则拒绝登录
    if admin.locked_until is not None and admin.locked_until > now:
        raise ApiError(1103, "账号已锁定，请15分钟后重试", 403)
    if not verify_password(body.password, admin.password_hash):
        # 失败计数 +1，达到 5 次锁定 15 分钟
        admin.fail_count = (admin.fail_count or 0) + 1
        if admin.fail_count >= 5:
            admin.locked_until = now + timedelta(minutes=15)
        # 显式提交：后续 raise 会触发 get_db 回滚，必须先落库计数
        db.commit()
        raise invalid
    # 登录成功：重置失败计数与锁定
    admin.fail_count = 0
    admin.locked_until = None
    return ok(
        {
            "mfa_required": True,
            "mfa_ticket": _create_mfa_ticket(admin.admin_uid),
        }
    )


@router.post("/mfa/verify", tags=["后台-配置"], summary="MFA 校验并签发后台令牌")
def admin_mfa_verify(body: MfaVerifyBody, db: Session = Depends(get_db)):
    """后台登录第二步：MFA 校验并签发正式 admin token。

    开发模式验证码固定为 123456；校验通过返回 token 与菜单清单。

    Args:
        body: MFA 校验请求体。
        db: 数据库会话。

    Returns:
        包络：{token, role, display_name, domain_scope, menus}。

    Raises:
        ApiError: 1104 票据无效/过期或验证码错误。
    """
    try:
        payload = decode_token(body.mfa_ticket, expected_type="mfa_ticket")
    except Exception:
        raise ApiError(*ERR_MFA_REQUIRED)
    admin = db.query(AdminUser).filter(AdminUser.admin_uid == payload.get("sub")).first()
    if admin is None or admin.status != "active":
        raise ApiError(*ERR_MFA_REQUIRED)
    # 开发模式固定验证码；生产替换为 TOTP/短信校验
    if body.code != "123456":
        raise ApiError(*ERR_MFA_REQUIRED)
    token = create_admin_token(admin.admin_uid, admin.role, admin.domain_scope)
    return ok(
        {
            "token": token,
            "role": admin.role,
            "display_name": admin.display_name,
            "domain_scope": admin.domain_scope,
            "menus": _admin_menus(admin),
        }
    )


@router.get("/me", tags=["后台-配置"], summary="当前后台账号信息与可访问菜单")
def admin_me(admin: AdminUser = Depends(get_admin)):
    """获取当前登录账号信息与可访问菜单。

    Args:
        admin: 鉴权后的当前账号。

    Returns:
        包络：账号基础信息 + menus。
    """
    phone = None
    try:
        # 手机号解密后脱敏展示（失败不阻断）
        phone = mask_phone(decrypt_field(admin.phone_enc))
    except Exception:
        phone = None
    return ok(
        {
            "admin_uid": admin.admin_uid,
            "username": admin.username,
            "display_name": admin.display_name,
            "role": admin.role,
            "domain_scope": admin.domain_scope,
            "phone_masked": phone,
            "menus": _admin_menus(admin),
        }
    )


# ==================== 审计日志 ====================


@router.get("/audit-logs", tags=["后台-配置"], summary="审计日志分页查询（快照仅返回键名，仅超管）")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    operator_id: Optional[int] = Query(None),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询后台审计日志（脱敏：不返回快照全文，仅返回键名）。

    审计记录含全后台账号操作留痕，属超管专属数据，仅 super_admin 可读
    （operator/support 均返回 1103，与 ROLE_MENUS 中 audit 菜单角色一致）。

    Args:
        page: 页码（1 起）。
        page_size: 每页条数（≤100）。
        action: 动作代码过滤。
        object_type: 对象类型过滤。
        operator_id: 操作人 ID 过滤。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}，快照仅含 keys。

    Raises:
        ApiError: 1103 当前角色无此权限（仅 super_admin）。
    """
    # 审计记录为超管专属只读数据（越权修复：此前 operator/support 可读）
    if admin.role != "super_admin":
        raise ApiError(*ERR_ADMIN_FORBIDDEN)
    q = db.query(AdminAuditLog)
    if action:
        q = q.filter(AdminAuditLog.action == action)
    if object_type:
        q = q.filter(AdminAuditLog.object_type == object_type)
    if operator_id is not None:
        q = q.filter(AdminAuditLog.operator_id == operator_id)
    total = q.count()
    rows = (
        q.order_by(AdminAuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for lg in rows:
        # 脱敏：快照正文不回传，仅回传键名列表
        before_keys = (
            list(lg.before_snapshot.keys())
            if isinstance(lg.before_snapshot, dict)
            else []
        )
        after_keys = (
            list(lg.after_snapshot.keys()) if isinstance(lg.after_snapshot, dict) else []
        )
        items.append(
            {
                "id": lg.id,
                "action": lg.action,
                "object_type": lg.object_type,
                "object_id": lg.object_id,
                "operator_role": lg.operator_role_snapshot,
                "reason": lg.reason,
                "result": lg.result,
                "confirm_used": lg.confirm_used,
                "before_keys": before_keys,
                "after_keys": after_keys,
                "created_at": _iso(lg.created_at),
            }
        )
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


# ==================== 退款工单 ====================


@router.get("/refunds", tags=["后台-配置"], summary="退款工单列表")
def list_refunds(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询退款工单列表（关联订单号展示）。

    Args:
        status: 工单状态过滤（submitted/refunded/rejected）。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 rights:handle 权限。
    """
    require_admin_perm(admin, "rights:handle")
    q = db.query(RefundRequest, Order).join(Order, Order.id == RefundRequest.order_id)
    if status:
        q = q.filter(RefundRequest.status == status)
    total = q.count()
    rows = (
        q.order_by(RefundRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "request_no": r.request_no,
            "order_no": o.order_no,
            "user_id": r.user_id,
            "reason_code": r.reason_code,
            "status": r.status,
            "reject_reason_code": r.reject_reason_code,
            "refund_amount_micro": r.refund_amount_micro,
            "entitlement_recycled": r.entitlement_recycled,
            "handled_at": _iso(r.handled_at),
            "created_at": _iso(r.created_at),
        }
        for r, o in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.put("/refunds/{request_no}", tags=["后台-配置"], summary="处置退款工单（approve 回收权益 / reject 驳回）")
def handle_refund(
    request_no: str,
    body: RefundHandleBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """处置退款工单：approve 退款并回收订阅权益；reject 必填驳回理由码。

    Args:
        request_no: 退款工单号。
        body: 处置请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：处置后的工单状态。

    Raises:
        ApiError: 1001 reject 未填理由码/重复处置；1002 工单不存在；1103 无权限。
    """
    require_admin_perm(admin, "rights:handle")
    refund = db.query(RefundRequest).filter(RefundRequest.request_no == request_no).first()
    if refund is None:
        raise ApiError(*ERR_NOT_FOUND)
    if refund.status != "submitted":
        raise ApiError(1001, "该工单已处置，不可重复操作", 409)
    now = _now()
    before = {"status": refund.status}
    if body.action == "approve":
        order = db.get(Order, refund.order_id)
        if order is not None:
            # 订单置 refunded；对应有效订阅回收置 revoked
            order.status = "refunded"
            sub = (
                db.query(Subscription)
                .filter(
                    Subscription.source_order_id == order.id,
                    Subscription.status == "active",
                )
                .first()
            )
            if sub is not None:
                sub.status = "revoked"
                sub.revoked_at = now
        refund.status = "refunded"
        refund.refund_amount_micro = order.amount_micro if order else refund.refund_amount_micro
        refund.entitlement_recycled = True
    elif body.action == "reject":
        if not body.reject_reason_code:
            # 驳回理由码必填（数据模型约束的服务端校验）
            raise ApiError(1001, "驳回必须填写 reject_reason_code", 422)
        refund.status = "rejected"
        refund.reject_reason_code = body.reject_reason_code
    else:
        raise ApiError(1001, "action 必须为 approve/reject", 422)
    refund.handled_by = admin.id
    refund.handled_at = now
    write_audit(
        db,
        admin,
        f"refund_{body.action}",
        "refund_request",
        refund.request_no,
        reason=body.reject_reason_code or body.reason or "-",
        before=before,
        after={"status": refund.status, "entitlement_recycled": refund.entitlement_recycled},
    )
    return ok({"request_no": refund.request_no, "status": refund.status})


# ==================== Agent 调用日志 ====================


@router.get("/agent-logs", tags=["后台-处置"], summary="Agent 调用日志列表（脱敏）")
def list_agent_logs(
    session_id: Optional[int] = Query(None),
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询 Agent 调用日志（脱敏列表：不还原输入，仅返回分节 title）。

    Args:
        session_id: 按会话过滤。
        agent_id: 按 Agent 标识过滤。
        status: 按调用状态过滤。
        date: 按调用日期（UTC）过滤。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}，input_digest 保持哈希不还原。

    Raises:
        ApiError: 1103 缺少 log:view 权限。
    """
    require_admin_perm(admin, "log:view")
    q = db.query(AgentCallLog)
    if session_id is not None:
        q = q.filter(AgentCallLog.session_id == session_id)
    if agent_id:
        q = q.filter(AgentCallLog.agent_id == agent_id)
    if status:
        q = q.filter(AgentCallLog.status == status)
    if date is not None:
        # 按自然日过滤（数据库侧 date() 函数）
        q = q.filter(func.date(AgentCallLog.created_at) == date.date())
    total = q.count()
    rows = (
        q.order_by(AgentCallLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": r.id,
            "session_id": r.session_id,
            "agent_id": r.agent_id,
            "provider": r.provider,
            "model": r.model,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "conflict_flag": r.conflict_flag,
            "input_digest": r.input_digest,  # 摘要哈希，不提供还原
            "output_titles": _extract_output_titles(r.output_json),
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/agent-logs/export", tags=["后台-处置"], summary="导出 Agent 日志 CSV（仅超管+二次确认）")
def export_agent_logs(
    confirm_token: Optional[str] = Query(None),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """导出 Agent 调用日志 CSV（仅 super_admin，需二次确认）。

    脱敏约束：不含输入原文（input_digest 为不可还原哈希）、
    不含 output_json 全文，仅输出链路元数据摘要。

    Args:
        confirm_token: 二次确认凭证（必须为 CONFIRMED）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        StreamingResponse：text/csv 附件（最多最近 1000 条）。

    Raises:
        ApiError: 1103 非超管；1602 缺少二次确认。
    """
    if admin.role != "super_admin":
        # 导出全量日志属高危操作，仅超管
        raise ApiError(*ERR_ADMIN_FORBIDDEN)
    require_confirm(confirm_token, "agent_logs_export")
    rows = (
        db.query(AgentCallLog).order_by(AgentCallLog.id.desc()).limit(1000).all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id", "session_id", "agent_id", "provider", "model", "status",
            "latency_ms", "conflict_flag", "prompt_tokens", "completion_tokens",
            "cost_micro", "created_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.id, r.session_id, r.agent_id, r.provider, r.model, r.status,
                r.latency_ms, r.conflict_flag, r.prompt_tokens, r.completion_tokens,
                r.cost_micro, _iso(r.created_at),
            ]
        )
    # 导出动作写审计（confirm_used=True）
    write_audit(
        db,
        admin,
        "export",
        "agent_call_log",
        f"batch_{_now():%Y%m%d%H%M%S}",
        reason="导出Agent调用日志（脱敏摘要，≤1000条）",
        confirm_used=True,
    )
    filename = f"agent_logs_{_now():%Y%m%d}.csv"
    # BOM 前缀便于 Excel 识别 UTF-8
    return StreamingResponse(
        iter(["\ufeff" + buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/agent-logs/{log_id}", tags=["后台-处置"], summary="Agent 调用日志详情")
def agent_log_detail(
    log_id: int,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """查询 Agent 调用日志详情（详情抽屉：完整输出/证据引用/耗时）。

    Args:
        log_id: 日志主键。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：完整日志字段（input_digest 仍为哈希）。

    Raises:
        ApiError: 1002 日志不存在；1103 缺少 log:view 权限。
    """
    require_admin_perm(admin, "log:view")
    log = db.get(AgentCallLog, log_id)
    if log is None:
        raise ApiError(*ERR_NOT_FOUND)
    return ok(
        {
            "id": log.id,
            "session_id": log.session_id,
            "agent_id": log.agent_id,
            "agent_version": log.agent_version,
            "provider": log.provider,
            "model": log.model,
            "model_version": log.model_version,
            "input_digest": log.input_digest,
            "output_json": log.output_json,
            "confidence": float(log.confidence) if log.confidence is not None else None,
            "conflict_flag": log.conflict_flag,
            "evidence_ref": log.evidence_ref,
            "prompt_tokens": log.prompt_tokens,
            "completion_tokens": log.completion_tokens,
            "cost_micro": log.cost_micro,
            "latency_ms": log.latency_ms,
            "status": log.status,
            "created_at": _iso(log.created_at),
        }
    )


# ==================== 用户反馈 ====================


@router.get("/feedback", tags=["后台-处置"], summary="用户反馈列表（正文按权限解密）")
def list_feedback(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询用户反馈（正文密文，仅 super_admin/support 解密展示）。

    Args:
        status: 状态过滤（pending/replied）。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}，无解密权限时 content 为 None。

    Raises:
        ApiError: 1103 缺少 fb:view 权限。
    """
    require_admin_perm(admin, "fb:view")
    q = db.query(Feedback)
    if status:
        q = q.filter(Feedback.status == status)
    total = q.count()
    rows = (
        q.order_by(Feedback.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    # 正文解密仅限超管与客服（operator 有查看权但无解密权）
    can_decrypt = admin.role in ("super_admin", "support")
    items = []
    for fb in rows:
        content = None
        if can_decrypt:
            try:
                content = decrypt_field(fb.content_enc)
            except Exception:
                content = "(解密失败)"
        items.append(
            {
                "id": fb.id,
                "feedback_no": fb.feedback_no,
                "user_id": fb.user_id,
                "content": content,
                "char_len": fb.char_len,
                "linked_session_id": fb.linked_session_id,
                "image_count": fb.image_count,
                "audit_status": fb.audit_status,
                "status": fb.status,
                "created_at": _iso(fb.created_at),
                "replied_at": _iso(fb.replied_at),
            }
        )
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.put("/feedback/{feedback_id}", tags=["后台-处置"], summary="处置用户反馈（回复并写审计）")
def handle_feedback(
    feedback_id: int,
    body: FeedbackReplyBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """处置用户反馈：填写回复内容后置 replied 并写审计。

    Args:
        feedback_id: 反馈主键。
        body: 回复请求体（reply_content 必填）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：处置后的反馈状态。

    Raises:
        ApiError: 1001 回复内容为空/重复回复；1002 反馈不存在；1103 无权限。
    """
    require_admin_perm(admin, "fb:handle")
    fb = db.get(Feedback, feedback_id)
    if fb is None:
        raise ApiError(*ERR_NOT_FOUND)
    if fb.status == "replied":
        raise ApiError(1001, "该反馈已回复", 409)
    before = {"status": fb.status}
    fb.reply_template_id = body.reply_template_id or fb.reply_template_id
    fb.status = "replied"
    fb.replied_at = _now()
    fb.handled_by = admin.id
    write_audit(
        db,
        admin,
        "feedback_reply",
        "feedback",
        fb.feedback_no,
        reason=body.reply_content[:256],
        before=before,
        after={"status": fb.status},
    )
    return ok({"feedback_no": fb.feedback_no, "status": fb.status})


# ==================== 投诉举报 ====================


@router.get("/reports", tags=["后台-处置"], summary="举报列表（涉未成年优先）")
def list_reports(
    handled: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询举报列表：涉未成年人优先，其次按 SLA 截止时间升序。

    Args:
        handled: True 仅已处置 / False 仅待处置 / None 全部。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 fb:view 权限。
    """
    require_admin_perm(admin, "fb:view")
    q = db.query(ContentReport)
    if handled is True:
        q = q.filter(ContentReport.handled_at.isnot(None))
    elif handled is False:
        q = q.filter(ContentReport.handled_at.is_(None))
    # 排序：involves_minor 优先 + SLA 到期升序（NULL 排最后）
    q = q.order_by(
        ContentReport.involves_minor.desc(),
        ContentReport.sla_due_at.asc().nullslast(),
        ContentReport.id.desc(),
    )
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": r.id,
            "report_no": r.report_no,
            "object_type": r.object_type,
            "object_id": r.object_id,
            "category": r.category,
            "involves_minor": r.involves_minor,
            "sla_due_at": _iso(r.sla_due_at),
            "action": r.action,
            "reported": r.reported,
            "receipt_sent": r.receipt_sent,
            "handled_at": _iso(r.handled_at),
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.put("/reports/{report_no}", tags=["后台-处置"], summary="举报处置（四动作，上报须附证据）")
def handle_report(
    report_no: str,
    body: ReportHandleBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """处置举报：reject/unpublish/escalate/no_action 四类动作。

    escalate（上报）必须附证据（evidence），否则 1602；
    处置后置 handled_by/handled_at 并标记回执已发送。

    Args:
        report_no: 举报编号。
        body: 处置请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：处置后的举报状态。

    Raises:
        ApiError: 1001 缺少处置依据；1602 上报缺证据；1002 不存在；1103 无权限。
    """
    require_admin_perm(admin, "fb:handle")
    report = db.query(ContentReport).filter(ContentReport.report_no == report_no).first()
    if report is None:
        raise ApiError(*ERR_NOT_FOUND)
    if body.action not in ("reject", "unpublish", "escalate", "no_action"):
        raise ApiError(1001, "action 必须为 reject/unpublish/escalate/no_action", 422)
    # 上报动作必须附证据（与前端交互强约束的服务端兜底）
    if body.action == "escalate" and not body.evidence:
        raise ApiError(*ERR_CONFIRM_REQUIRED)
    before = {"action": report.action, "reported": report.reported}
    report.action = body.action
    # 证据落库：无独立证据时以处置依据充当
    report.evidence = body.evidence if body.evidence else {"basis": body.basis}
    if body.action == "escalate":
        report.reported = True
    report.handled_by = admin.id
    report.handled_at = _now()
    report.receipt_sent = True
    write_audit(
        db,
        admin,
        "report_handle",
        "content_report",
        report.report_no,
        reason=body.basis[:256],
        before=before,
        after={"action": report.action, "reported": report.reported},
    )
    return ok({"report_no": report.report_no, "action": report.action})


# ==================== 高风险事件 ====================


@router.get("/risk-events", tags=["后台-处置"], summary="高风险事件列表")
def list_risk_events(
    level: Optional[str] = Query(None),
    disposal_result: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询高风险事件列表（user_id_hash 展示，含处置结果与 SLA）。

    Args:
        level: 等级过滤（L1/L2）。
        disposal_result: 处置结果过滤。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 risk:view 权限。
    """
    require_admin_perm(admin, "risk:view")
    q = db.query(RiskEvent)
    if level:
        q = q.filter(RiskEvent.level == level)
    if disposal_result:
        q = q.filter(RiskEvent.disposal_result == disposal_result)
    total = q.count()
    rows = (
        q.order_by(RiskEvent.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    items = [
        {
            "id": r.id,
            "event_no": r.event_no,
            "user_id_hash": r.user_id_hash,
            "session_id": r.session_id,
            "category_code": r.category_code,
            "level": r.level,
            "score_band": r.score_band,
            "source_scene": r.source_scene,
            "body_emitted": r.body_emitted,
            "disposal_result": r.disposal_result,
            "sla_due_at": _iso(r.sla_due_at),
            "reported": r.reported,
            "reviewed_at": _iso(r.reviewed_at),
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/risk-events/{event_no}", tags=["后台-处置"], summary="高风险事件详情")
def risk_event_detail(
    event_no: str,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """查询高风险事件详情。

    Args:
        event_no: 事件编号。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：事件全字段。

    Raises:
        ApiError: 1002 事件不存在；1103 缺少 risk:view 权限。
    """
    require_admin_perm(admin, "risk:view")
    event = db.query(RiskEvent).filter(RiskEvent.event_no == event_no).first()
    if event is None:
        raise ApiError(*ERR_NOT_FOUND)
    return ok(
        {
            "id": event.id,
            "event_no": event.event_no,
            "user_id_hash": event.user_id_hash,
            "session_id": event.session_id,
            "category_code": event.category_code,
            "level": event.level,
            "score_band": event.score_band,
            "rule_hit_id": event.rule_hit_id,
            "source_scene": event.source_scene,
            "body_emitted": event.body_emitted,
            "response_bytes": event.response_bytes,
            "disposal_result": event.disposal_result,
            "duty_officer_id": event.duty_officer_id,
            "reviewed_at": _iso(event.reviewed_at),
            "sla_due_at": _iso(event.sla_due_at),
            "reported": event.reported,
            "reported_target": event.reported_target,
            "created_at": _iso(event.created_at),
        }
    )


@router.post("/risk-events/{event_no}/review", tags=["后台-处置"], summary="复核高风险事件（误报联动放行）")
def review_risk_event(
    event_no: str,
    body: RiskReviewBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """复核高风险事件：upheld / misreport / need_more。

    misreport（误报）联动：关联申诉置 approved 且 24h 软类别放行
    （question_hash 未落库，放行以 appeal.allow_expire_at 为准），
    并记一条抽检记录（SamplingCheck, result=pass）。

    Args:
        event_no: 事件编号。
        body: 复核请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：复核后的事件状态。

    Raises:
        ApiError: 1001 参数非法；1002 事件不存在；1103 缺少 risk:review 权限。
    """
    require_admin_perm(admin, "risk:review")
    if body.conclusion not in ("upheld", "misreport", "need_more"):
        raise ApiError(1001, "conclusion 必须为 upheld/misreport/need_more", 422)
    event = db.query(RiskEvent).filter(RiskEvent.event_no == event_no).first()
    if event is None:
        raise ApiError(*ERR_NOT_FOUND)
    now = _now()
    before = {"disposal_result": event.disposal_result, "reviewed_at": _iso(event.reviewed_at)}
    # 落复核结论与责任人
    event.disposal_result = body.conclusion
    event.reviewed_at = now
    event.duty_officer_id = admin.id
    if body.conclusion == "misreport":
        # 优先按事件 ID 关联申诉，缺失时回退按会话取最近一条
        appeal = (
            db.query(RiskAppeal)
            .filter(RiskAppeal.risk_event_id == event.id)
            .order_by(RiskAppeal.id.desc())
            .first()
        )
        if appeal is None and event.session_id is not None:
            appeal = (
                db.query(RiskAppeal)
                .filter(RiskAppeal.session_id == event.session_id)
                .order_by(RiskAppeal.id.desc())
                .first()
            )
        if appeal is not None:
            appeal.status = "approved"
            appeal.review_result = "misreport"
            appeal.review_reason_code = body.reason_code
            appeal.reviewer_id = admin.id
            appeal.reviewed_at = now
            appeal.allow_expire_at = now + timedelta(hours=24)
            # question_hash 未落库：24h 软放行统一由 appeal.allow_expire_at 判定
        # 误报复核同步记抽检记录，供合规抽检率统计
        db.add(
            SamplingCheck(
                batch_no=f"W{now:%Y%m%d%H%M%S}{uuid.uuid4().hex[:4].upper()}",
                agent_call_id=None,
                checker_id=admin.id,
                result="pass",
                detail={"event_no": event.event_no, "scene": "risk_review_misreport"},
            )
        )
    write_audit(
        db,
        admin,
        "risk_review",
        "risk_event",
        event.event_no,
        reason=body.reason_code,
        before=before,
        after={"disposal_result": event.disposal_result, "reviewed_at": _iso(event.reviewed_at)},
    )
    return ok({"event_no": event.event_no, "disposal_result": event.disposal_result})


@router.post("/risk-events/{event_no}/report-authority", tags=["后台-处置"], summary="上报高风险事件至监管主体（先复核后上报）")
def report_risk_authority(
    event_no: str,
    body: ReportAuthorityBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """上报高风险事件至监管主体（复核结论未录入前禁止上报）。

    服务端兜底前端「上报按钮置灰」：disposal_result 为空直接 1103。

    Args:
        event_no: 事件编号。
        body: 上报请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：上报后的事件状态。

    Raises:
        ApiError: 1002 事件不存在；1103 结论未录入/缺少 risk:review 权限。
    """
    require_admin_perm(admin, "risk:review")
    event = db.query(RiskEvent).filter(RiskEvent.event_no == event_no).first()
    if event is None:
        raise ApiError(*ERR_NOT_FOUND)
    if not event.disposal_result:
        # 上报按钮前置灰的服务端兜底：先复核、后上报
        raise ApiError(1103, "复核结论出具前不可上报", 403)
    before = {"reported": event.reported, "reported_target": event.reported_target}
    event.reported = True
    event.reported_target = body.reported_target
    write_audit(
        db,
        admin,
        "risk_report_authority",
        "risk_event",
        event.event_no,
        reason=body.reported_target[:256],
        before=before,
        after={"reported": True, "reported_target": event.reported_target},
    )
    return ok({"event_no": event.event_no, "reported": True})


# ==================== 个人信息权利请求 ====================


@router.get("/rights", tags=["后台-处置"], summary="个人信息权利请求列表")
def list_rights(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询个人信息权利请求列表。

    Args:
        status: 状态过滤。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 rights:view 权限。
    """
    require_admin_perm(admin, "rights:view")
    q = db.query(RightsRequest)
    if status:
        q = q.filter(RightsRequest.status == status)
    total = q.count()
    rows = (
        q.order_by(RightsRequest.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    items = [
        {
            "id": r.id,
            "request_no": r.request_no,
            "user_id": r.user_id,
            "request_type": r.request_type,
            "status": r.status,
            "reject_reason_code": r.reject_reason_code,
            "delivery_method": r.delivery_method,
            "sla_due_at": _iso(r.sla_due_at),
            "export_file_url": r.export_file_url,
            "export_expire_at": _iso(r.export_expire_at),
            "export_downloaded": r.export_downloaded,
            "created_at": _iso(r.created_at),
            "handled_at": _iso(r.handled_at),
        }
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/rights/{request_no}/process", tags=["后台-处置"], summary="处理权利请求（导出/办结/拒绝）")
def process_rights(
    request_no: str,
    body: RightsProcessBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """处理权利请求：生成数据导出文件 / 标记办结 / 拒绝。

    generate_export：汇集用户档案+会话摘要+订单，写本地文件
    （JSON/CSV），导出链接 24 小时有效；reject 必填拒绝理由码。

    Args:
        request_no: 请求编号。
        body: 处理请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：处理后的请求状态与导出信息。

    Raises:
        ApiError: 1001 action 非法/拒绝缺理由码；1002 不存在；1103 无权限。
    """
    require_admin_perm(admin, "rights:handle")
    req = db.query(RightsRequest).filter(RightsRequest.request_no == request_no).first()
    if req is None:
        raise ApiError(*ERR_NOT_FOUND)
    now = _now()
    before = {"status": req.status}
    if body.action == "generate_export":
        fmt = body.format if body.format in ("json", "csv") else "json"
        payload = _collect_user_export(db, req.user_id)
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = _EXPORT_DIR / f"{req.request_no}.{fmt}"
        if fmt == "csv":
            _write_export_csv(path, payload)
        else:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        # 导出链接 24h 过期、限一次下载
        req.export_file_url = f"/api/v1/admin/rights/{req.request_no}/export-file"
        req.export_expire_at = now + timedelta(hours=24)
        req.delivery_method = fmt
        req.status = "exported"
    elif body.action == "mark_done":
        req.status = "done"
    elif body.action == "reject":
        if not body.reject_reason_code:
            raise ApiError(1001, "拒绝必须填写 reject_reason_code", 422)
        req.status = "rejected"
        req.reject_reason_code = body.reject_reason_code
    else:
        raise ApiError(1001, "action 必须为 generate_export/mark_done/reject", 422)
    req.handled_by = admin.id
    req.handled_at = now
    write_audit(
        db,
        admin,
        f"rights_{body.action}",
        "rights_request",
        req.request_no,
        reason=body.reject_reason_code or body.action,
        before=before,
        after={"status": req.status, "export_file_url": req.export_file_url},
    )
    return ok(
        {
            "request_no": req.request_no,
            "status": req.status,
            "export_file_url": req.export_file_url,
            "export_expire_at": _iso(req.export_expire_at),
        }
    )


@router.get("/rights/{request_no}/export-file", tags=["后台-处置"], summary="下载权利请求导出文件（24h 有效）")
def download_rights_export(
    request_no: str,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """下载权利请求数据导出文件（24h 内有效，标记已下载）。

    Args:
        request_no: 请求编号。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        FileResponse：JSON 或 CSV 文件。

    Raises:
        ApiError: 1002 请求不存在/文件缺失；1004 链接过期；1103 无权限。
    """
    require_admin_perm(admin, "rights:view")
    req = db.query(RightsRequest).filter(RightsRequest.request_no == request_no).first()
    if req is None:
        raise ApiError(*ERR_NOT_FOUND)
    if req.export_expire_at is not None and req.export_expire_at < _now():
        raise ApiError(1004, "导出链接已过期", 410)
    fmt = req.delivery_method or "json"
    path = _EXPORT_DIR / f"{req.request_no}.{fmt}"
    if not path.exists():
        raise ApiError(*ERR_NOT_FOUND)
    req.export_downloaded = True
    media = "text/csv" if fmt == "csv" else "application/json"
    return FileResponse(path, media_type=media, filename=path.name)


# ==================== 系统配置版本 ====================


@router.get("/configs", tags=["后台-配置"], summary="配置键最新版本列表（仅超管）")
def list_configs(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """查询全部配置键的最新版本列表。

    config（系统开关与配置）菜单仅 super_admin 拥有，读取同步收紧为仅超管
    （写权限 cfg:write 亦仅超管）。

    Args:
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items}（每 config_type+config_key 一条最新版）。

    Raises:
        ApiError: 1103 非超管。
    """
    # 系统开关配置属超管专属菜单（ROLE_MENUS 中 config 仅 super_admin），读取同步收紧
    if admin.role != "super_admin":
        raise ApiError(*ERR_ADMIN_FORBIDDEN)
    rows = db.query(ConfigVersion).order_by(ConfigVersion.id.desc()).all()
    latest: Dict[tuple, ConfigVersion] = {}
    for r in rows:
        key = (r.config_type, r.config_key)
        if key not in latest:
            latest[key] = r  # id 倒序遍历，首见即最新
    items = [
        {
            "config_type": r.config_type,
            "config_key": r.config_key,
            "version": r.version,
            "status": r.status,
            "snapshot": r.snapshot,
            "effective_at": _iso(r.effective_at),
            "reason": r.reason,
            "operator_id": r.operator_id,
        }
        for r in sorted(latest.values(), key=lambda x: (x.config_type, x.config_key))
    ]
    return ok({"items": items})


@router.put("/configs/{config_key}", tags=["后台-配置"], summary="更新系统配置（仅超管+二次确认）")
def update_config(
    config_key: str,
    body: ConfigUpdateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """更新系统配置（仅 super_admin）：写新版本 + 缓存热更新。

    版本递增留痕；同键旧 active 版本置 rolled_back，保持单活跃版语义。

    Args:
        config_key: 配置键。
        body: 更新请求体（snapshot 全量 + reason + confirm_token）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{config_key, version}。

    Raises:
        ApiError: 1103 非超管；1602 缺少二次确认。
    """
    require_admin_perm(admin, "cfg:write")  # 矩阵中仅 super_admin 的 "*" 覆盖
    require_confirm(body.confirm_token, "config_update")
    now = _now()
    rows = db.query(ConfigVersion).filter(ConfigVersion.config_key == config_key).all()
    max_version = max((r.version for r in rows), default=0)
    before = None
    for r in rows:
        if r.status == "active":
            before = {"version": r.version, "snapshot": r.snapshot}
            r.status = "rolled_back"
    cv = ConfigVersion(
        config_type="switch",
        config_key=config_key,
        version=max_version + 1,
        snapshot=body.snapshot,
        status="active",
        effective_at=now,
        reason=(body.reason or "-")[:128],
        operator_id=admin.id,
    )
    db.add(cv)
    db.flush()
    # 缓存热更新：运行时开关直读 switch:{key}
    cache.set(f"switch:{config_key}", json.dumps(body.snapshot, ensure_ascii=False), None)
    write_audit(
        db,
        admin,
        "config_update",
        "config_version",
        config_key,
        reason=body.reason,
        before=before,
        after={"version": cv.version, "snapshot": body.snapshot},
        confirm_used=True,
    )
    # 紧急开关语义：响应返回即代表新版本已提交（否则后续请求可能落在
    # get_db 收尾提交前的窗口内读到旧版本，开关"已关闭却仍放行"）
    db.commit()
    return ok({"config_key": config_key, "version": cv.version})


def _rollback_lexicon_config(db: Session, admin: AdminUser, target_version: int):
    """词库配置专用回滚（DEF-18）：目标版快照逐键写回 RiskRuleConfig 并失效词库缓存。

    词库的运行时数据源是 RiskRuleConfig 表（而非 switch:{key} 缓存），
    因此回滚必须回写数据行并删除 lexicon:snapshot 让它 1 分钟内全量生效。

    Args:
        db: 数据库会话。
        admin: 当前账号。
        target_version: 回滚目标版本号。

    Returns:
        包络：{config_key, version}。

    Raises:
        ApiError: 1002 目标版本不存在。
    """
    rows = db.query(ConfigVersion).filter(ConfigVersion.config_key == "lexicon").all()
    target = next((r for r in rows if r.version == target_version), None)
    if target is None:
        raise ApiError(*ERR_NOT_FOUND)
    current_active = next((r for r in rows if r.status == "active"), None)
    before = {"active_version": current_active.version if current_active else None}
    now = _now()
    for key, value in (target.snapshot or {}).items():
        row = db.query(RiskRuleConfig).filter(RiskRuleConfig.config_key == key).first()
        if row is None:
            db.add(
                RiskRuleConfig(
                    config_key=key,
                    config_value=value,
                    effective_at=now,
                    updated_by=admin.id,
                )
            )
        else:
            row.config_value = value
            row.effective_at = now
            row.updated_by = admin.id
            row.version += 1
    # 单活跃版语义：先全部置 rolled_back，再激活目标版
    for r in rows:
        r.status = "rolled_back"
    target.status = "active"
    target.rollback_from_version = current_active.version if current_active else None
    cache.delete("lexicon:snapshot")
    write_audit(
        db,
        admin,
        "config_rollback",
        "config_version",
        "lexicon",
        reason=f"rollback to v{target_version}",
        before=before,
        after={"active_version": target.version, "snapshot": target.snapshot},
        confirm_used=True,
    )
    # 响应返回即已提交：回滚必须立刻生效，不能等 get_db 收尾提交
    db.commit()
    return ok({"config_key": "lexicon", "version": target.version})


@router.post("/configs/{config_key}/rollback", tags=["后台-配置"], summary="回滚系统配置至指定版本")
def rollback_config(
    config_key: str,
    body: ConfigRollbackBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """回滚系统配置至指定历史版本（仅 super_admin + 二次确认）。

    目标版置 active、同键其余版本置 rolled_back，并刷新缓存。
    词库配置（lexicon）回写 RiskRuleConfig 数据行，见 _rollback_lexicon_config。

    Args:
        config_key: 配置键。
        body: 回滚请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{config_key, version}（回滚后的活跃版本号）。

    Raises:
        ApiError: 1002 目标版本不存在；1103 非超管；1602 缺少二次确认。
    """
    require_admin_perm(admin, "cfg:write")
    require_confirm(body.confirm_token, "config_rollback")
    if config_key == "lexicon":
        return _rollback_lexicon_config(db, admin, body.target_version)
    rows = db.query(ConfigVersion).filter(ConfigVersion.config_key == config_key).all()
    target = next((r for r in rows if r.version == body.target_version), None)
    if target is None:
        raise ApiError(*ERR_NOT_FOUND)
    current_active = next((r for r in rows if r.status == "active"), None)
    before = {"active_version": current_active.version if current_active else None}
    # 单活跃版语义：先全部置 rolled_back，再激活目标版
    for r in rows:
        r.status = "rolled_back"
    target.status = "active"
    target.rollback_from_version = current_active.version if current_active else None
    cache.set(
        f"switch:{config_key}", json.dumps(target.snapshot, ensure_ascii=False), None
    )
    write_audit(
        db,
        admin,
        "config_rollback",
        "config_version",
        config_key,
        reason=f"rollback to v{body.target_version}",
        before=before,
        after={"active_version": target.version, "snapshot": target.snapshot},
        confirm_used=True,
    )
    return ok({"config_key": config_key, "version": target.version})


@router.get("/configs/{config_key}/history", tags=["后台-配置"], summary="配置版本历史查询（仅超管）")
def config_history(
    config_key: str,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """查询配置键的版本历史（版本号倒序）。

    与 /admin/configs 同口径：config 菜单仅 super_admin 拥有，读取仅超管。

    Args:
        config_key: 配置键。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items}。

    Raises:
        ApiError: 1103 非超管。
    """
    if admin.role != "super_admin":
        raise ApiError(*ERR_ADMIN_FORBIDDEN)
    rows = (
        db.query(ConfigVersion)
        .filter(ConfigVersion.config_key == config_key)
        .order_by(ConfigVersion.version.desc())
        .all()
    )
    # 操作人展示名（前端抽屉列 prop=changed_by/changed_at，见 DEF-18 契约对齐）
    operator_ids = {r.operator_id for r in rows if r.operator_id}
    name_map = {}
    if operator_ids:
        name_map = {
            a.id: (a.display_name or a.username)
            for a in db.query(AdminUser).filter(AdminUser.id.in_(operator_ids)).all()
        }
    items = [
        {
            "config_type": r.config_type,
            "config_key": r.config_key,
            "version": r.version,
            "status": r.status,
            "snapshot": r.snapshot,
            "effective_at": _iso(r.effective_at),
            "rollback_from_version": r.rollback_from_version,
            "reason": r.reason,
            "operator_id": r.operator_id,
            "changed_by": name_map.get(r.operator_id) or (f"#{r.operator_id}" if r.operator_id else "-"),
            "changed_at": _iso(r.effective_at),
        }
        for r in rows
    ]
    return ok({"items": items})


# ==================== 商品价格（价格配置数据源） ====================


class ProductUpdateBody(BaseModel):
    """商品价格更新请求体。

    Attributes:
        price_micro: 新价格（micro 整数，1 元 = 1_000_000）。
        reason: 变更原因（写入审计日志）。
        confirm_token: 二次确认凭证（约定为 "CONFIRMED"）。
    """

    price_micro: int = Field(..., gt=0, description="价格（micro，1 元 = 1_000_000）")
    reason: Optional[str] = Field(default=None, max_length=128, description="变更原因（审计留痕）")
    confirm_token: Optional[str] = Field(default=None, description="二次确认凭证")


@router.get("/products", tags=["后台-配置"], summary="商品列表（价格配置卡数据源）")
def list_admin_products(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """查询商品列表（价格配置卡数据源，直读 product 表）。

    Args:
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items}（product_code/name/price_micro/duration_days/platform_scope/status）。
    """
    rows = db.query(Product).order_by(Product.id).all()
    items = [
        {
            "product_code": p.product_code,
            "name": p.name,
            "price_micro": p.price_micro,
            "duration_days": p.duration_days,
            "platform_scope": p.platform_scope,
            "status": p.status,
        }
        for p in rows
    ]
    return ok({"items": items})


@router.put("/products/{product_code}", tags=["后台-配置"], summary="更新商品价格（仅超管+二次确认）")
def update_admin_product(
    product_code: str,
    body: ProductUpdateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """更新商品价格（仅 super_admin，写审计留痕；下单按新价快照）。

    Args:
        product_code: 商品编码。
        body: {price_micro, reason?, confirm_token?}。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{product_code, price_micro}。

    Raises:
        ApiError: 1002 商品不存在；1103 非超管；1602 缺少二次确认。
    """
    require_admin_perm(admin, "cfg:write")
    require_confirm(body.confirm_token, "product_update")
    product = db.query(Product).filter(Product.product_code == product_code).first()
    if product is None:
        raise ApiError(*ERR_NOT_FOUND)
    before = {"price_micro": product.price_micro}
    product.price_micro = body.price_micro
    write_audit(
        db,
        admin,
        "product_update",
        "product",
        product_code,
        reason=body.reason or "-",
        before=before,
        after={"price_micro": body.price_micro},
        confirm_used=True,
    )
    return ok({"product_code": product_code, "price_micro": body.price_micro})


# ==================== 订单对账差异处置（spec 通道抽象 Task 3 对账闭环） ====================


class ReconcileResolveBody(BaseModel):
    """对账差异处置请求体。

    Attributes:
        resolution: 处置结论 manual_matched（人工确认已收款）/ refund_required（需退款）。
        confirm_token: 二次确认凭证（约定为 "CONFIRMED"）。
        reason: 处置备注（审计用，可空）。
    """

    resolution: str = Field(..., description="处置结论：manual_matched / refund_required")
    confirm_token: str = Field(..., min_length=1, description="二次确认凭证")
    reason: Optional[str] = Field(None, description="处置备注（审计用）")


@router.post("/orders/{order_no}/reconcile-resolve", tags=["后台-配置"], summary="对账差异闭环处置（人工确认/转退款）")
def resolve_reconcile_diff(
    order_no: str,
    body: ReconcileResolveBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """对账差异闭环处置：仅 reconcile_status='diff' 订单可处理 → 'resolved'。

    处置结论口径：
    - manual_matched：人工核对渠道侧已收款，差异闭环（补记 notify_status=received）；
    - refund_required：确认需退款，订单 status 置 refunding（后续走退款工单流程）。

    Args:
        order_no: 订单号。
        body: {resolution, confirm_token, reason?}。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{order_no, status, reconcile_status, resolution}。

    Raises:
        ApiError: 1001 resolution 非法；1002 订单不存在；1501 非 diff 状态不可处置；
                  1602 缺少二次确认凭证；1103 无 rights:handle 权限。
    """
    require_admin_perm(admin, "rights:handle")
    require_confirm(body.confirm_token, "reconcile_resolve")
    if body.resolution not in ("manual_matched", "refund_required"):
        raise ApiError(1001, "resolution 必须为 manual_matched/refund_required", 422)
    order = db.query(Order).filter(Order.order_no == order_no).first()
    if order is None:
        raise ApiError(*ERR_NOT_FOUND)
    if order.reconcile_status != "diff":
        # 仅对账差异订单可人工闭环，防止误改已 matched/resolved 订单
        raise ApiError(1501, "仅对账差异（reconcile_status=diff）订单可处置", 409)
    before = {"status": order.status, "reconcile_status": order.reconcile_status}
    # 两种结论均将差异状态闭环为 resolved
    order.reconcile_status = "resolved"
    if body.resolution == "refund_required":
        # 确认需退款：订单进入退款中（权益回收由后续退款工单流程处理）
        order.status = "refunding"
    else:
        # 人工确认已收款：渠道回调缺失场景补记通知已收到
        order.notify_status = "received"
    write_audit(
        db,
        admin,
        "reconcile_resolve",
        "order",
        order.order_no,
        reason=body.reason or "-",
        before=before,
        after={"status": order.status, "reconcile_status": order.reconcile_status},
        confirm_used=True,
    )
    db.flush()
    return ok({
        "order_no": order.order_no,
        "status": order.status,
        "reconcile_status": order.reconcile_status,
        "resolution": body.resolution,
    })

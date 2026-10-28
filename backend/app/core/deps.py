# -*- coding: utf-8 -*-
"""FastAPI 依赖注入模块。

提供 C 端用户鉴权、后台管理员鉴权（角色×页面×动作校验、专家域绑定、
二次确认凭证校验）与审计写入等公共依赖。
"""
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AdminAuditLog, AdminUser, AppUser
from .errors import (
    ApiError,
    ERR_ADMIN_FORBIDDEN,
    ERR_CONFIRM_REQUIRED,
    ERR_DOMAIN_SCOPE,
    ERR_FORBIDDEN,
    ERR_NO_SESSION,
)
from .envelope import request_id_var
from .security import decode_token

# 后台角色 × 页面 × 动作 权限矩阵（PRD §16 最小权限；服务端为真边界）
# 页面标识：kb(知识库) lex(词库) log(日志) fb(反馈举报) risk(高风险事件) rights(权利)
# cfg(系统开关) refund(退款) channel(危机渠道清单 RQ-03) triage(分级规则 RQ-06)
# content(专题包/轻工具 RQ-12/13/14)
ADMIN_ACTIONS = {
    "super_admin": {"*"},  # 超管全部动作
    "operator": {
        "kb:view", "kb:edit", "kb:review", "kb:publish", "kb:rollback",
        "lex:view", "lex:edit", "log:view",
        "fb:view", "fb:handle", "risk:view", "risk:review",
        "rights:view", "rights:handle",
        # V3.1：内容运营维护渠道清单与分级规则（法务/专家复核留痕在同一接口）
        "channel:view", "channel:edit", "channel:review",
        "triage:view", "triage:edit",
        "content:view", "content:edit",
    },
    "support": {
        "fb:view", "fb:handle", "rights:view", "rights:handle", "log:view",
        "channel:view",  # 客服只读渠道清单（号码字段脱敏）
    },
    # 域绑定 child / pet 由 domain_scope 限制
    "expert_child": {"kb:view", "kb:edit", "kb:review", "triage:view", "triage:review"},
    "expert_pet": {"kb:view", "kb:edit", "kb:review", "triage:view", "triage:review"},
}


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> AppUser:
    """C 端用户鉴权依赖。

    Args:
        authorization: 请求头 Bearer token。
        db: 数据库会话。

    Returns:
        当前用户 ORM 实例。

    Raises:
        ApiError: 1101 会话缺失或失效；1102 用户被禁用。
    """
    if not authorization.startswith("Bearer "):
        raise ApiError(*ERR_NO_SESSION)
    token = authorization[7:]
    try:
        payload = decode_token(token, expected_type="user_access")
    except Exception:
        raise ApiError(*ERR_NO_SESSION)
    user = db.query(AppUser).filter(AppUser.user_uid == payload["sub"]).first()
    if user is None:
        raise ApiError(*ERR_NO_SESSION)
    if user.status not in ("active", "deleting"):
        raise ApiError(*ERR_FORBIDDEN)
    return user


def get_admin(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> AdminUser:
    """后台管理员鉴权依赖：角色只从服务端会话（JWT）读取，忽略请求头角色（R-3）。

    Args:
        authorization: 请求头 Bearer token。
        db: 数据库会话。

    Returns:
        当前后台账号 ORM 实例。

    Raises:
        ApiError: 1101 未登录；1103 账号被禁用；1104 专家临时授权过期。
    """
    if not authorization.startswith("Bearer "):
        raise ApiError(*ERR_NO_SESSION)
    try:
        payload = decode_token(token := authorization[7:], expected_type="admin")
    except Exception:
        raise ApiError(*ERR_NO_SESSION)
    admin = db.query(AdminUser).filter(AdminUser.admin_uid == payload["sub"]).first()
    if admin is None or admin.status != "active":
        raise ApiError(*ERR_ADMIN_FORBIDDEN)
    # 专家临时授权到期自动失效（默认 30 天）
    if admin.role.startswith("expert") and admin.temp_auth_expire_at is not None:
        from datetime import datetime, timezone

        if admin.temp_auth_expire_at < datetime.now(timezone.utc):
            raise ApiError(*ERR_ADMIN_FORBIDDEN)
    return admin


def require_admin_perm(admin: AdminUser, perm: str) -> None:
    """校验后台角色是否拥有指定「页面:动作」权限。

    Args:
        admin: 当前后台账号。
        perm: 权限标识（如 kb:publish）。

    Raises:
        ApiError: 1103 角色无权限。
    """
    actions = ADMIN_ACTIONS.get(admin.role, set())
    if "*" not in actions and perm not in actions:
        raise ApiError(*ERR_ADMIN_FORBIDDEN)


def check_domain_scope(admin: AdminUser, domain: str) -> None:
    """校验专家领域绑定（育儿专家仅可操作 child 领域条目）。

    Args:
        admin: 当前后台账号。
        domain: 目标领域（child / pet）。

    Raises:
        ApiError: 1603 专家跨领域越权。
    """
    if admin.role.startswith("expert") and admin.domain_scope != domain:
        raise ApiError(*ERR_DOMAIN_SCOPE)


def require_confirm(confirm_token: Optional[str], action: str) -> None:
    """二次确认凭证校验：缺失返回 1602 且不产生副作用。

    Args:
        confirm_token: 前端二次确认后回传的凭证（约定为 "CONFIRMED"）。
        action: 动作名（审计记录用）。

    Raises:
        ApiError: 1602 缺少二次确认凭证。
    """
    if confirm_token != "CONFIRMED":
        raise ApiError(*ERR_CONFIRM_REQUIRED)


def write_audit(
    db: Session,
    admin: AdminUser,
    action: str,
    object_type: str,
    object_id: str,
    reason: str = "-",
    before: dict = None,
    after: dict = None,
    result: str = "ok",
    confirm_used: bool = False,
) -> None:
    """写后台审计日志（审计写入失败按业务失败处理，不得静默）。

    Args:
        db: 数据库会话。
        admin: 操作人。
        action: 动作代码。
        object_type: 对象类型。
        object_id: 对象 ID。
        reason: 原因（必填，默认 "-"）。
        before: 变更前快照。
        after: 变更后快照。
        result: ok / fail / denied。
        confirm_used: 是否经过二次确认。

    Raises:
        Exception: 审计落库失败时向上抛出（调用方事务回滚）。
    """
    log = AdminAuditLog(
        operator_id=admin.id,
        operator_role_snapshot=admin.role,  # 角色快照，不随后续变更改写
        action=action,
        object_type=object_type,
        object_id=object_id,
        before_snapshot=before,
        after_snapshot=after,
        reason=reason or "-",
        mfa_passed=True,
        confirm_used=confirm_used,
        result=result,
    )
    db.add(log)
    db.flush()

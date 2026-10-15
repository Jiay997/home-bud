# -*- coding: utf-8 -*-
"""认证 API 模块。

提供 C 端登录与令牌刷新接口（认证通道抽象，spec 通道收口 Task 3）：
- POST /auth/dev-login   开发模式设备码登录（device_id → 模拟 openid，DevProvider 语义不变）
- POST /auth/wx-login    微信 code 登录（code2session；auth_provider='wx' 时启用）
- POST /auth/refresh     刷新令牌对（校验 user_refresh 类型 JWT）

业务口径：openid 明文不落库、不出响应（CG13），仅存 Fernet 密文；
同一 device_id 恒定映射同一用户（幂等登录）；
wx-login 将 session_key 加密留存（wx_session_key_enc），同样不出响应。

【通道启动校验说明】get_auth_provider()（app/services/auth_provider.py）在
settings.auth_provider='wx' 且 WX_APPID/WX_SECRET 缺失时抛 AuthConfigError
（运行期首次调用即显式失败，符合 spec"配置不完整启动明确报错"语义，不伪造凭据）；
dev 配置下调 /auth/wx-login 返回 1101"当前通道未启用"。
"""
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.crypto import encrypt_field, sha256_hex
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NO_SESSION
from ...core.security import create_user_tokens, decode_token
from ...db import get_db
from ...models import AppUser
from ...services.auth_provider import (
    AuthConfigError,
    DevAuthProvider,
    get_auth_provider,
)

router = APIRouter(tags=["auth", "C端-认证同意"])


class DevLoginBody(BaseModel):
    """设备码登录请求体。

    Attributes:
        device_id: 客户端生成的设备唯一标识。
    """

    device_id: str = Field(min_length=1, max_length=128, description="客户端设备唯一标识")


class RefreshBody(BaseModel):
    """刷新令牌请求体。

    Attributes:
        refresh_token: 登录时下发的刷新令牌。
    """

    refresh_token: str = Field(min_length=1, description="user_refresh 类型 JWT")


def _user_brief(user: AppUser) -> Dict[str, Any]:
    """构造用户简要信息（登录/刷新响应公共部分）。

    Args:
        user: 用户 ORM 实例。

    Returns:
        {user_uid, member_status} 字典。
    """
    return {"user_uid": user.user_uid, "member_status": user.member_status}


def _openid_lookup_value(openid: str) -> str:
    """构造 openid 的确定性存储值（密钥化 HMAC，支持等值查找）。

    Fernet 密文含随机 IV，同一 openid 两次加密密文不同，无法用于
    数据库等值查询（会导致幂等登录失效、重复建号）。本函数以服务端
    字段加密密钥做 HMAC-SHA256 摘要：既保证确定性（幂等登录查找），
    又保持单向不可逆（openid 明文不落库，CG13 红线）。openid 无任何
    解密读路径，由可逆密文换为不可逆摘要不损失业务能力。

    Args:
        openid: 通道换取的 openid 明文（不落库）。

    Returns:
        形如 "vD:{hmac_hex}" 的确定性存储字符串。

    Raises:
        无。
    """
    settings = get_settings()
    return "vD:" + sha256_hex(openid + settings.field_enc_key)


@router.post("/auth/dev-login", summary="开发模式设备码登录")
def dev_login(body: DevLoginBody, db: Session = Depends(get_db)) -> dict:
    """开发模式设备码登录：device_id 哈希为模拟 openid，按密文查找或创建用户。

    幂等：同一 device_id 恒定得到同一 openid 密文 → 同一用户；
    重复登录不新建账号，仅刷新活跃时间并重新签发令牌。

    Args:
        body: {device_id}。
        db: 数据库会话。

    Returns:
        统一包络：令牌对 + {user_uid, member_status}。

    Raises:
        ApiError: 1901 用户创建落库异常时由全局处理器兜底（此处不吞异常）。
    """
    # device_id → 模拟 openid：走开发设备码通道（确定性哈希，保证幂等登录）
    mock_openid = DevAuthProvider().authenticate({"device_id": body.device_id})["openid"]
    openid_enc = _openid_lookup_value(mock_openid)

    user = db.query(AppUser).filter(AppUser.wx_openid_enc == openid_enc).first()
    if user is None:
        # 首次登录：创建用户（openid 仅存密文）
        user = AppUser(wx_openid_enc=openid_enc, member_status="free", status="active")
        db.add(user)
        db.flush()
    # 每次登录刷新活跃时间
    user.last_active_at = datetime.now(timezone.utc)
    return ok({**create_user_tokens(user.user_uid), **_user_brief(user)})


class WxLoginBody(BaseModel):
    """微信登录请求体。

    Attributes:
        code: wx.login() 获取的临时登录凭证（一次性，5 分钟有效）。
    """

    code: str = Field(min_length=1, max_length=128, description="wx.login 临时登录凭证")


@router.post("/auth/wx-login", summary="微信 code2session 登录（骨架，待凭据）")
def wx_login(body: WxLoginBody, db: Session = Depends(get_db)) -> dict:
    """微信 code 登录：code2session → openid 加密查/建用户 → 签发令牌对。

    仅在 settings.auth_provider='wx' 时启用；session_key 加密留存
    （wx_session_key_enc）供后续解手机号等场景，明文不落库、不出响应。

    Args:
        body: {code}。
        db: 数据库会话。

    Returns:
        统一包络：令牌对 + {user_uid, member_status}（与 dev-login 结构一致）。

    Raises:
        ApiError: 1101 当前通道未启用（dev 配置）；1901 通道凭据缺失/渠道异常；
                  1901 用户落库异常时由全局处理器兜底。
    """
    settings = get_settings()
    if settings.auth_provider != "wx":
        # dev 配置下微信通道未启用（1101 鉴权分段）
        raise ApiError(1101, "当前通道未启用", 401)
    try:
        creds = get_auth_provider().authenticate({"code": body.code})
    except AuthConfigError as exc:
        # 凭据缺失/渠道配置错误：按依赖服务不可用兜底，不泄露凭据细节
        raise ApiError(1901, "微信登录服务不可用", 503) from exc
    openid = creds["openid"]
    openid_enc = _openid_lookup_value(openid)
    user = db.query(AppUser).filter(AppUser.wx_openid_enc == openid_enc).first()
    if user is None:
        # 首次登录：创建用户（openid 仅存密文）
        user = AppUser(wx_openid_enc=openid_enc, member_status="free", status="active")
        db.add(user)
        db.flush()
    # session_key 仅加密留存；缺失（如 dev 通道）不覆盖
    if creds.get("session_key"):
        user.wx_session_key_enc = encrypt_field(creds["session_key"])
    # 每次登录刷新活跃时间
    user.last_active_at = datetime.now(timezone.utc)
    return ok({**create_user_tokens(user.user_uid), **_user_brief(user)})


@router.post("/auth/refresh", summary="刷新令牌")
def refresh_token(body: RefreshBody, db: Session = Depends(get_db)) -> dict:
    """刷新令牌：校验 user_refresh 类型 JWT 并签发新的令牌对。

    Args:
        body: {refresh_token}。
        db: 数据库会话。

    Returns:
        统一包络：新令牌对 + {user_uid, member_status}。

    Raises:
        ApiError: 1101 刷新令牌无效/过期/类型不符/用户不存在或被禁用。
    """
    try:
        payload = decode_token(body.refresh_token, expected_type="user_refresh")
    except Exception:
        # 类型不符、签名错误、过期统一按无会话处理，不泄露具体原因
        raise ApiError(*ERR_NO_SESSION)
    user = db.query(AppUser).filter(AppUser.user_uid == payload["sub"]).first()
    if user is None or user.status not in ("active", "deleting"):
        raise ApiError(*ERR_NO_SESSION)
    return ok({**create_user_tokens(user.user_uid), **_user_brief(user)})

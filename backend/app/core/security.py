# -*- coding: utf-8 -*-
"""认证与安全工具模块。

提供 JWT 签发/校验（C 端 user_token 与后台 admin_token 两类）
以及密码哈希（passlib bcrypt）。
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

# 密码哈希上下文：pbkdf2_sha256 算法（纯 Python 实现，规避 passlib 与
# bcrypt>=4.1 的版本兼容缺陷，安全强度满足后台账号要求）
_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# C 端访问令牌有效期：2 小时（架构文档 §6.1）
USER_ACCESS_TTL = timedelta(hours=2)
# C 端刷新令牌有效期：30 天
USER_REFRESH_TTL = timedelta(days=30)
# 后台令牌空闲有效期：30 分钟（专家 15 分钟）
ADMIN_IDLE_TTL = timedelta(minutes=30)


def hash_password(plain: str) -> str:
    """对明文密码做 bcrypt 哈希。

    Args:
        plain: 明文密码。

    Returns:
        bcrypt 哈希字符串。
    """
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。

    Args:
        plain: 明文密码。
        hashed: 数据库中的哈希值。

    Returns:
        匹配返回 True，否则 False。
    """
    try:
        return _pwd_ctx.verify(plain, hashed)
    except Exception:
        # 哈希格式非法等情况一律视为不匹配，避免泄露内部错误
        return False


def _create_token(
    subject: str, token_type: str, ttl: timedelta, extra: Optional[dict] = None
) -> str:
    """签发 JWT 的内部通用函数。

    Args:
        subject: 主体标识（user_uid 或 admin_uid）。
        token_type: 令牌类型（user_access / user_refresh / admin）。
        ttl: 有效时长。
        extra: 附加声明（如角色、领域绑定）。

    Returns:
        编码后的 JWT 字符串。

    Raises:
        无。
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_user_tokens(user_uid: str) -> dict:
    """为 C 端用户签发访问/刷新令牌对。

    Args:
        user_uid: 用户对外唯一标识。

    Returns:
        {access_token, refresh_token, token_type} 字典。
    """
    return {
        "access_token": _create_token(user_uid, "user_access", USER_ACCESS_TTL),
        "refresh_token": _create_token(user_uid, "user_refresh", USER_REFRESH_TTL),
        "token_type": "Bearer",
    }


def create_admin_token(admin_uid: str, role: str, domain_scope: str = None) -> str:
    """为后台账号签发令牌。

    Args:
        admin_uid: 后台账号唯一标识。
        role: 角色代码。
        domain_scope: 专家领域绑定（child/pet），非专家为 None。

    Returns:
        编码后的 JWT 字符串。
    """
    extra = {"role": role}
    if domain_scope:
        extra["domain_scope"] = domain_scope
    return _create_token(admin_uid, "admin", ADMIN_IDLE_TTL, extra)


def decode_token(token: str, expected_type: str = None) -> dict:
    """解码并校验 JWT。

    Args:
        token: JWT 字符串。
        expected_type: 期望的令牌类型，None 表示不限制。

    Returns:
        解码后的声明字典。

    Raises:
        JWTError: 令牌无效或过期。
        ValueError: 令牌类型不匹配。
    """
    settings = get_settings()
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer
    )
    if expected_type and payload.get("typ") != expected_type:
        raise ValueError("token type mismatch")
    return payload

# -*- coding: utf-8 -*-
"""用户与准入相关表模型。

对应数据模型文档 §3.1：app_user / consent_record / text_version，
以及 §3.2 的 current_context（当前问答对象）。
"""
from sqlalchemy import BigInteger, Boolean, Date, Integer, String, Text, UniqueConstraint, Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgIdMixin, gen_uuid


class AppUser(Base, OrgIdMixin):
    """用户表（表 1）。

    Attributes:
        user_uid: 对外唯一标识（openid 明文不出响应，CG13）。
        wx_openid_enc: 微信 openid 密文（仅服务端留存）。
        member_status: free / member / expired。
        member_expire_at: 会员到期时间（门控判定冗余列）。
        status: active / disabled / deleting / deleted。
    """

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_uid: Mapped[str] = mapped_column(
        UUID(as_uuid=False), unique=True, nullable=False, default=gen_uuid
    )
    wx_openid_enc: Mapped[str] = mapped_column(Text, nullable=False)
    wx_unionid_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 微信会话密钥密文（wx-login 换取后加密留存，供解手机号等场景；不出响应）
    wx_session_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_masked: Mapped[str | None] = mapped_column(String(16), nullable=True)
    member_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="free", server_default="free"
    )
    member_expire_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    register_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_active_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # 会员到期扫描与门控判定（文档索引设计）
        __import__("sqlalchemy").Index("idx_appuser_member", "member_status", "member_expire_at"),
        __import__("sqlalchemy").Index("idx_app_user_org_id", "org_id"),
        {"comment": "用户表：账号存续期留存"},
    )


class ConsentRecord(Base):
    """同意记录表（表 2）：分层同意合规留档，≥3 年。

    唯一索引 (user_id, consent_type, consent_version) 保证同版本只记一次。
    """

    __tablename__ = "consent_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    guardian_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guardian_verified_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    device_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_segment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    agreed_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    withdraw_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="compliance", server_default="compliance"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "consent_type", "consent_version", name="uk_consent"
        ),
        __import__("sqlalchemy").Index("idx_consent_scope", "user_id", "scope"),
        {"comment": "同意记录：合规留档 ≥3 年"},
    )


class TextVersion(Base):
    """文案版本表（表 3）：文案 ID 服务端下发，前端不得硬编码。"""

    __tablename__ = "text_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    text_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    requires_reconsent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("text_id", "version", name="uk_text_version"),
        {"comment": "文案版本：DISCLAIMER_V1 等合规文案"},
    )


class CurrentContext(Base):
    """当前问答对象表（表 6）：多档案场景下「这次问的是谁」。"""

    __tablename__ = "current_context"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    profile_type: Mapped[str] = mapped_column(String(8), nullable=False)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

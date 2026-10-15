# -*- coding: utf-8 -*-
"""配置、幂等与后台审计表模型。

对应数据模型文档 §3.8：config_version / idempotency_key / admin_user /
admin_audit_log / job_run_log。
"""
from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, SmallInteger, String, Text, UniqueConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, VersionMixin, gen_uuid


class ConfigVersion(Base, VersionMixin):
    """配置版本表（表 30）：变更留痕 + 一键回滚目标。

    唯一索引 (config_type, config_key, version)。
    """

    __tablename__ = "config_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_type: Mapped[str] = mapped_column(String(24), nullable=False)
    config_key: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[object] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    effective_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    rollback_from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("config_type", "config_key", "version", name="uk_config"),
        {"comment": "配置版本：改价/开关/AI文案/渠道清单全部留痕"},
    )


class IdempotencyKey(Base):
    """幂等表（表 31）：问答/测评/下单三类重复提交共用。

    唯一索引 (scope, client_request_id)；request_fingerprint 防同键不同参。
    """

    __tablename__ = "idempotency_key"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    client_request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_ref: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expire_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("scope", "client_request_id", name="uk_idem"),
        Index("idx_idem_expire", "expire_at"),
        {"comment": "幂等表：写路径最高频"},
    )


class AdminUser(Base):
    """后台账号表（表 32）：4 类角色，强制 MFA，5 次失败锁 15 分钟。"""

    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_enc: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    domain_scope: Mapped[str | None] = mapped_column(String(16), nullable=True)
    temp_auth_expire_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trust_device_until: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    locked_until: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        {"comment": "后台账号：super_admin/operator/support/expert_child/expert_pet"},
    )


class AdminAuditLog(Base):
    """后台审计日志表（表 33）：10 字段，403 也写审计并触发越权告警。"""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_role_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    object_type: Mapped[str] = mapped_column(String(24), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before_snapshot: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    after_snapshot: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    ip_segment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    mfa_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confirm_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirm_text_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False, default="ok")
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    retention_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="audit_6m", server_default="audit_6m"
    )

    __table_args__ = (
        Index("idx_audit_time", "created_at"),
        Index("idx_audit_operator", "operator_id", "created_at"),
        Index("idx_audit_object", "object_type", "object_id"),
        {"comment": "后台审计：登录/操作 ≥6 月，配置处置 ≥3 年"},
    )


class JobRunLog(Base):
    """定时任务执行日志表（表 34）：同日重跑幂等返回上次结果。"""

    __tablename__ = "job_run_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    biz_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    affected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    detail: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("job_name", "idempotency_key", name="uk_job"),
        {"comment": "定时任务：对账/清理/渲染幂等留痕"},
    )

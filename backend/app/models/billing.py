# -*- coding: utf-8 -*-
"""商业化表模型。

对应数据模型文档 §3.5：product / order / subscription / refund_request /
quota_usage。金额一律 amount_micro（int64，1 元 = 1_000_000），禁浮点。
"""
from sqlalchemy import BigInteger, Boolean, Date, Index, SmallInteger, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, VersionMixin, gen_uuid


class Product(Base, VersionMixin):
    """商品与价格表（表 14）：改价即刻生效（乐观锁 + 快照比对）。"""

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_days: Mapped[int] = mapped_column(BigInteger().with_variant(SmallInteger, "postgresql"), nullable=False, default=30)
    platform_scope: Mapped[object] = mapped_column(JSONB, nullable=False)
    entitlements: Mapped[object] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="on")
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Order(Base):
    """订单表（表 15）：out_trade_no / transaction_id 双唯一约束。"""

    __tablename__ = "order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_snapshot_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    out_trade_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    platform: Mapped[str] = mapped_column(String(8), nullable=False, default="android")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    notify_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reconcile_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contract_confirm_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="transaction", server_default="transaction"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_order_user_time", "user_id", "created_at"),
        Index("idx_order_reconcile", "reconcile_status", "paid_at"),
        {"comment": "订单：交易类留存 ≥3 年"},
    )


class Subscription(Base):
    """会员订阅表（表 16）：会员不受免费额度限制由额度服务读 member_status 放行。"""

    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    expire_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    revoked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_sub_expire", "status", "expire_at"),
        {"comment": "会员订阅：退款回收置 revoked"},
    )


class RefundRequest(Base):
    """退款/售后申请表（表 17）：驳回理由必填。"""

    __tablename__ = "refund_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    reject_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    refund_amount_micro: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    entitlement_recycled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    handled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_refund_status", "status", "created_at"),
        {"comment": "退款售后：虚拟内容解锁后不退款（购买前明示）"},
    )


class QuotaUsage(Base):
    """免费额度用量表（表 18）：唯一索引 (user_id, biz_date)，服务端唯一裁决入口。

    计次规则（PRD §12.5）：正常生成+申诉放行后重提计次；
    失败/被拦截/重试/缓存命中/测评不计次。
    """

    __tablename__ = "quota_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    biz_date: Mapped[object] = mapped_column(Date, nullable=False)
    used_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    limit_snapshot: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=4)
    is_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("user_id", "biz_date", name="uk_quota"),
        {"comment": "免费额度：留存 ≥1 年"},
    )

# -*- coding: utf-8 -*-
"""商业化计费 API 模块。

提供额度查询、商品下发、下单（幂等）、模拟支付回调、订单列表与订阅查询：
- GET  /billing/quota                          今日免费额度用量
- GET  /billing/product?platform=android       商品列表（iOS 不展示购买入口）
- POST /billing/orders                         幂等下单（价格快照 + 退款政策确认）
- POST /billing/orders/{order_no}/mock-pay     模拟支付回调（验签 + 状态机 + 发放）
- GET  /billing/orders                         当前用户订单列表
- GET  /billing/subscription                   当前有效订阅 + 会员状态

业务口径：金额一律 micro 整数（1 元 = 1_000_000）；biz_date 按
Asia/Shanghai 时区；额度接口直接查 QuotaUsage 实现（不依赖额度服务）。
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.crypto import sha256_hex
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import (
    ApiError,
    ERR_IDEMPOTENT_PROCESSING,
    ERR_NOT_FOUND,
    ERR_ORDER_STATE,
    ERR_PAY_VERIFY,
    raise_err,
)
from ...db import get_db
from ...services.pay_provider import get_pay_provider
from ...models import (
    AppUser,
    IdempotencyKey,
    Order,
    Product,
    QuotaUsage,
    Subscription,
)
from ...models.base import utcnow

router = APIRouter(tags=["billing", "C端-商业化"])

# 东八区时区（biz_date 口径）
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")

# 幂等键结果保留时长（done 状态在此期间可回放）
IDEMPOTENT_TTL_HOURS = 24

# 订单幂等 scope 标识
ORDER_SCOPE = "order"


# ---------- 请求体模型 ----------


class OrderCreateBody(BaseModel):
    """下单请求体。

    Attributes:
        product_code: 商品编码。
        platform: 下单平台（android / ios）。
        contract_confirm: 是否已确认退款政策（必须 True）。
        client_request_id: 客户端幂等 ID。
    """

    product_code: str = Field(min_length=1, max_length=32, description="商品编码")
    platform: str = Field(min_length=1, max_length=8, description="下单平台")
    contract_confirm: bool = Field(description="是否已确认退款政策")
    client_request_id: str = Field(min_length=1, max_length=64, description="客户端幂等 ID")


class MockPayBody(BaseModel):
    """模拟支付回调请求体。

    Attributes:
        transaction_id: 支付渠道交易号。
        sign: 验签（sha256_hex(transaction_id + pay_mock_sign_key)）。
    """

    transaction_id: str = Field(min_length=1, max_length=64, description="渠道交易号")
    sign: str = Field(min_length=32, max_length=128, description="验签摘要")


# ---------- 内部工具函数 ----------


def _iso(value: Any) -> Optional[str]:
    """datetime 转 ISO8601 字符串。

    Args:
        value: datetime 实例或 None。

    Returns:
        ISO 字符串；入参为 None 时返回 None。
    """
    return value.isoformat() if value is not None else None


def _is_member(user: AppUser) -> bool:
    """判定用户当前是否为有效会员。

    Args:
        user: 当前用户。

    Returns:
        member_status=member 且未到期（或未设置到期时间）返回 True。
    """
    if user.member_status != "member":
        return False
    return user.member_expire_at is None or user.member_expire_at > utcnow()


def _gen_out_trade_no(user_id: int) -> str:
    """生成商户订单号：JB + 时间戳 + user_id + 随机 4 位。

    Args:
        user_id: 用户主键。

    Returns:
        唯一的 out_trade_no 字符串。
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:4]
    return f"JB{ts}{user_id}{rand}"


def _order_view(order: Order, product_code: Optional[str] = None) -> Dict[str, Any]:
    """构造订单视图。

    Args:
        order: 订单 ORM 实例。
        product_code: 商品编码（可选）。

    Returns:
        订单字段字典。
    """
    data: Dict[str, Any] = {
        "order_no": order.order_no,
        "out_trade_no": order.out_trade_no,
        "amount_micro": order.amount_micro,
        "price_snapshot_micro": order.price_snapshot_micro,
        "platform": order.platform,
        "status": order.status,
        "transaction_id": order.transaction_id,
        "paid_at": _iso(order.paid_at),
        "created_at": _iso(order.created_at),
    }
    if product_code is not None:
        data["product_code"] = product_code
    return data


# ---------- 额度 ----------


@router.get("/billing/quota", summary="免费额度查询")
def get_quota(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """查询今日免费额度用量（biz_date 按 Asia/Shanghai 时区的今天）。

    会员不受免费额度限制（unlimited=True，limit/remaining 为 null）；
    当日无用量记录时按 0 次创建（limit_snapshot 取当前配置）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{used, limit, remaining, is_member, biz_date, unlimited?}。
    """
    settings = get_settings()
    member = _is_member(user)
    biz_date = datetime.now(TZ_SHANGHAI).date()

    usage = (
        db.query(QuotaUsage)
        .filter(QuotaUsage.user_id == user.id, QuotaUsage.biz_date == biz_date)
        .first()
    )
    if usage is None:
        # 当日首查：落一行 0 用量（limit_snapshot 取当前配置快照）
        usage = QuotaUsage(
            user_id=user.id,
            biz_date=biz_date,
            used_count=0,
            limit_snapshot=settings.free_quota_daily,
            is_member=member,
        )
        db.add(usage)
        db.flush()

    if member:
        return ok({
            "used": usage.used_count,
            "limit": None,
            "remaining": None,
            "is_member": True,
            "biz_date": biz_date.isoformat(),
            "unlimited": True,
        })
    limit = usage.limit_snapshot
    remaining = max(0, limit - usage.used_count)
    return ok({
        "used": usage.used_count,
        "limit": limit,
        "remaining": remaining,
        "is_member": False,
        "biz_date": biz_date.isoformat(),
    })


# ---------- 商品与订单 ----------


@router.get("/billing/product", summary="商品查询（iOS 不返回可购）")
def list_products(
    platform: str = Query(default="android", description="下单平台 android / ios"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """商品列表下发（仅 status='on'）；iOS 平台不展示购买入口。

    Args:
        platform: 平台标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：iOS 返回 {purchasable: false, reason_code}；
        其他平台返回 {purchasable: true, products: [...]}。
    """
    if platform == "ios":
        # iOS 渠道合规限制：不展示购买入口
        return ok({"purchasable": False, "reason_code": "platform_not_supported"})
    products = db.query(Product).filter(Product.status == "on").all()
    return ok({
        "purchasable": True,
        "products": [
            {
                "product_code": p.product_code,
                "name": p.name,
                "price_micro": p.price_micro,
                "duration_days": p.duration_days,
                "platform_scope": p.platform_scope,
                "entitlements": p.entitlements,
            }
            for p in products
        ],
    })


@router.post("/billing/orders", summary="创建订单（幂等）")
def create_order(
    body: OrderCreateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """幂等下单：退款政策确认 + 价格快照 + 幂等键落库。

    流程：幂等检查（done 回放 / processing 拒绝）→ 合同确认校验 →
    商品校验 → 创建 pending 订单 → 幂等键置 done。

    Args:
        body: 下单请求体。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：订单信息 + idempotent_replay 标记。

    Raises:
        ApiError: 1004 同键处理中；1001 需先确认退款政策 / 同键不同指纹；
                  1002 商品不存在或未上架。
    """
    now = utcnow()
    fingerprint = sha256_hex(f"{user.id}|{body.product_code}|{body.platform}")

    # ---- 幂等检查 ----
    idem = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.scope == ORDER_SCOPE,
            IdempotencyKey.client_request_id == body.client_request_id,
        )
        .first()
    )
    if idem is not None:
        if idem.request_fingerprint != fingerprint:
            raise ApiError(
                code=1001, message="client_request_id 已被其他请求占用", http_status=409
            )
        if idem.status == "done":
            # 已成功下单：回放首次结果
            ref = idem.result_ref or {}
            return ok({**ref, "idempotent_replay": True})
        if idem.status == "processing":
            raise_err(ERR_IDEMPOTENT_PROCESSING)
        # failed 状态：复用该行重试

    # 合同确认前置：退款政策须在购买前明示并确认
    if body.contract_confirm is not True:
        raise ApiError(code=1001, message="需先确认退款政策")

    product = (
        db.query(Product)
        .filter(Product.product_code == body.product_code, Product.status == "on")
        .first()
    )
    if product is None:
        raise_err(ERR_NOT_FOUND)

    order = Order(
        order_no=f"JB{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        user_id=user.id,
        product_id=product.id,
        # 价格快照：下单时刻价格，支付时不重新读价
        amount_micro=product.price_micro,
        price_snapshot_micro=product.price_micro,
        out_trade_no=_gen_out_trade_no(user.id),
        platform=body.platform,
        status="pending",
        contract_confirm_at=now,
    )
    db.add(order)
    db.flush()

    # 幂等键置 done（本事务内同步完成，无异步阶段）
    if idem is None:
        idem = IdempotencyKey(
            scope=ORDER_SCOPE,
            client_request_id=body.client_request_id,
            request_fingerprint=fingerprint,
            status="done",
            result_ref={"order_no": order.order_no},
            expire_at=now + timedelta(hours=IDEMPOTENT_TTL_HOURS),
        )
        db.add(idem)
    else:
        idem.status = "done"
        idem.result_ref = {"order_no": order.order_no}
        idem.expire_at = now + timedelta(hours=IDEMPOTENT_TTL_HOURS)
    db.flush()
    return ok({**_order_view(order, product.product_code), "idempotent_replay": False})


@router.post("/billing/orders/{order_no}/mock-pay", summary="模拟支付回调（验签+幂等+权益发放）")
def mock_pay(
    order_no: str,
    body: MockPayBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """模拟支付回调：验签 → 幂等 → 状态机 pending→paid → 发放会员订阅。

    验签走支付通道抽象（get_pay_provider().verify_callback）：
    mock 配置下 sign = sha256_hex(transaction_id + pay_mock_sign_key)，与既有口径一致；
    已有 transaction_id 视为重复回调，直接返回成功不重复发放；
    非 pending 状态拒绝操作（1501）。

    Args:
        order_no: 订单号。
        body: {transaction_id, sign}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{order_no, status, transaction_id, already_processed}。

    Raises:
        ApiError: 1504 验签失败；1002 订单不存在或越权；1501 状态不允许。
    """
    # ---- 验签（走支付通道抽象；mock 配置下与历史实现行为完全一致）----
    if not get_pay_provider().verify_callback(body.transaction_id, body.sign):
        raise_err(ERR_PAY_VERIFY)

    order = (
        db.query(Order)
        .filter(Order.order_no == order_no)
        .with_for_update()  # 行锁：并发重复回调串行化，后到事务重读即见已发放
        .first()
    )
    # 不区分不存在与无权限，防订单号枚举
    if order is None or order.user_id != user.id:
        raise_err(ERR_NOT_FOUND)

    # ---- 幂等：重复回调不重复发放 ----
    if order.transaction_id is not None:
        return ok({
            "order_no": order.order_no,
            "status": order.status,
            "transaction_id": order.transaction_id,
            "already_processed": True,
        })
    # 状态机：仅 pending 可支付
    if order.status != "pending":
        raise_err(ERR_ORDER_STATE)

    now = utcnow()
    order.status = "paid"
    order.paid_at = now
    order.transaction_id = body.transaction_id
    order.notify_status = "received"

    # ---- 发放权益：订阅 + 会员状态 ----
    product = db.query(Product).filter(Product.id == order.product_id).first()
    duration_days = product.duration_days if product is not None else 30
    expire_at = now + timedelta(days=duration_days)
    db.add(
        Subscription(
            user_id=user.id,
            source_order_id=order.id,
            start_at=now,
            expire_at=expire_at,
            status="active",
        )
    )
    user.member_status = "member"
    user.member_expire_at = expire_at
    db.flush()
    return ok({
        "order_no": order.order_no,
        "status": order.status,
        "transaction_id": order.transaction_id,
        "member_expire_at": _iso(expire_at),
        "already_processed": False,
    })


@router.get("/billing/orders", summary="订单列表")
def list_orders(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户订单列表（创建时间倒序，含状态与商品编码）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"orders": [订单视图...]}。
    """
    rows = (
        db.query(Order, Product.product_code)
        .join(Product, Product.id == Order.product_id, isouter=True)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    orders: List[Dict[str, Any]] = [_order_view(order, code) for order, code in rows]
    return ok({"orders": orders})


@router.get("/billing/subscription", summary="会员订阅状态")
def get_subscription(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前有效订阅 + 会员状态；member_expire_at 已过期则惰性置 expired。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{member_status, member_expire_at, subscription}。
    """
    now = utcnow()
    # 惰性过期：到期扫描任务未跑时先在本请求内修正状态
    if user.member_status == "member" and user.member_expire_at is not None and user.member_expire_at < now:
        user.member_status = "expired"

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status == "active",
            Subscription.expire_at > now,
        )
        .order_by(Subscription.expire_at.desc())
        .first()
    )
    return ok({
        "member_status": user.member_status,
        "member_expire_at": _iso(user.member_expire_at),
        "subscription": {
            "start_at": _iso(sub.start_at),
            "expire_at": _iso(sub.expire_at),
            "status": sub.status,
            "source_order_id": sub.source_order_id,
        }
        if sub is not None
        else None,
    })

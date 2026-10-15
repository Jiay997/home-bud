# -*- coding: utf-8 -*-
"""订单对账差异检测服务（对账闭环的发现侧）。

与 app/jobs/scheduler.py 既有 reconcile job（paid 且未对账 → matched）互补：
本模块负责"差异检测"——已支付但渠道回调缺失（notify_status 为空或 missed）、
且对账状态尚未闭环的订单，超过宽限期（1 小时）后置 reconcile_status='diff'，
由后台 /admin/orders/{order_no}/reconcile-resolve 端点人工闭环处置。

调度接入（由运行方负责，本模块不注册定时器）：
    from app.services.reconcile import run_reconcile_check
    run_reconcile_check(db)  # -> {"checked": N, "diff_count": M}
"""
from datetime import timedelta
from typing import Dict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Order
from ..models.base import utcnow

# 支付成功到渠道回调到达的宽限期：超过此窗仍未收到回调才判差异
DIFF_GRACE_HOURS = 1


def run_reconcile_check(db: Session) -> Dict[str, int]:
    """执行一轮对账差异检测（纯函数式：只改 reconcile_status，不提交事务）。

    判定口径：status='paid' 且 notify_status IS NULL 或 'missed'，
    且 reconcile_status IS NULL 或 'pending'，且 paid_at 早于 now-1h
    （宽限期内不判差异，容忍渠道回调延迟）的订单 → reconcile_status='diff'。

    Args:
        db: 数据库会话（调用方负责 commit/rollback，本函数仅 flush）。

    Returns:
        {"checked": 扫描的候选订单数, "diff_count": 其中被置 diff 的订单数}。

    Raises:
        Exception: 查询或落库失败时向上抛出（由调用方决定重试策略）。
    """
    cutoff = utcnow() - timedelta(hours=DIFF_GRACE_HOURS)
    # 候选集：已支付 + 回调缺失 + 对账未闭环（paid_at 过滤在内存中做，便于统计 checked）
    candidates = (
        db.query(Order)
        .filter(
            Order.status == "paid",
            or_(Order.notify_status.is_(None), Order.notify_status == "missed"),
            or_(Order.reconcile_status.is_(None), Order.reconcile_status == "pending"),
        )
        .all()
    )
    diff_orders = []
    for order in candidates:
        # 防御：paid 单必有 paid_at；为 None 时不判差异（等下一轮）
        if order.paid_at is not None and order.paid_at < cutoff:
            order.reconcile_status = "diff"
            diff_orders.append(order)
    db.flush()
    return {"checked": len(candidates), "diff_count": len(diff_orders)}
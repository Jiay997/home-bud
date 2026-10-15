# -*- coding: utf-8 -*-
"""运行指标与告警 API 模块。

端点：
- GET /metrics   运行指标与告警快照（进程内聚合）
- GET /admin/metrics/alert-history   告警历史留痕查询（管理员鉴权）

暴露维度：请求/Agent/降级/拦截/额度用尽计数、P50/P95 延迟、
关键比率（agent_fail_rate/timeout_rate/degraded_rate）及超阈值触发的
告警列表。进程内视角，供运维探查与告警核对；多实例汇聚留待
外部监控接入时扩展。

告警闭环：alert_watch 定时任务（app.jobs.scheduler）每分钟评估快照并
以 JobRunLog（job_name='alert_watch'）留痕，本模块的告警历史端点
读取该留痕供后台监控页回溯展示。
"""
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.deps import get_admin
from ...core.envelope import ok
from ...core.observe import metrics
from ...db import get_db
from ...models import AdminUser, JobRunLog

router = APIRouter(tags=["系统"])


@router.get("/metrics")
def get_metrics():
    """运行指标与告警：进程内聚合快照（计数/延迟分位/比率/告警）。

    Args:
        无。

    Returns:
        统一包络：{counters, latency:{p50,p95,samples}, rates, alerts}。

    Raises:
        无（指标读取为进程内内存操作，不涉及外部依赖）。
    """
    return ok(metrics.snapshot())


@router.get("/admin/metrics/alert-history")
def get_alert_history(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """告警历史：alert_watch 任务留痕最近 50 条（按发生时间倒序）。

    Args:
        admin: 鉴权后的当前后台账号（仅校验登录态，无额外权限矩阵）。
        db: 数据库会话。

    Returns:
        统一包络：{items:[{id, metric, value, threshold, message, status,
        started_at}]}；metric/value/threshold/message 从留痕 detail JSON 解析。

    Raises:
        ApiError: 1101 未登录（由 get_admin 依赖抛出）。
    """
    rows = (
        db.query(JobRunLog)
        .filter(JobRunLog.job_name == "alert_watch")
        .order_by(JobRunLog.started_at.desc())
        .limit(50)
        .all()
    )
    items: List[Dict] = []
    for row in rows:
        detail: Dict = row.detail if isinstance(row.detail, dict) else {}
        items.append(
            {
                "id": row.id,
                "metric": detail.get("metric"),
                "value": detail.get("value"),
                "threshold": detail.get("threshold"),
                "message": detail.get("message"),
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
            }
        )
    return ok({"items": items})

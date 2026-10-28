# -*- coding: utf-8 -*-
"""留存与主动触达 API 模块（RQ-08）。

端点：

- GET  /reminders                    提醒列表 + 订阅偏好总览 + 待展示数
- PUT  /reminders/prefs              逐类型开启 / 关闭（关闭即时生效）
- POST /reminders/prefs/off          一键关闭全部触达（站内周报仍可回看）
- POST /reminders/{task_uid}/open    标记已打开（归因链起点，返回 trace_id）
- GET  /reminders/weekly-report      成长周报（站内页，不含问答原文）
- GET  /reminders/weekly-question    每周一问话题卡
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser
from ...services import reminder_service as rs
from .consent_api import require_base_consent

logger = logging.getLogger("jiaban.reminders_api")

router = APIRouter(tags=["C端-档案"])


class PrefBody(BaseModel):
    """订阅偏好设置请求体。

    Attributes:
        pref_type: vaccine / checkup / deworm / report / weekly_q / all。
        enabled: 是否开启。
    """

    pref_type: str = Field(..., description="偏好类型（含 all 总开关）")
    enabled: bool = Field(..., description="是否开启")


@router.get(
    "/reminders",
    summary="提醒列表与订阅偏好",
    description="返回提醒任务（含站内补达）、订阅偏好总览与待展示数；不展示问答原文",
)
def list_reminders(
    limit: int = 50,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取提醒列表与偏好总览（AC-RQ08-1 / AC-RQ08-7）。

    Args:
        limit: 最大返回条数。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{items[], prefs, due_count, weekly_cap, template_reported}。
    """
    require_base_consent(db, user.id)
    # D-08：列表接口惰性生成到期任务，避免只能等定时任务导致「已开启提醒
    # 但仍显示暂无任务」。生成幂等，失败不阻断列表读取。
    try:
        rs.generate_tasks_for_user(db, user.id)
        db.commit()
    except Exception:  # noqa: BLE001 — 生成失败不阻断已有任务展示
        db.rollback()
        logger.warning("reminder lazy generation failed user=%s", user.id, exc_info=True)
    prefs = rs.prefs_overview(db, user.id)
    return ok(
        {
            "items": rs.list_tasks(db, user.id, limit=min(max(limit, 1), 100)),
            "prefs": prefs,
            "due_count": rs.due_count(db, user.id),
            "weekly_cap": {"weekly_max": prefs["weekly_max"]},
        }
    )


@router.put(
    "/reminders/prefs",
    summary="设置订阅偏好",
    description="逐类型开启/关闭；关闭即时生效并不再发送任何订阅消息",
)
def update_pref(
    body: PrefBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """设置单个订阅偏好（AC-RQ08-1 / AC-RQ08-7）。

    Args:
        body: 偏好设置请求体。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{pref_type, enabled, prefs}。

    Raises:
        ApiError: 1001 pref_type 非法。
    """
    require_base_consent(db, user.id)
    try:
        if body.pref_type == "all":
            # D-18：总开关必须级联全部子类型，否则界面出现「总开关已开启、
            # 子项仍关闭」的矛盾状态；关闭时同时把待发任务转 skipped。
            if body.enabled:
                for pref_type in rs.PREF_TYPES:
                    rs.set_pref(db, user.id, pref_type, True)
            else:
                rs.disable_all(db, user.id)
                rs.set_pref(db, user.id, "all", False)
        else:
            rs.set_pref(db, user.id, body.pref_type, body.enabled)
    except ValueError as exc:
        raise ApiError(code=1001, message=str(exc), http_status=422)
    db.commit()
    return ok(
        {
            "pref_type": body.pref_type,
            "enabled": body.enabled,
            "prefs": rs.prefs_overview(db, user.id),
        }
    )


@router.post(
    "/reminders/prefs/off",
    summary="关闭全部触达",
    description="立即生效：待发任务转 skipped、全部类型置关闭；周报站内页仍可回看",
)
def disable_all_reminders(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """一键关闭全部触达（AC-RQ08-7）。

    Args:
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{disabled: true, canceled_tasks, prefs}。
    """
    require_base_consent(db, user.id)
    canceled = rs.disable_all(db, user.id)
    db.commit()
    return ok(
        {
            "disabled": True,
            "canceled_tasks": canceled,
            "prefs": rs.prefs_overview(db, user.id),
        }
    )


@router.post(
    "/reminders/{task_uid}/open",
    summary="标记提醒已打开",
    description="归因链起点：返回 reminder_trace_id，提问时透传以支撑 M21",
)
def open_reminder(
    task_uid: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """标记任务已打开（AC-RQ08-8）。

    Args:
        task_uid: 任务对外标识。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{task_uid, status, trace_id}。

    Raises:
        ApiError: 1002 任务不存在或非本人。
    """
    require_base_consent(db, user.id)
    result = rs.mark_opened(db, user.id, task_uid)
    if result is None:
        raise ApiError(*ERR_NOT_FOUND)
    db.commit()
    return ok(result)


@router.get(
    "/reminders/weekly-report",
    summary="成长周报",
    description="站内周报：本月龄变化、可问主题推荐、上周问答主题标签（不含原文）",
)
def weekly_report(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取成长周报（AC-RQ08-5）。

    Args:
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{period, profiles[], last_week_topics[], suggested_questions[]}。
    """
    require_base_consent(db, user.id)
    return ok(rs.weekly_report(db, user.id))


@router.get(
    "/reminders/weekly-question",
    summary="每周一问",
    description="分龄话题卡 + 预置问题，点击直达问答输入态",
)
def weekly_question(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取每周一问话题卡（AC-RQ08-6）。

    Args:
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{title, question, kb_id, trace_id, enabled}。
    """
    require_base_consent(db, user.id)
    return ok(rs.weekly_question(db, user.id))

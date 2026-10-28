# -*- coding: utf-8 -*-
"""后台定时任务调度模块（APScheduler BackgroundScheduler）。

注册 3 个周期任务（架构文档 §7 / PA-08）：
- reconcile：每 6 小时，将 paid 且未对账订单置 matched，同日幂等（JobRunLog）。
- assessment_draft_cleanup：每 1 小时，清理过期的测评断点草稿标记。
- channel_review_remind：每 24 小时，提醒 7 天内到期的危机渠道复核。

模块收口追加任务（spec close-module-gaps Task 2）：
- report_render：每 30 分钟，为未渲染长图的测评报告装配 image_meta（协议 V1），
  幂等键 = 报告 uid，每报告只渲染一次，单条失败不中断整批。
- orphan_sweep：每 5 分钟，streaming 超 5 分钟未完成的会话置 orphaned（保留可回看），
  幂等键 = 当天日期+小时，同小时重跑跳过。

告警闭环追加任务（alert_watch）：
- alert_watch：每 1 分钟，读取进程内指标快照（core.observe），超阈值告警
  以 JobRunLog（job_name='alert_watch'）留痕（status='alert'），幂等键 =
  指标名 + 10 分钟窗口（同窗口天然去重，依赖 (job_name, idempotency_key)
  唯一约束），新告警留痕成功且配置了 alert_webhook_url 时推送 webhook 通知。

任务内部自建数据库会话；任何异常仅记录日志，不中断调度循环。

V3.1 追加任务：
- channel_review_sweep：每 24 小时，复核到期未复核的渠道降级为 pending_review
  （RQ-03 AC-RQ03-4，前端自此不再展示号码）；
- photo_purge：每 30 分钟，删除 24h 到期的图片原图并写删除日志
  （RQ-05 DR-27 / AC-RQ05-3）；
- reminder_sweep：每 1 小时，生成里程碑 / 周报 / 每周一问任务并按频控发送
  （RQ-08 NFR-A6 / DR-30，超频顺延、失败转站内补达）。
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import IntegrityError

from ..core.config import get_settings
from ..core.observe import metrics
from ..db import get_session_factory
from ..models import Assessment, CrisisChannel, JobRunLog, Order, QaSession, Report

# 调度器专用日志器
logger = logging.getLogger("jiaban.scheduler")

# 模块级调度器单例（None 表示未启动）
_scheduler = None


def _run_reconcile() -> None:
    """对账任务（每 6 小时）：paid 且 reconcile_status 为空的订单置 matched。

    幂等策略：JobRunLog 唯一键 (job_name, idempotency_key)，
    幂等键取当天日期（UTC），同日重跑直接跳过。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        session = get_session_factory()()
        try:
            now = datetime.now(timezone.utc)
            idem_key = now.date().isoformat()  # 幂等键 = 当天日期
            exists = (
                session.query(JobRunLog)
                .filter(JobRunLog.job_name == "reconcile", JobRunLog.idempotency_key == idem_key)
                .first()
            )
            if exists is not None:
                # 已有当日执行记录：幂等跳过
                logger.info("reconcile already ran today (%s), skip", idem_key)
                return
            # 待对账订单：已支付但对账状态为空
            orders = (
                session.query(Order)
                .filter(Order.status == "paid", Order.reconcile_status.is_(None))
                .all()
            )
            for order in orders:
                order.reconcile_status = "matched"
            session.add(
                JobRunLog(
                    job_name="reconcile",
                    idempotency_key=idem_key,
                    biz_date=now.date(),
                    affected_rows=len(orders),
                    status="ok",
                    started_at=now,
                    finished_at=datetime.now(timezone.utc),
                    detail={"matched_orders": len(orders)},
                )
            )
            session.commit()
            logger.info("reconcile done: %d orders matched", len(orders))
        finally:
            session.close()
    except Exception:
        logger.exception("reconcile job failed")


def _run_assessment_draft_cleanup() -> None:
    """测评断点清理任务（每 1 小时）：has_draft 且 draft_expire_at 已过期的置 False。

    断点草稿不进历史报告列表，过期后仅清除断点标记，不删除作答数据。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        session = get_session_factory()()
        try:
            now = datetime.now(timezone.utc)
            rows = (
                session.query(Assessment)
                .filter(
                    Assessment.has_draft.is_(True),
                    Assessment.draft_expire_at.isnot(None),
                    Assessment.draft_expire_at < now,
                )
                .all()
            )
            for row in rows:
                row.has_draft = False
            session.commit()
            if rows:
                logger.info("assessment draft cleanup: %d expired drafts cleared", len(rows))
        finally:
            session.close()
    except Exception:
        logger.exception("assessment_draft_cleanup job failed")


def _run_channel_review_remind() -> None:
    """危机渠道复核提醒任务（每 24 小时）。

    扫描 next_review_due_at 早于 now+7d 的渠道并输出提醒日志，
    号码未确认（placeholder）渠道一并列出，督促运营复核。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        session = get_session_factory()()
        try:
            deadline = datetime.now(timezone.utc) + timedelta(days=7)
            channels = (
                session.query(CrisisChannel)
                .filter(
                    CrisisChannel.next_review_due_at.isnot(None),
                    CrisisChannel.next_review_due_at < deadline,
                )
                .all()
            )
            for ch in channels:
                logger.warning(
                    "渠道 %s(%s) 复核到期日 %s，7 天内需复核（当前状态 %s）",
                    ch.channel_code,
                    ch.channel_name,
                    ch.next_review_due_at,
                    ch.status,
                )
            logger.info("channel review remind: %d channels due within 7 days", len(channels))
        finally:
            session.close()
    except Exception:
        logger.exception("channel_review_remind job failed")


# ==================== 模块收口追加任务（spec close-module-gaps Task 2） ====================

# 长图渲染协议 V1 常量：免责面积占比（合规下限 0.15）、免责出现次数（合规下限 2）
IMAGE_DISCLAIMER_RATIO = 0.18
IMAGE_DISCLAIMER_COUNT = 3
IMAGE_FONT_SIZE_PT = 12
IMAGE_SCALE = 2
IMAGE_PROTOCOL_VERSION = "V1"
IMAGE_SECTIONS_COUNT = 13


def build_image_meta(report_uid: str) -> dict:
    """装配报告长图渲染元数据（渲染协议 V1，可独立调用便于测试）。

    免责合规口径：disclaimer_ratio=0.18（≥0.15）、disclaimer_count=3（≥2），
    渲染层按该元数据保证长图免责面积与出现次数达标。

    Args:
        report_uid: 报告对外标识（用于拼装二维码占位链接）。

    Returns:
        长图渲染元数据字典：{disclaimer_ratio, disclaimer_count, font_size_pt,
        scale, qr_placeholder, protocol_version, sections_count}。
    """
    return {
        "disclaimer_ratio": IMAGE_DISCLAIMER_RATIO,
        "disclaimer_count": IMAGE_DISCLAIMER_COUNT,
        "font_size_pt": IMAGE_FONT_SIZE_PT,
        "scale": IMAGE_SCALE,
        "qr_placeholder": f"https://jiaban.example/r/{report_uid}",
        "protocol_version": IMAGE_PROTOCOL_VERSION,
        "sections_count": IMAGE_SECTIONS_COUNT,
    }


def _run_report_render() -> None:
    """报告长图渲染任务（每 30 分钟）：未渲染的测评报告装配 image_meta 并置渲染时间。

    幂等策略：JobRunLog 唯一键 (job_name='report_render', idempotency_key=报告 uid)，
    status='ok' 的记录存在即跳过（每报告只渲染一次；'failed' 记录允许下轮重试，
    重试成功时原地复用该行，规避唯一键冲突）。
    单次任务内逐条 try/except：单报告失败记 detail（status='failed'），不中断整批。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        session = get_session_factory()()
        try:
            now = datetime.now(timezone.utc)
            reports = (
                session.query(Report)
                .filter(
                    Report.image_rendered_at.is_(None),
                    Report.report_type == "assessment",
                )
                .all()
            )
            rendered = 0
            failures: list = []
            for report in reports:
                uid = getattr(report, "report_uid", "?")
                try:
                    # 幂等检查：同键记录 ok 则跳过；failed 行复用（下轮重试）
                    row = (
                        session.query(JobRunLog)
                        .filter(
                            JobRunLog.job_name == "report_render",
                            JobRunLog.idempotency_key == uid,
                        )
                        .first()
                    )
                    if row is not None and row.status == "ok":
                        continue
                    meta = build_image_meta(uid)
                    report.image_meta = meta
                    report.image_rendered_at = datetime.now(timezone.utc)
                    if row is None:
                        row = JobRunLog(job_name="report_render", idempotency_key=uid)
                        session.add(row)
                    # 新建行或复用 failed 行：原地更新为成功留痕
                    row.biz_date = now.date()
                    row.affected_rows = 1
                    row.status = "ok"
                    row.started_at = now
                    row.finished_at = datetime.now(timezone.utc)
                    row.detail = {"report_uid": uid, "protocol_version": meta["protocol_version"]}
                    rendered += 1
                    session.commit()
                except Exception as exc:  # noqa: BLE001 — 单条失败不中断整批
                    session.rollback()
                    failures.append({"report_uid": uid, "error": str(exc)})
                    logger.error("report_render failed for %s: %s", uid, exc)
                    try:
                        # 失败留痕（复用或新建 failed 行，不破坏唯一键，下轮可重试）
                        row = (
                            session.query(JobRunLog)
                            .filter(
                                JobRunLog.job_name == "report_render",
                                JobRunLog.idempotency_key == uid,
                            )
                            .first()
                        )
                        if row is None:
                            row = JobRunLog(job_name="report_render", idempotency_key=uid)
                            session.add(row)
                        row.biz_date = now.date()
                        row.affected_rows = 0
                        row.status = "failed"
                        row.started_at = now
                        row.finished_at = datetime.now(timezone.utc)
                        row.detail = {"report_uid": uid, "error": str(exc)}
                        session.commit()
                    except Exception:
                        session.rollback()
                        logger.exception("report_render failure log failed: %s", uid)
            if rendered or failures:
                logger.info(
                    "report_render done: %d rendered, %d failed", rendered, len(failures)
                )
        finally:
            session.close()
    except Exception:
        logger.exception("report_render job failed")


def _run_orphan_sweep() -> None:
    """孤儿会话清理任务（每 5 分钟）：streaming 超 5 分钟未完成的会话置 orphaned。

    幂等策略：JobRunLog 唯一键 (job_name='orphan_sweep', idempotency_key=当天日期+小时)，
    同小时重跑查存在即跳过（幂等返回上次结果语义）。
    orphaned 会话保留可回看（不删除数据，仅状态收敛，客户端见 1405）。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        session = get_session_factory()()
        try:
            now = datetime.now(timezone.utc)
            idem_key = now.strftime("%Y%m%d%H")  # 幂等键 = 当天日期+小时
            exists = (
                session.query(JobRunLog)
                .filter(
                    JobRunLog.job_name == "orphan_sweep",
                    JobRunLog.idempotency_key == idem_key,
                )
                .first()
            )
            if exists is not None:
                # 本小时已有执行记录：幂等跳过
                logger.info("orphan_sweep already ran this hour (%s), skip", idem_key)
                return
            cutoff = now - timedelta(minutes=5)
            orphans = (
                session.query(QaSession)
                .filter(
                    QaSession.status == "streaming",
                    QaSession.created_at < cutoff,
                )
                .all()
            )
            for s in orphans:
                s.status = "orphaned"
            session.add(
                JobRunLog(
                    job_name="orphan_sweep",
                    idempotency_key=idem_key,
                    biz_date=now.date(),
                    affected_rows=len(orphans),
                    status="ok",
                    started_at=now,
                    finished_at=datetime.now(timezone.utc),
                    detail={"orphaned_sessions": len(orphans)},
                )
            )
            session.commit()
            if orphans:
                logger.info("orphan_sweep done: %d sessions orphaned", len(orphans))
        finally:
            session.close()
    except Exception:
        logger.exception("orphan_sweep job failed")


def record_alerts(alerts, now, webhook_poster=None) -> int:
    """告警留痕落库（可独立调用便于测试）：每条告警一行 JobRunLog。

    幂等策略：JobRunLog 唯一键 (job_name='alert_watch', idempotency_key)，
    幂等键 = f"{metric}-{YYYYMMDDHH}{minute//10}"，同一指标在 10 分钟窗口内
    天然去重——依赖 (job_name, idempotency_key) 唯一约束，插入冲突即回滚跳过，
    且不触发 webhook（避免重复通知）。

    Args:
        alerts: 告警字典列表（每项含 metric/value/threshold/message）。
        now: 告警发生时间（决定幂等键窗口，通常传 UTC now）。
        webhook_poster: webhook 推送回调（可选）；新插入成功时以 dict 调用，
            内容为 alert 详情 + occurred_at + job='alert_watch'。约定该回调
            自行吞掉网络异常，不向上抛出。

    Returns:
        本次新插入的告警留痕条数（幂等跳过的不计入）。

    Raises:
        无（数据库不可达等异常向上抛出，由调用方 try/except 收口）。
    """
    if not alerts:
        return 0
    session = get_session_factory()()
    inserted = 0
    try:
        for alert in alerts:
            metric = str(alert.get("metric", "unknown"))
            idem_key = f"{metric}-{now.strftime('%Y%m%d%H')}{now.minute // 10}"
            occurred_at = now.isoformat()
            row = JobRunLog(
                job_name="alert_watch",
                idempotency_key=idem_key,
                biz_date=now.date(),
                affected_rows=1,
                status="alert",
                started_at=now,
                finished_at=datetime.now(timezone.utc),
                detail={
                    "metric": metric,
                    "value": alert.get("value"),
                    "threshold": alert.get("threshold"),
                    "message": alert.get("message"),
                    "occurred_at": occurred_at,
                },
            )
            try:
                session.add(row)
                session.commit()
            except IntegrityError:
                # 唯一键冲突：同窗口已留痕过该告警，回滚跳过且不重复通知
                session.rollback()
                continue
            inserted += 1
            if webhook_poster is not None:
                webhook_poster(
                    {
                        "metric": metric,
                        "value": alert.get("value"),
                        "threshold": alert.get("threshold"),
                        "message": alert.get("message"),
                        "occurred_at": occurred_at,
                        "job": "alert_watch",
                    }
                )
    finally:
        session.close()
    return inserted


def _run_alert_watch() -> None:
    """告警值守任务（每 1 分钟）：指标快照超阈值告警落库留痕并推送 webhook。

    读取进程内 metrics.snapshot()，alerts 非空时逐条 record_alerts 留痕；
    webhook 推送仅在 alert_webhook_url 配置非空时进行（timeout=5s，
    失败仅 logging.warning 不抛出，不影响调度与留痕）。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """

    def _post_webhook(payload: dict) -> None:
        """告警 webhook 推送内部实现。

        Args:
            payload: 推送载荷（alert 详情 + occurred_at + job='alert_watch'）。

        Returns:
            None。

        Raises:
            无（网络异常吞掉并 logging.warning，保证不中断告警留痕循环）。
        """
        url = get_settings().alert_webhook_url
        if not url:
            return
        try:
            import httpx  # 延迟导入：避免调度模块加载期引入网络栈（规避循环依赖）

            httpx.post(url, json=payload, timeout=5.0)
        except Exception:
            logger.warning(
                "alert_watch webhook post failed: metric=%s",
                payload.get("metric"),
                exc_info=True,
            )

    try:
        snapshot = metrics.snapshot()
        alerts = snapshot.get("alerts") or []
        if not alerts:
            return
        inserted = record_alerts(
            alerts, datetime.now(timezone.utc), webhook_poster=_post_webhook
        )
        if inserted:
            logger.info("alert_watch: %d alert(s) recorded", inserted)
    except Exception:
        logger.exception("alert_watch job failed")


# ==================== V3.1 增量任务（RQ-03 / RQ-05 / RQ-08） ====================


def _run_channel_review_sweep() -> None:
    """渠道复核到期降级（每 24 小时）：超期未复核条目转 pending_review。

    AC-RQ03-4：到期未复核的条目前端不再展示号码，只展示名称与「信息更新中」。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        from ..services import channel_service

        session = get_session_factory()()
        try:
            downgraded = channel_service.sweep_expired(session)
            if downgraded:
                logger.warning("channel_review_sweep: %d channels downgraded", downgraded)
        finally:
            session.close()
    except Exception:
        logger.exception("channel_review_sweep job failed")


def _run_photo_purge() -> None:
    """图片原图到期删除（每 30 分钟）：删除 24h 到期原图并写删除日志。

    DR-27 / AC-RQ05-3：删除动作必须可出具执行日志（时间、对象、结果）；
    原图不进入备份与缓存。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        from ..services import photo_service

        session = get_session_factory()()
        try:
            removed = photo_service.purge_expired(session)
            if removed:
                logger.info("photo_purge: %d images deleted (24h TTL)", removed)
        finally:
            session.close()
    except Exception:
        logger.exception("photo_purge job failed")


def _run_reminder_sweep() -> None:
    """触达扫描（每 1 小时）：生成里程碑 / 周报 / 每周一问任务并发送。

    NFR-A6：任务不丢——发送失败重试 1 次后转站内补达；超频任务顺延不丢弃。
    频控与偏好闸门均由 `reminder_service` 统一裁决（DR-30）。

    Raises:
        无（异常吞掉并记录堆栈，不中断调度）。
    """
    try:
        from ..services import reminder_service

        session = get_session_factory()()
        try:
            created = reminder_service.generate_weekly_tasks(session)
            stats = reminder_service.run_reminder_sweep(session)
            if created or stats.get("sent"):
                logger.info(
                    "reminder_sweep: weekly_created=%d users=%d sent=%d deferred=%d failed=%d",
                    created,
                    stats.get("users", 0),
                    stats.get("sent", 0),
                    stats.get("deferred", 0),
                    stats.get("failed", 0),
                )
        finally:
            session.close()
    except Exception:
        logger.exception("reminder_sweep job failed")


def start_scheduler() -> None:
    """启动全局调度器并注册周期任务（幂等：重复调用忽略）。

    注册 6 个任务：既有 3 任务（reconcile/draft_cleanup/channel_remind）
    + 模块收口追加 2 任务（report_render/orphan_sweep）
    + 告警闭环追加 1 任务（alert_watch）。

    Raises:
        无（启动失败向上抛出，由调用方决定是否阻断应用启动）。
    """
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_run_reconcile, "interval", hours=6, id="reconcile")
    _scheduler.add_job(
        _run_assessment_draft_cleanup, "interval", hours=1, id="assessment_draft_cleanup"
    )
    _scheduler.add_job(
        _run_channel_review_remind, "interval", hours=24, id="channel_review_remind"
    )
    # 模块收口追加：报告长图渲染（每 30 分钟）与孤儿会话清理（每 5 分钟）
    _scheduler.add_job(_run_report_render, "interval", minutes=30, id="report_render")
    _scheduler.add_job(_run_orphan_sweep, "interval", minutes=5, id="orphan_sweep")
    # 告警闭环追加：指标告警值守（每 1 分钟，超阈值留痕 + webhook 通知）
    _scheduler.add_job(_run_alert_watch, "interval", minutes=1, id="alert_watch")
    # V3.1 追加：渠道复核降级（24h）/ 图片原图删除（30m）/ 触达扫描（1h）
    _scheduler.add_job(
        _run_channel_review_sweep, "interval", hours=24, id="channel_review_sweep"
    )
    _scheduler.add_job(_run_photo_purge, "interval", minutes=30, id="photo_purge")
    _scheduler.add_job(_run_reminder_sweep, "interval", hours=1, id="reminder_sweep")
    _scheduler.start()
    logger.info(
        "scheduler started with 9 jobs: reconcile/6h, draft_cleanup/1h, "
        "channel_remind/24h, report_render/30m, orphan_sweep/5m, alert_watch/1m, "
        "channel_review_sweep/24h, photo_purge/30m, reminder_sweep/1h"
    )


def stop_scheduler() -> None:
    """停止全局调度器（应用关闭时调用；未启动时为空操作）。

    Raises:
        无（关闭异常吞掉，避免影响进程退出）。
    """
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
    except Exception:
        logger.exception("scheduler shutdown failed")
    finally:
        _scheduler = None
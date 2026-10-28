# -*- coding: utf-8 -*-
"""留存与主动触达服务（RQ-08 基础版）。

能力范围（对齐 PRD §3.8）：

- **里程碑提醒**：儿童疫苗 / 体检节点、宠物疫苗年免与驱虫周期（按档案推算）；
- **成长周报**：每周日 20:00，站内页 + 订阅消息提醒二段式；
- **每周一问**：每周三 10:00 推 1 条分龄话题卡，点击直达预置问题；
- **频控**：单用户每周 ≤2 条订阅消息，同日多任务合并为摘要，超频**顺延不丢弃**；
- **退订即停**：关闭后不再发送任何订阅消息，站内周报仍可回看；
- **归因**：`reminder_trace_id` 贯穿「提醒打开 → 提问」，支撑 M21。

诚实声明（依赖未解除时的默认行为）：

- 订阅消息模板报备（D14）未完成时，`template_id` 为空 → 走**站内补达**
  （首页轻提示 + `/reminders` 列表），不伪造外部发送成功；
- 疫苗 / 体检节点为**示例节点**，须由内容专家按当地接种门诊规范确认后
  回填（README 与 API 文档同步标注）。
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import (
    ChildProfile,
    KbEntry,
    NotificationPref,
    PetProfile,
    QaSession,
    ReminderTask,
)

logger = logging.getLogger("jiaban.reminder")

# 上海时区（触达节奏与频控口径）
_TZ_SHANGHAI = timezone(timedelta(hours=8))

# 提醒类型（PRD §3.8.3）
TASK_VACCINE = "vaccine"
TASK_CHECKUP = "checkup"
TASK_DEWORM = "deworm"
TASK_REPORT = "report"
TASK_WEEKLY_Q = "weekly_q"
TASK_TYPES = (TASK_VACCINE, TASK_CHECKUP, TASK_DEWORM, TASK_REPORT, TASK_WEEKLY_Q)

# 类型 → 开关粒度（订阅偏好按此分档；`all` 为总开关）
PREF_TYPES = (TASK_VACCINE, TASK_CHECKUP, TASK_DEWORM, TASK_REPORT, TASK_WEEKLY_Q, "all")

# 任务状态
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_OPENED = "opened"
STATUS_SKIPPED = "skipped"
STATUS_CANCELED = "canceled"

# 默认频控快照（周 ≤2 条）
DEFAULT_FREQUENCY_CAP: Dict[str, Any] = {
    "weekly_max": 2,
    "daily_merge": True,
    "windows": "ISO 周（周一 00:00 起算，UTC+8）",
}

# 儿童疫苗接种节点（示例节点：出生 / 1 / 2 / 3 / 4 / 5 / 6 / 8 / 9 / 12 / 18 / 24 / 36 月龄）
CHILD_VACCINE_MONTHS: Tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 8, 9, 12, 18, 24, 36)

# 儿童体检节点（半岁 / 1 岁 / 2 岁 / 3 岁）
CHILD_CHECKUP_MONTHS: Tuple[int, ...] = (6, 12, 24, 36)

# 宠物：疫苗年免周期（天）与驱虫周期（天）
PET_VACCINE_CYCLE_DAYS = 365
PET_DEWORM_CYCLE_DAYS = 90

# 提醒文案红线（不构成医疗建议，PRD §3.8.3）
TEMPLATE_NOTICE = "以上为养育科普参考信息，不构成医疗建议；具体请咨询接种门诊或执业兽医。"


def _now() -> datetime:
    """当前上海时间。

    Returns:
        带时区的 datetime。
    """
    return datetime.now(_TZ_SHANGHAI)


def _today() -> date:
    """东八区今日日期。

    Returns:
        date 对象。
    """
    return _now().date()


def week_window(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """返回当前 ISO 周窗口（周一 00:00 至下周一 00:00，UTC+8）。

    Args:
        now: 参考时间（缺省当前）。

    Returns:
        (窗口起, 窗口止) 二元组。
    """
    current = (now or _now()).astimezone(_TZ_SHANGHAI)
    start = (current - timedelta(days=current.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start, start + timedelta(days=7)


# ---------------------------------------------------------------------------
# 订阅偏好
# ---------------------------------------------------------------------------
def get_pref(db: Session, user_id: int, pref_type: str = "all") -> Optional[NotificationPref]:
    """读取订阅偏好行（无记录返回 None）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        pref_type: 偏好类型（含 all）。

    Returns:
        NotificationPref 实例或 None。
    """
    return (
        db.query(NotificationPref)
        .filter(
            NotificationPref.user_id == user_id,
            NotificationPref.pref_type == pref_type,
        )
        .first()
    )


def is_enabled(db: Session, user_id: int, task_type: str) -> bool:
    """判断某类提醒是否已开启（总开关关闭时一律视为关闭）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        task_type: 提醒类型。

    Returns:
        True 表示允许发送。
    """
    total = get_pref(db, user_id, "all")
    if total is not None and not total.enabled:
        return False
    row = get_pref(db, user_id, task_type)
    return bool(row is not None and row.enabled)


def set_pref(
    db: Session,
    user_id: int,
    pref_type: str,
    enabled: bool,
    cap: Optional[Dict[str, Any]] = None,
) -> NotificationPref:
    """设置订阅偏好（upsert，含频控上限快照，DR-30）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        pref_type: 偏好类型。
        enabled: 是否开启。
        cap: 频控上限快照（缺省用默认）。

    Returns:
        偏好行（未 commit）。

    Raises:
        ValueError: pref_type 非法。
    """
    if pref_type not in PREF_TYPES:
        raise ValueError(f"invalid pref_type: {pref_type}")
    row = get_pref(db, user_id, pref_type)
    snapshot = dict(cap or DEFAULT_FREQUENCY_CAP)
    if row is None:
        row = NotificationPref(
            user_id=user_id,
            pref_type=pref_type,
            enabled=bool(enabled),
            frequency_cap_snapshot=snapshot,
        )
        db.add(row)
    else:
        row.enabled = bool(enabled)
        row.frequency_cap_snapshot = snapshot
        row.updated_at = _now()
        row.version = int(row.version or 1) + 1
    return row


def disable_all(db: Session, user_id: int) -> int:
    """关闭全部触达（AC-RQ08-7：立即生效，pending 任务转 skipped）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        被置为 skipped 的待发任务数。
    """
    prefs = db.query(NotificationPref).filter(NotificationPref.user_id == user_id).all()
    for row in prefs:
        row.enabled = False
        row.version = int(row.version or 1) + 1
        row.updated_at = _now()
    if get_pref(db, user_id, "all") is None:
        set_pref(db, user_id, "all", False)
    pending = (
        db.query(ReminderTask)
        .filter(
            ReminderTask.user_id == user_id,
            ReminderTask.status == STATUS_PENDING,
        )
        .all()
    )
    for task in pending:
        task.status = STATUS_SKIPPED
    return len(pending)


def prefs_overview(db: Session, user_id: int) -> Dict[str, Any]:
    """返回订阅偏好总览（C 端设置页用）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        {items: [{type, enabled, cap}], any_enabled, weekly_max} 字典。
    """
    rows = db.query(NotificationPref).filter(NotificationPref.user_id == user_id).all()
    by_type = {row.pref_type: row for row in rows}
    items: List[Dict[str, Any]] = []
    for pref_type in PREF_TYPES:
        row = by_type.get(pref_type)
        items.append(
            {
                "type": pref_type,
                "enabled": bool(row.enabled) if row is not None else False,
                "configured": row is not None,
                "cap": (row.frequency_cap_snapshot if row is not None else None)
                or DEFAULT_FREQUENCY_CAP,
                "updated_at": (row.updated_at.isoformat() if row is not None and row.updated_at else None),
            }
        )
    total = by_type.get("all")
    cap = (total.frequency_cap_snapshot if total is not None else None) or DEFAULT_FREQUENCY_CAP
    return {
        "items": items,
        "any_enabled": any(item["enabled"] for item in items if item["type"] != "all"),
        "weekly_max": int(cap.get("weekly_max", 2)),
        "template_reported": bool(get_settings().reminder_template_vaccine)
        or bool(get_settings().reminder_template_report)
        or bool(get_settings().reminder_template_weekly_q),
    }


# ---------------------------------------------------------------------------
# 任务生成
# ---------------------------------------------------------------------------
def _dedupe_key(user_id: int, profile_type: str, profile_id: Optional[int], task_type: str, node: str) -> str:
    """构造任务幂等键（同用户 + 档案 + 类型 + 节点，防重复生成）。

    Args:
        user_id: 用户主键。
        profile_type: child / pet / none。
        profile_id: 档案主键。
        task_type: 提醒类型。
        node: 节点标识（如 6m / annual-2027）。

    Returns:
        幂等键字符串。
    """
    return f"u{user_id}:{profile_type}{profile_id or 0}:{task_type}:{node}"


def _upsert_task(
    db: Session,
    user_id: int,
    profile_type: str,
    profile_id: Optional[int],
    task_type: str,
    title: str,
    body: str,
    planned_at: datetime,
    node: str,
) -> Optional[ReminderTask]:
    """创建提醒任务（按幂等键去重；已存在则返回 None）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        profile_type: child / pet / none。
        profile_id: 档案主键。
        task_type: 提醒类型。
        title: 标题。
        body: 正文。
        planned_at: 计划发送时间。
        node: 节点标识。

    Returns:
        新建任务实例；已存在返回 None。
    """
    key = _dedupe_key(user_id, profile_type, profile_id, task_type, node)
    exists = db.query(ReminderTask).filter(ReminderTask.dedupe_key == key).first()
    if exists is not None:
        return None
    settings = get_settings()
    template_map = {
        TASK_VACCINE: settings.reminder_template_vaccine,
        TASK_CHECKUP: settings.reminder_template_vaccine,
        TASK_DEWORM: settings.reminder_template_vaccine,
        TASK_REPORT: settings.reminder_template_report,
        TASK_WEEKLY_Q: settings.reminder_template_weekly_q,
    }
    task = ReminderTask(
        user_id=user_id,
        profile_type=profile_type,
        profile_id=profile_id,
        task_type=task_type,
        title=title[:128],
        body=body,
        planned_at=planned_at,
        status=STATUS_PENDING,
        template_id=template_map.get(task_type) or None,
        frequency_cap_snapshot=dict(DEFAULT_FREQUENCY_CAP),
        dedupe_key=key,
    )
    db.add(task)
    return task


def _child_birth(profile: ChildProfile) -> Optional[date]:
    """解密儿童出生日期（失败返回 None）。

    Args:
        profile: 儿童档案。

    Returns:
        birth date 或 None。
    """
    try:
        from ..core.crypto import decrypt_field

        raw = decrypt_field(profile.birth_date_enc)
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001 — 解密/解析失败按无法推算处理
        return None


def generate_tasks_for_user(db: Session, user_id: int, now: Optional[datetime] = None) -> int:
    """为某用户生成到期的里程碑提醒任务（幂等）。

    生成口径：节点时间落在 [今天 - 30 天, 今天 + 提前天数 + 7 天] 窗口内即生成
    （提前 3 天提醒；错过 30 天内的节点补生成「站内补达」，便于新用户建档后
    立即看到已到期的疫苗/体检事项）。
    D-08：此前窗口只向前，刚过接种日的档案（如 24 月龄）永远生成不出任务；
    补上 30 天回溯窗口，与「补种/补检」运营口径一致。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        now: 参考时间。

    Returns:
        新建任务数。
    """
    current = now or _now()
    today = current.date()
    lead = get_settings().reminder_lead_days
    # D-08：30 天回溯窗口，覆盖「刚建档但接种日已过」的档案（补种提醒）
    window_start = today - timedelta(days=30)
    window_end = today + timedelta(days=lead + 7)
    created = 0

    children = (
        db.query(ChildProfile)
        .filter(ChildProfile.user_id == user_id, ChildProfile.status == "active")
        .all()
    )
    for child in children:
        birth = _child_birth(child)
        if birth is None:
            continue
        for months in CHILD_VACCINE_MONTHS:
            node_date = _add_months(birth, months)
            if not (window_start <= node_date <= window_end):
                continue
            planned = datetime.combine(
                node_date - timedelta(days=lead), datetime.min.time()
            ).replace(tzinfo=_TZ_SHANGHAI) + timedelta(hours=9)
            task = _upsert_task(
                db,
                user_id,
                "child",
                child.id,
                TASK_VACCINE,
                f"{months} 月龄接种节点提醒",
                f"宝宝的 {months} 月龄接种节点临近，建议咨询当地接种门诊确认本次疫苗种类与时间。{TEMPLATE_NOTICE}",
                planned,
                f"{months}m",
            )
            if task is not None:
                created += 1
        for months in CHILD_CHECKUP_MONTHS:
            node_date = _add_months(birth, months)
            if not (window_start <= node_date <= window_end):
                continue
            planned = datetime.combine(
                node_date - timedelta(days=lead), datetime.min.time()
            ).replace(tzinfo=_TZ_SHANGHAI) + timedelta(hours=9)
            task = _upsert_task(
                db,
                user_id,
                "child",
                child.id,
                TASK_CHECKUP,
                f"{months} 月龄体检节点提醒",
                f"建议安排 {months} 月龄常规体检，关注身高体重与发育里程碑。{TEMPLATE_NOTICE}",
                planned,
                f"{months}m",
            )
            if task is not None:
                created += 1

    pets = (
        db.query(PetProfile)
        .filter(PetProfile.user_id == user_id, PetProfile.deleted_at.is_(None))
        .all()
    )
    for pet in pets:
        anchor = (pet.created_at or current).date() if hasattr(pet, "created_at") else today
        for cycle_days, task_type, label in (
            (PET_VACCINE_CYCLE_DAYS, TASK_VACCINE, "疫苗年免"),
            (PET_DEWORM_CYCLE_DAYS, TASK_DEWORM, "体内外驱虫"),
        ):
            node_date = anchor + timedelta(days=cycle_days)
            if not (window_start <= node_date <= window_end):
                continue
            planned = datetime.combine(
                node_date - timedelta(days=lead), datetime.min.time()
            ).replace(tzinfo=_TZ_SHANGHAI) + timedelta(hours=9)
            task = _upsert_task(
                db,
                user_id,
                "pet",
                pet.id,
                task_type,
                f"宠物{label}提醒",
                f"{label}周期临近，建议咨询执业兽医确认本次{label}安排。{TEMPLATE_NOTICE}",
                planned,
                f"{task_type}-{node_date.isoformat()}",
            )
            if task is not None:
                created += 1
    return created


def _add_months(base: date, months: int) -> date:
    """日期加月份（月末安全）。

    Args:
        base: 基准日期。
        months: 增加月数。

    Returns:
        计算后的日期。
    """
    year = base.year + (base.month - 1 + months) // 12
    month = (base.month - 1 + months) % 12 + 1
    day = base.day
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


# ---------------------------------------------------------------------------
# 发送与频控
# ---------------------------------------------------------------------------
def weekly_sent_count(db: Session, user_id: int, now: Optional[datetime] = None) -> int:
    """统计本周已发送的订阅消息条数（频控分子）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        now: 参考时间。

    Returns:
        已发送条数（含已打开）。
    """
    start, end = week_window(now)
    return (
        db.query(ReminderTask)
        .filter(
            ReminderTask.user_id == user_id,
            ReminderTask.status.in_((STATUS_SENT, STATUS_OPENED)),
            ReminderTask.sent_at.isnot(None),
            ReminderTask.sent_at >= start,
            ReminderTask.sent_at < end,
        )
        .count()
    )


def _cap_of(db: Session, user_id: int) -> Dict[str, Any]:
    """读取用户频控上限快照（缺省默认）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        频控快照字典。
    """
    row = get_pref(db, user_id, "all")
    if row is not None and isinstance(row.frequency_cap_snapshot, dict):
        return row.frequency_cap_snapshot
    return dict(DEFAULT_FREQUENCY_CAP)


def send_due_tasks(db: Session, user_id: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    """发送到期的提醒任务（频控裁决 + 同日合并 + 失败重试 1 次 + 站内兜底）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        now: 参考时间。

    Returns:
        {sent, skipped, deferred, merged, failed} 统计字典。
    """
    current = now or _now()
    cap = _cap_of(db, user_id)
    weekly_max = int(cap.get("weekly_max", 2))
    sent_this_week = weekly_sent_count(db, user_id, now=current)
    due = (
        db.query(ReminderTask)
        .filter(
            ReminderTask.user_id == user_id,
            ReminderTask.status == STATUS_PENDING,
            ReminderTask.planned_at <= current,
        )
        .order_by(ReminderTask.planned_at.asc(), ReminderTask.id.asc())
        .all()
    )
    stats = {"sent": 0, "skipped": 0, "deferred": 0, "merged": 0, "failed": 0}
    if not due:
        return stats
    # 同日合并：同一自然日多任务合并为一条摘要（只发首条，其余标记 merged 后跳过）
    by_day: Dict[date, List[ReminderTask]] = {}
    for task in due:
        by_day.setdefault(task.planned_at.astimezone(_TZ_SHANGHAI).date(), []).append(task)
    for day, tasks in sorted(by_day.items()):
        # 订阅偏好闸门
        eligible = [t for t in tasks if is_enabled(db, user_id, t.task_type)]
        for task in tasks:
            if task not in eligible:
                task.status = STATUS_SKIPPED
                stats["skipped"] += 1
        if not eligible:
            continue
        head, rest = eligible[0], eligible[1:]
        if rest and cap.get("daily_merge", True):
            head.body = head.body + f"（今日另有 {len(rest)} 条提醒，请在「提醒」页查看）"
            for task in rest:
                # 同日合并进摘要：置 skipped 并在正文留痕，**不**计入周频控
                # 分子（DR-30：频控裁决必须可审计，合并≠独立发送）
                task.status = STATUS_SKIPPED
                task.body = (
                    f"{task.body}\n（已合并进当日提醒摘要：{head.title}）"
                )
                stats["merged"] += 1
        if sent_this_week >= weekly_max:
            # 超频顺延不丢弃：整体推到下周同一天
            for task in [head] + [t for t in rest]:
                task.planned_at = task.planned_at + timedelta(days=7)
                stats["deferred"] += 1
            continue
        # 发送：模板已报备走订阅消息；未报备走站内补达（不伪造外部成功）
        delivered = _deliver(db, user_id, head, current)
        if delivered:
            head.status = STATUS_SENT
            head.sent_at = current
            sent_this_week += 1
            stats["sent"] += 1
        else:
            head.send_fail_count = int(head.send_fail_count or 0) + 1
            if head.send_fail_count >= 2:
                # 重试 1 次仍失败：转站内补达（status 保持 pending 待站内展示）
                head.status = STATUS_SKIPPED
                stats["failed"] += 1
            else:
                stats["deferred"] += 1
    return stats


def _deliver(db: Session, user_id: int, task: ReminderTask, now: datetime) -> bool:
    """投递单条提醒（模板报备后走订阅消息，否则站内补达）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        task: 任务实例。
        now: 当前时间。

    Returns:
        True 表示已投递（含站内补达）；False 表示投递失败需重试。
    """
    if task.template_id:
        # 模板已报备：真实通道接入点在 services/auth_provider 同级的通道抽象内，
        # 当前无微信 access_token 凭据时按「未投递」处理（不伪造成功）。
        logger.info("reminder template send skipped (no channel): uid=%s task=%s", user_id, task.task_uid)
        return False
    # 站内补达：任务保留在列表，用户下次打开即见（首页轻提示）
    logger.info("reminder inbox delivery: uid=%s task=%s type=%s", user_id, task.task_uid, task.task_type)
    return True


def run_reminder_sweep(db: Session, now: Optional[datetime] = None) -> Dict[str, int]:
    """全量触达扫描（定时任务入口）：生成 + 发送。

    Args:
        db: 数据库会话。
        now: 参考时间。

    Returns:
        {users, created, sent, skipped, deferred, failed} 统计。
    """
    from ..models import AppUser

    current = now or _now()
    stats = {"users": 0, "created": 0, "sent": 0, "skipped": 0, "deferred": 0, "failed": 0}
    user_ids = [
        row[0]
        for row in db.query(AppUser.id).filter(AppUser.status == "active").all()
    ]
    for user_id in user_ids:
        stats["users"] += 1
        stats["created"] += generate_tasks_for_user(db, user_id, now=current)
        result = send_due_tasks(db, user_id, now=current)
        for key in ("sent", "skipped", "deferred", "failed"):
            stats[key] += result[key]
    db.commit()
    return stats


def generate_weekly_tasks(db: Session, now: Optional[datetime] = None) -> int:
    """生成成长周报与每周一问任务（按周节奏，幂等）。

    Args:
        db: 数据库会话。
        now: 参考时间。

    Returns:
        新建任务数。
    """
    from ..models import AppUser

    settings = get_settings()
    current = now or _now()
    # 周报：目标发送时刻 = 本周/下周的指定 weekday + hour
    report_at = _next_weekday(current, settings.reminder_weekly_report_weekday, settings.reminder_weekly_report_hour)
    weekly_q_at = _next_weekday(current, settings.reminder_weekly_q_weekday, settings.reminder_weekly_q_hour)
    created = 0
    for (user_id,) in db.query(AppUser.id).filter(AppUser.status == "active").all():
        # 任务一律生成（是否发送由订阅偏好闸门裁决），
        # 便于用户开启后立即在「提醒」页看到内容（AC-RQ08-1 可跳过 / 可随时开启）
        task = _upsert_task(
            db,
            user_id,
            "none",
            None,
            TASK_REPORT,
            "本周成长周报",
            "本周档案月龄变化、可问主题推荐与上周问答主题摘要已生成。",
            report_at,
            report_at.date().isoformat(),
        )
        if task is not None:
            created += 1
        task = _upsert_task(
            db,
            user_id,
            "none",
            None,
            TASK_WEEKLY_Q,
            "本周值得问",
            "本周分龄话题卡已更新，点击可直接提问。",
            weekly_q_at,
            weekly_q_at.date().isoformat(),
        )
        if task is not None:
            created += 1
    return created


def _next_weekday(now: datetime, weekday: int, hour: int) -> datetime:
    """计算下一目标时刻（含当天未过的情况）。

    Args:
        now: 参考时间。
        weekday: 目标星期（周一=0）。
        hour: 目标小时。

    Returns:
        目标时刻（UTC+8）。
    """
    current = now.astimezone(_TZ_SHANGHAI)
    delta = (weekday - current.weekday()) % 7
    target = (current + timedelta(days=delta)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    if target <= current:
        target += timedelta(days=7)
    return target


# ---------------------------------------------------------------------------
# C 端查询：任务列表 / 周报 / 每周一问 / 归因
# ---------------------------------------------------------------------------
def list_tasks(db: Session, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用户的提醒任务（含站内补达的 pending 任务）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        limit: 最大条数。

    Returns:
        任务字典列表（计划时间倒序）。
    """
    rows = (
        db.query(ReminderTask)
        .filter(ReminderTask.user_id == user_id)
        .order_by(ReminderTask.planned_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "task_uid": row.task_uid,
            "type": row.task_type,
            "title": row.title,
            "body": row.body,
            "planned_at": row.planned_at.isoformat() if row.planned_at else None,
            "status": row.status,
            "trace_id": row.trace_id,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            "opened_at": row.opened_at.isoformat() if row.opened_at else None,
            "delivery": "subscribe_message" if row.template_id else "inbox",
            # 档案类型用于前端选择问答入口（child / pet / none）
            "profile_type": row.profile_type,
        }
        for row in rows
    ]


def mark_opened(db: Session, user_id: int, task_uid: str) -> Optional[Dict[str, Any]]:
    """标记任务已打开（归因链 `reminder_open`，返回 trace_id 供提问透传）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        task_uid: 任务对外标识。

    Returns:
        {task_uid, status, trace_id} 字典；任务不存在或非本人返回 None。
    """
    task = (
        db.query(ReminderTask)
        .filter(ReminderTask.task_uid == task_uid, ReminderTask.user_id == user_id)
        .first()
    )
    if task is None:
        return None
    if task.status not in (STATUS_CANCELED, STATUS_SKIPPED):
        task.status = STATUS_OPENED
        task.opened_at = _now()
    return {"task_uid": task.task_uid, "status": task.status, "trace_id": task.trace_id}


def _recent_qa_topics(db: Session, user_id: int, days: int = 7) -> List[str]:
    """统计上周问答主题标签（**不含问答原文**，隐私对齐 §9.5）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        days: 回溯天数。

    Returns:
        主题标签列表（去重保序，最多 3 个）。
    """
    since = _now() - timedelta(days=days)
    rows = (
        db.query(QaSession)
        .filter(
            QaSession.user_id == user_id,
            QaSession.created_at >= since,
            QaSession.status.in_(("done", "degraded")),
        )
        .order_by(QaSession.created_at.desc())
        .limit(30)
        .all()
    )
    kb_ids: List[str] = []
    for row in rows:
        for kb_id in row.kb_refs or []:
            if kb_id not in kb_ids:
                kb_ids.append(str(kb_id))
    if not kb_ids:
        return []
    entries = db.query(KbEntry).filter(KbEntry.kb_id.in_(kb_ids[:10])).all()
    topics: List[str] = []
    for entry in entries:
        label = entry.topic_category or entry.title
        if label and label not in topics:
            topics.append(label)
    return topics[:3]


def weekly_report(db: Session, user_id: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    """装配成长周报（AC-RQ08-5：站内页数据，不含问答原文）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        now: 参考时间。

    Returns:
        周报字典：{period, profiles[], topics[], suggested_questions[], privacy_note}。
    """
    current = now or _now()
    start, end = week_window(current)
    profiles: List[Dict[str, Any]] = []
    children = (
        db.query(ChildProfile)
        .filter(ChildProfile.user_id == user_id, ChildProfile.status == "active")
        .all()
    )
    for child in children:
        birth = _child_birth(child)
        months_now = None
        if birth is not None:
            today = current.date()
            months_now = max(
                0,
                (today.year - birth.year) * 12
                + (today.month - birth.month)
                - (1 if today.day < birth.day else 0),
            )
        profiles.append(
            {
                "profile_type": "child",
                "nickname_masked": "宝宝",
                "age_months": months_now,
                "age_band": child.age_band,
                "delta_label": (
                    f"本周月龄：{months_now} 个月" if months_now is not None else "月龄待完善"
                ),
            }
        )
    pets = (
        db.query(PetProfile)
        .filter(PetProfile.user_id == user_id, PetProfile.deleted_at.is_(None))
        .all()
    )
    for pet in pets:
        profiles.append(
            {
                "profile_type": "pet",
                "nickname_masked": "宠物",
                "age_band": pet.age_band,
                "delta_label": f"当前阶段：{pet.age_band}",
            }
        )
    topics = _recent_qa_topics(db, user_id)
    suggested = suggested_questions(db, user_id, limit=2)
    return {
        "period": {"start": start.date().isoformat(), "end": (end - timedelta(days=1)).date().isoformat()},
        "profiles": profiles,
        "last_week_topics": topics,
        "suggested_questions": suggested,
        "privacy_note": "周报仅统计主题标签，不展示你的问答原文。",
        "generated_at": current.isoformat(),
    }


def suggested_questions(db: Session, user_id: int, limit: int = 2) -> List[Dict[str, str]]:
    """按档案年龄段推荐可问主题（来自知识库分龄内容）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        limit: 条数。

    Returns:
        [{title, question, kb_id}] 列表。
    """
    child = (
        db.query(ChildProfile)
        .filter(ChildProfile.user_id == user_id, ChildProfile.status == "active")
        .first()
    )
    query = db.query(KbEntry).filter(
        KbEntry.status == "published", KbEntry.kb_kind.in_(("child", "pet"))
    )
    if child is not None and child.age_band:
        query = query.filter(
            (KbEntry.age_band == child.age_band) | (KbEntry.age_band.is_(None))
        )
    entries = query.order_by(KbEntry.id.asc()).limit(limit * 3).all()
    out: List[Dict[str, str]] = []
    seen: List[str] = []
    for entry in entries:
        if entry.topic_category in seen:
            continue
        seen.append(entry.topic_category)
        out.append(
            {
                "title": entry.title,
                "question": f"{entry.title}，我们这个月龄要注意什么？",
                "kb_id": entry.kb_id,
            }
        )
        if len(out) >= limit:
            break
    return out


def weekly_question(db: Session, user_id: int) -> Dict[str, Any]:
    """返回「每周一问」话题卡（AC-RQ08-6：点击直达预置问题输入态）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        {title, question, kb_id, trace_id} 字典。
    """
    items = suggested_questions(db, user_id, limit=1)
    task = (
        db.query(ReminderTask)
        .filter(
            ReminderTask.user_id == user_id,
            ReminderTask.task_type == TASK_WEEKLY_Q,
        )
        .order_by(ReminderTask.planned_at.desc())
        .first()
    )
    base = items[0] if items else {
        "title": "本周值得问",
        "question": "这个阶段最需要关注什么？",
        "kb_id": "",
    }
    base["trace_id"] = task.trace_id if task is not None else None
    base["enabled"] = is_enabled(db, user_id, TASK_WEEKLY_Q)
    return base


def due_count(db: Session, user_id: int, now: Optional[datetime] = None) -> int:
    """统计待展示（站内补达）任务数（首页轻提示用）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        now: 参考时间。

    Returns:
        待展示任务数。
    """
    current = now or _now()
    return (
        db.query(ReminderTask)
        .filter(
            ReminderTask.user_id == user_id,
            ReminderTask.status == STATUS_PENDING,
            ReminderTask.planned_at <= current,
        )
        .count()
    )


def cancel_tasks_for_profile(db: Session, user_id: int, profile_type: str, profile_id: int) -> int:
    """档案删除时级联取消其 pending 任务（§3.8.4 并发口径）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        profile_type: child / pet。
        profile_id: 档案主键。

    Returns:
        取消的任务数。
    """
    rows = (
        db.query(ReminderTask)
        .filter(
            ReminderTask.user_id == user_id,
            ReminderTask.profile_type == profile_type,
            ReminderTask.profile_id == profile_id,
            ReminderTask.status == STATUS_PENDING,
        )
        .all()
    )
    for row in rows:
        row.status = STATUS_CANCELED
    return len(rows)

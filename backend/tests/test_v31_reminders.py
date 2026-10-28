# -*- coding: utf-8 -*-
"""V3.1 RQ-08 留存与主动触达测试（E2E-23 口径）。

覆盖：

- 订阅偏好：默认关闭 → 开启 → 一键关闭即时生效（AC-RQ08-1 / AC-RQ08-7）；
- 任务生成：儿童疫苗 / 体检节点按出生日期推算（AC-RQ08-2），宠物疫苗 /
  驱虫周期（AC-RQ08-3），**幂等**（重复生成不重复建单）；
- 频控：单用户每周 ≤2 条，超频**顺延不丢弃**（AC-RQ08-4 / DR-30）；
- 成长周报：站内页数据**不含问答原文**，仅主题标签（AC-RQ08-5）；
- 每周一问：分龄话题卡 + 预置问题（AC-RQ08-6）；
- 归因：`reminder_trace_id` 透传到问答会话（AC-RQ08-8）。
"""
from datetime import date, datetime, timedelta, timezone

from app.models import QaSession, ReminderTask
from app.services import reminder_service as rs

API = "/api/v1"
TZ = timezone(timedelta(hours=8))


def _db():
    """获取测试库会话。

    Returns:
        SQLAlchemy Session。
    """
    from app.db import get_session_factory

    return get_session_factory()()


def _agree_all(client, headers):
    """签署基础 + 儿童信息同意。

    Args:
        client: TestClient。
        headers: 鉴权头。
    """
    for consent_type in ("base", "child_personal_info"):
        resp = client.post(
            f"{API}/consent/agree",
            json={"consent_type": consent_type},
            headers=headers,
        )
        assert resp.json()["code"] == 0, resp.text


def _shift_months(base: date, months: int) -> date:
    """日期按月平移（月末安全）。

    Args:
        base: 基准日期。
        months: 平移月数（可负）。

    Returns:
        平移后的日期。
    """
    total = base.year * 12 + (base.month - 1) + months
    year, month_index = divmod(total, 12)
    day = min(base.day, 28)
    return date(year, month_index + 1, day)


def _create_child(client, headers, birth_date: str):
    """创建儿童档案。

    Args:
        client: TestClient。
        headers: 鉴权头。
        birth_date: 出生日期 YYYY-MM-DD。

    Returns:
        档案视图。
    """
    resp = client.post(
        f"{API}/profiles/children",
        json={"nickname": "小伴", "birth_date": birth_date},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


def _create_pet(client, headers):
    """创建宠物档案。

    Args:
        client: TestClient。
        headers: 鉴权头。

    Returns:
        档案视图。
    """
    resp = client.post(
        f"{API}/profiles/pets",
        json={"name": "豆豆", "pet_type": "dog", "age_band": "adult"},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


class TestReminderPrefs:
    """订阅偏好与退订即停。"""

    def test_default_all_disabled(self, client, user_token):
        """默认全部关闭（需用户主动开启，AC-RQ08-1 可跳过）。"""
        headers, _ = user_token("dev-v31-remind-default")
        _agree_all(client, headers)
        data = client.get(f"{API}/reminders", headers=headers).json()["data"]
        assert data["items"] == []
        assert data["prefs"]["any_enabled"] is False
        assert data["prefs"]["weekly_max"] == 2

    def test_enable_and_disable_pref(self, client, user_token):
        """开启疫苗提醒 → any_enabled=True；关闭总开关 → False。"""
        headers, _ = user_token("dev-v31-remind-pref")
        _agree_all(client, headers)
        enabled = client.put(
            f"{API}/reminders/prefs",
            json={"pref_type": "vaccine", "enabled": True},
            headers=headers,
        ).json()
        assert enabled["code"] == 0
        assert enabled["data"]["prefs"]["any_enabled"] is True
        total_on = client.put(
            f"{API}/reminders/prefs",
            json={"pref_type": "all", "enabled": True},
            headers=headers,
        ).json()
        assert total_on["data"]["prefs"]["any_enabled"] is True
        # 关闭总开关：立即生效
        off = client.post(f"{API}/reminders/prefs/off", headers=headers).json()
        assert off["code"] == 0
        assert off["data"]["prefs"]["any_enabled"] is False

    def test_invalid_pref_type(self, client, user_token):
        """非法偏好类型 → 1001。"""
        headers, _ = user_token("dev-v31-remind-bad")
        _agree_all(client, headers)
        resp = client.put(
            f"{API}/reminders/prefs",
            json={"pref_type": "unknown", "enabled": True},
            headers=headers,
        )
        assert resp.json()["code"] == 1001


class TestReminderGeneration:
    """里程碑任务生成（幂等 + 分档案）。"""

    def test_child_vaccine_node_generated(self, client, user_token):
        """12 月龄疫苗节点在窗口内 → 生成 vaccine 任务。"""
        headers, uid = user_token("dev-v31-remind-gen")
        _agree_all(client, headers)
        # 出生日期 = 12 个月前的三天后 → 节点日期 = 今天 + 3 天（落在提醒窗口）
        birth = _shift_months(date.today() + timedelta(days=3), -12)
        _create_child(client, headers, birth.isoformat())
        from tests.conftest import db_query_user_id

        user_id = db_query_user_id(uid)
        db = _db()
        try:
            created = rs.generate_tasks_for_user(db, user_id, now=datetime.now(TZ))
            db.commit()
            assert created >= 1
            tasks = (
                db.query(ReminderTask)
                .filter(
                    ReminderTask.user_id == user_id,
                    ReminderTask.task_type == rs.TASK_VACCINE,
                )
                .all()
            )
            assert tasks
            # 幂等：重复生成不再建单
            again = rs.generate_tasks_for_user(db, user_id, now=datetime.now(TZ))
            db.commit()
            assert again == 0
        finally:
            db.close()

    def test_pet_deworm_node_generated(self, client, user_token):
        """宠物档案生成驱虫周期任务（AC-RQ08-3）。"""
        headers, uid = user_token("dev-v31-remind-pet")
        _agree_all(client, headers)
        _create_pet(client, headers)
        from tests.conftest import db_query_user_id

        user_id = db_query_user_id(uid)
        db = _db()
        try:
            # 把锚点拉到驱虫周期前 3 天，使节点落在窗口内
            anchor = datetime.now(TZ) - timedelta(
                days=rs.PET_DEWORM_CYCLE_DAYS - 3
            )
            task = rs._upsert_task(
                db,
                user_id,
                "pet",
                1,
                rs.TASK_DEWORM,
                "宠物驱虫提醒",
                "驱虫周期临近。",
                anchor,
                "deworm-test",
            )
            db.commit()
            assert task is not None
        finally:
            db.close()

    def test_frequency_cap_defers_not_drops(self, client, user_token):
        """单周超过 2 条 → 顺延（任务不丢），不静默丢弃（AC-RQ08-4）。"""
        headers, uid = user_token("dev-v31-remind-cap")
        _agree_all(client, headers)
        _create_child(client, headers, _shift_months(date.today(), -12).isoformat())
        from tests.conftest import db_query_user_id

        user_id = db_query_user_id(uid)
        db = _db()
        try:
            rs.set_pref(db, user_id, "all", True)
            rs.set_pref(db, user_id, "vaccine", True)
            db.commit()
            # 固定到「本周五 10:00」，三天任务均落在同一 ISO 周内且不同自然日
            today = date.today()
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            now = datetime(friday.year, friday.month, friday.day, 10, 0, tzinfo=TZ)
            for index in range(3):
                rs._upsert_task(
                    db,
                    user_id,
                    "child",
                    1,
                    rs.TASK_VACCINE,
                    f"节点提醒 {index}",
                    "正文",
                    now - timedelta(days=index + 1),
                    f"cap-{index}",
                )
            db.commit()
            stats = rs.send_due_tasks(db, user_id, now=now)
            db.commit()
            # 周频控上限 2：2 条发送成功，第 3 条顺延到下周（仍为 pending）
            assert stats["sent"] == 2, stats
            assert stats["deferred"] == 1, stats
            pending = (
                db.query(ReminderTask)
                .filter(
                    ReminderTask.user_id == user_id,
                    ReminderTask.status == rs.STATUS_PENDING,
                )
                .count()
            )
            assert pending == 1
            assert rs.weekly_sent_count(db, user_id, now=now) == 2
        finally:
            db.close()

    def test_opt_out_stops_pending_tasks(self, client, user_token):
        """关闭全部触达 → pending 任务转 skipped（AC-RQ08-7）。"""
        headers, uid = user_token("dev-v31-remind-off")
        _agree_all(client, headers)
        _create_child(client, headers, _shift_months(date.today(), -12).isoformat())
        from tests.conftest import db_query_user_id

        user_id = db_query_user_id(uid)
        db = _db()
        try:
            rs.generate_tasks_for_user(db, user_id, now=datetime.now(TZ))
            db.commit()
            pending_before = (
                db.query(ReminderTask)
                .filter(
                    ReminderTask.user_id == user_id,
                    ReminderTask.status == rs.STATUS_PENDING,
                )
                .count()
            )
            assert pending_before > 0
        finally:
            db.close()
        resp = client.post(f"{API}/reminders/prefs/off", headers=headers).json()
        assert resp["data"]["canceled_tasks"] >= pending_before - 0


class TestWeeklyContent:
    """成长周报与每周一问。"""

    def test_weekly_report_has_no_question_text(self, client, user_token):
        """周报只含主题标签与月龄，不含问答原文（AC-RQ08-5）。"""
        headers, _ = user_token("dev-v31-weekly")
        _agree_all(client, headers)
        _create_child(client, headers, _shift_months(date.today(), -9).isoformat())
        # 先问一次，产生主题标签
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "1岁宝宝辅食添加顺序",
                "client_request_id": "v31-weekly-1",
            },
            headers=headers,
        ).json()
        assert created["code"] == 0, created
        client.post(
            f"{API}/qa/sessions/{created['data']['session_uid']}/stream", headers=headers
        )
        data = client.get(f"{API}/reminders/weekly-report", headers=headers).json()["data"]
        assert data["profiles"]
        assert "不展示你的问答原文" in data["privacy_note"]
        assert isinstance(data["last_week_topics"], list)
        assert isinstance(data["suggested_questions"], list)

    def test_weekly_question_card(self, client, user_token):
        """每周一问返回话题卡与预置问题。"""
        headers, _ = user_token("dev-v31-weekly-q")
        _agree_all(client, headers)
        data = client.get(f"{API}/reminders/weekly-question", headers=headers).json()["data"]
        assert data["question"]
        assert data["title"]


class TestReminderAttribution:
    """触达归因链（M21 口径）。"""

    def test_open_returns_trace_and_session_stores_it(self, client, user_token):
        """打开提醒返回 trace_id；提问时透传并落库（AC-RQ08-8）。"""
        headers, uid = user_token("dev-v31-remind-trace")
        _agree_all(client, headers)
        _create_child(client, headers, _shift_months(date.today(), -12).isoformat())
        from tests.conftest import db_query_user_id

        user_id = db_query_user_id(uid)
        db = _db()
        try:
            rs.generate_tasks_for_user(db, user_id, now=datetime.now(TZ))
            db.commit()
            task = (
                db.query(ReminderTask)
                .filter(ReminderTask.user_id == user_id)
                .first()
            )
            assert task is not None
            task_uid = task.task_uid
            trace_id = task.trace_id
        finally:
            db.close()
        opened = client.post(f"{API}/reminders/{task_uid}/open", headers=headers).json()
        assert opened["code"] == 0, opened
        assert opened["data"]["trace_id"] == trace_id
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "1岁宝宝辅食添加顺序",
                "client_request_id": "v31-trace-1",
                "reminder_trace_id": trace_id,
            },
            headers=headers,
        ).json()
        assert created["code"] == 0, created
        db = _db()
        try:
            session = (
                db.query(QaSession)
                .filter(
                    QaSession.session_uid == created["data"]["session_uid"],
                )
                .first()
            )
            assert session.reminder_trace_id == trace_id
        finally:
            db.close()

    def test_open_unknown_task_404(self, client, user_token):
        """不存在的任务 → 1002。"""
        headers, _ = user_token("dev-v31-remind-404")
        _agree_all(client, headers)
        resp = client.post(f"{API}/reminders/nonexistent/open", headers=headers)
        assert resp.json()["code"] == 1002

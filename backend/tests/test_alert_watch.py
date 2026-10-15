# -*- coding: utf-8 -*-
"""告警闭环单测（alert_watch 任务 + 告警历史端点）。

覆盖：
- record_alerts 留痕与幂等：超阈值告警写入 JobRunLog（job_name='alert_watch'，
  status='alert'），webhook_poster 仅在新插入成功时调用；同一 10 分钟窗口内
  重复告警因 (job_name, idempotency_key) 唯一约束去重（不发 webhook）；
  跨窗口（minute//10 变化）产生新键 → 新留痕 + 新通知；
- GET /api/v1/admin/metrics/alert-history：未带 token 返回 401；
  管理员登录后返回统一包络（code=0、items 为 list）且仅含 alert_watch 留痕。

留痕幂等通过内存假会话模拟唯一约束语义（commit 时按 (job_name,
idempotency_key) 查重，冲突抛 IntegrityError），不依赖真实数据库连接；
端点用例复用 conftest 的 client/admin_token 夹具（测试库 jiaban_test）。
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

# 保证以 tests/ 目录单独运行时也能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.jobs.scheduler as sched  # noqa: E402
from app.models import JobRunLog  # noqa: E402

# 固定告警样例（与 core.observe._evaluate_alerts 输出结构一致）
ALERTS = [
    {
        "metric": "agent_fail_rate",
        "value": 0.5,
        "threshold": 0.03,
        "message": "agent_fail_rate=0.5000 超过阈值 0.03",
    }
]

# 固定发生时间：12:07 → minute//10 = 0，幂等键为 agent_fail_rate-20261010120
NOW = datetime(2026, 10, 10, 12, 7, 0, tzinfo=timezone.utc)


class FakeAlertSession:
    """内存假数据库会话：模拟 JobRunLog (job_name, idempotency_key) 唯一约束。

    add() 暂存待写行；commit() 时按唯一键查重，冲突抛 IntegrityError
    （对齐真实 PG uk_job 约束语义），成功则落登记表；rollback() 丢弃暂存。

    Attributes:
        rows: 已提交成功的 JobRunLog 行列表。
        closed: close() 是否被调用。
    """

    def __init__(self):
        """初始化空登记表与暂存区。"""
        self.rows = []
        self._keys = set()
        self._pending = []
        self.closed = False

    def add(self, obj):
        """暂存待写对象（commit 时才查重落表）。

        Args:
            obj: ORM 模型实例。
        """
        self._pending.append(obj)

    def commit(self):
        """模拟 commit：逐行校验唯一键，冲突抛 IntegrityError。

        Raises:
            IntegrityError: (job_name, idempotency_key) 已存在时抛出。
        """
        for obj in self._pending:
            key = (obj.job_name, obj.idempotency_key)
            if key in self._keys:
                raise IntegrityError(
                    "INSERT INTO job_run_log", None,
                    Exception('duplicate key value violates unique constraint "uk_job"'),
                )
            self._keys.add(key)
            self.rows.append(obj)
        self._pending = []

    def rollback(self):
        """模拟 rollback：丢弃暂存区（已提交行不受影响）。"""
        self._pending = []

    def close(self):
        """记录关闭标记。"""
        self.closed = True


class TestRecordAlerts:
    """record_alerts：留痕写库 + 同窗口去重 + 跨窗口新通知。"""

    def test_record_dedupe_and_cross_window(self, monkeypatch):
        """首窗口留痕+通知；同窗口重复跳过；跨窗口（+11 分钟）新留痕+新通知。"""
        fake = FakeAlertSession()
        monkeypatch.setattr(sched, "get_session_factory", lambda: lambda: fake)

        calls = []

        def poster(payload):
            """假 webhook 推送：记录调用载荷。

            Args:
                payload: 推送载荷 dict。
            """
            calls.append(payload)

        # 首窗口：新留痕 1 条，poster 调用 1 次
        inserted = sched.record_alerts(ALERTS, NOW, webhook_poster=poster)
        assert inserted == 1
        assert len(fake.rows) == 1
        row = fake.rows[0]
        assert row.job_name == "alert_watch"
        assert row.idempotency_key == "agent_fail_rate-20261010120"
        assert row.status == "alert"
        assert row.detail["metric"] == "agent_fail_rate"
        assert row.detail["value"] == 0.5
        assert row.detail["threshold"] == 0.03
        assert len(calls) == 1
        assert calls[0]["job"] == "alert_watch"
        assert calls[0]["occurred_at"] == NOW.isoformat()

        # 同窗口再调：唯一键冲突去重，无新行、poster 仍只 1 次
        inserted2 = sched.record_alerts(ALERTS, NOW, webhook_poster=poster)
        assert inserted2 == 0
        assert len(fake.rows) == 1
        assert len(calls) == 1

        # 跨窗口（+11 分钟 → 12:18，minute//10=1）：新键 → 新留痕 + poster 共 2 次
        later = NOW + timedelta(minutes=11)
        inserted3 = sched.record_alerts(ALERTS, later, webhook_poster=poster)
        assert inserted3 == 1
        assert len(fake.rows) == 2
        assert fake.rows[1].idempotency_key == "agent_fail_rate-20261010121"
        assert len(calls) == 2
        assert calls[1]["occurred_at"] == later.isoformat()

    def test_no_poster_still_records(self, monkeypatch):
        """webhook_poster 缺省 None 时仅留痕不通知（不报错）。"""
        fake = FakeAlertSession()
        monkeypatch.setattr(sched, "get_session_factory", lambda: lambda: fake)
        assert sched.record_alerts(ALERTS, NOW) == 1
        assert len(fake.rows) == 1


class TestAlertHistoryApi:
    """GET /api/v1/admin/metrics/alert-history：鉴权与包络。"""

    def test_alert_history_requires_admin(self, client):
        """未带 token 访问告警历史 → 401（get_admin 依赖拒绝）。"""
        resp = client.get("/api/v1/admin/metrics/alert-history")
        assert resp.status_code == 401

    def test_alert_history_envelope_after_login(self, client, admin_token):
        """admin 登录后 200：包络 code=0、items 为 list 且仅含 alert_watch 留痕。"""
        from app.db import get_session_factory

        # 预置 1 条 alert_watch 留痕 + 1 条其他任务留痕（应被过滤）
        db = get_session_factory()()
        try:
            db.add(
                JobRunLog(
                    job_name="alert_watch",
                    idempotency_key="agent_fail_rate-20261010120",
                    biz_date=NOW.date(),
                    affected_rows=1,
                    status="alert",
                    started_at=NOW,
                    finished_at=NOW,
                    detail={
                        "metric": "agent_fail_rate",
                        "value": 0.5,
                        "threshold": 0.03,
                        "message": "agent_fail_rate=0.5000 超过阈值 0.03",
                        "occurred_at": NOW.isoformat(),
                    },
                )
            )
            db.add(
                JobRunLog(
                    job_name="reconcile",
                    idempotency_key=NOW.date().isoformat(),
                    biz_date=NOW.date(),
                    affected_rows=0,
                    status="ok",
                    started_at=NOW,
                    finished_at=NOW,
                    detail={"matched_orders": 0},
                )
            )
            db.commit()
        finally:
            db.close()

        headers = admin_token("admin")
        resp = client.get("/api/v1/admin/metrics/alert-history", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        items = body["data"]["items"]
        assert isinstance(items, list)
        assert len(items) == 1  # 仅 alert_watch 留痕（reconcile 行被过滤）
        assert items[0]["metric"] == "agent_fail_rate"
        assert items[0]["value"] == 0.5
        assert items[0]["threshold"] == 0.03
        assert items[0]["status"] == "alert"
        assert items[0]["started_at"] is not None

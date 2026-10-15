# -*- coding: utf-8 -*-
"""模块收口单测（spec close-module-gaps Task 2）。

覆盖：
- 内容安全送检：每日配额超限 1303（monkeypatch 配额）、submit/resolve 状态机
  （reviewing→pass/reject/manual、raw_deleted 副本删除、callback_log 仅存
  SHA-256 摘要）、本地规则裁决（高危词 reject / 放行标记 / 默认 pass）；
- 举报上报占位：report_to_authority 无凭据不报错；
- 后台任务纯逻辑：长图渲染元数据合规断言（ratio≥0.15 / count≥2 / scale=2）、
  report_render 幂等渲染与 orphan_sweep 同小时幂等（内存假会话）；
- 历史详情"内容已更新"标注：B/C 级已完成追溯命中 kb_refs 推导。

全部不依赖真实 HTTP 服务与数据库连接（模型仅实例化不建库）。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 保证以 tests/ 目录单独运行时也能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.cache import cache  # noqa: E402
from app.core.crypto import sha256_hex  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.models import ContentAuditRecord, JobRunLog, QaSession, Report  # noqa: E402
from app.services.safety_scan import (  # noqa: E402
    PASS_MARKER,
    SafetyScanService,
    report_to_authority,
)


# ---------------------------------------------------------------------------
# 假会话与假查询（SimpleNamespace 风格，参考 test_admin_perms.py）
# ---------------------------------------------------------------------------
class FakeSession:
    """内存假数据库会话：覆盖 safety_scan 所需的最小 Session 接口。

    Attributes:
        added: add() 收集的对象列表。
        committed: commit() 调用次数。
    """

    def __init__(self):
        """初始化空对象登记表与自增主键起点。"""
        self.added = []
        self.committed = 0
        self._identity = {}
        self._next_id = 1001

    def add(self, obj):
        """登记待写对象。

        Args:
            obj: ORM 模型实例。
        """
        self.added.append(obj)

    def flush(self):
        """模拟 flush：为未分配主键的对象依次编号并登记身份表。"""
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1
            self._identity.setdefault((type(obj), obj.id), obj)

    def commit(self):
        """模拟 commit：先 flush 分配主键再计数。"""
        self.flush()
        self.committed += 1

    def get(self, model, pk):
        """按 (模型, 主键) 取对象（对齐 Session.get 语义）。

        Args:
            model: ORM 模型类。
            pk: 主键值。

        Returns:
            已登记的对象；不存在返回 None。
        """
        return self._identity.get((model, pk))


class FakeQuery:
    """假查询对象：忽略 filter 条件，直接返回预置行集（first/all 语义）。"""

    def __init__(self, rows):
        """初始化预置行集。

        Args:
            rows: 查询应返回的行列表。
        """
        self._rows = list(rows)

    def filter(self, *args, **kwargs):
        """忽略过滤条件（内存假实现不解析 SQL 表达式）。

        Args:
            args: 位置过滤参数（忽略）。
            kwargs: 关键字过滤参数（忽略）。

        Returns:
            自身（链式调用）。
        """
        return self

    def first(self):
        """取首行。

        Returns:
            第一行；空集返回 None。
        """
        return self._rows[0] if self._rows else None

    def all(self):
        """取全部行。

        Returns:
            行列表副本。
        """
        return list(self._rows)


class FakeJobSession:
    """定时任务假会话：按模型分派行集，记录 commit/close 供断言。"""

    def __init__(self, job_logs=(), qa_sessions=(), reports=()):
        """初始化各模型的预置行集。

        Args:
            job_logs: JobRunLog 既有行。
            qa_sessions: QaSession 既有行。
            reports: Report 既有行。
        """
        self.job_logs = list(job_logs)
        self.qa_sessions = list(qa_sessions)
        self.reports = list(reports)
        self.commit_count = 0
        self.closed = False

    def query(self, model):
        """按模型分派假查询。

        Args:
            model: ORM 模型类。

        Returns:
            FakeQuery 实例。

        Raises:
            AssertionError: 未登记的模型类型。
        """
        if model is JobRunLog:
            return FakeQuery(self.job_logs)
        if model is QaSession:
            return FakeQuery(self.qa_sessions)
        if model is Report:
            return FakeQuery(self.reports)
        raise AssertionError(f"unexpected model: {model}")

    def add(self, obj):
        """登记新对象（仅处理 JobRunLog，与任务写入面一致）。

        Args:
            obj: ORM 模型实例。
        """
        if isinstance(obj, JobRunLog):
            self.job_logs.append(obj)

    def commit(self):
        """记录提交次数。"""
        self.commit_count += 1

    def close(self):
        """记录关闭标记。"""
        self.closed = True


@pytest.fixture
def quota_key():
    """配额计数键夹具：测试前后均清空进程内缓存键，避免串扰。

    Yields:
        当日配额计数键字符串。
    """
    key = SafetyScanService._quota_key()
    cache.delete(key)
    yield key
    cache.delete(key)


# ---------------------------------------------------------------------------
# 内容安全送检：配额
# ---------------------------------------------------------------------------
class TestSafetyScanQuota:
    """每日送检配额：未超限放行、超限 1303、submit 占用配额。"""

    def test_check_quota_ok_when_unused(self, quota_key):
        """未消耗配额时 check_quota 放行（不抛）。"""
        SafetyScanService.check_quota(FakeSession())

    def test_submit_increments_quota(self, quota_key):
        """submit 成功后当日配额计数 +1，记录处于 reviewing。"""
        db = FakeSession()
        record = SafetyScanService.submit(db, "text", "FB1", "feedback", "你好")
        assert record.audit_result == "reviewing"
        assert record.id is not None
        assert cache.get_int(quota_key) == 1

    def test_quota_exceeded_raises_1303(self, quota_key, monkeypatch):
        """已用次数达到配额（monkeypatch 配额=2）后 check_quota 抛 1303。"""
        monkeypatch.setenv("CONTENT_SCAN_QUOTA", "2")
        cache.incr(quota_key)
        cache.incr(quota_key)
        with pytest.raises(ApiError) as excinfo:
            SafetyScanService.check_quota(FakeSession())
        assert excinfo.value.code == 1303

    def test_submit_beyond_quota_raises_1303(self, quota_key, monkeypatch):
        """配额=1 时第二次 submit 直接拒绝（超配额拒绝放行）。"""
        monkeypatch.setenv("CONTENT_SCAN_QUOTA", "1")
        db = FakeSession()
        SafetyScanService.submit(db, "text", "FB1", "feedback", "第一条")
        with pytest.raises(ApiError) as excinfo:
            SafetyScanService.submit(db, "text", "FB2", "feedback", "第二条")
        assert excinfo.value.code == 1303

    def test_submit_stores_sha256_not_plaintext(self):
        """submit 正文不落库：callback_log 仅登记 SHA-256 摘要。"""
        db = FakeSession()
        record = SafetyScanService.submit(db, "text", "FB9", "feedback", "机密内容")
        assert record.callback_log["content_sha256"] == sha256_hex("机密内容")
        assert "机密内容" not in str(record.callback_log)


# ---------------------------------------------------------------------------
# 内容安全送检：resolve 状态机
# ---------------------------------------------------------------------------
class TestSafetyScanResolve:
    """resolve 裁决：pass/reject/manual、副本删除、幂等与非法入参。"""

    def _record(self, content="正文"):
        """构造一条 reviewing 记录。

        Args:
            content: 送检明文。

        Returns:
            (FakeSession, ContentAuditRecord)。
        """
        db = FakeSession()
        return db, SafetyScanService.submit(db, "text", "FB100", "feedback", content)

    def test_pass_flow(self):
        """reviewing→pass：audit_result/action 置位且副本删除（raw_deleted=True）。"""
        db, rec = self._record()
        out = SafetyScanService.resolve(db, rec.id, "pass", note="auto")
        assert out.audit_result == "pass"
        assert out.action == "allow"
        assert out.raw_deleted is True
        assert out.callback_log["verdict"] == "pass"
        assert out.callback_log["note"] == "auto"

    def test_reject_flow_blocks(self):
        """reviewing→reject：action=block，副本删除。"""
        db, rec = self._record()
        out = SafetyScanService.resolve(db, rec.id, "reject", note="high risk")
        assert out.audit_result == "reject"
        assert out.action == "block"
        assert out.raw_deleted is True

    def test_manual_flow(self):
        """reviewing→manual：action=manual_review，副本删除。"""
        db, rec = self._record()
        out = SafetyScanService.resolve(db, rec.id, "manual")
        assert out.audit_result == "manual"
        assert out.action == "manual_review"
        assert out.raw_deleted is True

    def test_duplicate_resolve_is_idempotent(self):
        """重复回调不覆盖既有结论（幂等返回现状）。"""
        db, rec = self._record()
        SafetyScanService.resolve(db, rec.id, "pass")
        out = SafetyScanService.resolve(db, rec.id, "reject")
        assert out.audit_result == "pass"
        assert out.action == "allow"

    def test_invalid_verdict_raises_1001(self):
        """非法裁决值拒绝（1001）。"""
        db, rec = self._record()
        with pytest.raises(ApiError) as excinfo:
            SafetyScanService.resolve(db, rec.id, "maybe")
        assert excinfo.value.code == 1001

    def test_missing_record_raises_1002(self):
        """记录不存在拒绝（1002）。"""
        with pytest.raises(ApiError) as excinfo:
            SafetyScanService.resolve(FakeSession(), 99999, "pass")
        assert excinfo.value.code == 1002


# ---------------------------------------------------------------------------
# 本地规则裁决
# ---------------------------------------------------------------------------
class TestLocalRuleVerdict:
    """_local_rule_verdict：高危词 reject、放行标记 pass、默认 pass。"""

    def test_high_risk_word_rejects(self):
        """命中高危词返回 reject。"""
        assert SafetyScanService._local_rule_verdict("教你制作爆炸物的步骤") == "reject"

    def test_pass_marker_passes(self):
        """含显式放行标记（审核通过测试）返回 pass。"""
        assert SafetyScanService._local_rule_verdict(f"冒烟{PASS_MARKER}样例") == "pass"

    def test_default_pass(self):
        """普通文本默认放行。"""
        assert SafetyScanService._local_rule_verdict("今天天气不错") == "pass"

    def test_high_risk_overrides_pass_marker(self):
        """安全优先：高危词命中不可被放行标记覆盖。"""
        assert (
            SafetyScanService._local_rule_verdict(f"爆炸物 {PASS_MARKER}") == "reject"
        )


# ---------------------------------------------------------------------------
# 举报上报占位
# ---------------------------------------------------------------------------
class TestReportToAuthority:
    """report_to_authority：无凭据时不报错并返回未上报语义。"""

    def test_placeholder_returns_not_reported(self):
        """占位实现恒返回 {reported: False, reason: credentials_not_configured}。"""
        result = report_to_authority(FakeSession(), "RP2026", "12391")
        assert result == {"reported": False, "reason": "credentials_not_configured"}


# ---------------------------------------------------------------------------
# 后台任务纯逻辑：长图渲染元数据
# ---------------------------------------------------------------------------
class TestImageMeta:
    """build_image_meta：协议 V1 字段与免责合规下限。"""

    def test_protocol_fields(self):
        """协议字段完整：V1 / 12pt / scale=2 / 13 区块 / 二维码占位含 uid。"""
        from app.jobs.scheduler import build_image_meta

        meta = build_image_meta("RPT-abc")
        assert meta["protocol_version"] == "V1"
        assert meta["font_size_pt"] == 12
        assert meta["scale"] == 2
        assert meta["sections_count"] == 13
        assert meta["qr_placeholder"] == "https://jiaban.example/r/RPT-abc"

    def test_disclaimer_compliance(self):
        """免责合规：ratio≥0.15 且 count≥2。"""
        from app.jobs.scheduler import build_image_meta

        meta = build_image_meta("RPT-x")
        assert meta["disclaimer_ratio"] >= 0.15
        assert meta["disclaimer_count"] >= 2


# ---------------------------------------------------------------------------
# 后台任务：report_render 幂等渲染
# ---------------------------------------------------------------------------
class TestReportRenderJob:
    """_run_report_render：渲染留痕 + 重复执行幂等跳过。"""

    def test_render_once_then_skip(self, monkeypatch):
        """首次渲染写 image_meta/image_rendered_at 并留痕；二次执行跳过。"""
        import app.jobs.scheduler as sched

        report = SimpleNamespace(
            report_uid="RPT-1",
            report_type="assessment",
            image_meta=None,
            image_rendered_at=None,
        )
        fake = FakeJobSession(reports=[report])
        monkeypatch.setattr(sched, "get_session_factory", lambda: lambda: fake)

        sched._run_report_render()
        assert report.image_meta is not None
        assert report.image_rendered_at is not None
        assert len(fake.job_logs) == 1
        log = fake.job_logs[0]
        assert log.job_name == "report_render"
        assert log.idempotency_key == "RPT-1"
        assert log.status == "ok"
        assert log.affected_rows == 1

        # 二次执行：同报告已有 ok 留痕 → 幂等跳过（渲染时间不变、不新增记录）
        first_rendered_at = report.image_rendered_at
        sched._run_report_render()
        assert report.image_rendered_at == first_rendered_at
        assert len(fake.job_logs) == 1


# ---------------------------------------------------------------------------
# 后台任务：orphan_sweep 同小时幂等
# ---------------------------------------------------------------------------
class TestOrphanSweepJob:
    """_run_orphan_sweep：streaming 超时置 orphaned + 同小时幂等跳过。"""

    def test_orphaned_then_hourly_idempotent(self, monkeypatch):
        """首轮置 orphaned 并留痕；同小时重跑直接跳过（状态不被二次处理）。"""
        import app.jobs.scheduler as sched

        # fake 不过滤 created_at：两个 streaming 会话均进入处置集
        stale = SimpleNamespace(status="streaming", created_at=None)
        other = SimpleNamespace(status="streaming", created_at=None)
        fake = FakeJobSession(qa_sessions=[stale, other])
        monkeypatch.setattr(sched, "get_session_factory", lambda: lambda: fake)

        sched._run_orphan_sweep()
        assert stale.status == "orphaned"
        assert other.status == "orphaned"
        assert len(fake.job_logs) == 1
        log = fake.job_logs[0]
        assert log.job_name == "orphan_sweep"
        assert log.status == "ok"
        assert log.affected_rows == 2

        # 同小时重跑：存在本小时记录 → 幂等跳过
        stale.status = "streaming"
        sched._run_orphan_sweep()
        assert stale.status == "streaming"  # 未被二次处置
        assert len(fake.job_logs) == 1


# ---------------------------------------------------------------------------
# 历史详情"内容已更新"标注（查询时推导）
# ---------------------------------------------------------------------------
class TestContentUpdatedFlag:
    """_has_updated_content：B/C 级已完成追溯命中 kb_refs 判定。"""

    def _db(self, rows):
        """构造仅支持 ContentTraceTask 查询的假会话。

        Args:
            rows: 查询应返回的行。

        Returns:
            SimpleNamespace 形式的假 db。
        """
        return SimpleNamespace(query=lambda model: FakeQuery(rows))

    def test_hit_done_bc_task(self):
        """存在已完成 B/C 级任务且 kb_refs 命中 → True。"""
        from app.api.v1.history_api import _has_updated_content

        assert _has_updated_content(self._db([1]), ["KB001"]) is True

    def test_miss_when_no_task(self):
        """无命中任务 → False。"""
        from app.api.v1.history_api import _has_updated_content

        assert _has_updated_content(self._db([]), ["KB001"]) is False

    def test_no_refs_skips_query(self):
        """kb_refs 为空/None → 直接 False（不触发查询）。"""
        from app.api.v1.history_api import _has_updated_content

        assert _has_updated_content(self._db([1]), None) is False
        assert _has_updated_content(self._db([1]), []) is False
# -*- coding: utf-8 -*-
"""RAG 检索层测试（spec rag-llamaindex-migration）。

覆盖：embed_client 确定性/维度/归一化/降级告警、rag_index 纯函数
（filters 哨兵语义、sync_entry 状态分派、降级矩阵）；gated 集成用例
（真 pgvector 扩展下 upsert→query→delete 往返）在 fixture 探测通过时执行。
"""
import math
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.llm.embed_client import EmbeddingError, embed_texts, mock_embed_2048

# ---------------------------------------------------------------------------
# embed_client：mock 确定性 / 维度 / 归一化 / 降级
# ---------------------------------------------------------------------------
T1 = "1岁宝宝夜里总醒怎么办，需要安抚还是就医？"
T2 = "幼儿辅食添加顺序与过敏观察要点"


class TestMockEmbed:
    """mock_embed_2048 确定性与数值性质。"""

    def test_dim_and_normalized(self):
        """维度 = settings.embedding_dimensions 且 L2 归一化。"""
        v = mock_embed_2048(T1)
        dim = get_settings().embedding_dimensions
        assert len(v) == dim
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    def test_deterministic_same_process(self):
        """同进程同文本两次调用结果一致；不同文本不同。"""
        assert mock_embed_2048(T1) == mock_embed_2048(T1)
        assert mock_embed_2048(T1) != mock_embed_2048(T2)

    def test_deterministic_cross_process(self):
        """跨进程复算一致（MD5 hashing 纯函数，无进程内状态）。"""
        code = (
            "import sys; sys.path.insert(0, r'd:\\HomeBud\\backend');"
            "from app.llm.embed_client import mock_embed_2048;"
            f"print(sum(mock_embed_2048({T1!r})))"
        )
        r1 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        r2 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        assert r1.returncode == 0 and r2.returncode == 0
        assert r1.stdout.strip() == r2.stdout.strip()
        # 与本进程结果一致
        assert abs(float(r1.stdout.strip()) - sum(mock_embed_2048(T1))) < 1e-9

    def test_empty_text_no_crash(self):
        """空文本不崩溃且仍归一化。"""
        v = mock_embed_2048("")
        assert len(v) == get_settings().embedding_dimensions
        assert abs(sum(x * x for x in v) - 1.0) < 1e-6


class TestEmbedTextsDispatch:
    """embed_texts provider 分派与降级。"""

    def test_mock_provider_batch(self, monkeypatch):
        """provider=mock 时走确定性 mock（与单文本一致）。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
        get_settings.cache_clear()
        try:
            out = embed_texts([T1, T2])
            assert len(out) == 2
            assert out[0] == mock_embed_2048(T1)
            assert out[1] == mock_embed_2048(T2)
        finally:
            get_settings.cache_clear()

    def test_empty_input(self, monkeypatch):
        """空输入返回空列表（不发起任何调用）。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
        get_settings.cache_clear()
        try:
            assert embed_texts([]) == []
        finally:
            get_settings.cache_clear()

    def test_zhipu_empty_key_falls_back_to_mock(self, monkeypatch, caplog):
        """provider=zhipu 但 key 为空：告警 + 降级 mock（不抛错）。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "zhipu")
        monkeypatch.setenv("ZHIPU_API_KEY", "")
        get_settings.cache_clear()
        try:
            with caplog.at_level("WARNING", logger="jiaban.embed"):
                out = embed_texts([T1])
            assert out[0] == mock_embed_2048(T1)
            assert any("ZHIPU_API_KEY" in r.message for r in caplog.records)
        finally:
            get_settings.cache_clear()

    def test_zhipu_http_error_raises(self, monkeypatch):
        """provider=zhipu 且 key 非空、接口不可达：抛 EmbeddingError。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "zhipu")
        monkeypatch.setenv("ZHIPU_API_KEY", "dummy-key-for-error-path")
        monkeypatch.setenv("ZHIPU_BASE_URL", "http://127.0.0.1:1/api/paas/v4")
        get_settings.cache_clear()
        try:
            with pytest.raises(EmbeddingError):
                embed_texts([T1], timeout=1.0)
        finally:
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# rag_index 纯函数：filters 哨兵语义 / sync_entry 状态分派 / 降级矩阵
# ---------------------------------------------------------------------------
from app.services import rag_index  # noqa: E402


class TestBuildFilterExpr:
    """Milvus 过滤表达式：哨兵/别名同构 + 注入防护。"""

    def test_base_conditions_always_present(self):
        """status/kb_kind 固定 + domain 别名集 IN。"""
        expr = rag_index.build_filter_expr(("child", "育儿"), None, None)
        assert 'status == "published"' in expr
        assert 'kb_kind in ["child", "pet"]' in expr
        assert 'domain in ["child", "育儿"]' in expr
        assert "age_band" not in expr and "species" not in expr

    def test_age_band_sentinel_in(self):
        """age_band 非空 → IN [value, 'any']（哨兵 OR 语义）。"""
        expr = rag_index.build_filter_expr(("child", "育儿"), "1-3y", None)
        assert 'age_band in ["1-3y", "any"]' in expr
        assert "species" not in expr

    def test_species_only_for_pet_domain(self):
        """species 仅 pet 域参与过滤；child 域传 species 也不生效。"""
        expr_pet = rag_index.build_filter_expr(("pet", "宠物"), None, "cat")
        assert 'species in ["cat", "any"]' in expr_pet
        expr_child = rag_index.build_filter_expr(("child", "育儿"), None, "cat")
        assert "species" not in expr_child

    def test_injection_values_rejected(self):
        """含引号/运算符的非法值：非法项剔除、合法项保留（绝不原样拼接）。"""
        expr = rag_index.build_filter_expr(('child" or status != "x', "育儿"), '1-3y" or "a" == "a', None)
        # 非法 domain 项被剔除（无注入痕迹）、合法中文别名保留
        assert "child" not in expr or 'child" ' not in expr
        assert "or status" not in expr
        assert 'domain in ["育儿"]' in expr
        # 非法 age_band → 该条件整体丢弃
        assert "age_band" not in expr
        # 固定条件保留（published/kb_kind 兜底仍在）
        assert 'status == "published"' in expr

    def test_all_domains_illegal_keeps_base_conditions(self):
        """domain 全非法：仅丢弃 domain 条件，固定条件保留（published 兜底）。"""
        expr = rag_index.build_filter_expr(('a" x', 'b" y'), None, None)
        assert "domain in" not in expr
        assert 'status == "published"' in expr
        assert 'kb_kind in ["child", "pet"]' in expr

    def test_mixed_legal_and_illegal_domains(self):
        """domain 列表部分非法：合法项保留、非法项剔除。"""
        expr = rag_index.build_filter_expr(("child", '育儿" inject'), None, None)
        assert 'domain in ["child"]' in expr
        assert "inject" not in expr


class TestSyncEntryDispatch:
    """sync_entry 状态分派（mock 层面，不依赖真库）。"""

    def _make_sync(self, monkeypatch, entry):
        """构造 sync_entry 可调环境：available=True + upsert/delete 打桩。

        Args:
            monkeypatch: pytest monkeypatch。
            entry: KbEntry 替身对象（或 None 表示条目不存在）。

        Returns:
            (calls, db)——calls 为打桩调用记录，db 为已配置的会话替身
            （须原样传入 sync_entry）。
        """
        calls = {"upsert": [], "delete": []}
        monkeypatch.setattr(rag_index, "available", lambda: True)
        monkeypatch.setattr(
            rag_index, "upsert_entry", lambda db, kb_id: calls["upsert"].append(kb_id)
        )
        monkeypatch.setattr(rag_index, "delete_entry", lambda kb_id: calls["delete"].append(kb_id))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry
        return calls, db

    def test_published_child_pet_upserts(self, monkeypatch):
        """published + child/pet → upsert。"""
        entry = SimpleNamespace(status="published", kb_kind="child", kb_id="KB1")
        calls, db = self._make_sync(monkeypatch, entry)
        rag_index.sync_entry(db, "KB1")
        assert calls["upsert"] == ["KB1"] and calls["delete"] == []

    def test_unpublished_deletes(self, monkeypatch):
        """非 published（unpublished/rejected/draft 等）→ delete。"""
        for status in ("unpublished", "rejected", "draft", "pending_review", "merged"):
            entry = SimpleNamespace(status=status, kb_kind="child", kb_id="KB1")
            calls, db = self._make_sync(monkeypatch, entry)
            rag_index.sync_entry(db, "KB1")
            assert calls["delete"] == ["KB1"], f"status={status}"

    def test_wrong_kb_kind_deletes(self, monkeypatch):
        """published 但 kb_kind 不属于 child/pet（如题库）→ delete。"""
        entry = SimpleNamespace(status="published", kb_kind="assessment_pool", kb_id="KB2")
        calls, db = self._make_sync(monkeypatch, entry)
        rag_index.sync_entry(db, "KB2")
        assert calls["delete"] == ["KB2"]

    def test_missing_entry_deletes(self, monkeypatch):
        """条目已不存在 → delete（清理残留向量）。"""
        calls, db = self._make_sync(monkeypatch, None)
        rag_index.sync_entry(db, "KB3")
        assert calls["delete"] == ["KB3"]

    def test_swallow_exception(self, monkeypatch):
        """available 抛异常：吞掉不外抛（best-effort 承诺）。"""
        monkeypatch.setattr(rag_index, "available", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        rag_index.sync_entry(MagicMock(), "KB4")  # 不应抛出

    def test_unavailable_noop(self, monkeypatch):
        """主通道不可用（available=False）时直接返回（走降级链）。"""
        calls, db = self._make_sync(monkeypatch, SimpleNamespace(status="published", kb_kind="child", kb_id="KB5"))
        monkeypatch.setattr(rag_index, "available", lambda: False)
        rag_index.sync_entry(db, "KB5")
        assert calls["upsert"] == [] and calls["delete"] == []


class TestDegradationMatrix:
    """降级矩阵：pymilvus 缺失 / URI 未配置。"""

    def test_available_false_when_pymilvus_missing(self, monkeypatch):
        """_PYMILVUS_OK=False（import 失败）→ available()=False。"""
        monkeypatch.setattr(rag_index, "_PYMILVUS_OK", False)
        assert rag_index.available() is False

    def test_available_false_when_uri_empty(self, monkeypatch):
        """MILVUS_URI 空（快路径，不发起连接）→ available()=False。"""
        from app.core.config import get_settings

        monkeypatch.setattr(rag_index, "_PYMILVUS_OK", True)
        s = get_settings()
        monkeypatch.setattr(s, "milvus_uri", "")
        monkeypatch.setattr(rag_index, "_probe_cache", None)
        assert rag_index.available() is False

    def test_available_true_cached(self, monkeypatch):
        """探测成功缓存 True（二次调用不重查 has_collection）。"""
        monkeypatch.setattr(rag_index, "_configured", lambda: True)
        monkeypatch.setattr(rag_index, "_probe_cache", True)
        assert rag_index.available() is True

    def test_failure_not_cached(self, monkeypatch):
        """探测失败不缓存（Milvus 后启自动恢复，无需重启后端）。"""
        monkeypatch.setattr(rag_index, "_configured", lambda: True)
        calls = {"n": 0}

        def fake_get_client():
            calls["n"] += 1
            raise RuntimeError("conn refused")

        monkeypatch.setattr(rag_index, "get_client", fake_get_client)
        monkeypatch.setattr(rag_index, "_probe_cache", None)
        assert rag_index.available() is False
        assert rag_index.available() is False
        assert calls["n"] == 2  # 每次都重试（失败不缓存）


# ---------------------------------------------------------------------------
# gated 集成（宿主 Milvus 可达时执行；否则整组 skip——
# 真实往返同时在端到端验证实测：compose 三件套 init→seed→reindex→语义命中）
# ---------------------------------------------------------------------------
class TestGatedIntegration:
    """真 Milvus 下的 upsert→search→delete 往返、过滤语义与写后立读。"""

    def test_upsert_query_delete_roundtrip(self, milvus_gated, monkeypatch):
        """写入→语义查询命中→删除后不可见（原生 upsert 幂等）。"""
        import uuid

        from app.db import get_session_factory
        from app.models import KbEntry

        monkeypatch.setattr(rag_index, "_client", None)
        monkeypatch.setattr(rag_index, "_probe_cache", None)
        assert rag_index.available() is True
        kb_id = f"KB_GATED_{uuid.uuid4().hex[:8]}"
        db = get_session_factory()()
        try:
            db.add(KbEntry(
                kb_id=kb_id, kb_kind="child", domain="child",
                topic_key="t_gated", topic_category="gated",
                title="婴儿夜醒安抚方法", content="宝宝夜里频繁醒来时，先排查环境与饥饿，再逐步安抚。",
                preconditions="演示", stance="support", source_type="manual",
                source_ref="gated", status="published", is_high_risk=False,
            ))
            db.commit()
            # 原生 upsert 两次（幂等，无重复——主键即 kb_id）
            rag_index.upsert_entry(db, kb_id)
            rag_index.upsert_entry(db, kb_id)
            # 写后立读（Strong 一致性）
            hits = rag_index.query("宝宝夜里醒来哭闹怎么安抚", ("child", "育儿"), top_k=5)
            assert any(k == kb_id for k, _ in hits)
            # 删除后立查不可见
            rag_index.delete_entry(kb_id)
            hits2 = rag_index.query("宝宝夜里醒来哭闹怎么安抚", ("child", "育儿"), top_k=5)
            assert not any(k == kb_id for k, _ in hits2)
        finally:
            db.rollback()
            try:
                from sqlalchemy import text as _t

                db.execute(_t("DELETE FROM kb_entry WHERE kb_id = :k"), {"k": kb_id})
                db.commit()
            except Exception:  # noqa: BLE001 — 清理失败不影响断言
                db.rollback()
            db.close()

    def test_published_filter_excludes_draft(self, milvus_gated, monkeypatch):
        """status 过滤兜底：draft 状态条目（同文本）不出现在检索结果。"""
        import uuid

        from app.db import get_session_factory
        from app.models import KbEntry

        monkeypatch.setattr(rag_index, "_client", None)
        monkeypatch.setattr(rag_index, "_probe_cache", None)
        kb_id = f"KB_DRAFT_{uuid.uuid4().hex[:8]}"
        db = get_session_factory()()
        try:
            db.add(KbEntry(
                kb_id=kb_id, kb_kind="child", domain="child",
                topic_key="t_draft", topic_category="draft",
                title="草稿态夜醒条目", content="宝宝夜里频繁醒来的草稿内容。",
                preconditions="演示", stance="support", source_type="manual",
                source_ref="gated", status="draft", is_high_risk=False,
            ))
            db.commit()
            # 直接 upsert（绕过 sync_entry 分派）——查询侧 status 过滤兜底
            rag_index.upsert_entry(db, kb_id)
            hits = rag_index.query("宝宝夜里频繁醒来的草稿内容", ("child", "育儿"), top_k=8)
            assert not any(k == kb_id for k, _ in hits)
        finally:
            db.rollback()
            try:
                rag_index.delete_entry(kb_id)
            except Exception:  # noqa: BLE001 — 清理失败不影响断言
                pass
            try:
                from sqlalchemy import text as _t

                db.execute(_t("DELETE FROM kb_entry WHERE kb_id = :k"), {"k": kb_id})
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
            db.close()

    def test_age_band_filter_semantics(self, milvus_gated, monkeypatch):
        """age_band 哨兵过滤：标注不匹配的条目不命中（同构语义实测）。"""
        import uuid

        from app.db import get_session_factory
        from app.models import KbEntry

        monkeypatch.setattr(rag_index, "_client", None)
        monkeypatch.setattr(rag_index, "_probe_cache", None)
        kb_id = f"KB_BAND_{uuid.uuid4().hex[:8]}"
        db = get_session_factory()()
        try:
            db.add(KbEntry(
                kb_id=kb_id, kb_kind="child", domain="child",
                topic_key="t_band", topic_category="gated",
                title="6 岁学龄儿童专注力训练", content="学龄期儿童专注力家庭训练方法演示。",
                preconditions="演示", stance="support", source_type="manual",
                source_ref="gated", status="published", is_high_risk=False,
                age_band="6y+",
            ))
            db.commit()
            rag_index.upsert_entry(db, kb_id)
            # 1-3y 查询：条目标注 6y+（非通用）→ 须相等才命中 → 不命中
            hits = rag_index.query(
                "学龄儿童专注力训练方法", ("child", "育儿"), age_band="1-3y", top_k=8,
            )
            assert not any(k == kb_id for k, _ in hits)
            # 6y+ 查询：相等 → 命中
            hits2 = rag_index.query(
                "学龄儿童专注力训练方法", ("child", "育儿"), age_band="6y+", top_k=8,
            )
            assert any(k == kb_id for k, _ in hits2)
        finally:
            db.rollback()
            try:
                rag_index.delete_entry(kb_id)
            except Exception:  # noqa: BLE001
                pass
            try:
                from sqlalchemy import text as _t

                db.execute(_t("DELETE FROM kb_entry WHERE kb_id = :k"), {"k": kb_id})
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
            db.close()

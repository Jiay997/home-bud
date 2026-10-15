# -*- coding: utf-8 -*-
"""检索层三分支降级链测试（spec rag-llamaindex-migration）。

覆盖：
- 主通道不可用（默认测试库无 data_kb_dense/vector 扩展）时 retrieve 走
  降级路径，输出契约字段齐全（fallback 契约，原用例保留）；
- 主通道就绪时 _retrieve_by_index 混合重排：monkeypatch rag_index.query
  返回 (kb_id, cos) 候选，验证 0.6×cos+0.4×关键词重排、token 零分过滤、
  top5 截断与异常回退。

原 densify/vector_literal/PgVectorStore SQL 组装用例随旧路径删除
（spec REMOVED：自研 pgvector 直连检索路径），由 test_rag_index.py 的
纯函数与 gated 集成用例承接。
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import rag_index  # noqa: E402
from app.services.retriever import CANDIDATE_SIZE, Retriever  # noqa: E402

# 检索输出契约字段（与 _entry_doc 一致）
DOC_FIELDS = {"kb_id", "kb_version", "title", "content", "preconditions", "stance", "topic_key", "domain"}


# ---------------------------------------------------------------------------
# 降级路径契约（主通道不可用，默认测试库）
# ---------------------------------------------------------------------------
class TestFallbackContract:
    """主通道不可用时的回退契约（默认测试库无扩展，自然降级）。"""

    def test_available_false_on_test_db(self):
        """默认测试库（无 vector 扩展/data_kb_dense）rag_index 探测为 False。

        Returns:
            None。
        """
        from app.db import get_session_factory

        session = get_session_factory()()
        try:
            assert rag_index.available() is False
        finally:
            session.close()

    def test_retrieve_fallback_contract(self):
        """available()=False 时 retrieve 走降级路径，输出契约字段齐全。

        Returns:
            None。
        """
        from app.db import get_session_factory

        session = get_session_factory()()
        try:
            result = Retriever().retrieve(session, "宝宝发烧了怎么办", "child")
        finally:
            session.close()
        # 顶层契约：hit + docs
        assert set(result.keys()) == {"hit", "docs"}
        assert isinstance(result["docs"], list)
        assert isinstance(result["hit"], bool)
        assert result["hit"] == bool(result["docs"])
        # 文档契约字段齐全（conftest 已种子 published 条目，应能命中）
        for doc in result["docs"]:
            assert set(doc.keys()) == DOC_FIELDS


# ---------------------------------------------------------------------------
# 主通道混合重排（monkeypatch rag_index.query，不依赖真向量库）
# ---------------------------------------------------------------------------
def _entry(row_id: int, title: str, content: str, kb_id: str = "", **kw):
    """构造检索打分用条目替身（属性面与 KbEntry 检索所需字段一致）。

    Args:
        row_id: 自增主键（同分稳定排序用）。
        title: 标题（关键词通道权重 2）。
        content: 正文（关键词通道权重 1）。
        kb_id: 业务编号（默认按 row_id 生成）。
        **kw: 可选覆盖（embedding 等）。

    Returns:
        SimpleNamespace 条目替身。
    """
    return SimpleNamespace(
        id=row_id,
        kb_id=kb_id or f"KB{row_id:012d}",
        title=title,
        content=content,
        preconditions="演示前提",
        stance="support",
        topic_key="t",
        domain="child",
        embedding=kw.get("embedding"),
    )


class TestRetrieveByIndex:
    """主通道混合重排（mock rag_index.query，不触真向量库）。"""

    def _patch_available(self, monkeypatch):
        """打桩 rag_index.available()=True。

        Args:
            monkeypatch: pytest monkeypatch。

        Returns:
            None。
        """
        monkeypatch.setattr(rag_index, "available", lambda: True)

    def test_hybrid_rerank_top5(self, monkeypatch):
        """0.6×cos + 0.4×关键词重排：高分在前，截断 top5。

        Args:
            monkeypatch: pytest monkeypatch。

        Returns:
            None。
        """
        self._patch_available(monkeypatch)
        # 候选 6 条（top8 粗筛内），关键词/余弦分布使排序可断言
        entries = [
            _entry(1, "宝宝发烧护理", "发烧物理降温与就医指引", kb_id="KB_A"),
            _entry(2, "幼儿咳嗽", "咳嗽护理要点", kb_id="KB_B"),
            _entry(3, "发烧惊厥处理", "高热惊厥紧急处理", kb_id="KB_C"),
            _entry(4, "辅食添加", "辅食顺序", kb_id="KB_D"),
            _entry(5, "疫苗时间表", "疫苗接种", kb_id="KB_E"),
            _entry(6, "夜醒安抚", "夜醒原因", kb_id="KB_F"),
        ]
        by_kb = {e.kb_id: e for e in entries}
        monkeypatch.setattr(
            rag_index, "query",
            lambda q, domains, age_band=None, species=None, top_k=8: [
                ("KB_A", 0.90), ("KB_C", 0.80), ("KB_B", 0.60),
                ("KB_D", 0.50), ("KB_E", 0.40), ("KB_F", 0.30),
            ],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = entries
        result = Retriever()._retrieve_by_index(
            db, set("宝宝发烧".split()) | {"宝宝", "发烧"},
            "宝宝发烧怎么办", ("child", "育儿"), None, None,
        )
        assert len(result) <= 5
        for doc in result:
            assert set(doc.keys()) == DOC_FIELDS
        # 混合分：KB_A cos 最高且含关键词 → 应排第一
        assert result[0]["kb_id"] == "KB_A"

    def test_zero_score_filtered_with_tokens(self, monkeypatch):
        """有 token 时零分条目（无余弦且无关键词命中）被过滤。

        Args:
            monkeypatch: pytest monkeypatch。

        Returns:
            None。
        """
        self._patch_available(monkeypatch)
        entries = [
            _entry(1, "宝宝发烧护理", "物理降温", kb_id="KB_A"),
            _entry(2, "完全不相关条目", "xyz", kb_id="KB_B"),
        ]
        monkeypatch.setattr(
            rag_index, "query",
            lambda q, domains, age_band=None, species=None, top_k=8: [("KB_A", 0.8)],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = entries
        result = Retriever()._retrieve_by_index(
            db, {"宝宝", "发烧"}, "宝宝发烧", ("child", "育儿"), None, None,
        )
        assert [d["kb_id"] for d in result] == ["KB_A"]

    def test_main_channel_exception_falls_back(self, monkeypatch):
        """主通道检索抛错：retrieve 捕获并回退降级路径（warning 留痕）。

        Args:
            monkeypatch: pytest monkeypatch。

        Returns:
            None。
        """

        def _boom(*a, **kw):
            raise RuntimeError("vector store down")

        monkeypatch.setattr(rag_index, "available", lambda: True)
        monkeypatch.setattr(rag_index, "query", _boom)
        from app.db import get_session_factory

        session = get_session_factory()()
        try:
            result = Retriever().retrieve(session, "宝宝发烧了怎么办", "child")
        finally:
            session.close()
        # 回退降级路径：契约不变且能命中种子条目
        assert set(result.keys()) == {"hit", "docs"}
        for doc in result["docs"]:
            assert set(doc.keys()) == DOC_FIELDS

    def test_empty_hits_returns_empty(self, monkeypatch):
        """候选 0 命中：返回空 docs（hit=False）。"""
        self._patch_available(monkeypatch)
        monkeypatch.setattr(
            rag_index, "query",
            lambda q, domains, age_band=None, species=None, top_k=8: [],
        )
        db = MagicMock()
        result = Retriever()._retrieve_by_index(
            db, {"发烧"}, "不相关查询", ("child", "育儿"), None, None,
        )
        assert result == []

    def test_candidate_size_top8(self, monkeypatch):
        """query 以 top_k=CANDIDATE_SIZE(8) 粗筛。"""
        self._patch_available(monkeypatch)
        captured = {}

        def fake_query(q, domains, age_band=None, species=None, top_k=8):
            captured["top_k"] = top_k
            return []

        monkeypatch.setattr(rag_index, "query", fake_query)
        Retriever()._retrieve_by_index(
            MagicMock(), {"x"}, "q", ("child",), None, None,
        )
        assert captured["top_k"] == CANDIDATE_SIZE

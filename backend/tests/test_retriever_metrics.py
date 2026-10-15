# -*- coding: utf-8 -*-
"""检索混合化与可观测模块单测（Task 4：M 模块增强）。

覆盖：
- hashing_embed：同文本同向量、异文本异向量、维度 ≤512、权重 >0；
- cosine_sparse：相同文本 ≈1、无关文本低、空向量 =0；
- 混合打分 _score_entry：余弦通道影响排序（字面重合高 vs 3-gram 重叠高）；
- MetricsRegistry：observe_* 计数快照、P50/P95 分位、告警规则触发
  （含环境变量阈值覆盖）。

纯函数级测试：不依赖数据库、Redis 与网络；兼容任意工作目录的
pytest 调用方式（显式将 backend 目录加入 sys.path）。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

# 保证从 backend 根目录导入 app 包（无论从哪个目录启动 pytest）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.core.observe import MetricsRegistry  # noqa: E402
from app.services.retriever import (  # noqa: E402
    EMBED_DIM,
    _score_entry,
    cosine_sparse,
    hashing_embed,
)


# ---------------------------------------------------------------------------
# hashing_embed
# ---------------------------------------------------------------------------
class TestHashingEmbed:
    """字符 3-gram hashing 稀疏向量的基本性质。"""

    def test_same_text_same_vector(self):
        """同文本重复调用结果完全一致（MD5 哈希跨进程稳定）。"""
        v1 = hashing_embed("宝宝发烧了怎么办")
        v2 = hashing_embed("宝宝发烧了怎么办")
        assert v1 == v2
        assert len(v1) > 0

    def test_different_text_different_vector(self):
        """不同文本向量不同（区分性）。"""
        v1 = hashing_embed("宝宝发烧了怎么办")
        v2 = hashing_embed("小狗呕吐拉稀禁食")
        assert v1 != v2

    def test_dim_bound_and_weights_positive(self):
        """桶位落在 [0, EMBED_DIM) 且权重严格为正。"""
        vec = hashing_embed("宝宝辅食添加时间表与过敏注意事项")
        assert 0 < len(vec) <= EMBED_DIM
        for idx, weight in vec.items():
            assert 0 <= idx < EMBED_DIM
            assert weight > 0

    def test_empty_text_returns_empty(self):
        """空文本返回空稀疏向量（余弦通道安全回退）。"""
        assert hashing_embed("") == {}

    def test_short_text_single_gram_weight_is_one(self):
        """恰 3 字符仅 1 个 gram：权重 = 1 + log(1) = 1.0。"""
        vec = hashing_embed("发高烧")
        assert len(vec) == 1
        assert all(w == 1.0 for w in vec.values())

    def test_repeated_gram_weight_sublinear(self):
        """重复 3-gram 的 sublinear tf 权重（1+log(tf)）大于单次出现。"""
        single = max(hashing_embed("发高烧").values())
        repeated = max(hashing_embed("发高烧发高烧").values())
        # 「发高烧发高烧」任一桶 tf>=2 → 权重 > 1（碰撞只会让 tf 更大）
        assert repeated > single


# ---------------------------------------------------------------------------
# cosine_sparse
# ---------------------------------------------------------------------------
class TestCosineSparse:
    """稀疏向量余弦相似度。"""

    def test_identical_text_similarity_one(self):
        """相同文本余弦 ≈ 1（浮点误差范围内）。"""
        v = hashing_embed("宝宝辅食添加时间")
        assert cosine_sparse(v, v) == pytest.approx(1.0, abs=1e-9)

    def test_unrelated_text_low_similarity(self):
        """语义无关文本相似度接近 0（容许偶发桶位哈希碰撞的小值）。"""
        v1 = hashing_embed("宝宝辅食添加时间")
        v2 = hashing_embed("犬猫疫苗注射周期")
        # 512 维折叠下个别 3-gram 可能碰撞：共同桶 <=1 时相似度 <= 1/6
        assert cosine_sparse(v1, v2) < 0.35

    def test_empty_vector_returns_zero(self):
        """任一向量为空时相似度为 0（不抛异常）。"""
        v = hashing_embed("宝宝发烧怎么办")
        assert cosine_sparse({}, v) == 0.0
        assert cosine_sparse(v, {}) == 0.0
        assert cosine_sparse({}, {}) == 0.0


# ---------------------------------------------------------------------------
# 混合打分 _score_entry
# ---------------------------------------------------------------------------
class TestHybridScore:
    """混合打分：余弦通道影响排序。"""

    # 问题原文：8 个 2-gram token（宝宝/宝反/反复/复低/低烧/烧怎/么护/护理）
    QUESTION = "宝宝反复低烧怎么护理"

    def _entry(self, title, content, embedding):
        """构造打分函数可用的条目替身（绕开数据库依赖）。

        Args:
            title: 标题。
            content: 正文。
            embedding: 稀疏向量（None 表示缺失）。

        Returns:
            具备 title/content/embedding 属性的 SimpleNamespace。
        """
        return SimpleNamespace(title=title, content=content, embedding=embedding)

    def test_keyword_only_score(self):
        """无 embedding 条目：全 token 命中标题 → 关键词归一化分 = 0.4。"""
        entry = self._entry(
            title="宝宝反复低烧怎么护理",
            content="宝宝反复低烧护理要点",
            embedding=None,
        )
        score = _score_entry(entry, {"宝宝", "宝反", "反复", "复低", "低烧", "烧怎", "么护", "护理"}, hashing_embed(self.QUESTION))
        # 余弦项 0，关键词项 1.0 → 0.4 × 1.0
        assert score == pytest.approx(0.4, abs=1e-9)

    def test_cosine_channel_affects_ranking(self):
        """字面重合低的条目因 3-gram 余弦高而反超字面重合高的条目。

        A：无 embedding，token 全命中标题（关键词通道满分 0.4）；
        B：embedding 与问题向量同源（余弦 ≈1），字面命中仅 3 token
        （关键词通道 6/16≈0.375）。
        关掉余弦通道时 B(0.15) < A(0.4)；开启后 B(0.75) > A(0.4)。
        """
        tokens = {"宝宝", "宝反", "反复", "复低", "低烧", "烧怎", "么护", "护理"}
        question_vec = hashing_embed(self.QUESTION)
        entry_a = self._entry(
            title="宝宝反复低烧怎么护理",
            content="宝宝反复低烧护理要点",
            embedding=None,
        )
        entry_b = self._entry(
            title="婴幼儿反复低烧的家庭护理",
            content="婴幼儿出现反复低烧时的家庭护理办法",
            embedding=question_vec,
        )
        score_a = _score_entry(entry_a, tokens, question_vec)
        score_b = _score_entry(entry_b, tokens, question_vec)
        # 余弦通道开启：B 反超 A（0.6×cos + 0.4×0.375 ≈ 0.75 > 0.4）
        assert score_b > score_a
        # 反证：若 B 缺 embedding（余弦按 0），则 B < A
        entry_b_no_vec = self._entry(
            title="婴幼儿反复低烧的家庭护理",
            content="婴幼儿出现反复低烧时的家庭护理办法",
            embedding=None,
        )
        assert _score_entry(entry_b_no_vec, tokens, question_vec) < score_a

    def test_score_range(self):
        """混合得分始终落在 0-1 区间。"""
        tokens = {"宝宝", "发烧"}
        question_vec = hashing_embed("宝宝发烧")
        entry = self._entry(
            title="宝宝发烧", content="宝宝发烧宝宝发烧", embedding=question_vec
        )
        score = _score_entry(entry, tokens, question_vec)
        assert 0.0 <= score <= 1.0

    def test_missing_embedding_treated_as_zero(self):
        """embedding 为非法格式（非 dict）时余弦项按 0 处理不抛异常。"""
        entry = self._entry(title="发烧", content="发烧", embedding="not-a-dict")
        score = _score_entry(entry, {"发烧"}, hashing_embed("发烧"))
        # 关键词满分 1.0、余弦 0 → 0.4
        assert score == pytest.approx(0.4, abs=1e-9)


# ---------------------------------------------------------------------------
# MetricsRegistry
# ---------------------------------------------------------------------------
class TestMetricsRegistry:
    """进程内指标聚合器。"""

    def test_request_counters_and_percentiles(self):
        """请求计数/错误计数与 P50/P95 分位计算正确。"""
        reg = MetricsRegistry()
        reg.observe_request(200, 100.0)
        reg.observe_request(200, 200.0)
        reg.observe_request(503, 300.0)
        snap = reg.snapshot()
        assert snap["counters"]["request_count"] == 3
        assert snap["counters"]["error_count"] == 1
        # 样本 [100,200,300]：P50=200；P95 线性插值 = 200×0.1 + 300×0.9 = 290
        assert snap["latency"]["p50"] == 200.0
        assert snap["latency"]["p95"] == pytest.approx(290.0, abs=1e-6)
        assert snap["latency"]["samples"] == 3

    def test_business_counters_and_rates(self):
        """Agent/降级/拦截/额度用尽计数与比率口径正确。"""
        reg = MetricsRegistry()
        for _ in range(3):
            reg.observe_agent(True)
        reg.observe_agent(False)
        reg.observe_degraded()
        reg.observe_blocked()
        reg.observe_quota_exhausted()
        reg.observe_request(200, 50.0)
        reg.observe_request(200, 50.0)
        snap = reg.snapshot()
        counters = snap["counters"]
        assert counters["agent_total_count"] == 4
        assert counters["agent_fail_count"] == 1
        assert counters["degraded_count"] == 1
        assert counters["blocked_count"] == 1
        assert counters["quota_exhausted_count"] == 1
        assert snap["rates"]["agent_fail_rate"] == pytest.approx(0.25)
        assert snap["rates"]["degraded_rate"] == pytest.approx(0.5)
        assert snap["rates"]["timeout_rate"] == 0.0

    def test_alert_triggered_on_agent_fail_rate(self):
        """Agent 失败率超过默认阈值 0.03 时触发告警。"""
        reg = MetricsRegistry()
        for i in range(100):
            # 10% 失败率：i<90 成功，i>=90 失败
            reg.observe_agent(i < 90)
        snap = reg.snapshot()
        alerts = [a for a in snap["alerts"] if a["metric"] == "agent_fail_rate"]
        assert len(alerts) == 1
        assert alerts[0]["value"] == pytest.approx(0.1)
        assert alerts[0]["threshold"] == 0.03

    def test_alert_threshold_env_override(self, monkeypatch):
        """环境变量提高阈值后同比例失败不再告警。"""
        monkeypatch.setenv("METRIC_ALERT_AGENT_FAIL_RATE", "0.5")
        reg = MetricsRegistry()
        for i in range(10):
            reg.observe_agent(i < 9)  # 10% 失败率
        snap = reg.snapshot()
        assert not any(a["metric"] == "agent_fail_rate" for a in snap["alerts"])

    def test_alert_degraded_rate(self):
        """降级率超过默认阈值 0.03 时触发告警。"""
        reg = MetricsRegistry()
        for _ in range(100):
            reg.observe_request(200, 50.0)
        for _ in range(5):
            reg.observe_degraded()
        snap = reg.snapshot()
        alerts = [a for a in snap["alerts"] if a["metric"] == "degraded_rate"]
        assert len(alerts) == 1
        assert alerts[0]["value"] == pytest.approx(0.05)

    def test_no_alert_on_zero_samples(self):
        """冷启动（无任何观测样本）时不误报告警。"""
        snap = MetricsRegistry().snapshot()
        assert snap["alerts"] == []
        assert all(v == 0.0 for v in snap["rates"].values())

    def test_latency_sample_window(self):
        """延迟样本环形截断：仅保留最近 1000 条。"""
        reg = MetricsRegistry()
        for ms in range(1005):
            reg.observe_request(200, float(ms))
        snap = reg.snapshot()
        assert snap["latency"]["samples"] == 1000
        # 最早的 5 条被挤出：保留窗口 [5,1004]，P50 = (504+505)/2 = 504.5
        assert snap["latency"]["p50"] == pytest.approx(504.5, abs=1e-6)

    def test_invalid_env_threshold_falls_back(self, monkeypatch):
        """非法阈值配置回退缺省值，告警链路不失效。"""
        monkeypatch.setenv("METRIC_ALERT_AGENT_FAIL_RATE", "not-a-number")
        reg = MetricsRegistry()
        for i in range(100):
            reg.observe_agent(i < 90)  # 10% 失败率 > 缺省 0.03
        snap = reg.snapshot()
        assert any(a["metric"] == "agent_fail_rate" for a in snap["alerts"])
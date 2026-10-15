# -*- coding: utf-8 -*-
"""风险引擎单元测试（纯函数级，不依赖数据库与网络）。

覆盖：
- 一级规则引擎：词库命中→阻断结果、正则命中、非法正则跳过；
- 分级边界：band_of_score 阈值（>0.8 / 0.5-0.8 / <0.5）；
- 硬类别判定：is_hard_category 与「硬类别低分强制拦截」；
- 二级语义：异常保守按命中、一级优先（命中不调语义模型）；
- 输出过滤：词库/正则命中置空、正常内容放行。

词库快照均为手工构造的 LexiconSnapshot，不触发 DB/LLM 调用；
兼容任意工作目录的 pytest 调用方式（显式将 backend 目录加入 sys.path）。
"""
import sys
from pathlib import Path

# 保证从 backend 根目录导入 app 包（无论从哪个目录启动 pytest）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk.engine import (  # noqa: E402
    DEFAULT_PATTERNS,
    HARD_CATEGORIES,
    SOFT_CATEGORIES,
    LexiconSnapshot,
    band_of_score,
    decide,
    filter_content,
    first_pass,
    is_hard_category,
    match_lexicon,
    match_regex_rules,
)

# 测试用词库快照工厂（词条 + 正则各一）
SNAPSHOT = LexiconSnapshot(
    terms=[
        {"term": "虐待", "category_code": "child_abuse", "strategy": "block"},
        {"term": "安眠药剂量", "category_code": "medicine_dosage", "strategy": "block"},
    ],
    patterns={
        "medicine_dosage_pattern": {
            "regex": r"(?i)\d+\s*(mg|毫克)",
            "category_code": "medicine_dosage",
        },
        "efficacy_pattern": {
            "regex": r"(包治|根治|药到病除)",
            "category_code": "efficacy",
        },
    },
    loaded_at=0.0,
)


def _semantic(score: float, category=None):
    """构造固定输出的语义分类假函数（测试注入用）。

    Args:
        score: 固定返回的风险分。
        category: 固定返回的类别代码。

    Returns:
        semantic_fn 函数。
    """

    def _fn(text: str) -> dict:
        """假语义分类实现。

        Args:
            text: 输入文本（忽略）。

        Returns:
            {"score": score, "category": category}。
        """
        return {"score": score, "category": category}

    return _fn


# ----------------------------------------------------------------------
# 一级规则引擎
# ----------------------------------------------------------------------
class TestFirstPass:
    """一级规则引擎：词库/正则命中 → 直接阻断。"""

    def test_match_lexicon_hit(self):
        """词库命中返回命中词与类别，level=L1。"""
        hit = match_lexicon("他威胁要虐待孩子", SNAPSHOT.terms)
        assert hit is not None
        assert hit["term"] == "虐待"
        assert hit["category_code"] == "child_abuse"
        assert hit["level"] == "L1"
        assert hit["source"] == "lexicon"

    def test_match_lexicon_miss(self):
        """未命中返回 None。"""
        assert match_lexicon("宝宝晚上睡觉不踏实怎么办", SNAPSHOT.terms) is None

    def test_first_pass_blocked_result(self):
        """一级命中 → 阻断结果：blocked=True / level=L1 / band=rule_hit。"""
        result = first_pass("如何给孩子喂安眠药剂量", SNAPSHOT)
        assert result is not None
        assert result["blocked"] is True
        assert result["level"] == "L1"
        assert result["score_band"] == "rule_hit"
        assert result["category_code"] == "medicine_dosage"
        # 硬类别联动：child_abuse 属硬类别
        assert result["hard"] == is_hard_category(result["category_code"])

    def test_regex_hit(self):
        """正则规则命中：剂量描述触发阻断。"""
        result = first_pass("孩子一次吃 5mg 阿司匹林可以吗", SNAPSHOT)
        assert result is not None
        assert result["blocked"] is True
        assert result["hit_source"] == "regex"
        assert result["hit_term"] == "medicine_dosage_pattern"

    def test_regex_invalid_pattern_skipped(self):
        """非法正则按未命中跳过，不抛异常。"""
        bad = LexiconSnapshot(
            terms=[],
            patterns={"bad_rule": {"regex": "([unclosed", "category_code": "x"}},
        )
        assert match_regex_rules("任意文本", bad.patterns) is None

    def test_first_pass_miss_returns_none(self):
        """一级未命中返回 None（进入二级）。"""
        assert first_pass("两岁宝宝不爱吃蔬菜怎么办", SNAPSHOT) is None


# ----------------------------------------------------------------------
# 分级与硬类别
# ----------------------------------------------------------------------
class TestGrading:
    """语义分分级与硬类别判定。"""

    def test_band_boundaries(self):
        """阈值边界：>0.8 → L1/high；=0.8 → L2/mid；=0.5 → L2/mid；<0.5 → low。"""
        assert band_of_score(0.81) == ("L1", "high")
        assert band_of_score(0.80) == ("L2", "mid")
        assert band_of_score(0.65) == ("L2", "mid")
        assert band_of_score(0.50) == ("L2", "mid")
        assert band_of_score(0.49) == (None, "low")

    def test_hard_and_soft_categories(self):
        """硬/软类别集合与判定函数一致。"""
        assert is_hard_category("child_abuse")
        assert is_hard_category("high_fever")
        assert not is_hard_category("depression")
        assert HARD_CATEGORIES.isdisjoint(SOFT_CATEGORIES)

    def test_hard_category_low_score_forced_block(self):
        """硬类别永不自动放行：低分也强制拦截（L2，hard=True，可引导）。"""
        result = decide("说下怎么处理", SNAPSHOT, _semantic(0.3, "child_selfharm"))
        assert result["blocked"] is True
        assert result["hard"] is True
        assert result["level"] == "L2"
        assert result["guide"] is True


# ----------------------------------------------------------------------
# 二级语义
# ----------------------------------------------------------------------
class TestSecondPass:
    """二级语义模型分级与容错。"""

    def test_semantic_block_high(self):
        """score>0.8 → 拦截 L1/high，无温和引导。"""
        result = decide("任意问题", SNAPSHOT, _semantic(0.9, "pet_poison"))
        assert result["blocked"] is True
        assert result["level"] == "L1"
        assert result["score_band"] == "high"
        assert result["guide"] is False

    def test_semantic_block_with_guide(self):
        """0.5-0.8 → 拦截+温和引导（L2/mid）。"""
        result = decide("任意问题", SNAPSHOT, _semantic(0.65, "depression"))
        assert result["blocked"] is True
        assert result["level"] == "L2"
        assert result["guide"] is True

    def test_semantic_pass_low(self):
        """<0.5 → 放行打标（low）。"""
        result = decide("任意问题", SNAPSHOT, _semantic(0.1, None))
        assert result["blocked"] is False
        assert result["score_band"] == "low"

    def test_semantic_error_conservative_block(self):
        """语义模型异常/超时 → 按命中保守处理（不漏放）。"""

        def _boom(text: str) -> dict:
            """模拟语义调用失败的实现。

            Args:
                text: 输入文本。

            Raises:
                RuntimeError: 始终抛出（模拟超时）。
            """
            raise RuntimeError("timeout")

        result = decide("任意问题", SNAPSHOT, _boom)
        assert result["blocked"] is True
        assert result["level"] == "L1"
        assert result["score_band"] == "high"

    def test_first_pass_priority_over_semantic(self):
        """一级命中时不再调用语义模型（先于一切、省时省钱）。"""
        called = {"n": 0}

        def _spy(text: str) -> dict:
            """调用计数间谍。

            Args:
                text: 输入文本。

            Returns:
                语义分类结果。
            """
            called["n"] += 1
            return {"score": 0.0, "category": None}

        result = decide("涉及虐待的输入", SNAPSHOT, _spy)
        assert result["blocked"] is True
        assert result["hit_source"] == "lexicon"
        assert called["n"] == 0

    def test_decide_semantic_none_pass(self):
        """仅一级场景（semantic_fn=None）：一级未命中放行打标。"""
        result = decide("普通问题", SNAPSHOT, None)
        assert result["blocked"] is False
        assert result["score_band"] == "low"


# ----------------------------------------------------------------------
# 输出过滤
# ----------------------------------------------------------------------
class TestOutputFilter:
    """output_filter：生成内容再过词库/正则，命中置空。"""

    def test_filter_lexicon_hit_emptied(self):
        """内容含词库词条 → 置空。"""
        assert filter_content("建议每天陪读，切勿虐待孩子", SNAPSHOT) == ""

    def test_filter_regex_hit_emptied(self):
        """内容命中疗效正则 → 置空。"""
        assert filter_content("这个方法可以包治百病", SNAPSHOT) == ""

    def test_filter_pass_normal_content(self):
        """正常内容原样返回。"""
        text = "两岁宝宝可以尝试自主进食，注意观察过敏反应。"
        assert filter_content(text, SNAPSHOT) == text

    def test_filter_default_patterns(self):
        """默认正则兜底可用（空库环境）。"""
        snap = LexiconSnapshot(terms=[], patterns=dict(DEFAULT_PATTERNS))
        assert filter_content("请按 10mg 每天", snap) == ""
        assert filter_content("多陪孩子读绘本", snap) != ""

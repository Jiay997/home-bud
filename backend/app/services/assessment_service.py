# -*- coding: utf-8 -*-
"""气质测评计分服务模块。

实现 PRD §12.2 冻结口径的气质测评计分引擎：
- 16 题 / 4 维度（ACT 活动水平、APP 趋近-退缩、ADP 适应性、EMO 情绪强度），各维 4 题；
- 反向题（q_no ∈ {4, 8, 12, 16}）计分 s = 6 - raw；
- 维度均分 HALF_UP 保留两位小数（计分全程仅此一次舍入）；
- 三档判定：低 [1.00, 2.50) / 中 [2.50, 3.50) / 高 [3.50, 5.00]（2.50 归中、3.50 归高）；
- 缺答降级：单维缺答 ≤1 用已答均值；>1 该维 partial「信息不足」不参与判定；
  全局缺答 >3 不出报告（eligible=False，保留断点）；
- 四类类型判定：无任一维达「高」→ easy（随和型）；否则取分数最高的前 2 主导维
  （并列优先级 ACT＞EMO＞APP＞ADP），按无序维度对映射：
  含 ACT → active（活跃型）；否则含 EMO → sensitive（敏感型）；否则 → slow_warm（慢热型）。

计分为纯函数实现，不依赖数据库，可独立单元测试（tests/test_assessment_scoring.py）。
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

# 维度固定顺序（与报告 dimension_bands 区块展示顺序一致）
DIMENSIONS: Tuple[str, ...] = ("ACT", "APP", "ADP", "EMO")

# 冻结的题目-维度映射（PRD §12.2：各维 4 题，与种子题库 kb_question_01~16 对应）
DIMENSION_QUESTIONS: Dict[str, Tuple[int, int, int, int]] = {
    "ACT": (1, 2, 3, 4),
    "APP": (5, 6, 7, 8),
    "ADP": (9, 10, 11, 12),
    "EMO": (13, 14, 15, 16),
}

# 反向题号集合（计分规则 1：s = 6 - raw）
REVERSE_QNOS = frozenset({4, 8, 12, 16})

# 题号 -> 维度 反查表（作答落库与校验使用）
QNO_DIMENSION: Dict[int, str] = {
    q_no: dim for dim, qnos in DIMENSION_QUESTIONS.items() for q_no in qnos
}

# 主导维并列优先级：ACT ＞ EMO ＞ APP ＞ ADP（数值越小优先级越高）
DIM_PRIORITY: Dict[str, int] = {"ACT": 0, "EMO": 1, "APP": 2, "ADP": 3}

# 三档灰度阈值（判定规则 3：2.50 归中、3.50 归高）
GRAY_LOW = Decimal("2.50")
GRAY_HIGH = Decimal("3.50")

# 阈值快照（提交时落库 assessment.threshold_snapshot）
THRESHOLD_SNAPSHOT: Dict[str, float] = {"gray_low": 2.5, "gray_high": 3.5}

# 全局缺答上限：缺答 >3 题不出报告
MAX_GLOBAL_SKIPPED = 3

# 气质类型对内代码 -> 对外类型名（对外命名未定稿，先按 PRD 占位）
TYPE_NAMES: Dict[str, str] = {
    "easy": "随和型",
    "active": "活跃型",
    "sensitive": "敏感型",
    "slow_warm": "慢热型",
}


class AssessmentService:
    """气质测评计分服务。

    全部为无状态静态方法，不依赖数据库与会话，
    供 API 层（assessment_api）与单元测试直接调用。
    """

    @staticmethod
    def round_half_up2(value: Any) -> float:
        """按 HALF_UP（四舍五入）保留两位小数。

        使用 Decimal(str(value)) 规避二进制浮点误差，
        保证 2.345 这类字面值按十进制语义进位。

        Args:
            value: 待舍入数值（float / int / Decimal）。

        Returns:
            HALF_UP 舍入后的两位小数浮点值（如 2.345 -> 2.35）。
        """
        # 先转十进制字符串再量化，避免 float 二进制表示（2.3449999...）导致的向下舍
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @staticmethod
    def band_of(mean: Any) -> str:
        """维度均分 -> 三档档位。

        Args:
            mean: 维度均分（1.00-5.00）。

        Returns:
            "low"（[1.00,2.50)）/ "middle"（[2.50,3.50)）/ "high"（[3.50,5.00]），
            注意 2.50 归中、3.50 归高。
        """
        m = Decimal(str(mean))
        if m < GRAY_LOW:
            return "low"
        if m < GRAY_HIGH:
            return "middle"
        return "high"

    @staticmethod
    def reverse_score(q_no: int, raw_score: int) -> int:
        """按题号做反向题换算。

        Args:
            q_no: 题号（1-16）。
            raw_score: 原始李克特分值（1-5）。

        Returns:
            计分用分值：反向题（4/8/12/16）为 6 - raw，正向题原值返回。
        """
        return 6 - raw_score if q_no in REVERSE_QNOS else raw_score

    @staticmethod
    def score(answers: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """16 题作答计分（PRD §12.2 计分规则 1-4）。

        Args:
            answers: 作答明细列表 [{q_no, dimension, raw_score(1-5) | skipped:True}]；
                raw_score 为 None 或 skipped 为真表示跳题；
                完全未出现的题号（条目缺失）同样按缺答计。

        Returns:
            计分结果字典：
            {
              "dimension_scores": {维: {"mean": float|None, "band": str|None, "partial": bool}},
                  # partial=True 时 mean/band 为 None（信息不足）
              "type_code": "easy"|"active"|"sensitive"|"slow_warm"|None,
                  # eligible=False（全局缺答 >3）时为 None，不出报告
              "skipped_count": int,   # 全局缺答题数（显式跳题 + 未作答）
              "partial_dims": List[str],  # 信息不足、不参与判定的维度
              "eligible": bool,       # False 表示全局缺答 >3，保留断点不出报告
            }
        """
        # 规则 0：归一化作答 -> {题号: 原始分}，None 表示缺答
        raw_by_qno: Dict[int, Optional[int]] = {}
        for item in answers or []:
            q_no = item.get("q_no")
            if q_no is None:
                continue
            if item.get("skipped") or item.get("raw_score") is None:
                raw_by_qno[q_no] = None
            else:
                raw_by_qno[q_no] = int(item["raw_score"])

        dimension_scores: Dict[str, Dict[str, Any]] = {}
        partial_dims: List[str] = []
        skipped_count = 0
        for dim in DIMENSIONS:
            converted: List[int] = []
            missing = 0
            for q_no in DIMENSION_QUESTIONS[dim]:
                raw = raw_by_qno.get(q_no)
                if raw is None:
                    missing += 1  # 显式跳题与未作答均计缺答
                    continue
                # 规则 1：反向题 s = 6 - raw
                converted.append(6 - raw if q_no in REVERSE_QNOS else raw)
            skipped_count += missing
            if missing > 1:
                # 规则 4：单维缺答 >1 -> 该维「信息不足」，不参与判定
                partial_dims.append(dim)
                dimension_scores[dim] = {"mean": None, "band": None, "partial": True}
            else:
                # 规则 2/4：维度均分（缺答 ≤1 用已答均值），HALF_UP 保留两位（仅此一次舍入）
                mean = AssessmentService.round_half_up2(
                    Decimal(sum(converted)) / Decimal(len(converted))
                )
                dimension_scores[dim] = {
                    "mean": mean,
                    "band": AssessmentService.band_of(mean),
                    "partial": False,
                }

        # 规则 4：全局缺答 >3 不出报告（保留断点，由调用方返回错误）
        eligible = skipped_count <= MAX_GLOBAL_SKIPPED
        return {
            "dimension_scores": dimension_scores,
            "type_code": AssessmentService.judge(dimension_scores) if eligible else None,
            "skipped_count": skipped_count,
            "partial_dims": partial_dims,
            "eligible": eligible,
        }

    @staticmethod
    def judge(dimension_scores: Dict[str, Dict[str, Any]]) -> str:
        """四类气质类型判定（PRD §12.2 判定规则 5）。

        Args:
            dimension_scores: score() 输出的维度分结构
                {维: {"mean": float|None, "partial": bool, ...}}；
                档位由 mean 依据 band_of() 现算，不信任外部传入的 band。

        Returns:
            "easy" / "active" / "sensitive" / "slow_warm"。
        """
        # 收集参与判定的维度（partial「信息不足」不参与）
        candidates: List[Tuple[str, Decimal]] = []
        for dim in DIMENSIONS:
            info = dimension_scores.get(dim) or {}
            if info.get("partial"):
                continue
            mean = info.get("mean")
            if mean is None:
                continue
            candidates.append((dim, Decimal(str(mean))))

        # 无任一维达到「高」→ 随和型（easy）
        if not any(AssessmentService.band_of(mean) == "high" for _, mean in candidates):
            return "easy"

        # 取分数最高的前 2 主导维（并列按 ACT＞EMO＞APP＞ADP 优先级）
        candidates.sort(key=lambda t: (-t[1], DIM_PRIORITY[t[0]]))
        top2 = {candidates[0][0], candidates[1][0]}

        # 无序维度对映射：含 ACT 即 active；否则含 EMO 即 sensitive；
        # 否则只可能 APP+ADP → slow_warm
        if "ACT" in top2:
            return "active"
        if "EMO" in top2:
            return "sensitive"
        return "slow_warm"

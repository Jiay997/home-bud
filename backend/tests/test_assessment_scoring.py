# -*- coding: utf-8 -*-
"""气质测评计分引擎单元测试。

覆盖 PRD §12.2 冻结口径：
- C1 全维 1.00 低档 → easy；C2 全维 5.00 高档 → active；C3 反向题换算；
  C4 三档边界；C5 缺答降级（单维 partial / 全局缺答 >3 不出报告）；
- T1-T5 四类类型判定与主导维并列优先级；T6 HALF_UP 舍入。

计分为纯函数调用，不依赖数据库；兼容任意工作目录的 pytest 调用方式
（显式将 backend 目录加入 sys.path）。

注意：反向题（q_no ∈ {4,8,12,16}）计分 s = 6 - raw。因此「每维极值」用例
按换算后目标分构造作答：正向题答目标分、反向题答 6-目标分。
"""
import sys
from pathlib import Path

# 保证从 backend 根目录导入 app 包（无论从哪个目录启动 pytest）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.assessment_service import (  # noqa: E402
    AssessmentService,
    QNO_DIMENSION,
    REVERSE_QNOS,
)


def _answers_uniform_effective(ratings: dict) -> list:
    """按「换算后目标分」生成 16 题作答（测试辅助工厂）。

    正向题原始分 = 目标分；反向题原始分 = 6 - 目标分，
    保证每题换算后（含反向换算）恰好等于目标分。

    Args:
        ratings: {维度代码: 换算后目标分 1-5}。

    Returns:
        answers 列表 [{q_no, dimension, raw_score}]。
    """
    out = []
    for q_no in range(1, 17):
        dim = QNO_DIMENSION[q_no]
        target = ratings[dim]
        raw = 6 - target if q_no in REVERSE_QNOS else target
        out.append({"q_no": q_no, "dimension": dim, "raw_score": raw})
    return out


def _answers(default: int, overrides: dict = None, skips: tuple = ()) -> list:
    """按原始分生成 16 题作答明细（测试辅助工厂，用于反向题专项验证）。

    Args:
        default: 全部题目的默认原始李克特分值（1-5）。
        overrides: {q_no: 原始分} 按题号覆盖项。
        skips: 需要显式跳题（skipped=True）的题号集合。

    Returns:
        answers 列表 [{q_no, dimension, raw_score}]
        （跳题为 {.., skipped: True, raw_score: None}）。
    """
    overrides = overrides or {}
    out = []
    for q_no in range(1, 17):
        dim = QNO_DIMENSION[q_no]
        if q_no in skips:
            out.append({"q_no": q_no, "dimension": dim, "skipped": True, "raw_score": None})
        else:
            out.append({"q_no": q_no, "dimension": dim, "raw_score": overrides.get(q_no, default)})
    return out


def test_c1_all_low_is_easy():
    """C1：每维换算后均 1.00 低档，无「高」→ easy。

    构造说明：正向题答 1、反向题（4/8/12/16）答 5，
    反向换算后每题计 1 分，等价于「全部作答落在低活动端」。
    """
    result = AssessmentService.score(
        _answers_uniform_effective({"ACT": 1, "APP": 1, "ADP": 1, "EMO": 1})
    )
    ds = result["dimension_scores"]
    assert all(ds[d]["mean"] == 1.0 for d in ds), "每维均值应为 1.00"
    assert all(ds[d]["band"] == "low" for d in ds), "每维均应为低档"
    assert result["type_code"] == "easy"
    assert result["eligible"] is True
    assert result["skipped_count"] == 0
    assert result["partial_dims"] == []


def test_c2_all_high_is_active():
    """C2：每维换算后均 5.00 高档 → 主导维并列取优先级 ACT+EMO → active。"""
    result = AssessmentService.score(
        _answers_uniform_effective({"ACT": 5, "APP": 5, "ADP": 5, "EMO": 5})
    )
    ds = result["dimension_scores"]
    assert all(ds[d]["mean"] == 5.0 for d in ds), "每维均值应为 5.00"
    assert all(ds[d]["band"] == "high" for d in ds), "每维均应为高档"
    # 四维并列 5.00，按 ACT＞EMO＞APP＞ADP 取前两主导维 {ACT, EMO} → active
    assert result["type_code"] == "active"


def test_c3_reverse_question():
    """C3：反向题 q_no=4 答 1 → 计 5；ACT 维均值 (2+2+2+5)/4 = 2.75。"""
    assert AssessmentService.reverse_score(4, 1) == 5, "反向题 4 答 1 应计 5"
    assert AssessmentService.reverse_score(1, 1) == 1, "正向题应原值计分"
    answers = _answers(3, overrides={1: 2, 2: 2, 3: 2, 4: 1})
    result = AssessmentService.score(answers)
    ds = result["dimension_scores"]
    assert ds["ACT"]["mean"] == 2.75, "ACT 反向换算后均值应为 2.75"
    assert ds["ACT"]["band"] == "middle"
    # 无任何维达「高」→ easy
    assert result["type_code"] == "easy"


def test_c4_band_boundaries():
    """C4：边界值——恰 2.50 → middle；恰 3.50 → high（band_of 与 score 全链路）。"""
    # 直接档位判定（注意 2.50 归中、3.50 归高）
    assert AssessmentService.band_of(2.50) == "middle"
    assert AssessmentService.band_of(2.49) == "low"
    assert AssessmentService.band_of(3.50) == "high"
    assert AssessmentService.band_of(3.49) == "middle"
    assert AssessmentService.band_of(1.00) == "low"
    assert AssessmentService.band_of(5.00) == "high"
    # 恰 2.50：ACT 换算后为 2,2,3,3（q4 为反向题，原始 3 换算仍为 3）
    r_mid = AssessmentService.score(_answers(3, overrides={1: 2, 2: 2, 3: 3, 4: 3}))
    assert r_mid["dimension_scores"]["ACT"]["mean"] == 2.5
    assert r_mid["dimension_scores"]["ACT"]["band"] == "middle"
    assert r_mid["type_code"] == "easy"
    # 恰 3.50：ACT 换算后为 3,3,4,4（q4 反向题原始 2 → 计 4）
    r_high = AssessmentService.score(_answers(3, overrides={1: 3, 2: 3, 3: 4, 4: 2}))
    assert r_high["dimension_scores"]["ACT"]["mean"] == 3.5
    assert r_high["dimension_scores"]["ACT"]["band"] == "high"
    # ACT 达高 → 主导维 ACT + （并列 3.0 中优先级最高的 EMO）→ active
    assert r_high["type_code"] == "active"


def test_c5_partial_and_ineligible():
    """C5：缺答降级——单维缺 2 题 → partial；单维缺 1 题 → 已答均值；全局缺 4 题 → eligible=False。"""
    # 单维（ACT）缺 2 题：partial=True、不参与判定，其余维正常
    r_partial = AssessmentService.score(_answers(3, skips=(1, 2)))
    assert r_partial["partial_dims"] == ["ACT"]
    assert r_partial["dimension_scores"]["ACT"]["partial"] is True
    assert r_partial["dimension_scores"]["ACT"]["mean"] is None
    assert r_partial["eligible"] is True
    # ACT 不参与判定，其余三维均 3.00 无「高」→ easy
    assert r_partial["type_code"] == "easy"
    # 缺答也可以是「整题缺失」（未作答条目不出现在列表中），结果一致
    absent = [a for a in _answers(3) if a["q_no"] not in (1, 2)]
    assert AssessmentService.score(absent)["partial_dims"] == ["ACT"]
    # 单维缺 1 题：用已答均值（q2=4, q3=4, q4=2 反向计 4 → 12/3 = 4.00 高档）
    r_one = AssessmentService.score(_answers(3, overrides={2: 4, 3: 4, 4: 2}, skips=(1,)))
    ds_one = r_one["dimension_scores"]["ACT"]
    assert r_one["skipped_count"] == 1
    assert ds_one["partial"] is False
    assert ds_one["mean"] == 4.0
    assert ds_one["band"] == "high"
    # ACT 高 → 主导维 ACT + EMO（并列 3.0 优先级最高）→ active
    assert r_one["type_code"] == "active"
    # 全局缺 4 题（ACT 缺 2 + APP 缺 2）：不出报告
    r_over = AssessmentService.score(_answers(3, skips=(1, 2, 5, 6)))
    assert r_over["skipped_count"] == 4
    assert r_over["eligible"] is False
    assert r_over["type_code"] is None
    assert r_over["partial_dims"] == ["ACT", "APP"]


def test_t1_act_high_others_middle_is_active():
    """T1：ACT 高（4.00）其余中（3.00）→ 主导维 ACT+EMO → active。"""
    result = AssessmentService.score(
        _answers_uniform_effective({"ACT": 4, "APP": 3, "ADP": 3, "EMO": 3})
    )
    ds = result["dimension_scores"]
    assert ds["ACT"]["band"] == "high"
    assert all(ds[d]["band"] == "middle" for d in ("APP", "ADP", "EMO"))
    assert result["type_code"] == "active"


def test_t2_app_adp_high_is_slow_warm():
    """T2：APP+ADP 高（4.00）其余低（2.00）→ slow_warm。"""
    result = AssessmentService.score(
        _answers_uniform_effective({"ACT": 2, "APP": 4, "ADP": 4, "EMO": 2})
    )
    ds = result["dimension_scores"]
    assert ds["APP"]["mean"] == 4.0 and ds["ADP"]["mean"] == 4.0
    assert ds["APP"]["band"] == "high" and ds["ADP"]["band"] == "high"
    assert ds["ACT"]["band"] == "low" and ds["EMO"]["band"] == "low"
    assert result["type_code"] == "slow_warm"


def test_t3_emo_app_high_is_sensitive():
    """T3：EMO+APP 高（4.00）、ACT 低（2.00）、ADP 中（3.00）→ sensitive。"""
    result = AssessmentService.score(
        _answers_uniform_effective({"ACT": 2, "APP": 4, "ADP": 3, "EMO": 4})
    )
    ds = result["dimension_scores"]
    assert ds["EMO"]["band"] == "high" and ds["APP"]["band"] == "high"
    assert ds["ACT"]["band"] == "low" and ds["ADP"]["band"] == "middle"
    assert result["type_code"] == "sensitive"


def test_t4_tie_priority():
    """T4：并列优先级——ACT 与 ADP 同为 3.6 → 前两主导维 ACT+ADP → active。"""
    ds = {
        "ACT": {"mean": 3.6, "partial": False},
        "APP": {"mean": 2.0, "partial": False},
        "ADP": {"mean": 3.6, "partial": False},
        "EMO": {"mean": 2.0, "partial": False},
    }
    assert AssessmentService.judge(ds) == "active"
    # 对照：EMO 与 APP 并列 3.6（ACT/ADP 低）→ 前两主导维 EMO+APP → sensitive
    ds2 = {
        "ACT": {"mean": 2.0, "partial": False},
        "APP": {"mean": 3.6, "partial": False},
        "ADP": {"mean": 2.0, "partial": False},
        "EMO": {"mean": 3.6, "partial": False},
    }
    assert AssessmentService.judge(ds2) == "sensitive"


def test_t5_no_high_is_easy():
    """T5：无任何「高」→ easy；partial 维即便分高也不参与判定。"""
    ds = {
        "ACT": {"mean": 3.49, "partial": False},
        "APP": {"mean": 3.49, "partial": False},
        "ADP": {"mean": 2.0, "partial": False},
        "EMO": {"mean": 3.49, "partial": False},
    }
    assert AssessmentService.judge(ds) == "easy"
    # ACT 信息不足（partial），其余三维均 3.0 无「高」→ easy
    ds_partial = {
        "ACT": {"mean": None, "partial": True},
        "APP": {"mean": 3.0, "partial": False},
        "ADP": {"mean": 3.0, "partial": False},
        "EMO": {"mean": 3.0, "partial": False},
    }
    assert AssessmentService.judge(ds_partial) == "easy"


def test_t6_half_up_rounding():
    """T6：HALF_UP——均值 2.345 → 2.35（进位而非 2.34）。

    档位说明：2.35 < 2.50，按三档规则属 low 档；
    middle 档的 HALF_UP 边界另以 2.545 → 2.55 验证。
    """
    assert AssessmentService.round_half_up2(2.345) == 2.35, "2.345 应 HALF_UP 进位为 2.35"
    assert AssessmentService.round_half_up2(2.344) == 2.34
    assert AssessmentService.band_of(2.35) == "low"
    # middle 档内的 HALF_UP 进位：2.545 → 2.55，档位 middle
    assert AssessmentService.round_half_up2(2.545) == 2.55
    assert AssessmentService.band_of(2.55) == "middle"

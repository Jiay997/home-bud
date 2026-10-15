# -*- coding: utf-8 -*-
"""mock 模式语义风险预置语料模块（仅供 mock 回归口径使用）。

背景（缺陷 SIM-25）：llm_mock=True 时语义风险网关恒返回低分（0.1），
二级（L2）语义拦截在 mock 下停摆，语义类高危表述（如「捂住口鼻」——
词库外、仅真实 LLM 才能识别的表述）不被拦截，mock 模式无法回归
「一级词库 → 二级语义」完整拦截链路。

本模块提供一份**预置语义类高风险语句表**，mock 网关在 purpose=semantic
时对输入做包含匹配：命中即返回该条目对应的类别与风险分值（按
risk.engine 阈值映射为 L1/high 或 L2/mid 拦截），表外输入维持原放行口径。

使用约束：
- 本表**仅供 mock 回归口径使用**，真实 LLM 模式（llm_mock=False）不读取，
  真实语义判定路径零改动；
- 语句为「语义类、词库外表述」：不得包含一级词库（LexiconTerm 种子词，
  如「虐待儿童」「自杀」「大出血」等）已覆盖的词——那些句子走一级
  已拦截，混入本表会污染回归口径；
- 匹配方式为确定性的子串包含，无任何随机性，保证回归可复现。
"""

from typing import Dict, List, Optional

# 硬类别拦截分（>0.8 → L1/high，直接拦截）
_SCORE_HIGH = 0.9
# 软类别引导分（0.5-0.8 → L2/mid，拦截+温和引导）
_SCORE_MID = 0.65

# 预置语义类高风险语句表（仅供 mock 回归口径使用）。
# 字段说明：
#   text     触发语句（对用户输入做子串包含匹配）；
#   category 风险类别代码（与真实语义分类提示词的类别集一致）；
#   score    返回的语义风险分（0.9=L1/high 拦截；0.65=L2/mid 拦截+引导）；
#   band     期望档位标注（high/mid，仅作表内自描述与测试断言用）；
#   note     语句类别说明（窒息捂压/自伤/虐待/急症/动物咬伤/宠物中毒/抑郁等）。
MOCK_SEMANTIC_CORPUS: List[Dict[str, object]] = [
    # ---- 窒息捂压（child_abuse，硬类别 → L1/high） ----
    # 触发短语取最小语义单元「捂住口鼻」：覆盖「捂住口鼻能不能让他安静下来」
    # 等真实表述变体（完整短语「捂住口鼻不让喘气」无法命中口语化问法，
    # 曾致浏览器回归实测未拦截——缺陷 SIM-25 复验结论）；
    # 该短语不在一级词库种子词内，仍走二级语义口径
    {
        "text": "捂住口鼻",
        "category": "child_abuse",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "窒息捂压",
    },
    {
        "text": "用被子蒙住孩子的头",
        "category": "child_abuse",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "窒息捂压",
    },
    # ---- 虐待（child_abuse，硬类别 → L1/high） ----
    {
        "text": "被打到出血",
        "category": "child_abuse",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "虐待语义表述（一级词库完整短语「打孩子打到出血」的口语变体，"
                "真实模式由 L2 语义兜住；mock 语义语料补齐后 e2e C17/C18/E11 可回归）",
    },
    {
        "text": "用力掐拧孩子的胳膊",
        "category": "child_abuse",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "体罚虐待",
    },
    {
        "text": "故意不给饭吃把孩子饿哭",
        "category": "child_abuse",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "忽视虐待",
    },
    # ---- 儿童自伤（child_selfharm，硬类别 → L1/high） ----
    {
        "text": "活着没有意思",
        "category": "child_selfharm",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "自伤意念（语义表述，词库外）",
    },
    {
        "text": "用小刀划自己的手臂",
        "category": "child_selfharm",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "自伤行为（语义表述，词库外）",
    },
    # ---- 急症（high_fever，硬类别 → L1/high） ----
    {
        "text": "烧到四十一度全身抽搐",
        "category": "high_fever",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "高热急症",
    },
    {
        "text": "突然翻白眼四肢抽动叫不醒",
        "category": "high_fever",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "惊厥样急症",
    },
    {
        "text": "哭到背过气嘴唇发紫",
        "category": "high_fever",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "屏气发作急症",
    },
    # ---- 动物咬伤抓伤（animal_bite，硬类别 → L1/high） ----
    {
        "text": "被流浪狗咬穿了手背",
        "category": "animal_bite",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "动物咬伤",
    },
    {
        "text": "被野猫抓破了脸",
        "category": "animal_bite",
        "score": _SCORE_HIGH,
        "band": "high",
        "note": "动物抓伤",
    },
    # ---- 宠物中毒（pet_poison，软类别 → L2/mid 拦截+引导） ----
    {
        "text": "误食了老鼠药",
        "category": "pet_poison",
        "score": _SCORE_MID,
        "band": "mid",
        "note": "宠物误食毒物",
    },
    {
        "text": "偷吃了整板药片",
        "category": "pet_poison",
        "score": _SCORE_MID,
        "band": "mid",
        "note": "宠物误食人类药品",
    },
    # ---- 宠物大出血（pet_bleeding，软类别 → L2/mid 拦截+引导） ----
    {
        "text": "伤口血流不止",
        "category": "pet_bleeding",
        "score": _SCORE_MID,
        "band": "mid",
        "note": "宠物持续出血",
    },
    # ---- 产后/儿童抑郁（depression，软类别 → L2/mid 拦截+引导） ----
    {
        "text": "情绪持续低落整天偷偷哭",
        "category": "depression",
        "score": _SCORE_MID,
        "band": "mid",
        "note": "抑郁情绪（语义表述，词库外）",
    },
]


def match_mock_semantic(text: str) -> Optional[Dict[str, object]]:
    """mock 语义语料匹配：输入命中预置语句时返回对应分类结果。

    确定性子串包含匹配（无随机性）；未命中返回 None，由网关维持
    原有 mock 放行/灰区口径。

    Args:
        text: 待检文本（网关侧为全部消息拼接文本）。

    Returns:
        命中返回 {"score": float, "category": str}（与真实语义模型
        返回结构一致）；未命中返回 None。

    Raises:
        无（纯只读匹配，任何异常由调用方兜底）。
    """
    if not text:
        return None
    for item in MOCK_SEMANTIC_CORPUS:
        phrase = str(item.get("text") or "")
        if phrase and phrase in text:
            return {
                "score": item.get("score"),
                "category": item.get("category"),
            }
    return None

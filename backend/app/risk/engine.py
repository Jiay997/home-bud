# -*- coding: utf-8 -*-
"""风险引擎纯函数模块。

实现两级风险流水线的核心判定逻辑（架构 §5.1），先于一切生成动作执行：
- 一级规则引擎：词库明文匹配 + RiskRuleConfig 正则匹配，命中直接阻断（L1）；
- 二级语义模型：DeepSeek 风险分类（score/category JSON），分级决策——
  score>0.8 拦截（L1/high）；0.5-0.8 拦截+温和引导（L2/mid）；
  <0.5 放行打标（low）；硬类别永不自动放行；语义调用异常按命中保守处理；
- 输出过滤：生成内容逐 block 再过词库与正则，命中置空。

本模块全部为纯函数/纯数据，不依赖数据库与网络，
可独立单元测试（tests/test_risk_engine.py）。
"""
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# 硬风险类别：永不自动放行（即使语义分低也强制拦截，不可申诉自动放行）
HARD_CATEGORIES = frozenset({"child_abuse", "child_selfharm", "high_fever", "animal_bite"})

# 软风险类别：可拦截后走申诉放行通道
SOFT_CATEGORIES = frozenset({"depression", "pet_poison", "pet_bleeding"})

# 语义分级阈值（>0.8 拦截；0.5-0.8 拦截+温和引导；<0.5 放行）
SCORE_BLOCK = 0.8
SCORE_GUIDE = 0.5

# 语义风险分类系统提示词（要求只返回 JSON）
SEMANTIC_RISK_PROMPT = (
    "你是家庭养育内容的安全风险分类器。判断用户输入是否涉及以下风险类别，"
    "只输出一个 JSON 对象，不要输出任何其他文字：\n"
    '{"score": <0到1之间的风险分>, "category": <类别代码或null>}\n'
    "类别代码：child_abuse(虐待儿童)、child_selfharm(儿童自伤)、high_fever(高热惊厥、窒息、误食、溺水、烫伤等急症)、"
    "animal_bite(动物咬伤抓伤)、depression(产后/儿童抑郁)、pet_poison(宠物中毒)、"
    "pet_bleeding(宠物大出血)。无风险或无法判断时 category 为 null、score 接近 0。"
)

# RiskRuleConfig 缺失时的兜底正则（开发/空库环境保证一级引擎可用）
DEFAULT_PATTERNS: Dict[str, dict] = {
    "medicine_dosage_pattern": {
        "regex": r"(?i)\d+\s*(mg|ml|毫克|毫升)",
        "category_code": "medicine_dosage",
    },
    "diagnosis_pattern": {
        "regex": r"(确诊|诊断为|判断为)[一-龥]{0,12}(病|症|炎|综合征)",
        "category_code": "diagnosis",
    },
    "efficacy_pattern": {
        "regex": r"(保证|包治|根治|药到病除|百分百有效)",
        "category_code": "efficacy",
    },
    # 缺陷 D1（2026-10-19 全功能模拟测试报告）：一级词库原先只收「高烧惊厥」
    # 「热性惊厥」等复合短语，缺「抽搐/窒息/烫伤」等独立急症表述，口语化短句
    # （如「宝宝突然抽搐了怎么办」）一级不命中；LLM_MOCK=true 时二级语义恒返回
    # 低分，整条风险链静默放行。此处补齐急症模式兜底，空库/未重新播种的环境
    # 同样生效（DB 配置存在时按 config_key 覆盖）。
    # 类别归入 high_fever：PRD/后台口径中 high_fever 即「儿童急症类」，其危机
    # 渠道卡为「儿科急症就诊」；exclude_if 排除宠物语境，避免把宠物急症误判为
    # 儿童急症（宠物中毒/出血走 pet_poison / pet_bleeding 语义与词库链路）。
    "acute_emergency_pattern": {
        "regex": (
            r"(抽搐|惊厥|窒息|噎住|噎到|呛奶|呛到|溺水|"
            r"烫伤|烧伤|呼吸困难|喘不上气|叫不醒|翻白眼|失去意识)"
        ),
        "category_code": "high_fever",
        "exclude_if": r"(狗|犬|猫|宠物|汪|喵)",
    },
    # 药物/化学品摄入模式：补齐「药名 + 剂量」正则覆盖不到的摄入表述
    # （「药片误食」这类无剂量词的问法）。两个方向都要覆盖——「误食…药片」
    # 与「药片…误食」；宠物语境同样排除，宠物误食由 pet_poison 链路处理。
    "medicine_ingestion_pattern": {
        "regex": (
            r"(误食|误服|吞下|咽下|当糖吃)[^。]{0,12}"
            r"(药|药片|胶囊|药水|退烧药|布洛芬|对乙酰氨基酚|消毒液|清洁剂|农药)"
            r"|(药片|胶囊|药水|退烧药|布洛芬|对乙酰氨基酚|消毒液|清洁剂|农药|纽扣电池)"
            r"[^。]{0,12}(误食|误服|吞下|咽下|吃下去|吃了)"
        ),
        "category_code": "medicine_dosage",
        "exclude_if": r"(狗|犬|猫|宠物|汪|喵)",
    },
}


@dataclass
class LexiconSnapshot:
    """词库快照（一级规则引擎的输入）。

    由 RiskService 从 LexiconTerm + RiskRuleConfig 加载并缓存 60s，
    本结构本身为纯数据，可手工构造用于测试。

    Attributes:
        terms: 词条列表 [{"term": 明文, "category_code": 类别, "strategy": 策略}]。
        patterns: 正则配置 {规则键: {"regex": 表达式, "category_code": 类别}}。
        loaded_at: 加载时间戳（单调语义仅作观测）。
        term_rows: 库内 effective 词条行数（解密前，用于识别「词库整体不可用」）。
        term_decrypt_failed: 解密失败被跳过的词条数。
        degraded_reason: 非 None 表示快照不可信（安全依赖失效），
            风险入口据此按「命中」保守处理（PRD：服务不可用按命中处理）。
    """

    terms: List[dict] = field(default_factory=list)
    patterns: Dict[str, dict] = field(default_factory=dict)
    loaded_at: float = 0.0
    term_rows: int = 0
    term_decrypt_failed: int = 0
    degraded_reason: Optional[str] = None

    def usable(self) -> bool:
        """判断快照是否可用于安全判定。

        Returns:
            True 表示快照可信；False 表示安全依赖失效，调用方须按命中处理。
        """
        return not self.degraded_reason


def is_hard_category(category_code: Optional[str]) -> bool:
    """判断风险类别是否为硬类别（永不自动放行）。

    Args:
        category_code: 风险类别代码，可为 None。

    Returns:
        属于硬类别返回 True。
    """
    return category_code in HARD_CATEGORIES


def match_lexicon(text: str, terms: List[dict]) -> Optional[dict]:
    """一级规则引擎：词库明文匹配。

    Args:
        text: 待检文本（用户问题/生成内容）。
        terms: 词条列表，元素含 term/category_code/strategy 键。

    Returns:
        命中返回 {"term", "category_code", "level": "L1", "source": "lexicon"}；
        未命中返回 None。
    """
    if not text:
        return None
    for item in terms:
        term = item.get("term") or ""
        # 空词条跳过（密文解密失败时 service 侧已跳过，此处双保险）
        if term and term in text:
            return {
                "term": term,
                "category_code": item.get("category_code"),
                "level": "L1",
                "source": "lexicon",
            }
    return None


def match_regex_rules(text: str, patterns: Dict[str, dict]) -> Optional[dict]:
    """一级规则引擎：RiskRuleConfig 正则匹配。

    规则可选带 `exclude_if`（排除正则）：命中正文但文本同时命中排除正则
    时跳过该条规则——用于按语境消歧（如「急症」规则排除宠物语境，
    避免把宠物急症误判为儿童急症）。

    Args:
        text: 待检文本。
        patterns: 正则配置 {规则键: {"regex": ..., "category_code": ...,
            "exclude_if": ...(可选)}}，非法正则按未命中跳过（不阻断主流程）。

    Returns:
        命中返回 {"term": 规则键, "category_code", "level": "L1",
        "source": "regex"}；未命中返回 None。
    """
    if not text:
        return None
    for key, cfg in (patterns or {}).items():
        regex = (cfg or {}).get("regex")
        if not regex:
            continue
        try:
            if not re.search(regex, text):
                continue
            exclude = (cfg or {}).get("exclude_if")
            if exclude and re.search(exclude, text):
                # 语境不匹配（如宠物语境下的急症规则）：跳过本规则
                continue
            return {
                "term": key,
                "category_code": (cfg or {}).get("category_code"),
                "level": "L1",
                "source": "regex",
            }
        except re.error:
            # 配置了非法正则：跳过该条规则，不影响其他规则
            continue
    return None


def first_pass(text: str, snapshot: LexiconSnapshot) -> Optional[dict]:
    """一级规则引擎判定：词库 + 正则，任一命中即阻断（L1）。

    Args:
        text: 待检文本。
        snapshot: 词库快照（含词条与正则配置）。

    Returns:
        命中返回完整 risk_result（blocked=True, level=L1,
        score_band=rule_hit）；未命中返回 None（进入二级）。
    """
    hit = match_lexicon(text, snapshot.terms) or match_regex_rules(text, snapshot.patterns)
    if hit is None:
        return None
    category = hit.get("category_code")
    return {
        "blocked": True,
        "level": "L1",
        "category_code": category,
        "score": None,
        "score_band": "rule_hit",
        "hit_term": hit.get("term"),
        "hit_source": hit.get("source"),
        "guide": False,
        "hard": is_hard_category(category),
        "reason": f"命中一级规则：{hit.get('term')}",
    }


def band_of_score(score: float) -> tuple:
    """语义风险分 → (level, score_band) 分级。

    Args:
        score: 语义模型输出的 0-1 风险分。

    Returns:
        (level, band) 元组：>0.8 → ("L1","high")；
        0.5-0.8 → ("L2","mid")；<0.5 → (None,"low")。
    """
    if score > SCORE_BLOCK:
        return ("L1", "high")
    if score >= SCORE_GUIDE:
        return ("L2", "mid")
    return (None, "low")


def second_pass(text: str, semantic_fn: Callable[[str], dict]) -> dict:
    """二级语义模型判定。

    调用注入的 semantic_fn（内部封装 DeepSeek 分类调用），
    超时/异常/解析失败按命中保守处理（不漏放）；
    硬类别永不自动放行：低分但类别为硬类别时强制拦截。

    Args:
        text: 待检文本。
        semantic_fn: 语义分类函数，签名 (text) -> {"score": float,
            "category": str|None}；失败时抛异常。

    Returns:
        完整 risk_result 字典（blocked/level/score/score_band/...）。
    """
    try:
        sem = semantic_fn(text) or {}
        score = float(sem.get("score") or 0.0)
        category = sem.get("category") or None
    except Exception:  # noqa: BLE001 — 超时/网络/解析失败一律保守按命中
        return {
            "blocked": True,
            "level": "L1",
            "category_code": "semantic_unavailable",
            "score": 0.9,
            "score_band": "high",
            "hit_term": "semantic_unavailable",
            "hit_source": "semantic",
            "guide": False,
            "hard": False,
            "reason": "语义风险模型不可用，按命中保守处理",
        }
    level, band = band_of_score(score)
    hard = is_hard_category(category)
    blocked = level is not None
    # 硬类别永不自动放行：低分也强制拦截（L2，可申诉）
    if not blocked and hard:
        return {
            "blocked": True,
            "level": "L2",
            "category_code": category,
            "score": score,
            "score_band": "mid",
            "hit_term": None,
            "hit_source": "semantic",
            "guide": True,
            "hard": True,
            "reason": f"硬类别风险（{category}），永不自动放行",
        }
    return {
        "blocked": blocked,
        "level": level,
        "category_code": category,
        "score": score,
        "score_band": band,
        "hit_term": None,
        "hit_source": "semantic",
        "guide": bool(blocked) and level == "L2",
        "hard": hard,
        "reason": (
            f"语义风险分 {score:.2f}（{'拦截+温和引导' if level == 'L2' else '拦截' if blocked else '放行打标'}）"
        ),
    }


def decide(
    text: str,
    snapshot: LexiconSnapshot,
    semantic_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """两级风险流水线入口：先一级规则，后二级语义。

    Args:
        text: 待检文本（用户问题原文）。
        snapshot: 词库快照。
        semantic_fn: 二级语义分类函数（None 时仅跑一级，
            一级未命中视为放行，用于纯一级场景如申诉备注）。

    Returns:
        完整 risk_result 字典：
        {blocked, level(L1/L2/None), category_code, score, score_band
        (rule_hit/high/mid/low), hit_term, hit_source, guide, hard, reason}。
    """
    # 一级：命中直接阻断，不调语义模型
    hit = first_pass(text, snapshot)
    if hit is not None:
        return hit
    # 一级未命中：调二级语义模型（None 时直接放行打标）
    if semantic_fn is None:
        return {
            "blocked": False,
            "level": None,
            "category_code": None,
            "score": None,
            "score_band": "low",
            "hit_term": None,
            "hit_source": None,
            "guide": False,
            "hard": False,
            "reason": "仅一级流水线，未命中",
        }
    return second_pass(text, semantic_fn)


def filter_content(text: str, snapshot: LexiconSnapshot) -> str:
    """输出过滤器：生成内容再过一遍词库与正则，命中置空。

    用于 output_filter 节点对每个 block content 的最终把关。

    Args:
        text: 生成的 block 内容。
        snapshot: 词库快照。

    Returns:
        命中返回空串（该 block content 置空）；未命中原样返回。
    """
    if not text:
        return text
    if match_lexicon(text, snapshot.terms) is not None:
        return ""
    if match_regex_rules(text, snapshot.patterns) is not None:
        return ""
    return text


def build_semantic_messages(text: str) -> List[dict]:
    """构造二级语义风险分类的消息列表。

    Args:
        text: 用户问题原文。

    Returns:
        OpenAI 兼容消息列表（system 提示词 + user 输入）。
    """
    return [
        {"role": "system", "content": SEMANTIC_RISK_PROMPT},
        {"role": "user", "content": text},
    ]

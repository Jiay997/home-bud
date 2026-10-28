# -*- coding: utf-8 -*-
"""分级决策规则引擎（RQ-06 §3.6.3「判定位置」：服务端规则引擎，毫秒级）。

设计要点：

- **判定在规则引擎，不在模型**：档位只由规则命中结果决定；模型仅负责观察项
  文案与追问理解，**不得改写档位**（`triage` 对象不参与权重排序）；
- **保守从严**：同级取优先级高者，跨级取严重档（🔴 > 🟡 > 🟢）；条件信息
  缺失时不落入 🟢（要求 `mental_state=normal` 的规则在未识别到正常精神
  状态时不命中）；
- **可还原**：输出携带 `rule_hits[].rule_id` 与 `rule_version`，
  满足 DR-29「线上判定必须可还原命中的规则版本」；
- **不输出确定性结论**：模板文案受 `DETERMINISTIC_PHRASES` 断言约束
  （AC-RQ06-4 / NFR-Q6），命中即为内容缺陷。

规则来源：`triage_rule` 表（后台可配置、可灰度、带专家审核留痕）。表为空时
回退 `triage.templates.TRIAGE_RULES` 内置首批模板，保证功能可用性（fail-safe
口径：规则引擎不可用时输出「分级服务暂不可用」，**不得静默降级为纯模型回答**）。
"""
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.cache import cache
from ..core.config import get_settings
from . import templates

# 规则快照缓存（与词库快照同口径：60 秒内全量生效）
TRIAGE_CACHE_KEY = "triage:snapshot"
TRIAGE_CACHE_TTL = 60

# 上海时区（夜间判定口径，UTC+8）
_TZ_SHANGHAI = timezone(timedelta(hours=8))

# 档位严重度排序（跨级取严重档）
LEVEL_RANK = {"green": 1, "yellow": 2, "red": 3}

# 档位展示顺序（前端渲染用）
LEVEL_ORDER = ["red", "yellow", "green"]

# 禁止出现的确定性结论表述（AC-RQ06-4 / NFR-Q6 零容忍抽检口径）
DETERMINISTIC_PHRASES = (
    "不用去医院",
    "不需要去医院",
    "肯定没事",
    "绝对没事",
    "放心",
    "可以放心",
    "保证没事",
    "一定能好",
    "就是普通感冒",
    "确诊为",
)

# 精神状态识别词表
POOR_STATE_KEYWORDS = (
    "精神萎靡", "精神差", "精神很差", "嗜睡", "叫不醒", "萎靡", "没精神",
    "反应差", "意识不清", "昏迷", "翻白眼", "蔫", "虚脱",
)
NORMAL_STATE_KEYWORDS = (
    "精神好", "精神状态正常", "精神不错", "精神还可以", "精神正常", "精神尚可",
    "能吃能玩", "活蹦乱跳", "能玩能闹", "精神挺好", "精神状态好",
    # 口语化补充（D-03）：家长常用「还好 / 还行 / 挺好 / 没事」描述精神反应
    "精神还好", "精神还行", "精神很好", "精神状态还可以", "精神头不错",
    "状态还好", "状态不错", "吃喝正常", "能吃能睡", "照常玩耍",
)

# 「有风险」的否定语境（避免「没有呕吐」被当作呕吐命中）
NEGATION_PREFIXES = ("没有", "没", "无", "未", "不", "不伴", "未出现", "并没有")

# 体温正则（38.5℃ / 38.5 度 / 38度5 / 体温 38.2）
_TEMP_RE = re.compile(r"(?<![0-9])(3[4-9](?:\.\d)?|4[0-3](?:\.\d)?)\s*(?:℃|度|摄氏度)")
_TEMP_HALF_RE = re.compile(r"(3[4-9]|4[0-3])\s*度\s*([0-9])\s*(?![0-9])")
# 无单位读数（「低烧 37.8」「体温38.2」这类口语省略单位的写法）
_TEMP_BARE_RE = re.compile(
    r"(?:体温|发烧|发热|低烧|高烧|烧到|烧了)\s*[约]?\s*"
    r"(3[4-9](?:\.\d)?|4[0-3](?:\.\d)?)"
)
# 持续时长正则
_DURATION_HOUR_RE = re.compile(r"(\d{1,3})\s*(?:个)?\s*(?:小时|钟头)")
_DURATION_DAY_RE = re.compile(r"(\d{1,2})\s*(?:天|日)")

# 问题文本中的年龄表达（D-02：未绑定档案时从问句推断月龄）
# 例：「2岁」「2岁3个月」「24个月」「3月龄」「6个月大」
_AGE_YEAR_MONTH_RE = re.compile(r"(\d{1,2})\s*岁\s*(\d{1,2})\s*(?:个)?\s*月")
_AGE_YEAR_RE = re.compile(r"(\d{1,2})\s*岁")
_AGE_MONTH_RE = re.compile(r"(\d{1,3})\s*(?:个)?\s*(?:月龄|月大|个月)")

# 常用中文化提示：场景关键词之外的口语补充（不改变场景判定，仅提高命中）
DEFAULT_MISSING_INFO = list(templates.MISSING_INFO_PROMPT)


class TriageUnavailable(RuntimeError):
    """分级服务不可用（规则加载失败等）：按 PRD §3.6.4 输出「暂不可用」态。"""


@dataclass
class TriageSnapshot:
    """分级规则快照（进程内缓存，避免每次问答访问数据库）。

    Attributes:
        rules: 归一化后的规则列表。
        loaded_at: 加载时间戳。
        rule_version: 快照内规则最大版本（DR-29 可还原）。
        source: 来源（db / builtin）。
    """

    rules: List[Dict[str, Any]] = field(default_factory=list)
    loaded_at: float = 0.0
    rule_version: int = 1
    source: str = "builtin"
    signed: int = 0

    def usable(self) -> bool:
        """快照是否可用（至少一条 active 规则）。

        Returns:
            True 表示可用于判定。
        """
        return bool(self.rules)

    def decision_rules(self) -> List[Dict[str, Any]]:
        """返回可用于对外判定的规则（D-07：未签署规则不得对外生效）。

        DB 来源的快照只允许已写 `expert_signoff` 的规则参与判定；内置首批
        模板由 PRD 基线评审（`source=builtin`）不在此处过滤，保证纯函数
        单测与离线兜底可用。若全部 DB 规则均未签署返回空列表，由调用方
        输出「待签署」态而不是给出档位。

        Returns:
            可参与判定的规则列表。
        """
        if self.source != "db":
            return list(self.rules)
        return [rule for rule in self.rules if rule.get("expert_signoff")]


def _normalize_rule(raw: Dict[str, Any]) -> Dict[str, Any]:
    """归一化规则行（DB 行或内置模板）为统一结构。

    Args:
        raw: 原始规则字典（含 triage_rule 列或模板键）。

    Returns:
        归一化规则字典（条件字段统一为 dict）。
    """
    conditions = raw.get("conditions") or {}
    if isinstance(conditions, str):
        try:
            conditions = json.loads(conditions)
        except Exception:  # noqa: BLE001 — 非法 JSON 按无条件下处理（不可判定）
            conditions = {}
    def _as_list(value: Any) -> List[str]:
        """把 JSONB 值规整为字符串列表（容错标量 / None）。"""
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:  # noqa: BLE001
                return [value]
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value if v is not None]
        return [str(value)]

    groups = conditions.get("any_of_groups") or []
    if isinstance(groups, str):
        try:
            groups = json.loads(groups)
        except Exception:  # noqa: BLE001
            groups = []
    return {
        "rule_id": str(raw.get("rule_id") or ""),
        "scene": str(raw.get("scene") or ""),
        "domain": str(raw.get("domain") or "child"),
        "title": str(raw.get("title") or ""),
        "age_min_months": int(raw.get("age_min_months") or 0),
        "age_max_months": int(
            raw.get("age_max_months") if raw.get("age_max_months") is not None else 9999
        ),
        "level": str(raw.get("level") or "yellow"),
        "priority": int(raw.get("priority") or 100),
        "basis": raw.get("basis") or "",
        "observations": _as_list(raw.get("observations")),
        "escalation_flags": _as_list(raw.get("escalation_flags")),
        "contraindications": _as_list(raw.get("contraindications")),
        "disclaimers": _as_list(raw.get("disclaimers")),
        "source_ref": raw.get("source_ref") or "",
        "version": int(raw.get("version") or 1),
        "expert_signoff": raw.get("expert_signoff"),
        "conditions": {
            "any_keywords": _as_list(conditions.get("any_keywords")),
            "all_keywords": _as_list(conditions.get("all_keywords")),
            "none_keywords": _as_list(conditions.get("none_keywords")),
            "any_of_groups": [list(map(str, g)) for g in groups if isinstance(g, (list, tuple))],
            "temp_min": conditions.get("temp_min"),
            "temp_max": conditions.get("temp_max"),
            "duration_min_hours": conditions.get("duration_min_hours"),
            "mental_state": conditions.get("mental_state"),
        },
    }


def load_rules(db: Optional[Session] = None, force_refresh: bool = False) -> TriageSnapshot:
    """加载分级规则快照（进程内缓存 60 秒；无库/空表回退内置模板）。

    Args:
        db: 数据库会话（None 时直接用内置模板）。
        force_refresh: True 时绕过缓存。

    Returns:
        TriageSnapshot 实例。

    Raises:
        TriageUnavailable: 快照装配异常且无内置兜底可用（正常不会发生）。
    """
    if not force_refresh:
        cached = cache.get(TRIAGE_CACHE_KEY)
        if cached:
            try:
                raw = json.loads(cached)
                return TriageSnapshot(
                    rules=raw.get("rules", []),
                    loaded_at=raw.get("loaded_at", 0.0),
                    rule_version=raw.get("rule_version", 1),
                    source=raw.get("source", "db"),
                    signed=int(raw.get("signed") or 0),
                )
            except Exception:  # noqa: BLE001 — 缓存损坏回源重建
                pass
    rules: List[Dict[str, Any]] = []
    source = "builtin"
    max_version = 1
    if db is not None:
        try:
            from ..models import TriageRule

            rows = db.query(TriageRule).filter(TriageRule.status == "active").all()
            for row in rows:
                rules.append(
                    _normalize_rule(
                        {
                            "rule_id": row.rule_id,
                            "scene": row.scene,
                            "domain": row.domain,
                            "title": row.title,
                            "age_min_months": row.age_min_months,
                            "age_max_months": row.age_max_months,
                            "conditions": row.conditions,
                            "level": row.level,
                            "priority": row.priority,
                            "basis": row.basis,
                            "observations": row.observations,
                            "escalation_flags": row.escalation_flags,
                            "contraindications": row.contraindications,
                            "disclaimers": row.disclaimers,
                            "source_ref": row.source_ref,
                            "version": row.version,
                            "expert_signoff": row.expert_signoff,
                        }
                    )
                )
                max_version = max(max_version, int(row.version or 1))
            if rules:
                source = "db"
        except Exception:  # noqa: BLE001 — 表未建/查询失败时回退内置模板
            rules = []
    if not rules:
        # 兜底：内置首批模板（保证「不得静默降级为纯模型回答」）
        rules = [_normalize_rule(dict(row)) for row in templates.TRIAGE_RULES]
        source = "builtin"
        max_version = max((r["version"] for r in rules), default=1)
    snapshot = TriageSnapshot(
        rules=rules,
        loaded_at=time.time(),
        rule_version=max_version,
        source=source,
        signed=sum(1 for rule in rules if rule.get("expert_signoff")),
    )
    try:
        cache.set(
            TRIAGE_CACHE_KEY,
            json.dumps(
                {
                    "rules": rules,
                    "loaded_at": snapshot.loaded_at,
                    "rule_version": snapshot.rule_version,
                    "source": snapshot.source,
                    "signed": snapshot.signed,
                },
                ensure_ascii=False,
            ),
            ttl_seconds=TRIAGE_CACHE_TTL,
        )
    except Exception:  # noqa: BLE001 — 缓存写入失败不影响本次判定
        pass
    return snapshot


# ---------------------------------------------------------------------------
# 信号提取
# ---------------------------------------------------------------------------
def _is_negated(question: str, keyword: str) -> bool:
    """判断关键词是否处在否定语境（「没有呕吐」不算命中）。

    Args:
        question: 问题原文。
        keyword: 待判定关键词。

    Returns:
        True 表示被否定（视作未命中）。
    """
    start = 0
    while True:
        idx = question.find(keyword, start)
        if idx < 0:
            return False
        prefix = question[max(0, idx - 3) : idx]
        if any(neg in prefix for neg in NEGATION_PREFIXES):
            start = idx + len(keyword)
            continue
        return False


def contains(question: str, keyword: str) -> bool:
    """判断问题是否命中关键词（含否定语境排除）。

    Args:
        question: 问题原文。
        keyword: 关键词。

    Returns:
        True 表示有效命中。
    """
    if not keyword or keyword not in question:
        return False
    return not _is_negated(question, keyword)


def extract_temperature(question: str) -> Optional[float]:
    """从问题中提取体温读数（℃）。

    支持三种常见写法：`38.5℃` / `38.5 度` / `38 度 5`，以及口语省略单位的
    `低烧 37.8`、`体温38.2`。

    Args:
        question: 问题原文。

    Returns:
        体温浮点数；未识别到返回 None。
    """
    half = _TEMP_HALF_RE.search(question)
    if half:
        whole = int(half.group(1))
        frac = int(half.group(2))
        value = whole + frac / 10.0
        if 34.0 <= value <= 43.0:
            return value
    for pattern in (_TEMP_RE, _TEMP_BARE_RE):
        match = pattern.search(question)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if 34.0 <= value <= 43.0:
            return value
    return None


def extract_age_months(question: str) -> Optional[int]:
    """从问题文本中推断儿童月龄（未绑定档案时使用，AC-RQ06-2）。

    支持「2岁」「2岁3个月」「24个月」「3月龄」「6个月大」等常见表达；
    同一句出现多个表达时优先「X岁Y个月」，其次「X岁」，最后「X个月」。

    Args:
        question: 问题原文。

    Returns:
        推断的月龄；无法推断或超出 0–72 月范围时返回 None。
    """
    if not question:
        return None
    match = _AGE_YEAR_MONTH_RE.search(question)
    if match:
        months = int(match.group(1)) * 12 + int(match.group(2))
        return months if 0 <= months <= 72 else None
    match = _AGE_YEAR_RE.search(question)
    if match:
        months = int(match.group(1)) * 12
        return months if 0 <= months <= 72 else None
    match = _AGE_MONTH_RE.search(question)
    if match:
        months = int(match.group(1))
        return months if 0 <= months <= 72 else None
    return None


def age_band_from_months(age_months: Optional[int]) -> Optional[str]:
    """把月龄映射为档案年龄段口径（与 child_profile.age_band 一致）。

    Args:
        age_months: 月龄（可为 None）。

    Returns:
        0-6m / 6-12m / 1-3y / 3-6y；月龄缺失返回 None。
    """
    if age_months is None:
        return None
    if age_months < 6:
        return "0-6m"
    if age_months < 12:
        return "6-12m"
    if age_months < 36:
        return "1-3y"
    return "3-6y"


def extract_duration_hours(question: str) -> Optional[float]:
    """从问题中提取症状持续小时数。

    Args:
        question: 问题原文。

    Returns:
        小时数；未识别到返回 None。
    """
    hours = _DURATION_HOUR_RE.search(question)
    if hours:
        return float(hours.group(1))
    days = _DURATION_DAY_RE.search(question)
    if days:
        return float(days.group(1)) * 24.0
    return None


def extract_mental_state(question: str) -> Optional[str]:
    """识别精神状态（normal / poor / None）。

    Args:
        question: 问题原文。

    Returns:
        "poor" / "normal" / None。
    """
    for keyword in POOR_STATE_KEYWORDS:
        if contains(question, keyword):
            return "poor"
    for keyword in NORMAL_STATE_KEYWORDS:
        if contains(question, keyword):
            return "normal"
    return None


def detect_scene(question: str, domain: str) -> Optional[str]:
    """判定问题属于哪一类分级模板（无命中返回 None）。

    领域隔离：儿童域只用儿科模板场景，宠物域只用宠物模板场景，避免
    「宠物发烧」误落儿科模板、「宝宝呕吐」误落宠物模板。

    Args:
        question: 问题原文。
        domain: child / pet。

    Returns:
        场景键或 None。
    """
    allowed = templates.SCENES_BY_DOMAIN.get(domain, templates.SCENES_BY_DOMAIN["child"])
    scores: Dict[str, int] = {}
    for scene in allowed:
        keywords = templates.SCENE_KEYWORDS.get(scene, [])
        score = sum(1 for kw in keywords if contains(question, kw))
        if score:
            scores[scene] = score
    if not scores:
        return None
    best = max(scores.values())
    for scene in templates.SCENE_ORDER:
        if scores.get(scene) == best:
            return scene
    return max(scores, key=lambda k: scores[k])


# ---------------------------------------------------------------------------
# 条件匹配
# ---------------------------------------------------------------------------
def _match_conditions(
    rule: Dict[str, Any],
    question: str,
    signals: Dict[str, Any],
    age_months: Optional[int],
    domain: str,
) -> bool:
    """判断单条规则条件是否命中。

    Args:
        rule: 归一化规则。
        question: 问题原文。
        signals: 提取到的信号（temperature / duration_hours / mental_state）。
        age_months: 当前档案月龄（无档案为 None）。
        domain: child / pet。

    Returns:
        True 表示命中。
    """
    conditions = rule["conditions"]
    # 领域隔离：规则 domain 为 child / pet / any
    rule_domain = rule["domain"]
    if rule_domain not in (domain, "any"):
        return False
    # 月龄区间（D-02）：有月龄（档案或问句推断）时严格落在区间内；
    # **无月龄时年龄受限规则一律不命中**，避免「2 岁低热」被 <3 月龄红档
    # 规则（priority=1000）无条件压过，违反 AC-RQ06-2。
    if rule["domain"] != "pet" and (rule["age_min_months"] > 0 or rule["age_max_months"] < 9999):
        if age_months is None:
            return False
        if age_months < rule["age_min_months"] or age_months > rule["age_max_months"]:
            return False
    # 关键词：any 至少一个；all 全部；none 出现即否决
    any_keywords = conditions["any_keywords"]
    all_keywords = conditions["all_keywords"]
    none_keywords = conditions["none_keywords"]
    if any_keywords and not any(contains(question, kw) for kw in any_keywords):
        return False
    if all_keywords and not all(contains(question, kw) for kw in all_keywords):
        return False
    if none_keywords and any(contains(question, kw) for kw in none_keywords):
        return False
    # 分组命中（OR 语义：任一分组内任一关键词命中即满足；用于
    # 「意识改变 / 呕吐 / 出血」这类并列就医指征，命中其一即够）
    groups = conditions["any_of_groups"]
    if groups and not any(
        any(contains(question, kw) for kw in group) for group in groups
    ):
        return False
    # 体温区间（左闭右开：temp_min ≤ t < temp_max）
    temp = signals.get("temperature")
    temp_min = conditions["temp_min"]
    temp_max = conditions["temp_max"]
    if temp_min is not None:
        if temp is None or float(temp) < float(temp_min):
            return False
    if temp_max is not None:
        if temp is None or float(temp) >= float(temp_max):
            return False
    # 持续时长下限
    duration_min = conditions["duration_min_hours"]
    if duration_min is not None:
        duration = signals.get("duration_hours")
        if duration is None or float(duration) < float(duration_min):
            return False
    # 精神状态（规则声明 normal 时，未识别到正常状态即不命中 → 保守不从绿）
    mental = conditions["mental_state"]
    if mental:
        detected = signals.get("mental_state")
        if detected != mental:
            return False
    return True


def _level_meta(level: str) -> Dict[str, str]:
    """返回档位元信息（缺省按 yellow 保守处理）。

    Args:
        level: red / yellow / green。

    Returns:
        档位元信息字典。
    """
    return dict(templates.LEVEL_META.get(level, templates.LEVEL_META["yellow"]))


def is_night_time(now: Optional[datetime] = None) -> bool:
    """判断当前是否处于夜间时段（22:00–6:00，上海时区）。

    Args:
        now: 时间（缺省取当前上海时间）。

    Returns:
        True 表示夜间。
    """
    settings = get_settings()
    current = (now or datetime.now(_TZ_SHANGHAI)).astimezone(_TZ_SHANGHAI)
    hour = current.hour
    start = settings.triage_night_start_hour
    end = settings.triage_night_end_hour
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end


def _night_notice(level: str, now: Optional[datetime] = None) -> Optional[str]:
    """按档位返回夜间提示文案（AC-RQ06-7）。

    Args:
        level: 档位。
        now: 判定时刻（缺省取当前上海时间；测试可注入）。

    Returns:
        夜间文案；非夜间返回 None。
    """
    if not is_night_time(now):
        return None
    return templates.NIGHT_NOTICE_GREEN if level == "green" else templates.NIGHT_NOTICE_NON_GREEN


def insufficient_result(scene: Optional[str], domain: str, reason: str) -> Dict[str, Any]:
    """构造「信息不足」态（不给档位，只给需要补充的关键信息）。

    Args:
        scene: 场景键（可能为 None）。
        domain: child / pet。
        reason: 说明。

    Returns:
        triage 字典（level=None，insufficient=True）。
    """
    return {
        "level": None,
        "level_label": "信息不足，暂不定档",
        "level_color": "neutral",
        "icon": "⚪",
        "scene": scene,
        "domain": domain,
        "insufficient": True,
        "reason": reason,
        "missing_info": DEFAULT_MISSING_INFO,
        "rule_hits": [],
        "basis": "",
        "observations": [],
        "escalation_flags": [],
        "contraindications": [],
        "disclaimers": list(templates.COMMON_DISCLAIMERS),
        "night_mode": False,
        "night_notice": None,
        "rule_version": 1,
        "decided_at": datetime.now(_TZ_SHANGHAI).isoformat(),
        "age_band_used": None,
    }


def publish_pending_result(scene: Optional[str], domain: str, total_rules: int) -> Dict[str, Any]:
    """构造「规则待签署」冻结态（D-07：未签署规则不得对外发布档位结论）。

    与「信息不足」区分：本态不是用户描述不足，而是内容治理门禁未通过，
    因此不给档位、不给规则命中，但保留通用就医提示，避免静默降级为
    纯模型回答（PRD §3.6.4 fail-safe 口径）。

    Args:
        scene: 命中的分级场景键。
        domain: child / pet。
        total_rules: 当前快照规则总数（用于后台排查展示）。

    Returns:
        triage 字典（level=None，publish_gated=True）。
    """
    result = insufficient_result(
        scene,
        domain,
        "分级规则尚未完成专家签署，暂不对外发布档位结论；如对情况判断不确定，请及时就医。",
    )
    result.update(
        {
            "level_label": "分级结论暂缓发布",
            "level_color": "neutral",
            "publish_gated": True,
            "generic_advice": "如对状况判断不确定，请及时就医或拨打急救电话。",
            "snapshot_source": "db",
            "rule_total": total_rules,
        }
    )
    return result


def unavailable_result(reason: str) -> Dict[str, Any]:
    """构造「分级服务暂不可用」态（AC-RQ06-4 失败语义）。

    失败时给出通用就医建议与渠道卡片提示，**不得静默降级为纯模型回答**。

    Args:
        reason: 不可用原因。

    Returns:
        triage 字典（level=None，unavailable=True）。
    """
    result = insufficient_result(None, "child", reason)
    result.update(
        {
            "level_label": "分级服务暂不可用",
            "level_color": "warning",
            "icon": "⚠️",
            "unavailable": True,
            "missing_info": [],
            "generic_advice": "如对状况判断不确定，请及时就医或拨打急救电话。",
        }
    )
    return result


def decide(
    question: str,
    domain: str = "child",
    age_months: Optional[int] = None,
    age_band: Optional[str] = None,
    species: Optional[str] = None,
    snapshot: Optional[TriageSnapshot] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """执行分级判定（纯函数，毫秒级；不访问数据库）。

    Args:
        question: 用户问题原文（风险已放行）。
        domain: child / pet。
        age_months: 档案月龄（儿童）。
        age_band: 档案年龄段（透传到输出，供信任条展示）。
        species: 宠物物种（cat / dog）。
        snapshot: 规则快照（None 时用内置模板）。
        now: 判定时刻（夜间口径与测试注入用）。

    Returns:
        triage 契约对象；未命中任何分级场景时返回 None（走常规问答）。

    Raises:
        TriageUnavailable: 快照不可用（调用方转「暂不可用」态，不得静默降级）。
    """
    snap = snapshot or load_rules(None)
    if not snap.usable():
        raise TriageUnavailable("分级规则快照为空")
    scene = detect_scene(question, domain)
    if scene is None:
        return None
    # D-02：未绑定档案时从问句推断月龄（「2 岁宝宝」等），缺失则年龄受限
    # 规则不命中，由「信息不足」态兜底，避免跨月龄误用高优先级红档规则。
    effective_age = age_months
    if effective_age is None and domain == "child":
        effective_age = extract_age_months(question)
    if age_band is None:
        age_band = age_band_from_months(effective_age)
    signals = {
        "temperature": extract_temperature(question),
        "duration_hours": extract_duration_hours(question),
        "mental_state": extract_mental_state(question),
    }
    # D-07：只允许已签署规则对外判定；DB 规则全部未签署时冻结档位发布
    rules = snap.decision_rules()
    if not rules:
        gated = publish_pending_result(scene, domain, len(snap.rules))
        gated.update(
            {
                "age_band_used": age_band,
                "age_months_used": effective_age,
                "age_source": "profile"
                if age_months is not None
                else ("question" if effective_age is not None else None),
                "signals": signals,
                "rule_version": snap.rule_version,
            }
        )
        return gated
    matched: List[Dict[str, Any]] = []
    for rule in rules:
        if rule["scene"] != scene:
            continue
        if _match_conditions(rule, question, signals, effective_age, domain):
            matched.append(rule)
    if not matched:
        return insufficient_result(scene, domain, "症状描述不足以判定档位，请补充关键信息")
    # 保守从严：先按规则优先级（作者显式设定的临床特异性），同级再取严重档。
    # 说明：不能只按档位排序——否则「通用保守默认档（yellow）」会压过
    # 「针对该情形的特异绿档」，导致 AC-RQ06-2 的「2 岁低热精神正常 → 🟢」
    # 永远不可达；红色硬规则已配 900+ 优先级，优先级排序同样满足
    # 「月龄越小越保守」。
    matched.sort(
        key=lambda r: (int(r["priority"]), LEVEL_RANK.get(r["level"], 0)), reverse=True
    )
    chosen = matched[0]
    level = chosen["level"] if chosen["level"] in LEVEL_RANK else "yellow"
    meta = _level_meta(level)
    disclaimers = list(dict.fromkeys(list(chosen["disclaimers"]) or templates.COMMON_DISCLAIMERS))
    if level == "green":
        for line in templates.GREEN_DISCLAIMERS:
            if line not in disclaimers:
                disclaimers.append(line)
    night_notice = _night_notice(level, now)

    def _public(rule: Dict[str, Any]) -> Dict[str, Any]:
        """规则对外摘要（不含内部条件原文）。"""
        return {
            "rule_id": rule["rule_id"],
            "title": rule["title"],
            "level": rule["level"],
            "priority": rule["priority"],
            "version": rule["version"],
            "source_ref": rule["source_ref"],
        }

    return {
        "level": level,
        "level_label": meta["label"],
        "level_color": meta["color"],
        "icon": meta["icon"],
        "action_hint": meta["action_hint"],
        "scene": scene,
        "domain": domain,
        "species": species,
        "insufficient": False,
        "unavailable": False,
        "reason": None,
        "missing_info": [],
        "rule_hits": [_public(rule) for rule in matched[:3]],
        "basis": chosen["basis"],
        "observations": list(chosen["observations"]),
        "escalation_flags": list(chosen["escalation_flags"]),
        "contraindications": list(chosen["contraindications"]),
        "disclaimers": disclaimers,
        "night_mode": night_notice is not None,
        "night_notice": night_notice,
        "rule_version": max((rule["version"] for rule in matched), default=snap.rule_version),
        "snapshot_source": snap.source,
        "decided_at": datetime.now(_TZ_SHANGHAI).isoformat(),
        "age_band_used": age_band,
        "age_months_used": effective_age,
        "age_source": "profile" if age_months is not None else ("question" if effective_age is not None else None),
        "signals": {
            "temperature": signals["temperature"],
            "duration_hours": signals["duration_hours"],
            "mental_state": signals["mental_state"],
        },
    }


def decide_for_session(
    db: Session,
    question: str,
    session: Any,
    child: Any = None,
    pet: Any = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """按问答会话绑定档案执行分级判定（含宠物月龄换算口径）。

    Args:
        db: 数据库会话。
        question: 问题原文。
        session: QaSession（提供 entry 与档案绑定）。
        child: ChildProfile 实例（已归属校验）。
        pet: PetProfile 实例（已归属校验）。
        now: 判定时刻。

    Returns:
        triage 契约对象或 None；规则快照异常时返回 unavailable 态
        （不抛异常，保证问答主流程不中断，但绝不放行为纯模型回答）。
    """
    domain = "pet" if (session.entry == "pet" or (pet is not None and child is None)) else "child"
    age_months = None
    age_band = None
    species = None
    if domain == "child" and child is not None:
        age_months = int(getattr(child, "age_months", 0) or 0)
        age_band = getattr(child, "age_band", None)
    if domain == "pet" and pet is not None:
        species = getattr(pet, "pet_type", None)
        age_band = getattr(pet, "age_band", None)
    try:
        snapshot = load_rules(db)
    except Exception as exc:  # noqa: BLE001 — 规则引擎不可用不得静默降级
        return unavailable_result(f"分级规则加载失败：{exc}")
    try:
        return decide(
            question,
            domain=domain,
            age_months=age_months,
            age_band=age_band,
            species=species,
            snapshot=snapshot,
            now=now,
        )
    except TriageUnavailable as exc:
        return unavailable_result(str(exc))
    except Exception as exc:  # noqa: BLE001 — 判定异常按不可用态处理
        return unavailable_result(f"分级判定异常：{exc}")


def scan_deterministic_phrases(text: str) -> List[str]:
    """扫描文本中的确定性结论表述（AC-RQ06-4 零容忍）。

    Args:
        text: 待扫描文本（拼接后的档位卡 + 正文）。

    Returns:
        命中的禁用表述列表（空列表表示通过）。
    """
    if not text:
        return []
    return [phrase for phrase in DETERMINISTIC_PHRASES if phrase in text]


def flatten_triage_text(triage: Dict[str, Any]) -> str:
    """把 triage 对象中的可读文案拼成一段用于合规扫描。

    Args:
        triage: triage 契约对象。

    Returns:
        拼接文本。
    """
    parts: List[str] = []
    for key in (
        "level_label",
        "basis",
        "action_hint",
        "night_notice",
        "generic_advice",
        "reason",
    ):
        value = triage.get(key)
        if value:
            parts.append(str(value))
    for key in (
        "observations",
        "escalation_flags",
        "contraindications",
        "disclaimers",
        "missing_info",
    ):
        parts.extend(str(item) for item in (triage.get(key) or []))
    return "\n".join(parts)


def build_contraindication_block(triage: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """把禁忌项装配为置顶 block（AC-RQ07-2：禁忌区置顶于正文之前）。

    Args:
        triage: triage 契约对象。

    Returns:
        block 字典（无禁忌项时返回 None）。
    """
    if not triage:
        return None
    items = [str(x) for x in (triage.get("contraindications") or [])]
    flags = [str(x) for x in (triage.get("escalation_flags") or [])]
    if not items and not flags:
        return None
    lines: List[str] = []
    if flags:
        lines.append("**出现任一情况请按 🔴 处理（立即就医）**")
        lines.extend(f"- {flag}" for flag in flags)
    if items:
        if lines:
            lines.append("")
        lines.append("**不要做**")
        lines.extend(f"- {item}" for item in items)
    return {
        "block_key": "triage_redflags",
        "title": "升级红旗与禁忌",
        "content": "\n".join(lines),
        "access_tier": "free",
        "immutable": False,
        "pinned": True,
        "source": "triage_engine",
    }


def rule_summary(snapshot: TriageSnapshot) -> Dict[str, Any]:
    """输出规则快照摘要（后台体检 / 门禁自检用）。

    Args:
        snapshot: 规则快照。

    Returns:
        {source, rule_version, total, by_scene, signed} 摘要。
    """
    by_scene: Dict[str, int] = {}
    signed = 0
    for rule in snapshot.rules:
        by_scene[rule["scene"]] = by_scene.get(rule["scene"], 0) + 1
        if rule.get("expert_signoff"):
            signed += 1
    return {
        "source": snapshot.source,
        "rule_version": snapshot.rule_version,
        "total": len(snapshot.rules),
        "by_scene": by_scene,
        "signed": signed,
    }


def worst_level(levels: List[Optional[str]]) -> Optional[str]:
    """取一组档位中最严重者（追问重判时判定「档位变化」用）。

    Args:
        levels: 档位列表。

    Returns:
        最严重档位；全空返回 None。
    """
    valid = [lv for lv in levels if lv in LEVEL_RANK]
    if not valid:
        return None
    return max(valid, key=lambda lv: LEVEL_RANK[lv])

# -*- coding: utf-8 -*-
"""每日一则小知识与「科普全书」服务。

数据来源与取用规则（对应需求「明确知识库的数据来源与取用规则」）：

1. **唯一数据源**：``kb_entry`` 表中 ``status='published'`` 且
   ``topic_key`` 以 ``daily_science_`` 开头的条目。``topic_key`` 后缀即业务
   分类（infant / toddler / pet / family），由运营在知识库后台维护。
2. **隔离演示与测试数据**：只读取 ``daily_science_*`` 前缀，不读取
   ``assessment_pool``、``risk_lexicon``、``sensitive_lexicon``，也不会把
   自动化测试探针条目混入每日推荐。
3. **每日稳定**：以北京时间（UTC+8）的日期为基准日，把候选条目按
   ``kb_id`` 的固定哈希排序形成一条固定循环队列，再用「日期序数 % 条目数」
   取一条。因此同一天所有用户、所有端拿到同一条；连续 N 天不重复
   （N = 当前候选条目数）。
4. **内容为空或查询失败**：本服务在无候选条目时返回 ``None``，由客户端
   展示内置通用提示；数据库异常向上抛出，由统一异常处理器转 500，客户端
   同样进入降级展示，不影响首页其他模块。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from ..models import KbEntry

# 北京时间固定偏移：避免依赖运行环境的 tzdata
CN_TZ = timezone(timedelta(hours=8))

# C 端科普专用主题键前缀（与运营侧约定，勿随意修改）
TOPIC_PREFIX = "daily_science_"

# 业务模块分类（顺序即前端 tab 顺序）
CATEGORIES: Sequence[Dict[str, str]] = (
    {"code": "infant", "label": "母婴", "hint": "0–12 月龄"},
    {"code": "toddler", "label": "幼儿", "hint": "1–6 岁"},
    {"code": "pet", "label": "宠物", "hint": "猫狗科学饲养"},
    {"code": "family", "label": "家庭共处", "hint": "孩子与宠物同处"},
)
CATEGORY_CODES = tuple(item["code"] for item in CATEGORIES)
CATEGORY_LABELS = {item["code"]: item["label"] for item in CATEGORIES}

# 固定哈希盐：变更会让历史日期的展示顺序整体重排，非必要不要改
PERMUTATION_SALT = "babe-kidscience-v1"

# 年龄段 / 宠物阶段的展示文案
AGE_LABELS = {
    "0-6m": "0–6 月",
    "6-12m": "6–12 月",
    "6-24m": "6–24 月",
    "0-12m": "0–12 月",
    "1-3y": "1–3 岁",
    "3-6y": "3–6 岁",
    "1-6y": "1–6 岁",
    "0-6y": "0–6 岁",
    "0-3y": "0–3 岁",
}
PET_STAGE_LABELS = {
    "junior": "幼年",
    "adult": "成年",
    "senior": "老年",
}

# 摘要截断长度（首页卡片展示用；详情页仍返回全文）
SUMMARY_LIMIT = 92


def today_cn() -> date:
    """获取北京时间「今天」的日期。

    Returns:
        北京时间（UTC+8）对应的 date 对象。
    """
    return datetime.now(CN_TZ).date()


def parse_day(value: Optional[str]) -> Optional[date]:
    """解析可选的日期参数（YYYY-MM-DD）。

    Args:
        value: 日期字符串；为空时返回 None，由调用方使用北京时间当天。

    Returns:
        解析成功的 date；入参为空时返回 None。

    Raises:
        ValueError: 字符串不是合法的 YYYY-MM-DD 日期。
    """
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def is_category(value: Optional[str]) -> bool:
    """判断分类编码是否合法。

    Args:
        value: 分类编码。

    Returns:
        True 表示属于 infant / toddler / pet / family。
    """
    return value in CATEGORY_CODES


def _category_of(entry: KbEntry) -> str:
    """从 topic_key 中解析业务分类。

    Args:
        entry: 知识条目。

    Returns:
        分类编码；无法识别时归入 infant，保证前端总能落到某个 tab。
    """
    suffix = str(entry.topic_key or "")[len(TOPIC_PREFIX):]
    return suffix if suffix in CATEGORY_CODES else CATEGORY_CODES[0]


def _stage_label(entry: KbEntry) -> Optional[str]:
    """生成适用阶段的展示文案。

    Args:
        entry: 知识条目。

    Returns:
        年龄段或宠物阶段文案；均未设置时返回 None。
    """
    if entry.age_band and entry.age_band in AGE_LABELS:
        return AGE_LABELS[entry.age_band]
    if entry.pet_stage and entry.pet_stage in PET_STAGE_LABELS:
        return PET_STAGE_LABELS[entry.pet_stage]
    return None


def _summary(content: str, limit: int = SUMMARY_LIMIT) -> str:
    """压缩正文为单行摘要。

    Args:
        content: 条目正文。
        limit: 最大字符数（含省略号）。

    Returns:
        去除换行后的摘要；超长时截断并补省略号。
    """
    compact = " ".join(str(content or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def to_public(entry: KbEntry) -> Dict[str, Any]:
    """把知识条目转为 C 端视图。

    Args:
        entry: KbEntry ORM 实例。

    Returns:
        供首页卡片与科普全书使用的字段字典。
    """
    category = _category_of(entry)
    return {
        "kb_id": entry.kb_id,
        "title": entry.title,
        "summary": _summary(entry.content),
        "content": entry.content,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, "科普"),
        "topic": entry.topic_category,
        "stage_label": _stage_label(entry),
        "preconditions": entry.preconditions,
        "source_level": entry.source_level,
        "source_name": entry.source_ref,
    }


def _query_entries(db: Session) -> List[KbEntry]:
    """查询全部已发布的 C 端科普条目。

    Args:
        db: 数据库会话。

    Returns:
        按业务分类顺序（母婴 → 幼儿 → 宠物 → 家庭共处）与 kb_id 排列的
        条目列表（空列表表示知识库暂无内容）。
    """
    rows = (
        db.query(KbEntry)
        .filter(
            KbEntry.status == "published",
            KbEntry.kb_kind.in_(("child", "pet")),
            KbEntry.topic_key.like(f"{TOPIC_PREFIX}%"),
        )
        .order_by(KbEntry.kb_id.asc())
        .all()
    )
    # 列表顺序与 tab 顺序一致（母婴 → 幼儿 → 宠物 → 家庭共处），
    # 避免「全部」首屏按编号字母序先出现家庭共处
    category_index = {code: index for index, code in enumerate(CATEGORY_CODES)}
    return sorted(rows, key=lambda row: (category_index.get(_category_of(row), 99), row.kb_id))


def list_entries(db: Session, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取科普全书条目列表。

    Args:
        db: 数据库会话。
        category: 分类编码；为空表示全部。

    Returns:
        条目视图列表；分类非法时返回空列表。
    """
    if category and not is_category(category):
        return []
    rows = _query_entries(db)
    if category:
        rows = [row for row in rows if _category_of(row) == category]
    return [to_public(row) for row in rows]


def count_entries(db: Session) -> int:
    """统计当前可用的科普条目总数（用于向客户端说明每日轮换周期）。

    Args:
        db: 数据库会话。

    Returns:
        已发布科普条目数量。
    """
    return len(_query_entries(db))


def category_counts(db: Session) -> List[Dict[str, Any]]:
    """统计各业务模块的条目数（供前端 tab 展示）。

    Args:
        db: 数据库会话。

    Returns:
        [{code, label, hint, count}]，顺序固定为母婴、幼儿、宠物、家庭共处。
    """
    rows = _query_entries(db)
    counts = {code: 0 for code in CATEGORY_CODES}
    for row in rows:
        counts[_category_of(row)] += 1
    return [
        {
            "code": item["code"],
            "label": item["label"],
            "hint": item["hint"],
            "count": counts[item["code"]],
        }
        for item in CATEGORIES
    ]


def _stable_order(rows: List[KbEntry]) -> List[KbEntry]:
    """按固定哈希生成稳定循环队列。

    Args:
        rows: 候选条目列表。

    Returns:
        重新排序后的新列表；入参为空时返回空列表。
    """
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{PERMUTATION_SALT}|{row.kb_id}".encode("utf-8")
        ).hexdigest(),
    )


def pick_daily(db: Session, day: date) -> Optional[KbEntry]:
    """按日期从知识库中稳定选取一条小知识。

    规则：固定哈希排序后，用「日期序数 % 条目数」取一条。同一天
    所有用户命中同一条；连续 N 天走完整队列后才会重复。

    Args:
        db: 数据库会话。
        day: 目标日期（北京时间口径）。

    Returns:
        选中的条目；知识库为空时返回 None。
    """
    rows = _query_entries(db)
    if not rows:
        return None
    ordered = _stable_order(rows)
    return ordered[day.toordinal() % len(ordered)]

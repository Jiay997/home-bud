# -*- coding: utf-8 -*-
"""专题包服务（RQ-13 育儿×宠物交叉主题包 / RQ-14 宠物行为内容线）。

口径（PRD §3.13 / §3.14 + F9.8）：

- 专题**独立计费，会员不含**（口径不变）；购买与权益复用 F9 订单 / 权益体系
  的既有字段（`product_code` 指向 `product` 表，价格 `price_micro`）；
- 交叉内容**必须育儿 + 宠物专家双签**（`review_child_signoff` +
  `review_pet_signoff`）方可上架（AC-RQ13-1）；
- **红旗前置**（AC-RQ13-2 / AC-RQ14-1）：`redflag_blocks` 结构固定在前部，
  抓咬伤主题包开篇即狂犬病暴露分级与「24 小时内就诊犬伤门诊」引导，
  安抚内容置于就医引导之后；
- 推广位挂在 F6 三面答结果页与相关问答尾部（不做弹窗打扰，AC-RQ13-3）。
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..compliance import ai_label as labels
from ..models import TopicPack

logger = logging.getLogger("jiaban.topic")

# 领域枚举
DOMAIN_CROSS = "cross"
DOMAIN_BEHAVIOR = "behavior"
DOMAIN_CHILD = "child"
DOMAIN_PET = "pet"
DOMAINS = (DOMAIN_CROSS, DOMAIN_BEHAVIOR, DOMAIN_CHILD, DOMAIN_PET)

# 行为内容线固定结构（AC-RQ14-1：① 与 ④ 位置固定在结构前部）
BEHAVIOR_STRUCTURE = (
    "physiological_check",
    "behavior_cause",
    "action_plan",
    "redflags",
)

# 结构标题（服务端下发，前端不得自造）
STRUCTURE_TITLES = {
    "physiological_check": "先排查生理原因",
    "behavior_cause": "行为成因科普",
    "action_plan": "分龄 / 分场景可执行方案",
    "redflags": "红旗：何时需要就医而不是训练",
}

# 交叉主题的强制前置提示（抓咬伤类）
BITE_REDFLAG_FIRST = (
    "**先看这一条**：动物致伤属狂犬病暴露风险，请按暴露分级处理并"
    "**24 小时内前往犬伤门诊 / 疾控中心**评估。以下安抚与共居内容在就医引导之后。"
)

# 免责（专题包同样带 AI 标识与免责）
TOPIC_DISCLAIMER = (
    "本专题为养育科普参考内容，不构成诊断或治疗建议；涉及疾病与用药请咨询专业人士。"
)


def _is_published_ok(row: TopicPack) -> bool:
    """判断专题包是否满足上架条件（双签 + 红旗前置）。

    Args:
        row: 专题包实例。

    Returns:
        True 表示满足上架条件。
    """
    if row.domain == DOMAIN_CROSS:
        if not (row.review_child_signoff and row.review_pet_signoff):
            return False
    elif not (row.review_child_signoff or row.review_pet_signoff):
        return False
    if row.redflag_first and not row.redflag_blocks:
        return False
    return True


def to_public(row: TopicPack) -> Dict[str, Any]:
    """把专题包转为对外视图（含红旗前置语义与标识）。

    Args:
        row: 专题包实例。

    Returns:
        专题包视图字典。
    """
    blocks: List[Dict[str, Any]] = []
    if row.redflag_first and row.redflag_blocks:
        blocks.extend(list(row.redflag_blocks))
    blocks.extend(list(row.content_blocks or []))
    return {
        "topic_code": row.topic_code,
        "title": row.title,
        "domain": row.domain,
        "summary": row.summary,
        "price_micro": int(row.price_micro or 0),
        "product_code": row.product_code,
        "redflag_first": bool(row.redflag_first),
        "redflag_blocks": list(row.redflag_blocks or []),
        "content_blocks": blocks,
        "member_included": False,
        "purchasable": row.status == "on",
        "review_child_signoff": row.review_child_signoff,
        "review_pet_signoff": row.review_pet_signoff,
        "disclaimer": TOPIC_DISCLAIMER,
        "ai_label": labels.ai_label("home"),
    }


def list_topics(db: Session, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出上架专题包。

    Args:
        db: 数据库会话。
        domain: 领域过滤。

    Returns:
        专题包视图列表。
    """
    query = db.query(TopicPack).filter(TopicPack.status == "on")
    if domain:
        query = query.filter(TopicPack.domain == domain)
    rows = query.order_by(TopicPack.id.asc()).all()
    return [to_public(row) for row in rows if _is_published_ok(row)]


def get_topic(db: Session, topic_code: str) -> Optional[Dict[str, Any]]:
    """读取单个专题包。

    Args:
        db: 数据库会话。
        topic_code: 专题编码。

    Returns:
        专题包视图；不存在或未上架返回 None。
    """
    row = (
        db.query(TopicPack)
        .filter(TopicPack.topic_code == topic_code, TopicPack.status == "on")
        .first()
    )
    if row is None:
        return None
    return to_public(row)


def recommend_for_entry(db: Session, entry: str, limit: int = 2) -> List[Dict[str, Any]]:
    """按入口推荐专题包（AC-RQ13-3 场景化推荐，不做弹窗）。

    Args:
        db: 数据库会话。
        entry: child / pet / family。
        limit: 条数。

    Returns:
        专题包视图列表（family 入口优先交叉主题）。
    """
    rows = (
        db.query(TopicPack)
        .filter(TopicPack.status == "on")
        .order_by(TopicPack.id.asc())
        .all()
    )
    ordered = rows
    if entry == "family":
        ordered = sorted(rows, key=lambda r: 0 if r.domain == DOMAIN_CROSS else 1)
    elif entry == "pet":
        ordered = sorted(
            rows, key=lambda r: 0 if r.domain in (DOMAIN_BEHAVIOR, DOMAIN_PET) else 1
        )
    elif entry == "child":
        ordered = sorted(rows, key=lambda r: 0 if r.domain in (DOMAIN_CHILD, DOMAIN_CROSS) else 1)
    out: List[Dict[str, Any]] = []
    for row in ordered:
        if not _is_published_ok(row):
            continue
        out.append(to_public(row))
        if len(out) >= limit:
            break
    return out


def validate_behavior_structure(content_blocks: List[Dict[str, Any]]) -> List[str]:
    """校验行为内容线结构合规（AC-RQ14-1）。

    Args:
        content_blocks: 内容块列表（每块含 key/title/content）。

    Returns:
        问题清单（空列表表示通过）。
    """
    keys = [str(block.get("key") or "") for block in content_blocks or []]
    issues: List[str] = []
    if keys[:1] != ["physiological_check"]:
        issues.append("首个内容块必须是「生理原因排查清单」")
    if "redflags" not in keys[:2]:
        issues.append("红旗（何时需要就医）必须位于结构前部（前两块之内）")
    return issues


def validate_publish(row: TopicPack) -> List[str]:
    """校验专题包上架条件（双签 + 红旗前置 + 行为结构）。

    Args:
        row: 专题包实例。

    Returns:
        问题清单（空列表表示可上架）。
    """
    issues: List[str] = []
    if row.domain == DOMAIN_CROSS:
        if not row.review_child_signoff:
            issues.append("交叉主题包缺少育儿专家会签（AC-RQ13-1）")
        if not row.review_pet_signoff:
            issues.append("交叉主题包缺少宠物专家会签（AC-RQ13-1）")
    if row.redflag_first and not row.redflag_blocks:
        issues.append("红旗前置已开启但未配置红旗内容（AC-RQ13-2 / AC-RQ14-1）")
    if row.domain == DOMAIN_BEHAVIOR:
        issues.extend(validate_behavior_structure(list(row.content_blocks or [])))
    return issues

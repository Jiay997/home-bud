# -*- coding: utf-8 -*-
"""轻工具服务（RQ-12）：知识资产前台化。

定位（PRD §3.12.1）：轻工具是「结构化内容 + 简单交互」，**不是新问答形态**，
不走多 Agent 调度（成本约束），不消耗问答额度（AC-RQ12-2）。

合规要点：

- 内容来自 F12 知识资产，100% 审核后上架（NFR-Q1），`kb_refs` 可追溯；
- 工具页带 AI 标识与免责（RQ-01 覆盖页扩展）；
- 配料表解析仅做成分科普，**不输出「能吃 / 不能吃」确定性结论**
  （AC-RQ12-4），附「以兽医师意见为准」；
- 首页四入口布局不变，轻工具收纳于「工具」次级入口（AC-RQ12-5）。
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..compliance import ai_label as labels
from ..models import ToolItem, ToolRunRecord

logger = logging.getLogger("jiaban.tool")

# 工具类型
TOOL_CHECKLIST = "checklist"
TOOL_PARSER = "parser"

# 免责文案（AC-RQ12-1 工具页必备）
TOOL_DISCLAIMER = (
    "以上为养育科普参考内容，不构成诊断或治疗建议；具体请咨询儿科医生或执业兽医。"
)

# 配料表解析的口径红线（AC-RQ12-4）
PARSER_CAVEAT = (
    "以下仅为成分科普与常见禁忌提示，**不判定能否喂食**；是否适合你家宠物，"
    "请以执业兽医师意见为准。"
)

# 确定性结论表述（命中即内容缺陷，发布前必须改掉）
DETERMINISTIC_TOOL_PHRASES = ("能吃", "不能吃", "可以吃", "不可以吃", "放心喂", "绝对安全")

# 兜底工具目录（数据库未播种时的可用性保障；内容与 seed 一致）
BUILTIN_TOOLS: List[Dict[str, Any]] = [
    {
        "tool_code": "tool_fever_checklist",
        "title": "发烧自查清单",
        "tool_type": TOOL_CHECKLIST,
        "domain": "child",
        "summary": "按顺序自查：体温读数、精神状态、饮水排尿、伴随症状",
        "kb_refs": ["kb_child_fever_01"],
        "sort_order": 10,
        "content": {
            "steps": [
                {"key": "temp", "title": "测体温并记录", "detail": "用体温计测量并记录读数与时间，不要用「摸额头」替代。"},
                {"key": "mental", "title": "看精神状态", "detail": "能否正常互动、是否嗜睡或叫不醒。"},
                {"key": "intake", "title": "记录饮水与排尿", "detail": "最近 6 小时的小便次数是判断脱水的关键。"},
                {"key": "symptoms", "title": "列出伴随症状", "detail": "皮疹、呕吐、呼吸急促、拒食、抽搐等。"},
            ],
            "escalation": [
                "3 月龄以下婴儿体温 ≥37.5℃",
                "出现抽搐、呼吸困难、叫不醒",
                "精神明显变差或尿量明显减少",
            ],
        },
    },
    {
        "tool_code": "tool_pet_behavior_checklist",
        "title": "宠物行为自查",
        "tool_type": TOOL_CHECKLIST,
        "domain": "pet",
        "summary": "拆家 / 乱尿 / 护食 / 分离焦虑：先排查生理与发情因素",
        "kb_refs": ["kb_pet_behavior_01"],
        "sort_order": 20,
        "content": {
            "steps": [
                {"key": "physical", "title": "先排查生理原因", "detail": "疼痛、泌尿系统问题、发情期、认知衰退都会表现为行为变化。"},
                {"key": "environment", "title": "核对环境变化", "detail": "搬家、新成员、作息改变是行为问题的常见诱因。"},
                {"key": "record", "title": "记录发生规律", "detail": "记录时间、地点、频率与前后事件，便于判断成因。"},
            ],
            "escalation": [
                "排尿困难或完全尿不出（尤其公猫）",
                "伴随呕吐、拒食或精神萎靡",
                "出现攻击性行为且频率上升",
            ],
        },
    },
    {
        "tool_code": "tool_pet_food_label",
        "title": "宠粮配料表解析",
        "tool_type": TOOL_PARSER,
        "domain": "pet",
        "summary": "按配料表顺序做成分科普与常见禁忌提示（不判定能否喂食）",
        "kb_refs": ["kb_pet_food_01"],
        "sort_order": 30,
        "content": {
            "how_to_read": [
                "配料按含量从高到低排列，前 3 位决定了主要成分结构。",
                "关注是否标注具体肉源与占比（如「鸡肉 30%」优于「肉类」）。",
                "关注添加剂项：防腐剂、诱食剂、着色剂的具体名称。",
            ],
            "common_hazards": [
                "巧克力 / 可可碱：犬猫常见中毒来源。",
                "洋葱与大蒜：可致红细胞损伤。",
                "葡萄与葡萄干：与急性肾损伤相关。",
                "木糖醇：可致低血糖与肝损伤。",
                "百合：对猫毒性高。",
            ],
            "caveat": PARSER_CAVEAT,
        },
    },
]


def _as_public(row: ToolItem) -> Dict[str, Any]:
    """把工具行转为对外视图（含标识与免责）。

    Args:
        row: 工具 ORM 实例。

    Returns:
        工具视图字典。
    """
    content = row.content or {}
    return {
        "tool_code": row.tool_code,
        "title": row.title,
        "tool_type": row.tool_type,
        "domain": row.domain,
        "summary": row.summary,
        "kb_refs": row.kb_refs or [],
        "content": content,
        "disclaimer": TOOL_DISCLAIMER,
        "ai_label": labels.ai_label("home"),
        "quota_cost": 0,
        "source": "db",
    }


def _as_public_builtin(raw: Dict[str, Any]) -> Dict[str, Any]:
    """内置工具目录的对外视图。

    Args:
        raw: 内置目字字典。

    Returns:
        工具视图字典。
    """
    return {
        "tool_code": raw["tool_code"],
        "title": raw["title"],
        "tool_type": raw["tool_type"],
        "domain": raw["domain"],
        "summary": raw["summary"],
        "kb_refs": raw["kb_refs"],
        "content": raw["content"],
        "disclaimer": TOOL_DISCLAIMER,
        "ai_label": labels.ai_label("home"),
        "quota_cost": 0,
        "source": "builtin",
    }


def list_tools(db: Session, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出已上架轻工具（数据库优先，空则回退内置目录）。

    Args:
        db: 数据库会话。
        domain: 领域过滤（child / pet；None 返回全部）。

    Returns:
        工具视图列表（按 sort_order 升序）。
    """
    query = db.query(ToolItem).filter(ToolItem.status == "on")
    if domain:
        query = query.filter(ToolItem.domain == domain)
    rows = query.order_by(ToolItem.sort_order.asc(), ToolItem.id.asc()).all()
    if rows:
        return [_as_public(row) for row in rows]
    items = [
        _as_public_builtin(raw)
        for raw in BUILTIN_TOOLS
        if not domain or raw["domain"] == domain
    ]
    return items


def get_tool(db: Session, tool_code: str) -> Optional[Dict[str, Any]]:
    """读取单个工具（含内容）。

    Args:
        db: 数据库会话。
        tool_code: 工具编码。

    Returns:
        工具视图；不存在返回 None。
    """
    row = None
    if db is not None:
        row = (
            db.query(ToolItem)
            .filter(ToolItem.tool_code == tool_code, ToolItem.status == "on")
            .first()
        )
    if row is not None:
        return _as_public(row)
    for raw in BUILTIN_TOOLS:
        if raw["tool_code"] == tool_code:
            return _as_public_builtin(raw)
    return None


def record_run(
    db: Session,
    user_id: int,
    tool_code: str,
    action: str = "view",
    completed_items: int = 0,
) -> ToolRunRecord:
    """记录工具使用（埋点 `tool_view` / `tool_complete` 的服务端留痕）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        tool_code: 工具编码。
        action: view / complete / to_qa / to_topic。
        completed_items: 完成项数。

    Returns:
        新建的使用记录（未 commit）。
    """
    row = ToolRunRecord(
        user_id=user_id,
        tool_code=tool_code,
        action=action,
        completed_items=int(completed_items or 0),
    )
    db.add(row)
    return row


def scan_deterministic(text: str) -> List[str]:
    """扫描工具内容中的确定性进食结论（AC-RQ12-4 零容忍）。

    Args:
        text: 待扫描文本。

    Returns:
        命中的表述列表（空列表表示通过）。
    """
    if not text:
        return []
    return [phrase for phrase in DETERMINISTIC_TOOL_PHRASES if phrase in text]


def validate_tool_content(content: Dict[str, Any]) -> List[str]:
    """校验工具内容合规（后台保存前调用）。

    Args:
        content: 工具内容字典。

    Returns:
        问题清单（空列表表示通过）。
    """
    import json

    text = json.dumps(content or {}, ensure_ascii=False)
    return [f"含确定性进食结论表述：{phrase}" for phrase in scan_deterministic(text)]

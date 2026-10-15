# -*- coding: utf-8 -*-
"""LangGraph 多智能体编排图定义。

图结构（StateGraph + TypedDict QAState）：
    START → risk_scan ──blocked──→ END
                │ok
                ▼
          intent_route → retrieve ──fan-out──→ {child_agent, pet_agent,
                                                safety_agent}（并行）
                                                │fan-in
                                                ▼
                                            aggregate → output_filter → END

- agent_outputs / node_meta 用 Annotated reducer 合并，保证并行节点
  写入不互相覆盖；
- 提供模块级编译缓存与 run_qa_graph 同步 invoke 入口。
"""
from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .nodes import (
    aggregate_node,
    child_agent_node,
    intent_route_node,
    merge_dicts,
    output_filter_node,
    pet_agent_node,
    retrieve_node,
    risk_scan_node,
    route_after_risk,
    safety_agent_node,
)


class QAState(TypedDict, total=False):
    """问答编排图状态。

    Attributes:
        request_id: 请求追踪 ID。
        session_id / session_uid: 问答会话主键与对外标识。
        client_request_id: 客户端幂等键。
        question: 用户问题原文（服务端解密后传入）。
        entry: 显式入口 child/pet/family。
        profile_bound: 是否绑定档案。
        age_band: 儿童年龄段（检索过滤）。
        species: 宠物物种 cat/dog（检索过滤）。
        risk_result: 风险判定结果（risk_scan 填充）。
        risk_pre_scanned: SSE 生成器已预扫标记（避免重复语义调用）。
        risk_event_no: 风险事件号（命中时）。
        channels: 危机干预渠道卡（命中时）。
        appeal_allowed: 是否允许申诉（硬类别 False）。
        lexicon_snapshot: 词库快照（output_filter 复用）。
        intent: 意图分类结果。
        has_child_entity / has_pet_entity: 意图实体归属。
        active_domains: 参与生成的领域。
        retrieved_docs: {domain: [知识条目]}。
        kb_hit: 是否有检索命中。
        render_order: 分节渲染顺序。
        sections: 聚合后的分节内容。
        agent_outputs: 各 Agent 输出（并行合并）。
        node_meta: 各节点调用元数据（并行合并，落 agent_call_log）。
        conflict_note: 跨域冲突提示。
        degraded_reason: 降级原因 safety_failed/agent_failed。
        status: 图执行状态 blocked/ok/done/degraded/failed。
        user_id: 用户主键。
        member_status: 会员状态（门控）。
        db: 数据库会话（运行上下文，非序列化）。
        session: QaSession ORM 实例（运行上下文）。
    """

    request_id: str
    session_id: int
    session_uid: str
    client_request_id: str
    question: str
    entry: str
    profile_bound: bool
    age_band: Optional[str]
    species: Optional[str]
    risk_result: Optional[dict]
    risk_pre_scanned: bool
    risk_event_no: Optional[str]
    channels: List[dict]
    appeal_allowed: bool
    lexicon_snapshot: Any
    intent: Optional[str]
    has_child_entity: bool
    has_pet_entity: bool
    active_domains: List[str]
    retrieved_docs: Dict[str, List[dict]]
    kb_hit: bool
    render_order: List[str]
    sections: Dict[str, dict]
    # 并行 fan-out 节点写入合并（reducer），避免同一 super-step 覆盖
    agent_outputs: Annotated[Dict[str, Any], merge_dicts]
    node_meta: Annotated[Dict[str, Any], merge_dicts]
    conflict_note: Optional[str]
    degraded_reason: Optional[str]
    status: str
    user_id: int
    member_status: str
    db: Any
    session: Any


def build_graph():
    """编译问答编排图（节点链见模块 docstring）。

    Returns:
        编译后的 LangGraph 可执行图（同步 invoke）。
    """
    g = StateGraph(QAState)
    g.add_node("risk_scan", risk_scan_node)
    g.add_node("intent_route", intent_route_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("child_agent", child_agent_node)
    g.add_node("pet_agent", pet_agent_node)
    g.add_node("safety_agent", safety_agent_node)
    g.add_node("aggregate", aggregate_node)
    g.add_node("output_filter", output_filter_node)

    g.add_edge(START, "risk_scan")
    # 风险命中：条件边直达 END（不出任何正文）
    g.add_conditional_edges(
        "risk_scan", route_after_risk, {"blocked": END, "ok": "intent_route"}
    )
    g.add_edge("intent_route", "retrieve")
    # fan-out：三 Agent 并行——从 retrieve 分别引出三条边，
    # LangGraph 将同一步内的多分支自动并行执行
    g.add_edge("retrieve", "child_agent")
    g.add_edge("retrieve", "pet_agent")
    g.add_edge("retrieve", "safety_agent")
    # fan-in：三条边汇入 aggregate，全部完成后进入聚合
    g.add_edge("child_agent", "aggregate")
    g.add_edge("pet_agent", "aggregate")
    g.add_edge("safety_agent", "aggregate")
    g.add_edge("aggregate", "output_filter")
    g.add_edge("output_filter", END)
    return g.compile()


# 模块级编译缓存（进程内复用）
_compiled = None


def run_qa_graph(initial_state: dict) -> dict:
    """同步执行问答编排图。

    Args:
        initial_state: 初始状态（QAState 允许的键的子集）。

    Returns:
        图执行完成后的最终状态。

    Raises:
        Exception: 图内部异常向上抛出（由 SSE 层捕获转 error 帧）。
    """
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled.invoke(initial_state)

# -*- coding: utf-8 -*-
"""LangGraph 节点实现模块。

节点链：risk_scan → intent_route → retrieve → {child_agent, pet_agent,
safety_agent 并行} → aggregate → output_filter。
- 所有节点均为同步函数，输入/输出为 state 增量 dict；
- agent_outputs / node_meta 通过 graph.py 中 QAState 的 Annotated reducer
  做字典合并，保证并行 fan-out 写入不互相覆盖；
- llm_mock=True 时 Agent 节点直接从检索结果组装模板 blocks（不调网关）；
- 单 Agent 超时由网关 timeout=12s 控制，失败输出 {"status": "fail"}。
"""
import time
from typing import Any, Dict, List, Optional

from ..core.config import get_settings
from ..llm.gateway import estimate_mock_tokens, extract_json, get_gateway, mock_latency_ms
from ..risk.service import RiskService
from ..services.retriever import Retriever
from .prompts import build_agent_messages, build_intent_messages

# 全局检索器（无状态可共享）
_retriever = Retriever()

# 分节标题（服务端下发，前端不得硬编码文案）
SECTION_TITLES: Dict[str, str] = {
    "safety": "安全提示",
    "child": "育儿建议",
    "pet": "宠物养护建议",
}

# 检索无命中时的转介提示文案
NO_HIT_NOTICE = (
    "当前未匹配到知识库条目，以下建议仅供参考，请结合实际情况并咨询专业人士。"
)

# safety 失败时的静态安全卡文案（immutable，禁出其余正文）
SAFETY_FALLBACK_TEXT = (
    "当前无法提供完整回答，请优先关注家人与宠物安全，必要时联系专业人士。"
)

# 冲突提示文案
CONFLICT_NOTE = "育儿与宠物侧建议存在差异，请结合实际谨慎采纳"


def merge_dicts(left: Optional[dict], right: Optional[dict]) -> dict:
    """Annotated reducer：字典浅合并（并行节点写入合并而非覆盖）。

    Args:
        left: 已有 channel 值。
        right: 本次节点返回的增量值。

    Returns:
        合并后的字典（right 优先）。
    """
    result: dict = dict(left or {})
    result.update(right or {})
    return result


def _active_domains(state: dict) -> List[str]:
    """按入口与意图实体确定参与生成的领域（SIM-18 修复：按入口显式分流）。

    规则（SIM 台账：pet 入口不得混入育儿分节）：
    - entry=pet → 仅 pet 域（不因意图实体 has_child_entity 追加 child，
      避免 pet 问答被 family 三 Agent 管线应答而出现「育儿建议」分节）；
    - entry=child → child 域，意图实体 has_pet_entity=True 可追加 pet
      （现状保持：育儿问题连带宠物话题）；
    - entry=family → 双域（child + pet，现状保持）。

    Args:
        state: 当前图状态。

    Returns:
        参与域列表（"child"/"pet"，顺序固定 child 在前）。
    """
    entry = state.get("entry") or "child"
    domains: List[str] = []
    if entry == "family":
        domains.append("child")
        domains.append("pet")
    elif entry == "pet":
        # 显式宠物入口固定只走 pet 域（safety 恒参与，图结构不变）
        domains.append("pet")
    else:
        # entry=child：child 域恒参与；意图识别出宠物实体时追加 pet（现状保持）
        domains.append("child")
        if state.get("has_pet_entity"):
            domains.append("pet")
    if not domains:
        domains.append("child")
    return domains


# ----------------------------------------------------------------------
# 节点：风险扫描
# ----------------------------------------------------------------------
def risk_scan_node(state: dict) -> dict:
    """risk_scan 节点：两级风险流水线，命中即置 blocked（条件边直 END）。

    state 含 risk_pre_scanned=True 时跳过（SSE 生成器已逐次预扫并放入
    risk_result，避免重复调用语义模型）；放行时 risk_result 一并回填
    供打标与落库使用，并附带词库快照供 output_filter 复用。

    Args:
        state: 当前图状态（含 db/session/question/user_id 等）。

    Returns:
        状态增量 dict：
        命中 → {"status": "blocked", "risk_result", "risk_event_no",
        "channels", "appeal_allowed"}；
        放行 → {"status": "ok", "risk_result"}；
        附加 {"lexicon_snapshot": 快照}。
    """
    db = state["db"]
    # 词库快照（60s 进程内缓存）随 state 下发，output_filter 不再回源
    snapshot = RiskService.load_snapshot(db)
    updates: dict = {"lexicon_snapshot": snapshot}
    # SSE 生成器已预扫（缓存命中路径也必须扫过）：直接沿用结果
    if state.get("risk_pre_scanned"):
        risk_result = state.get("risk_result") or {"blocked": False}
        if risk_result.get("blocked"):
            channels = RiskService.get_channels(db, risk_result.get("category_code"))
            updates.update(
                {
                    "status": "blocked",
                    "risk_result": risk_result,
                    "channels": channels,
                    # SIM-19 口径留证：appeal_allowed 仅软类别为 True。
                    # PRD《家伴-PRD_V1.5.md》§7.9.2 第 4 条：「高危类别是否永远不自动放行——
                    # 是，分两类：①硬类别（儿童虐待、孩子自伤/自杀想法、幼儿持续高烧惊厥、
                    # 儿童被动物抓咬伤/皮肤破损出血）永不自动放行，复核只能『维持拦截』或
                    # 『转人工线下引导』」；§7.9.3：「硬类别被放行的可能性——不存在，不提供
                    # 技术上的强制放行入口」；§7.9.4：「硬类别→不提供『继续提问』出口，只显示
                    # 渠道清单」。故硬类别（risk_result.hard=True）申诉入口不予放通。
                    "appeal_allowed": not risk_result.get("hard", False),
                }
            )
        else:
            updates["status"] = "ok"
        return updates
    # 未预扫（regenerate 等场景）：完整执行两级流水线
    scanned = RiskService.scan(
        db,
        state["question"],
        state["user_id"],
        session=state.get("session"),
        source_scene="qa",
    )
    risk_result = scanned["risk_result"]
    updates["risk_result"] = risk_result
    updates["risk_event_no"] = scanned["risk_event_no"]
    if risk_result.get("blocked"):
        updates.update(
            {
                "status": "blocked",
                "channels": RiskService.get_channels(db, risk_result.get("category_code")),
                # SIM-19 口径留证：同上，PRD §7.9.2/§7.9.3/§7.9.4——硬类别永不放行，
                # 仅软类别（严重抑郁、宠物中毒/大出血等）复核通过后可放行。
                "appeal_allowed": not risk_result.get("hard", False),
            }
        )
    else:
        updates["status"] = "ok"
    return updates


def route_after_risk(state: dict) -> str:
    """risk_scan 条件边路由：blocked 直达 END，否则进入意图路由。

    Args:
        state: 当前图状态。

    Returns:
        "blocked" 或 "ok"。
    """
    return "blocked" if state.get("status") == "blocked" else "ok"


# ----------------------------------------------------------------------
# 节点：意图路由
# ----------------------------------------------------------------------
def intent_route_node(state: dict) -> dict:
    """intent_route 节点：DeepSeek 意图分类（1s 超时），失败回退显式入口。

    回退规则：entry=child → has_child_entity=True；entry=pet →
    has_pet_entity=True；family → 双实体 True；intent 取 entry。

    Args:
        state: 当前图状态（含 entry/question）。

    Returns:
        {"intent", "has_child_entity", "has_pet_entity",
        "node_meta": {"intent_route": {...}}}。
    """
    settings = get_settings()
    gateway = get_gateway()
    entry = state.get("entry") or "child"
    try:
        resp = gateway.chat(
            build_intent_messages(state["question"]), purpose="intent", timeout=1.0
        )
        parsed = extract_json(resp["content"])
        if parsed is None:
            raise ValueError("intent response not json")
        intent = str(parsed.get("intent") or entry)
        has_child = bool(parsed.get("has_child_entity"))
        has_pet = bool(parsed.get("has_pet_entity"))
        # intent 一并写入观测 meta（随 agent_call_log.output_json 落库，
        # 供后台日志详情「意图」展示；真实/mock 两模式口径一致，仅观测字段）
        meta = {
            "status": "ok",
            "intent": intent,
            "has_child_entity": has_child,
            "has_pet_entity": has_pet,
            "latency_ms": resp["latency_ms"],
            "prompt_tokens": resp["prompt_tokens"],
            "completion_tokens": resp["completion_tokens"],
        }
    except Exception:  # noqa: BLE001 — 1s 超时/失败回退显式入口，不阻断主流程
        intent = entry
        has_child = entry in ("child", "family")
        has_pet = entry in ("pet", "family")
        meta = {"status": "fallback", "latency_ms": 0}
    return {
        "intent": intent,
        "has_child_entity": has_child,
        "has_pet_entity": has_pet,
        "node_meta": {"intent_route": meta},
    }


# ----------------------------------------------------------------------
# 节点：知识检索
# ----------------------------------------------------------------------
def retrieve_node(state: dict) -> dict:
    """retrieve 节点：按参与域执行关键词检索（每域 top8→前 5）。

    Args:
        state: 当前图状态（含 db/question/entry/age_band/species）。

    Returns:
        {"retrieved_docs": {domain: [doc...]}, "kb_hit": bool,
        "active_domains": [...], "node_meta": {"retrieve": {...}}}。
    """
    db = state["db"]
    start = time.monotonic()
    domains = _active_domains(state)
    age_band = state.get("age_band")
    species = state.get("species")
    retrieved: Dict[str, List[dict]] = {}
    for domain in domains:
        # 物种过滤仅对 pet 域生效
        sp = species if domain == "pet" else None
        retrieved[domain] = _retriever.retrieve(
            db, state["question"], domain, age_band=age_band, species=sp
        )["docs"]
    kb_hit = any(len(docs) > 0 for docs in retrieved.values())
    return {
        "retrieved_docs": retrieved,
        "kb_hit": kb_hit,
        "active_domains": domains,
        "node_meta": {
            "retrieve": {
                "status": "ok",
                "latency_ms": int((time.monotonic() - start) * 1000),
                "domains": domains,
            }
        },
    }


# ----------------------------------------------------------------------
# 节点：领域 Agent（child/pet/safety 共用实现）
# ----------------------------------------------------------------------
def _normalize_agent_output(agent_id: str, parsed: dict, docs: List[dict]) -> dict:
    """规整模型输出：blocks 归一 + evidence_ref 约束到检索 kb_id。

    Args:
        agent_id: Agent 标识。
        parsed: extract_json 解析出的 dict。
        docs: 该域检索命中条目（约束 evidence_ref 与无命中转介）。

    Returns:
        规整后的 agent 输出 dict（不含 status）。
    """
    raw_blocks = parsed.get("blocks") or []
    blocks: List[dict] = []
    for i, raw in enumerate(raw_blocks):
        if not isinstance(raw, dict):
            continue
        tier = raw.get("access_tier")
        blocks.append(
            {
                "block_key": str(raw.get("block_key") or f"b{i + 1}")[:32],
                "title": str(raw.get("title") or "建议")[:64],
                "content": str(raw.get("content") or ""),
                "access_tier": "block" if tier == "block" else "free",
            }
        )
    # 检索无命中：强制转介 + 前插提示 block
    professional = bool(parsed.get("professional_referral"))
    if not docs:
        professional = True
        blocks.insert(
            0,
            {
                "block_key": "referral_notice",
                "title": "专业咨询提示",
                "content": NO_HIT_NOTICE,
                "access_tier": "free",
            },
        )
    return {
        "title": str(parsed.get("title") or SECTION_TITLES.get(
            "child" if agent_id == "child_agent" else "pet" if agent_id == "pet_agent" else "safety"
        ))[:64],
        "topic_key": parsed.get("topic_key"),
        "stance": parsed.get("stance") or "support",
        "professional_referral": professional,
        # evidence_ref 必须来自本次检索命中的 kb_id（编造引用一律过滤）
        "evidence_ref": RiskService.evidence_filter(parsed.get("evidence_ref"), docs),
        "blocks": blocks,
    }


def _mock_agent_output(agent_id: str, state: dict, docs: List[dict]) -> dict:
    """mock 模式 Agent 输出：从检索结果组装模板 blocks。

    约定：第 1 条知识 → advice 块（content=知识内容）；
    第 2 个 block access_tier="block" 模拟会员门控内容。

    Args:
        agent_id: Agent 标识。
        state: 当前图状态（safety 判断实体归属用）。
        docs: 该域检索命中条目。

    Returns:
        规整后的 agent 输出 dict（不含 status）。
    """
    if agent_id == "safety_agent":
        # 双实体 → 儿童-宠物共处安全提示；否则通用安全提示（1-2 句）
        if state.get("has_child_entity") and state.get("has_pet_entity"):
            content = (
                "儿童与宠物共处安全提示：\n"
                "- 婴幼儿与宠物共处须有成人在场陪护；\n"
                "- 宠物食盆、猫砂盆放置在儿童不可触及区域；\n"
                "- 教育孩子不打扰宠物进食与睡眠、不拉拽尾巴。"
            )
        else:
            content = "通用家庭安全提示：保持看护人在场，危险物品妥善收纳，异常情况及时联系专业人士。"
        return {
            "title": SECTION_TITLES["safety"],
            "topic_key": "family_safety",
            "stance": "support",
            "professional_referral": False,
            "evidence_ref": [],
            "blocks": [
                {
                    "block_key": "safety_tip",
                    "title": SECTION_TITLES["safety"],
                    "content": content,
                    "access_tier": "free",
                }
            ],
        }
    # child/pet：模板组装
    if docs:
        first = docs[0]
        blocks = [
            {
                "block_key": "advice",
                "title": "建议要点",
                "content": first["content"],
                "access_tier": "free",
            }
        ]
        evidence = [first["kb_id"]]
        if len(docs) > 1:
            second = docs[1]
            # 第 2 个 block 模拟会员内容（门控裁剪在 SSE 组帧时执行）
            blocks.append(
                {
                    "block_key": "member_extra",
                    "title": "会员进阶方案",
                    "content": second["content"],
                    "access_tier": "block",
                }
            )
            evidence.append(second["kb_id"])
        return {
            "title": SECTION_TITLES["child" if agent_id == "child_agent" else "pet"],
            "topic_key": first.get("topic_key"),
            "stance": first.get("stance") or "support",
            "professional_referral": False,
            "evidence_ref": evidence,
            "blocks": blocks,
        }
    # 无命中：提示 + 转介
    return {
        "title": SECTION_TITLES["child" if agent_id == "child_agent" else "pet"],
        "topic_key": None,
        "stance": "support",
        "professional_referral": True,
        "evidence_ref": [],
        "blocks": [
            {
                "block_key": "referral_notice",
                "title": "专业咨询提示",
                "content": NO_HIT_NOTICE,
                "access_tier": "free",
            }
        ],
    }


def _run_agent_node(state: dict, agent_id: str, domain: Optional[str]) -> dict:
    """领域 Agent 通用实现：调 DeepSeek 生成结构化输出（12s 超时）。

    失败（网关异常/解析失败）输出 {"status": "fail"}，由 aggregate 降级；
    mock 模式直接组装模板，不调网关。

    Args:
        state: 当前图状态。
        agent_id: Agent 标识。
        domain: 领域（child/pet；safety 为 None 且恒参与）。

    Returns:
        {"agent_outputs": {agent_id: {...}}, "node_meta": {agent_id: {...}}}。
    """
    # 参与判断：非参与域直接 skip（不进 render_order、不计日志）
    if agent_id in ("child_agent", "pet_agent") and domain not in state.get(
        "active_domains", []
    ):
        return {"agent_outputs": {agent_id: {"status": "skip"}}}
    settings = get_settings()
    gateway = get_gateway()
    start = time.monotonic()
    docs = state.get("retrieved_docs", {}).get(domain or "", []) if domain else []
    prompt_tokens = completion_tokens = 0
    if settings.llm_mock:
        # mock：从检索结果组装模板 blocks（含会员门控模拟块）
        output = _mock_agent_output(agent_id, state, docs)
        status = "ok"
        # mock 口径补齐（AgentCallLog 耗时/Token 展示）：token 按输入/输出
        # 文本长度确定性估算；耗时按节点伪随机但可复现（真实路径走上游
        # usage 与实测耗时，逻辑不变）
        input_text = str(state.get("question") or "") + "".join(
            str(d.get("content") or "") for d in docs if isinstance(d, dict)
        )
        output_text = "".join(
            str(b.get("content") or "")
            for b in output.get("blocks", []) or []
            if isinstance(b, dict)
        )
        prompt_tokens = estimate_mock_tokens(len(input_text))
        completion_tokens = estimate_mock_tokens(len(output_text))
    else:
        try:
            ctx = {
                "entry": state.get("entry"),
                "age_band": state.get("age_band"),
                "species": state.get("species"),
            }
            resp = gateway.chat(
                build_agent_messages(agent_id, state["question"], docs, ctx),
                purpose=agent_id,
                timeout=30.0,  # 结构化 JSON 输出实测约 15-25s，12s 会频繁超时（PRD 8s 目标为优化后指标）
            )
            parsed = extract_json(resp["content"])
            if parsed is None:
                raise ValueError("agent response not json")
            output = _normalize_agent_output(agent_id, parsed, docs)
            status = "ok"
            prompt_tokens = resp["prompt_tokens"]
            completion_tokens = resp["completion_tokens"]
        except Exception:  # noqa: BLE001 — 单 Agent 失败按域降级，不拖垮整图
            output = {}
            status = "fail"
    latency = int((time.monotonic() - start) * 1000)
    if settings.llm_mock:
        # mock 口径补齐：耗时按节点伪随机但可复现（真实路径保留实测耗时）
        latency = mock_latency_ms(agent_id)
    return {
        "agent_outputs": {agent_id: {**output, "status": status}},
        "node_meta": {
            agent_id: {
                "status": status,
                "latency_ms": latency,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                # 观测补齐（评估 2026-10-12）：意图路由在 Agent 节点之前执行，
                # state.intent 此时必有值；写入各 Agent 行 node_meta 随
                # agent_call_log 落库，消除后台日志 Agent 行「意图=--」
                # （真实/mock 两模式口径一致，仅观测字段，不参与生成）
                "intent": state.get("intent"),
            }
        },
    }


def child_agent_node(state: dict) -> dict:
    """child_agent 节点：0-6 岁育儿科普生成（entry 涉儿童时参与）。

    Args:
        state: 当前图状态。

    Returns:
        状态增量（agent_outputs/node_meta）。
    """
    return _run_agent_node(state, "child_agent", "child")


def pet_agent_node(state: dict) -> dict:
    """pet_agent 节点：猫狗饲养行为科普生成（entry 涉宠物时参与）。

    Args:
        state: 当前图状态。

    Returns:
        状态增量（agent_outputs/node_meta）。
    """
    return _run_agent_node(state, "pet_agent", "pet")


def safety_agent_node(state: dict) -> dict:
    """safety_agent 节点：家庭安全提示（恒参与）。

    Args:
        state: 当前图状态。

    Returns:
        状态增量（agent_outputs/node_meta）。
    """
    return _run_agent_node(state, "safety_agent", None)


# ----------------------------------------------------------------------
# 节点：聚合（模板骨架，不调 LLM）
# ----------------------------------------------------------------------
def _degraded_section(section_key: str) -> dict:
    """构造失败节的降级分节。

    Args:
        section_key: 分节键（child/pet）。

    Returns:
        分节 dict（blocks 只含降级占位块）。
    """
    return {
        "section_key": section_key,
        "title": SECTION_TITLES[section_key],
        "blocks": [
            {
                "block_key": "degraded",
                "title": "本次部分内容未能生成",
                "content": "",
                "access_tier": "free",
                "status": "degraded",
            }
        ],
        "pinned": False,
        "immutable": False,
        "status": "degraded",
    }


def aggregate_node(state: dict) -> dict:
    """aggregate 节点：fan-in 聚合，实现降级矩阵与冲突比对（纯模板）。

    降级矩阵（架构 §5.2）：
    - safety fail：只出静态安全卡（immutable），隐藏 child/pet 正文，
      status=degraded，degraded_reason=safety_failed，不扣额度（由 SSE 层执行）；
    - child/pet 单侧 fail：失败节出降级占位块，其余正常，
      degraded_reason=agent_failed；
    - 全部 fail：无正文，status=failed；
    - 冲突比对：child 与 pet 同 topic_key 不同 stance → conflict_note。

    Args:
        state: 当前图状态（含 agent_outputs）。

    Returns:
        {"sections", "render_order", "status", "degraded_reason",
        "conflict_note"}。
    """
    outputs = state.get("agent_outputs", {})
    safety = outputs.get("safety_agent") or {"status": "fail"}
    child = outputs.get("child_agent") or {"status": "skip"}
    pet = outputs.get("pet_agent") or {"status": "skip"}
    # 实际参与的领域节（skip 视为未参与）
    child_involved = child.get("status") != "skip"
    pet_involved = pet.get("status") != "skip"

    # 全部参与域失败：无正文，status=failed
    domain_failures = [
        o.get("status")
        for o in (safety, child if child_involved else None, pet if pet_involved else None)
        if o is not None
    ]
    if all(s == "fail" for s in domain_failures):
        return {
            "sections": {},
            "render_order": [],
            "status": "failed",
            "degraded_reason": None,
            "conflict_note": None,
        }

    # safety 失败：只出静态安全卡（immutable），隐藏 child/pet 全部正文
    if safety.get("status") == "fail":
        static_card = {
            "section_key": "safety",
            "title": SECTION_TITLES["safety"],
            "blocks": [
                {
                    "block_key": "static_safety",
                    "title": SECTION_TITLES["safety"],
                    "content": SAFETY_FALLBACK_TEXT,
                    "access_tier": "free",
                }
            ],
            "pinned": True,
            "immutable": True,
            "status": "ok",
        }
        return {
            "sections": {"safety": static_card},
            "render_order": ["safety"],
            "status": "degraded",
            "degraded_reason": "safety_failed",
            "conflict_note": None,
        }

    # 正常聚合：safety 恒 pinned；失败领域节出降级块
    sections: Dict[str, dict] = {}
    render_order: List[str] = []
    degraded_any = False
    safety_section = {
        "section_key": "safety",
        "title": safety.get("title") or SECTION_TITLES["safety"],
        "blocks": safety.get("blocks", []),
        "pinned": True,
        "immutable": False,
        "status": "ok",
    }
    sections["safety"] = safety_section
    render_order.append("safety")
    for key, output, involved in (
        ("child", child, child_involved),
        ("pet", pet, pet_involved),
    ):
        if not involved:
            continue
        if output.get("status") == "fail":
            sections[key] = _degraded_section(key)
            degraded_any = True
        else:
            sections[key] = {
                "section_key": key,
                "title": output.get("title") or SECTION_TITLES[key],
                "blocks": output.get("blocks", []),
                "pinned": False,
                "immutable": False,
                "status": "ok",
            }
        render_order.append(key)

    # 冲突比对：child 与 pet 同 topic_key 且 stance 不同
    conflict_note = None
    if (
        child_involved
        and pet_involved
        and child.get("status") == "ok"
        and pet.get("status") == "ok"
        and child.get("topic_key")
        and child.get("topic_key") == pet.get("topic_key")
        and child.get("stance") != pet.get("stance")
    ):
        conflict_note = CONFLICT_NOTE

    return {
        "sections": sections,
        "render_order": render_order,
        "status": "degraded" if degraded_any else "done",
        "degraded_reason": "agent_failed" if degraded_any else None,
        "conflict_note": conflict_note,
    }


# ----------------------------------------------------------------------
# 节点：输出过滤
# ----------------------------------------------------------------------
def output_filter_node(state: dict) -> dict:
    """output_filter 节点：全部 block content 再过词库/正则，命中置空。

    Args:
        state: 当前图状态（含 sections/db）。

    Returns:
        {"sections": 过滤后的分节字典}。
    """
    db = state["db"]
    snapshot = state.get("lexicon_snapshot") or RiskService.load_snapshot(db)
    sections = state.get("sections", {})
    filtered = RiskService.filter_blocks_content(sections, snapshot)
    return {"sections": filtered}

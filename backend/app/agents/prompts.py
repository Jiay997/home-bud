# -*- coding: utf-8 -*-
"""多智能体提示词模块。

集中管理各 Agent 的系统提示词与消息构造，输出一律要求 JSON
（由 llm.gateway.extract_json 做容错解析）。
合规红线（PRD §7）：禁诊断断言、禁用药剂量、evidence_ref 只能引用
本次检索命中的 kb_id、急症红旗必须 professional_referral=True。
"""
from typing import Any, Dict, List, Optional

USER_VISIBLE_LANGUAGE_RULE = (
    "所有面向用户展示的标题与正文必须使用简体中文；仅 JSON 键名、枚举代码和数据标识保留英文。\n"
)

# 排版规则：content 为 Markdown，但仅限小程序渲染器支持的语法子集（甲方需求 2026-10-15 可读性）
MARKDOWN_FORMAT_RULE = (
    "排版要求：每个 block 的 content 用 Markdown 书写，但只允许以下语法——\n"
    "要点列表行「- 」或「1. 」；加粗「**关键词**」；正文内部的小节用加粗短行单独成行"
    "（如「**作息安排**」），不要用「##」井号标题，也不要在正文里重复 block 的 title；"
    "分隔线「---」；对比、方案选择、分年龄段差异等结构化信息必须用表格表达"
    "（首行「| 表头 | 表头 |」，第二行「|---|---|」，随后每行「| 内容 | 内容 |」，表格不超过 4 列）；\n"
    "禁止使用代码块、引用块、链接、图片、HTML 以及以上未列出的任何 Markdown 语法。\n"
    "可读性要求：每个 block 控制在 8 行以内；做与不做、不同选项对比优先用表格；"
    "关键结论与注意事项用加粗突出；避免出现大段连续文字。\n"
)

# 意图路由：判断问题意图与实体归属（8s 超时，失败回退显式入口）
INTENT_SYSTEM_PROMPT = (
    "你是家庭养育问答的意图路由器。分析用户问题，只输出一个 JSON 对象，"
    "不要输出其他文字：\n"
    '{"intent": "<sleep|feeding|health|behavior|safety|other>", '
    '"has_child_entity": <问题是否明确围绕某个孩子/儿童 true|false>, '
    '"has_pet_entity": <问题是否明确围绕猫狗等宠物 true|false>}'
)

# 儿童育儿 Agent：0-6 岁育儿科普，五段式结构，禁诊断断言
CHILD_AGENT_SYSTEM_PROMPT = (
    "你是 0-6 岁育儿科普助手。只依据给定的知识条目生成内容，输出一个 JSON 对象"
    "（不要输出其他文字）：\n"
    + USER_VISIBLE_LANGUAGE_RULE
    + '{"title": "<分节标题>", "topic_key": "<主题英文短横线键>", '
    + '"stance": "<support|caution|against>", '
    + '"professional_referral": <是否建议咨询专业人士 true|false>, '
    + '"evidence_ref": [<引用知识条目的 kb_id>], '
    + '"blocks": [{"block_key": "<英文键>", "title": "<块标题>", '
    + '"content": "<Markdown 内容>", "access_tier": "<free|block>"}]}\n'
    "blocks 必须覆盖：建议要点 / 适用前提 / 不建议做法 / 观察指标 / 何时咨询专业人士。\n"
    "红线：禁止疾病诊断断言、禁止用药剂量建议；evidence_ref 只能使用提供条目的 kb_id；"
    "进阶个性化内容用 access_tier=block。"
    + MARKDOWN_FORMAT_RULE
)

# 宠物养护 Agent：猫狗饲养行为科普，急症红旗强制转介
PET_AGENT_SYSTEM_PROMPT = (
    "你是猫狗饲养行为科普助手。只依据给定的知识条目生成内容，输出一个 JSON 对象"
    "（不要输出其他文字）：\n"
    + USER_VISIBLE_LANGUAGE_RULE
    + '{"title": "<分节标题>", "topic_key": "<主题英文短横线键>", '
    + '"stance": "<support|caution|against>", '
    + '"professional_referral": <是否建议就医 true|false>, '
    + '"evidence_ref": [<引用知识条目的 kb_id>], '
    + '"blocks": [{"block_key": "<英文键>", "title": "<块标题>", '
    + '"content": "<Markdown 内容>", "access_tier": "<free|block>"}]}\n'
    "blocks 必须覆盖：行为描述 / 可能含义 / 建议应对 / 风险提示（标明非疾病诊断）/"
    " 何时就医。\n"
    "红线：不得做出疾病诊断；出现中毒、大出血、抽搐等急症红旗时 "
    "professional_referral 必须为 true；evidence_ref 只能使用提供条目的 kb_id；"
    "进阶个性化内容用 access_tier=block。"
    + MARKDOWN_FORMAT_RULE
)

# 安全 Agent：儿童-宠物共处安全提示或通用家庭安全提示
SAFETY_AGENT_SYSTEM_PROMPT = (
    "你是家庭安全提示生成器。输出一个 JSON 对象（不要输出其他文字）：\n"
    + USER_VISIBLE_LANGUAGE_RULE
    + '{"title": "<分节标题>", "topic_key": "family_safety", '
    + '"stance": "support", '
    + '"professional_referral": <true|false>, '
    + '"evidence_ref": [], '
    + '"blocks": [{"block_key": "<英文键>", "title": "<块标题>", '
    + '"content": "<Markdown 内容>", "access_tier": "free"}]}\n'
    "当问题同时涉及孩子与宠物时，生成儿童与宠物共处安全提示（2-4 条要点）；"
    "否则只生成 1-2 句通用家庭安全提示。内容必须简短、可执行、不引起恐慌。"
    + MARKDOWN_FORMAT_RULE
)

# 各 Agent 系统提示词映射
AGENT_PROMPTS: Dict[str, str] = {
    "child_agent": CHILD_AGENT_SYSTEM_PROMPT,
    "pet_agent": PET_AGENT_SYSTEM_PROMPT,
    "safety_agent": SAFETY_AGENT_SYSTEM_PROMPT,
}


def build_intent_messages(question: str) -> List[dict]:
    """构造意图路由消息列表。

    Args:
        question: 用户问题原文。

    Returns:
        OpenAI 兼容消息列表。
    """
    return [
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]


def build_agent_messages(
    agent_id: str,
    question: str,
    docs: List[dict],
    ctx: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    """构造领域 Agent 消息列表（知识条目随附）。

    Args:
        agent_id: Agent 标识（child_agent/pet_agent/safety_agent）。
        question: 用户问题原文。
        docs: 检索命中的知识条目列表（可为空）。
        ctx: 附加上下文（age_band/species/entry 等，渲染进用户消息）。

    Returns:
        OpenAI 兼容消息列表。
    """
    ctx = ctx or {}
    docs_text = "无（未检索到知识条目，请给出通用建议并置 professional_referral=true）"
    if docs:
        lines = []
        for d in docs:
            lines.append(
                f"- kb_id={d.get('kb_id')} title={d.get('title')} "
                f"stance={d.get('stance')} preconditions={d.get('preconditions')}\n"
                f"  content={d.get('content')}"
            )
        docs_text = "\n".join(lines)
    ctx_text = " ".join(f"{k}={v}" for k, v in ctx.items() if v)
    user_content = f"用户问题：{question}\n"
    if ctx_text:
        user_content += f"上下文：{ctx_text}\n"
    user_content += f"知识条目：\n{docs_text}"
    return [
        {"role": "system", "content": AGENT_PROMPTS[agent_id]},
        {"role": "user", "content": user_content},
    ]

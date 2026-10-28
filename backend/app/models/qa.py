# -*- coding: utf-8 -*-
"""问答链路表模型。

对应数据模型文档 §3.3：qa_session / qa_answer_section / agent_call_log /
crisis_channel / risk_appeal。
"""
from sqlalchemy import BigInteger, Boolean, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgIdMixin, gen_uuid


class QaSession(Base, OrgIdMixin):
    """问答会话表（表 7）：留存 ≥6 个月。

    Attributes:
        session_uid: 对外会话标识（点查与重连）。
        question_text_enc: 问题原文密文（P0）。
        status: pending / streaming / done / blocked / degraded / failed / orphaned。
        render_order: 服务端决定的分节顺序（JSONB）。
    """

    __tablename__ = "qa_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    profile_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    profile_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    entry: Mapped[str] = mapped_column(String(16), nullable=False)  # child/pet/family
    question_text_enc: Mapped[str] = mapped_column(Text, nullable=False)
    char_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    degraded_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_member_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_retry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    risk_score_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    agents_involved: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    kb_refs: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    render_order: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    first_packet_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # --- V3.1 增量列（PRD §5.3.3 / §6.1）---
    # 输入形态预留（RQ-05 AC-RQ05-7）：text / voice / photo
    input_mode: Mapped[str] = mapped_column(
        String(8), nullable=False, default="text", server_default="text"
    )
    # 图片元数据摘要（张数 / 场景枚举 / 送检结果 / 删除时间；无 URL、无原图）
    photo_meta: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    # 分级决策结果快照（RQ-06 §6.3 契约扩展；不参与权重排序）
    triage: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    # 档位扁平列（历史/后台筛选用；None 表示未命中分级规则）
    triage_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # 触达归因（RQ-08 AC-RQ08-8）：提醒打开 → 提问的 trace 透传
    reminder_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_session_user_time", "user_id", "created_at"),
        Index("idx_session_status", "status", "created_at"),
        Index("idx_session_risk", "risk_level", "created_at"),
        Index("idx_qa_session_org_id", "org_id"),
        {"comment": "问答会话：≥6 个月，用户删除后保留元数据删正文"},
    )


class QaAnswerSection(Base):
    """回答分节表（表 8）：唯一索引 (session_id, section_key) 覆盖写。"""

    __tablename__ = "qa_answer_section"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(16), nullable=False)  # safety/child/pet
    section_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    blocks: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("session_id", "section_key", name="uk_section"),
        {"comment": "回答分节：safety 恒 pinned，immutable 为不可改写字段"},
    )


class AgentCallLog(Base):
    """Agent 调用日志表（表 9）：留存 ≥6 个月，输入摘要化不可还原。"""

    __tablename__ = "agent_call_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0.0")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    conflict_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_ref: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_micro: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_agentlog_session", "session_id", "agent_id"),
        Index("idx_agentlog_status_time", "status", "created_at"),
        Index("idx_agentlog_model", "provider", "model", "created_at"),
        {"comment": "Agent 调用日志：链路还原（PA-05）"},
    )


class CrisisChannel(Base):
    """危机干预渠道清单表（表 10）：号码未确认前必须留空，不得编造。

    V3.1 RQ-03 字段扩展（PRD §3.3.3 数据结构）：号码持久化点唯一（DR-26），
    超期未复核条目自动降为 `pending_review` 且前端不再展示号码
    （AC-RQ03-4）。`category_scope` 保留为「适用高危类别映射」
    （= PRD `applicable_categories[]`）。
    """

    __tablename__ = "crisis_channel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_scope: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    verified_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="placeholder", server_default="placeholder"
    )
    # --- V3.1 增量列（RQ-03 §3.3.3）---
    # 渠道类目：psychological / pediatric_emergency / pet_emergency /
    # police / minor_protection
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="psychological", server_default="psychological"
    )
    region: Mapped[str] = mapped_column(String(32), nullable=False, default="全国", server_default="全国")
    service_hours: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")

    __table_args__ = (
        Index("idx_channel_category_status", "category", "status"),
        {"comment": "危机渠道清单：号码唯一存放点（DR-26），含历史版本"},
    )


class RiskAppeal(Base):
    """误报申诉工单表（表 11）：上限 2 次，软类别放行 24h 有效。"""

    __tablename__ = "risk_appeal"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    appeal_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    risk_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    appeal_note_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_risk_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="appeal_submitted")
    review_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    review_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sla_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allow_expire_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    appeal_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_appeal_sla", "status", "sla_due_at"),
        {"comment": "误报申诉工单：合规留档 ≥3 年"},
    )

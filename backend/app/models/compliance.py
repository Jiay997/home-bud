# -*- coding: utf-8 -*-
"""合规与处置表模型。

对应数据模型文档 §3.7 / §3.9：risk_event / rights_request / content_report /
content_trace_task / sampling_check / content_audit_record / feedback。
"""
from sqlalchemy import BigInteger, Boolean, Index, Integer, SmallInteger, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, gen_uuid


class RiskEvent(Base):
    """高风险事件表（表 23）：user_id 存不可逆哈希；合规留档 ≥3 年。

    Attributes:
        body_emitted: 是否曾输出正文（命中后恒为 false）。
        response_bytes: 命中响应体字节数（应为 0）。
        reported: 上报标记（结论未录入前恒为 false，按钮置灰）。
    """

    __tablename__ = "risk_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    level: Mapped[str] = mapped_column(String(8), nullable=False)  # L1 / L2
    score_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rule_hit_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_scene: Mapped[str] = mapped_column(String(16), nullable=False, default="qa")
    body_emitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disposal_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duty_officer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reported_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retention_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="compliance", server_default="compliance"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_risk_event_time", "created_at"),
        Index("idx_risk_event_sla", "disposal_result", "sla_due_at"),
        {"comment": "高风险事件：复核 SLA 24h"},
    )


class RightsRequest(Base):
    """个人信息权利请求表（表 24）：六类请求，导出链接 24h 过期限一次下载。"""

    __tablename__ = "rights_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    reject_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sla_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_file_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    export_expire_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_downloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deletion_receipt: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    handled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_rights_sla", "status", "sla_due_at"),
        Index("idx_rights_export_expire", "export_expire_at"),
        {"comment": "权利请求：合规留档 ≥3 年"},
    )


class ContentReport(Base):
    """投诉举报处置表（表 25）：4 分类，涉未成年人单列加急。"""

    __tablename__ = "content_report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    involves_minor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sla_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    evidence: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    reported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    receipt_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    handled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_report_minor_sla", "involves_minor", "sla_due_at"),
        {"comment": "投诉举报：处置留痕 ≥3 年"},
    )


class ContentTraceTask(Base):
    """内容追溯处置表（表 26）：下架触发，闭环 7 个工作日。"""

    __tablename__ = "content_trace_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False)
    affected_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_reports: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disposal_level: Mapped[str | None] = mapped_column(String(4), nullable=True)  # A/B/C
    disposed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_trace_kb", "kb_id", "done_at"),
        {"comment": "内容追溯：闭环率 100% / 7 工作日"},
    )


class SamplingCheck(Base):
    """内容抽检表（表 27）：月度 30 条 / 每周 200 条 / 高危 100%。"""

    __tablename__ = "sampling_check"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(32), nullable=False)
    kb_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agent_call_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checker_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    veto_hits: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    detail: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContentAuditRecord(Base):
    """内容安全送检记录表（表 28）：超配额拒绝放行；送检副本回调后即删。"""

    __tablename__ = "content_audit_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scene: Mapped[str] = mapped_column(String(24), nullable=False)
    audit_result: Mapped[str] = mapped_column(String(16), nullable=False, default="reviewing")
    quota_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    callback_log: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Feedback(Base):
    """用户反馈表（表 29）：正文密文，附图 ≤3 张先过内容安全。"""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feedback_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    content_enc: Mapped[str] = mapped_column(Text, nullable=False)
    char_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linked_session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    linked_report_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    image_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    audit_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reply_template_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    replied_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_feedback_user_time", "user_id", "created_at"),
        {"comment": "用户反馈：回执默认 72h"},
    )

# -*- coding: utf-8 -*-
"""测评与报告表模型。

对应数据模型文档 §3.4：assessment / report。
测评 16 题（PRD §12.2 冻结口径），报告 13 区块固定顺序。
"""
from sqlalchemy import BigInteger, Boolean, Index, Integer, SmallInteger, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgIdMixin, gen_uuid


class Assessment(Base):
    """测评记录表（表 12）：断点续填 90 天，幂等提交。

    Attributes:
        answers: 作答明细 [{q_no, dimension, raw_score, skipped}]。
        dimension_scores: {ACT:{mean,band}, APP:..., ADP:..., EMO:...}。
        type_code: 四类占位名内部代码（对外命名未定稿）。
        has_draft: 断点标记（断点不进历史报告列表）。
    """

    __tablename__ = "assessment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assessment_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    profile_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    question_version: Mapped[str] = mapped_column(String(16), nullable=False, default="QB-1.0")
    answers: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    answered_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    dimension_scores: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    type_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    threshold_snapshot: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    has_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    submitted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft_expire_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_asmt_draft", "user_id", "has_draft", "draft_expire_at"),
        {"comment": "气质测评：PRD §12.2 冻结 16 题口径"},
    )


class Report(Base, OrgIdMixin):
    """报告表（表 13）：13 区块结构化内容 + access_tier_map 门控裁剪依据。"""

    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False, default="assessment")
    assessment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    question_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    content: Mapped[object] = mapped_column(JSONB, nullable=False)
    access_tier_map: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    image_rendered_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    image_meta: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    share_count: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "postgresql"), nullable=False, default=0)
    readonly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_report_user_time", "user_id", "created_at"),
        Index("idx_report_org_id", "org_id"),
        {"comment": "报告：会员到期转只读，长图免责≥15%"},
    )

# -*- coding: utf-8 -*-
"""知识库与词库表模型。

对应数据模型文档 §3.6：kb_entry / kb_review / lexicon_term / risk_rule_config。
"""
from sqlalchemy import BigInteger, Boolean, Index, Integer, SmallInteger, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, VersionMixin


class KbEntry(Base, VersionMixin):
    """知识库条目表（表 19）：五类口径，历史版本不物理删除。

    Attributes:
        kb_id: 业务编号（evidence_ref 引用对象）。
        kb_kind: child / pet / assessment_pool / risk_lexicon / sensitive_lexicon。
        preconditions: 适用前提（不得为空，一票否决项）。
        status: draft / pending_review / published / rejected / unpublished / merged。
        is_high_risk: 高危类目（100% 审核 + 合格线 90 分）。
    """

    __tablename__ = "kb_entry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    kb_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    topic_key: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_category: Mapped[str] = mapped_column(String(32), nullable=False)
    age_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pet_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    species: Mapped[str | None] = mapped_column(String(8), nullable=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    preconditions: Mapped[str] = mapped_column(Text, nullable=False)
    contraindications: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    stance: Mapped[str] = mapped_column(String(16), nullable=False, default="support")
    conclusion_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    # 来源等级（DR-10：权威指南 guide / 学术 academic / 机构 institution /
    # 媒体 media）；为空时按 source_type 映射推导，RQ-07 信任条据此渲染徽标
    source_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    license_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    license_expire_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    is_high_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    adjudication_ref: Mapped[str | None] = mapped_column(String(32), nullable=True)
    merged_into_kb_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vector_synced_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    embedding: Mapped[object | None] = mapped_column(JSONB, nullable=True)  # 降级向量存储（spec D6）

    __table_args__ = (
        Index("idx_kb_retrieval", "kb_kind", "domain", "status", "version"),
        Index("idx_kb_matrix", "domain", "topic_category", "age_band", "pet_stage", "species"),
        Index("idx_kb_review_due", "status", "next_review_due_at"),
        Index("idx_kb_source", "source_type", "license_expire_at"),
        {"comment": "知识库条目：长期留存含历史版本"},
    )


class KbReview(Base):
    """知识库审核记录表（表 20）：上线前 100% 审核。"""

    __tablename__ = "kb_review"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    kb_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kb_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_round: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewer_role: Mapped[str] = mapped_column(String(16), nullable=False)
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effort_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=6)
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    veto_hits: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_ref_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sign_off: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rollback_target_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_review_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_kbreview_kb", "kb_id", "version", "review_round"),
        {"comment": "知识库审核工单"},
    )


class LexiconTerm(Base, VersionMixin):
    """词库条目表（表 21）：词条密文存储，埋点只记哈希。

    Attributes:
        term_hash: 词条 SHA-256 哈希（唯一去重）。
        term_enc: 词条密文。
        lexicon_type: risk（高危）/ sensitive（敏感）。
        strategy: block / rewrite / degrade。
    """

    __tablename__ = "lexicon_term"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    term_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    term_enc: Mapped[str] = mapped_column(Text, nullable=False)
    lexicon_type: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False, default="block")
    threshold_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    effective: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_term_type_effective", "lexicon_type", "effective", "threshold_band"),
        {"comment": "风险词库：一级规则引擎热加载"},
    )


class RiskRuleConfig(Base, VersionMixin):
    """风险规则与阈值配置表（表 22）：变更后 1 分钟内全量生效。"""

    __tablename__ = "risk_rule_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    config_value: Mapped[object] = mapped_column(JSONB, nullable=False)
    effective_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

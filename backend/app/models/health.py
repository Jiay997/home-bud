# -*- coding: utf-8 -*-
"""健康档案表模型（甲方需求 2026-10-15）。

child_profile / pet_profile 多态关联（subject_type + subject_id，与
profile_photo 同口径，不建外键）；体检报告文件落在 upload_dir/health/，
行内只存相对路径；医生建议与复查说明加密落库。
复查提醒为纯应用内展示（列表页按 next_checkup_date 计算 due_status），
不接 agent、不做推送。
"""
from sqlalchemy import BigInteger, Date, Index, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgIdMixin, VersionMixin, gen_uuid


class HealthRecord(Base, OrgIdMixin, VersionMixin):
    """健康档案记录表（表 36）。

    Attributes:
        record_uid: 对外标识，防枚举（越权统一按"不存在"处理）。
        subject_type: child / pet。
        subject_id: 档案内部主键（出参一律用 subject_uid，不暴露）。
        subject_uid: 建档时快照的档案对外标识（档案删除后记录仍可展示）。
        notes_enc: 医生建议/备注（加密）。
        next_checkup_date / next_checkup_note_enc: 复查计划（提醒来源）。
        file_path: 报告文件相对路径（health/<uuid>.pdf|jpg），NULL 表示未上传。
        file_name: 上传时的原始文件名（仅展示用，不入盘）。
    """

    __tablename__ = "health_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(8), nullable=False)
    subject_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subject_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    record_date: Mapped[object] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    notes_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_checkup_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    next_checkup_note_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_health_user", "user_id", "deleted_at"),
        Index("idx_health_subject", "subject_type", "subject_id", "deleted_at"),
        Index("idx_health_next_checkup", "user_id", "next_checkup_date"),
        Index("idx_health_record_org_id", "org_id"),
        {"comment": "健康档案：体检报告与复查提醒（纯应用内）"},
    )

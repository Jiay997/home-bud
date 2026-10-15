# -*- coding: utf-8 -*-
"""个人笔记表模型（甲方需求 2026-10-15）。

用户整理经验心得的知识手册条目；正文 Fernet 加密落库，仅本人可见
（不公开分享）；乐观锁更新（version）防多端并发覆盖。
"""
from sqlalchemy import BigInteger, Index, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgIdMixin, VersionMixin, gen_uuid


class Note(Base, OrgIdMixin, VersionMixin):
    """个人笔记表（表 37）。

    Attributes:
        note_uid: 对外标识，防枚举（越权统一按"不存在"处理）。
        title: 笔记标题（明文，列表排序展示用；不涉敏感个人信息）。
        content_enc: 笔记正文 Markdown（加密）。
    """

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    note_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    content_enc: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_note_user", "user_id", "deleted_at"),
        Index("idx_note_org_id", "org_id"),
        {"comment": "个人笔记：Markdown 知识手册，正文加密+乐观锁"},
    )

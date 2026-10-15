# -*- coding: utf-8 -*-
"""ORM 基类与公共混入模块。

数据模型文档 V1.1 §1 设计原则落地：
- 乐观锁统一：可变实体带 version，更新走 WHERE version = ?
- org_id 预留：五张主表加列不加查询（PRD NFR-4.3 机构维度预留）
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类。"""

    pass


def gen_uuid() -> str:
    """生成对外暴露的 UUID 标识（防枚举）。

    Returns:
        uuid4 字符串。
    """
    return str(uuid.uuid4())


class VersionMixin:
    """乐观锁混入：可变实体统一携带 version 列。"""

    version = Column(Integer, nullable=False, default=1, server_default="1")


class OrgIdMixin:
    """机构维度预留混入（本期只加字段与索引位，不做机构功能）。

    数据模型文档附注：五张主表（app_user/child_profile/pet_profile/
    qa_session/report）各加 org_id 列 + idx_<表>_org_id 索引，
    暂不加入任何查询条件。
    """

    org_id = Column("org_id", Text, nullable=True, comment="机构预留：NULL 表示个人用户")

    @declared_attr
    def __table_args__(cls):  # noqa: N805 — SQLAlchemy 声明式约定
        """为混入表声明 org_id 索引（与业务索引合并）。

        Returns:
            索引元组（子类未定义 __table_args__ 时生效；
            已定义的子类自行合并——本项目中五表均已单独声明，见各自文件）。
        """
        return (Index(f"idx_{cls.__tablename__}_org_id", "org_id"),)


def utcnow() -> datetime:
    """当前 UTC 时间（时间传输一律 RFC3339/UTC，架构 §4.3）。

    Returns:
        带时区的 datetime。
    """
    from datetime import timezone

    return datetime.now(timezone.utc)

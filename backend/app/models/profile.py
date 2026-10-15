# -*- coding: utf-8 -*-
"""档案表模型。

对应数据模型文档 §3.2：child_profile / pet_profile。
儿童敏感字段（昵称/出生日期/过敏项）以 *_enc 密文列存储（P0），
排序与筛选只依赖派生列 age_months / age_band。
"""
from sqlalchemy import BigInteger, Boolean, Index, Integer, Numeric, SmallInteger, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OrgIdMixin, VersionMixin, gen_uuid


class ChildProfile(Base, OrgIdMixin, VersionMixin):
    """儿童档案表（表 4）。

    Attributes:
        profile_uid: 对外标识，防枚举（越权统一返回"不存在或无权限"）。
        nickname_enc / birth_date_enc / allergy_enc: P0 加密字段。
        age_months / age_band: 服务端计算的派生列，查询/筛选专用。
        status: active / disabled（撤回同意后置 disabled）。
        avatar_path: 头像文件相对路径（upload_dir 下），NULL 表示未设置。
    """

    __tablename__ = "child_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    nickname_enc: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date_enc: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    premature_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allergy_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    solid_food_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    age_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    age_band: Mapped[str] = mapped_column(String(16), nullable=False, default="1-3y")
    age_months_updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_child_user_status", "user_id", "status"),
        Index("idx_child_age_band", "user_id", "age_band"),
        Index("idx_child_profile_org_id", "org_id"),
        {"comment": "儿童档案：敏感字段加密+派生列，账号存续期+30天"},
    )


class PetProfile(Base, OrgIdMixin, VersionMixin):
    """宠物档案表（表 5）：MVP 仅猫狗。"""

    __tablename__ = "pet_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pet_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pet_type: Mapped[str] = mapped_column(String(16), nullable=False)  # cat / dog
    breed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    age_band: Mapped[str] = mapped_column(String(16), nullable=False, default="adult")
    neutered_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    main_food: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_pet_user", "user_id", "deleted_at"),
        Index("idx_pet_profile_org_id", "org_id"),
        {"comment": "宠物档案：MVP 仅 cat/dog"},
    )


class ProfilePhoto(Base, OrgIdMixin):
    """档案相册照片表（表 35）。

    child_profile / pet_profile 多态关联（profile_type + profile_id，
    与 current_context 同口径）；不建外键，删除档案时同事务软删并清理文件。
    文件以规范化 JPEG 落在 upload_dir，行内只存相对路径。

    Attributes:
        photo_uid: 对外标识，防枚举（越权统一返回"不存在或无权限"）。
        profile_type: child / pet。
        profile_id: 档案内部主键（出参一律用 profile_uid，不暴露）。
        file_path: 相对 upload_dir 的路径（形如 photos/<uuid>.jpg）。
    """

    __tablename__ = "profile_photo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    photo_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    profile_type: Mapped[str] = mapped_column(String(8), nullable=False)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_profile_photo_owner", "profile_type", "profile_id", "deleted_at"),
        Index("idx_profile_photo_user", "user_id", "deleted_at"),
        Index("idx_profile_photo_org_id", "org_id"),
        {"comment": "档案相册：多态关联 child/pet，软删 + 文件清理"},
    )

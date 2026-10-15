# -*- coding: utf-8 -*-
"""档案管理 API 模块。

提供儿童/宠物档案 CRUD、档案媒体（头像/相册）与当前问答对象设置：
- GET/POST /profiles/children                 儿童档案列表/新建（加密字段 + 派生列）
- PUT/DELETE /profiles/children/{profile_uid} 儿童档案更新（乐观锁）/删除（软删+回执）
- GET/POST /profiles/pets                     宠物档案列表/新建
- PUT/DELETE /profiles/pets/{pet_uid}         宠物档案更新（乐观锁）/软删
- PUT/DELETE /profiles/{kind}/{uid}/avatar    档案头像上传/移除（kind ∈ children|pets）
- GET/POST/DELETE /profiles/{kind}/{uid}/photos 相册列表/添加/删除（单张 multipart）
- POST /profiles/current                      设置当前问答对象（upsert）

业务口径：儿童昵称/出生日期/过敏项 Fernet 加密落库；age_months/age_band
服务端计算；新建儿童档案前置校验 child_personal_info 未撤回同意；
档案上限免费 3 个 / 会员 10 个；横向越权一律按 1002 不存在处理（防枚举）；
儿童档案媒体（头像/相册）同样受儿童同意门禁（1302）保护
（甲方需求 2026-10-14：档案可设置头像与相册，上限 30 张/档案）。
"""
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.crypto import decrypt_field, encrypt_field
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import (
    ApiError,
    ERR_CHILD_CONSENT,
    ERR_NOT_FOUND,
    ERR_OPTIMISTIC_LOCK,
    raise_err,
)
from ...db import get_db
from ...models import (
    AppUser,
    ChildProfile,
    ConsentRecord,
    CurrentContext,
    PetProfile,
    ProfilePhoto,
)
from ...models.base import utcnow
from ...services.media_store import (
    AVATAR_MAX_SIDE,
    PHOTO_MAX_SIDE,
    MediaValidationError,
    delete_file,
    save_image,
)

router = APIRouter(tags=["C端-档案"])

# 撤回同意后档案展示的脱敏昵称
MASKED_NICKNAME = "宝宝 A"

# 档案数量上限：免费 / 会员
PROFILE_LIMIT_FREE = 3
PROFILE_LIMIT_MEMBER = 10

# 儿童信息单独同意类型标识
CHILD_CONSENT_TYPE = "child_personal_info"

# 东八区时区（月龄按本地日历日计算）
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


# ---------- 请求体模型 ----------


class ChildCreateBody(BaseModel):
    """新建儿童档案请求体。

    Attributes:
        nickname: 昵称（加密存储）。
        birth_date: 出生日期 YYYY-MM-DD。
        gender: 性别（可选）。
        height_cm: 身高 cm（可选）。
        weight_kg: 体重 kg（可选）。
        premature_flag: 是否早产，默认 False。
        allergy: 过敏项列表（加密存储，可选）。
        solid_food_month: 辅食添加月龄（可选）。
    """

    nickname: str = Field(min_length=1, max_length=32, description="儿童昵称")
    birth_date: date = Field(description="出生日期 YYYY-MM-DD")
    gender: Optional[Literal["male", "female", "unknown"]] = Field(
        default=None, description="性别"
    )
    height_cm: Optional[float] = Field(default=None, ge=20, le=200, description="身高 cm")
    weight_kg: Optional[float] = Field(default=None, ge=1, le=100, description="体重 kg")
    premature_flag: bool = Field(default=False, description="是否早产")
    allergy: Optional[List[str]] = Field(default=None, description="过敏项列表")
    solid_food_month: Optional[int] = Field(
        default=None, ge=0, le=36, description="辅食添加月龄"
    )


class ChildUpdateBody(BaseModel):
    """更新儿童档案请求体（乐观锁）。

    Attributes:
        version: 客户端持有的版本号，与服务端不一致返回 1003。
        nickname: 昵称（可选，传则更新）。
        birth_date: 出生日期（可选，传则更新）。
        gender / height_cm / weight_kg / premature_flag / allergy / solid_food_month: 同新建。
    """

    version: int = Field(ge=1, description="乐观锁版本号")
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=32)
    birth_date: Optional[date] = None
    gender: Optional[Literal["male", "female", "unknown"]] = None
    height_cm: Optional[float] = Field(default=None, ge=20, le=200)
    weight_kg: Optional[float] = Field(default=None, ge=1, le=100)
    premature_flag: Optional[bool] = None
    allergy: Optional[List[str]] = None
    solid_food_month: Optional[int] = Field(default=None, ge=0, le=36)


class ChildDeleteBody(BaseModel):
    """删除儿童档案请求体。

    Attributes:
        mode: profile_only 仅删档案（保留问答历史）；purge_all 连同关联数据清除。
        confirm_nickname: 二次确认昵称，须与解密昵称一致。
    """

    mode: Literal["profile_only", "purge_all"] = Field(
        default="profile_only", description="删除模式"
    )
    confirm_nickname: str = Field(min_length=1, max_length=32, description="确认昵称")


class PetBody(BaseModel):
    """新建/更新宠物档案请求体。

    Attributes:
        pet_type: 宠物类型（cat / dog，MVP 仅猫狗）。
        breed: 品种（可选）。
        age_band: 年龄段（junior / adult / senior）。
        neutered_flag: 是否绝育（可选）。
        weight_kg: 体重 kg（可选）。
        main_food: 主粮（可选）。
    """

    pet_type: Literal["cat", "dog"] = Field(description="宠物类型")
    breed: Optional[str] = Field(default=None, max_length=64)
    age_band: Literal["junior", "adult", "senior"] = Field(default="adult")
    neutered_flag: Optional[bool] = None
    weight_kg: Optional[float] = Field(default=None, ge=0.1, le=100)
    main_food: Optional[str] = Field(default=None, max_length=64)


class PetUpdateBody(PetBody):
    """更新宠物档案请求体（在新建字段基础上追加乐观锁版本号）。

    Attributes:
        version: 客户端持有的版本号。
    """

    version: int = Field(ge=1, description="乐观锁版本号")


class CurrentContextBody(BaseModel):
    """设置当前问答对象请求体。

    Attributes:
        profile_type: 档案类型（child / pet）。
        profile_uid: 档案对外标识（服务端解析为内部 ID 存储，不暴露自增主键）。
    """

    profile_type: Literal["child", "pet"] = Field(description="档案类型")
    profile_uid: str = Field(min_length=1, max_length=64, description="档案对外标识")


# ---------- 内部工具函数 ----------


def _iso(value: Any) -> Optional[str]:
    """datetime 转 ISO8601 字符串。

    Args:
        value: datetime 实例或 None。

    Returns:
        ISO 字符串；入参为 None 时返回 None。
    """
    return value.isoformat() if value is not None else None


def is_user_member(user: AppUser) -> bool:
    """判定用户当前是否为有效会员。

    Args:
        user: 当前用户。

    Returns:
        member_status=member 且未到期（或未设置到期时间）返回 True。
    """
    if user.member_status != "member":
        return False
    return user.member_expire_at is None or user.member_expire_at > utcnow()


def profile_limit(user: AppUser) -> int:
    """按会员状态返回档案数量上限。

    Args:
        user: 当前用户。

    Returns:
        会员 10 个，免费 3 个。
    """
    return PROFILE_LIMIT_MEMBER if is_user_member(user) else PROFILE_LIMIT_FREE


def calc_age_months(birth: date, today: date) -> int:
    """按月差计算月龄（不足整月向下取整）。

    Args:
        birth: 出生日期。
        today: 计算基准日（东八区今天）。

    Returns:
        月龄整数（最小 0）。
    """
    months = (today.year - birth.year) * 12 + (today.month - birth.month)
    # 未到生日当日：减一个月
    if today.day < birth.day:
        months -= 1
    return max(0, months)


def calc_age_band(age_months: int) -> str:
    """按月龄映射年龄段（派生列口径）。

    Args:
        age_months: 月龄。

    Returns:
        0-6m / 6-12m / 1-3y / 3-6y 之一。
    """
    if age_months < 6:
        return "0-6m"
    if age_months < 12:
        return "6-12m"
    if age_months < 36:
        return "1-3y"
    return "3-6y"


def _shanghai_today() -> date:
    """获取东八区今天的日期。

    Returns:
        Asia/Shanghai 时区的当前日期。
    """
    return datetime.now(TZ_SHANGHAI).date()


def _media_url(rel_path: Optional[str]) -> Optional[str]:
    """媒体相对路径转对外 URL（静态挂载 /media）。

    Args:
        rel_path: 入库相对路径（如 "children/xxx.jpg"）。

    Returns:
        "/media/..." 前缀 URL；未设置时返回 None。
    """
    return f"/media/{rel_path}" if rel_path else None


def _child_view(profile: ChildProfile) -> Dict[str, Any]:
    """构造儿童档案展示视图（解密字段 + 派生列）。

    status=disabled（同意已撤回）时昵称脱敏为「宝宝 A」。

    Args:
        profile: 儿童档案 ORM 实例。

    Returns:
        展示字段字典。
    """
    nickname = decrypt_field(profile.nickname_enc)
    if profile.status == "disabled":
        # 撤回同意后停止展示真实昵称
        nickname = MASKED_NICKNAME
    birth = decrypt_field(profile.birth_date_enc)
    allergy: List[str] = []
    if profile.allergy_enc:
        try:
            allergy = json.loads(decrypt_field(profile.allergy_enc))
        except (ValueError, TypeError):
            # 脏数据兜底：解密失败按空列表展示
            allergy = []
    return {
        "profile_uid": profile.profile_uid,
        "nickname": nickname,
        "birth_date": birth,
        "gender": profile.gender,
        "height_cm": float(profile.height_cm) if profile.height_cm is not None else None,
        "weight_kg": float(profile.weight_kg) if profile.weight_kg is not None else None,
        "premature_flag": profile.premature_flag,
        "allergy": allergy,
        "solid_food_month": profile.solid_food_month,
        "age_months": profile.age_months,
        "age_band": profile.age_band,
        "status": profile.status,
        "version": profile.version,
        "created_at": _iso(profile.created_at),
        # disabled（同意已撤回）同口径停止展示：不返回头像 URL
        "avatar_url": _media_url(profile.avatar_path)
        if profile.status == "active"
        else None,
    }


def _pet_view(pet: PetProfile) -> Dict[str, Any]:
    """构造宠物档案展示视图（列表/新建/更新三处统一）。

    Args:
        pet: 宠物档案 ORM 实例。

    Returns:
        展示字段字典。
    """
    return {
        "pet_uid": pet.pet_uid,
        "pet_type": pet.pet_type,
        "breed": pet.breed,
        "age_band": pet.age_band,
        "neutered_flag": pet.neutered_flag,
        "weight_kg": float(pet.weight_kg) if pet.weight_kg is not None else None,
        "main_food": pet.main_food,
        "version": pet.version,
        "created_at": _iso(pet.created_at),
        "avatar_url": _media_url(pet.avatar_path),
    }


def _get_owned_child(
    db: Session, user: AppUser, profile_uid: str, for_update: bool = False
) -> ChildProfile:
    """按 uid 取当前用户的儿童档案（防枚举：越权与不存在统一 1002）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        profile_uid: 档案对外标识。
        for_update: True 时加行锁（SELECT ... FOR UPDATE），用于乐观锁
            更新场景——并发双写时后到事务阻塞至前序提交后重读，
            使其读到新版本而触发 1003，避免丢失更新。

    Returns:
        儿童档案 ORM 实例。

    Raises:
        ApiError: 1002 不存在、不属于当前用户或已删除。
    """
    query = db.query(ChildProfile).filter(ChildProfile.profile_uid == profile_uid)
    if for_update:
        query = query.with_for_update()
    profile = query.first()
    # 不区分「不存在」与「无权限」，防止 uid 枚举
    if profile is None or profile.user_id != user.id or profile.deleted_at is not None:
        raise_err(ERR_NOT_FOUND)
    return profile


def _get_owned_pet(
    db: Session, user: AppUser, pet_uid: str, for_update: bool = False
) -> PetProfile:
    """按 uid 取当前用户的宠物档案（防枚举：越权与不存在统一 1002）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        pet_uid: 宠物对外标识。
        for_update: True 时加行锁（同儿童档案更新并发兜底）。

    Returns:
        宠物档案 ORM 实例。

    Raises:
        ApiError: 1002 不存在、不属于当前用户或已删除。
    """
    query = db.query(PetProfile).filter(PetProfile.pet_uid == pet_uid)
    if for_update:
        query = query.with_for_update()
    pet = query.first()
    if pet is None or pet.user_id != user.id or pet.deleted_at is not None:
        raise_err(ERR_NOT_FOUND)
    return pet


def _check_profile_quota(db: Session, user: AppUser, model, deleted_col) -> None:
    """校验档案数量上限（免费 3 / 会员 10）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        model: ChildProfile 或 PetProfile 模型类。
        deleted_col: 软删标记列（deleted_at）。

    Returns:
        None。

    Raises:
        ApiError: 1006 档案数量已达上限（HTTP 409）。
    """
    count = (
        db.query(func.count(model.id))
        .filter(model.user_id == user.id, deleted_col.is_(None))
        .scalar()
        or 0
    )
    if count >= profile_limit(user):
        raise ApiError(code=1006, message="档案数量已达上限", http_status=409)


def _require_child_consent(db: Session, user_id: int) -> None:
    """前置校验：必须存在 child_personal_info 且未撤回的同意记录。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        None。

    Raises:
        ApiError: 1302 需先完成儿童信息单独同意。
    """
    active = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == CHILD_CONSENT_TYPE,
            ConsentRecord.withdraw_at.is_(None),
        )
        .first()
    )
    if active is None:
        raise_err(ERR_CHILD_CONSENT)


# ---------- 档案媒体辅助（头像 / 相册） ----------


def _resolve_media_target(
    db: Session, user: AppUser, kind: str, uid: str
) -> Tuple[str, Any, str]:
    """解析档案媒体操作目标（kind 路径段 → 档案实例）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        kind: "children" 或 "pets"（路由路径段）。
        uid: 档案对外标识。

    Returns:
        (profile_type, profile, subdir)：profile_type ∈ {"child","pet"}，
        profile 为档案 ORM 实例，subdir 为媒体子目录名。

    Raises:
        ApiError: 1002 不存在、越权或已删除（防枚举）。
    """
    if kind == "children":
        return "child", _get_owned_child(db, user, uid), "children"
    return "pet", _get_owned_pet(db, user, uid), "pets"


def _guard_child_media_consent(db: Session, user: AppUser, profile_type: str) -> None:
    """儿童档案媒体访问前置门禁（宠物无此限制）。

    撤回儿童信息同意后档案置 disabled（停止展示与使用），头像/相册
    一并停止读写；同意未撤回时直接返回。

    Args:
        db: 数据库会话。
        user: 当前用户。
        profile_type: "child" 或 "pet"。

    Raises:
        ApiError: 1302 儿童信息单独同意缺失或已撤回。
    """
    if profile_type == "child":
        _require_child_consent(db, user.id)


def _save_upload_or_raise(
    data: bytes, subdir: str, max_side: int
) -> Tuple[str, int, int, int]:
    """规范化保存上传图片（校验失败统一映射 1001）。

    Args:
        data: 原始上传字节。
        subdir: 媒体子目录（children / pets）。
        max_side: 规范化最长边。

    Returns:
        (相对路径, 宽, 高, 字节数)。

    Raises:
        ApiError: 1001 图片格式不支持或文件过大（422）。
    """
    try:
        return save_image(data, subdir, max_side)
    except MediaValidationError:
        raise ApiError(
            code=1001,
            message="图片格式不支持或文件过大，请换一张试试。",
            http_status=422,
        ) from None


def _photo_view(row: ProfilePhoto) -> Dict[str, Any]:
    """构造相册照片展示视图。

    Args:
        row: 照片 ORM 实例。

    Returns:
        展示字段字典（含对外 URL）。
    """
    return {
        "photo_uid": row.photo_uid,
        "url": _media_url(row.file_path),
        "size": row.file_size,
        "created_at": _iso(row.created_at),
    }


def _purge_profile_media(db: Session, profile_type: str, profile_id: int) -> int:
    """清理档案媒体（删除档案时调用）：软删照片行 + 删除文件。

    Args:
        db: 数据库会话。
        profile_type: "child" 或 "pet"。
        profile_id: 档案内部主键。

    Returns:
        本次清理的照片行数（幂等：无照片时返回 0）。
    """
    rows = (
        db.query(ProfilePhoto)
        .filter(
            ProfilePhoto.profile_type == profile_type,
            ProfilePhoto.profile_id == profile_id,
            ProfilePhoto.deleted_at.is_(None),
        )
        .all()
    )
    now = utcnow()
    for row in rows:
        row.deleted_at = now
        delete_file(row.file_path)
    return len(rows)


# ---------- 儿童档案路由 ----------


@router.get("/profiles/children", summary="儿童档案列表", description="解密展示，不含已删除；disabled 档案昵称脱敏")
def list_children(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户儿童档案列表（不含已删除，解密展示）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"children": [档案视图...]}，disabled 档案昵称脱敏。
    """
    profiles = (
        db.query(ChildProfile)
        .filter(ChildProfile.user_id == user.id, ChildProfile.deleted_at.is_(None))
        .order_by(ChildProfile.id.asc())
        .all()
    )
    return ok({"children": [_child_view(p) for p in profiles]})


@router.post("/profiles/children", summary="新建儿童档案", description="前置校验儿童信息同意与数量上限，加密落库并计算派生列")
def create_child(
    body: ChildCreateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """新建儿童档案：前置校验儿童信息同意 + 数量上限，加密落库并计算派生列。

    Args:
        body: 档案字段。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：新建档案视图（含 age_months/age_band/version）。

    Raises:
        ApiError: 1302 未完成儿童信息单独同意；1006 档案数量已达上限；
                  1901 落库异常由全局处理器兜底。
    """
    # 合规前置：儿童信息单独同意未撤回
    _require_child_consent(db, user.id)
    # 数量上限：免费 3 / 会员 10
    _check_profile_quota(db, user, ChildProfile, ChildProfile.deleted_at)

    today = _shanghai_today()
    age_months = calc_age_months(body.birth_date, today)
    profile = ChildProfile(
        user_id=user.id,
        # P0 敏感字段加密落库：昵称/出生日期/过敏项
        nickname_enc=encrypt_field(body.nickname),
        birth_date_enc=encrypt_field(body.birth_date.isoformat()),
        gender=body.gender,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        premature_flag=body.premature_flag,
        allergy_enc=encrypt_field(json.dumps(body.allergy or [], ensure_ascii=False))
        if body.allergy
        else None,
        solid_food_month=body.solid_food_month,
        age_months=age_months,
        age_band=calc_age_band(age_months),
        status="active",
    )
    db.add(profile)
    db.flush()
    return ok(_child_view(profile))


@router.put("/profiles/children/{profile_uid}", summary="更新儿童档案", description="乐观锁更新，成功后 version+1 并重算月龄档位")
def update_child(
    profile_uid: str,
    body: ChildUpdateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """更新儿童档案（乐观锁）：版本不一致返回 1003，成功后 version+1 并重算派生列。

    Args:
        profile_uid: 档案对外标识。
        body: 更新字段 + version。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：更新后的档案视图。

    Raises:
        ApiError: 1002 不存在或越权；1003 乐观锁冲突。
    """
    profile = _get_owned_child(db, user, profile_uid, for_update=True)
    if profile.version != body.version:
        raise_err(ERR_OPTIMISTIC_LOCK)

    # 仅更新客户端显式传入的字段
    if body.nickname is not None:
        profile.nickname_enc = encrypt_field(body.nickname)
    if body.birth_date is not None:
        profile.birth_date_enc = encrypt_field(body.birth_date.isoformat())
    if body.gender is not None:
        profile.gender = body.gender
    if body.height_cm is not None:
        profile.height_cm = body.height_cm
    if body.weight_kg is not None:
        profile.weight_kg = body.weight_kg
    if body.premature_flag is not None:
        profile.premature_flag = body.premature_flag
    if body.allergy is not None:
        profile.allergy_enc = (
            encrypt_field(json.dumps(body.allergy, ensure_ascii=False))
            if body.allergy
            else None
        )
    if body.solid_food_month is not None:
        profile.solid_food_month = body.solid_food_month

    # 重算派生列并递增版本
    birth = date.fromisoformat(decrypt_field(profile.birth_date_enc))
    profile.age_months = calc_age_months(birth, _shanghai_today())
    profile.age_band = calc_age_band(profile.age_months)
    profile.age_months_updated_at = utcnow()
    profile.version += 1
    db.flush()
    return ok(_child_view(profile))


@router.delete("/profiles/children/{profile_uid}", summary="删除儿童档案", description="昵称二次确认后软删；purge_all 返回删除回执")
def delete_child(
    profile_uid: str,
    body: ChildDeleteBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """删除儿童档案：confirm_nickname 校验通过后软删。

    profile_only：仅软删档案，问答历史保留（历史展示脱敏昵称）；
    purge_all：软删档案并返回 deletion_receipt（说明删除与留存范围，
    合规留档数据不可删除）。

    Args:
        profile_uid: 档案对外标识。
        body: {mode, confirm_nickname}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：profile_only 返回 {deleted: true}；purge_all 额外含
        deletion_receipt: {deleted: [...], retained: [...]}。

    Raises:
        ApiError: 1002 不存在或越权；1001 昵称校验不一致。
    """
    profile = _get_owned_child(db, user, profile_uid)
    nickname = decrypt_field(profile.nickname_enc)
    if body.confirm_nickname != nickname:
        raise ApiError(code=1001, message="昵称校验不一致")

    # 统一软删：保留外键引用与审计链路
    profile.deleted_at = utcnow()
    # 媒体清理（两种模式一致）：照片行软删 + 文件删除 + 头像文件清理
    photo_count = _purge_profile_media(db, "child", profile.id)
    avatar_rel = profile.avatar_path
    profile.avatar_path = None
    if avatar_rel:
        delete_file(avatar_rel)
    db.flush()

    data: Dict[str, Any] = {"deleted": True, "mode": body.mode}
    if body.mode == "purge_all":
        # 删除回执：删除范围 vs 法定留存范围
        data["deletion_receipt"] = {
            "deleted": [
                {"item": "child_profile", "profile_uid": profile_uid},
                {
                    "item": "profile_media",
                    "photos": photo_count,
                    "note": "头像与相册照片已删除",
                },
                {"item": "related_qa_history", "note": "关联问答记录不再展示"},
            ],
            "retained": [
                {"item": "consent_record", "reason": "合规留档≥3年"},
                {"item": "order", "reason": "交易记录留存≥3年"},
            ],
        }
    return ok(data)


# ---------- 宠物档案路由 ----------


@router.get("/profiles/pets", summary="宠物档案列表", description="不含已删除的宠物档案")
def list_pets(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户宠物档案列表（不含已删除）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"pets": [宠物视图...]}。
    """
    pets = (
        db.query(PetProfile)
        .filter(PetProfile.user_id == user.id, PetProfile.deleted_at.is_(None))
        .order_by(PetProfile.id.asc())
        .all()
    )
    return ok({"pets": [_pet_view(p) for p in pets]})


@router.post("/profiles/pets", summary="新建宠物档案", description="数量上限同儿童档案（免费 3 / 会员 10）")
def create_pet(
    body: PetBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """新建宠物档案（数量上限同儿童档案，无加密字段）。

    Args:
        body: 档案字段。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：新建宠物视图。

    Raises:
        ApiError: 1006 档案数量已达上限。
    """
    _check_profile_quota(db, user, PetProfile, PetProfile.deleted_at)
    pet = PetProfile(
        user_id=user.id,
        pet_type=body.pet_type,
        breed=body.breed,
        age_band=body.age_band,
        neutered_flag=body.neutered_flag,
        weight_kg=body.weight_kg,
        main_food=body.main_food,
    )
    db.add(pet)
    db.flush()
    return ok(_pet_view(pet))


@router.put("/profiles/pets/{pet_uid}", summary="更新宠物档案", description="乐观锁更新，版本不一致返回 1003")
def update_pet(
    pet_uid: str,
    body: PetUpdateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """更新宠物档案（乐观锁）：版本不一致返回 1003。

    Args:
        pet_uid: 宠物对外标识。
        body: 档案字段 + version。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：更新后的宠物视图。

    Raises:
        ApiError: 1002 不存在或越权；1003 乐观锁冲突。
    """
    pet = _get_owned_pet(db, user, pet_uid, for_update=True)
    if pet.version != body.version:
        raise_err(ERR_OPTIMISTIC_LOCK)
    # 全量覆盖更新（宠物字段无加密，直接赋值）
    pet.pet_type = body.pet_type
    pet.breed = body.breed
    pet.age_band = body.age_band
    pet.neutered_flag = body.neutered_flag
    pet.weight_kg = body.weight_kg
    pet.main_food = body.main_food
    pet.version += 1
    db.flush()
    return ok(_pet_view(pet))


@router.delete("/profiles/pets/{pet_uid}", summary="删除宠物档案", description="软删，保留问答历史引用")
def delete_pet(
    pet_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """删除宠物档案（软删，保留问答历史引用）。

    Args:
        pet_uid: 宠物对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"deleted": true}。

    Raises:
        ApiError: 1002 不存在或越权。
    """
    pet = _get_owned_pet(db, user, pet_uid)
    pet.deleted_at = utcnow()
    # 媒体清理：照片行软删 + 文件删除 + 头像文件清理
    _purge_profile_media(db, "pet", pet.id)
    avatar_rel = pet.avatar_path
    pet.avatar_path = None
    if avatar_rel:
        delete_file(avatar_rel)
    db.flush()
    return ok({"deleted": True})


# ---------- 当前问答对象 ----------


@router.post("/profiles/current", summary="设置当前问答对象", description="多档案场景下 upsert 本次问答对象（按对外 uid 解析，不暴露内部主键）")
def set_current_context(
    body: CurrentContextBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """设置当前问答对象（upsert）：多档案场景下「这次问的是谁」。

    Args:
        body: {profile_type, profile_uid}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{profile_type, profile_uid, updated_at}。

    Raises:
        ApiError: 1002 档案不存在、越权或已删除。
    """
    now = utcnow()
    # 按对外 uid 解析档案，校验归属与存续（防越权设置他人档案）
    if body.profile_type == "child":
        profile = (
            db.query(ChildProfile)
            .filter(
                ChildProfile.profile_uid == body.profile_uid,
                ChildProfile.user_id == user.id,
                ChildProfile.deleted_at.is_(None),
            )
            .first()
        )
    else:
        profile = (
            db.query(PetProfile)
            .filter(
                PetProfile.pet_uid == body.profile_uid,
                PetProfile.user_id == user.id,
                PetProfile.deleted_at.is_(None),
            )
            .first()
        )
    if profile is None:
        raise_err(ERR_NOT_FOUND)

    # upsert：current_context 以 user_id 为主键（库内存内部主键 ID，出参只给对外 uid）
    ctx = db.query(CurrentContext).filter(CurrentContext.user_id == user.id).first()
    if ctx is None:
        ctx = CurrentContext(
            user_id=user.id,
            profile_type=body.profile_type,
            profile_id=profile.id,
            updated_at=now,
        )
        db.add(ctx)
    else:
        ctx.profile_type = body.profile_type
        ctx.profile_id = profile.id
        ctx.updated_at = now
    db.flush()
    return ok({
        "profile_type": body.profile_type,
        "profile_uid": body.profile_uid,
        "updated_at": _iso(now),
    })


# ---------- 档案媒体（头像 / 相册，甲方需求 2026-10-14） ----------


@router.post(
    "/profiles/{kind}/{uid}/avatar",
    summary="上传档案头像",
    description="multipart 单文件（file 字段），服务端规范化 JPEG 存储并返回 avatar_url；覆盖旧的自动删除。"
    "用 POST 而非 PUT：微信 uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（2026-10-14 实测）",
)
def post_profile_avatar(
    kind: Literal["children", "pets"],
    uid: str,
    file: UploadFile = File(..., description="图片文件（jpeg/png/webp，≤8MB）"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """上传/更换档案头像（覆盖旧文件，幂等替换）。

    Args:
        kind: 档案类型路径段（children / pets）。
        uid: 档案对外标识。
        file: 图片文件。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{avatar_url, width, height, size}。

    Raises:
        ApiError: 1002 档案不存在/越权；1302 儿童同意缺失或已撤回；
                  1001 图片格式不支持或文件过大。
    """
    profile_type, profile, subdir = _resolve_media_target(db, user, kind, uid)
    _guard_child_media_consent(db, user, profile_type)
    rel, width, height, size = _save_upload_or_raise(
        file.file.read(), subdir, AVATAR_MAX_SIDE
    )
    old_rel = profile.avatar_path
    profile.avatar_path = rel
    db.flush()
    if old_rel:
        # 数据库先行、旧文件后删；不触碰 version（媒体变更不走乐观锁）
        delete_file(old_rel)
    return ok(
        {"avatar_url": _media_url(rel), "width": width, "height": height, "size": size}
    )


@router.delete(
    "/profiles/{kind}/{uid}/avatar",
    summary="移除档案头像",
    description="置空头像并删除文件；未设置时同样成功（幂等）",
)
def delete_profile_avatar(
    kind: Literal["children", "pets"],
    uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """移除档案头像（幂等：未设置时也返回成功）。

    Args:
        kind: 档案类型路径段（children / pets）。
        uid: 档案对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"deleted": true}。

    Raises:
        ApiError: 1002 档案不存在/越权；1302 儿童同意缺失或已撤回。
    """
    profile_type, profile, _subdir = _resolve_media_target(db, user, kind, uid)
    _guard_child_media_consent(db, user, profile_type)
    old_rel = profile.avatar_path
    profile.avatar_path = None
    db.flush()
    if old_rel:
        delete_file(old_rel)
    return ok({"deleted": True})


@router.get(
    "/profiles/{kind}/{uid}/photos",
    summary="档案相册列表",
    description="按加入时间升序返回照片 URL 与上限；孩子档案需儿童信息同意有效",
)
def list_profile_photos(
    kind: Literal["children", "pets"],
    uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """档案相册列表（不含已删除照片）。

    Args:
        kind: 档案类型路径段（children / pets）。
        uid: 档案对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"photos": [照片视图...], "limit": 上限}。

    Raises:
        ApiError: 1002 档案不存在/越权；1302 儿童同意缺失或已撤回。
    """
    profile_type, profile, _subdir = _resolve_media_target(db, user, kind, uid)
    _guard_child_media_consent(db, user, profile_type)
    rows = (
        db.query(ProfilePhoto)
        .filter(
            ProfilePhoto.profile_type == profile_type,
            ProfilePhoto.profile_id == profile.id,
            ProfilePhoto.deleted_at.is_(None),
        )
        .order_by(ProfilePhoto.id.asc())
        .all()
    )
    return ok({
        "photos": [_photo_view(r) for r in rows],
        "limit": get_settings().profile_photo_limit,
    })


@router.post(
    "/profiles/{kind}/{uid}/photos",
    summary="添加相册照片",
    description="multipart 单文件（file 字段）；数量上限按配置（默认 30 张），超限返回 1007",
)
def add_profile_photo(
    kind: Literal["children", "pets"],
    uid: str,
    file: UploadFile = File(..., description="图片文件（jpeg/png/webp，≤8MB）"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """添加相册照片（单张上传，前端多选按序多次调用）。

    Args:
        kind: 档案类型路径段（children / pets）。
        uid: 档案对外标识。
        file: 图片文件。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"photo": 照片视图, "count": 当前总数, "limit": 上限}。

    Raises:
        ApiError: 1002 档案不存在/越权；1302 儿童同意缺失或已撤回；
                  1001 图片格式不支持或文件过大；1007 相册数量已达上限。
    """
    profile_type, profile, subdir = _resolve_media_target(db, user, kind, uid)
    _guard_child_media_consent(db, user, profile_type)
    limit = get_settings().profile_photo_limit
    count = (
        db.query(func.count(ProfilePhoto.id))
        .filter(
            ProfilePhoto.profile_type == profile_type,
            ProfilePhoto.profile_id == profile.id,
            ProfilePhoto.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    if count >= limit:
        raise ApiError(code=1007, message="相册数量已达上限", http_status=409)
    rel, _width, _height, size = _save_upload_or_raise(
        file.file.read(), subdir, PHOTO_MAX_SIDE
    )
    row = ProfilePhoto(
        user_id=user.id,
        profile_type=profile_type,
        profile_id=profile.id,
        file_path=rel,
        file_size=size,
    )
    db.add(row)
    db.flush()
    return ok({"photo": _photo_view(row), "count": count + 1, "limit": limit})


@router.delete(
    "/profiles/{kind}/{uid}/photos/{photo_uid}",
    summary="删除相册照片",
    description="软删照片行并删除文件；不存在或越权统一 1002（防枚举）",
)
def delete_profile_photo(
    kind: Literal["children", "pets"],
    uid: str,
    photo_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """删除相册照片（软删行 + 删除文件）。

    Args:
        kind: 档案类型路径段（children / pets）。
        uid: 档案对外标识。
        photo_uid: 照片对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"deleted": true}。

    Raises:
        ApiError: 1002 档案或照片不存在/越权；1302 儿童同意缺失或已撤回。
    """
    profile_type, profile, _subdir = _resolve_media_target(db, user, kind, uid)
    _guard_child_media_consent(db, user, profile_type)
    row = (
        db.query(ProfilePhoto)
        .filter(
            ProfilePhoto.photo_uid == photo_uid,
            ProfilePhoto.profile_type == profile_type,
            ProfilePhoto.profile_id == profile.id,
            ProfilePhoto.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise_err(ERR_NOT_FOUND)
    row.deleted_at = utcnow()
    db.flush()
    delete_file(row.file_path)
    return ok({"deleted": True})

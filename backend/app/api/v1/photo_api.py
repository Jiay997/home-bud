# -*- coding: utf-8 -*-
"""图片提问 API 模块（RQ-05 / NFR-S7 / DR-27 / DR-28）。

端点：

- GET  /qa/photos/guide          场景化前置说明（拍什么 / 如何处理 / 何时删除）
- POST /qa/photos                上传并送检（未通过或超配额即拒绝，不扣额度）
- GET  /qa/photos/{photo_uid}    图片元数据（**无原图、无 URL、无后台查看入口**）

红线：本模块**不提供任何返回图片字节或图片 URL 的接口**（AC-RQ05-4）。
"""
import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_CHILD_CONSENT, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser, ChildProfile, PhotoAsset
from ...services import photo_service
from .consent_api import require_base_consent

logger = logging.getLogger("jiaban.photo_api")

router = APIRouter(tags=["C端-问答"])

# 单张图片上传体积上限（前端已压缩，服务端再校验）
PHOTO_MAX_BYTES = 8 * 1024 * 1024

# 儿童信息单独同意类型（RQ-05 AC-6：儿童影像按敏感个人信息处理）
CHILD_CONSENT_TYPE = "child_personal_info"


def _require_child_consent_if_applicable(db: Session, user: AppUser) -> None:
    """上传图片前校验儿童信息单独同意（保守口径）。

    图片可能包含儿童影像，按 PRD §3.5 AC-6「按敏感个人信息执行」处理：
    只要该用户名下存在 active 儿童档案，即要求 `child_personal_info` 同意
    未撤回；纯宠物用户不强制（避免与 F1 同意范围错配）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Raises:
        ApiError: 1302 儿童信息单独同意缺失或已撤回。
    """
    has_child = (
        db.query(ChildProfile)
        .filter(
            ChildProfile.user_id == user.id,
            ChildProfile.status == "active",
        )
        .first()
        is not None
    )
    if not has_child:
        return
    from ...models import ConsentRecord

    active = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.user_id == user.id,
            ConsentRecord.consent_type == CHILD_CONSENT_TYPE,
            ConsentRecord.withdraw_at.is_(None),
        )
        .first()
    )
    if active is None:
        raise ApiError(*ERR_CHILD_CONSENT)


@router.get(
    "/qa/photos/guide",
    summary="图片提问前置说明",
    description="场景化告知：拍什么、照片如何被处理、何时删除（拒绝授权可改用文字问答）",
)
def photo_guide(
    scene: str = "unknown",
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """下发场景化前置说明（AC-RQ05-1）。

    Args:
        scene: 场景枚举（rash / stool / vomit / food_label / medicine_pack / unknown）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{scenes[], selected, privacy_notice, max_count, ttl_hours}。
    """
    require_base_consent(db, user.id)
    return ok(photo_service.scene_guide(scene))


@router.post(
    "/qa/photos",
    summary="上传图片并送检",
    description="顺序执行压缩→送检；未通过或配额超限即拒绝（不进入推理、不扣额度）",
)
def upload_photo(
    file: UploadFile = File(..., description="图片文件（jpeg/png/webp，≤8MB）"),
    scene: str = Form("unknown", description="场景枚举"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """上传并送检一张图片（AC-RQ05-2）。

    Args:
        file: 图片文件。
        scene: 场景枚举。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{photo_uid, scene, moderation_result, expires_at, notice}。

    Raises:
        ApiError: 1001 文件为空/超限/格式不支持；1303 送检未通过或配额超限；
            1302 儿童信息单独同意缺失（存在儿童档案时）；1301 未同意基础协议。
    """
    require_base_consent(db, user.id)
    _require_child_consent_if_applicable(db, user)
    data = file.file.read()
    if not data:
        raise ApiError(code=1001, message="文件为空", http_status=422)
    if len(data) > PHOTO_MAX_BYTES:
        raise ApiError(code=1001, message="图片超过 8MB 上限", http_status=422)
    asset, error = photo_service.submit_photo(
        db, user.id, data, file.filename or "", scene=scene
    )
    if error is not None:
        db.rollback()
        code, message, status = error
        raise ApiError(code=code, message=message, http_status=status)
    db.commit()
    return ok(
        {
            "photo_uid": asset.photo_uid,
            "scene": asset.scene,
            "moderation_result": asset.moderation_result,
            "expires_at": asset.expires_at.isoformat() if asset.expires_at else None,
            "notice": photo_service.PRIVACY_NOTICE,
            "parse_notice": photo_service.PARSE_STUB_NOTICE,
        }
    )


@router.get(
    "/qa/photos/{photo_uid}",
    summary="图片元数据",
    description="仅返回元数据（场景/送检结果/删除时间），无原图、无 URL、无后台查看入口",
)
def photo_metadata(
    photo_uid: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """查询图片元数据（AC-RQ05-3/4：只暴露元数据）。

    Args:
        photo_uid: 图片标识。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{photo_uid, scene, moderation_result, expires_at, deleted_at}。

    Raises:
        ApiError: 1002 图片不存在或非本人。
    """
    asset = (
        db.query(PhotoAsset)
        .filter(PhotoAsset.photo_uid == photo_uid, PhotoAsset.user_id == user.id)
        .first()
    )
    if asset is None:
        raise ApiError(*ERR_NOT_FOUND)
    return ok(photo_service.meta_summary(db, [photo_uid])["items"][0])

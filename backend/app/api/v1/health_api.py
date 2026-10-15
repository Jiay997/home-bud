# -*- coding: utf-8 -*-
"""健康档案 API 模块（甲方需求 2026-10-15）。

- GET/POST /health/records                    健康记录列表 / 新建（multipart 可附报告文件）
- GET/PUT/DELETE /health/records/{record_uid} 详情 / 更新（JSON 全量替换）/ 删除（软删+文件清理）
- POST /health/records/{record_uid}/file      替换报告文件（multipart）

业务口径：
- subject 多态关联 child_profile / pet_profile（沿用 profile_photo 口径，
  出参只用 subject_uid，内部主键不暴露）；儿童主体受儿童信息同意门禁（1302）：
  撤回同意后档案置 disabled，其健康记录行保留但列表/详情停止下发（1002）；
- notes / 复查说明 Fernet 加密落库；报告文件经 /media 静态挂载直出；
- 复查提醒为纯应用内展示：列表按 next_checkup_date 计算 due_status
  （overdue 已过期 / soon 7 天内 / upcoming / none），不接 agent、不做推送；
- 横向越权一律按 1002 不存在处理（防枚举，复用 profiles_api 归属校验）。
"""
from datetime import date
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.crypto import decrypt_field, encrypt_field
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, raise_err, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser, ChildProfile, HealthRecord
from ...models.base import utcnow
from ...services.media_store import MediaValidationError, delete_file, save_document
from .profiles_api import (
    _get_owned_child,
    _get_owned_pet,
    _iso,
    _media_url,
    _require_child_consent,
    _shanghai_today,
)

router = APIRouter(tags=["C端-健康与笔记"])

# 复查提醒：临期窗口（含当天）
DUE_SOON_DAYS = 7

# 报告文件大小口径提示
_FILE_HINT = "支持 PDF/JPG/PNG，PDF ≤10MB"


# ---------- 请求体模型 ----------


class RecordCreateBody(BaseModel):
    """新建健康记录请求体（JSON；报告文件经 /file 端点单独上传）。

    Attributes:
        subject_type: child / pet。
        subject_uid: 档案对外标识。
        record_date: 体检日期 YYYY-MM-DD。
        title: 记录标题。
        notes: 医生建议/备注（可空，加密存储）。
        next_checkup_date: 下次复查日期（可空，提醒来源）。
        next_checkup_note: 复查项目说明（可空，加密存储）。
    """

    subject_type: Literal["child", "pet"] = Field(description="档案主体类型")
    subject_uid: str = Field(min_length=1, max_length=64, description="档案对外标识")
    record_date: date = Field(description="体检日期 YYYY-MM-DD")
    title: str = Field(min_length=1, max_length=64, description="记录标题")
    notes: Optional[str] = Field(default=None, max_length=500, description="医生建议/备注")
    next_checkup_date: Optional[date] = Field(default=None, description="下次复查日期")
    next_checkup_note: Optional[str] = Field(
        default=None, max_length=200, description="复查项目说明"
    )


class RecordUpdateBody(BaseModel):
    """更新健康记录请求体（全量替换可编辑字段）。

    Attributes:
        record_date: 体检日期 YYYY-MM-DD。
        title: 记录标题。
        notes: 医生建议/备注（可空，加密存储）。
        next_checkup_date: 下次复查日期（可空，提醒来源）。
        next_checkup_note: 复查项目说明（可空，加密存储）。
    """

    record_date: date = Field(description="体检日期 YYYY-MM-DD")
    title: str = Field(min_length=1, max_length=64, description="记录标题")
    notes: Optional[str] = Field(default=None, max_length=500, description="医生建议/备注")
    next_checkup_date: Optional[date] = Field(default=None, description="下次复查日期")
    next_checkup_note: Optional[str] = Field(
        default=None, max_length=200, description="复查项目说明"
    )


# ---------- 内部工具函数 ----------


def _due_status(next_checkup: Optional[date], today: date) -> str:
    """按复查日期计算提醒状态。

    Args:
        next_checkup: 下次复查日期（可空）。
        today: 东八区今天。

    Returns:
        overdue / soon / upcoming / none。
    """
    if next_checkup is None:
        return "none"
    delta = (next_checkup - today).days
    if delta < 0:
        return "overdue"
    if delta <= DUE_SOON_DAYS:
        return "soon"
    return "upcoming"


def _get_owned_record(
    db: Session, user: AppUser, record_uid: str, for_update: bool = False
) -> HealthRecord:
    """按 uid 取当前用户的健康记录（防枚举：越权与不存在统一 1002）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        record_uid: 记录对外标识。
        for_update: True 时加行锁。

    Returns:
        健康记录 ORM 实例。

    Raises:
        ApiError: 1002 不存在、不属于当前用户或已删除。
    """
    query = db.query(HealthRecord).filter(HealthRecord.record_uid == record_uid)
    if for_update:
        query = query.with_for_update()
    row = query.first()
    if row is None or row.user_id != user.id or row.deleted_at is not None:
        raise_err(ERR_NOT_FOUND)
    return row


def _disabled_child_uids(db: Session, user_id: int) -> set:
    """当前用户已停用（撤回儿童信息同意）的儿童档案标识集合。

    撤回后儿童档案置 disabled，其关联数据沿用「保留但不展示与使用」口径，
    健康记录列表/详情据此停止下发（同 profiles 列表 avatar_url 置空）。

    Args:
        db: 数据库会话。
        user_id: 当前用户主键。

    Returns:
        status 非 active 的 ChildProfile.profile_uid 集合。
    """
    return {
        uid
        for (uid,) in db.query(ChildProfile.profile_uid).filter(
            ChildProfile.user_id == user_id, ChildProfile.status != "active"
        )
    }


def _resolve_subject(
    db: Session, user: AppUser, subject_type: str, subject_uid: str
) -> Dict[str, Any]:
    """解析并校验档案主体归属（child/pet 多态）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        subject_type: "child" 或 "pet"。
        subject_uid: 档案对外标识。

    Returns:
        {"subject_id": 内部主键, "subject_uid": 对外标识}。

    Raises:
        ApiError: 1001 主体类型不合法；1002 档案不存在/越权/已禁用；
                  1302 儿童信息同意缺失或已撤回。
    """
    if subject_type == "child":
        profile = _get_owned_child(db, user, subject_uid)
        # 撤回同意后档案置 disabled，停止一切读写
        if profile.status == "disabled":
            raise_err(ERR_NOT_FOUND)
        _require_child_consent(db, user.id)
    elif subject_type == "pet":
        profile = _get_owned_pet(db, user, subject_uid)
    else:
        raise ApiError(
            code=1001, message="subject_type 须为 child 或 pet", http_status=422
        )
    return {"subject_id": profile.id, "subject_uid": subject_uid}


def _save_document_or_raise(data: bytes, filename: Optional[str]) -> Dict[str, Any]:
    """保存报告文件（校验失败统一映射 1001）。

    Args:
        data: 原始上传字节。
        filename: 上传原始文件名。

    Returns:
        {"file_path": 相对路径, "file_size": 字节数}。

    Raises:
        ApiError: 1001 文件格式不支持或超过大小限制。
    """
    try:
        rel, size = save_document(data, "health", filename or "")
    except MediaValidationError:
        raise ApiError(
            code=1001, message=f"文件格式不支持或超过大小限制（{_FILE_HINT}）", http_status=422
        ) from None
    return {"file_path": rel, "file_size": size}


def _record_list_view(row: HealthRecord, today: date) -> Dict[str, Any]:
    """构造列表视图（不含加密正文，轻量化）。"""
    return {
        "record_uid": row.record_uid,
        "subject_type": row.subject_type,
        "subject_uid": row.subject_uid,
        "record_date": row.record_date.isoformat(),
        "title": row.title,
        "next_checkup_date": (
            row.next_checkup_date.isoformat() if row.next_checkup_date else None
        ),
        "due_status": _due_status(row.next_checkup_date, today),
        "has_file": row.file_path is not None,
        "file_url": _media_url(row.file_path),
        "updated_at": _iso(row.updated_at),
    }


def _record_detail_view(row: HealthRecord, today: date) -> Dict[str, Any]:
    """构造详情视图（解密正文字段）。"""
    view = _record_list_view(row, today)
    view.update(
        {
            "notes": decrypt_field(row.notes_enc) if row.notes_enc else None,
            "next_checkup_note": (
                decrypt_field(row.next_checkup_note_enc)
                if row.next_checkup_note_enc
                else None
            ),
            "file_name": row.file_name,
            "file_size": row.file_size,
            "created_at": _iso(row.created_at),
        }
    )
    return view


# ---------- 路由 ----------


@router.get(
    "/health/records",
    summary="健康记录列表",
    description="按体检日期倒序；每条含复查提醒状态 due_status（overdue/soon/upcoming/none）",
)
def list_health_records(
    subject_type: Optional[Literal["child", "pet"]] = None,
    subject_uid: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户的健康记录列表（不含已删除）。

    Args:
        subject_type: 可选过滤（child/pet）。
        subject_uid: 可选过滤（指定档案）。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"records": [记录视图...], "today": 东八区今天}。
    """
    today = _shanghai_today()
    disabled = _disabled_child_uids(db, user.id)
    query = db.query(HealthRecord).filter(
        HealthRecord.user_id == user.id, HealthRecord.deleted_at.is_(None)
    )
    if subject_type:
        query = query.filter(HealthRecord.subject_type == subject_type)
    if subject_uid:
        query = query.filter(HealthRecord.subject_uid == subject_uid)
    rows = (
        query.order_by(HealthRecord.record_date.desc(), HealthRecord.id.desc()).all()
    )
    rows = [
        r
        for r in rows
        if not (r.subject_type == "child" and r.subject_uid in disabled)
    ]
    return ok({
        "records": [_record_list_view(r, today) for r in rows],
        "today": today.isoformat(),
    })


@router.post(
    "/health/records",
    summary="新建健康记录",
    description="JSON 体：档案主体 + 体检信息；报告文件创建后经 /file 端点单独上传。"
    "儿童主体需儿童信息同意有效",
)
def create_health_record(
    body: RecordCreateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """新建健康记录（报告文件另经 /health/records/{uid}/file 上传）。

    Args:
        body: 新建请求体。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"record": 详情视图}。

    Raises:
        ApiError: 1001 参数不合法；1002 档案不存在/越权；1302 同意缺失。
    """
    today = _shanghai_today()
    subject = _resolve_subject(db, user, body.subject_type, body.subject_uid)
    row = HealthRecord(
        user_id=user.id,
        subject_type=body.subject_type,
        subject_id=subject["subject_id"],
        subject_uid=subject["subject_uid"],
        record_date=body.record_date,
        title=body.title,
        notes_enc=encrypt_field(body.notes) if body.notes else None,
        next_checkup_date=body.next_checkup_date,
        next_checkup_note_enc=(
            encrypt_field(body.next_checkup_note) if body.next_checkup_note else None
        ),
        updated_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return ok({"record": _record_detail_view(row, today)})


@router.get(
    "/health/records/{record_uid}",
    summary="健康记录详情",
    description="解密返回医生建议与复查说明",
)
def get_health_record(
    record_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """健康记录详情。

    Args:
        record_uid: 记录对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"record": 详情视图}。
    """
    row = _get_owned_record(db, user, record_uid)
    if row.subject_type == "child" and row.subject_uid in _disabled_child_uids(
        db, user.id
    ):
        # 撤回儿童信息同意后停止展示与使用（数据保留，防枚举按 1002）
        raise_err(ERR_NOT_FOUND)
    return ok({"record": _record_detail_view(row, _shanghai_today())})


@router.put(
    "/health/records/{record_uid}",
    summary="更新健康记录",
    description="JSON 全量替换可编辑字段（体检日期/标题/备注/复查计划）",
)
def update_health_record(
    record_uid: str,
    body: RecordUpdateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """更新健康记录可编辑字段（全量替换语义）。

    Args:
        record_uid: 记录对外标识。
        body: 更新请求体。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"record": 详情视图}。
    """
    row = _get_owned_record(db, user, record_uid, for_update=True)
    row.record_date = body.record_date
    row.title = body.title
    row.notes_enc = encrypt_field(body.notes) if body.notes else None
    row.next_checkup_date = body.next_checkup_date
    row.next_checkup_note_enc = (
        encrypt_field(body.next_checkup_note) if body.next_checkup_note else None
    )
    row.updated_at = utcnow()
    db.flush()
    return ok({"record": _record_detail_view(row, _shanghai_today())})


@router.post(
    "/health/records/{record_uid}/file",
    summary="替换报告文件",
    description="multipart 单文件（file 字段），覆盖旧的自动删除。"
    "用 POST 而非 PUT：微信 uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（2026-10-14 实测）",
)
def replace_health_record_file(
    record_uid: str,
    file: UploadFile = File(..., description=f"报告文件（{_FILE_HINT}）"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """替换健康记录的报告文件（旧文件删除，幂等替换）。

    Args:
        record_uid: 记录对外标识。
        file: 报告文件。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"file_url", "file_name", "file_size"}。
    """
    row = _get_owned_record(db, user, record_uid)
    saved = _save_document_or_raise(file.file.read(), file.filename)
    old_rel = row.file_path
    row.file_path = saved["file_path"]
    row.file_name = file.filename
    row.file_size = saved["file_size"]
    row.updated_at = utcnow()
    db.flush()
    if old_rel and old_rel != row.file_path:
        # 数据库先行、旧文件后删
        delete_file(old_rel)
    return ok({
        "file_url": _media_url(row.file_path),
        "file_name": row.file_name,
        "file_size": row.file_size,
    })


@router.delete(
    "/health/records/{record_uid}",
    summary="删除健康记录",
    description="软删并清理报告文件",
)
def delete_health_record(
    record_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """删除健康记录（软删 + 文件清理）。

    Args:
        record_uid: 记录对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"deleted": true}。
    """
    row = _get_owned_record(db, user, record_uid)
    row.deleted_at = utcnow()
    row.updated_at = utcnow()
    db.flush()
    if row.file_path:
        delete_file(row.file_path)
    return ok({"deleted": True})

# -*- coding: utf-8 -*-
"""个人笔记 API 模块（甲方需求 2026-10-15）。

- GET/POST /notes                笔记列表（标题+摘要）/ 新建
- GET/PUT/DELETE /notes/{note_uid} 详情 / 更新（乐观锁）/ 删除（软删）

业务口径：
- 正文 Markdown 加密落库（Fernet），仅本人可见，不公开分享；
- 更新走乐观锁（version 不一致返回 1003），防多端并发覆盖；
- 保存前复用反馈模块的本地敏感词前置检查（命中推广引流词直接拒绝）；
- 横向越权一律按 1002 不存在处理（防枚举）。
"""
from typing import Any, Dict, Optional
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.crypto import decrypt_field, encrypt_field
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import raise_err, ERR_NOT_FOUND, ERR_OPTIMISTIC_LOCK
from ...db import get_db
from ...models import AppUser, Note
from ...models.base import utcnow
from .feedback_api import _check_sensitive_words

router = APIRouter(tags=["C端-健康与笔记"])

# 列表摘要长度
EXCERPT_LEN = 60


# ---------- 请求体模型 ----------


class NoteCreateBody(BaseModel):
    """新建笔记请求体。

    Attributes:
        title: 笔记标题。
        content: 笔记正文（Markdown）。
    """

    title: str = Field(min_length=1, max_length=60, description="笔记标题")
    content: str = Field(min_length=1, max_length=20000, description="笔记正文 Markdown")


class NoteUpdateBody(NoteCreateBody):
    """更新笔记请求体（乐观锁）。

    Attributes:
        version: 客户端持有的版本号（不一致返回 1003）。
    """

    version: int = Field(ge=1, description="乐观锁版本号")


# ---------- 内部工具函数 ----------


def _get_owned_note(
    db: Session, user: AppUser, note_uid: str, for_update: bool = False
) -> Note:
    """按 uid 取当前用户的笔记（防枚举：越权与不存在统一 1002）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        note_uid: 笔记对外标识。
        for_update: True 时加行锁（乐观锁更新并发兜底，同 profiles 口径）。

    Returns:
        笔记 ORM 实例。

    Raises:
        ApiError: 1002 不存在、不属于当前用户或已删除。
    """
    query = db.query(Note).filter(Note.note_uid == note_uid)
    if for_update:
        query = query.with_for_update()
    row = query.first()
    if row is None or row.user_id != user.id or row.deleted_at is not None:
        raise_err(ERR_NOT_FOUND)
    return row


def _strip_markdown(text: str) -> str:
    """剥离正文中的 Markdown 排版语法，供列表摘要纯文本展示。

    Args:
        text: 解密后的 Markdown 正文。

    Returns:
        去掉标题井号、列表符号、加粗/斜体星号、表格分隔线后的纯文本。
    """
    lines: list = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if re.match(r"^#{1,6}\s", stripped) or re.fullmatch(r"[-*_]{3,}", stripped):
            continue
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            lines.append(" ".join(c for c in cells if c))
            continue
        lines.append(re.sub(r"^\s*[-*]\s+", "", line))
    return " ".join(lines).replace("**", "").replace("*", "")


def _excerpt(content: str) -> str:
    """生成列表摘要（剥离 Markdown、压平换行、截断）。

    Args:
        content: 解密后的正文。

    Returns:
        摘要字符串（最长 EXCERPT_LEN，超长加省略号）。
    """
    flat = " ".join(_strip_markdown(content).split())
    if len(flat) <= EXCERPT_LEN:
        return flat
    return flat[:EXCERPT_LEN] + "…"


def _note_view(row: Note, with_content: bool) -> Dict[str, Any]:
    """构造笔记展示视图。

    Args:
        row: 笔记 ORM 实例。
        with_content: True 返回解密正文（详情）；False 返回摘要（列表）。
    """
    content = decrypt_field(row.content_enc)
    view: Dict[str, Any] = {
        "note_uid": row.note_uid,
        "title": row.title,
        "version": row.version,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if with_content:
        view["content"] = content
        view["created_at"] = row.created_at.isoformat() if row.created_at else None
    else:
        view["excerpt"] = _excerpt(content)
    return view


# ---------- 路由 ----------


@router.get(
    "/notes",
    summary="笔记列表",
    description="按更新时间倒序，返回标题+摘要；keyword 按标题过滤",
)
def list_notes(
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户的笔记列表（不含已删除）。

    Args:
        keyword: 标题过滤关键字（可选）。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"notes": [笔记视图...]}。
    """
    query = db.query(Note).filter(Note.user_id == user.id, Note.deleted_at.is_(None))
    if keyword:
        query = query.filter(Note.title.contains(keyword))
    rows = query.order_by(Note.updated_at.desc(), Note.id.desc()).all()
    return ok({"notes": [_note_view(r, with_content=False) for r in rows]})


@router.post(
    "/notes",
    summary="新建笔记",
    description="正文 Markdown 加密落库；本地敏感词前置检查（命中推广引流词拒绝）",
)
def create_note(
    body: NoteCreateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """新建笔记。

    Args:
        body: 新建请求体。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"note": 详情视图}。

    Raises:
        ApiError: 1303 内容包含违规推广信息。
    """
    _check_sensitive_words(f"{body.title}\n{body.content}")
    row = Note(
        user_id=user.id,
        title=body.title,
        content_enc=encrypt_field(body.content),
        updated_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return ok({"note": _note_view(row, with_content=True)})


@router.get(
    "/notes/{note_uid}",
    summary="笔记详情",
    description="解密返回正文 Markdown 与乐观锁版本号",
)
def get_note(
    note_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """笔记详情。

    Args:
        note_uid: 笔记对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"note": 详情视图}。
    """
    row = _get_owned_note(db, user, note_uid)
    return ok({"note": _note_view(row, with_content=True)})


@router.put(
    "/notes/{note_uid}",
    summary="更新笔记",
    description="乐观锁更新：version 不一致返回 1003；保存前同样过敏感词检查",
)
def update_note(
    note_uid: str,
    body: NoteUpdateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """更新笔记（乐观锁）。

    Args:
        note_uid: 笔记对外标识。
        body: 更新请求体。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"note": 详情视图}。

    Raises:
        ApiError: 1002 不存在/越权；1003 版本冲突；1303 敏感词命中。
    """
    row = _get_owned_note(db, user, note_uid, for_update=True)
    if row.version != body.version:
        raise_err(ERR_OPTIMISTIC_LOCK)
    _check_sensitive_words(f"{body.title}\n{body.content}")
    row.title = body.title
    row.content_enc = encrypt_field(body.content)
    row.version = row.version + 1
    row.updated_at = utcnow()
    db.flush()
    return ok({"note": _note_view(row, with_content=True)})


@router.delete(
    "/notes/{note_uid}",
    summary="删除笔记",
    description="软删",
)
def delete_note(
    note_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """删除笔记（软删）。

    Args:
        note_uid: 笔记对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"deleted": true}。
    """
    row = _get_owned_note(db, user, note_uid)
    row.deleted_at = utcnow()
    row.updated_at = utcnow()
    db.flush()
    return ok({"deleted": True})

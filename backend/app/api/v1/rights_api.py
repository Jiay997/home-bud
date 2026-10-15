# -*- coding: utf-8 -*-
"""个人信息权利请求 API 模块。

提供六类权利请求的提交、列表与导出文件下载：
- POST /rights/requests                        提交权利请求（15 天 SLA）
- GET  /rights/requests                        当前用户请求列表
- GET  /rights/requests/{request_no}/download  导出文件下载（一次有效）

业务口径：六类请求 access/correct/export/withdraw/delete/deactivate；
export 类 delivery_method='download'，导出链接 24h 过期且限一次下载。
"""
import os
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND, raise_err
from ...db import get_db
from ...models import AppUser, RightsRequest
from ...models.base import utcnow

router = APIRouter(tags=["C端-权利反馈"])

# 权利请求处理 SLA：15 天
RIGHTS_SLA_DAYS = 15

# 导出文件有效期：24 小时
EXPORT_TTL_HOURS = 24


class RightsRequestBody(BaseModel):
    """提交权利请求体。

    Attributes:
        request_type: 请求类型（access/correct/export/withdraw/delete/deactivate）。
        scope: 请求范围说明（可选，如仅导出问答记录）。
    """

    request_type: Literal[
        "access", "correct", "export", "withdraw", "delete", "deactivate"
    ] = Field(description="请求类型")
    scope: Optional[Dict[str, Any]] = Field(default=None, description="请求范围")


def _iso(value: Any) -> Optional[str]:
    """datetime 转 ISO8601 字符串。

    Args:
        value: datetime 实例或 None。

    Returns:
        ISO 字符串；入参为 None 时返回 None。
    """
    return value.isoformat() if value is not None else None


def _rights_view(req: RightsRequest) -> Dict[str, Any]:
    """构造权利请求视图。

    Args:
        req: 权利请求 ORM 实例。

    Returns:
        请求字段字典。
    """
    return {
        "request_no": req.request_no,
        "request_type": req.request_type,
        "scope": req.scope,
        "status": req.status,
        "delivery_method": req.delivery_method,
        "sla_due_at": _iso(req.sla_due_at),
        "reject_reason_code": req.reject_reason_code,
        "created_at": _iso(req.created_at),
        "handled_at": _iso(req.handled_at),
    }


def _get_owned_request(db: Session, user: AppUser, request_no: str) -> RightsRequest:
    """按 request_no 取当前用户的权利请求（防枚举：越权与不存在统一 1002）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        request_no: 请求编号。

    Returns:
        RightsRequest ORM 实例。

    Raises:
        ApiError: 1002 不存在或不属于当前用户。
    """
    req = db.query(RightsRequest).filter(RightsRequest.request_no == request_no).first()
    if req is None or req.user_id != user.id:
        raise_err(ERR_NOT_FOUND)
    return req


@router.post("/rights/requests", summary="提交权利请求", description="六类请求，15 天 SLA；export 类标记下载交付")
def create_rights_request(
    body: RightsRequestBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """提交权利请求：15 天 SLA；export 类标记 download 交付方式。

    Args:
        body: {request_type, scope?}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{request_no, request_type, status, sla_due_at}。
    """
    now = utcnow()
    req = RightsRequest(
        request_no=f"RT{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        user_id=user.id,
        request_type=body.request_type,
        scope=body.scope,
        status="submitted",
        # 导出类请求以下载链接交付
        delivery_method="download" if body.request_type == "export" else None,
        sla_due_at=now + timedelta(days=RIGHTS_SLA_DAYS),
    )
    db.add(req)
    db.flush()
    return ok({
        "request_no": req.request_no,
        "request_type": req.request_type,
        "status": req.status,
        "sla_due_at": _iso(req.sla_due_at),
    })


@router.get("/rights/requests", summary="权利请求列表", description="当前用户请求，创建时间倒序")
def list_rights_requests(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户权利请求列表（创建时间倒序，含状态）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"requests": [请求视图...]}。
    """
    reqs = (
        db.query(RightsRequest)
        .filter(RightsRequest.user_id == user.id)
        .order_by(RightsRequest.created_at.desc())
        .all()
    )
    return ok({"requests": [_rights_view(r) for r in reqs]})


@router.get("/rights/requests/{request_no}/download", summary="下载导出文件", description="仅 export 请求且未过期未下载过（一次有效）")
def download_export(
    request_no: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> Any:
    """下载导出文件：仅 export 请求且后台已生成、未过期、未下载过。

    首次下载标记 export_downloaded=True（链接一次有效）；
    已下载或已过期返回 1002「下载链接已失效」。

    Args:
        request_no: 请求编号。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        本地文件存在时返回 FileResponse；否则以纯文本下发导出文件地址。

    Raises:
        ApiError: 1002 请求不存在/越权/非导出类/文件未生成/已下载/已过期。
    """
    req = _get_owned_request(db, user, request_no)
    if req.request_type != "export":
        raise ApiError(code=1002, message="该请求类型不支持下载")
    # 后台尚未生成导出文件
    if not req.export_file_url:
        raise ApiError(code=1002, message="导出文件尚未生成")

    now = utcnow()
    if req.export_downloaded:
        raise ApiError(code=1002, message="下载链接已失效")
    if req.export_expire_at is not None and req.export_expire_at < now:
        raise ApiError(code=1002, message="下载链接已失效")

    # 首次下载即失效（一次有效）
    req.export_downloaded = True
    db.flush()

    # 本地文件直接下发；对象存储 URL 以文本形式返回地址
    if os.path.isfile(req.export_file_url):
        return FileResponse(
            req.export_file_url,
            filename=f"{request_no}_export.txt",
            media_type="application/octet-stream",
        )
    return PlainTextResponse(f"{request_no} export file: {req.export_file_url}")

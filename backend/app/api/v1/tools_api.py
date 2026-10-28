# -*- coding: utf-8 -*-
"""轻工具 API 模块（RQ-12）。

端点：

- GET  /tools                    工具列表（含标识与免责；不消耗问答额度）
- GET  /tools/{tool_code}        工具详情
- POST /tools/{tool_code}/complete 完成自查（记录完成项数与转化归因）
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser
from ...services import tool_service
from .consent_api import require_base_consent

logger = logging.getLogger("jiaban.tools_api")

router = APIRouter(tags=["C端-健康与笔记"])


class CompleteBody(BaseModel):
    """工具完成请求体。

    Attributes:
        completed_items: 勾选完成的项数。
        next: 完成后去向（qa / topic / done），用于转化归因。
    """

    completed_items: int = Field(0, ge=0, le=100, description="完成项数")
    next: Optional[str] = Field(None, description="去向 qa/topic/done")


@router.get(
    "/tools",
    summary="轻工具列表",
    description="结构化内容 + 简单交互；不消耗问答额度，工具页带 AI 标识与免责",
)
def list_tools(
    domain: Optional[str] = None,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取轻工具列表（AC-RQ12-1 / AC-RQ12-2）。

    Args:
        domain: 领域过滤 child / pet。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{items[], quota_cost: 0, entry: "secondary"}。
    """
    require_base_consent(db, user.id)
    items: List[dict] = tool_service.list_tools(db, domain=domain)
    return ok({"items": items, "quota_cost": 0, "entry": "secondary"})


@router.get(
    "/tools/{tool_code}",
    summary="轻工具详情",
    description="返回工具内容（清单步骤 / 解析口径）与免责；不消耗问答额度",
)
def get_tool(
    tool_code: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取轻工具详情（AC-RQ12-1）。

    Args:
        tool_code: 工具编码。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：工具视图。

    Raises:
        ApiError: 1002 工具不存在或未上架。
    """
    require_base_consent(db, user.id)
    data = tool_service.get_tool(db, tool_code)
    if data is None:
        raise ApiError(*ERR_NOT_FOUND)
    tool_service.record_run(db, user.id, tool_code, action="view")
    db.commit()
    data["quota_cost"] = 0
    return ok(data)


@router.post(
    "/tools/{tool_code}/complete",
    summary="完成轻工具自查",
    description="记录完成项数与去向（转化归因）；不消耗问答额度",
)
def complete_tool(
    tool_code: str,
    body: CompleteBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """记录工具使用完成（AC-RQ12-3 转化归因）。

    Args:
        tool_code: 工具编码。
        body: 完成请求体。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{tool_code, completed_items, next, quota_cost}。

    Raises:
        ApiError: 1002 工具不存在。
    """
    require_base_consent(db, user.id)
    if tool_service.get_tool(db, tool_code) is None:
        raise ApiError(*ERR_NOT_FOUND)
    tool_service.record_run(
        db, user.id, tool_code, action="complete", completed_items=body.completed_items
    )
    if body.next == "qa":
        tool_service.record_run(db, user.id, tool_code, action="to_qa")
    elif body.next == "topic":
        tool_service.record_run(db, user.id, tool_code, action="to_topic")
    db.commit()
    return ok(
        {
            "tool_code": tool_code,
            "completed_items": body.completed_items,
            "next": body.next,
            "quota_cost": 0,
        }
    )

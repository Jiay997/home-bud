# -*- coding: utf-8 -*-
"""专题包 API 模块（RQ-13 交叉主题包 / RQ-14 宠物行为内容线）。

端点：

- GET /topics                     上架专题包列表（红旗前置，双签后才展示）
- GET /topics/{topic_code}        专题包详情
- GET /topics/recommended        按入口场景化推荐（问答结果页尾部，不做弹窗）

计费口径：专题独立计费、会员不含（口径不变）；购买走 F9 订单体系。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser
from ...services import topic_service
from .consent_api import require_base_consent

logger = logging.getLogger("jiaban.topics_api")

router = APIRouter(tags=["C端-商业化"])


@router.get(
    "/topics",
    summary="专题包列表",
    description="交叉主题包与宠物行为内容线；红旗前置，交叉内容育儿+宠物专家双签后才上架",
)
def list_topics(
    domain: Optional[str] = None,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取上架专题包列表（AC-RQ13-1 / AC-RQ14-1）。

    Args:
        domain: 领域过滤 cross / behavior / child / pet。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{items[], member_included: false}。
    """
    require_base_consent(db, user.id)
    return ok(
        {
            "items": topic_service.list_topics(db, domain=domain),
            "member_included": False,
        }
    )


@router.get(
    "/topics/recommended",
    summary="专题包场景化推荐",
    description="按入口推荐（family 优先育儿×宠物交叉），挂问答尾部，不做弹窗打扰",
)
def recommended_topics(
    entry: str = Query("family", description="child / pet / family"),
    limit: int = Query(2, ge=1, le=5),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """按入口推荐专题包（AC-RQ13-3）。

    Args:
        entry: 入口。
        limit: 条数。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{items[]}。
    """
    require_base_consent(db, user.id)
    return ok({"items": topic_service.recommend_for_entry(db, entry, limit=limit)})


@router.get(
    "/topics/{topic_code}",
    summary="专题包详情",
    description="返回红旗前置块 + 正文块；不含会员权益（专题独立计费）",
)
def get_topic(
    topic_code: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取专题包详情（AC-RQ13-2）。

    Args:
        topic_code: 专题编码。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：专题包视图。

    Raises:
        ApiError: 1002 专题包不存在或未上架。
    """
    require_base_consent(db, user.id)
    data = topic_service.get_topic(db, topic_code)
    if data is None:
        raise ApiError(*ERR_NOT_FOUND)
    return ok(data)

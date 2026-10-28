# -*- coding: utf-8 -*-
"""C 端知识科普 API 模块（每日一则小知识 / 科普全书）。

端点：

- GET /knowledge/daily    按北京时间日期稳定选取一条已发布科普知识
- GET /knowledge/entries  科普全书条目列表（可按业务模块筛选）与分类计数

数据源与取用规则见 ``app.services.knowledge_service`` 模块文档：只读取知识库
``kb_entry`` 中 ``topic_key`` 以 ``daily_science_`` 开头且已发布的条目。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_PARAM
from ...db import get_db
from ...models import AppUser
from ...services import knowledge_service
from .consent_api import require_base_consent

logger = logging.getLogger("jiaban.knowledge_api")

router = APIRouter(tags=["C端-知识科普"])


@router.get(
    "/knowledge/daily",
    summary="每日一则小知识",
    description="按北京时间日期从知识库稳定选取一条已发布科普条目；知识库为空时 entry 为 null",
)
def get_daily_knowledge(
    day: Optional[str] = Query(
        None,
        alias="date",
        description="可选日期（YYYY-MM-DD），仅用于联调与验证每日轮换；缺省取北京时间当天",
    ),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取当日小知识。

    同一天内所有用户、所有端返回同一条；不同日期按固定循环队列轮换，
    连续 N 天不重复（N 为可用条目数）。

    Args:
        day: 可选日期参数（YYYY-MM-DD）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{date, entry, total}；知识库为空时 entry 为 None。

    Raises:
        ApiError: 1301 未完成基础同意；1001 日期格式非法。
    """
    require_base_consent(db, user.id)
    try:
        target_day = knowledge_service.parse_day(day) or knowledge_service.today_cn()
    except ValueError:
        raise ApiError(ERR_PARAM[0], "日期格式应为 YYYY-MM-DD", ERR_PARAM[2])
    entry = knowledge_service.pick_daily(db, target_day)
    return ok(
        {
            "date": target_day.isoformat(),
            "entry": knowledge_service.to_public(entry) if entry else None,
            "total": knowledge_service.count_entries(db),
        }
    )


@router.get(
    "/knowledge/entries",
    summary="科普全书条目列表",
    description="按业务模块（母婴 / 幼儿 / 宠物 / 家庭共处）返回知识科普条目与分类计数",
)
def list_knowledge_entries(
    category: Optional[str] = Query(
        None, description="分类编码：infant / toddler / pet / family；缺省返回全部"
    ),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取科普全书条目列表。

    Args:
        category: 分类编码；缺省返回全部。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{categories, items, total}。

    Raises:
        ApiError: 1301 未完成基础同意；1001 分类编码非法。
    """
    require_base_consent(db, user.id)
    if category and not knowledge_service.is_category(category):
        raise ApiError(ERR_PARAM[0], "分类编码应为 infant / toddler / pet / family", ERR_PARAM[2])
    items = knowledge_service.list_entries(db, category)
    return ok(
        {
            "categories": knowledge_service.category_counts(db),
            "items": items,
            "total": len(items),
        }
    )

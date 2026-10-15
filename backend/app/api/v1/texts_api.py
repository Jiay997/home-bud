# -*- coding: utf-8 -*-
"""合规文案下发 API 模块。

提供文案 ID 批量下发接口（协议/免责声明/AI 生成标识等）：
- GET /texts?ids=DISCLAIMER_V1,AI_GEN_LABEL_V1   批量查询文案当前版本内容

业务口径：文案内容一律服务端下发，前端不得硬编码；
未登录可访问（协议文案需在登录/同意前展示）。
"""
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.envelope import ok
from ...core.errors import ApiError, ERR_PARAM
from ...db import get_db
from ...models import TextVersion

router = APIRouter(tags=["系统"])


@router.get("/texts", summary="批量下发文案", description="按文案 ID 批量查询当前生效版本内容（未登录可访问）")
def get_texts(
    ids: str = Query(default="", description="逗号分隔的文案 ID 列表，如 DISCLAIMER_V1,AI_GEN_LABEL_V1"),
    db: Session = Depends(get_db),
) -> dict:
    """批量下发文案 ID 当前版本内容（无需登录）。

    按 text_id 取最新一条版本（id 最大即最新生效版本）；
    库中不存在的 text_id 直接跳过，不出现在返回字典中。

    Args:
        ids: 逗号分隔的文案 ID 字符串。
        db: 数据库会话。

    Returns:
        统一包络：{"texts": {text_id: content}}。

    Raises:
        ApiError: 1001 ids 参数为空或全部非法。
    """
    # 解析并去重文案 ID（容忍空格与末尾逗号）
    text_ids: List[str] = [t.strip() for t in ids.split(",") if t.strip()]
    if not text_ids:
        raise ApiError(*ERR_PARAM)

    texts: Dict[str, str] = {}
    for text_id in text_ids:
        # 当前版本 = 同一 text_id 下最新记录（自增 id 最大）
        version = (
            db.query(TextVersion)
            .filter(TextVersion.text_id == text_id)
            .order_by(TextVersion.id.desc())
            .first()
        )
        if version is not None:
            # 未配置的文案 ID 跳过，避免前端渲染空内容
            texts[text_id] = version.content
    return ok({"texts": texts})

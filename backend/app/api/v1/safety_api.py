# -*- coding: utf-8 -*-
"""内容安全平台回调 API 模块（送检异步回调闭环收口）。

端点：
- POST /safety-scan/callback  平台异步裁决回调（HMAC-SHA256 验签 + 时间窗防重放）

口径：
- 机器对机器接口：无用户/管理员会话，以共享密钥签名鉴权
  （SAFETY_SCAN_CALLBACK_SECRET 未配置时显式 1901 拒绝，不静默放行）；
- 幂等：仅 reviewing 记录可裁决，重复回调返回现状（idempotent=true）；
- 业务回写：反馈场景同步 feedback.audit_status（见 apply_platform_callback）。
"""
import hmac
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.envelope import ok
from ...core.errors import ERR_DEPENDENCY, ERR_FORBIDDEN, ERR_NOT_FOUND, ERR_PARAM, ApiError
from ...db import get_db
from ...models import ContentAuditRecord
from ...services.safety_scan import (
    CALLBACK_TS_WINDOW_SECONDS,
    apply_platform_callback,
    callback_signature,
)

router = APIRouter(tags=["系统"])


class SafetyScanCallbackBody(BaseModel):
    """平台回调请求体。

    Attributes:
        record_id: 送检记录主键（submit 返回）。
        verdict: 平台裁决 pass/reject/manual。
        timestamp: Unix 秒级时间戳（与签名同为协议字段）。
        signature: HMAC-SHA256(secret, "{record_id}:{verdict}:{timestamp}") 十六进制。
        note: 平台备注（审计留痕，可空）。
    """

    record_id: int = Field(..., ge=1, description="送检记录主键")
    verdict: Literal["pass", "reject", "manual"] = Field(..., description="平台裁决")
    timestamp: int = Field(..., gt=0, description="Unix 秒级时间戳")
    signature: str = Field(..., min_length=1, max_length=128, description="HMAC-SHA256 签名")
    note: Optional[str] = Field(default=None, max_length=200, description="平台备注")


@router.post("/safety-scan/callback", summary="内容安全平台回调（HMAC 验签 + 幂等裁决）")
def safety_scan_callback(body: SafetyScanCallbackBody, db: Session = Depends(get_db)) -> dict:
    """平台异步回调：验签 → 时间窗校验 → 裁决记录并回写业务状态。

    Args:
        body: {record_id, verdict, timestamp, signature, note?}。
        db: 数据库会话。

    Returns:
        统一包络：{record_id, audit_result, idempotent, object_type, object_id}。

    Raises:
        ApiError: 1901 回调密钥未配置；1001 时间戳超出有效窗口；
                  1102 签名不匹配；1002 记录不存在。
    """
    settings = get_settings()
    # 通道未配置：显式拒绝（不静默放行，符合"配置不完整明确报错"口径）
    if not settings.safety_scan_callback_secret:
        raise ApiError(*ERR_DEPENDENCY)
    # 防重放：时间戳须落在有效窗口内
    if abs(int(time.time()) - body.timestamp) > CALLBACK_TS_WINDOW_SECONDS:
        raise ApiError(
            ERR_PARAM[0], "回调时间戳超出有效窗口", ERR_PARAM[2],
            details={"window_seconds": CALLBACK_TS_WINDOW_SECONDS},
        )
    # 验签：常量时间比对防时序侧信道
    expected = callback_signature(
        settings.safety_scan_callback_secret, body.record_id, body.verdict, body.timestamp
    )
    if not hmac.compare_digest(expected, body.signature):
        raise ApiError(*ERR_FORBIDDEN)
    record = db.get(ContentAuditRecord, body.record_id)
    if record is None:
        raise ApiError(*ERR_NOT_FOUND)
    # 幂等标记：回调前已非 reviewing 即重复回调
    idempotent = record.audit_result != "reviewing"
    record = apply_platform_callback(
        db, body.record_id, verdict=body.verdict, note=body.note or "platform callback"
    )
    db.commit()
    return ok(
        {
            "record_id": record.id,
            "audit_result": record.audit_result,
            "idempotent": idempotent,
            "object_type": record.object_type,
            "object_id": record.object_id,
        }
    )

# -*- coding: utf-8 -*-
"""合规要素 API 模块（RQ-01 AI 标识 / RQ-02 文案扫描 / RQ-11 隐私承诺）。

端点：

- GET  /compliance/ai-label            标识组件下发（页面固定位唯一真源）
- GET  /compliance/privacy-pledge      隐私承诺页数据（RQ-11）
- GET  /compliance/copy-checklist      文案合规检查清单（RQ-02 发布流程用）
- POST /compliance/png-metadata        为客户端 canvas PNG 补写隐式标识
"""
import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ...compliance import ai_label as labels
from ...compliance import copy_scan
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError
from ...db import get_db
from ...models import AppUser
from ...services import png_meta, privacy_service, share_service

logger = logging.getLogger("jiaban.compliance_api")

router = APIRouter(tags=["系统"])

# 客户端 PNG 体积上限（长图 ≤8MB，与档案媒体同口径）
PNG_MAX_BYTES = 8 * 1024 * 1024


@router.get(
    "/compliance/ai-label",
    summary="AI 生成标识组件下发",
    description="返回标识可见性、文案 text_id、页面固定位与备案号；前端只渲染 text_id 对应文案",
)
def get_ai_label(page: str = "answer") -> dict:
    """下发 AI 标识组件契约（AC-RQ01-1）。

    Args:
        page: 页面类型（home / answer / report / blocked / history / share_image）。

    Returns:
        统一包络：{visible, text_id, position, fallback_text, filing_no, pages}。

    Raises:
        无（未知页面类型按 answer 固定位处理）。
    """
    data = labels.ai_label(page)
    data["pages"] = labels.PAGE_POSITIONS
    data["min_ratio"] = labels.LONG_IMAGE_LABEL_MIN_RATIO
    data["min_count"] = labels.LONG_IMAGE_LABEL_MIN_COUNT
    return ok(data)


@router.get(
    "/compliance/privacy-pledge",
    summary="隐私承诺",
    description="四条（及以上）已实现承诺，每条附可操作跳转；未实现能力不写入承诺",
)
def get_privacy_pledge() -> dict:
    """获取隐私承诺页数据（AC-RQ11-1 / AC-RQ11-3）。

    Returns:
        统一包络：{version, items[], training_statement, honesty_note}。
    """
    return ok(privacy_service.pledge())


@router.get(
    "/compliance/copy-checklist",
    summary="文案合规检查清单",
    description="RQ-02 §3.2.3 五项检查清单（发布流程勾选留痕）与禁用表述词表",
)
def get_copy_checklist() -> dict:
    """获取文案合规检查清单与禁用表述词表（AC-RQ02-5）。

    Returns:
        统一包络：{checklist[], forbidden_phrases[], replacements{}}。
    """
    return ok(
        {
            "checklist": copy_scan.checklist(),
            "forbidden_phrases": list(copy_scan.FORBIDDEN_PHRASES),
            "replacements": dict(copy_scan.REPLACEMENTS),
            "scope": list(copy_scan.SCAN_SCOPES),
        }
    )


@router.post(
    "/compliance/png-metadata",
    summary="PNG 隐式标识写入",
    description="为客户端 canvas 导出的 PNG 补写 AI 隐式标识（tEXt），写入后回读断言，返回合规 PNG",
)
def embed_png_metadata(
    file: UploadFile = File(..., description="PNG 文件（≤8MB）"),
    content_type: str = "share_card",
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """为客户端 PNG 写入隐式标识（RQ-01 导出文件链路）。

    Args:
        file: PNG 文件。
        content_type: 内容类型枚举（share_card / qa_answer / assessment_report）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        统一包络：{render_id, metadata{}, label_check{}, png_base64, byte_size}。

    Raises:
        ApiError: 1001 非 PNG / 超过体积上限 / 空文件；
            1901 元数据写入或回读校验失败（不产出无标识文件）。
    """
    data = file.file.read()
    if not data:
        raise ApiError(code=1001, message="文件为空", http_status=422)
    if len(data) > PNG_MAX_BYTES:
        raise ApiError(code=1001, message="文件超过 8MB 上限", http_status=422)
    if not png_meta.is_png(data):
        raise ApiError(code=1001, message="仅接受 PNG 文件", http_status=422)
    try:
        png, meta = share_service.embed_client_png(
            db, user.id, data, content_type=content_type
        )
    except Exception as exc:  # noqa: BLE001 — 标识写入/校验失败按依赖错误处理
        logger.exception("png metadata embed failed")
        raise ApiError(code=1901, message=f"隐式标识写入失败：{exc}", http_status=500)
    db.commit()
    import base64

    return ok(
        {
            "render_id": meta["render_id"],
            "metadata": meta["metadata"],
            "label_check": meta["label_check"],
            "byte_size": len(png),
            "png_base64": base64.b64encode(png).decode("ascii"),
        }
    )

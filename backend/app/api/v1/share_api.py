# -*- coding: utf-8 -*-
"""分享长图 API 模块（RQ-09 + RQ-01 三链路标识）。

端点（均直接返回 `image/png`，非 JSON 包络）：

- GET /qa/sessions/{session_uid}/share-card.png   问答分享长图（被拦截不可分享）
- GET /history/report/{report_uid}/image.png      测评报告长图

响应保证（逐条可程序化校验）：

- PNG `tEXt` 内含 `software=BabeJiabanAI` / `ai_generated=1` / `content_type` /
  `generated_at` / `render_id`（AC-RQ01-3）；
- 显式标识面积 ≥15% 且出现 ≥2 处（AC-RQ01-2），校验失败即返回错误而不出图；
- 响应头附 `X-Render-Id` / `X-Share-Trace-Id` / `X-AI-Generated`，
  便于抽检脚本与端到端断言（E2E-20）。
"""
import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND
from ...db import get_db
from ...models import AppUser, QaSession
from ...services import share_service

logger = logging.getLogger("jiaban.share_api")

router = APIRouter(tags=["C端-问答"])

# 长图响应头（抽检与端到端断言用）
COMMON_HEADERS = {
    "Cache-Control": "private, max-age=300",
    "Content-Disposition": 'inline; filename="babe-share.png"',
}


def _png_response(png: bytes, meta: dict, record) -> Response:
    """构造 PNG 响应（附标识校验相关响应头）。

    Args:
        png: PNG 字节。
        meta: 渲染元信息。
        record: RenderRecord 实例（提供 share_trace_id）。

    Returns:
        Response（image/png）。
    """
    headers = dict(COMMON_HEADERS)
    headers["X-Render-Id"] = str(meta.get("render_id", ""))
    headers["X-Share-Trace-Id"] = str(getattr(record, "share_trace_id", ""))
    headers["X-AI-Generated"] = "1"
    headers["X-AI-Label-Ratio"] = f"{meta.get('ratio', 0):.4f}"
    headers["X-AI-Label-Count"] = str(meta.get("count", 0))
    return Response(content=png, media_type="image/png", headers=headers)


@router.get(
    "/qa/sessions/{session_uid}/share-card.png",
    summary="问答分享长图",
    description="服务端模板渲染（信任条+正文+免责+双标识）+ PNG tEXt 隐式标识；被拦截会话 403",
    responses={200: {"content": {"image/png": {}}}},
)
def qa_share_card(
    session_uid: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """生成问答分享长图（AC-RQ09-1/2/3）。

    Args:
        session_uid: 会话标识。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        Response（image/png，附标识校验响应头）。

    Raises:
        ApiError: 1002 会话不存在或越权；1102 会话不可分享（被拦截 / 未完成）；
            1901 标识校验失败（不产出无标识文件）。
    """
    session = db.query(QaSession).filter(QaSession.session_uid == session_uid).first()
    if session is None or session.user_id != user.id:
        raise ApiError(*ERR_NOT_FOUND)
    try:
        png, meta, record = share_service.render_qa_png(db, session, user.id)
    except share_service.ShareNotAllowed as exc:
        raise ApiError(code=1102, message=str(exc), http_status=403)
    except Exception as exc:  # noqa: BLE001 — 标识校验失败不出半成品
        logger.exception("qa share render failed")
        raise ApiError(code=1901, message=f"长图渲染失败：{exc}", http_status=500)
    db.commit()
    return _png_response(png, meta, record)


@router.get(
    "/history/report/{report_uid}/image.png",
    summary="测评报告长图",
    description="服务端模板渲染（信任条+分节+免责+双标识）+ PNG tEXt 隐式标识",
    responses={200: {"content": {"image/png": {}}}},
)
def report_long_image(
    report_uid: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """生成测评报告长图（RQ-01 长图链路 / F10）。

    Args:
        report_uid: 报告对外标识。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        Response（image/png，附标识校验响应头）。

    Raises:
        ApiError: 1002 报告不存在或越权；1901 标识校验失败。
    """
    from ...models import Report

    report = (
        db.query(Report)
        .filter(Report.report_uid == report_uid, Report.user_id == user.id)
        .first()
    )
    if report is None:
        raise ApiError(*ERR_NOT_FOUND)
    try:
        png, meta, record = share_service.render_report_png(db, user.id, report_uid)
    except share_service.ShareNotAllowed as exc:
        raise ApiError(code=1002, message=str(exc), http_status=404)
    except Exception as exc:  # noqa: BLE001 — 标识校验失败不出半成品
        logger.exception("report image render failed")
        raise ApiError(code=1901, message=f"长图渲染失败：{exc}", http_status=500)
    db.commit()
    return _png_response(png, meta, record)


@router.get(
    "/compliance/ai-label/check",
    summary="AI 标识三链路自检",
    description="校验页面契约 / 长图标识 / 导出元数据三条链路的关键断言（抽检辅助，非门禁替代）",
)
def ai_label_check(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """AI 标识三链路自检（E2E-20 辅助断言）。

    Args:
        user: 当前用户（仅用于鉴权，不参与断言）。
        db: 数据库会话。

    Returns:
        统一包络：{links[], passed, min_ratio, min_count}。
    """
    from ...compliance import ai_label as labels
    from ...services import png_meta, report_image

    sample, meta = report_image.render_report_long_image(
        report_uid="selfcheck",
        title="标识自检样张",
        sections=[{"title": "自检", "content": "用于校验显式与隐式标识。"}],
        trust_items=[labels.AI_LABEL_FALLBACK_TEXT],
    )
    readback = png_meta.read_text_metadata(sample)
    links = [
        {
            "link": "page_fixed_position",
            "passed": bool(labels.ai_label("answer")["visible"]),
            "detail": labels.ai_label("answer"),
        },
        {
            "link": "long_image_explicit",
            "passed": (
                meta["ratio"] >= labels.LONG_IMAGE_LABEL_MIN_RATIO
                and meta["count"] >= labels.LONG_IMAGE_LABEL_MIN_COUNT
            ),
            "detail": {"ratio": meta["ratio"], "count": meta["count"]},
        },
        {
            "link": "export_implicit_metadata",
            "passed": all(readback.get(key) for key in labels.required_png_keys()),
            "detail": readback,
        },
    ]
    return ok(
        {
            "links": links,
            "passed": all(item["passed"] for item in links),
            "min_ratio": labels.LONG_IMAGE_LABEL_MIN_RATIO,
            "min_count": labels.LONG_IMAGE_LABEL_MIN_COUNT,
        }
    )

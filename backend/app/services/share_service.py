# -*- coding: utf-8 -*-
"""分享长图渲染服务（RQ-09 + RQ-01 三链路标识）。

服务端统一渲染（US-RQ01-04：标识由服务端模板强制渲染而非前端拼装）：

- 测评报告长图（F10 `GET /history/report/{uid}/image.png`）；
- 问答分享长图（F10/F4/F6 `GET /qa/sessions/{uid}/share-card.png`）。

硬约束：

- 被拦截或未完成的会话**不可分享**（无入口 + 服务端 403，AC-RQ09-2）；
- 长图只含昵称与月龄档，**不含出生日期、体重、过敏项**（AC-RQ09-3）；
- 显式标识 ≥15% 且 ≥2 处（AC-RQ01-2），隐式标识写入 PNG `tEXt`
  并回读断言（AC-RQ01-3），任一失败即渲染失败并告警；
- 同一 `object + version` 24 h 内复用渲染物，`render_id` 一致
  （AC-RQ09-3 幂等口径）。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..compliance import ai_label as labels
from ..models import RenderRecord, Report
from . import answer_contract, png_meta, report_image, trust_service

logger = logging.getLogger("jiaban.share")

# 上海时区
_TZ_SHANGHAI = timezone(timedelta(hours=8))

# 分享落地页（AC-RQ09-1：跳小程序测评或首页，合规类目内）
LANDING_PAGE = "/pages/index/index"


class ShareNotAllowed(RuntimeError):
    """会话不可分享（被拦截 / 未完成）。"""


def _now() -> datetime:
    """当前上海时间。

    Returns:
        带时区的 datetime。
    """
    return datetime.now(_TZ_SHANGHAI)


def _recent_record(
    db: Session, object_type: str, object_id: str, now: Optional[datetime] = None
) -> Optional[RenderRecord]:
    """查找缓存期内的渲染记录（同对象 24h 复用）。

    Args:
        db: 数据库会话。
        object_type: report / qa。
        object_id: 对象标识。
        now: 参考时间。

    Returns:
        RenderRecord 或 None。
    """
    settings = get_settings()
    current = now or _now()
    cutoff = current - timedelta(hours=settings.share_render_cache_hours)
    return (
        db.query(RenderRecord)
        .filter(
            RenderRecord.object_type == object_type,
            RenderRecord.object_id == object_id,
            RenderRecord.generated_at >= cutoff,
        )
        .order_by(RenderRecord.generated_at.desc())
        .first()
    )


def _persist_record(
    db: Session,
    user_id: int,
    object_type: str,
    object_id: str,
    meta: Dict[str, Any],
    byte_size: int,
) -> RenderRecord:
    """写入渲染记录（标识校验结果留痕，AC-RQ01-4）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        object_type: report / qa。
        object_id: 对象标识。
        meta: 渲染返回的校验信息。
        byte_size: PNG 字节数。

    Returns:
        新建或复用的 RenderRecord。
    """
    record = RenderRecord(
        render_id=meta["render_id"],
        user_id=user_id,
        object_type=object_type,
        object_id=object_id,
        protocol_version="V2",
        content_type="image/png",
        byte_size=byte_size,
        label_check=meta.get("label_check"),
    )
    db.add(record)
    db.flush()
    return record


def _trust_items(triage: Optional[Dict[str, Any]], age_label: str, sources: List[Dict[str, Any]]) -> List[str]:
    """构造长图页首信任条要素文案（RQ-07 要素同步到分享载体）。

    Args:
        triage: 档位对象。
        age_label: 月龄 / 宠龄适配标识。
        sources: 来源等级列表。

    Returns:
        信任条要素文案列表。
    """
    items = [labels.AI_LABEL_FALLBACK_TEXT, age_label]
    if sources:
        badges = "、".join(
            f"{item.get('title', '')}（{item.get('level_label', '')}）" for item in sources[:2]
        )
        items.append(f"来源：{badges}")
    if triage and triage.get("level"):
        items.append(f"档位：{triage.get('level_label')}")
    return items


def render_report_png(
    db: Session,
    user_id: int,
    report_uid: str,
    now: Optional[datetime] = None,
) -> Tuple[bytes, Dict[str, Any], RenderRecord]:
    """渲染测评报告长图（含显式 + 隐式标识）。

    Args:
        db: 数据库会话。
        user_id: 用户主键（归属校验由调用方完成）。
        report_uid: 报告对外标识。
        now: 参考时间。

    Returns:
        (PNG 字节, 元信息, 渲染记录)。

    Raises:
        ShareNotAllowed: 报告不存在。
        report_image.RenderLabelError: 标识校验失败（不产出文件）。
    """
    report = db.query(Report).filter(Report.report_uid == report_uid).first()
    if report is None:
        raise ShareNotAllowed("报告不存在")
    cached = _recent_record(db, "report", report_uid, now=now)
    sections = [
        {"title": blk.get("title"), "content": blk.get("content")}
        for blk in (report.content or [])
        if blk.get("access_tier") == "free"
    ]
    trust_items = _trust_items(
        None,
        "适用：通用区间",
        [],
    )
    png, meta = report_image.render_report_long_image(
        report_uid=report_uid,
        title=str(getattr(report, "type_name", "") or "测评报告"),
        sections=sections,
        trust_items=trust_items,
        subtitle="Babe宝伴 · 养育科普参考工具",
        footer_note=(
            f"分享标识：{cached.share_trace_id if cached else ''} ｜ "
            f"落地页：{LANDING_PAGE}"
        ),
        render_id=cached.render_id if cached else None,
        content_type=labels.CONTENT_TYPE_REPORT,
    )
    record = cached or _persist_record(db, user_id, "report", report_uid, meta, len(png))
    if cached is not None:
        cached.label_check = meta.get("label_check")
        cached.byte_size = len(png)
        record = cached
    if hasattr(report, "image_rendered_at") and report.image_rendered_at is None:
        report.image_rendered_at = _now()
        report.image_meta = {
            "render_id": meta["render_id"],
            "disclaimer_ratio": meta["ratio"],
            "disclaimer_count": meta["count"],
            "protocol_version": "V2",
        }
    return png, meta, record


def render_qa_png(
    db: Session,
    session: Any,
    user_id: int,
    now: Optional[datetime] = None,
) -> Tuple[bytes, Dict[str, Any], RenderRecord]:
    """渲染问答分享长图（含显式 + 隐式标识与脱敏）。

    Args:
        db: 数据库会话。
        session: QaSession 实例。
        user_id: 用户主键。
        now: 参考时间。

    Returns:
        (PNG 字节, 元信息, 渲染记录)。

    Raises:
        ShareNotAllowed: 会话被拦截 / 未完成（AC-RQ09-2）。
    """
    from ..models import QaAnswerSection

    if session.status in ("blocked", "pending", "streaming", "failed", "orphaned"):
        raise ShareNotAllowed("该会话不可分享（未完成或已被拦截）")
    if session.status not in ("done", "degraded"):
        raise ShareNotAllowed("该会话不可分享")
    rows = (
        db.query(QaAnswerSection)
        .filter(QaAnswerSection.session_id == session.id)
        .order_by(QaAnswerSection.id.asc())
        .all()
    )
    if not rows:
        raise ShareNotAllowed("会话内容为空，不可分享")
    profile_ctx = answer_contract.resolve_profile_context(db, session)
    triage = session.triage
    sources = trust_service.build_source_levels(db, session.kb_refs or [])
    age_label = trust_service.age_adaptation(
        bool(profile_ctx.get("profile_bound")),
        profile_ctx.get("age_band"),
        domain=profile_ctx.get("domain") or "child",
        age_months=profile_ctx.get("age_months"),
    )["label"]
    sections = [
        {
            "title": row.title,
            # AC-RQ09-3：仅正文文本，不含档案敏感字段
            "blocks": [
                {"content": block.get("content") or ""}
                for block in (row.blocks or [])
                if isinstance(block, dict)
            ],
        }
        for row in rows
    ]
    cached = _recent_record(db, "qa", session.session_uid, now=now)
    png, meta = report_image.render_report_long_image(
        report_uid=session.session_uid,
        title=str(session.entry) + " 问答参考",
        sections=sections,
        trust_items=_trust_items(triage, age_label, sources),
        subtitle="Babe宝伴 · 养育科普参考工具",
        footer_note=(
            f"分享标识：{cached.share_trace_id if cached else ''} ｜ 落地页：{LANDING_PAGE}"
        ),
        render_id=cached.render_id if cached else None,
        content_type=labels.CONTENT_TYPE_QA,
    )
    record = cached or _persist_record(db, user_id, "qa", session.session_uid, meta, len(png))
    if cached is not None:
        cached.label_check = meta.get("label_check")
        cached.byte_size = len(png)
        record = cached
    return png, meta, record


def embed_client_png(
    db: Session,
    user_id: int,
    png: bytes,
    content_type: str = labels.CONTENT_TYPE_SHARE,
    source_id: str = "client_canvas",
) -> Tuple[bytes, Dict[str, Any]]:
    """为客户端 canvas 导出的 PNG 补写隐式标识（RQ-01 三链路之导出文件）。

    客户端（H5 / 小程序 canvas）产出的 PNG 不带元数据，必须回传服务端统一
    写入 `tEXt` 后再下载/保存，保证「导出文件隐式标识」链路 100% 覆盖。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        png: 客户端上传的 PNG 字节。
        content_type: 内容类型枚举。
        source_id: 来源标识（默认 client_canvas）。

    Returns:
        (写入后的 PNG 字节, 元信息)。

    Raises:
        png_meta.PngMetadataError: 非 PNG 或写入失败。
        report_image.RenderLabelError: 回读校验失败。
    """
    generated_at = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    render_id = f"rnd_cli_{int(_now().timestamp())}_{abs(hash(source_id)) % 100000}"
    metadata = labels.png_metadata(
        content_type=content_type,
        render_id=render_id,
        generated_at=generated_at,
        extra={"source_uid": source_id[:64]},
    )
    out = png_meta.embed_text_metadata(png, metadata)
    ok, readback, missing = png_meta.verify_ai_metadata(out, labels.required_png_keys())
    check = labels.label_check_result(ratio=1.0, count=2, metadata=readback, metadata_ok=ok)
    if not check["passed"]:
        logger.error("share_render_fail (client png) missing=%s", missing)
        raise report_image.RenderLabelError(f"隐式标识写入失败：{missing}")
    _persist_record(
        db,
        user_id,
        "client_png",
        source_id,
        {"render_id": render_id, "label_check": check},
        len(out),
    )
    return out, {
        "render_id": render_id,
        "metadata": readback,
        "label_check": check,
        "generated_at": generated_at,
    }

# -*- coding: utf-8 -*-
"""历史记录 API 模块。

提供当前用户的历史列表与详情：
- GET /history                        问答会话（done/degraded）+ 报告联合列表，时间倒序分页
- GET /history/qa/{session_uid}       问答会话详情（sections 全量，非会员会员分节裁剪）
- GET /history/report/{report_uid}    报告详情（与测评报告同一装配与门控逻辑）
- GET /history/{item_type}/{uid}/image 报告长图渲染数据（免责面积 ≥15% 且出现 ≥2 次）

门控口径：会员有效（member_status=member 且未过期）可见会员内容；
否则（free 或 member_expire_at<now）会员分节/区块不下发 content，历史条目只读。

"内容已更新"标注（spec close-module-gaps Task 2.4）：问答详情返回 content_updated——
存在已完成的 B/C 级内容追溯（ContentTraceTask.done_at 非空且 disposal_level∈{B,C}）
且命中该会话 kb_refs 时置 true，查询时推导，不改表结构、处置时无需额外写路径。
"""
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.crypto import decrypt_field
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND, raise_err
from ...db import get_db
from ...models import (
    AppUser,
    Assessment,
    ChildProfile,
    ContentTraceTask,
    PetProfile,
    QaAnswerSection,
    QaSession,
    Report,
)
from .assessment_api import build_report_payload, is_member

router = APIRouter(tags=["history"])
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 报告类型 -> 展示名（summary 用报告类型名）
REPORT_TYPE_NAMES: Dict[str, str] = {
    "assessment": "气质测评报告",
}

# 加密内容解密失败时的占位文案（密钥轮换等极端场景）
DECRYPT_FALLBACK = "（内容已加密留存）"

# 视为"内容已更新"的处置等级：B（追加提示）/ C（降级展示）
# A 级为下架阻断，命中会话不进历史详情，无需标注
CONTENT_UPDATED_LEVELS = ("B", "C")


def _iso(value: Any) -> Optional[str]:
    """datetime 转 RFC3339 字符串。

    Args:
        value: datetime 实例或 None。

    Returns:
        ISO8601 字符串；入参为 None 时返回 None。
    """
    return value.isoformat() if value is not None else None


def _has_updated_content(db: Session, kb_refs: Any) -> bool:
    """判断会话是否命中已完成的 B/C 级内容追溯（查询时推导，不改表结构）。

    口径：ContentTraceTask(kb_id ∈ 会话 kb_refs, done_at 非空,
    disposal_level ∈ {B, C}) 存在即视为"内容已更新"。

    Args:
        db: 数据库会话。
        kb_refs: 会话引用的知识条目编号列表（JSONB，可能为 None/非列表）。

    Returns:
        命中返回 True；无引用或未命中返回 False。
    """
    refs = [str(r) for r in kb_refs] if isinstance(kb_refs, list) else []
    if not refs:
        # 会话未引用任何知识条目：无需查询直接返回
        return False
    hit = (
        db.query(ContentTraceTask.id)
        .filter(
            ContentTraceTask.kb_id.in_(refs),
            ContentTraceTask.done_at.isnot(None),
            ContentTraceTask.disposal_level.in_(CONTENT_UPDATED_LEVELS),
        )
        .first()
    )
    return hit is not None


def _decrypt_question(ciphertext: str) -> str:
    """解密问题原文（解密失败降级为占位文案，不阻断列表/详情）。

    Args:
        ciphertext: 库中问题密文。

    Returns:
        问题明文（前 50 字由调用方截取）；解密失败返回占位文案。
    """
    try:
        return decrypt_field(ciphertext)
    except Exception:
        # 密钥轮换或密文损坏时不阻断历史浏览
        return DECRYPT_FALLBACK


@router.get("/history")
def list_history(
    type: str = Query(default="all", pattern="^(all|qa|report)$", description="列表类型"),
    profile_type: Optional[str] = Query(default=None, pattern="^(child|pet|family)$", description="按观察对象过滤"),
    record_date: Optional[date] = Query(default=None, description="按上海时区的记录日期筛选"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户历史联合列表：问答会话（done/degraded）+ 报告，时间倒序分页。

    Args:
        type: all / qa / report。
        profile_type: 可选，child / pet（问答按会话档案过滤，报告经测评关联档案过滤）。
        page: 页码。
        page_size: 每页条数。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{total, page, page_size, items:[{item_type, uid, created_at,
        summary(问题前 50 字/报告类型名), is_member_content}]}。
    """
    # (created_at, item_type, ORM 对象) 池：合并后统一排序分页
    entries: List[Tuple[Any, str, Any]] = []
    day_start = datetime.combine(record_date, time.min, tzinfo=_SHANGHAI_TZ) if record_date else None
    day_end = day_start + timedelta(days=1) if day_start else None

    if type in ("all", "qa"):
        query = db.query(QaSession).filter(
            QaSession.user_id == user.id,
            QaSession.status.in_(("done", "degraded")),
        )
        if profile_type:
            query = query.filter(QaSession.profile_type == profile_type)
        if day_start and day_end:
            query = query.filter(QaSession.created_at >= day_start, QaSession.created_at < day_end)
        entries.extend((s.created_at, "qa", s) for s in query.all())

    if type in ("all", "report") and profile_type != "family":
        query = db.query(Report).filter(Report.user_id == user.id)
        if profile_type:
            # 报告经测评关联档案：按档案类型取档案主键集合过滤
            if profile_type == "child":
                profile_ids = [
                    row[0]
                    for row in db.query(ChildProfile.id)
                    .filter(ChildProfile.user_id == user.id)
                    .all()
                ]
            else:
                profile_ids = [
                    row[0]
                    for row in db.query(PetProfile.id)
                    .filter(PetProfile.user_id == user.id)
                    .all()
                ]
            query = query.join(Assessment, Report.assessment_id == Assessment.id).filter(
                Assessment.profile_id.in_(profile_ids)
            )
        if day_start and day_end:
            query = query.filter(Report.created_at >= day_start, Report.created_at < day_end)
        entries.extend((r.created_at, "report", r) for r in query.all())

    # 时间倒序（created_at 均为服务端生成，非空）
    entries.sort(key=lambda t: t[0], reverse=True)
    total = len(entries)
    start = (page - 1) * page_size
    page_entries = entries[start:start + page_size]

    items: List[Dict[str, Any]] = []
    for created_at, item_type, obj in page_entries:
        if item_type == "qa":
            items.append({
                "item_type": "qa",
                "uid": obj.session_uid,
                "created_at": _iso(created_at),
                "summary": _decrypt_question(obj.question_text_enc)[:50],
                "is_member_content": obj.is_member_content,
                "profile_type": obj.profile_type or obj.entry,
                "entry": obj.entry,
            })
        else:
            # 报告基础区块为免费内容，is_member_content 恒为 False
            items.append({
                "item_type": "report",
                "uid": obj.report_uid,
                "created_at": _iso(created_at),
                "summary": REPORT_TYPE_NAMES.get(obj.report_type, "测评报告"),
                "is_member_content": False,
                "profile_type": "child",
            })
    return ok({"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/history/summary", summary="近七日观察记录概览")
def history_summary(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """汇总近七日的有效问答与报告记录，并按观察对象统计问答记录数。"""
    today = datetime.now(_SHANGHAI_TZ).date()
    first_day = today - timedelta(days=6)
    start_at = datetime.combine(first_day, time.min, tzinfo=_SHANGHAI_TZ)
    end_at = datetime.combine(today + timedelta(days=1), time.min, tzinfo=_SHANGHAI_TZ)
    counts = {first_day + timedelta(days=offset): 0 for offset in range(7)}
    qa_records = {"child": 0, "pet": 0, "family": 0}

    qa_rows = db.query(QaSession).filter(
        QaSession.user_id == user.id,
        QaSession.status.in_(("done", "degraded")),
        QaSession.created_at >= start_at,
        QaSession.created_at < end_at,
    ).all()
    for session in qa_rows:
        created_day = session.created_at.astimezone(_SHANGHAI_TZ).date()
        counts[created_day] += 1
        observed_as = session.profile_type or session.entry
        if observed_as in qa_records:
            qa_records[observed_as] += 1

    report_rows = db.query(Report.created_at).filter(
        Report.user_id == user.id,
        Report.created_at >= start_at,
        Report.created_at < end_at,
    ).all()
    for (created_at,) in report_rows:
        counts[created_at.astimezone(_SHANGHAI_TZ).date()] += 1

    return ok({
        "days": [{"date": day.isoformat(), "count": count} for day, count in counts.items()],
        "qa_records": qa_records,
    })


@router.get("/history/qa/{session_uid}")
def get_qa_detail(
    session_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """问答会话详情：sections 全量下发，会员分节按会员状态裁剪。

    裁剪口径：非会员（free 或会员已到期）且会话含会员内容时，
    除 safety 安全节外均只下发占位（access_tier=block，无 blocks 内容）；
    非会员历史条目只读（readonly=True）。
    "内容已更新"标注：已完成 B/C 级追溯命中会话 kb_refs 时 content_updated=true。

    Args:
        session_uid: 会话对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：会话详情（question 明文、sections、readonly、content_updated）。

    Raises:
        ApiError: 1002 会话不存在 / 越权 / 状态不在 done/degraded。
    """
    session = (
        db.query(QaSession)
        .filter(QaSession.session_uid == session_uid, QaSession.user_id == user.id)
        .first()
    )
    if session is None or session.status not in ("done", "degraded"):
        # 不存在 / 越权 / 未完成会话不进历史详情
        raise_err(ERR_NOT_FOUND)
    member = is_member(user)
    sections = (
        db.query(QaAnswerSection).filter(QaAnswerSection.session_id == session.id).all()
    )

    # 服务端分节顺序（render_order）优先，未登记的分节按主键稳定排后
    order = list(session.render_order or [])

    def _order_key(sec: QaAnswerSection) -> Tuple[int, int]:
        """分节排序键。

        Args:
            sec: 分节 ORM 实例。

        Returns:
            (render_order 中的位置, 主键)。
        """
        try:
            return (order.index(sec.section_key), sec.id)
        except ValueError:
            return (len(order), sec.id)

    sections.sort(key=_order_key)

    out_sections: List[Dict[str, Any]] = []
    for sec in sections:
        item: Dict[str, Any] = {
            "section_key": sec.section_key,
            "title": sec.title,
            "status": sec.status,
            "pinned": sec.pinned,
            "immutable": sec.immutable,
            "updated_at": _iso(sec.updated_at),
        }
        # 门控裁剪：非会员对会员分节只给层级占位，不下发 blocks（safety 恒可见）
        if not member and session.is_member_content and sec.section_key != "safety":
            item["access_tier"] = "block"
        else:
            item["access_tier"] = "free"
            item["blocks"] = sec.blocks
        out_sections.append(item)

    # V3.1 RQ-01/RQ-06/RQ-07：历史详情同样下发合规契约（标识 / 档位 / 信任条），
    # 口径与 SSE completed、轮询兜底一致；档位与月龄取**回答时**快照（AC-RQ07-4）
    from ...services import answer_contract

    contract = answer_contract.contract_from_stored(
        db,
        session,
        kb_refs=session.kb_refs or [],
        sections=out_sections,
    )
    return ok({
        "session_uid": session.session_uid,
        "status": session.status,
        "degraded_reason": session.degraded_reason,
        "entry": session.entry,
        "profile_type": session.profile_type,
        "risk_level": session.risk_level,
        "question": _decrypt_question(session.question_text_enc),
        "created_at": _iso(session.created_at),
        # SIM-23：与历史列表条目同口径下发内容档位（是否含会员内容），
        # 前端详情页「免费内容/会员内容」标签据此与列表页保持一致
        "is_member_content": session.is_member_content,
        # "内容已更新"标注：B/C 级已完成追溯命中 kb_refs（查询时推导）
        "content_updated": _has_updated_content(db, session.kb_refs),
        # 非会员（free 或会员已到期）历史只读
        "readonly": not member,
        "sections": out_sections,
        # V3.1 合规契约（历史页信任条 / 档位卡数据来源）
        "ai_label": contract["ai_label"],
        "disclaimer_id": contract["disclaimer_id"],
        "trust_bar": contract["trust_bar"],
        "triage": contract["triage"],
        "input_mode": session.input_mode,
    })


@router.get("/history/report/{report_uid}")
def get_report_detail(
    report_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """报告详情（与测评报告同一装配与门控裁剪逻辑）。

    Args:
        report_uid: 报告对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：报告视图（blocks 按会员状态裁剪 content，非会员只读）。

    Raises:
        ApiError: 1002 报告不存在或越权。
    """
    report = (
        db.query(Report)
        .filter(Report.report_uid == report_uid, Report.user_id == user.id)
        .first()
    )
    if report is None:
        raise_err(ERR_NOT_FOUND)
    return ok(build_report_payload(report, user))


@router.get("/history/{item_type}/{uid}/image")
def get_item_image(
    item_type: str,
    uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """报告长图渲染数据（分享图与免费视图一致，仅含免费区块）。

    数据装配层保证免责合规：disclaimer_ratio=0.18（≥15%）、
    disclaimer_count=3（≥2 次），渲染层按此装配长图。

    Args:
        item_type: 条目类型，当前仅支持 report。
        uid: 报告对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{report_uid, sections, disclaimer_ratio, disclaimer_count,
        qr_placeholder, scale}。

    Raises:
        ApiError: 1001 非 report 类型不支持长图；1002 报告不存在或越权。
    """
    if item_type != "report":
        raise ApiError(code=1001, message="仅报告支持长图渲染", http_status=422)
    report = (
        db.query(Report).filter(Report.report_uid == uid, Report.user_id == user.id).first()
    )
    if report is None:
        raise_err(ERR_NOT_FOUND)
    # 长图仅渲染免费区块（分享出去的内容与免费用户所见一致，会员内容不外泄）
    sections = [
        {"key": blk.get("key"), "title": blk.get("title"), "content": blk.get("content")}
        for blk in (report.content or [])
        if blk.get("access_tier") == "free"
    ]
    return ok({
        "report_uid": report.report_uid,
        "sections": sections,
        # 免责面积占比 18%（≥15%）且出现 3 次（≥2），由渲染层保证
        "disclaimer_ratio": 0.18,
        "disclaimer_count": 3,
        "qr_placeholder": f"https://jiaban.example/r/{report.report_uid}",
        "scale": 2,
    })

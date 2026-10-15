# -*- coding: utf-8 -*-
"""知识库管理路由模块。

覆盖知识库运营闭环（PRD §14 / PA-01~PA-03）：
- 条目 CRUD（草稿态，专家域绑定校验，乐观锁 1601）
- 敏感词预检（保存时命中 LexiconTerm 敏感词返回 warning）
- 提交送审（创建 KbReview 工单，上线前 100% 审核）
- 审核（pass 需二次确认 + 发布新版本 + 失效检索缓存；reject 留回滚目标）
- 下架（触发内容追溯 ContentTraceTask: violation）
- 版本回滚（记录式回滚 + 审计快照 + 追溯任务 expert_reject）
- 审核工单列表与追溯任务分级处置
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.cache import cache
from ...core.crypto import decrypt_field
from ...core.deps import (
    check_domain_scope,
    get_admin,
    require_admin_perm,
    require_confirm,
    write_audit,
)
from ...core.envelope import ok
from ...core.errors import (
    ERR_ADMIN_LOCK,
    ERR_NOT_FOUND,
    ApiError,
)
from ...db import get_db
from ...models import (
    AdminAuditLog,
    AdminUser,
    ContentTraceTask,
    KbEntry,
    KbReview,
    LexiconTerm,
    QaSession,
)
from ...services import rag_index
from ...services.retriever import hashing_embed

# 知识库与追溯任务共用一个路由器（main 只注册 kb_api.router）
router = APIRouter(prefix="/admin", tags=["后台-知识库"])


def _now() -> datetime:
    """获取当前 UTC 时间。

    Returns:
        带时区的 datetime。
    """
    return datetime.now(timezone.utc)


def _iso(dt) -> Optional[str]:
    """datetime 转 ISO 字符串（JSON 序列化辅助）。

    Args:
        dt: 时间对象，可为 None。

    Returns:
        ISO8601 字符串；入参为 None 时返回 None。
    """
    return dt.isoformat() if dt is not None else None


def _gen_kb_id() -> str:
    """生成知识条目业务编号。

    Returns:
        形如 KB + 12 位大写十六进制的唯一编号。
    """
    return f"KB{uuid.uuid4().hex[:12].upper()}"


def _gen_review_no() -> str:
    """生成审核工单号。

    Returns:
        形如 KB + 12 位大写十六进制的唯一编号。
    """
    return f"KB{uuid.uuid4().hex[:12].upper()}"


def _check_sensitive_terms(db: Session, content: str) -> List[str]:
    """敏感词预检：content 命中有效敏感词则返回命中词列表。

    Args:
        db: 数据库会话。
        content: 待检测文本。

    Returns:
        命中的敏感词明文列表（解密失败的词条跳过）。
    """
    terms = (
        db.query(LexiconTerm)
        .filter(LexiconTerm.lexicon_type == "sensitive", LexiconTerm.effective.is_(True))
        .all()
    )
    hits = []
    for t in terms:
        try:
            plain = decrypt_field(t.term_enc)
        except Exception:
            # 密文损坏的词条跳过，不阻断保存
            continue
        if plain and plain in content:
            hits.append(plain)
    return hits


def _entry_dict(e: KbEntry) -> dict:
    """知识条目序列化。

    Args:
        e: KbEntry ORM 实例。

    Returns:
        条目字典（含 version/status 等管理端字段）。
    """
    return {
        "id": e.id,
        "kb_id": e.kb_id,
        "kb_kind": e.kb_kind,
        "domain": e.domain,
        "topic_key": e.topic_key,
        "topic_category": e.topic_category,
        "age_band": e.age_band,
        "pet_stage": e.pet_stage,
        "species": e.species,
        "title": e.title,
        "content": e.content,
        "preconditions": e.preconditions,
        "source_type": e.source_type,
        "source_ref": e.source_ref,
        "status": e.status,
        "is_high_risk": e.is_high_risk,
        "version": e.version,
        "published_at": _iso(e.published_at),
        "created_at": _iso(e.created_at) if hasattr(e, "created_at") else None,
    }


def _content_digest(content: Optional[str], limit: int = 200) -> Optional[str]:
    """截取内容摘要用于审计快照（避免 JSONB 存全文）。

    Args:
        content: 原文。
        limit: 截断长度。

    Returns:
        摘要字符串；入参为 None 时返回 None。
    """
    return content[:limit] if content else None


def _count_sessions_referencing(db: Session, kb_id: str) -> int:
    """统计 kb_refs 引用了指定条目的会话数（JSONB 简化处理：全查后 Python 过滤）。

    Args:
        db: 数据库会话。
        kb_id: 知识条目业务编号。

    Returns:
        引用会话数。
    """
    refs_rows = db.query(QaSession.kb_refs).all()
    count = 0
    for (kb_refs,) in refs_rows:
        if isinstance(kb_refs, list) and kb_id in kb_refs:
            count += 1
        elif isinstance(kb_refs, dict) and kb_id in [str(v) for v in kb_refs.values()]:
            count += 1
    return count


# ==================== 请求体模型 ====================


class KbCreateBody(BaseModel):
    """知识条目创建请求体。"""

    kb_kind: str = Field(..., description="child / pet / assessment_pool / risk_lexicon / sensitive_lexicon")
    domain: str = Field(..., description="领域：child / pet")
    topic_key: str = Field(..., description="主题键")
    topic_category: str = Field(..., description="主题类目")
    title: str = Field(..., min_length=1, description="标题")
    content: str = Field(..., min_length=1, description="正文")
    preconditions: str = Field(..., min_length=1, description="适用前提（一票否决项，必填）")
    source_type: str = Field(..., description="来源类型")
    source_ref: str = Field(..., min_length=1, description="来源引用（必填，可溯源）")
    age_band: Optional[str] = Field(None, description="年龄段")
    pet_stage: Optional[str] = Field(None, description="宠物生命周期")
    species: Optional[str] = Field(None, description="物种（cat/dog）")
    stance: Optional[str] = Field(None, description="立场：support / neutral / against")
    is_high_risk: bool = Field(False, description="高危类目（100% 审核 + 合格线 90 分）")


class KbUpdateBody(BaseModel):
    """知识条目更新请求体（乐观锁）。"""

    version: int = Field(..., ge=1, description="客户端持有的版本号（乐观锁比对）")
    title: Optional[str] = Field(None, description="标题")
    content: Optional[str] = Field(None, description="正文")
    preconditions: Optional[str] = Field(None, description="适用前提")
    topic_category: Optional[str] = Field(None, description="主题类目")
    source_type: Optional[str] = Field(None, description="来源类型")
    source_ref: Optional[str] = Field(None, description="来源引用")
    age_band: Optional[str] = Field(None, description="年龄段")
    pet_stage: Optional[str] = Field(None, description="宠物生命周期")
    species: Optional[str] = Field(None, description="物种")
    stance: Optional[str] = Field(None, description="立场")
    is_high_risk: Optional[bool] = Field(None, description="高危类目标记")


class KbReviewActionBody(BaseModel):
    """知识条目审核请求体。"""

    verdict: str = Field(..., description="审核结论：pass / reject")
    score: Optional[int] = Field(None, ge=0, le=100, description="审核评分")
    reject_code: Optional[str] = Field(None, description="驳回理由码（reject 必填）")
    confirm_token: Optional[str] = Field(None, description="二次确认凭证（pass 必填）")


class KbUnpublishBody(BaseModel):
    """知识条目下架请求体。"""

    reason: str = Field(..., min_length=1, description="下架原因（审计必填）")
    confirm_token: Optional[str] = Field(None, description="二次确认凭证")


class KbRollbackBody(BaseModel):
    """知识条目版本回滚请求体。"""

    target_version: int = Field(..., ge=1, description="回滚目标版本号（审计留档）")
    version: int = Field(..., ge=1, description="客户端持有的当前版本号（乐观锁）")
    reason: str = Field(..., min_length=1, description="回滚原因（审计必填）")
    confirm_token: Optional[str] = Field(None, description="二次确认凭证")


class TraceDisposeBody(BaseModel):
    """内容追溯任务分级处置请求体。"""

    disposal_level: str = Field(..., description="处置等级：A / B / C")
    confirm_token: Optional[str] = Field(None, description="二次确认凭证")


# ==================== 条目管理 ====================


@router.get("/kb/entries", summary="知识条目列表", description="分页查询（专家域隔离），含待审核角标计数")
def list_kb_entries(
    kb_kind: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询知识条目列表（含待审核角标计数）。

    专家角色仅可见自身绑定领域的条目。

    Args:
        kb_kind: 条目类型过滤。
        domain: 领域过滤。
        status: 状态过滤。
        keyword: 标题模糊匹配。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size, pending_badge}。

    Raises:
        ApiError: 1103 缺少 kb:view 权限。
    """
    require_admin_perm(admin, "kb:view")
    q = db.query(KbEntry)
    # 专家域隔离：仅本人绑定领域可见
    if admin.role.startswith("expert") and admin.domain_scope:
        q = q.filter(KbEntry.domain == admin.domain_scope)
    if kb_kind:
        q = q.filter(KbEntry.kb_kind == kb_kind)
    if domain:
        q = q.filter(KbEntry.domain == domain)
    if status:
        q = q.filter(KbEntry.status == status)
    if keyword:
        q = q.filter(KbEntry.title.ilike(f"%{keyword}%"))
    total = q.count()
    rows = (
        q.order_by(KbEntry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    # 待审核角标（领域隔离下同样只统计可见范围）
    pending_q = db.query(func.count(KbEntry.id)).filter(KbEntry.status == "pending_review")
    if admin.role.startswith("expert") and admin.domain_scope:
        pending_q = pending_q.filter(KbEntry.domain == admin.domain_scope)
    pending_badge = pending_q.scalar() or 0
    return ok(
        {
            "items": [_entry_dict(e) for e in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pending_badge": pending_badge,
        }
    )


@router.post("/kb/entries", summary="创建知识条目", description="初始 draft 态；专家仅可创建绑定领域条目")
def create_kb_entry(
    body: KbCreateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """创建知识条目（初始 draft 态）。

    专家仅可创建绑定领域条目（check_domain_scope，越权 1603）。

    Args:
        body: 创建请求体（preconditions/source_ref 必填）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, status}。

    Raises:
        ApiError: 1103 缺少 kb:edit 权限；1603 专家跨领域。
    """
    require_admin_perm(admin, "kb:edit")
    check_domain_scope(admin, body.domain)
    entry = KbEntry(
        kb_id=_gen_kb_id(),
        kb_kind=body.kb_kind,
        domain=body.domain,
        topic_key=body.topic_key,
        topic_category=body.topic_category,
        title=body.title,
        content=body.content,
        preconditions=body.preconditions,
        source_type=body.source_type,
        source_ref=body.source_ref,
        age_band=body.age_band,
        pet_stage=body.pet_stage,
        species=body.species,
        stance=body.stance or "support",
        is_high_risk=body.is_high_risk,
        status="draft",
        created_by=admin.id,
    )
    # 降级向量预计算（与 ensure_embeddings 同口径：title + content，
    # hashing 降级链的检索源），并 best-effort 同步 LlamaIndex 向量索引
    # （draft 状态 sync_entry 内部按状态分派 delete，published 后重新发布时 upsert）
    entry.embedding = hashing_embed(f"{entry.title}\n{entry.content}")
    entry.vector_synced_at = _now()
    db.add(entry)
    db.flush()
    rag_index.sync_entry(db, entry.kb_id)
    write_audit(
        db,
        admin,
        "kb_create",
        "kb_entry",
        entry.kb_id,
        reason="-",
        after={
            "kb_id": entry.kb_id,
            "title": entry.title,
            "kb_kind": entry.kb_kind,
            "domain": entry.domain,
            "status": "draft",
        },
    )
    return ok({"kb_id": entry.kb_id, "status": entry.status})


@router.put("/kb/entries/{kb_id}", summary="更新知识条目", description="乐观锁；命中敏感词返回 warnings；改后回草稿")
def update_kb_entry(
    kb_id: str,
    body: KbUpdateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """更新知识条目（乐观锁 1601）：更新后回 draft 重新走审核。

    命中有效敏感词时在响应 warnings 中返回（不阻断保存，供编辑器提示）。

    Args:
        kb_id: 条目业务编号。
        body: 更新请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, version, status, warnings}。

    Raises:
        ApiError: 1002 条目不存在；1103 无权限；1601 版本冲突；1603 专家跨领域。
    """
    require_admin_perm(admin, "kb:edit")
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        raise ApiError(*ERR_NOT_FOUND)
    check_domain_scope(admin, entry.domain)
    # 乐观锁：版本不符直接 1601，不产生副作用
    if body.version != entry.version:
        raise ApiError(*ERR_ADMIN_LOCK)
    before = {
        "version": entry.version,
        "status": entry.status,
        "title": entry.title,
        "content": _content_digest(entry.content),
    }
    if body.title is not None:
        entry.title = body.title
    if body.content is not None:
        entry.content = body.content
    if body.preconditions is not None:
        entry.preconditions = body.preconditions
    if body.topic_category is not None:
        entry.topic_category = body.topic_category
    if body.source_type is not None:
        entry.source_type = body.source_type
    if body.source_ref is not None:
        entry.source_ref = body.source_ref
    if body.age_band is not None:
        entry.age_band = body.age_band
    if body.pet_stage is not None:
        entry.pet_stage = body.pet_stage
    if body.species is not None:
        entry.species = body.species
    if body.stance is not None:
        entry.stance = body.stance
    if body.is_high_risk is not None:
        entry.is_high_risk = body.is_high_risk
    # 任何修改后回草稿，必须重新走审核
    entry.status = "draft"
    entry.version += 1
    # 标题/正文可能变更：重算降级向量（与 ensure_embeddings 同口径），
    # 先 flush 让 ORM 修改落库（autoflush 已关闭），再 best-effort 同步
    # LlamaIndex 向量索引（改后回草稿 → sync_entry 分派 delete，重新发布时 upsert）
    entry.embedding = hashing_embed(f"{entry.title}\n{entry.content}")
    entry.vector_synced_at = _now()
    db.flush()
    rag_index.sync_entry(db, entry.kb_id)
    # 敏感词预检（仅对当前正文检测）
    warnings = _check_sensitive_terms(db, entry.content)
    write_audit(
        db,
        admin,
        "kb_update",
        "kb_entry",
        entry.kb_id,
        reason="-",
        before=before,
        after={
            "version": entry.version,
            "status": entry.status,
            "title": entry.title,
            "content": _content_digest(entry.content),
        },
    )
    return ok(
        {"kb_id": entry.kb_id, "version": entry.version, "status": entry.status, "warnings": warnings}
    )


@router.post("/kb/entries/{kb_id}/submit", summary="提交条目送审", description="draft → pending_review，创建审核工单")
def submit_kb_entry(
    kb_id: str,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """提交知识条目送审：draft → pending_review，创建审核工单。

    Args:
        kb_id: 条目业务编号。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, status, review_no}。

    Raises:
        ApiError: 1002 条目不存在；1001 非 draft 状态；1103 无权限；1603 跨领域。
    """
    require_admin_perm(admin, "kb:edit")
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        raise ApiError(*ERR_NOT_FOUND)
    check_domain_scope(admin, entry.domain)
    if entry.status != "draft":
        raise ApiError(1001, "仅草稿状态可提交审核", 409)
    entry.status = "pending_review"
    review = KbReview(
        review_no=_gen_review_no(),
        kb_id=entry.kb_id,
        kb_kind=entry.kb_kind,
        version=entry.version,
        review_round="上线前全量",
        reviewer_role=admin.role,
        submitted_at=_now(),
    )
    db.add(review)
    write_audit(
        db,
        admin,
        "kb_submit",
        "kb_entry",
        entry.kb_id,
        before={"status": "draft"},
        after={"status": "pending_review", "review_no": review.review_no},
    )
    return ok({"kb_id": entry.kb_id, "status": entry.status, "review_no": review.review_no})


@router.post("/kb/entries/{kb_id}/review", summary="审核知识条目", description="pass 发布新版本（需二次确认）；reject 驳回留回滚目标")
def review_kb_entry(
    kb_id: str,
    body: KbReviewActionBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """审核知识条目：pass 发布新版本；reject 驳回并留回滚目标版本。

    pass 属上线动作，必须二次确认（1602）；发布后失效 QA 检索缓存。

    Args:
        kb_id: 条目业务编号。
        body: 审核请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, status, version}。

    Raises:
        ApiError: 1002 不存在/无待审工单；1001 reject 缺理由码；
                  1103 缺少 kb:review；1602 缺少二次确认；1603 跨领域。
    """
    require_admin_perm(admin, "kb:review")
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        raise ApiError(*ERR_NOT_FOUND)
    check_domain_scope(admin, entry.domain)
    if body.verdict == "pass":
        # 上线动作必须二次确认
        require_confirm(body.confirm_token, "kb_review_pass")
    review = (
        db.query(KbReview)
        .filter(KbReview.kb_id == entry.kb_id, KbReview.verdict.is_(None))
        .order_by(KbReview.id.desc())
        .first()
    )
    if review is None:
        raise ApiError(1002, "该条目无待审核工单", 404)
    now = _now()
    before = {"version": entry.version, "status": entry.status}
    if body.verdict == "pass":
        entry.status = "published"
        entry.version += 1  # 发布生成新版本（审核针对提交时版本）
        entry.published_at = now
        review.verdict = "pass"
        review.score = body.score
        review.reviewed_at = now
        review.reviewer_id = admin.id
        # 失效 QA 检索缓存：以 kb_version 计数轮换实现（简化处理）
        cache.set("kb_version", str(int(now.timestamp())), None)
    elif body.verdict == "reject":
        if not body.reject_code:
            raise ApiError(1001, "驳回必须填写 reject_code", 422)
        entry.status = "rejected"
        review.verdict = "reject"
        review.score = body.score
        review.reject_code = body.reject_code
        review.rollback_target_version = entry.version
        review.reviewed_at = now
        review.reviewer_id = admin.id
    else:
        raise ApiError(1001, "verdict 必须为 pass/reject", 422)
    # 状态流转后 best-effort 同步 LlamaIndex 向量索引：
    # pass → published upsert 入索引；reject → 非published delete 出索引
    db.flush()
    rag_index.sync_entry(db, entry.kb_id)
    write_audit(
        db,
        admin,
        f"kb_review_{body.verdict}",
        "kb_entry",
        entry.kb_id,
        reason=body.reject_code or f"verdict={body.verdict}",
        before=before,
        after={"version": entry.version, "status": entry.status},
        confirm_used=(body.verdict == "pass"),
    )
    return ok({"kb_id": entry.kb_id, "status": entry.status, "version": entry.version})


@router.post("/kb/entries/{kb_id}/unpublish", summary="下架知识条目", description="触发内容追溯任务（violation），统计影响会话数")
def unpublish_kb_entry(
    kb_id: str,
    body: KbUnpublishBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """下架知识条目并触发内容追溯任务（trigger=violation）。

    统计 qa_session.kb_refs 引用该条目的会话数作为影响面。

    Args:
        kb_id: 条目业务编号。
        body: 下架请求体（reason + confirm_token）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, status, affected_sessions}。

    Raises:
        ApiError: 1002 不存在；1103 缺少 kb:publish；1602 缺少二次确认；1603 跨领域。
    """
    require_admin_perm(admin, "kb:publish")
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        raise ApiError(*ERR_NOT_FOUND)
    check_domain_scope(admin, entry.domain)
    require_confirm(body.confirm_token, "kb_unpublish")
    before = {"status": entry.status}
    entry.status = "unpublished"
    # 下架：best-effort 从向量索引移除（下架内容绝不从检索泄露）
    db.flush()
    rag_index.sync_entry(db, entry.kb_id)
    # 内容追溯：影响会话数（JSONB 简化全查过滤）
    affected_sessions = _count_sessions_referencing(db, entry.kb_id)
    db.add(
        ContentTraceTask(
            kb_id=entry.kb_id,
            trigger="violation",
            affected_sessions=affected_sessions,
            affected_reports=0,
        )
    )
    write_audit(
        db,
        admin,
        "kb_unpublish",
        "kb_entry",
        entry.kb_id,
        reason=body.reason,
        before=before,
        after={"status": "unpublished", "affected_sessions": affected_sessions},
        confirm_used=True,
    )
    return ok({"kb_id": entry.kb_id, "status": entry.status, "affected_sessions": affected_sessions})


@router.post("/kb/entries/{kb_id}/rollback", summary="回滚条目版本", description="记录式回滚（version+1 回草稿），触发专家驳回追溯")
def rollback_kb_entry(
    kb_id: str,
    body: KbRollbackBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """回滚知识条目版本（记录式：version+1，before/after 快照存审计）。

    不建历史版本表；回滚后条目回 draft 需重新审核，并触发
    ContentTraceTask（trigger=expert_reject）。

    Args:
        kb_id: 条目业务编号。
        body: 回滚请求体（含乐观锁 version）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, version, status}。

    Raises:
        ApiError: 1002 不存在；1103 缺少 kb:rollback；1601 版本冲突；
                  1602 缺少二次确认；1603 跨领域。
    """
    require_admin_perm(admin, "kb:rollback")
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        raise ApiError(*ERR_NOT_FOUND)
    check_domain_scope(admin, entry.domain)
    require_confirm(body.confirm_token, "kb_rollback")
    # 乐观锁：以请求携带的当前版本比对
    if body.version != entry.version:
        raise ApiError(*ERR_ADMIN_LOCK)
    before = {
        "version": entry.version,
        "status": entry.status,
        "title": entry.title,
        "content": _content_digest(entry.content),
        "target_version": body.target_version,
    }
    # 记录式回滚：递增版本回到草稿，历史可由审计快照还原
    entry.version += 1
    entry.status = "draft"
    # 回滚后非 published：best-effort 从向量索引移除（→ delete）
    db.flush()
    rag_index.sync_entry(db, entry.kb_id)
    db.add(
        ContentTraceTask(
            kb_id=entry.kb_id,
            trigger="expert_reject",
            affected_sessions=_count_sessions_referencing(db, entry.kb_id),
            affected_reports=0,
        )
    )
    write_audit(
        db,
        admin,
        "kb_rollback",
        "kb_entry",
        entry.kb_id,
        reason=body.reason,
        before=before,
        after={"version": entry.version, "status": "draft", "target_version": body.target_version},
        confirm_used=True,
    )
    return ok({"kb_id": entry.kb_id, "version": entry.version, "status": entry.status})


@router.get("/kb/entries/{kb_id}/versions", summary="条目版本历史", description="从审计日志聚合版本历史（不建历史版本表）")
def kb_entry_versions(
    kb_id: str,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """从审计日志聚合条目版本历史（不建历史版本表的替代视图）。

    Args:
        kb_id: 条目业务编号。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{kb_id, items}（动作/前后版本/操作角色/时间倒序）。

    Raises:
        ApiError: 1002 条目不存在；1103 缺少 kb:view 权限。
    """
    require_admin_perm(admin, "kb:view")
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        raise ApiError(*ERR_NOT_FOUND)
    logs = (
        db.query(AdminAuditLog)
        .filter(AdminAuditLog.object_type == "kb_entry", AdminAuditLog.object_id == kb_id)
        .order_by(AdminAuditLog.id.desc())
        .limit(200)
        .all()
    )
    items = []
    for lg in logs:
        before = lg.before_snapshot if isinstance(lg.before_snapshot, dict) else {}
        after = lg.after_snapshot if isinstance(lg.after_snapshot, dict) else {}
        items.append(
            {
                "id": lg.id,
                "action": lg.action,
                "operator_role": lg.operator_role_snapshot,
                "reason": lg.reason,
                "result": lg.result,
                "confirm_used": lg.confirm_used,
                "before_version": before.get("version"),
                "after_version": after.get("version"),
                "created_at": _iso(lg.created_at),
            }
        )
    return ok({"kb_id": kb_id, "items": items})


@router.get("/kb/reviews", summary="审核工单列表", description="分页查询，status=pending 映射 verdict 为空")
def list_kb_reviews(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询审核工单列表（status=pending 映射 verdict 为空）。

    Args:
        status: pending / pass / reject。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 kb:view 权限。
    """
    require_admin_perm(admin, "kb:view")
    q = db.query(KbReview)
    if status == "pending":
        q = q.filter(KbReview.verdict.is_(None))
    elif status in ("pass", "reject"):
        q = q.filter(KbReview.verdict == status)
    total = q.count()
    rows = (
        q.order_by(KbReview.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    items = [
        {
            "id": r.id,
            "review_no": r.review_no,
            "kb_id": r.kb_id,
            "kb_kind": r.kb_kind,
            "version": r.version,
            "review_round": r.review_round,
            "reviewer_role": r.reviewer_role,
            "submitted_at": _iso(r.submitted_at),
            "reviewed_at": _iso(r.reviewed_at),
            "score": r.score,
            "verdict": r.verdict,
            "reject_code": r.reject_code,
            "rollback_target_version": r.rollback_target_version,
        }
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


# ==================== 内容追溯任务 ====================


@router.get("/trace-tasks", summary="追溯任务列表", description="内容追溯任务分页查询（pending/done）")
def list_trace_tasks(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询内容追溯任务列表。

    Args:
        status: pending（未处置）/ done（已处置）。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 risk:view 权限。
    """
    require_admin_perm(admin, "risk:view")
    q = db.query(ContentTraceTask)
    if status == "done":
        q = q.filter(ContentTraceTask.done_at.isnot(None))
    elif status == "pending":
        q = q.filter(ContentTraceTask.done_at.is_(None))
    total = q.count()
    rows = (
        q.order_by(ContentTraceTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": t.id,
            "kb_id": t.kb_id,
            "trigger": t.trigger,
            "affected_sessions": t.affected_sessions,
            "affected_reports": t.affected_reports,
            "disposal_level": t.disposal_level,
            "disposed_count": t.disposed_count,
            "operator_id": t.operator_id,
            "created_at": _iso(t.created_at),
            "decided_at": _iso(t.decided_at),
            "done_at": _iso(t.done_at),
        }
        for t in rows
    ]
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/trace-tasks/{task_id}/dispose", summary="追溯任务分级处置", description="A/B/C 分级处置，处置数=影响会话数")
def dispose_trace_task(
    task_id: int,
    body: TraceDisposeBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """内容追溯任务分级处置（A/B/C），处置数=影响会话数。

    Args:
        task_id: 追溯任务主键。
        body: 处置请求体（disposal_level + confirm_token）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{id, disposal_level, done_at}。

    Raises:
        ApiError: 1002 任务不存在；1001 等级非法；1103 缺少 risk:view；1602 缺少二次确认。
    """
    require_admin_perm(admin, "risk:view")
    require_confirm(body.confirm_token, "trace_dispose")
    task = db.get(ContentTraceTask, task_id)
    if task is None:
        raise ApiError(*ERR_NOT_FOUND)
    if body.disposal_level not in ("A", "B", "C"):
        raise ApiError(1001, "disposal_level 必须为 A/B/C", 422)
    before = {"disposal_level": task.disposal_level, "done_at": _iso(task.done_at)}
    now = _now()
    task.disposal_level = body.disposal_level
    task.decided_at = now
    task.done_at = now
    task.disposed_count = task.affected_sessions
    task.operator_id = admin.id
    write_audit(
        db,
        admin,
        "trace_dispose",
        "content_trace_task",
        str(task.id),
        reason=f"level={body.disposal_level}",
        before=before,
        after={
            "disposal_level": task.disposal_level,
            "disposed_count": task.disposed_count,
            "done_at": _iso(task.done_at),
        },
        confirm_used=True,
    )
    return ok({"id": task.id, "disposal_level": task.disposal_level, "done_at": _iso(task.done_at)})

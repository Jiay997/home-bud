# -*- coding: utf-8 -*-
"""问答 SSE 流式 API 模块。

端点：
- POST /qa/sessions                        创建会话（开关/幂等/申诉放行/活跃/额度预检）
- POST /qa/sessions/{uid}/stream           SSE 流式问答（风险扫描 → 缓存 → LangGraph）
- POST /qa/sessions/{uid}/cancel           取消进行中的会话
- GET  /qa/sessions/{uid}                  轮询兜底（sections 全量+门控裁剪）
- GET  /qa/sessions/{uid}/stream           断线续发（已完成会话重发帧）
- POST /qa/sessions/{uid}/regenerate       会员重生成指定分节

SSE 帧格式：`event: {type}\\ndata: {json}\\n\\n`，sequence 递增，
单帧 ≤8KB（超长内容切片为多个 section_delta）。
计次口径（PRD §12.5）：正常生成与申诉放行后重提计次；
被拦截/失败/缓存命中（含断线重连）不计次。
"""
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...agents.graph import run_qa_graph
from ...core.cache import cache
from ...core.crypto import decrypt_field, encrypt_field, sha256_hex
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import (
    ApiError,
    ERR_ACTIVE_STREAM,
    ERR_FORBIDDEN,
    ERR_IDEMPOTENT_PROCESSING,
    ERR_NOT_FOUND,
    ERR_PARAM,
    ERR_QUOTA_EXHAUSTED,
    raise_err,
)
from ...core.config import get_settings
from ...core.observe import metrics
from ...db import get_db
from ...models import (
    AgentCallLog,
    AppUser,
    ChildProfile,
    ConfigVersion,
    IdempotencyKey,
    PetProfile,
    QaAnswerSection,
    QaSession,
    RiskAppeal,
)
from ...models.base import gen_uuid
from ...services.quota_service import QuotaService
from ...risk.service import RiskService

router = APIRouter(tags=["C端-问答"])

# 活跃会话缓存 TTL（秒）——超时未完成自动释放
ACTIVE_TTL = 120

# 回答缓存 TTL（秒）
ANSWER_CACHE_TTL = 3600

# 幂等键有效期（小时）
IDEMPOTENT_TTL_HOURS = 24

# 单帧数据切片字符上限（约 3.6KB UTF-8，含帧头 < 8KB）
CHUNK_CHARS = 1200

# 合规文案 ID（服务端下发，前端不得硬编码）
DISCLAIMER_ID = "DISCLAIMER_V1"
AI_GEN_LABEL_ID = "AI_GEN_LABEL_V1"

# 上海时区（UTC+8 固定偏移）
_TZ_SHANGHAI = timezone(timedelta(hours=8))

# 缓存命中提示文案（首个 block 前插入）
CACHE_NOTICE = "内容来自缓存，可能不是最新"

# 断线续发起始帧号参数校验下限
MIN_SEQUENCE = 0


# ----------------------------------------------------------------------
# 请求/响应模型
# ----------------------------------------------------------------------
class SessionCreateBody(BaseModel):
    """创建问答会话请求体。

    Attributes:
        entry: 显式入口 child/pet/family。
        question: 问题原文（≤2000 字）。
        profile_uid: 档案对外标识（可选，越权按不存在处理）。
        client_request_id: 客户端幂等键（必填）。
    """

    entry: str = Field(..., description="入口 child/pet/family")
    question: str = Field(..., min_length=1, max_length=2000, description="问题原文")
    profile_uid: Optional[str] = Field(None, max_length=64, description="档案 UID")
    client_request_id: str = Field(..., min_length=1, max_length=64, description="幂等键")


class CancelBody(BaseModel):
    """取消会话请求体。

    Attributes:
        cancel_token: started 帧下发的取消凭证。
    """

    cancel_token: Optional[str] = Field(None, max_length=64)


class RegenerateBody(BaseModel):
    """重生成请求体。

    Attributes:
        section: 目标分节 child/pet/safety（缺省重跑全部）。
        client_request_id: 客户端幂等键（必填）。
    """

    section: Optional[str] = Field(None, description="目标分节 child/pet/safety")
    client_request_id: str = Field(..., min_length=1, max_length=64, description="幂等键")


# ----------------------------------------------------------------------
# 内部工具
# ----------------------------------------------------------------------
def _sse(event_type: str, data: dict) -> str:
    """构造一帧 SSE 文本。

    Args:
        event_type: 事件类型（started/section_delta/section_done/blocked/...）。
        data: 帧数据（服务端追加 sequence）。

    Returns:
        `event: {type}\\ndata: {json}\\n\\n` 字符串。
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> List[str]:
    """按字符上限切片（保证单帧 ≤8KB）。

    Args:
        text: 原始内容。
        max_chars: 单片最大字符数。

    Returns:
        切片列表（空文本返回空列表）。
    """
    if not text:
        return []
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def _get_session_owned(db: Session, user: AppUser, session_uid: str) -> QaSession:
    """查询本人会话（越权统一按不存在处理，防枚举）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        session_uid: 会话对外标识。

    Returns:
        QaSession ORM 实例。

    Raises:
        ApiError: 1002 不存在或无权限。
    """
    session = (
        db.query(QaSession).filter(QaSession.session_uid == session_uid).first()
    )
    if session is None or session.user_id != user.id:
        raise ApiError(*ERR_NOT_FOUND)
    return session


def _resolve_profile(db: Session, user: AppUser, session: QaSession) -> Tuple[bool, Optional[str], Optional[str]]:
    """解析会话绑定档案的检索过滤参数。

    Args:
        db: 数据库会话。
        user: 当前用户。
        session: 会话（profile_type/profile_id 由创建时写入）。

    Returns:
        (profile_bound, age_band, species) 三元组。
    """
    profile_type = session.profile_type
    profile_id = session.profile_id
    if profile_type == "child" and profile_id:
        child = (
            db.query(ChildProfile)
            .filter(
                ChildProfile.id == profile_id,
                ChildProfile.user_id == user.id,
                ChildProfile.status == "active",
            )
            .first()
        )
        if child:
            return True, child.age_band, None
    if profile_type == "pet" and profile_id:
        pet = (
            db.query(PetProfile)
            .filter(PetProfile.id == profile_id, PetProfile.user_id == user.id)
            .first()
        )
        if pet:
            return True, None, pet.pet_type
    return False, None, None


def _gated_blocks(blocks: List[dict], member: bool) -> List[dict]:
    """会员门控裁剪：非会员剔除 access_tier=block 块的 content 字段。

    Args:
        blocks: 分节 block 列表。
        member: 是否会员。

    Returns:
        裁剪后的 block 列表（会员块仅去 content，标记 is_member_content）。
    """
    out: List[dict] = []
    for block in blocks:
        if not member and block.get("access_tier") == "block":
            gated = {k: v for k, v in block.items() if k != "content"}
            gated["is_member_content"] = True
            out.append(gated)
        else:
            out.append(dict(block))
    return out


def _estimate_render_order(entry: str) -> List[str]:
    """按入口预估分节顺序（started 帧骨架用，实际以 aggregate 为准）。

    Args:
        entry: 入口 child/pet/family。

    Returns:
        分节键列表。
    """
    if entry == "child":
        return ["safety", "child"]
    if entry == "pet":
        return ["safety", "pet"]
    return ["safety", "child", "pet"]


def _set_idem_done(db: Session, session_uid: str) -> None:
    """将本会话关联的幂等键置 done（流结束/异常均执行）。

    Args:
        db: 数据库会话。
        session_uid: 会话标识（幂等键 result_ref 反查）。
    """
    try:
        db.query(IdempotencyKey).filter(
            IdempotencyKey.scope == "qa",
            IdempotencyKey.status == "processing",
            IdempotencyKey.result_ref["session_uid"].astext == session_uid,
        ).update({"status": "done"})
        db.commit()
    except Exception:  # noqa: BLE001 — 幂等标记失败不影响已交付内容
        db.rollback()


# ----------------------------------------------------------------------
# POST /qa/sessions
# ----------------------------------------------------------------------
@router.post("/qa/sessions", summary="创建问答会话", description="校验开关/幂等/申诉放行/活跃限制/额度后落库 pending，返回 session_uid")
def create_session(
    body: SessionCreateBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建问答会话（流式接口的前置步骤）。

    校验链：入口紧急开关 → 幂等 → 申诉放行 → 活跃会话 → 额度预检（不扣）
    → 落库 pending。

    Args:
        body: 创建请求体。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({"session_uid", "status": "pending"})；幂等重放附
        idempotent_replay=True 与 result_ref。

    Raises:
        ApiError: 1406 入口维护中(503)；1004 相同请求处理中；
            1203 已有活跃流(retry_after=30)；1202 免费额度用尽；
            1002 档案不存在或无权限。
    """
    if body.entry not in ("child", "pet", "family"):
        raise ApiError(*ERR_PARAM)
    # 1. 入口紧急开关（config_type='switch' 最新 active 版本）
    switch = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.config_type == "switch",
            ConfigVersion.config_key == f"switch.entry.{body.entry}",
            ConfigVersion.status == "active",
        )
        .order_by(ConfigVersion.version.desc())
        .first()
    )
    if switch is not None and isinstance(switch.snapshot, dict):
        if switch.snapshot.get("enabled") is False:
            raise ApiError(
                code=1406, message="该功能维护中，请稍后再试", http_status=503
            )
    # 2. 幂等：done 回放 / processing 拒绝 / 新建指纹
    fingerprint = sha256_hex(
        body.entry + body.question + (body.profile_uid or "")
    )
    idem = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.scope == "qa",
            IdempotencyKey.client_request_id == body.client_request_id,
        )
        .first()
    )
    if idem is not None and idem.status == "done":
        ref = idem.result_ref or {}
        return ok(
            {
                "session_uid": ref.get("session_uid"),
                "status": "done",
                "idempotent_replay": True,
                "result_ref": ref,
            }
        )
    if idem is not None and idem.status == "processing":
        if idem.request_fingerprint != fingerprint:
            raise ApiError(*ERR_PARAM)
        raise_err(ERR_IDEMPOTENT_PROCESSING)
    # 3. 申诉放行：approved 且在有效期内的工单存在 → 本次会话标记 is_retry
    now = datetime.now(_TZ_SHANGHAI)
    approved = (
        db.query(RiskAppeal)
        .filter(
            RiskAppeal.user_id == user.id,
            RiskAppeal.status == "approved",
            RiskAppeal.allow_expire_at.isnot(None),
            RiskAppeal.allow_expire_at > now,
        )
        .first()
    )
    is_retry = approved is not None
    # 4. 活跃会话：同一用户并发流限制
    if cache.get(f"qa:active:{user.id}") is not None:
        raise_err(ERR_ACTIVE_STREAM, retryable=True, retry_after=30)
    # 5. 额度预检（不扣）：会员放行；免费 used>=limit → 1202
    try:
        QuotaService.quota_check(db, user)
    except ApiError as exc:
        # 观察埋点：免费额度用尽（1202）计数，随后按原语义抛出
        if exc.code == ERR_QUOTA_EXHAUSTED[0]:
            metrics.observe_quota_exhausted()
        raise
    # 6. 档案解析（可选；越权按不存在）
    profile_type: Optional[str] = None
    profile_id: Optional[int] = None
    if body.profile_uid:
        child = (
            db.query(ChildProfile)
            .filter(
                ChildProfile.profile_uid == body.profile_uid,
                ChildProfile.user_id == user.id,
                ChildProfile.status == "active",
            )
            .first()
        )
        if child:
            profile_type, profile_id = "child", child.id
        else:
            pet = (
                db.query(PetProfile)
                .filter(
                    PetProfile.pet_uid == body.profile_uid,
                    PetProfile.user_id == user.id,
                )
                .first()
            )
            if pet:
                profile_type, profile_id = "pet", pet.id
            else:
                raise ApiError(*ERR_NOT_FOUND)
    # 7. 落库：会话 pending + 幂等键 processing（预写 result_ref 供流结束置 done）
    session = QaSession(
        user_id=user.id,
        profile_type=profile_type or body.entry,
        profile_id=profile_id,
        entry=body.entry,
        question_text_enc=encrypt_field(body.question),
        char_len=len(body.question),
        status="pending",
        risk_level="none",
        is_retry=is_retry,
    )
    db.add(session)
    db.flush()
    if idem is None:
        idem = IdempotencyKey(
            scope="qa",
            client_request_id=body.client_request_id,
            request_fingerprint=fingerprint,
            result_ref={"session_uid": session.session_uid},
            status="processing",
            expire_at=now + timedelta(hours=IDEMPOTENT_TTL_HOURS),
        )
        db.add(idem)
    else:
        idem.status = "processing"
        idem.result_ref = {"session_uid": session.session_uid}
    db.commit()
    return ok({"session_uid": session.session_uid, "status": "pending"})


# ----------------------------------------------------------------------
# POST /qa/sessions/{uid}/stream
# ----------------------------------------------------------------------
def _qa_stream_generator(session: QaSession, user: AppUser, db: Session) -> Generator[str, None, None]:
    """SSE 流式生成器：风险扫描 → 缓存 → LangGraph → 逐节下发 → 落库。

    风险扫描与会员门控逐次执行不跳过；缓存命中直接发缓存节（跳过 LLM），
    首个 block 前插入缓存提示 block；计次仅在非会员、非缓存命中的
    done/degraded 场景执行。

    Args:
        session: 已校验归属的会话。
        user: 当前用户。
        db: 数据库会话。

    Yields:
        SSE 帧字符串序列，帧顺序：started → (blocked | section_delta* →
        section_done* → degraded? → completed | error)。
    """
    active_key = f"qa:active:{user.id}"
    cancel_token = gen_uuid()
    cache.set(
        active_key,
        json.dumps({"session_uid": session.session_uid, "cancel_token": cancel_token}),
        ttl_seconds=ACTIVE_TTL,
    )
    seq = 0
    start = time.monotonic()
    question = decrypt_field(session.question_text_enc)
    member = QuotaService.is_member(user)
    profile_bound, age_band, species = _resolve_profile(db, user, session)
    try:
        # ---- started 帧（render_order 为入口预估，实际以 aggregate 为准） ----
        first_packet_ms = int((time.monotonic() - start) * 1000)
        seq += 1
        yield _sse(
            "started",
            {
                "sequence": seq,
                "session_uid": session.session_uid,
                "request_id": gen_uuid(),
                "cancel_token": cancel_token,
                "render_order": _estimate_render_order(session.entry),
                "first_packet_ms": first_packet_ms,
            },
        )
        # ---- 1. 风险扫描：逐次执行，纯输入侧不读档案 ----
        scanned = RiskService.scan(db, question, user.id, session=session)
        risk_result = scanned["risk_result"]
        if risk_result.get("blocked"):
            # 命中：blocked 帧（正文为空 100%，无任何 section 帧）；不扣额度
            metrics.observe_blocked()
            db.commit()
            seq += 1
            yield _sse(
                "blocked",
                {
                    "sequence": seq,
                    "reason": risk_result.get("reason"),
                    "risk_event_no": scanned["risk_event_no"],
                    "channels": RiskService.get_channels(
                        db, risk_result.get("category_code")
                    ),
                    "appeal_allowed": not risk_result.get("hard", False),
                },
            )
            return
        # ---- 2. 回答缓存命中：跳过 LLM，直接发缓存节；不计次 ----
        cache_key = f"qa:cache:{sha256_hex(question + (age_band or '') + 'v1')}"
        cached_raw = cache.get(cache_key)
        if cached_raw:
            payload = json.loads(cached_raw)
            section_rows: List[dict] = payload.get("sections", [])
            # 缓存提示 block 插入首个 block 之前（不落库、不回写缓存）
            first = True
            for section in section_rows:
                blocks = json.loads(json.dumps(section.get("blocks", [])))
                if first:
                    blocks.insert(
                        0,
                        {
                            "block_key": "cache_notice",
                            "title": "提示",
                            "content": CACHE_NOTICE,
                            "access_tier": "free",
                            "immutable": True,
                        },
                    )
                    first = False
                seq += 1
                yield _sse(
                    "section_done",
                    {
                        "sequence": seq,
                        "section_key": section.get("section_key"),
                        "title": section.get("title"),
                        "blocks": _gated_blocks(blocks, member),
                        "pinned": section.get("pinned", False),
                        "immutable": section.get("immutable", False),
                        "cached": True,
                    },
                )
            quota_row = QuotaService.get_or_create_today(db, user)
            seq += 1
            yield _sse(
                "completed",
                {
                    "sequence": seq,
                    "status": "done",
                    "degraded_reason": None,
                    "agents_involved": payload.get("agents_involved", []),
                    "disclaimer_id": DISCLAIMER_ID,
                    "ai_generated_label": AI_GEN_LABEL_ID,
                    "from_cache": True,
                    "quota": {
                        "used": quota_row.used_count,
                        "limit": quota_row.limit_snapshot,
                    },
                },
            )
            # 会话落库（缓存内容同样构成回答记录）+ 分节覆盖写
            session.status = "done"
            session.risk_level = "low"
            session.risk_score_band = risk_result.get("score_band")
            session.render_order = payload.get("render_order", [])
            session.agents_involved = payload.get("agents_involved", [])
            session.first_packet_ms = first_packet_ms
            session.total_latency_ms = int((time.monotonic() - start) * 1000)
            db.commit()
            _persist_sections(db, session, section_rows)
            return
        # ---- 3. 运行 LangGraph（风险已预扫，graph 内 risk_scan 沿用结果） ----
        initial: Dict[str, Any] = {
            "request_id": gen_uuid(),
            "session_id": session.id,
            "session_uid": session.session_uid,
            "client_request_id": "",
            "question": question,
            "entry": session.entry,
            "profile_bound": profile_bound,
            "age_band": age_band,
            "species": species,
            "risk_pre_scanned": True,
            "risk_result": risk_result,
            "status": "ok",
            "user_id": user.id,
            "member_status": user.member_status,
            "db": db,
            "session": session,
        }
        final = run_qa_graph(initial)
        if final.get("status") == "blocked":  # 双保险（正常已被预扫拦截）
            metrics.observe_blocked()
            seq += 1
            yield _sse(
                "blocked",
                {
                    "sequence": seq,
                    "reason": final.get("risk_result", {}).get("reason"),
                    "risk_event_no": final.get("risk_event_no"),
                    "channels": final.get("channels", []),
                    "appeal_allowed": final.get("appeal_allowed", True),
                },
            )
            db.commit()
            return
        if final.get("status") == "failed":
            raise RuntimeError("all agents failed")
        # ---- 4. 按 render_order 逐节下发：骨架 → 内容切片 → 完整帧 ----
        sections: Dict[str, dict] = final.get("sections", {})
        render_order: List[str] = final.get("render_order", [])
        has_member_block = False
        for key in render_order:
            section = sections.get(key)
            if not section:
                continue
            # section_delta：标题/骨架
            seq += 1
            yield _sse(
                "section_delta",
                {
                    "sequence": seq,
                    "section_key": key,
                    "stage": "skeleton",
                    "title": section.get("title"),
                    "block_titles": [b.get("title") for b in section.get("blocks", [])],
                },
            )
            # section_delta：内容切片（每 block 独立切片下发）
            for block in section.get("blocks", []):
                for piece in _chunk_text(block.get("content") or ""):
                    seq += 1
                    yield _sse(
                        "section_delta",
                        {
                            "sequence": seq,
                            "section_key": key,
                            "block_key": block.get("block_key"),
                            "stage": "content",
                            "delta": piece,
                        },
                    )
            # section_done：完整 blocks（会员门控裁剪）
            gated = _gated_blocks(section.get("blocks", []), member)
            if any(b.get("is_member_content") for b in gated):
                has_member_block = True
            seq += 1
            yield _sse(
                "section_done",
                {
                    "sequence": seq,
                    "section_key": key,
                    "title": section.get("title"),
                    "blocks": gated,
                    "pinned": section.get("pinned", False),
                    "immutable": section.get("immutable", False),
                },
            )
        # degraded 帧（存在失败节时）
        if final.get("status") == "degraded":
            metrics.observe_degraded()
            seq += 1
            yield _sse(
                "degraded",
                {
                    "sequence": seq,
                    "degraded_reason": final.get("degraded_reason"),
                    "conflict_note": final.get("conflict_note"),
                },
            )
        # ---- 5. 计次：非会员 且 非缓存命中 且 生成成功（done/degraded） ----
        quota_row = QuotaService.get_or_create_today(db, user)
        if final.get("status") in ("done", "degraded") and not member:
            used = QuotaService.increment(db, user)
            quota_row.used_count = used
        # ---- 6. 落库：会话元数据 + 分节覆盖写 + agent_call_log + 写缓存 ----
        session.status = final.get("status") or "done"
        session.degraded_reason = final.get("degraded_reason")
        session.risk_level = "low"
        session.risk_score_band = risk_result.get("score_band")
        session.render_order = render_order
        session.first_packet_ms = first_packet_ms
        session.total_latency_ms = int((time.monotonic() - start) * 1000)
        session.is_member_content = has_member_block
        agents_involved = [
            k.replace("_agent", "")
            for k, v in (final.get("agent_outputs") or {}).items()
            if v.get("status") not in ("skip", None)
        ]
        session.agents_involved = agents_involved
        kb_refs = sorted(
            {
                d.get("kb_id")
                for docs in (final.get("retrieved_docs") or {}).values()
                for d in docs
                if d.get("kb_id")
            }
        )
        session.kb_refs = kb_refs
        db.flush()
        # 分节落库（含会员块完整 content；下发侧门控裁剪，存储不裁剪）
        plain_sections = [
            {
                "section_key": key,
                "title": sections[key].get("title"),
                "blocks": sections[key].get("blocks", []),
                "pinned": sections[key].get("pinned", False),
                "immutable": sections[key].get("immutable", False),
            }
            for key in render_order
            if key in sections
        ]
        _persist_sections(db, session, plain_sections)
        # agent_call_log：每节点一条（intent_route/retrieve/各 Agent）
        _persist_agent_logs(db, session, final, question)
        db.commit()
        # 回答写缓存（TTL 3600；缓存不含会员门控，下发侧裁剪）
        cache.set(
            cache_key,
            json.dumps(
                {
                    "render_order": render_order,
                    "agents_involved": agents_involved,
                    "sections": plain_sections,
                },
                ensure_ascii=False,
            ),
            ttl_seconds=ANSWER_CACHE_TTL,
        )
        # ---- completed 帧 ----
        seq += 1
        yield _sse(
            "completed",
            {
                "sequence": seq,
                "status": session.status,
                "degraded_reason": session.degraded_reason,
                "agents_involved": agents_involved,
                "conflict_note": final.get("conflict_note"),
                "disclaimer_id": DISCLAIMER_ID,
                "ai_generated_label": AI_GEN_LABEL_ID,
                "quota": {
                    "used": quota_row.used_count,
                    "limit": quota_row.limit_snapshot,
                },
            },
        )
    except Exception:  # noqa: BLE001 — 流内异常转 error 帧 + 会话 failed
        db.rollback()
        try:
            session.status = "failed"
            session.total_latency_ms = int((time.monotonic() - start) * 1000)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        seq += 1
        yield _sse(
            "error",
            {
                "sequence": seq,
                "code": 1902,
                "message": "生成中断，请稍后重试",
                "session_uid": session.session_uid,
            },
        )
    finally:
        # 释放活跃会话 + 幂等键置 done（无论成功失败均执行）
        cache.delete(active_key)
        _set_idem_done(db, session.session_uid)


def _persist_sections(db: Session, session: QaSession, section_rows: List[dict]) -> None:
    """按 (session_id, section_key) 覆盖写回答分节。

    Args:
        db: 数据库会话。
        session: 会话。
        section_rows: 分节数据列表（section_key/title/blocks/pinned/immutable）。
    """
    for row_data in section_rows:
        key = row_data["section_key"]
        row = (
            db.query(QaAnswerSection)
            .filter(
                QaAnswerSection.session_id == session.id,
                QaAnswerSection.section_key == key,
            )
            .first()
        )
        if row is None:
            db.add(
                QaAnswerSection(
                    session_id=session.id,
                    section_key=key,
                    section_version=1,
                    pinned=row_data.get("pinned", False),
                    immutable=row_data.get("immutable", False),
                    title=row_data.get("title"),
                    blocks=row_data.get("blocks", []),
                    status="ok",
                )
            )
        else:
            row.title = row_data.get("title")
            row.blocks = row_data.get("blocks", [])
            row.pinned = row_data.get("pinned", False)
            row.immutable = row_data.get("immutable", False)
            row.status = "ok"
            row.section_version = (row.section_version or 1) + 1
            row.updated_at = datetime.now(_TZ_SHANGHAI)
    db.flush()


def _persist_agent_logs(db: Session, session: QaSession, final: dict, question: str) -> None:
    """写 agent_call_log：每个执行节点一条（输入摘要化不可还原）。

    Args:
        db: 数据库会话。
        session: 会话。
        final: 图最终状态（node_meta/agent_outputs）。
        question: 问题原文（仅取哈希）。
    """
    settings = get_settings()
    node_meta: Dict[str, dict] = final.get("node_meta") or {}
    agent_outputs: Dict[str, dict] = final.get("agent_outputs") or {}
    for agent_id, meta in node_meta.items():
        output = agent_outputs.get(agent_id)
        # 输出快照：agent 取其产出；路由/检索节点取 meta 本身
        output_json = output if isinstance(output, dict) else meta
        # 观测补齐（评估 2026-10-12）：Agent 行快照合并 node_meta 的 intent，
        # 供后台日志详情「意图」展示（否则 Agent 行恒显示「意图=--」）；
        # 仅观测字段，新建 dict 不污染 agent_outputs 原始产出
        if isinstance(output_json, dict) and meta.get("intent"):
            output_json = {**output_json, "intent": meta["intent"]}
        # 观察埋点：Agent 成功/失败计数（与落库 status 同口径）
        metrics.observe_agent(meta.get("status") == "ok")
        db.add(
            AgentCallLog(
                session_id=session.id,
                agent_id=agent_id,
                agent_version="1.0.0",
                provider="deepseek",
                model=settings.llm_model,
                input_digest=sha256_hex(question),
                output_json=output_json,
                evidence_ref=(output or {}).get("evidence_ref")
                if isinstance(output, dict)
                else None,
                prompt_tokens=meta.get("prompt_tokens"),
                completion_tokens=meta.get("completion_tokens"),
                latency_ms=meta.get("latency_ms"),
                status="ok" if meta.get("status") == "ok" else "fail",
            )
        )
    db.flush()


@router.post("/qa/sessions/{session_uid}/stream", summary="SSE 流式问答", description="风险扫描→缓存→LangGraph 逐节下发，帧序 started→section_*→completed")
def stream_session(
    session_uid: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SSE 流式问答端点。

    Args:
        session_uid: 会话标识。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        StreamingResponse（text/event-stream）。

    Raises:
        ApiError: 1002 会话不存在或无权限。
    """
    session = _get_session_owned(db, user, session_uid)
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Content-Encoding": "identity",
    }
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        _qa_stream_generator(session, user, db),
        media_type="text/event-stream",
        headers=headers,
    )


# ----------------------------------------------------------------------
# POST /qa/sessions/{uid}/cancel
# ----------------------------------------------------------------------
@router.post("/qa/sessions/{session_uid}/cancel", summary="取消进行中的会话", description="释放活跃会话键；未完成会话置 orphaned")
def cancel_session(
    session_uid: str,
    body: CancelBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消进行中的问答会话。

    删除活跃会话键；未完成的会话置 orphaned，已完成会话保持原状态。

    Args:
        session_uid: 会话标识。
        body: 取消请求体（cancel_token）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({"session_uid", "status"})。

    Raises:
        ApiError: 1002 会话不存在或无权限；1102 取消凭证不匹配。
    """
    session = _get_session_owned(db, user, session_uid)
    active_key = f"qa:active:{user.id}"
    active_raw = cache.get(active_key)
    if active_raw:
        try:
            active = json.loads(active_raw)
        except Exception:  # noqa: BLE001
            active = {}
        # 凭证不匹配（非本会话持有者）拒绝取消
        if active.get("session_uid") == session_uid and body.cancel_token and \
                active.get("cancel_token") != body.cancel_token:
            raise ApiError(*ERR_FORBIDDEN)
        cache.delete(active_key)
    if session.status not in ("done", "blocked", "degraded", "failed", "orphaned"):
        session.status = "orphaned"
    db.commit()
    return ok({"session_uid": session.session_uid, "status": session.status})


# ----------------------------------------------------------------------
# GET /qa/sessions/{uid}（轮询兜底）
# ----------------------------------------------------------------------
@router.get("/qa/sessions/{session_uid}", summary="轮询兜底查询会话", description="会话元数据 + 分节全量（会员门控裁剪）")
def get_session(
    session_uid: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """轮询兜底：会话元数据 + 分节全量（会员门控裁剪）。

    Args:
        session_uid: 会话标识。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({session 元数据, sections: [...], render_order})。

    Raises:
        ApiError: 1002 会话不存在或无权限。
    """
    session = _get_session_owned(db, user, session_uid)
    member = QuotaService.is_member(user)
    rows = (
        db.query(QaAnswerSection)
        .filter(QaAnswerSection.session_id == session.id)
        .all()
    )
    order = session.render_order or [r.section_key for r in rows]
    by_key = {r.section_key: r for r in rows}
    sections = []
    for key in order:
        row = by_key.get(key)
        if row is None:
            continue
        sections.append(
            {
                "section_key": row.section_key,
                "section_version": row.section_version,
                "title": row.title,
                "blocks": _gated_blocks(row.blocks or [], member),
                "pinned": row.pinned,
                "immutable": row.immutable,
                "status": row.status,
            }
        )
    return ok(
        {
            "session_uid": session.session_uid,
            "status": session.status,
            "entry": session.entry,
            "risk_level": session.risk_level,
            "degraded_reason": session.degraded_reason,
            "agents_involved": session.agents_involved or [],
            "kb_refs": session.kb_refs or [],
            "render_order": order,
            "is_member_content": session.is_member_content,
            "sections": sections,
        }
    )


# ----------------------------------------------------------------------
# GET /qa/sessions/{uid}/stream?from_sequence=N（断线续发）
# ----------------------------------------------------------------------
@router.get("/qa/sessions/{session_uid}/stream", summary="断线续发", description="已完成会话从落库分节重发 section_done 与 completed 帧")
def resume_stream(
    session_uid: str,
    from_sequence: int = Query(MIN_SEQUENCE, ge=0),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """断线续发：已完成会话从落库分节重发 section_done + completed。

    未完成（pending/streaming）返回 1004（有流正在处理或尚未生成内容，
    客户端应走轮询兜底）。

    Args:
        session_uid: 会话标识。
        from_sequence: 起始帧号。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        StreamingResponse（text/event-stream）。

    Raises:
        ApiError: 1002 会话不存在或无权限；1004 会话尚未完成。
    """
    session = _get_session_owned(db, user, session_uid)
    if session.status not in ("done", "degraded", "blocked"):
        raise_err(ERR_IDEMPOTENT_PROCESSING)
    member = QuotaService.is_member(user)

    def _resume_generator() -> Generator[str, None, None]:
        """续发生成器：从落库分节重建帧序列。

        Yields:
            SSE 帧字符串序列（section_done* → completed，blocked 单帧）。
        """
        seq = from_sequence
        if session.status == "blocked":
            # 被阻断会话续发：单 blocked 帧（渠道卡留空，凭 risk_event 走申诉接口）
            seq += 1
            yield _sse(
                "blocked",
                {
                    "sequence": seq,
                    "reason": "该问题已停止生成回答",
                    "risk_event_no": None,
                    "channels": [],
                    "appeal_allowed": session.risk_level == "high",
                },
            )
            return
        rows = (
            db.query(QaAnswerSection)
            .filter(QaAnswerSection.session_id == session.id)
            .all()
        )
        order = session.render_order or [r.section_key for r in rows]
        by_key = {r.section_key: r for r in rows}
        for key in order:
            row = by_key.get(key)
            if row is None:
                continue
            seq += 1
            yield _sse(
                "section_done",
                {
                    "sequence": seq,
                    "section_key": row.section_key,
                    "title": row.title,
                    "blocks": _gated_blocks(row.blocks or [], member),
                    "pinned": row.pinned,
                    "immutable": row.immutable,
                },
            )
        quota_row = QuotaService.get_or_create_today(db, user)
        seq += 1
        yield _sse(
            "completed",
            {
                "sequence": seq,
                "status": session.status,
                "degraded_reason": session.degraded_reason,
                "agents_involved": session.agents_involved or [],
                "disclaimer_id": DISCLAIMER_ID,
                "ai_generated_label": AI_GEN_LABEL_ID,
                "quota": {
                    "used": quota_row.used_count,
                    "limit": quota_row.limit_snapshot,
                },
            },
        )

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Content-Encoding": "identity",
    }
    from fastapi.responses import StreamingResponse

    return StreamingResponse(_resume_generator(), media_type="text/event-stream", headers=headers)


# ----------------------------------------------------------------------
# POST /qa/sessions/{uid}/regenerate（会员专属）
# ----------------------------------------------------------------------
@router.post("/qa/sessions/{session_uid}/regenerate", summary="重生成指定分节", description="会员专属：重跑整图后替换目标分节（section_version+1）")
def regenerate_session(
    session_uid: str,
    body: RegenerateBody,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重生成指定分节（会员专属）：重跑整图后仅替换目标分节。

    风险扫描随整图重新执行；若被阻断则返回 1401。
    覆盖写 qa_answer_section（section_version+1）。

    Args:
        session_uid: 会话标识。
        body: 重生成请求体（section 可空=全部）。
        user: 当前用户。
        db: 数据库会话。

    Returns:
        ok({session_uid, section, section_version, status})。

    Raises:
        ApiError: 1002 不存在或无权限；1102 非会员；1401 被风险拦截；
            1001 非法分节。
    """
    session = _get_session_owned(db, user, session_uid)
    # 会员专属
    if not QuotaService.is_member(user):
        raise ApiError(code=1102, message="会员功能", http_status=403)
    if body.section is not None and body.section not in ("safety", "child", "pet"):
        raise ApiError(*ERR_PARAM)
    question = decrypt_field(session.question_text_enc)
    profile_bound, age_band, species = _resolve_profile(db, user, session)
    initial: Dict[str, Any] = {
        "request_id": gen_uuid(),
        "session_id": session.id,
        "session_uid": session.session_uid,
        "client_request_id": body.client_request_id,
        "question": question,
        "entry": session.entry,
        "profile_bound": profile_bound,
        "age_band": age_band,
        "species": species,
        "user_id": user.id,
        "member_status": user.member_status,
        "db": db,
        "session": session,
    }
    final = run_qa_graph(initial)
    if final.get("status") == "blocked":
        db.commit()
        # 重生成也被风险拦截：1401（HTTP 200，业务码表达）
        raise ApiError(code=1401, message="该问题已停止生成回答", http_status=200)
    sections: Dict[str, dict] = final.get("sections", {})
    render_order: List[str] = final.get("render_order", [])
    targets = [body.section] if body.section else render_order
    versions: Dict[str, int] = {}
    for key in targets:
        section = sections.get(key)
        if not section:
            continue
        row = (
            db.query(QaAnswerSection)
            .filter(
                QaAnswerSection.session_id == session.id,
                QaAnswerSection.section_key == key,
            )
            .first()
        )
        if row is None:
            row = QaAnswerSection(
                session_id=session.id, section_key=key, section_version=1
            )
            db.add(row)
        else:
            row.section_version = (row.section_version or 1) + 1
        row.title = section.get("title")
        row.blocks = section.get("blocks", [])
        row.pinned = section.get("pinned", False)
        row.immutable = section.get("immutable", False)
        row.status = section.get("status", "ok")
        row.updated_at = datetime.now(_TZ_SHANGHAI)
        db.flush()
        versions[key] = row.section_version
    # 会话状态同步（degraded_reason/agents_involved 可能变化）
    session.status = final.get("status") or session.status
    session.degraded_reason = final.get("degraded_reason")
    db.commit()
    return ok(
        {
            "session_uid": session.session_uid,
            "section": body.section,
            "section_versions": versions,
            "status": session.status,
        }
    )

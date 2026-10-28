# -*- coding: utf-8 -*-
"""后台 V3.1 增量 API 模块（RQ-01/RQ-02/RQ-03/RQ-06/RQ-08/RQ-12/RQ-13/RQ-14）。

端点分组：

- 危机渠道清单（RQ-03 / PA-10 单一数据源）：列表 / 新增 / 编辑 / 核验 / 核验记录 / 汇总
- 分级规则（RQ-06 AC-RQ06-6）：列表 / 编辑 / 专家确认留痕 / 快照自检
- 文案合规扫描（RQ-02）：仓库全量扫描 / 自定义文案扫描 / 检查清单
- 触达统计（RQ-08）：只出统计与状态，**不展示问答原文**
- 内容运营（RQ-12 / RQ-13 / RQ-14）：专题包与轻工具的上下架
- 发布门禁自检（§7.2）：四项阻塞门禁的当前状态

审计口径：所有写操作走 `write_audit`；危险操作（改号码、改档位阈值、
上下架）要求二次确认 + 原因（对齐 §3.4 与 V3.0 二次确认机制）。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.deps import (
    get_admin,
    require_admin_perm,
    require_confirm,
    write_audit,
)
from ...core.envelope import ok
from ...core.errors import ApiError, ERR_NOT_FOUND
from ...db import get_db
from ...models import (
    AdminUser,
    ChannelReviewRecord,
    CrisisChannel,
    ReminderTask,
    ToolItem,
    TopicPack,
    TriageRule,
)
from ...services import agent_weight_service, channel_service, tool_service, topic_service
from ...triage import engine as triage_engine

logger = logging.getLogger("jiaban.admin_v31")

router = APIRouter(tags=["后台-配置"])

# 上海时区
_TZ_SHANGHAI = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# 请求体
# ---------------------------------------------------------------------------
class ChannelBody(BaseModel):
    """渠道清单创建请求体（RQ-03）。"""

    channel_code: str = Field(..., min_length=2, max_length=32, description="渠道编码")
    channel_name: str = Field(..., min_length=1, max_length=64, description="渠道名称")
    category: str = Field(
        "psychological",
        description="psychological / pediatric_emergency / pet_emergency / police / minor_protection",
    )
    phone_number: Optional[str] = Field(None, max_length=32, description="号码（未核验留空，禁止编造）")
    region: str = Field("全国", max_length=32, description="覆盖地域")
    service_hours: Optional[str] = Field(None, max_length=64, description="服务时段")
    applicable_categories: List[str] = Field(
        default_factory=list, description="适用的风险类别编码清单"
    )
    script: Optional[str] = Field(None, description="引导话术")
    sort_weight: int = Field(100, description="排序权重（小者优先）")


class ChannelUpdateBody(BaseModel):
    """渠道清单更新请求体（改号码需二次确认 + 原因 + 渠道 ID 后 4 位）。"""

    channel_name: Optional[str] = Field(None, max_length=64)
    phone_number: Optional[str] = Field(None, max_length=32)
    category: Optional[str] = None
    region: Optional[str] = Field(None, max_length=32)
    service_hours: Optional[str] = Field(None, max_length=64)
    applicable_categories: Optional[List[str]] = None
    script: Optional[str] = None
    sort_weight: Optional[int] = None
    status: Optional[str] = Field(
        None, description="active / pending_review / placeholder / retired（非法值返回 422）"
    )
    reason: str = Field("-", description="变更原因（改号码必填）")
    channel_code_suffix: Optional[str] = Field(
        None, description="改号码二次确认：输入渠道编码后 4 位"
    )
    confirm_token: Optional[str] = Field(None, description="危险操作二次确认凭证")


class ChannelReviewBody(BaseModel):
    """渠道核验请求体（AC-RQ03-5）。"""

    review_method: str = Field(..., description="call_dial / official_site / verbal / document")
    review_result: str = Field(..., description="reachable / unreachable / changed / pending")
    conclusion: Optional[str] = Field(None, description="结论说明")
    note: Optional[str] = Field(None, description="备注")


class TriageRuleUpdateBody(BaseModel):
    """分级规则更新请求体（RQ-06；阈值类变更需专家复核留痕）。"""

    title: Optional[str] = Field(None, max_length=128)
    level: Optional[str] = Field(None, description="red / yellow / green")
    priority: Optional[int] = None
    conditions: Optional[Dict[str, Any]] = None
    basis: Optional[str] = None
    observations: Optional[List[str]] = None
    escalation_flags: Optional[List[str]] = None
    contraindications: Optional[List[str]] = None
    disclaimers: Optional[List[str]] = None
    status: Optional[str] = Field(None, description="active / inactive / draft（非法值返回 422）")
    reason: str = Field("-", description="变更原因")
    confirm_token: Optional[str] = Field(None, description="危险操作二次确认凭证")


class TriageReviewBody(BaseModel):
    """分级规则专家确认请求体（§7.2 门禁：首批规则须专家书面确认）。"""

    expert_signoff: str = Field(..., min_length=2, max_length=64, description="专家签署（姓名/工号）")
    note: Optional[str] = None


class CopyScanBody(BaseModel):
    """文案扫描请求体（单条或多条具名文案）。"""

    texts: Dict[str, str] = Field(default_factory=dict, description="{名称: 文案}")


class TopicBody(BaseModel):
    """专题包创建 / 更新请求体（RQ-13 / RQ-14）。"""

    topic_code: str = Field(..., min_length=2, max_length=32)
    title: str = Field(..., min_length=1, max_length=128)
    domain: str = Field(..., description="cross / behavior / child / pet")
    summary: Optional[str] = None
    price_micro: int = Field(0, ge=0)
    product_code: Optional[str] = None
    redflag_first: bool = True
    redflag_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    content_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    review_child_signoff: Optional[str] = None
    review_pet_signoff: Optional[str] = None
    status: str = Field("draft", description="draft / on / off")


class ToolUpsertBody(BaseModel):
    """轻工具创建 / 更新请求体（RQ-12）。"""

    tool_code: str = Field(..., min_length=2, max_length=32)
    title: str = Field(..., min_length=1, max_length=128)
    tool_type: str = Field(..., description="checklist / parser")
    domain: str = Field("child", description="child / pet")
    summary: Optional[str] = None
    kb_refs: List[str] = Field(default_factory=list)
    content: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 100
    status: str = Field("on", description="on / off")
    confirm_token: Optional[str] = Field(None)


# ---------------------------------------------------------------------------
# 危机渠道清单（RQ-03 / 修复 N3 双数据源）
# ---------------------------------------------------------------------------
def _channel_view(row: CrisisChannel, mask_phone: bool) -> Dict[str, Any]:
    """后台渠道视图（可含号码，按角色脱敏）。

    Args:
        row: 渠道实例。
        mask_phone: 是否脱敏。

    Returns:
        渠道视图字典。
    """
    card = channel_service.to_public_card(row, mask_phone=mask_phone)
    card["id"] = row.id
    card["version"] = int(row.id or 1)
    return card


@router.get(
    "/admin/channels",
    summary="危机渠道清单",
    description="单一数据源：问答渠道卡与后台维护读同一张 crisis_channel 表（RQ-03 / DR-26）",
)
def admin_list_channels(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """列出危机渠道清单（AC-RQ03-2 单一数据源）。

    Args:
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{items[], summary, categories}。

    Raises:
        ApiError: 1103 缺少 channel:view。
    """
    require_admin_perm(admin, "channel:view")
    mask = admin.role in ("support",)
    rows = (
        db.query(CrisisChannel)
        .order_by(CrisisChannel.sort_weight.asc(), CrisisChannel.id.asc())
        .all()
    )
    return ok(
        {
            "items": [_channel_view(row, mask) for row in rows],
            "summary": channel_service.verified_summary(db),
            "categories": channel_service.CATEGORIES,
            "data_source": "crisis_channel",
        }
    )


@router.post(
    "/admin/channels",
    summary="新增危机渠道",
    description="号码未核验时留空（禁止编造）；新增后需走核验接口留痕",
)
def admin_create_channel(
    body: ChannelBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """新增渠道条目（AC-RQ03-1/3）。

    Args:
        body: 创建请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：渠道视图。

    Raises:
        ApiError: 1103 缺 channel:edit；1001 编码已存在。
    """
    require_admin_perm(admin, "channel:edit")
    exists = (
        db.query(CrisisChannel)
        .filter(CrisisChannel.channel_code == body.channel_code)
        .first()
    )
    if exists is not None:
        raise ApiError(code=1001, message="渠道编码已存在", http_status=409)
    row = CrisisChannel(
        channel_code=body.channel_code,
        channel_name=body.channel_name,
        phone_number=body.phone_number or None,
        category=body.category,
        region=body.region,
        service_hours=body.service_hours,
        script=body.script,
        sort_weight=body.sort_weight,
        category_scope=list(body.applicable_categories),
        status=(
            channel_service.STATUS_ACTIVE
            if body.phone_number
            else channel_service.STATUS_PLACEHOLDER
        ),
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        admin,
        action="channel_create",
        object_type="crisis_channel",
        object_id=body.channel_code,
        reason="新增危机渠道",
        after={"channel_code": body.channel_code, "category": body.category},
    )
    db.commit()
    return ok(_channel_view(row, mask_phone=False))


@router.put(
    "/admin/channels/{channel_code}",
    summary="编辑危机渠道",
    description="修改号码需二次确认 + 原因 + 渠道编码后 4 位（对齐 V3.0 §3.4）",
)
def admin_update_channel(
    channel_code: str,
    body: ChannelUpdateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """编辑渠道条目（RO-03 二次确认机制）。

    Args:
        channel_code: 渠道编码。
        body: 更新请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：渠道视图。

    Raises:
        ApiError: 1002 不存在；1103 缺 channel:edit；1602 改号码缺二次确认；
            1001 后 4 位校验不通过。
    """
    require_admin_perm(admin, "channel:edit")
    row = (
        db.query(CrisisChannel)
        .filter(CrisisChannel.channel_code == channel_code)
        .first()
    )
    if row is None:
        raise ApiError(*ERR_NOT_FOUND)
    payload = body.model_dump(exclude_none=True)
    phone_changed = (
        body.phone_number is not None and body.phone_number != row.phone_number
    )
    if phone_changed:
        require_confirm(body.confirm_token, "channel_phone_change")
        suffix = (body.channel_code_suffix or "").strip()
        if suffix != channel_code[-4:]:
            raise ApiError(
                code=1001,
                message="渠道编码后 4 位校验不通过",
                http_status=422,
            )
        if not body.reason or body.reason == "-":
            raise ApiError(code=1001, message="修改号码必须填写原因", http_status=422)
    before = {
        "channel_name": row.channel_name,
        "phone_number": "***" if row.phone_number else None,
        "status": row.status,
    }
    try:
        channel_service.apply_channel_payload(row, payload)
    except ValueError as exc:
        # apply_channel_payload 状态强校验失败（非法 status 会导致下架渠道号码透出 C 端）
        raise ApiError(code=1001, message=str(exc), http_status=422)
    db.flush()
    write_audit(
        db,
        admin,
        action="channel_update",
        object_type="crisis_channel",
        object_id=channel_code,
        reason=body.reason or "-",
        before=before,
        after={
            "channel_name": row.channel_name,
            "phone_number": "***" if row.phone_number else None,
            "status": row.status,
        },
        confirm_used=bool(body.confirm_token),
    )
    db.commit()
    return ok(_channel_view(row, mask_phone=False))


@router.post(
    "/admin/channels/{channel_code}/review",
    summary="提交渠道核验记录",
    description="人工拨测/官网核对结论留痕（≥3 年），成功核验后自动顺延复核到期日",
)
def admin_review_channel(
    channel_code: str,
    body: ChannelReviewBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """写入渠道核验记录（AC-RQ03-5）。

    Args:
        channel_code: 渠道编码。
        body: 核验请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{review_no, channel, summary}。

    Raises:
        ApiError: 1002 不存在；1103 缺 channel:review；1001 方式/结论非法。
    """
    require_admin_perm(admin, "channel:review")
    row = (
        db.query(CrisisChannel)
        .filter(CrisisChannel.channel_code == channel_code)
        .first()
    )
    if row is None:
        raise ApiError(*ERR_NOT_FOUND)
    try:
        record = channel_service.record_review(
            db,
            row,
            reviewer=admin.username,
            method=body.review_method,
            result=body.review_result,
            conclusion=body.conclusion,
            note=body.note,
        )
    except ValueError as exc:
        raise ApiError(code=1001, message=str(exc), http_status=422)
    write_audit(
        db,
        admin,
        action="channel_review_done",
        object_type="crisis_channel",
        object_id=channel_code,
        reason=body.conclusion or "-",
        after={"review_result": body.review_result, "method": body.review_method},
    )
    db.commit()
    return ok(
        {
            "review_no": record.review_no,
            "channel": _channel_view(row, mask_phone=False),
            "summary": channel_service.verified_summary(db),
        }
    )


@router.get(
    "/admin/channels/{channel_code}/reviews",
    summary="渠道核验记录",
    description="按时间倒序返回核验留痕（核验人/方式/结论/时间/版本）",
)
def admin_channel_reviews(
    channel_code: str,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """列出渠道核验记录（AC-RQ03-5 留档可查）。

    Args:
        channel_code: 渠道编码。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{items[]}。

    Raises:
        ApiError: 1103 缺 channel:view。
    """
    require_admin_perm(admin, "channel:view")
    rows = (
        db.query(ChannelReviewRecord)
        .filter(ChannelReviewRecord.channel_code == channel_code)
        .order_by(ChannelReviewRecord.reviewed_at.desc())
        .limit(50)
        .all()
    )
    return ok(
        {
            "items": [
                {
                    "review_no": row.review_no,
                    "review_method": row.review_method,
                    "review_result": row.review_result,
                    "reviewer": row.reviewer,
                    "conclusion": row.conclusion,
                    "note": row.note,
                    "channel_version": row.channel_version,
                    "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
                }
                for row in rows
            ]
        }
    )


# ---------------------------------------------------------------------------
# 分级规则（RQ-06）
# ---------------------------------------------------------------------------
def _rule_view(row: TriageRule) -> Dict[str, Any]:
    """分级规则视图（后台可配置口径）。

    Args:
        row: 规则实例。

    Returns:
        规则视图字典。
    """
    return {
        "rule_id": row.rule_id,
        "scene": row.scene,
        "domain": row.domain,
        "title": row.title,
        "age_min_months": row.age_min_months,
        "age_max_months": row.age_max_months,
        "conditions": row.conditions,
        "level": row.level,
        "priority": row.priority,
        "basis": row.basis,
        "observations": row.observations or [],
        "escalation_flags": row.escalation_flags or [],
        "contraindications": row.contraindications or [],
        "disclaimers": row.disclaimers or [],
        "source_ref": row.source_ref,
        "expert_signoff": row.expert_signoff,
        "expert_reviewed_at": (
            row.expert_reviewed_at.isoformat() if row.expert_reviewed_at else None
        ),
        "status": row.status,
        "version": row.version,
    }


@router.get(
    "/admin/triage-rules",
    summary="分级规则列表",
    description="条目化分级规则（RQ-06 AC-6）：可配置、带来源与专家审核记录",
)
def admin_list_triage_rules(
    scene: Optional[str] = None,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """列出分级规则（含专家确认状态）。

    Args:
        scene: 场景过滤。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{items[], snapshot, signed_ratio}。

    Raises:
        ApiError: 1103 缺 triage:view。
    """
    require_admin_perm(admin, "triage:view")
    query = db.query(TriageRule)
    if scene:
        query = query.filter(TriageRule.scene == scene)
    rows = query.order_by(TriageRule.scene.asc(), TriageRule.priority.desc()).all()
    snapshot = triage_engine.load_rules(db, force_refresh=True)
    signed = sum(1 for row in rows if row.expert_signoff)
    return ok(
        {
            "items": [_rule_view(row) for row in rows],
            "snapshot": triage_engine.rule_summary(snapshot),
            "signed": signed,
            "total": len(rows),
            "gate_ready": bool(rows) and signed == len(rows),
        }
    )


@router.put(
    "/admin/triage-rules/{rule_id}",
    summary="编辑分级规则",
    description="阈值/档位变更需二次确认 + 原因；变更后规则快照 60 秒内生效",
)
def admin_update_triage_rule(
    rule_id: str,
    body: TriageRuleUpdateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """编辑分级规则（AC-RQ06-6）。

    Args:
        rule_id: 规则编码。
        body: 更新请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{rule, snapshot}。

    Raises:
        ApiError: 1002 不存在；1103 缺 triage:edit；1602 缺二次确认；1001 档位非法。
    """
    require_admin_perm(admin, "triage:edit")
    row = db.query(TriageRule).filter(TriageRule.rule_id == rule_id).first()
    if row is None:
        raise ApiError(*ERR_NOT_FOUND)
    if body.level is not None and body.level not in ("red", "yellow", "green"):
        raise ApiError(code=1001, message="level 必须为 red/yellow/green", http_status=422)
    if body.status is not None and body.status not in ("active", "inactive", "draft"):
        # 快照加载只取 status=="active"（triage/engine.py），非法值会导致规则静默失效
        raise ApiError(code=1001, message="status 必须为 active/inactive/draft", http_status=422)
    require_confirm(body.confirm_token, "triage_rule_change")
    before = {
        "level": row.level,
        "priority": row.priority,
        "conditions": row.conditions,
        "status": row.status,
    }
    for field, attr in (
        ("title", "title"),
        ("level", "level"),
        ("priority", "priority"),
        ("conditions", "conditions"),
        ("basis", "basis"),
        ("observations", "observations"),
        ("escalation_flags", "escalation_flags"),
        ("contraindications", "contraindications"),
        ("disclaimers", "disclaimers"),
        ("status", "status"),
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(row, attr, value)
    row.version = int(row.version or 1) + 1
    row.updated_at = datetime.now(_TZ_SHANGHAI)
    db.flush()
    write_audit(
        db,
        admin,
        action="triage_rule_change",
        object_type="triage_rule",
        object_id=rule_id,
        reason=body.reason or "-",
        before=before,
        after={
            "level": row.level,
            "priority": row.priority,
            "conditions": row.conditions,
            "status": row.status,
            "version": row.version,
        },
        confirm_used=True,
    )
    db.commit()
    snapshot = triage_engine.load_rules(db, force_refresh=True)
    return ok({"rule": _rule_view(row), "snapshot": triage_engine.rule_summary(snapshot)})


@router.post(
    "/admin/triage-rules/{rule_id}/review",
    summary="分级规则专家确认",
    description="首批/变更规则须专家书面确认后才满足发布门禁（§7.2）",
)
def admin_signoff_triage_rule(
    rule_id: str,
    body: TriageReviewBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """专家确认留痕（§7.2 门禁前置条件）。

    Args:
        rule_id: 规则编码。
        body: 确认请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{rule, gate_ready, signed, total}。

    Raises:
        ApiError: 1002 不存在；1103 缺 triage:review。
    """
    # super_admin 持 "*" 通配；育儿 / 宠物专家持 triage:review（域内确认）
    require_admin_perm(admin, "triage:review")
    row = db.query(TriageRule).filter(TriageRule.rule_id == rule_id).first()
    if row is None:
        raise ApiError(*ERR_NOT_FOUND)
    row.expert_signoff = body.expert_signoff
    row.expert_reviewed_at = datetime.now(_TZ_SHANGHAI)
    db.flush()
    write_audit(
        db,
        admin,
        action="triage_rule_signoff",
        object_type="triage_rule",
        object_id=rule_id,
        reason=body.note or "-",
        after={"expert_signoff": body.expert_signoff},
    )
    db.commit()
    rows = db.query(TriageRule).all()
    signed = sum(1 for item in rows if item.expert_signoff)
    return ok(
        {
            "rule": _rule_view(row),
            "signed": signed,
            "total": len(rows),
            "gate_ready": bool(rows) and signed == len(rows),
        }
    )


# ---------------------------------------------------------------------------
# 文案合规扫描（RQ-02）
# ---------------------------------------------------------------------------
@router.post(
    "/admin/copy-scan",
    summary="文案合规扫描",
    description="全量仓库扫描或指定文案扫描；命中即 blocked（fail-closed 口径）",
)
def admin_copy_scan(
    body: CopyScanBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """执行拟人化文案扫描（AC-RQ02-1 / NFR-C14）。

    Args:
        body: 扫描请求体（texts 为空时扫描全仓库）。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{mode, result, checklist}。

    Raises:
        ApiError: 1103 缺 content:view。
    """
    require_admin_perm(admin, "content:view")
    from ...compliance import copy_scan

    if body.texts:
        result = copy_scan.check_texts(body.texts)
        mode = "texts"
    else:
        result = copy_scan.scan_repository()
        mode = "repository"
    write_audit(
        db,
        admin,
        action="copy_scan_result",
        object_type="copy_scan",
        object_id=mode,
        reason="-",
        after={"hit_count": len(result.hits), "blocked": result.blocked},
    )
    db.commit()
    return ok(
        {
            "mode": mode,
            "result": result.as_dict(),
            "checklist": copy_scan.checklist(),
        }
    )


# ---------------------------------------------------------------------------
# 触达统计（RQ-08）
# ---------------------------------------------------------------------------
@router.get(
    "/admin/reminders/stats",
    summary="触达任务统计",
    description="按类型/状态统计提醒任务；仅出统计与状态，不展示问答原文",
)
def admin_reminder_stats(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """触达统计（AC-RQ08 后台口径）。

    Args:
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{total, by_type, by_status, delivered_by_channel, send_fail}。

    Raises:
        ApiError: 1103 缺 content:view。
    """
    require_admin_perm(admin, "content:view")
    rows = db.query(ReminderTask).all()
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    delivered = {"subscribe_message": 0, "inbox": 0}
    send_fail = 0
    for row in rows:
        by_type[row.task_type] = by_type.get(row.task_type, 0) + 1
        by_status[row.status] = by_status.get(row.status, 0) + 1
        key = "subscribe_message" if row.template_id else "inbox"
        delivered[key] = delivered.get(key, 0) + 1
        if int(row.send_fail_count or 0) > 0:
            send_fail += 1
    return ok(
        {
            "total": len(rows),
            "by_type": by_type,
            "by_status": by_status,
            "delivered_by_channel": delivered,
            "send_fail": send_fail,
            "privacy_note": "统计不含任何问答原文与档案明细（对齐 §9.5）",
        }
    )


# ---------------------------------------------------------------------------
# 内容运营：专题包 / 轻工具（RQ-12 / RQ-13 / RQ-14）
# ---------------------------------------------------------------------------
@router.get(
    "/admin/topics",
    summary="专题包列表（后台）",
    description="含未上架草稿；交叉主题包展示双签状态与上架校验问题",
)
def admin_list_topics(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """后台专题包列表（含草稿与上架校验）。

    Args:
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{items[]}。

    Raises:
        ApiError: 1103 缺 content:view。
    """
    require_admin_perm(admin, "content:view")
    rows = db.query(TopicPack).order_by(TopicPack.id.asc()).all()
    items = []
    for row in rows:
        # 后台视图返回**原始** redflag_blocks / content_blocks（不合并），
        # 便于编辑回填后原样保存，不产生「红旗块重复」问题
        items.append(
            {
                "topic_code": row.topic_code,
                "title": row.title,
                "domain": row.domain,
                "summary": row.summary,
                "price_micro": int(row.price_micro or 0),
                "product_code": row.product_code,
                "redflag_first": bool(row.redflag_first),
                "redflag_blocks": list(row.redflag_blocks or []),
                "content_blocks": list(row.content_blocks or []),
                "review_child_signoff": row.review_child_signoff,
                "review_pet_signoff": row.review_pet_signoff,
                "status": row.status,
                "version": row.version,
                "member_included": False,
                "disclaimer": topic_service.TOPIC_DISCLAIMER,
                "publish_issues": topic_service.validate_publish(row),
            }
        )
    return ok({"items": items})


@router.post(
    "/admin/topics",
    summary="新增或更新专题包",
    description="交叉主题包须育儿+宠物专家双签；行为内容线须红旗前置结构合规",
)
def admin_upsert_topic(
    body: TopicBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """新增 / 更新专题包（AC-RQ13-1/2 / AC-RQ14-1）。

    Args:
        body: 专题包请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{topic, publish_issues}。

    Raises:
        ApiError: 1103 缺 content:edit；1001 领域或结构非法。
    """
    require_admin_perm(admin, "content:edit")
    if body.domain not in topic_service.DOMAINS:
        raise ApiError(code=1001, message="domain 非法", http_status=422)
    row = (
        db.query(TopicPack).filter(TopicPack.topic_code == body.topic_code).first()
    )
    created = row is None
    if row is None:
        row = TopicPack(topic_code=body.topic_code, title=body.title, domain=body.domain)
        db.add(row)
    row.title = body.title
    row.domain = body.domain
    row.summary = body.summary
    row.price_micro = body.price_micro
    row.product_code = body.product_code
    row.redflag_first = body.redflag_first
    row.redflag_blocks = body.redflag_blocks
    row.content_blocks = body.content_blocks
    row.review_child_signoff = body.review_child_signoff
    row.review_pet_signoff = body.review_pet_signoff
    row.status = body.status
    row.version = int(row.version or 1) + 1 if not created else 1
    db.flush()
    issues = topic_service.validate_publish(row)
    if row.status == "on" and issues:
        db.rollback()
        raise ApiError(
            code=1001,
            message="专题包不满足上架条件：" + "；".join(issues),
            http_status=422,
        )
    write_audit(
        db,
        admin,
        action="topic_upsert",
        object_type="topic_pack",
        object_id=body.topic_code,
        reason="内容运营维护",
        after={"status": row.status, "domain": row.domain},
    )
    db.commit()
    return ok({"topic": topic_service.to_public(row), "publish_issues": issues})


@router.get(
    "/admin/tools",
    summary="轻工具列表（后台）",
    description="含未上架条目；内容命中确定性进食结论即拒绝保存",
)
def admin_list_tools(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """后台轻工具列表。

    Args:
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{items[]}。

    Raises:
        ApiError: 1103 缺 content:view。
    """
    require_admin_perm(admin, "content:view")
    rows = db.query(ToolItem).order_by(ToolItem.sort_order.asc()).all()
    items = [
        {
            "tool_code": row.tool_code,
            "title": row.title,
            "tool_type": row.tool_type,
            "domain": row.domain,
            "summary": row.summary,
            "kb_refs": row.kb_refs or [],
            # 后台编辑需要回显正文内容（对话接口不外泄，管理角色可读）
            "content": row.content or {},
            "status": row.status,
            "version": row.version,
            "sort_order": row.sort_order,
            "issues": tool_service.validate_tool_content(row.content or {}),
        }
        for row in rows
    ]
    return ok({"items": items})


@router.post(
    "/admin/tools",
    summary="新增或更新轻工具",
    description="内容来自知识资产（kb_refs 可追溯）；含确定性进食结论即拒绝（AC-RQ12-4）",
)
def admin_upsert_tool(
    body: ToolUpsertBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """新增 / 更新轻工具（AC-RQ12-1/4）。

    Args:
        body: 工具请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{tool_code, status}。

    Raises:
        ApiError: 1103 缺 content:edit；1001 内容违规或类型非法。
    """
    require_admin_perm(admin, "content:edit")
    if body.tool_type not in (tool_service.TOOL_CHECKLIST, tool_service.TOOL_PARSER):
        raise ApiError(code=1001, message="tool_type 非法", http_status=422)
    issues = tool_service.validate_tool_content(body.content)
    if issues:
        raise ApiError(
            code=1001, message="；".join(issues), http_status=422
        )
    row = db.query(ToolItem).filter(ToolItem.tool_code == body.tool_code).first()
    if row is None:
        row = ToolItem(tool_code=body.tool_code, title=body.title, tool_type=body.tool_type)
        db.add(row)
    row.title = body.title
    row.tool_type = body.tool_type
    row.domain = body.domain
    row.summary = body.summary
    row.kb_refs = body.kb_refs
    row.content = body.content
    row.sort_order = body.sort_order
    row.status = body.status
    row.version = int(row.version or 1) + 1
    db.flush()
    write_audit(
        db,
        admin,
        action="tool_upsert",
        object_type="tool_item",
        object_id=body.tool_code,
        reason="内容运营维护",
        after={"status": row.status, "tool_type": row.tool_type},
    )
    db.commit()
    return ok({"tool_code": row.tool_code, "status": row.status})


# ---------------------------------------------------------------------------
# 发布门禁自检（V3.1 §7.2）
# ---------------------------------------------------------------------------
@router.get(
    "/admin/gates/summary",
    summary="V3.1 发布门禁自检",
    description="四项阻塞门禁（AI 标识三链路 / 拟人化零命中 / 渠道核验 / 分级规则专家确认）当前状态",
)
def admin_gates_summary(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """发布门禁自检汇总（PM/合规看板用）。

    Args:
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{gates[], passed}。

    Raises:
        ApiError: 1103 缺 content:view。
    """
    require_admin_perm(admin, "content:view")
    from ...compliance import ai_label as labels
    from ...compliance import copy_scan
    from ...services import png_meta, report_image

    sample, meta = report_image.render_report_long_image(
        report_uid="gate-check",
        title="门禁自检样张",
        sections=[{"title": "自检", "content": "用于门禁校验。"}],
        trust_items=[labels.AI_LABEL_FALLBACK_TEXT],
    )
    readback = png_meta.read_text_metadata(sample)
    ai_label_ok = (
        meta["ratio"] >= labels.LONG_IMAGE_LABEL_MIN_RATIO
        and meta["count"] >= labels.LONG_IMAGE_LABEL_MIN_COUNT
        and all(readback.get(key) for key in labels.required_png_keys())
    )
    scan = copy_scan.scan_repository()
    channel_summary = channel_service.verified_summary(db)
    channel_ok = not channel_summary["missing_required"] and channel_summary["verified"] > 0
    rules = db.query(TriageRule).all()
    triage_ok = bool(rules) and all(row.expert_signoff for row in rules)
    # D-09：订阅消息模板未报备时站外触达不成立，纳入发布门禁显式暴露
    # （真实模板 ID 需在微信公众平台报备后回填环境变量，代码侧只能门禁+兜底）。
    settings = get_settings()
    template_keys = {
        "vaccine": settings.reminder_template_vaccine,
        "report": settings.reminder_template_report,
        "weekly_q": settings.reminder_template_weekly_q,
    }
    missing_templates = [key for key, value in template_keys.items() if not value]
    templates_ok = not missing_templates
    gates = [
        {
            "id": "ai_label_three_links",
            "title": "AI 标识三链路抽检（E2E-20）",
            "passed": ai_label_ok,
            "detail": {
                "ratio": meta["ratio"],
                "count": meta["count"],
                "metadata": readback,
            },
        },
        {
            "id": "copy_scan_zero_hit",
            "title": "拟人化禁用词全量扫描（E2E-21）",
            "passed": not scan.blocked,
            "detail": {
                "hit_count": len(scan.hits),
                "scanned_files": scan.scanned_files,
                "errors": scan.errors,
            },
        },
        {
            "id": "channel_verified",
            "title": "渠道清单核验（E2E-22）",
            "passed": channel_ok,
            "detail": channel_summary,
        },
        {
            "id": "triage_rules_signed",
            "title": "分级决策规则上线评审（E2E-19）",
            "passed": triage_ok,
            "detail": {
                "total": len(rules),
                "signed": sum(1 for row in rules if row.expert_signoff),
            },
        },
        {
            "id": "reminder_templates_reported",
            "title": "订阅消息模板报备（D-09）",
            "passed": templates_ok,
            "detail": {
                "configured": [key for key, value in template_keys.items() if value],
                "missing": missing_templates,
                "fallback": "未配置时仅站内补达，不发送外部订阅消息",
            },
        },
        {
            # D-10：专题包需完成双签并上架后才会出现在用户端；此处显式暴露
            "id": "topics_published",
            "title": "专题包上架（RQ-13 / RQ-14）",
            "passed": bool(topic_service.list_topics(db)),
            "detail": {
                "published": len(topic_service.list_topics(db)),
                "hint": "草稿需补齐专家签署与红旗前置后，在内容运营页上架",
            },
        },
    ]
    return ok({"gates": gates, "passed": all(gate["passed"] for gate in gates)})


# ---------------------------------------------------------------------------
# Agent 权重配置（F12.7 / AC-F12-07-1~3）
# ---------------------------------------------------------------------------
class AgentWeightBody(BaseModel):
    """权重更新请求体。

    Attributes:
        weights: {child: 0~1, pet: 0~1}，两者之和必须为 1。
        reason: 变更原因（必填，用于审计与历史）。
        confirm_token: 二次确认凭证。
    """

    weights: Dict[str, float] = Field(..., description="领域权重 child/pet")
    reason: str = Field(..., min_length=4, max_length=128, description="变更原因")
    confirm_token: str = Field(..., description="二次确认凭证")


class AgentWeightRollbackBody(BaseModel):
    """权重回滚请求体。

    Attributes:
        version: 回滚目标版本号。
        reason: 回滚原因（必填）。
        confirm_token: 二次确认凭证。
    """

    version: int = Field(..., ge=1, description="目标版本号")
    reason: str = Field(..., min_length=4, max_length=128, description="回滚原因")
    confirm_token: str = Field(..., description="二次确认凭证")


@router.get(
    "/admin/agent-weights",
    summary="Agent 展示权重（当前生效）",
    description="超管可读；返回 child/pet 权重、版本与安全分节固定置顶说明（F12.7）",
)
def admin_get_agent_weights(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """读取当前生效权重。

    Args:
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{weights, version, updated_at, operator_id, reason,
        defaults, safety_pinned}。

    Raises:
        ApiError: 1103 缺 cfg:write。
    """
    require_admin_perm(admin, "cfg:write")
    return ok(agent_weight_service.get_active(db))


@router.put(
    "/admin/agent-weights",
    summary="更新 Agent 展示权重",
    description="超管 + 二次确认 + 变更原因；写新版本并返回前后 diff（AC-F12-07-1/2）",
)
def admin_update_agent_weights(
    body: AgentWeightBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """保存新权重版本。

    Args:
        body: 权重更新请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{weights, version, before, diff, rollback_from_version}。

    Raises:
        ApiError: 1103 缺权限；1602 缺少二次确认；1001 权重非法。
    """
    require_admin_perm(admin, "cfg:write")
    require_confirm(body.confirm_token, "agent_weight_update")
    try:
        result = agent_weight_service.save_weights(
            db, admin.id, body.weights, body.reason
        )
    except agent_weight_service.WeightValidationError as exc:
        raise ApiError(code=1001, message=str(exc), http_status=422) from exc
    write_audit(
        db,
        admin,
        action="agent_weight_update",
        object_type="config_version",
        object_id=agent_weight_service.CONFIG_KEY,
        reason=body.reason,
        before={"weights": result["before"]},
        after={"weights": result["weights"], "version": result["version"]},
        confirm_used=True,
    )
    db.commit()
    return ok(result)


@router.get(
    "/admin/agent-weights/history",
    summary="Agent 权重历史",
    description="按版本倒序返回历史快照、原因与操作人，供回滚选择（AC-F12-07-3）",
)
def admin_agent_weight_history(
    limit: int = 20,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """读取权重历史版本。

    Args:
        limit: 最大返回条数（1–100）。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：{items}。

    Raises:
        ApiError: 1103 缺 cfg:write。
    """
    require_admin_perm(admin, "cfg:write")
    return ok({"items": agent_weight_service.list_history(db, limit)})


@router.post(
    "/admin/agent-weights/rollback",
    summary="回滚 Agent 权重",
    description="按历史版本回滚，生成新版本并留痕（AC-F12-07-3）",
)
def admin_rollback_agent_weights(
    body: AgentWeightRollbackBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
) -> dict:
    """回滚到指定权重版本。

    Args:
        body: 回滚请求体。
        admin: 当前后台账号。
        db: 数据库会话。

    Returns:
        统一包络：save_weights 结果 + 回滚来源版本。

    Raises:
        ApiError: 1103 缺权限；1602 缺少二次确认；1002 目标版本不存在。
    """
    require_admin_perm(admin, "cfg:write")
    require_confirm(body.confirm_token, "agent_weight_rollback")
    try:
        result = agent_weight_service.rollback_to(
            db, admin.id, body.version, body.reason
        )
    except agent_weight_service.WeightValidationError as exc:
        raise ApiError(*ERR_NOT_FOUND) from exc
    write_audit(
        db,
        admin,
        action="agent_weight_rollback",
        object_type="config_version",
        object_id=agent_weight_service.CONFIG_KEY,
        reason=body.reason,
        before={"version": body.version},
        after={"weights": result["weights"], "version": result["version"]},
        confirm_used=True,
    )
    db.commit()
    return ok(result)

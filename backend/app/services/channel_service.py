# -*- coding: utf-8 -*-
"""危机渠道清单服务（RQ-03）：单一数据源 + 核验机制 + 过期降级。

关键口径（逐条落地 PRD §3.3）：

- **单一数据源**（AC-RQ03-2 / DR-26）：号码只存 `crisis_channel.phone_number`，
  前台渠道卡、后台维护页、配置视图全部读这一张表；任何前端 / 常量文件不得
  出现硬编码号码（CI 断言见 `scripts/check_hardcoded_phones.py`）。
- **空态与占位**（AC-RQ03-3）：某类别无 active 条目或号码未回填时，
  下发 `status=placeholder` + 「渠道信息维护中」，**不得编造号码**。
- **超期降级**（AC-RQ03-4）：`next_review_due_at` 到期未复核的条目自动转
  `pending_review`，前端**不再展示号码**（只展示名称与「信息更新中」）。
- **核验留痕**（AC-RQ03-5）：每次核验写 `channel_review_record`（≥3 年）。
- **角色脱敏**（§3.3.4）：无权限角色看到的号码字段脱敏为 `***`。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import ChannelReviewRecord, CrisisChannel

logger = logging.getLogger("jiaban.channel")

# 上海时区（复核到期判定口径）
_TZ_SHANGHAI = timezone(timedelta(hours=8))

# 渠道状态
STATUS_ACTIVE = "active"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_PLACEHOLDER = "placeholder"
STATUS_RETIRED = "retired"
VALID_STATUSES = (STATUS_ACTIVE, STATUS_PENDING_REVIEW, STATUS_PLACEHOLDER, STATUS_RETIRED)

# 渠道类目（PRD §3.3.3）
CATEGORIES = {
    "psychological": "心理援助",
    "pediatric_emergency": "儿科急诊",
    "pet_emergency": "宠物急诊",
    "police": "报警求助",
    "minor_protection": "未成年人保护",
}

# 高危类别 → 必需渠道类目（AC-RQ03-6：儿童自伤 / 虐待必须同时含 110 与 12345）
REQUIRED_CATEGORIES: Dict[str, List[str]] = {
    "child_abuse": ["police", "minor_protection"],
    "child_selfharm": ["police", "psychological"],
    "harmful_to_minor": ["minor_protection"],
    "high_fever": ["pediatric_emergency"],
    "animal_bite": ["pediatric_emergency"],
    "pet_poison": ["pet_emergency"],
    "pet_bleeding": ["pet_emergency"],
    # 严重抑郁（软类别）→ 心理援助热线；误食药物 / 风险服务不可用 → 儿科急诊
    "depression": ["psychological"],
    "medicine_dosage": ["pediatric_emergency"],
    "risk_unavailable": ["pediatric_emergency"],
}

# 维护中占位文案（文案非号码，经合规评审）
PLACEHOLDER_TEXT = "渠道信息维护中，请以官方渠道为准"
PENDING_REVIEW_TEXT = "信息更新中"
CALL_FALLBACK_TEXT = "紧急情况请立即拨打 120 或 110，并马上联系身边的成年人陪同"
MASKED_PHONE = "***"

# 单卡最多展示渠道条数（§3.3.4 极值：默认 ≤3 条，其余收进「更多渠道」）
MAX_CARDS = 3

# 默认复核周期（天，≤90 天）
DEFAULT_REVIEW_DAYS = 90


def _now() -> datetime:
    """当前上海时间。

    Returns:
        带时区的 datetime。
    """
    return datetime.now(_TZ_SHANGHAI)


def ensure_review_state(db: Session, channel: CrisisChannel) -> CrisisChannel:
    """按复核到期时间收敛渠道状态（AC-RQ03-4 自动降级）。

    Args:
        db: 数据库会话（仅用于标注是否需要提交，不在此处 commit）。
        channel: 渠道 ORM 实例。

    Returns:
        处理后的渠道实例（可能已改状态，未提交）。
    """
    due = channel.next_review_due_at
    if due is not None and channel.status == STATUS_ACTIVE and due <= _now():
        channel.status = STATUS_PENDING_REVIEW
        logger.warning(
            "channel %s 复核到期未复核，自动转 pending_review（前端不再展示号码）",
            channel.channel_code,
        )
    return channel


def sweep_expired(db: Session) -> int:
    """批量扫描并降级超期渠道（定时任务入口）。

    Args:
        db: 数据库会话。

    Returns:
        被降级的条目数。
    """
    rows = (
        db.query(CrisisChannel)
        .filter(
            CrisisChannel.status == STATUS_ACTIVE,
            CrisisChannel.next_review_due_at.isnot(None),
            CrisisChannel.next_review_due_at <= _now(),
        )
        .all()
    )
    for row in rows:
        row.status = STATUS_PENDING_REVIEW
    if rows:
        db.commit()
        logger.warning("channel sweep: %d channels downgraded to pending_review", len(rows))
    return len(rows)


def _scope_list(channel: CrisisChannel) -> List[str]:
    """读取渠道的适用高危类别清单（JSONB 容错）。

    Args:
        channel: 渠道实例。

    Returns:
        类别编码列表。
    """
    scope = channel.category_scope or []
    if isinstance(scope, str):
        import json

        try:
            scope = json.loads(scope)
        except Exception:  # noqa: BLE001
            scope = []
    return [str(item) for item in scope] if isinstance(scope, (list, tuple)) else []


def to_public_card(
    channel: CrisisChannel, mask_phone: bool = False, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """把渠道条目转为对外渠道卡（含占位与超期降级语义）。

    Args:
        channel: 渠道实例。
        mask_phone: 是否脱敏号码（无权限角色）。
        now: 当前时间（测试注入）。

    Returns:
        渠道卡字典：号码字段在占位 / 超期 / 脱敏场景下为 None。
    """
    current = now or _now()
    status = channel.status
    expired = (
        channel.next_review_due_at is not None and channel.next_review_due_at <= current
    )
    phone = channel.phone_number
    placeholder = False
    notice: Optional[str] = None
    if status in (STATUS_RETIRED,):
        phone = None
        placeholder = True
        notice = PLACEHOLDER_TEXT
    elif status == STATUS_PENDING_REVIEW or expired:
        # 超期未复核：不展示号码，只展示名称 + 更新中（AC-RQ03-4）
        phone = None
        placeholder = True
        notice = PENDING_REVIEW_TEXT
    elif not phone:
        # 号码未回填：占位，不编造（AC-RQ03-3）
        phone = None
        placeholder = True
        notice = PLACEHOLDER_TEXT
    if phone and mask_phone:
        phone = MASKED_PHONE
    return {
        "channel_code": channel.channel_code,
        "channel_name": channel.channel_name,
        "category": channel.category,
        "category_label": CATEGORIES.get(channel.category, channel.category),
        "phone_number": phone,
        "phone_masked": bool(phone and mask_phone),
        "script": channel.script,
        "region": channel.region,
        "service_hours": channel.service_hours,
        "applicable_categories": _scope_list(channel),
        "status": status,
        "placeholder": placeholder,
        "notice": notice,
        "verified_at": channel.verified_at.isoformat() if channel.verified_at else None,
        "verified_by": channel.verified_by,
        "review_due_at": (
            channel.next_review_due_at.isoformat() if channel.next_review_due_at else None
        ),
        "expired": expired,
        "source": "crisis_channel",
        # D-01：占位/超期渠道必须同时给出可执行兜底指引（110/120），
        # 避免拦截页只剩「维护中」而无任何可拨打电话。
        "fallback_text": CALL_FALLBACK_TEXT if placeholder else None,
    }


def get_channels_for_category(
    db: Session,
    category_code: Optional[str],
    mask_phone: bool = False,
    limit: int = MAX_CARDS,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """按风险类别返回渠道卡（单一数据源，替代旧的双轨读取）。

    Args:
        db: 数据库会话。
        category_code: 风险类别编码（None 返回空列表）。
        mask_phone: 是否脱敏号码。
        limit: 最大条数。
        now: 当前时间。

    Returns:
        渠道卡列表（按 sort_weight、类目优先序排序；占位条目同样返回，
        以便前端展示「维护中」而不是空卡片）。
    """
    if not category_code:
        return []
    wanted = set(REQUIRED_CATEGORIES.get(category_code, []))
    alias = {
        "risk_unavailable": {"pediatric_emergency"},
        "medicine_dosage": {"pediatric_emergency"},
    }.get(category_code, set())
    wanted |= alias

    rows = (
        db.query(CrisisChannel)
        .filter(CrisisChannel.status != STATUS_RETIRED)
        .order_by(CrisisChannel.sort_weight.asc(), CrisisChannel.id.asc())
        .all()
    )
    matched: List[CrisisChannel] = []
    for row in rows:
        scope = _scope_list(row)
        if category_code in scope or row.category in wanted:
            matched.append(row)
    if not matched:
        # 类别无任何条目：返回占位卡（不编造号码，AC-RQ03-3）
        return [
            {
                "channel_code": f"placeholder_{category_code}",
                "channel_name": CATEGORIES.get(
                    list(wanted)[0] if wanted else "pediatric_emergency", "求助渠道"
                ),
                "category": list(wanted)[0] if wanted else "pediatric_emergency",
                "category_label": "求助渠道",
                "phone_number": None,
                "phone_masked": False,
                "script": PLACEHOLDER_TEXT,
                "region": "全国",
                "service_hours": None,
                "applicable_categories": [category_code],
                "status": STATUS_PLACEHOLDER,
                "placeholder": True,
                "notice": PLACEHOLDER_TEXT,
                "verified_at": None,
                "verified_by": None,
                "review_due_at": None,
                "expired": False,
                "source": "placeholder",
                "fallback_text": CALL_FALLBACK_TEXT,
            }
        ]
    return [to_public_card(row, mask_phone=mask_phone, now=now) for row in matched[:limit]]


def missing_required_categories(db: Session) -> Dict[str, List[str]]:
    """检查各高危类别缺哪些必需渠道类目（发布门禁 E2E-22 自检）。

    Returns:
        {风险类别: [缺失类目]} 字典（仅包含有缺失的类别）。
    """
    rows = db.query(CrisisChannel).filter(CrisisChannel.status == STATUS_ACTIVE).all()
    have: Dict[str, set] = {}
    for row in rows:
        if not row.phone_number:
            continue  # 未回填号码不计为「已具备」
        if row.next_review_due_at is not None and row.next_review_due_at <= _now():
            continue  # 超期未复核不计
        for code in _scope_list(row):
            have.setdefault(code, set()).add(row.category)
        have.setdefault("*", set()).add(row.category)
    result: Dict[str, List[str]] = {}
    for code, required in REQUIRED_CATEGORIES.items():
        present = have.get(code, set())
        missing = [cat for cat in required if cat not in present]
        if missing:
            result[code] = missing
    return result


def verified_summary(db: Session) -> Dict[str, Any]:
    """渠道核验状态汇总（后台与发布门禁用）。

    Args:
        db: 数据库会话。

    Returns:
        {total, active, placeholder, pending_review, verified, categories} 摘要。
    """
    rows = db.query(CrisisChannel).all()
    by_category: Dict[str, Dict[str, int]] = {}
    verified = 0
    for row in rows:
        cat = row.category
        bucket = by_category.setdefault(cat, {"total": 0, "verified": 0})
        bucket["total"] += 1
        if row.phone_number and row.status == STATUS_ACTIVE:
            bucket["verified"] += 1
            verified += 1
    return {
        "total": len(rows),
        "active": sum(1 for r in rows if r.status == STATUS_ACTIVE),
        "placeholder": sum(1 for r in rows if r.status == STATUS_PLACEHOLDER),
        "pending_review": sum(1 for r in rows if r.status == STATUS_PENDING_REVIEW),
        "retired": sum(1 for r in rows if r.status == STATUS_RETIRED),
        "verified": verified,
        "by_category": by_category,
        "missing_required": missing_required_categories(db),
    }


def record_review(
    db: Session,
    channel: CrisisChannel,
    reviewer: str,
    method: str,
    result: str,
    conclusion: Optional[str] = None,
    note: Optional[str] = None,
) -> ChannelReviewRecord:
    """写入核验记录并同步渠道的核验字段（AC-RQ03-5）。

    Args:
        db: 数据库会话。
        channel: 渠道实例。
        reviewer: 核验人。
        method: 核验方式（call_dial / official_site / verbal / document）。
        result: 结论（reachable / unreachable / changed / pending）。
        conclusion: 结论说明。
        note: 备注。

    Returns:
        新建的核验记录（未 commit）。

    Raises:
        ValueError: 方式或结论非法。
    """
    if method not in ("call_dial", "official_site", "verbal", "document"):
        raise ValueError(f"invalid review method: {method}")
    if result not in ("reachable", "unreachable", "changed", "pending"):
        raise ValueError(f"invalid review result: {result}")
    now = _now()
    record = ChannelReviewRecord(
        channel_code=channel.channel_code,
        review_method=method,
        review_result=result,
        reviewer=reviewer,
        channel_version=int(channel.id or 1),
        conclusion=conclusion,
        note=note,
        reviewed_at=now,
    )
    db.add(record)
    channel.verified_by = reviewer
    channel.verified_at = now
    if result == "reachable":
        channel.status = STATUS_ACTIVE if channel.phone_number else STATUS_PLACEHOLDER
    elif result == "unreachable":
        # 号码失效：不再展示号码（占位），等待运营回填
        channel.status = STATUS_PENDING_REVIEW
    elif result == "changed":
        channel.status = STATUS_PENDING_REVIEW
    channel.next_review_due_at = now + timedelta(days=DEFAULT_REVIEW_DAYS)
    return record


def apply_channel_payload(channel: CrisisChannel, payload: Dict[str, Any]) -> CrisisChannel:
    """把后台提交的渠道字段写入实例（含版本号递增）。

    Args:
        channel: 渠道实例。
        payload: 字段字典（channel_name / phone_number / category / region /
            service_hours / applicable_categories / script / status / sort_weight）。

    Returns:
        更新后的渠道实例。

    Raises:
        ValueError: status 不在合法枚举（active/pending_review/placeholder/retired）内。

    Note:
        状态必须强校验：非法值（如文档曾误写的 inactive）一旦落库，
        C 端展示分支（retired/pending_review/无号码）全部不命中，
        已下架渠道的号码会原样透出到拦截卡（实测踩坑：续测 2026-10-21）。
    """
    status = payload.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"invalid channel status: {status}")
    mapping = {
        "channel_name": "channel_name",
        "phone_number": "phone_number",
        "category": "category",
        "region": "region",
        "service_hours": "service_hours",
        "script": "script",
        "status": "status",
        "sort_weight": "sort_weight",
    }
    for key, attr in mapping.items():
        if key in payload and payload[key] is not None:
            setattr(channel, attr, payload[key])
    if "applicable_categories" in payload and payload["applicable_categories"] is not None:
        channel.category_scope = list(payload["applicable_categories"])
    # 号码回填后自动转 active（未回填保持 placeholder）
    if channel.phone_number and channel.status == STATUS_PLACEHOLDER:
        channel.status = STATUS_ACTIVE
    return channel

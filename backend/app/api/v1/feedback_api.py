# -*- coding: utf-8 -*-
"""反馈/举报/个人信息 API 模块。

提供用户反馈提交、内容举报与当前用户信息查询：
- POST /feedback        反馈提交（敏感词前置检查 + 内容安全送检闭环，正文加密）
- POST /reports         内容举报（涉未成年人 24h SLA，其余 72h）
- GET  /me              当前用户信息（账号资料 + 会员状态 + 档案计数）
- PUT  /me/profile      更新账号资料（昵称）
- POST /me/avatar       上传账号头像（multipart，覆盖旧图）
- DELETE /me/avatar     移除账号头像（幂等）
- GET  /me/consents     同意状态简版

业务口径：反馈正文 Fernet 加密落库，附图 ≤3；反馈回执 72h；
送检流程 submit(reviewing) → 本地规则裁决 → resolve 回调（真实平台接入后改异步），
拒绝时反馈仍留档（audit_status=rejected）并返回 1303；
举报四分类，harmful_to_minor 加急；账号昵称加密落库、头像规范化 JPEG 存储。
"""
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.crypto import decrypt_field, encrypt_field
from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import ApiError
from ...db import get_db
from ...models import (
    AppUser,
    ChildProfile,
    ConsentRecord,
    ContentReport,
    Feedback,
    PetProfile,
)
from ...models.base import utcnow
from ...services.media_store import (
    AVATAR_MAX_SIDE,
    MediaValidationError,
    delete_file,
    save_image,
)
from ...services.safety_scan import VERDICT_TO_AUDIT_STATUS, SafetyScanService

router = APIRouter(tags=["feedback", "C端-权利反馈"])

# 反馈回执时长（小时）
FEEDBACK_RECEIPT_HOURS = 72

# 涉未成年人举报 SLA（小时）
MINOR_REPORT_SLA_HOURS = 24

# 普通举报 SLA（小时）
REPORT_SLA_HOURS = 72

# 推广引流敏感词（简单子串匹配；命中即拒绝 1303）
SENSITIVE_WORDS: List[str] = [
    "加微信", "加vx", "加v", "微信号", "vx号", "vx:", "weixin",
    "代购", "刷单", "兼职", "转账", "汇款", "招商", "招代理",
    "推广合作", "广告投放", "扫码", "进群",
]


class FeedbackBody(BaseModel):
    """反馈提交请求体。

    Attributes:
        content: 反馈正文（加密存储）。
        linked_session_id: 关联问答会话 ID（可选）。
        linked_report_id: 关联举报记录 ID（可选）。
        image_count: 附图数量，0-3。
    """

    content: str = Field(min_length=1, max_length=2000, description="反馈正文")
    linked_session_id: Optional[int] = Field(default=None, ge=1)
    linked_report_id: Optional[int] = Field(default=None, ge=1)
    image_count: int = Field(default=0, ge=0, le=3, description="附图数量 ≤3")


class ReportBody(BaseModel):
    """内容举报请求体。

    Attributes:
        object_type: 被举报对象类型（如 qa_answer / kb_entry / feedback）。
        object_id: 被举报对象标识。
        category: 举报分类（illegal/medical_misleading/harmful_to_minor/other）。
        description: 举报说明（可选，存 evidence）。
    """

    object_type: str = Field(min_length=1, max_length=16, description="对象类型")
    object_id: str = Field(min_length=1, max_length=64, description="对象标识")
    category: Literal["illegal", "medical_misleading", "harmful_to_minor", "other"] = (
        Field(description="举报分类")
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="举报说明"
    )


def _iso(value: Any) -> Optional[str]:
    """datetime 转 ISO8601 字符串。

    Args:
        value: datetime 实例或 None。

    Returns:
        ISO 字符串；入参为 None 时返回 None。
    """
    return value.isoformat() if value is not None else None


def _check_sensitive_words(content: str) -> None:
    """敏感词简单前置检查：命中推广引流词直接拒绝送检。

    Args:
        content: 用户提交文本。

    Returns:
        None。

    Raises:
        ApiError: 1303 内容包含违规推广信息。
    """
    lowered = content.lower()
    for word in SENSITIVE_WORDS:
        if word in lowered:
            raise ApiError(
                code=1303,
                message="内容包含违规推广信息，请修改后提交",
                http_status=403,
            )


def _consent_brief(db: Session, user_id: int) -> Dict[str, bool]:
    """查询同意状态简版（各类型是否处于已同意状态）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。

    Returns:
        {base: bool, child_personal_info: bool}。
    """
    result: Dict[str, bool] = {}
    for ctype in ("base", "child_personal_info"):
        record = (
            db.query(ConsentRecord)
            .filter(
                ConsentRecord.user_id == user_id,
                ConsentRecord.consent_type == ctype,
            )
            .order_by(ConsentRecord.id.desc())
            .first()
        )
        # 最新记录 withdraw_at 非空视为已撤回
        result[ctype] = record is not None and record.withdraw_at is None
    return result


@router.post("/feedback", summary="提交反馈（内容安全送检闭环）")
def create_feedback(
    body: FeedbackBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """提交反馈：敏感词前置检查 → 配额检查 → 送检闭环 → 反馈落库（正文加密）。

    送检闭环（本地模拟回调）：check_quota → submit(reviewing) →
    _local_rule_verdict 本地裁决 → resolve 置终态并删除送检副本。
    reject：Feedback.audit_status='rejected' 先行落库留档（合规审计），
    再抛 1303 拒绝受理；pass：audit_status='passed'、status='pending' 正常受理。

    Args:
        body: {content, linked_session_id?, linked_report_id?, image_count?}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{feedback_no, receipt_hours, audit_result}。

    Raises:
        ApiError: 1303 内容命中推广引流敏感词；1303 送检未通过（拒绝）；
                  1303(429) 当日送检配额超限。
    """
    # 前置敏感词检查：命中直接拒绝，不进入送检流程
    _check_sensitive_words(body.content)
    now = utcnow()
    feedback_no = f"FB{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    # 内容安全送检闭环：配额检查 → 提交（正文不落库仅存摘要）→ 本地裁决回调
    SafetyScanService.check_quota(db)
    record = SafetyScanService.submit(
        db,
        object_type="text",
        object_id=feedback_no,
        scene="feedback",
        content=body.content,
    )
    # 模拟平台回调：本地规则裁决后立即 resolve（真实平台接入后改为异步回调）
    verdict = SafetyScanService._local_rule_verdict(body.content)
    SafetyScanService.resolve(db, record.id, verdict=verdict, note="local-rule auto verdict")

    feedback = Feedback(
        feedback_no=feedback_no,
        user_id=user.id,
        # 正文密文落库，明文不出服务端
        content_enc=encrypt_field(body.content),
        char_len=len(body.content),
        linked_session_id=body.linked_session_id,
        linked_report_id=body.linked_report_id,
        image_count=body.image_count,
        audit_status="reviewing",
        status="pending",
    )
    db.add(feedback)
    db.flush()
    if verdict == "reject":
        # 拒绝：反馈仍留档供合规审计，随后抛送检未通过（手动提交规避统一回滚）
        feedback.audit_status = "rejected"
        db.commit()
        raise ApiError(code=1303, message="内容安全送检未通过", http_status=403)
    # 通过/人工复核：同步裁决状态，正常受理排队
    feedback.audit_status = VERDICT_TO_AUDIT_STATUS.get(verdict, verdict)
    feedback.status = "pending"
    return ok({
        "feedback_no": feedback_no,
        "receipt_hours": FEEDBACK_RECEIPT_HOURS,
        "audit_result": feedback.audit_status,
    })


@router.post("/reports", summary="一键举报（四分类/涉未成年加急）")
def create_report(
    body: ReportBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """提交内容举报：涉未成年人 24h SLA 加急，其余 72h。

    Args:
        body: {object_type, object_id, category, description?}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{report_no, sla_due_at}。
    """
    now = utcnow()
    involves_minor = body.category == "harmful_to_minor"
    # 涉未成年人加急处置
    sla_hours = MINOR_REPORT_SLA_HOURS if involves_minor else REPORT_SLA_HOURS
    sla_due_at = now + timedelta(hours=sla_hours)

    report = ContentReport(
        report_no=f"RP{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        user_id=user.id,
        object_type=body.object_type,
        object_id=body.object_id,
        category=body.category,
        involves_minor=involves_minor,
        sla_due_at=sla_due_at,
        # 举报说明存 evidence 留痕
        evidence={"description": body.description} if body.description else None,
    )
    db.add(report)
    db.flush()
    return ok({"report_no": report.report_no, "sla_due_at": _iso(sla_due_at)})


# 账号昵称长度上限（与儿童昵称保持同一输入约束）
NICKNAME_MAX_LENGTH = 20
# 账号头像媒体子目录（upload_dir 下）
USER_AVATAR_SUBDIR = "users"


def _media_url(rel_path: Optional[str]) -> Optional[str]:
    """媒体相对路径转对外 URL（/media 静态挂载）。

    Args:
        rel_path: 入库相对路径（如 "users/xxx.jpg"）。

    Returns:
        "/media/..." 前缀 URL；未设置时返回 None。
    """
    return f"/media/{rel_path}" if rel_path else None


def _user_profile_view(user: AppUser) -> Dict[str, Any]:
    """构造账号资料展示视图（昵称明文 + 头像 URL）。

    Args:
        user: 当前用户 ORM 实例。

    Returns:
        {"nickname": str, "avatar_url": str | None} 字典；未设置昵称时为空串，
        由客户端按默认称呼兜底。
    """
    nickname = decrypt_field(user.nickname_enc) if user.nickname_enc else ""
    return {"nickname": nickname, "avatar_url": _media_url(user.avatar_path)}


def _save_user_avatar_or_raise(data: bytes) -> Tuple[str, int, int, int]:
    """规范化保存账号头像（校验失败统一映射 1001）。

    Args:
        data: 原始上传字节。

    Returns:
        (相对路径, 宽, 高, 字节数)。

    Raises:
        ApiError: 1001 图片格式不支持或文件过大。
    """
    try:
        return save_image(data, USER_AVATAR_SUBDIR, AVATAR_MAX_SIDE)
    except MediaValidationError:
        raise ApiError(
            code=1001,
            message="图片格式不支持或文件过大，请换一张试试。",
            http_status=422,
        ) from None


class MeProfileUpdateBody(BaseModel):
    """账号资料更新请求体。

    Attributes:
        nickname: 昵称（1-20 字，加密存储）。
    """

    nickname: str = Field(
        min_length=1, max_length=NICKNAME_MAX_LENGTH, description="账号昵称"
    )


@router.get("/me", summary="我的信息")
def get_me(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户信息：账号资料、会员状态与到期时间、档案计数。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：用户信息字典（含 nickname / avatar_url）。
    """
    child_count = (
        db.query(func.count(ChildProfile.id))
        .filter(ChildProfile.user_id == user.id, ChildProfile.deleted_at.is_(None))
        .scalar()
        or 0
    )
    pet_count = (
        db.query(func.count(PetProfile.id))
        .filter(PetProfile.user_id == user.id, PetProfile.deleted_at.is_(None))
        .scalar()
        or 0
    )
    return ok({
        "user_uid": user.user_uid,
        **_user_profile_view(user),
        "member_status": user.member_status,
        "member_expire_at": _iso(user.member_expire_at),
        "child_profile_count": child_count,
        "pet_profile_count": pet_count,
        "register_at": _iso(user.register_at),
    })


@router.put("/me/profile", summary="更新账号资料")
def update_me_profile(
    body: MeProfileUpdateBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """更新账号资料：仅修改昵称，保存后立即生效。

    Args:
        body: {nickname}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：更新后的账号资料视图。

    Raises:
        ApiError: 1001 昵称仅含空白字符。
    """
    nickname = body.nickname.strip()
    if not nickname:
        raise ApiError(code=1001, message="昵称不能为空", http_status=422)
    # 昵称按手机号/儿童昵称同口径加密落库，响应回传明文供客户端即时回显
    user.nickname_enc = encrypt_field(nickname)
    db.flush()
    return ok(_user_profile_view(user))


@router.post(
    "/me/avatar",
    summary="上传账号头像",
    description="multipart 单文件（file 字段），服务端规范化 JPEG 存储并返回 avatar_url；"
    "覆盖旧头像时自动删除旧文件。",
)
def upload_me_avatar(
    file: UploadFile = File(..., description="图片文件（jpeg/png/webp，≤8MB）"),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """上传/更换账号头像（覆盖旧文件，幂等替换）。

    Args:
        file: 图片文件。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{avatar_url, width, height, size}。

    Raises:
        ApiError: 1001 图片格式不支持或文件过大。
    """
    rel, width, height, size = _save_user_avatar_or_raise(file.file.read())
    old_rel = user.avatar_path
    user.avatar_path = rel
    db.flush()
    if old_rel:
        # 数据库先行、旧文件后删（与档案头像同一口径）
        delete_file(old_rel)
    return ok(
        {"avatar_url": _media_url(rel), "width": width, "height": height, "size": size}
    )


@router.delete(
    "/me/avatar",
    summary="移除账号头像",
    description="置空头像并删除文件；未设置时同样成功（幂等）",
)
def remove_me_avatar(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """移除账号头像（幂等：未设置时也返回成功）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"deleted": true}。
    """
    old_rel = user.avatar_path
    user.avatar_path = None
    db.flush()
    if old_rel:
        delete_file(old_rel)
    return ok({"deleted": True})


@router.get("/me/consents", summary="我的同意状态")
def get_my_consents(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """当前用户同意状态简版（各类型是否处于已同意状态）。

    Args:
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{"consents": {base: bool, child_personal_info: bool}}。
    """
    return ok({"consents": _consent_brief(db, user.id)})
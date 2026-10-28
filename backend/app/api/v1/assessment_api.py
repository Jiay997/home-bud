# -*- coding: utf-8 -*-
"""气质测评 API 模块。

提供测评题库下发、断点开始/续填、单题作答、幂等提交计分与报告查询：
- GET  /assessment/questions                 16 题列表（题干按 age_band 选择，入口开关校验）
- POST /assessment/start                     开始/续填测评（90 天断点）
- PUT  /assessment/{uid}/answer              单题作答 upsert（raw_score=null 表示跳题）
- POST /assessment/{uid}/submit              幂等提交：计分 → 落库 → 生成 13 区块报告
- GET  /assessment/{uid}/report              报告查询（会员门控裁剪）

业务口径：PRD §12.2 冻结 16 题；测评不计问答额度；
报告 13 区块固定顺序，前 9 免费、后 4 会员门控（access_tier_map）。
"""
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...core.envelope import ok
from ...core.errors import (
    ApiError,
    ERR_IDEMPOTENT_PROCESSING,
    ERR_NOT_FOUND,
    raise_err,
)
from ...core.crypto import sha256_hex
from ...db import get_db
from ...models import (
    AppUser,
    Assessment,
    ChildProfile,
    ConfigVersion,
    IdempotencyKey,
    KbEntry,
    PetProfile,
    Report,
)
from ...models.base import gen_uuid, utcnow
from ...services.assessment_service import (
    QNO_DIMENSION,
    THRESHOLD_SNAPSHOT,
    TYPE_NAMES,
    AssessmentService,
)

router = APIRouter(tags=["C端-测评"])

# 测评题目版本（PRD §12.2 冻结口径版本号）
QUESTION_VERSION = "QB-1.0"

# 断点保留时长（90 天）
DRAFT_KEEP_DAYS = 90

# 幂等键结果保留时长（done 状态在此期间可回放）
IDEMPOTENT_TTL_HOURS = 24

# 测评入口开关键（config_type='switch'）
ENTRY_SWITCH_KEY = "switch.entry.assessment"

# 报告 13 区块固定顺序（前 9 免费，后 4 会员门控 block）
BLOCK_ORDER: List[str] = [
    "ai_label", "report_header", "wave_notice", "non_fatalism", "type_conclusion",
    "dimension_bands", "basic_advice", "disclaimer", "share_entry",
    "member_plan_detail", "member_communication", "member_scores", "member_history",
]

# 区块标题（服务端下发，前端不得硬编码文案）
BLOCK_TITLES: Dict[str, str] = {
    "ai_label": "AI 生成标识",
    "report_header": "报告概览",
    "wave_notice": "成长波动提示",
    "non_fatalism": "关于气质",
    "type_conclusion": "气质类型解读",
    "dimension_bands": "维度档位",
    "basic_advice": "通用养育建议",
    "disclaimer": "免责声明",
    "share_entry": "分享报告",
    "member_plan_detail": "个性化养育方案",
    "member_communication": "亲子沟通建议",
    "member_scores": "维度分数详情",
    "member_history": "历史测评对比",
}

# 区块访问层级映射（落库 report.access_tier_map，门控裁剪依据）
BLOCK_TIERS: Dict[str, str] = {
    key: ("free" if idx < 9 else "block") for idx, key in enumerate(BLOCK_ORDER)
}

# 非宿命论固定文案（PRD 冻结口径）
NON_FATALISM_TEXT = "气质没有好坏，不是宿命判定，只是行为倾向参考"

# 四类气质类型科普描述（禁「科学测评/信效度/心理测评」等表述）
TYPE_DESCRIPTIONS: Dict[str, str] = {
    "easy": "孩子的日常节奏比较平稳，对新事物的接受度较高，情绪起伏相对温和。"
            "这类倾向的孩子通常比较容易适应生活中的常规变化，按稳定的节奏陪伴即可。",
    "active": "孩子精力比较旺盛，动作幅度大，喜欢跑跳与探索，这是活动需求较高的表现。"
              "安排充足的运动与游戏时间，用「先动后静」的节奏安排一天，亲子相处会更轻松。",
    "sensitive": "孩子对环境变化、陌生人与新事物的反应比较强烈，情绪起伏明显，"
                 "这代表孩子的感受力很细腻。多给预告、多陪伴、多安抚，帮助孩子慢慢建立安全感。",
    "slow_warm": "孩子面对新环境与新事物时，需要较长的观察与缓冲时间，熟悉之后能逐渐放开。"
                 "家长可以放慢节奏，提前预告、允许观望，不催促、不比较。",
}

# 通用建议映射（演示数据：正式建议文案由运营配置下发）
BASIC_ADVICE: Dict[str, List[str]] = {
    "easy": [
        "保持规律的作息与陪伴节奏，及时回应孩子的需求",
        "鼓励孩子尝试新事物，对探索行为给予具体肯定",
    ],
    "active": [
        "每天安排充足的户外活动与运动游戏，释放孩子的活动需求",
        "用「先动后静」的顺序安排活动，如先跑跳再读绘本",
        "进入需要安静的场合前，提前预告规则",
    ],
    "sensitive": [
        "进入新环境前提前预告，给孩子留出观察与缓冲时间",
        "情绪来临时先共情、命名情绪，再引导孩子表达",
        "避免突然的环境切换与过于强烈的声音、光线刺激",
    ],
    "slow_warm": [
        "不催促、不贴标签，允许孩子先观察再参与",
        "用「提前踩点、逐步尝试」的方式接触新事物",
        "对孩子的每一点尝试给予具体的鼓励",
    ],
}

# 会员区块展示文案（会员可见；免费用户服务端裁剪不下发）
# D-11：移除「演示数据 / 占位内容」等面向用户的内部标注，改为可直接上线的权益说明。
MEMBER_DEMO_TEXTS: Dict[str, str] = {
    "member_plan_detail": "开通会员后，可查看按气质类型生成的个性化养育方案，含日常节奏与互动建议。",
    "member_communication": "开通会员后，可查看针对该气质类型的亲子沟通话术示例。",
    "member_scores": "开通会员后，可查看各维度精确分数、对比解读与成长追踪。",
    "member_history": "开通会员后，可查看历史测评对比与变化趋势。",
}


def _iso(value: Any) -> Optional[str]:
    """datetime 转 RFC3339 字符串。

    Args:
        value: datetime 实例或 None。

    Returns:
        ISO8601 字符串；入参为 None 时返回 None。
    """
    return value.isoformat() if value is not None else None


def is_member(user: AppUser) -> bool:
    """判定用户当前是否为有效会员。

    Args:
        user: 当前用户 ORM 实例。

    Returns:
        会员状态为 member 且未过期（或未设置到期时间）时为 True。
    """
    if user.member_status != "member":
        return False
    return user.member_expire_at is None or user.member_expire_at > utcnow()


def _check_entry_switch(db: Session) -> None:
    """校验测评入口运维开关（config_type='switch'）。

    Args:
        db: 数据库会话。

    Returns:
        None。

    Raises:
        ApiError: 开关 enabled=False 时抛 1406「该功能维护中」（HTTP 503）。
    """
    cfg = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.config_type == "switch",
            ConfigVersion.config_key == ENTRY_SWITCH_KEY,
            ConfigVersion.status == "active",
        )
        .order_by(ConfigVersion.version.desc())
        .first()
    )
    snapshot = (cfg.snapshot or {}) if cfg is not None else {}
    if snapshot.get("enabled") is False:
        # 入口紧急下线（PRD：系统开关，5 分钟内生效）
        raise ApiError(code=1406, message="该功能维护中", http_status=503)


def _get_owned_assessment(db: Session, user: AppUser, assessment_uid: str) -> Assessment:
    """按 uid 取当前用户的测评记录（防枚举：越权统一按不存在处理）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        assessment_uid: 测评对外标识。

    Returns:
        测评 ORM 实例。

    Raises:
        ApiError: 不存在或不属于当前用户时抛 1002。
    """
    assessment = (
        db.query(Assessment).filter(Assessment.assessment_uid == assessment_uid).first()
    )
    if assessment is None or assessment.user_id != user.id:
        raise_err(ERR_NOT_FOUND)
    return assessment


def _assessment_view(assessment: Assessment, resumed: bool) -> Dict[str, Any]:
    """构造测评断点视图（含已答明细，供前端续填）。

    Args:
        assessment: 测评 ORM 实例。
        resumed: 是否为断点续填。

    Returns:
        断点视图字典。
    """
    return {
        "assessment_uid": assessment.assessment_uid,
        "profile_id": assessment.profile_id,
        "question_version": assessment.question_version,
        "status": assessment.status,
        "has_draft": assessment.has_draft,
        "draft_expire_at": _iso(assessment.draft_expire_at),
        "answers": assessment.answers or [],
        "answered_count": assessment.answered_count,
        "skipped_count": assessment.skipped_count,
        "resumed": resumed,
    }


def _build_report_blocks(
    assessment: Assessment,
    score_result: Dict[str, Any],
    wave_notice: Dict[str, Any],
    report_uid: str,
) -> List[Dict[str, Any]]:
    """组装报告 13 区块（固定顺序；以列表存储，规避 jsonb 对象键乱序）。

    Args:
        assessment: 已写入计分结果的测评实例。
        score_result: AssessmentService.score() 的计分结果。
        wave_notice: 波动提示区块内容。
        report_uid: 报告标识（share_entry 链接使用）。

    Returns:
        13 个区块字典组成的列表（key/title/access_tier/summary?/content）。
    """
    type_code = score_result["type_code"]
    # dimension_bands：仅档位不渲染精确分数（partial 维标注「信息不足」）
    bands = []
    for dim, info in score_result["dimension_scores"].items():
        item: Dict[str, Any] = {
            "dimension": dim,
            "band": info.get("band"),
            "partial": bool(info.get("partial")),
        }
        if info.get("partial"):
            item["note"] = "信息不足"
        bands.append(item)

    blocks: List[Dict[str, Any]] = []

    def _add(key: str, content: Dict[str, Any], summary: Optional[str] = None) -> None:
        """追加一个区块（access_tier 取自固定映射）。

        Args:
            key: 区块标识。
            content: 区块内容。
            summary: 会员区块的免费占位摘要（可省略）。

        Returns:
            None。
        """
        blk: Dict[str, Any] = {
            "key": key,
            "title": BLOCK_TITLES[key],
            "access_tier": BLOCK_TIERS[key],
        }
        if summary is not None:
            blk["summary"] = summary
        blk["content"] = content
        blocks.append(blk)

    _add("ai_label", {"ai_generated_label": "AI_GEN_LABEL_V1"})
    _add("report_header", {
        "type_name": TYPE_NAMES.get(type_code, "未知类型"),
        "completed_at": _iso(assessment.submitted_at),
        "question_version": assessment.question_version,
        # 占位昵称：报告不落儿童昵称明文（CG13）
        "child_nickname": "宝宝A",
    })
    _add("wave_notice", wave_notice)
    _add("non_fatalism", {"text": NON_FATALISM_TEXT})
    _add("type_conclusion", {"type_code": type_code, "type_desc": TYPE_DESCRIPTIONS[type_code]})
    _add("dimension_bands", {"bands": bands, "note": "仅展示档位，不渲染精确分数"})
    _add("basic_advice", {
        "demo": False,
        "note": "以上建议按气质类型生成，供日常养育参考",
        "items": BASIC_ADVICE[type_code],
    })
    _add("disclaimer", {"disclaimer_id": "DISCLAIMER_V1"})
    _add("share_entry", {"share_url": f"/app/report/{report_uid}/image"})
    for key in ("member_plan_detail", "member_communication", "member_scores", "member_history"):
        _add(key, {"demo": True, "text": MEMBER_DEMO_TEXTS[key]}, summary="开通会员查看完整方案")
    return blocks


def build_report_payload(report: Report, user: AppUser) -> Dict[str, Any]:
    """报告装配 + 会员门控裁剪（供测评报告与历史报告详情共用）。

    裁剪规则：access_tier='block' 的区块，非会员响应中不含 content 字段
    （服务端裁剪），仅保留下发 summary 占位；会员可见全部内容。
    非会员（free 或会员已到期）报告只读。

    Args:
        report: 报告 ORM 实例。
        user: 当前用户。

    Returns:
        报告视图字典（含 blocks 列表与 readonly 标记）。
    """
    member = is_member(user)
    blocks: List[Dict[str, Any]] = []
    for blk in report.content or []:
        tier = blk.get("access_tier")
        item: Dict[str, Any] = {
            "key": blk.get("key"),
            "title": blk.get("title"),
            "access_tier": tier,
        }
        if "summary" in blk:
            item["summary"] = blk["summary"]
        if tier == "free" or member:
            item["content"] = blk.get("content")
        # 免费用户：block 级区块服务端裁剪，响应中不含 content 字段
        blocks.append(item)
    return {
        "report_uid": report.report_uid,
        "report_type": report.report_type,
        "question_version": report.question_version,
        "created_at": _iso(report.created_at),
        "is_member": member,
        "readonly": report.readonly or not member,
        "blocks": blocks,
    }


# ---------- 请求体模型 ----------


class AssessmentStartBody(BaseModel):
    """开始测评请求体。

    Attributes:
        profile_id: 关联档案（可选）——整型主键（向后兼容）或档案 UID 字符串
            （前端现状口径：传 profile 的 UUID 字符串）；二者类型自动识别。
        profile_uid: 档案对外 UID（可选）；与 profile_id 同时传入时 uid 优先。
    """

    profile_id: Optional[Union[int, str]] = Field(
        default=None,
        description="关联档案：整型主键（向后兼容）或档案 UID 字符串（可选）",
    )
    profile_uid: Optional[str] = Field(
        default=None, max_length=64, description="档案对外 UID（可选，uid 优先）"
    )


def _resolve_profile_id(db: Session, user: AppUser, body: AssessmentStartBody) -> Optional[int]:
    """解析开始测评请求中的档案主键。

    解析优先级：profile_uid > profile_id（字符串按 UID 解析，整型按主键直用）。
    UID 解析先查儿童档案（限本人且 active），再查宠物档案（限本人）；
    UID 不存在或不属于当前用户统一按资源不存在处理（防枚举，对齐问答
    会话创建的档案解析口径）。

    Args:
        db: 数据库会话。
        user: 当前用户。
        body: 开始测评请求体。

    Returns:
        解析出的档案主键 int；未传任何档案标识时返回 None。

    Raises:
        ApiError: UID 无法匹配当前用户的任何档案时抛 1002「资源不存在」（HTTP 404）。
    """
    uid = body.profile_uid
    raw = body.profile_id
    # 兼容前端现状：UUID 字符串放在 profile_id 字段传入 → 按 UID 解析
    if uid is None and isinstance(raw, str):
        uid = raw.strip() or None
    if uid is not None:
        child = (
            db.query(ChildProfile)
            .filter(
                ChildProfile.profile_uid == uid,
                ChildProfile.user_id == user.id,
                ChildProfile.status == "active",
            )
            .first()
        )
        if child is not None:
            return child.id
        pet = (
            db.query(PetProfile)
            .filter(PetProfile.pet_uid == uid, PetProfile.user_id == user.id)
            .first()
        )
        if pet is not None:
            return pet.id
        raise ApiError(*ERR_NOT_FOUND)
    # 整型主键直用（向后兼容既有调用方）
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None


class AnswerBody(BaseModel):
    """单题作答请求体。

    Attributes:
        q_no: 题号 1-16。
        raw_score: 李克特分值 1-5；null 表示跳题。
    """

    q_no: int = Field(ge=1, le=16, description="题号 1-16")
    raw_score: Optional[int] = Field(
        default=None, ge=1, le=5, description="李克特分值 1-5；null 表示跳题"
    )


class SubmitBody(BaseModel):
    """提交测评请求体。

    Attributes:
        client_request_id: 客户端幂等 ID（同 ID 重复提交返回首次结果）。
    """

    client_request_id: str = Field(min_length=1, max_length=64, description="客户端幂等 ID")


# ---------- 路由 ----------


@router.get("/assessment/questions", summary="下发测评题目", description="16 题列表，题干按 age_band 选择；入口开关校验")
def list_assessment_questions(
    age_band: str = Query(
        default="1-3y", description="0-6m/6-12m 用婴幼儿题干，其余用 1-6 岁题干"
    ),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """下发气质测评 16 题（题库存于 kb_entry assessment_pool）。

    Args:
        age_band: 月龄段；0-6m/6-12m 取 stem_0_12m，其余取 stem_1_6y。
        db: 数据库会话。
        user: 当前用户（需登录）。

    Returns:
        统一包络：question_version / age_band / demo_note / questions 列表
        （q_no、dimension、reverse、stem、options 5 项李克特）。

    Raises:
        ApiError: 1406 入口维护中；1002 题库未初始化。
    """
    _check_entry_switch(db)
    entries = (
        db.query(KbEntry)
        .filter(KbEntry.kb_kind == "assessment_pool", KbEntry.status == "published")
        .all()
    )
    if not entries:
        # 题库未种子化（需先执行 scripts/seed_data.py）
        raise_err(ERR_NOT_FOUND)
    questions: List[Dict[str, Any]] = []
    for entry in entries:
        try:
            data = json.loads(entry.content)
        except (TypeError, ValueError):
            # 脏数据条目跳过，不影响其余题目下发
            continue
        # 题干按月龄段选择（0-6m/6-12m 用婴幼儿题干，其余用 1-6 岁题干）
        stem = (
            data.get("stem_0_12m") if age_band in ("0-6m", "6-12m") else data.get("stem_1_6y")
        )
        options = [
            {"score": idx + 1, "label": label}
            for idx, label in enumerate(data.get("options", []))
        ]
        questions.append({
            "q_no": data.get("q_no"),
            "dimension": data.get("dimension"),
            "reverse": bool(data.get("reverse")),
            "stem": stem,
            "options": options,
        })
    questions.sort(key=lambda q: q["q_no"] or 0)
    return ok({
        "question_version": QUESTION_VERSION,
        "age_band": age_band,
        # 响应标注：题库为合成演示数据（真实题库未定稿，PRD Q-08）
        "demo_note": "题库为合成演示数据（真实题库未定稿），仅用于产品演示与联调",
        "questions": questions,
    })


@router.post("/assessment/start", summary="开始/续填测评", description="有未过期断点直接续填（含已答明细）")
def start_assessment(
    body: AssessmentStartBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """开始测评；已有未过期断点则直接续填（含已答 answers）。

    Args:
        body: 请求体（profile_id / profile_uid 可选，uid 优先）。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：测评断点视图（resumed=True 表示续填）。

    Raises:
        ApiError: 档案 UID 不存在或不属于当前用户时抛 1002（HTTP 404）。
    """
    now = utcnow()
    # 查找未过期断点（has_draft=True 且 draft_expire_at>now）
    draft = (
        db.query(Assessment)
        .filter(
            Assessment.user_id == user.id,
            Assessment.has_draft.is_(True),
            Assessment.status == "in_progress",
            Assessment.draft_expire_at > now,
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )
    if draft is not None:
        return ok(_assessment_view(draft, resumed=True))
    assessment = Assessment(
        user_id=user.id,
        profile_id=_resolve_profile_id(db, user, body),
        question_version=QUESTION_VERSION,
        answers=[],
        answered_count=0,
        skipped_count=0,
        has_draft=True,
        status="in_progress",
        draft_expire_at=now + timedelta(days=DRAFT_KEEP_DAYS),
    )
    db.add(assessment)
    db.flush()
    return ok(_assessment_view(assessment, resumed=False))


@router.put("/assessment/{assessment_uid}/answer", summary="单题作答", description="upsert 即存即返；raw_score=null 表示跳题")
def save_answer(
    assessment_uid: str,
    body: AnswerBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """单题作答 upsert（即存即返；断网本地暂存由前端负责）。

    Args:
        assessment_uid: 测评对外标识。
        body: {q_no, raw_score: 1-5 | null}，null 表示跳题。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：作答进度（answered_count / skipped_count / 断点到期时间）。

    Raises:
        ApiError: 1002 测评不存在或越权；1001 已提交不可再作答；
                  1002 断点已过期需重新开始。
    """
    assessment = _get_owned_assessment(db, user, assessment_uid)
    if assessment.status != "in_progress":
        raise ApiError(code=1001, message="该测评已提交，无法继续作答", http_status=409)
    now = utcnow()
    if assessment.draft_expire_at is None or assessment.draft_expire_at <= now:
        raise ApiError(code=1002, message="测评断点已过期，请重新开始测评", http_status=410)

    # upsert 该题作答明细（维度由冻结题号映射推导）
    entry = {
        "q_no": body.q_no,
        "dimension": QNO_DIMENSION[body.q_no],
        "raw_score": body.raw_score,
        "skipped": body.raw_score is None,
    }
    answers = list(assessment.answers or [])
    for idx, item in enumerate(answers):
        if item.get("q_no") == body.q_no:
            answers[idx] = entry
            break
    else:
        answers.append(entry)
    # 整体重赋值，确保 JSONB 变更可被 SQLAlchemy 追踪
    assessment.answers = answers
    assessment.answered_count = sum(1 for x in answers if x.get("raw_score") is not None)
    assessment.skipped_count = sum(1 for x in answers if x.get("raw_score") is None)
    return ok({
        "assessment_uid": assessment.assessment_uid,
        "q_no": body.q_no,
        "raw_score": body.raw_score,
        "answered_count": assessment.answered_count,
        "skipped_count": assessment.skipped_count,
        "draft_expire_at": _iso(assessment.draft_expire_at),
    })


@router.post("/assessment/{assessment_uid}/submit", summary="提交测评", description="幂等提交：计分→落库→生成 13 区块报告；不计问答额度")
def submit_assessment(
    assessment_uid: str,
    body: SubmitBody,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """幂等提交测评：计分 → 落库 → 生成 13 区块报告。

    流程：幂等检查（done 回放 / processing 拒绝 / 过期或失败可重试）→
    全局缺答 >3 拒绝（保留断点）→ 计分 → 更新测评 → 波动提示 → 创建报告 →
    幂等键置 done。测评不计问答额度（不调用额度服务）。

    Args:
        assessment_uid: 测评对外标识。
        body: {client_request_id}。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：{assessment_uid, report_uid, type_code, idempotent_replay}。

    Raises:
        ApiError: 1002 不存在或越权；1004 并发同键处理中；
                  1001 缺答过多（保留断点）/ 同键不同指纹 / 重复提交无报告。
    """
    assessment = _get_owned_assessment(db, user, assessment_uid)
    now = utcnow()
    # 指纹绑定「用户 + 测评」：同键不同对象直接拒绝
    fingerprint = sha256_hex(f"{user.id}|{assessment_uid}")

    # ---- 幂等检查 ----
    idem = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.scope == "assessment",
            IdempotencyKey.client_request_id == body.client_request_id,
        )
        .first()
    )
    if idem is not None:
        if idem.request_fingerprint != fingerprint:
            raise ApiError(code=1001, message="client_request_id 已被其他请求占用", http_status=409)
        if idem.expire_at is not None and idem.expire_at > now:
            if idem.status == "done":
                # 已成功提交：直接回放首次结果
                ref = idem.result_ref or {}
                return ok({
                    "assessment_uid": ref.get("assessment_uid", assessment_uid),
                    "report_uid": ref.get("report_uid"),
                    "type_code": ref.get("type_code"),
                    "idempotent_replay": True,
                })
            if idem.status == "processing":
                raise_err(ERR_IDEMPOTENT_PROCESSING)
            # failed 等状态：复用该行重试

    if assessment.status == "completed":
        # 换了 client_request_id 的重复提交：回放已有报告
        report = (
            db.query(Report)
            .filter(
                Report.assessment_id == assessment.id,
                Report.report_type == "assessment",
            )
            .order_by(Report.created_at.desc())
            .first()
        )
        if report is not None:
            return ok({
                "assessment_uid": assessment_uid,
                "report_uid": report.report_uid,
                "type_code": assessment.type_code,
                "idempotent_replay": True,
            })
        raise ApiError(code=1001, message="该测评已提交", http_status=409)

    # ---- 计分（PRD §12.2 冻结口径，纯函数不落库） ----
    result = AssessmentService.score(assessment.answers or [])
    if not result["eligible"]:
        # 全局缺答 >3：不出报告、保留断点（异常回滚，幂等键不落库）
        raise ApiError(code=1001, message="缺答题目过多，请补全后提交", http_status=422)

    # ---- 预占幂等键（并发同键在 flush 时暴露唯一约束冲突） ----
    if idem is None:
        idem = IdempotencyKey(
            scope="assessment",
            client_request_id=body.client_request_id,
            request_fingerprint=fingerprint,
            status="processing",
            expire_at=now + timedelta(hours=IDEMPOTENT_TTL_HOURS),
        )
        db.add(idem)
    else:
        idem.status = "processing"
        idem.expire_at = now + timedelta(hours=IDEMPOTENT_TTL_HOURS)
    try:
        db.flush()
    except IntegrityError:
        # 并发重复提交同一 client_request_id
        raise_err(ERR_IDEMPOTENT_PROCESSING)

    # ---- 波动提示：30 天内同用户有完成且 type_code 不同的测评 ----
    previous = (
        db.query(Assessment)
        .filter(
            Assessment.user_id == user.id,
            Assessment.id != assessment.id,
            Assessment.status == "completed",
            Assessment.submitted_at.isnot(None),
            Assessment.submitted_at >= now - timedelta(days=30),
            Assessment.type_code.isnot(None),
            Assessment.type_code != result["type_code"],
        )
        .order_by(Assessment.submitted_at.desc())
        .first()
    )
    wave_notice: Dict[str, Any] = {
        "triggered": previous is not None,
        "window_days": 30,
        "previous_type_code": previous.type_code if previous is not None else None,
    }

    # ---- 更新测评结果（断点消费） ----
    assessment.dimension_scores = result["dimension_scores"]
    assessment.type_code = result["type_code"]
    assessment.threshold_snapshot = dict(THRESHOLD_SNAPSHOT)
    assessment.status = "completed"
    assessment.submitted_at = now
    assessment.has_draft = False

    # ---- 创建 13 区块报告（测评不计问答额度） ----
    report_uid = gen_uuid()
    report = Report(
        report_uid=report_uid,
        user_id=user.id,
        report_type="assessment",
        assessment_id=assessment.id,
        question_version=assessment.question_version,
        content=_build_report_blocks(assessment, result, wave_notice, report_uid),
        access_tier_map=dict(BLOCK_TIERS),
        readonly=False,
    )
    db.add(report)

    # ---- 幂等键置 done（回放期内重复提交返回 report_uid） ----
    idem.status = "done"
    idem.result_ref = {
        "assessment_uid": assessment.assessment_uid,
        "report_uid": report_uid,
        "type_code": result["type_code"],
    }
    idem.expire_at = now + timedelta(hours=IDEMPOTENT_TTL_HOURS)

    # 显式提交（P1 竞态修复）：get_db 的依赖 teardown commit 发生在响应发送之后，
    # 客户端拿到 report_uid 立即查询详情会命中"数据尚未持久化"的竞态窗口
    # （e2e 实测复现：submit 返回后紧跟 GET /history/report/{uid} 返回 1002）。
    db.commit()

    return ok({
        "assessment_uid": assessment.assessment_uid,
        "report_uid": report_uid,
        "type_code": result["type_code"],
        "idempotent_replay": False,
    })


@router.get("/assessment/{assessment_uid}/report", summary="查询测评报告", description="统一报告装配 + 会员门控裁剪 content")
def get_assessment_report(
    assessment_uid: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> dict:
    """查询测评报告（走统一报告装配 + 会员门控裁剪）。

    Args:
        assessment_uid: 测评对外标识。
        db: 数据库会话。
        user: 当前用户。

    Returns:
        统一包络：报告视图（blocks 已按会员状态裁剪 content）。

    Raises:
        ApiError: 1002 测评不存在 / 越权 / 报告未生成（尚未提交完成）。
    """
    assessment = _get_owned_assessment(db, user, assessment_uid)
    report = (
        db.query(Report)
        .filter(
            Report.assessment_id == assessment.id,
            Report.report_type == "assessment",
        )
        .order_by(Report.created_at.desc())
        .first()
    )
    if report is None:
        # 尚未提交完成，报告未生成
        raise_err(ERR_NOT_FOUND)
    return ok(build_report_payload(report, user))

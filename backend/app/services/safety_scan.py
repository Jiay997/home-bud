# -*- coding: utf-8 -*-
"""内容安全送检服务（平台能力抽象的本地实现）。

状态机：submit(reviewing) → resolve(pass/reject/manual)。
- 超配额拒绝放行：每日送检配额 DAILY_QUOTA=1000（可被环境变量 CONTENT_SCAN_QUOTA
  覆盖），计数键 cache "scan:quota:{date}"，超限抛 ApiError(1303)。
- 副本最小化：送检正文不落库，submit 时仅在 callback_log 登记 SHA-256 摘要；
  回调裁决后 raw_deleted=True（副本删除语义）。
- 真实平台接入点：SafetyScanService._call_platform_api()（留位，当前由
  _local_rule_verdict 本地规则裁决）。
- 举报上报抽象位：report_to_authority()（凭据未配置时仅记日志不报错，
  供后台 escalate 处置调用）。
"""
import hashlib
import hmac
import logging
import os
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..core.cache import cache
from ..core.crypto import sha256_hex
from ..core.errors import ApiError
from ..models import ContentAuditRecord, Feedback

# 服务专用日志器
logger = logging.getLogger("jiaban.safety")

# 送检副本删除标记与本地规则词表
ACTION_BY_VERDICT = {"pass": "allow", "reject": "block", "manual": "manual_review"}

# 裁决 → 反馈审核状态映射（单点定义：反馈提交与平台回调共用）
VERDICT_TO_AUDIT_STATUS = {"pass": "passed", "reject": "rejected", "manual": "manual"}

# 回调时间戳有效窗口（秒）：超出即拒绝，防重放
CALLBACK_TS_WINDOW_SECONDS = 300

# 本地规则高危词（真实平台接入后由平台词库替代）
HIGH_RISK_WORDS: list = [
    "爆炸物", "制毒", "枪支买卖", "毒品交易", "儿童色情",
    "自杀方法", "自残教程", "虐待儿童",
]

# 本地规则显式放行标记（联调/冒烟用）
PASS_MARKER = "审核通过测试"


class SafetyScanService:
    """内容安全送检服务（平台能力抽象的本地实现）。

    状态机：submit(reviewing) → resolve(pass/reject/manual)。
    超配额拒绝放行；副本回调后删除（raw_deleted）。
    真实平台接入点：_call_platform_api()（留位，当前本地规则裁决）。

    Attributes:
        DAILY_QUOTA: 每日送检配额（可被环境变量 CONTENT_SCAN_QUOTA 覆盖）。
    """

    DAILY_QUOTA = 1000

    @staticmethod
    def _quota_key(now: Optional[datetime] = None) -> str:
        """构造当日配额计数键。

        Args:
            now: 参考时间；缺省取当前 UTC 时间。

        Returns:
            形如 "scan:quota:2026-10-08" 的计数键。
        """
        ref = now or datetime.now(timezone.utc)
        return f"scan:quota:{ref.date().isoformat()}"

    @staticmethod
    def _daily_quota() -> int:
        """读取当日有效配额（环境变量 CONTENT_SCAN_QUOTA 覆盖类属性默认值）。

        Returns:
            每日配额整数；环境变量非法或缺省时回退 DAILY_QUOTA。
        """
        raw = os.environ.get("CONTENT_SCAN_QUOTA", "").strip()
        try:
            return int(raw) if raw else SafetyScanService.DAILY_QUOTA
        except ValueError:
            return SafetyScanService.DAILY_QUOTA

    @staticmethod
    def check_quota(db) -> None:
        """检查当日送检配额，超限拒绝放行。

        计数键 cache "scan:quota:{date}"：已用次数 ≥ 配额即拒绝。

        Args:
            db: 数据库会话（预留：真实平台接入后用于核对平台侧配额）。

        Returns:
            None。

        Raises:
            ApiError: 1303 当日送检配额已用尽（http 429）。
        """
        used = cache.get_int(SafetyScanService._quota_key())
        quota = SafetyScanService._daily_quota()
        if used >= quota:
            logger.warning("safety scan quota exhausted: %d/%d", used, quota)
            raise ApiError(
                code=1303,
                message="今日内容安全送检配额已用尽",
                http_status=429,
                details={"used": used, "quota": quota},
            )

    @staticmethod
    def submit(
        db, object_type: str, object_id: str, scene: str, content: str
    ) -> ContentAuditRecord:
        """提交送检：写 ContentAuditRecord(audit_result='reviewing') 并占用配额。

        正文不落库：仅在 callback_log 登记 SHA-256 摘要（副本最小化），
        明文随送检请求发出后即丢弃。

        Args:
            db: 数据库会话。
            object_type: 被检对象类型（如 text）。
            object_id: 被检对象标识（如反馈编号）。
            scene: 送检场景（如 feedback）。
            content: 送检明文。

        Returns:
            新建的 ContentAuditRecord（id 已随 flush 分配）。

        Raises:
            ApiError: 1303 当日送检配额超限。
        """
        # 先查配额再占坑：超限直接拒绝，不产生记录
        SafetyScanService.check_quota(db)
        record = ContentAuditRecord(
            object_type=object_type,
            object_id=object_id,
            scene=scene,
            audit_result="reviewing",
            callback_log={"content_sha256": sha256_hex(content)},
        )
        db.add(record)
        db.flush()
        # 占用当日配额（键按天过期，TTL 24h）
        cache.incr(SafetyScanService._quota_key(), ttl_seconds=86400)
        logger.info(
            "safety scan submitted: type=%s id=%s scene=%s", object_type, object_id, scene
        )
        return record

    @staticmethod
    def resolve(
        db, record_id: int, verdict: str, note: str = ""
    ) -> ContentAuditRecord:
        """回调裁决：置 audit_result/action 并删除送检副本（raw_deleted=True）。

        状态机约束：仅 reviewing 记录可裁决；非 reviewing 的重复回调按幂等
        处理（直接返回现状，不覆盖既有结论）。

        Args:
            db: 数据库会话。
            record_id: 送检记录主键。
            verdict: 裁决结果，pass / reject / manual。
            note: 裁决备注（存入 callback_log）。

        Returns:
            裁决后的 ContentAuditRecord。

        Raises:
            ApiError: 1002 记录不存在；1001 verdict 非法。
        """
        record = db.get(ContentAuditRecord, record_id)
        if record is None:
            raise ApiError(code=1002, message="送检记录不存在", http_status=404)
        if verdict not in ACTION_BY_VERDICT:
            raise ApiError(code=1001, message="verdict 必须为 pass/reject/manual", http_status=422)
        if record.audit_result != "reviewing":
            # 幂等：重复回调不覆盖既有裁决
            logger.info("safety scan resolve idempotent: id=%s already %s", record_id, record.audit_result)
            return record
        record.audit_result = verdict
        record.action = ACTION_BY_VERDICT[verdict]
        # 副本删除：正文从未落库，摘要保留于 callback_log
        record.raw_deleted = True
        log = dict(record.callback_log or {})
        log.update(
            {
                "verdict": verdict,
                "note": note,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        record.callback_log = log
        db.flush()
        logger.info("safety scan resolved: id=%s verdict=%s", record_id, verdict)
        return record

    @staticmethod
    def _call_platform_api(content: str) -> Optional[str]:
        """真实内容安全平台送检调用点（留位）。

        当前返回 None 表示平台未接入，由 _local_rule_verdict 本地规则兜底；
        接入真实平台后在此同步调用并返回平台裁决（pass/reject/manual）。

        Args:
            content: 送检明文。

        Returns:
            平台裁决字符串；未接入时返回 None。
        """
        return None

    @staticmethod
    def _local_rule_verdict(content: str) -> str:
        """本地规则裁决（真实平台留位）。

        规则：含高危词 → reject（安全优先，即使同时含放行标记）；
        含"审核通过测试"等显式标记 → pass；默认 pass
        （接入真实平台后默认改为 manual，交人工复核）。

        Args:
            content: 送检明文。

        Returns:
            "reject" 或 "pass"。
        """
        lowered = (content or "").lower()
        # 高危词优先：安全结论不可被放行标记覆盖
        for word in HIGH_RISK_WORDS:
            if word in lowered:
                return "reject"
        if PASS_MARKER in lowered:
            return "pass"
        return "pass"


def callback_signature(secret: str, record_id: int, verdict: str, timestamp: int) -> str:
    """计算平台回调签名（HMAC-SHA256 十六进制）。

    签名字串口径："{record_id}:{verdict}:{timestamp}"，供平台侧
    与本地验签共用（单点定义，避免两端实现漂移）。

    Args:
        secret: 回调共享密钥（SAFETY_SCAN_CALLBACK_SECRET）。
        record_id: 送检记录主键。
        verdict: 裁决结果 pass/reject/manual。
        timestamp: Unix 秒级时间戳。

    Returns:
        64 位十六进制 HMAC 摘要。
    """
    message = f"{record_id}:{verdict}:{timestamp}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def apply_platform_callback(
    db, record_id: int, verdict: str, note: str = ""
) -> ContentAuditRecord:
    """平台回调落库：裁决送检记录并同步被检业务对象状态（异步闭环收口）。

    - 记录侧：复用 resolve（仅 reviewing 可裁决，重复回调幂等）；
    - 业务侧：object_type='text' 且存在同号反馈时，同步
      feedback.audit_status（pass→passed / reject→rejected / manual→manual）。

    Args:
        db: 数据库会话。
        record_id: 送检记录主键。
        verdict: 平台裁决 pass/reject/manual。
        note: 平台备注（存入 callback_log，可空）。

    Returns:
        裁决后的 ContentAuditRecord。

    Raises:
        ApiError: 1002 记录不存在；1001 verdict 非法。
    """
    record = SafetyScanService.resolve(db, record_id, verdict=verdict, note=note)
    # 业务侧回写：反馈场景同步审核状态（其余对象类型由各自域后续扩展）
    if record.object_type == "text":
        feedback = (
            db.query(Feedback).filter(Feedback.feedback_no == record.object_id).first()
        )
        if feedback is not None:
            feedback.audit_status = VERDICT_TO_AUDIT_STATUS.get(verdict, verdict)
            db.flush()
            logger.info(
                "platform callback synced feedback: no=%s audit_status=%s",
                record.object_id,
                feedback.audit_status,
            )
    return record


def report_to_authority(db, report_no: str, target: str) -> dict:
    """举报向监管平台上报（凭据未配置时的占位实现，不抛错）。

    供后台 escalate 处置调用；真实平台接入后在此读取凭据并回写
    content_report.reported 状态。

    Args:
        db: 数据库会话（真实平台接入后用于回写上报状态）。
        report_no: 举报编号（content_report.report_no）。
        target: 上报目标平台标识。

    Returns:
        {reported: bool, reason: str}——未配置凭据时恒为
        {reported: False, reason: "credentials_not_configured"}。
    """
    logger.info("authority report placeholder: report_no=%s target=%s", report_no, target)
    return {"reported": False, "reason": "credentials_not_configured"}
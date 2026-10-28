# -*- coding: utf-8 -*-
"""ORM 模型汇总导出。

init_db.py 通过本模块的 metadata 建表；业务代码统一从此导入模型。
"""
from .base import Base, VersionMixin, OrgIdMixin, gen_uuid, utcnow
from .user import AppUser, ConsentRecord, TextVersion, CurrentContext
from .profile import ChildProfile, PetProfile, ProfilePhoto
from .health import HealthRecord
from .note import Note
from .qa import QaSession, QaAnswerSection, AgentCallLog, CrisisChannel, RiskAppeal
from .assessment import Assessment, Report
from .billing import Product, Order, Subscription, RefundRequest, QuotaUsage
from .kb import KbEntry, KbReview, LexiconTerm, RiskRuleConfig
from .compliance import (
    RiskEvent,
    RightsRequest,
    ContentReport,
    ContentTraceTask,
    SamplingCheck,
    ContentAuditRecord,
    Feedback,
)
from .admin import ConfigVersion, IdempotencyKey, AdminUser, AdminAuditLog, JobRunLog
from .v31 import (
    ChannelReviewRecord,
    Collaborator,
    NotificationPref,
    PhotoAsset,
    ReferralLog,
    ReminderTask,
    RenderRecord,
    ToolItem,
    ToolRunRecord,
    TopicPack,
    TriageRule,
)

# 全部 48 张表模型清单（供 init_db 校验数量）
# 37 张 V3.0 基线表 + 11 张 V3.1 增量表（PRD V3.1 §6.1）
ALL_MODELS = [
    AppUser, ConsentRecord, TextVersion, CurrentContext,
    ChildProfile, PetProfile, ProfilePhoto,
    HealthRecord,
    Note,
    QaSession, QaAnswerSection, AgentCallLog, CrisisChannel, RiskAppeal,
    Assessment, Report,
    Product, Order, Subscription, RefundRequest, QuotaUsage,
    KbEntry, KbReview, LexiconTerm, RiskRuleConfig,
    RiskEvent, RightsRequest, ContentReport, ContentTraceTask,
    SamplingCheck, ContentAuditRecord, Feedback,
    ConfigVersion, IdempotencyKey, AdminUser, AdminAuditLog, JobRunLog,
    # V3.1 增量（RQ-03/RQ-05/RQ-06/RQ-08/RQ-09/RQ-10/RQ-12/RQ-13/RQ-14）
    ChannelReviewRecord, ReminderTask, NotificationPref, Collaborator,
    RenderRecord, ReferralLog, TriageRule, TopicPack, ToolItem, ToolRunRecord,
    PhotoAsset,
]

__all__ = [
    "Base", "VersionMixin", "OrgIdMixin", "gen_uuid", "utcnow",
    "AppUser", "ConsentRecord", "TextVersion", "CurrentContext",
    "ChildProfile", "PetProfile", "ProfilePhoto",
    "HealthRecord",
    "Note",
    "QaSession", "QaAnswerSection", "AgentCallLog", "CrisisChannel", "RiskAppeal",
    "Assessment", "Report",
    "Product", "Order", "Subscription", "RefundRequest", "QuotaUsage",
    "KbEntry", "KbReview", "LexiconTerm", "RiskRuleConfig",
    "RiskEvent", "RightsRequest", "ContentReport", "ContentTraceTask",
    "SamplingCheck", "ContentAuditRecord", "Feedback",
    "ConfigVersion", "IdempotencyKey", "AdminUser", "AdminAuditLog", "JobRunLog",
    "ChannelReviewRecord", "ReminderTask", "NotificationPref", "Collaborator",
    "RenderRecord", "ReferralLog", "TriageRule", "TopicPack", "ToolItem",
    "ToolRunRecord", "PhotoAsset",
    "ALL_MODELS",
]

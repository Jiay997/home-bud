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

# 全部 37 张表模型清单（供 init_db 校验数量）
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
    "ALL_MODELS",
]

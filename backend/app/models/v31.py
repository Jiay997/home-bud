# -*- coding: utf-8 -*-
"""V3.1 增量实体表模型（PRD V3.1 §6.1 新增 9 项实体 / 预留结构）。

对应关系（PRD §6.1 增补表）：

============================  ==================================================
PRD 实体                       本模块模型
============================  ==================================================
渠道核验记录                    ChannelReviewRecord
提醒任务                        ReminderTask
订阅偏好                        NotificationPref
协作者（V1.0 建表，不开放功能）  Collaborator
分享渲染记录（预留）             RenderRecord
LBS 转介记录（预留）             ReferralLog
分级规则条目                    TriageRule
专题包（RQ-13 / RQ-14）         TopicPack
轻工具（RQ-12）                 ToolItem
图片问答元数据（RQ-05）          PhotoAsset
============================  ==================================================

数据约束（PRD V3.1 §6.2）逐条落地位置：

- DR-26 渠道号码仅存 `crisis_channel.phone_number`（唯一存放点）；
- DR-27 图片原图 24h 内删除：`photo_asset.expires_at` + `deleted_at` + `delete_log`；
- DR-28 图片/位置原始数据禁止进埋点：`photo_asset` 不存原图字节与 URL，
  `referral_log` 仅存市 / 区级字段（无经纬度列）；
- DR-29 分级规则带 `version` 与专家审核记录：`triage_rule.expert_signoff` /
  `expert_reviewed_at`；
- DR-30 触达任务带频控快照：`reminder_task.frequency_cap_snapshot`；
- DR-31 协作者授权关联独立同意记录 + 移除审计：`collaborator.consent_record_id`。
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, VersionMixin, gen_uuid


class ChannelReviewRecord(Base):
    """渠道核验记录表：每次人工拨测 / 合规核验留痕（留存 ≥3 年）。

    AC-RQ03-5：核验人、方式、时间、结论、version 全量留痕，监管检查可举证。

    Attributes:
        review_no: 核验单号（对外唯一）。
        channel_code: 关联渠道业务编码（不建外键，渠道删除后记录仍留档）。
        review_method: 核验方式（call_dial 电话拨测 / official_site 官网核对 /
            verbal 口头确认 / document 文件核对）。
        review_result: 结论（reachable 可接通 / unreachable 不可接通 /
            changed 信息已变更 / pending 待复测）。
        reviewer: 核验人（后台账号名或姓名，脱敏前）。
        channel_version: 核验时渠道条目版本（DR-29 同口径可还原）。
    """

    __tablename__ = "channel_review_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=lambda: f"CRV{gen_uuid()[:12]}"
    )
    channel_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    review_method: Mapped[str] = mapped_column(String(24), nullable=False)
    review_result: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_channel_review_code_time", "channel_code", "reviewed_at"),
        {"comment": "渠道核验记录：合规留档 ≥3 年（AC-RQ03-5）"},
    )


class ReminderTask(Base):
    """提醒任务表（PRD §3.8.3）：里程碑提醒 / 成长周报 / 每周一问。

    Attributes:
        task_uid: 对外任务标识（归因 `reminder_trace_id` 载体）。
        task_type: vaccine / checkup / deworm / report / weekly_q。
        planned_at: 计划发送时间（节点前 3 天）。
        status: pending / sent / opened / skipped / canceled。
        frequency_cap_snapshot: 频控上限快照（DR-30，可审计）。
        dedupe_key: 幂等键（user + 类型 + 计划日期），防重复生成。
    """

    __tablename__ = "reminder_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    profile_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    profile_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    task_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    planned_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: f"rmd_{gen_uuid()[:16]}"
    )
    frequency_cap_snapshot: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    send_fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_reminder_user_status", "user_id", "status", "planned_at"),
        Index("idx_reminder_due", "status", "planned_at"),
        {"comment": "提醒任务：已发送留存 ≥1 年（PRD §6.1）"},
    )


class NotificationPref(Base, VersionMixin):
    """订阅偏好表（PRD §3.8.3）：逐类型开关 + 频控上限快照。

    Attributes:
        pref_type: vaccine / checkup / deworm / report / weekly_q / all。
        enabled: 是否开启（关闭即时生效且不再发送，AC-RQ08-7）。
        frequency_cap_snapshot: 设置时的频控上限快照（周 ≤2 条）。
    """

    __tablename__ = "notification_pref"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pref_type: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frequency_cap_snapshot: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "pref_type", name="uk_notification_pref"),
        {"comment": "订阅偏好：账号存续期（AC-RQ08-9）"},
    )


class Collaborator(Base, VersionMixin):
    """协作者表（V1.0 建表、不开放功能；RQ-10 法律形态 Q-53 未定前不开发）。

    AC-RQ10-6 / DR-31：每条授权必须关联独立同意记录，移除须写审计。

    Attributes:
        collaborator_uid: 对外标识。
        owner_user_id: 档案创建者（监护人）用户主键。
        role: viewer（只读 + 提问）/ editor（可编辑非敏感字段）。
        consent_record_id: 协作者本人独立同意记录（不与创建者共用）。
        status: invited / active / removed / expired。
    """

    __tablename__ = "collaborator"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collaborator_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    collaborator_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    profile_type: Mapped[str] = mapped_column(String(8), nullable=False, default="child")
    profile_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role: Mapped[str] = mapped_column(String(8), nullable=False, default="viewer")
    consent_record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    invited_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="invited", server_default="invited"
    )
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_collab_owner", "owner_user_id", "status"),
        {"comment": "协作者（预留）：V1.0 仅建表不开放功能（AC-RQ10-6）"},
    )


class RenderRecord(Base):
    """分享渲染记录表（AC-RQ01-2/3、AC-RQ09-1/5）：长图标识校验留痕。

    Attributes:
        render_id: 渲染唯一标识（同一 `session_id + version` 幂等复用）。
        object_type: report（测评长图）/ qa（问答长图）。
        share_trace_id: 分享归因标识（AC-RQ09-4）。
        label_check: 标识校验结果 {ratio, count, passed, chunks[], errors[]}。
    """

    __tablename__ = "render_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    render_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: f"rnd_{gen_uuid()}"
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    share_trace_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: f"shr_{gen_uuid()[:16]}"
    )
    protocol_version: Mapped[str] = mapped_column(String(8), nullable=False, default="V2")
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="image/png")
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_check: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_render_object", "object_type", "object_id"),
        Index("idx_render_user_time", "user_id", "generated_at"),
        {"comment": "分享渲染记录（预留）：随报告留存期"},
    )


class ReferralLog(Base):
    """LBS 转介记录表（RQ-04 预留；V1.0 建表不写业务）。

    合规红线（AC-RQ04-4 / DR-28）：**精确坐标不落库、不进埋点**，
    仅保留市 / 区级统计字段与点击结果枚举。

    Attributes:
        scene: 触发场景（emergency_block / triage_red / pet_redflag）。
        region_city / region_district: 城市 / 区级（无经纬度列）。
        poi_count: 本次返回机构条数。
        clicked: 是否点击机构条目。
        data_source: POI 数据来源标注（AC-RQ04-5）。
    """

    __tablename__ = "referral_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    referral_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: f"rfl_{gen_uuid()[:16]}"
    )
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scene: Mapped[str] = mapped_column(String(24), nullable=False)
    region_city: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region_district: Mapped[str | None] = mapped_column(String(32), nullable=True)
    poi_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_referral_scene_time", "scene", "created_at"),
        {"comment": "LBS 转介记录（预留）：仅城市/区级，≥6 个月"},
    )


class TriageRule(Base, VersionMixin):
    """分级规则条目表（RQ-06 AC-RQ06-6 / DR-29）：条目化、可配置、可专家审核。

    Attributes:
        rule_id: 业务规则编码（对外唯一，命中摘要回显该编码）。
        scene: fever / vomit / trauma / ingestion / pet_acute（首批 5 类模板）。
        domain: child / pet。
        age_min_months / age_max_months: 月龄区间（宠物按换算月龄）。
        conditions: 判定条件 {keywords[], any_keywords[], temp_min,
            temp_max, duration_hours_min, mental_state}。
        level: red / yellow / green（档位）。
        priority: 命中优先级（数值越大越优先，红色档位通常配高优先级）。
        observations / escalation_flags / contraindications / disclaimers:
            档位随附的四类结构化文案（前端按契约渲染）。
        expert_signoff / expert_reviewed_at: 专家书面确认留痕（§7.2 门禁）。
        status: active / inactive / draft。
    """

    __tablename__ = "triage_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scene: Mapped[str] = mapped_column(String(24), nullable=False)
    domain: Mapped[str] = mapped_column(String(8), nullable=False, default="child")
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    age_min_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    age_max_months: Mapped[int] = mapped_column(Integer, nullable=False, default=9999)
    conditions: Mapped[object] = mapped_column(JSONB, nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    escalation_flags: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    contraindications: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    disclaimers: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    expert_signoff: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expert_reviewed_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_triage_scene_status", "scene", "status", "priority"),
        {"comment": "分级规则：长期留存含历史版本（DR-29）"},
    )


class TopicPack(Base, VersionMixin):
    """专题包表（RQ-13 交叉主题包 / RQ-14 宠物行为内容线）。

    Attributes:
        topic_code: 专题编码（对外唯一，购买权益凭此解锁）。
        domain: cross（育儿×宠物）/ behavior（宠物行为）/ child / pet。
        redflag_first: 红旗是否前置（AC-RQ13-2 / AC-RQ14-1 硬约束）。
        review_child_signoff / review_pet_signoff: 专家双审留痕
            （交叉内容必须双签，AC-RQ13-1）。
        price_micro: 独立计费价格（会员不含专题，口径不变）。
    """

    __tablename__ = "topic_pack"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_micro: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    product_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    redflag_first: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_blocks: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    redflag_blocks: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    review_child_signoff: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_pet_signoff: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )

    __table_args__ = (
        Index("idx_topic_domain_status", "domain", "status"),
        {"comment": "专题包：独立计费、会员不含（F9.8 口径）"},
    )


class ToolItem(Base, VersionMixin):
    """轻工具条目表（RQ-12）：结构化内容 + 简单交互，不走多 Agent 调度。

    Attributes:
        tool_code: 工具编码（对外唯一）。
        tool_type: checklist（自查清单）/ parser（配料表解析）。
        kb_refs: 内容来源知识条目编码清单（AC-RQ12-1 可追溯）。
        content: 工具内容块（步骤 / 选项 / 参考说明）。
    """

    __tablename__ = "tool_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tool_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(16), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False, default="child")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    kb_refs: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    content: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="on", server_default="on"
    )

    __table_args__ = (
        Index("idx_tool_status_sort", "status", "sort_order"),
        {"comment": "轻工具：内容来自 F12 知识资产，100% 审核后上架"},
    )


class PhotoAsset(Base):
    """图片问答元数据表（RQ-05 / AC-RQ05-3/4 / DR-27）。

    **只存元数据，不存原图字节、不存 URL、不进埋点**；原图按 `file_path`
    落临时盘并在 24 h 内删除，`deleted_at` + `delete_log` 构成删除执行日志。

    Attributes:
        photo_uid: 对外图片标识（前端仅回传该标识）。
        scene: rash / stool / vomit / food_label / medicine_pack / unknown。
        moderation_result: pass / reject / quota_exceeded / error。
        file_path: 临时盘相对路径（删除后置 NULL）。
        expires_at: 24 h 删除到期时间。
        delete_log: 删除执行日志 {deleted_at, by, bytes, result}。
    """

    __tablename__ = "photo_asset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    photo_uid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=gen_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    scene: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unknown", server_default="unknown"
    )
    moderation_result: Mapped[str] = mapped_column(String(16), nullable=False, default="pass")
    moderation_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delete_log: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_photo_expire", "deleted_at", "expires_at"),
        {"comment": "图片问答元数据：原图 24h 删除，仅留元数据 ≥6 个月"},
    )


class ToolRunRecord(Base):
    """轻工具使用记录表：`tool_view` / `tool_complete` 归因与转化观测。

    Attributes:
        tool_code: 工具编码。
        action: view / complete / to_qa / to_topic。
        completed_items: 完成项数（自查清单勾选数）。
    """

    __tablename__ = "tool_run_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tool_code: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="view")
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_tool_run_code_time", "tool_code", "created_at"),
        {"comment": "轻工具使用记录：转化归因"},
    )

# -*- coding: utf-8 -*-
"""OpenAPI → docs/API.md 接口文档导出脚本（Task 4.1）。

功能：
- 读取 OpenAPI 规范（优先运行中服务 http://127.0.0.1:8000/openapi.json，
  失败则本地导入 app.main.app 生成），按 tags 分组生成中文接口文档
  d:/HomeBud/docs/API.md；
- 每个端点包含：方法+路径、tag、summary/description、鉴权要求
  （需登录 / 需后台角色 / 公开）、路径参数 / 查询参数 / 请求体要点、
  响应要点（data 结构概述）、主要错误码（依代码审查口径标注）；
- 本脚本可重复执行（幂等覆盖生成），生成时间写入文档头部。

使用方式（在 backend 目录下）：
    python scripts/export_api_doc.py

鉴权与错误码口径来源：backend/app/api/v1/*.py 路由代码审查结论
（get_current_user / get_admin / require_admin_perm / require_confirm 依赖链），
不确定端点特有错误码时统一归入文档末尾「通用错误码」小节。
"""
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 项目根目录与输出路径（脚本位于 backend/scripts，docs 位于仓库根 docs）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC_PATH = os.path.join(ROOT_DIR, "docs", "API.md")
OPENAPI_URL = "http://127.0.0.1:8000/openapi.json"

# OpenAPI 正式 tags（与 app/main.py OPENAPI_TAGS 对应，共 12 组）
FORMAL_TAGS = [
    "系统", "C端-认证同意", "C端-档案", "C端-问答", "C端-测评", "C端-商业化",
    "C端-权利反馈", "C端-健康与笔记",
    "后台-知识库", "后台-词库", "后台-处置", "后台-配置",
]
# history_api 4 个端点使用独立 history tag（未入正式 tags），作为补充分组保留
EXTRA_TAGS = ["history"]
GROUP_ORDER = FORMAL_TAGS + EXTRA_TAGS

HTTP_METHODS = ("get", "post", "put", "delete", "patch")

# ---------------------------------------------------------------------------
# 鉴权标注（基于代码审查：core/deps.py 依赖链 + 各路由显式权限校验）
# ---------------------------------------------------------------------------
# 特例标注表：(method, path) -> 鉴权说明；未命中的端点按 _default_auth 规则判断
AUTH_OVERRIDES: Dict[Tuple[str, str], str] = {
    ("GET", "/api/v1/health"): "公开",
    ("GET", "/api/v1/texts"): "公开（协议文案需在登录/同意前展示）",
    ("GET", "/api/v1/metrics"): "公开（进程内指标快照，运维探查）",
    ("POST", "/api/v1/safety-scan/callback"): "公开（机器对机器：HMAC-SHA256 验签 + 时间窗防重放，无会话）",
    ("POST", "/api/v1/auth/dev-login"): "公开",
    ("POST", "/api/v1/auth/wx-login"): "公开（通道由 settings.auth_provider 控制）",
    ("POST", "/api/v1/auth/refresh"): "公开（校验 user_refresh 类型 JWT）",
    ("POST", "/api/v1/admin/login"): "公开（账密 + 失败锁定）",
    ("POST", "/api/v1/admin/mfa/verify"): "公开（MFA 票据校验）",
    ("GET", "/api/v1/admin/me"): "需后台角色（get_admin 登录态）",
    ("GET", "/api/v1/admin/metrics/alert-history"): "需后台角色（get_admin 登录态，无额外权限矩阵）",
    ("GET", "/api/v1/admin/products"): "需后台角色（get_admin 登录态，价格配置卡数据源）",
    ("GET", "/api/v1/admin/audit-logs"): "需后台角色（仅超管 super_admin）",
    ("GET", "/api/v1/admin/configs"): "需后台角色（仅超管 super_admin）",
    ("GET", "/api/v1/admin/configs/{config_key}/history"): "需后台角色（仅超管 super_admin）",
}

# 后台端点权限矩阵标注：(method, path) -> 权限说明后缀（叠加在「需后台角色」之后）
ADMIN_PERM_OVERRIDES: Dict[Tuple[str, str], str] = {
    ("PUT", "/api/v1/admin/refunds/{request_no}"): "rights:handle",
    ("GET", "/api/v1/admin/agent-logs"): "log:view",
    ("GET", "/api/v1/admin/agent-logs/export"): "log:view + 仅超管 + 二次确认",
    ("GET", "/api/v1/admin/agent-logs/{log_id}"): "log:view",
    ("GET", "/api/v1/admin/feedback"): "fb:view",
    ("PUT", "/api/v1/admin/feedback/{feedback_id}"): "fb:handle",
    ("GET", "/api/v1/admin/reports"): "fb:view",
    ("PUT", "/api/v1/admin/reports/{report_no}"): "fb:handle（escalate 须附证据）",
    ("GET", "/api/v1/admin/risk-events"): "risk:view",
    ("GET", "/api/v1/admin/risk-events/{event_no}"): "risk:view",
    ("POST", "/api/v1/admin/risk-events/{event_no}/review"): "risk:review",
    ("POST", "/api/v1/admin/risk-events/{event_no}/report-authority"): "risk:review（须先复核）",
    ("GET", "/api/v1/admin/rights"): "rights:view",
    ("POST", "/api/v1/admin/rights/{request_no}/process"): "rights:handle",
    ("GET", "/api/v1/admin/rights/{request_no}/export-file"): "rights:view",
    ("PUT", "/api/v1/admin/configs/{config_key}"): "cfg:write（仅超管）+ 二次确认",
    ("POST", "/api/v1/admin/configs/{config_key}/rollback"): "cfg:write（仅超管）+ 二次确认",
    ("PUT", "/api/v1/admin/products/{product_code}"): "cfg:write（仅超管）+ 二次确认",
    ("POST", "/api/v1/admin/orders/{order_no}/reconcile-resolve"): "rights:handle + 二次确认",
}

# ---------------------------------------------------------------------------
# 响应要点（data 结构概述）与端点特有错误码（来自代码审查与 docstring Raises 口径）
# 键：(METHOD, 完整路径)；值：(响应要点, 特有错误码说明)
# ---------------------------------------------------------------------------
ENDPOINT_NOTES: Dict[Tuple[str, str], Tuple[str, str]] = {
    # ---- 系统 ----
    ("GET", "/api/v1/health"): ("{service, db_connected, model_whitelist[], llm_mock}", "无（DB 不可达以 degraded 字段表达）"),
    ("GET", "/api/v1/texts"): ("{texts: {text_id: content}}", "1001 ids 为空"),
    ("GET", "/api/v1/metrics"): ("{counters, latency{p50,p95,samples}, rates, alerts[]}", "无"),
    ("GET", "/api/v1/admin/metrics/alert-history"): ("{items:[{id, metric, value, threshold, message, status, started_at}]}（最近 50 条）", "1101 未登录"),
    ("POST", "/api/v1/safety-scan/callback"): ("{record_id, audit_result, idempotent, object_type, object_id}", "1901 密钥未配置；1001 时间戳超窗；1102 签名不匹配；1002 记录不存在"),
    # ---- 认证同意 ----
    ("POST", "/api/v1/auth/dev-login"): ("令牌对 + {user_uid, member_status}（幂等登录）", "1901 落库异常兜底"),
    ("POST", "/api/v1/auth/wx-login"): ("令牌对 + {user_uid, member_status}", "1101 通道未启用；1901 微信服务不可用"),
    ("POST", "/api/v1/auth/refresh"): ("新令牌对 + {user_uid, member_status}", "1101 刷新令牌无效/过期/类型不符"),
    ("GET", "/api/v1/consent/status"): ("{base:{agreed,version,agreed_at,withdraw_at}, child_personal_info:{...}}", "1101"),
    ("POST", "/api/v1/consent/agree"): ("{consent_type, consent_version, agreed_at, idempotent}", "1001 consent_type 非法"),
    ("POST", "/api/v1/consent/withdraw"): ("{consent_type, withdrawn, withdrawn_at?, impact?}", "1001 consent_type 非法"),
    # ---- 档案 ----
    ("GET", "/api/v1/profiles/children"): ("{children:[档案视图]}（解密展示，disabled 昵称脱敏）", "1101"),
    ("POST", "/api/v1/profiles/children"): ("新建档案视图（含 age_months/age_band/version）", "1302 未完成儿童信息同意；1006 档案超上限(409)"),
    ("PUT", "/api/v1/profiles/children/{profile_uid}"): ("更新后档案视图（version+1，重算月龄档位）", "1002 不存在/越权；1003 乐观锁冲突(409)"),
    ("DELETE", "/api/v1/profiles/children/{profile_uid}"): ("{deleted, mode, deletion_receipt?(purge_all)}", "1002 不存在/越权；1001 昵称校验不一致"),
    ("GET", "/api/v1/profiles/pets"): ("{pets:[宠物视图]}", "1101"),
    ("POST", "/api/v1/profiles/pets"): ("新建宠物视图", "1006 档案超上限(409)"),
    ("PUT", "/api/v1/profiles/pets/{pet_uid}"): ("更新后宠物视图（version+1）", "1002 不存在/越权；1003 乐观锁冲突(409)"),
    ("DELETE", "/api/v1/profiles/pets/{pet_uid}"): ("{deleted: true}", "1002 不存在/越权"),
    ("POST", "/api/v1/profiles/current"): ("{profile_type, profile_uid, updated_at}", "1002 档案不存在/越权/已删除"),
    ("POST", "/api/v1/profiles/{kind}/{uid}/avatar"): ("{avatar_url, width, height, size}（multipart：file 字段单文件；POST 口径见描述）", "1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)；1001 图片格式不支持/超 8MB(422)"),
    ("DELETE", "/api/v1/profiles/{kind}/{uid}/avatar"): ("{deleted: true}（幂等：未设置时同样成功）", "1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)"),
    ("GET", "/api/v1/profiles/{kind}/{uid}/photos"): ("{photos:[{photo_uid, url, size, created_at}], limit}（按加入时间升序）", "1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)"),
    ("POST", "/api/v1/profiles/{kind}/{uid}/photos"): ("{photo, count, limit}（multipart：file 字段单张上传）", "1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)；1001 图片格式不支持/超 8MB(422)；1007 相册数量已达上限(409)"),
    ("DELETE", "/api/v1/profiles/{kind}/{uid}/photos/{photo_uid}"): ("{deleted: true}", "1002 档案或照片不存在/越权；1302 儿童同意缺失或已撤回(403)"),
    # ---- 问答 ----
    ("POST", "/api/v1/qa/sessions"): ("{session_uid, status: pending}；幂等重放附 idempotent_replay/result_ref", "1406 入口维护中(503)；1004 同键处理中(409)；1203 已有活跃流(409, retry_after=30)；1202 免费额度用尽(429)；1002 档案不存在；1001 参数/指纹不符"),
    ("POST", "/api/v1/qa/sessions/{session_uid}/stream"): ("SSE 流：started→section_delta/section_done→completed（blocked 单帧）", "1002 会话不存在/越权"),
    ("POST", "/api/v1/qa/sessions/{session_uid}/cancel"): ("{session_uid, status}", "1002 会话不存在/越权；1102 取消凭证不匹配"),
    ("GET", "/api/v1/qa/sessions/{session_uid}"): ("会话元数据 + sections（会员门控裁剪）+ render_order", "1002 会话不存在/越权"),
    ("GET", "/api/v1/qa/sessions/{session_uid}/stream"): ("SSE 续发：section_done*→completed（blocked 单帧）", "1002 不存在/越权；1004 会话未完成(409)"),
    ("POST", "/api/v1/qa/sessions/{session_uid}/regenerate"): ("{session_uid, section, section_version, status}", "1002 不存在/越权；1102 非会员(403)；1401 风险拦截(HTTP 200)；1001 非法分节"),
    ("POST", "/api/v1/risk/appeals"): ("{appeal_no, sla_due_at, status}（命中硬类别 status=abandoned）", "1002 会话/事件不存在或无权限；1001 申诉次数已达上限(400)"),
    ("GET", "/api/v1/risk/appeals/{appeal_no}"): ("{appeal_no, status, sla_due_at, review_result, resubmit_allowed?, allow_expire_at?}", "1002 申诉单不存在/无权限"),
    ("GET", "/api/v1/risk/channels"): ("{channels:[渠道卡]}", "1001 类别参数非法"),
    # ---- 测评 ----
    ("GET", "/api/v1/assessment/questions"): ("{question_version, age_band, demo_note, questions[]}", "1406 入口维护中(503)；1002 题库未初始化"),
    ("POST", "/api/v1/assessment/start"): ("测评断点视图（resumed=True 表示续填）", "1101"),
    ("PUT", "/api/v1/assessment/{assessment_uid}/answer"): ("{answered_count, skipped_count, draft_expire_at}", "1002 不存在/越权；1001 已提交(409)；1002 断点过期(410)"),
    ("POST", "/api/v1/assessment/{assessment_uid}/submit"): ("{assessment_uid, report_uid, type_code, idempotent_replay}", "1002 不存在/越权；1004 并发同键(409)；1001 缺答过多(422)/同键不同指纹(409)"),
    ("GET", "/api/v1/assessment/{assessment_uid}/report"): ("报告视图（blocks 按会员状态裁剪 content，readonly 标记）", "1002 不存在/越权/报告未生成"),
    # ---- 商业化 ----
    ("GET", "/api/v1/billing/quota"): ("{used, limit, remaining, is_member, biz_date, unlimited?}", "1101"),
    ("GET", "/api/v1/billing/product"): ("iOS：{purchasable:false, reason_code}；其他：{purchasable:true, products[]}", "1101"),
    ("POST", "/api/v1/billing/orders"): ("订单视图 + idempotent_replay", "1004 同键处理中(409)；1001 同键不同指纹(409)/未确认退款政策；1002 商品不存在或未上架"),
    ("POST", "/api/v1/billing/orders/{order_no}/mock-pay"): ("{order_no, status, transaction_id, member_expire_at, already_processed}", "1504 验签失败(400)；1002 订单不存在/越权；1501 状态不允许(409)"),
    ("GET", "/api/v1/billing/orders"): ("{orders:[订单视图]}（创建时间倒序）", "1101"),
    ("GET", "/api/v1/billing/subscription"): ("{member_status, member_expire_at, subscription?}", "1101"),
    # ---- 权利反馈 ----
    ("POST", "/api/v1/rights/requests"): ("{request_no, request_type, status, sla_due_at}", "1101"),
    ("GET", "/api/v1/rights/requests"): ("{requests:[请求视图]}（创建时间倒序）", "1101"),
    ("GET", "/api/v1/rights/requests/{request_no}/download"): ("FileResponse 或纯文本下载地址（链接一次有效）", "1002 不存在/越权/非导出类/未生成/已下载/已过期"),
    ("POST", "/api/v1/feedback"): ("{feedback_no, receipt_hours, audit_result}", "1303 敏感词/送检未通过(403)/送检配额超限(429)"),
    ("POST", "/api/v1/reports"): ("{report_no, sla_due_at}（涉未成年 24h，其余 72h）", "1101"),
    ("GET", "/api/v1/me"): ("{user_uid, member_status, member_expire_at, child_profile_count, pet_profile_count, register_at}", "1101"),
    ("GET", "/api/v1/me/consents"): ("{consents: {base: bool, child_personal_info: bool}}", "1101"),
    # ---- 知识库 ----
    ("GET", "/api/v1/admin/kb/entries"): ("{items, total, page, page_size, pending_badge}（专家域隔离）", "1103 缺少 kb:view"),
    ("POST", "/api/v1/admin/kb/entries"): ("{kb_id, status: draft}", "1103 缺少 kb:edit；1603 专家跨领域"),
    ("PUT", "/api/v1/admin/kb/entries/{kb_id}"): ("{kb_id, version, status, warnings[]}", "1002 不存在；1103 kb:edit；1601 乐观锁(409)；1603 跨领域"),
    ("POST", "/api/v1/admin/kb/entries/{kb_id}/submit"): ("{kb_id, status, review_no}", "1002 不存在；1001 非 draft 状态(409)；1103 kb:edit；1603 跨领域"),
    ("POST", "/api/v1/admin/kb/entries/{kb_id}/review"): ("{kb_id, status, version}", "1002 不存在/无待审工单；1001 reject 缺理由码(422)；1103 kb:review；1602 缺二次确认；1603 跨领域"),
    ("POST", "/api/v1/admin/kb/entries/{kb_id}/unpublish"): ("{kb_id, status, affected_sessions}", "1002 不存在；1103 kb:publish；1602 缺二次确认；1603 跨领域"),
    ("POST", "/api/v1/admin/kb/entries/{kb_id}/rollback"): ("{kb_id, version, status: draft}", "1002 不存在；1103 kb:rollback；1601 乐观锁(409)；1602 缺二次确认；1603 跨领域"),
    ("GET", "/api/v1/admin/kb/entries/{kb_id}/versions"): ("{kb_id, items[]}（审计聚合版本历史）", "1002 不存在；1103 kb:view"),
    ("GET", "/api/v1/admin/kb/reviews"): ("{items, total, page, page_size}", "1103 缺少 kb:view"),
    ("GET", "/api/v1/admin/trace-tasks"): ("{items, total, page, page_size}（追溯任务列表）", "1103 缺少 kb:view"),
    ("POST", "/api/v1/admin/trace-tasks/{task_id}/dispose"): ("{task_id, disposal_level, status}", "1002 任务不存在；1001 处置等级非法(422)；1103 kb:review；1602 缺二次确认"),
    # ---- 词库 ----
    ("GET", "/api/v1/admin/lexicon/terms"): ("{items, total, page, page_size}（term 解密展示）", "1103 缺少 lex:view"),
    ("POST", "/api/v1/admin/lexicon/terms"): ("{id, term_hash, lexicon_type, strategy}", "1001 词条已存在(409)；1103 lex:edit"),
    ("PUT", "/api/v1/admin/lexicon/terms/{term_id}"): ("词条视图（term 重算密文与哈希）", "1002 不存在；1103 lex:edit"),
    ("DELETE", "/api/v1/admin/lexicon/terms/{term_id}"): ("{id, deleted: true}", "1002 不存在；1103 lex:edit；1602 缺二次确认"),
    ("GET", "/api/v1/admin/lexicon/config"): ("{items[]}", "1103 缺少 lex:view"),
    ("PUT", "/api/v1/admin/lexicon/config/{config_key}"): ("{config_key, config_value}（upsert + 版本留痕）", "1103 缺少 lex:edit"),
    ("POST", "/api/v1/admin/lexicon/test"): ("{hit, matched_terms[], matched_patterns[]}", "1103 缺少 lex:view"),
    # ---- 处置 ----
    ("POST", "/api/v1/admin/login"): ("{mfa_required: true, mfa_ticket}", "1101 用户名或密码错误(401)；1103 账号已锁定(403)"),
    ("POST", "/api/v1/admin/mfa/verify"): ("{token, role, display_name, domain_scope, menus}", "1104 票据无效/过期或验证码错误(403)"),
    ("GET", "/api/v1/admin/me"): ("{admin_uid, username, display_name, role, domain_scope, phone_masked, menus}", "1101 未登录"),
    ("GET", "/api/v1/admin/audit-logs"): ("{items, total, page, page_size}（快照仅返回键名）", "1103 非超管"),
    ("GET", "/api/v1/admin/refunds"): ("{items, total, page, page_size}", "1103 缺少 rights:handle"),
    ("PUT", "/api/v1/admin/refunds/{request_no}"): ("{request_no, status, entitlement_recycled}", "1002 工单不存在；1001 已处置(409)/驳回缺理由码(422)/action 非法(422)；1103 rights:handle"),
    ("GET", "/api/v1/admin/agent-logs"): ("{items, total, page, page_size}（脱敏）", "1103 缺少 log:view"),
    ("GET", "/api/v1/admin/agent-logs/export"): ("CSV 文件流（StreamingResponse）", "1103 缺少 log:view/非超管；1602 缺二次确认"),
    ("GET", "/api/v1/admin/agent-logs/{log_id}"): ("日志详情（脱敏）", "1002 不存在；1103 log:view"),
    ("GET", "/api/v1/admin/feedback"): ("{items, total, page, page_size}（正文按权限解密）", "1103 缺少 fb:view"),
    ("PUT", "/api/v1/admin/feedback/{feedback_id}"): ("{feedback_id, status, reply}", "1002 不存在；1001 已回复(409)；1103 fb:handle"),
    ("GET", "/api/v1/admin/reports"): ("{items, total, page, page_size}（涉未成年优先）", "1103 缺少 fb:view"),
    ("PUT", "/api/v1/admin/reports/{report_no}"): ("{report_no, status}", "1002 不存在；1001 action 非法(422)；1602 escalate 缺证据/确认；1103 fb:handle"),
    ("GET", "/api/v1/admin/risk-events"): ("{items, total, page, page_size}", "1103 缺少 risk:view"),
    ("GET", "/api/v1/admin/risk-events/{event_no}"): ("事件详情", "1002 不存在；1103 risk:view"),
    ("POST", "/api/v1/admin/risk-events/{event_no}/review"): ("{event_no, conclusion, resubmit_allowed?}", "1002 不存在；1001 conclusion 非法(422)；1103 risk:review"),
    ("POST", "/api/v1/admin/risk-events/{event_no}/report-authority"): ("上报结果", "1002 不存在；1103 未复核先上报/缺 risk:review"),
    ("GET", "/api/v1/admin/rights"): ("{items, total, page, page_size}", "1103 缺少 rights:view"),
    ("POST", "/api/v1/admin/rights/{request_no}/process"): ("{request_no, status, export_file_url?}", "1002 不存在；1001 已处置(409)/action 非法(422)/拒绝缺理由码(422)；1103 rights:handle"),
    ("GET", "/api/v1/admin/rights/{request_no}/export-file"): ("FileResponse（24h 有效）", "1002 不存在/文件未生成；1004 链接过期(410)；1103 rights:view"),
    # ---- 配置 ----
    ("GET", "/api/v1/admin/configs"): ("{items[]}（每 config_type+key 最新版）", "1103 非超管"),
    ("PUT", "/api/v1/admin/configs/{config_key}"): ("{config_key, version, status}（版本留痕 + 缓存热更新）", "1002 键不存在；1103 非超管；1602 缺二次确认"),
    ("POST", "/api/v1/admin/configs/{config_key}/rollback"): ("{config_key, version}（回滚至指定版本）", "1002 版本不存在；1103 非超管；1602 缺二次确认"),
    ("GET", "/api/v1/admin/configs/{config_key}/history"): ("{items[]}（版本历史）", "1103 非超管"),
    ("GET", "/api/v1/admin/products"): ("{items[]}（价格配置卡数据源）", "1101"),
    ("PUT", "/api/v1/admin/products/{product_code}"): ("{product_code, price_micro}", "1002 商品不存在；1103 非超管；1602 缺二次确认"),
    ("POST", "/api/v1/admin/orders/{order_no}/reconcile-resolve"): ("{order_no, reconcile_status}", "1002 订单不存在；1001 resolution 非法(422)；1501 非差异订单(409)；1103 rights:handle；1602 缺二次确认"),
    # ---- history（补充 tag） ----
    ("GET", "/api/v1/history"): ("{total, page, page_size, items[]}（问答+报告联合列表）", "1101"),
    ("GET", "/api/v1/history/qa/{session_uid}"): ("会话详情（sections 全量、非会员裁剪、readonly、content_updated）", "1002 不存在/越权/未完成"),
    ("GET", "/api/v1/history/report/{report_uid}"): ("报告视图（blocks 按会员裁剪）", "1002 不存在或越权"),
    ("GET", "/api/v1/history/{item_type}/{uid}/image"): ("{report_uid, sections, disclaimer_ratio, disclaimer_count, qr_placeholder, scale}", "1001 非 report 类型(422)；1002 不存在或越权"),
}


def load_openapi() -> dict:
    """加载 OpenAPI 规范。

    优先请求运行中的服务（NO_PROXY 绕过本机系统代理），失败则本地导入
    app.main.app 生成。

    Returns:
        OpenAPI JSON 字典。

    Raises:
        SystemExit: 两种方式均失败时退出（退出码 1）。
    """
    # 方式一：运行中服务（需绕过本机系统代理）
    try:
        os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
        os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
        import httpx

        resp = httpx.get(OPENAPI_URL, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        print(f"[export] loaded openapi from {OPENAPI_URL}")
        return data
    except Exception:
        pass
    # 方式二：本地导入 app 生成
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, backend_dir)
        from app.main import app

        data = app.openapi()
        print("[export] loaded openapi from local app.openapi()")
        return data
    except Exception as exc:  # noqa: BLE001
        print(f"[export] ERROR: cannot load openapi: {exc}")
        sys.exit(1)


def _default_auth(method: str, path: str) -> str:
    """按路径推断默认鉴权级别。

    Args:
        method: HTTP 方法（大写）。
        path: 完整路径（含 /api/v1 前缀）。

    Returns:
        鉴权说明文本。
    """
    rest = path[len("/api/v1"):] if path.startswith("/api/v1") else path
    if rest.startswith("/admin"):
        # 后台端点：get_admin 登录态 + 权限矩阵标注（如有）
        perm = ADMIN_PERM_OVERRIDES.get((method, path))
        if perm:
            return f"需后台角色（{perm}）"
        return "需后台角色（get_admin + 角色权限矩阵）"
    return "需登录（Bearer token，get_current_user）"


def _resolve_ref(spec: dict, node: dict) -> Optional[dict]:
    """解析 OpenAPI $ref 引用（仅一层，指向 components.schemas）。

    Args:
        spec: OpenAPI 全量字典。
        node: 可能含 $ref 的节点。

    Returns:
        解析后的 schema 字典；无 $ref 时原样返回，解析失败返回 None。
    """
    ref = node.get("$ref") if isinstance(node, dict) else None
    if not ref:
        return node if isinstance(node, dict) else None
    match = re.match(r"^#/components/schemas/(.+)$", ref)
    if not match:
        return None
    return spec.get("components", {}).get("schemas", {}).get(match.group(1))


def _render_params(spec: dict, op: dict) -> Tuple[List[str], List[str]]:
    """提取路径参数与查询参数描述行。

    Args:
        spec: OpenAPI 全量字典。
        op: 端点 operation 对象。

    Returns:
        (路径参数行列表, 查询参数行列表)。
    """
    path_params: List[str] = []
    query_params: List[str] = []
    for p in op.get("parameters", []) or []:
        resolved = _resolve_ref(spec, p) or p
        name = resolved.get("name", "?")
        where = resolved.get("in")
        schema = resolved.get("schema", {}) or {}
        typ = schema.get("type", "")
        desc = (resolved.get("description") or "").strip()
        required = "必填" if resolved.get("required") else "可选"
        line = f"`{name}`（{typ}，{required}）：{desc}" if desc else f"`{name}`（{typ}，{required}）"
        if where == "path":
            path_params.append(line)
        elif where == "query":
            default = schema.get("default")
            if default is not None:
                line += f"，默认 `{default}`"
            query_params.append(line)
    return path_params, query_params


def _render_body(spec: dict, op: dict) -> List[str]:
    """提取请求体要点（字段名/类型/必填/说明）。

    Args:
        spec: OpenAPI 全量字典。
        op: 端点 operation 对象。

    Returns:
        请求体字段描述行列表（无请求体时为空）。
    """
    body = op.get("requestBody")
    if not body:
        return []
    content = (body.get("content") or {}).get("application/json", {})
    schema = _resolve_ref(spec, content.get("schema", {}))
    if not schema:
        return []
    required = set(schema.get("required", []) or [])
    lines: List[str] = []
    props = schema.get("properties", {}) or {}
    for name, prop in props.items():
        resolved = _resolve_ref(spec, prop) or {}
        typ = prop.get("type") or resolved.get("type") or ""
        if prop.get("type") == "array" or resolved.get("type") == "array":
            item = prop.get("items") or resolved.get("items") or {}
            item_ref = _resolve_ref(spec, item) or {}
            typ = "array" + (f"<{item_ref.get('type', 'object')}>" if item_ref else "<object>")
        req = "必填" if name in required else "可选"
        desc = (prop.get("description") or resolved.get("description") or "").strip()
        lines.append(f"- `{name}`（{typ}，{req}）：{desc}" if desc else f"- `{name}`（{typ}，{req}）")
    return lines


def _pick_tag(op: dict) -> str:
    """选取端点的主分组 tag：优先正式 tags，否则保留原第一个 tag。

    Args:
        op: 端点 operation 对象。

    Returns:
        分组 tag 字符串。
    """
    tags = op.get("tags", []) or ["未分组"]
    for t in tags:
        if t in FORMAL_TAGS:
            return t
    return tags[0]


def _group_endpoints(spec: dict) -> Dict[str, List[Tuple[str, str, dict]]]:
    """将全部端点按 tag 分组。

    Args:
        spec: OpenAPI 全量字典。

    Returns:
        {tag: [(METHOD, path, operation), ...]}，组内按路径与方法排序。
    """
    groups: Dict[str, List[Tuple[str, str, dict]]] = {}
    for path, methods in (spec.get("paths") or {}).items():
        for method, op in methods.items():
            if method not in HTTP_METHODS or not isinstance(op, dict):
                continue
            tag = _pick_tag(op)
            groups.setdefault(tag, []).append((method.upper(), path, op))
    for items in groups.values():
        items.sort(key=lambda x: (x[1], x[0]))
    return groups


def _render_endpoint(spec: dict, method: str, path: str, op: dict) -> List[str]:
    """渲染单个端点小节。

    Args:
        spec: OpenAPI 全量字典。
        method: HTTP 方法（大写）。
        path: 完整路径。
        op: 端点 operation 对象。

    Returns:
        Markdown 行列表（首行为 `## METHOD /path`，供 check 脚本解析）。
    """
    lines: List[str] = [f"## {method} {path}", ""]
    summary = (op.get("summary") or "").strip()
    # description 取 docstring 首段（FastAPI 会把整段 docstring 塞入 description，
    # 其中 Args/Returns/Raises 段落为内部注释口径，不进入文档正文）
    desc = (op.get("description") or "").strip().split("\n\n")[0].strip()
    if desc.startswith("Args:") or desc.startswith(("Returns:", "Raises:")):
        desc = ""
    if summary:
        lines.append(f"**{summary}**")
        lines.append("")
    if desc and desc != summary:
        lines.append(desc)
        lines.append("")
    tags = "、".join(op.get("tags", []) or [])
    auth = AUTH_OVERRIDES.get((method, path)) or _default_auth(method, path)
    lines.append(f"- **Tag**：{tags}")
    lines.append(f"- **鉴权**：{auth}")
    notes = ENDPOINT_NOTES.get((method, path))
    # 路径 / 查询参数
    path_params, query_params = _render_params(spec, op)
    if path_params:
        lines.append("- **路径参数**：" + "；".join(path_params))
    if query_params:
        lines.append("- **查询参数**：")
        for line in query_params:
            lines.append(f"  - {line}")
    # 请求体
    body_lines = _render_body(spec, op)
    if body_lines:
        lines.append("- **请求体**（application/json）：")
        lines.extend("  " + line for line in body_lines)
    # 响应要点 / 错误码
    if notes:
        resp_note, err_note = notes
        lines.append(f"- **响应 data**：{resp_note}")
        if err_note and not err_note.startswith("无"):
            lines.append(f"- **主要错误码**：{err_note}（其余见「通用错误码」）")
    else:
        lines.append("- **响应 data**：统一包络 data（详见端点 docstring）")
    lines.append("")
    return lines


def build_markdown(spec: dict) -> str:
    """组装完整 API.md 文档内容。

    Args:
        spec: OpenAPI 全量字典。

    Returns:
        Markdown 文本。
    """
    groups = _group_endpoints(spec)
    total = sum(len(v) for v in groups.values())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out: List[str] = []
    out.append("# 小光景后端 API 接口文档")
    out.append("")
    out.append("> **生成信息**：由 `backend/scripts/export_api_doc.py` 自动生成（可重复执行，勿手改）")
    out.append(f"> 生成时间：{now} ｜ 生成方式：优先抓取运行中服务 `{OPENAPI_URL}`，失败则本地导入 `app.main.app.openapi()`")
    out.append(f"> 端点总数：{total} ｜ 分组：{len(groups)} 个 tag（{len(FORMAL_TAGS)} 个正式 tags + history 补充组）")
    out.append("")
    out.append("**统一包络**：所有接口返回 `{code, message, data, request_id, trace_id}`；")
    out.append("`code=0` 成功，非 0 为业务错误码（分段：1000 参数 / 1100 鉴权 / 1200 限流额度 / 1300 合规同意 / 1400 问答风险 / 1500 支付 / 1600 后台 / 1900 故障）。")
    out.append("")
    out.append("**鉴权方式**：C 端接口携带 `Authorization: Bearer <user_token>`；后台接口携带后台 admin token；")
    out.append("公开接口（登录/文案/健康检查/指标/安全回调）无需会话，安全回调以 HMAC-SHA256 验签。")
    out.append("")
    out.append("**通用错误码**（全端点适用，端点小节仅列特有错误码）：")
    out.append("")
    out.append("| 错误码 | 含义 | HTTP 状态 |")
    out.append("| --- | --- | --- |")
    out.append("| 1001 | 参数校验失败 | 422 |")
    out.append("| 1002 | 资源不存在（含防枚举的越权场景） | 404 |")
    out.append("| 1003 | 内容已被更新，请刷新（乐观锁，C 端档案） | 409 |")
    out.append("| 1004 | 相同请求正在处理中（幂等冲突） | 409 |")
    out.append("| 1007 | 相册数量已达上限 | 409 |")
    out.append("| 1101 | 会话缺失或已失效 | 401 |")
    out.append("| 1102 | 无权访问该资源 | 403 |")
    out.append("| 1103 | 当前角色无此权限 | 403 |")
    out.append("| 1104 | MFA 校验未通过 | 403 |")
    out.append("| 1201 | 请求过于频繁 | 429 |")
    out.append("| 1202 | 今日免费额度已用尽 | 429 |")
    out.append("| 1301 | 请先同意用户协议与免责声明 | 403 |")
    out.append("| 1302 | 需先完成儿童信息单独同意 | 403 |")
    out.append("| 1303 | 内容安全送检未通过 | 403 |")
    out.append("| 1406 | 该功能维护中（入口开关关闭） | 503 |")
    out.append("| 1601 | 内容已被更新，请刷新后重试（后台乐观锁） | 409 |")
    out.append("| 1602 | 危险操作需要二次确认 | 403 |")
    out.append("| 1603 | 超出您的授权领域范围（专家域绑定） | 403 |")
    out.append("| 1901 | 依赖服务不可用 | 503 |")
    out.append("| 1902 | 服务内部错误 | 500 |")
    out.append("")
    # 目录
    out.append("## 目录")
    out.append("")
    for tag in GROUP_ORDER:
        if tag in groups:
            anchor = tag.replace(" ", "-").replace("/", "").replace("（", "").replace("）", "")
            out.append(f"- [{tag}](#{anchor})（{len(groups[tag])} 个端点）")
    out.append("")
    # 分组正文
    for tag in GROUP_ORDER:
        if tag not in groups:
            continue
        out.append(f"# {tag}")
        out.append("")
        if tag == "history":
            out.append(f"> 补充分组：4 个历史端点在 OpenAPI 中使用独立 `history` tag（未列入 {len(FORMAL_TAGS)} 个正式 tags），建议后续任务归并至 C端-问答 或补登正式 tag。")
            out.append("")
        for method, path, op in groups[tag]:
            out.extend(_render_endpoint(spec, method, path, op))
    out.append("---")
    out.append(f"*本文档由脚本自动生成于 {now}，共 {total} 个端点。*")
    return "\n".join(out) + "\n"


def main() -> None:
    """脚本入口：加载 OpenAPI → 渲染 Markdown → 写出 docs/API.md。

    Returns:
        None。

    Raises:
        SystemExit: OpenAPI 加载失败时以退出码 1 终止。
    """
    spec = load_openapi()
    md = build_markdown(spec)
    os.makedirs(os.path.dirname(DOC_PATH), exist_ok=True)
    with open(DOC_PATH, "w", encoding="utf-8") as fh:
        fh.write(md)
    endpoints = sum(1 for line in md.splitlines() if line.startswith("## ") and " /api/" in line)
    print(f"[export] wrote {DOC_PATH} ({endpoints} endpoints)")


if __name__ == "__main__":
    main()

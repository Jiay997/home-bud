/**
 * =============================================================================
 * 文件级注释：Babe宝伴后台管理端 API 封装（Task 8 / PA-01~PA-08 专用）
 * =============================================================================
 * 1. 独立于 C 端 client.ts：内部自带 fetch 请求帮助函数；
 * 2. 统一包络 {code, message, data}，code=0 视为成功，否则抛出 ApiError；
 * 3. 鉴权：请求头 Authorization: Bearer <token>，token 存于 localStorage('jiaban_admin_token')；
 * 4. 二次确认约定：危险操作请求体/查询参数携带 confirm_token:"CONFIRMED"（日志导出走查询参数）；
 * 5. 后端契约基地址：http://localhost:8000/api/v1。
 */

import { ElMessageBox } from 'element-plus'

/** 后端 API 基地址（同源代理） */
const BASE_URL = '/api/v1'

/** 管理端登录令牌 localStorage 键名 */
export const TOKEN_KEY = 'jiaban_admin_token'

/** 管理端账号信息（角色/显示名/菜单）localStorage 键名 */
export const INFO_KEY = 'jiaban_admin_info'

/** 危险操作二次确认固定令牌（与后端约定：confirm_token = "CONFIRMED"） */
export const CONFIRM_TOKEN = 'CONFIRMED'

/**
 * 类级注释：后台 API 业务/网络错误。
 * 统一请求函数在包络 code!==0、HTTP 非 2xx、响应非合法包络三种情况下抛出本异常。
 */
export class ApiError extends Error {
  /** 错误码：业务码（如 1602 需二次确认、1003/1601 并发冲突）或 HTTP 状态码，包络缺失时为 -1 */
  code: number

  /**
   * 构造函数
   * @param code 错误码
   * @param message 错误提示文案
   */
  constructor(code: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

/**
 * 函数级注释：读取管理端登录令牌
 * @returns localStorage 中的 token，未登录时为空字符串
 */
export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

/**
 * 函数级注释：保存管理端登录令牌
 * @param token 登录/MFA 校验通过后返回的 token
 */
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * 函数级注释：清除登录态（退出登录时调用）
 */
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(INFO_KEY)
}

/**
 * 会话失效（HTTP 401 / 业务码 1101）统一处理：清登录态 + 整页回登录页。
 *
 * 背景：后台令牌为 30 分钟无操作过期（后端 ADMIN_IDLE_TTL）。原先前端只校验
 * 「localStorage 里有没有 token」，过期后 SPA 仍停留在控制台、所有接口 401，
 * 表现为「已经登录进去却什么都加载不出来 / 界面像坏了」。此处统一兜底：
 * 一旦命中会话失效，立即清态并整页跳登录页（带 expired=1 供登录页提示），
 * 避免用户停留在半失效的控制台里。
 *
 * 说明：用整页跳转而非 router 跳转——此时路由实例状态不可靠（可能正处在
 * 未完成的导航中），整页跳转同时可重新拉取最新 index.html 与分包。
 */
let redirectingToLogin = false

function handleSessionExpired(): void {
  clearAuth()
  if (redirectingToLogin) return
  if (typeof window === 'undefined') return
  // 已在登录页则不再跳转（避免循环）
  if (window.location.pathname.startsWith('/admin/login')) return
  redirectingToLogin = true
  window.location.replace('/admin/login?expired=1')
}

/**
 * 函数级注释：读取管理端账号信息
 * @returns 登录时保存的 {role, display_name, domain_scope, menus} 对象；未登录或解析失败返回 null
 */
export function getAdminInfo(): any {
  try {
    const raw = localStorage.getItem(INFO_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * 函数级注释：保存管理端账号信息
 * @param info 登录成功后的账号信息对象（role/display_name/domain_scope/menus 等）
 */
export function setAdminInfo(info: any): void {
  localStorage.setItem(INFO_KEY, JSON.stringify(info))
}

/** 接口级注释：单次请求选项 */
interface ReqOptions {
  /** URL 查询参数（值为 undefined/null/空串时自动忽略） */
  params?: Record<string, any>
  /** 请求体对象（自动 JSON 序列化；GET 请求忽略） */
  body?: any
  /** 附加请求头（例如导出场景的 X-Confirm-Token） */
  headers?: Record<string, string>
}

/**
 * 函数级注释：统一请求帮助函数（fetch + 包络解析）
 * @param method HTTP 方法（GET/POST/PUT/DELETE）
 * @param path API 路径，以 / 开头（自动拼接 BASE_URL）
 * @param opts 查询参数/请求体/附加请求头，可选
 * @returns 包络中 data 字段内容
 * @throws ApiError 包络 code!==0、HTTP 状态非 2xx、响应非合法 JSON 包络时抛出
 */
async function request<T = any>(method: string, path: string, opts: ReqOptions = {}): Promise<T> {
  // 拼接 URL 并序列化查询参数（相对路径需带 base，否则 new URL 抛 TypeError）
  const url = new URL(BASE_URL + path, location.origin)
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    }
  }
  // 组装请求头：默认 JSON + Bearer 令牌
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  let resp: Response
  try {
    resp = await fetch(url.toString(), {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch (e: any) {
    // 网络层异常（断网/超时/后端未启动）
    throw new ApiError(-1, `网络异常：${e?.message || '请检查后端服务是否可用'}`)
  }

  // 尝试解析 JSON 包络
  let env: any = null
  try {
    env = await resp.json()
  } catch {
    env = null
  }

  if (!resp.ok) {
    // 会话失效（401/1101）：清态并回登录页，避免停留在半失效的控制台
    if (resp.status === 401 || (env && env.code === 1101)) {
      handleSessionExpired()
    }
    // HTTP 失败：优先取后端包络中的业务码与文案（如 409 + code=1003 并发冲突）
    if (env && typeof env.code === 'number' && env.code !== 0) {
      throw new ApiError(env.code, env.message || `请求失败（HTTP ${resp.status}）`)
    }
    throw new ApiError(resp.status, `请求失败（HTTP ${resp.status}）`)
  }
  if (!env || typeof env.code !== 'number') {
    throw new ApiError(-1, '响应包络格式错误（缺少 code 字段）')
  }
  if (env.code !== 0) {
    // 兜底：HTTP 200 但业务码为会话失效
    if (env.code === 1101) handleSessionExpired()
    throw new ApiError(env.code, env.message || '业务处理失败')
  }
  return env.data as T
}

/**
 * 函数级注释：二次确认请求包装器。
 * 先正常发起请求；若后端返回 1602（缺少二次确认令牌），弹出确认框，
 * 用户确认后自动携带 confirm_token:"CONFIRMED" 重发一次。
 * @param fn 执行请求的函数，入参为 confirmToken（首次调用为 undefined，重发时为 CONFIRM_TOKEN）
 * @param opts.message 确认框文案（缺省时使用后端返回的 message）
 * @returns 请求成功时的 data
 * @throws ApiError 用户取消确认时抛出 code=-2；请求本身失败时透传 ApiError
 */
export async function withConfirm(
  fn: (confirmToken?: string) => Promise<any>,
  opts: { message?: string } = {}
): Promise<any> {
  try {
    return await fn()
  } catch (e) {
    // 仅对"缺少二次确认令牌"错误码 1602 做自动确认重发
    if (e instanceof ApiError && e.code === 1602) {
      try {
        await ElMessageBox.confirm(
          opts.message || (e as ApiError).message || '该操作为高风险操作，确定继续执行？',
          '二次确认',
          { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' }
        )
      } catch {
        throw new ApiError(-2, '用户取消了二次确认')
      }
      return await fn(CONFIRM_TOKEN)
    }
    throw e
  }
}

/**
 * 函数级注释：将 Blob 内容触发浏览器下载
 * @param blob 文件二进制内容
 * @param filename 下载保存的文件名
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 函数级注释：导出 Agent 调用日志 CSV（二次确认通过 confirm_token 查询参数传递）
 * @param params 筛选参数（session_id/agent_id/status/time_start/time_end 等）
 * @returns CSV 文件 Blob
 * @throws ApiError HTTP 失败或被权限拒绝时抛出
 */
export async function exportAgentLogsCsv(params: Record<string, any> = {}): Promise<Blob> {
  // BASE_URL 为相对路径，new URL 需显式提供 base，否则抛 TypeError
  const url = new URL(BASE_URL + '/admin/agent-logs/export', location.origin)
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  }
  // 后端契约：二次确认凭证从 query 参数 confirm_token 读取（非请求头）
  url.searchParams.set('confirm_token', CONFIRM_TOKEN)
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const resp = await fetch(url.toString(), { headers })
  if (!resp.ok) throw new ApiError(resp.status, `导出失败（HTTP ${resp.status}）`)
  return await resp.blob()
}

// =============================================================================
// V3.1 类型契约（危机渠道清单 / 分级规则 / 内容运营 / 门禁自检）
// 字段名与后端 admin_v31_api.py 逐字一致，勿改写为前端别名（否则列表全部落空）。
// =============================================================================

/** 渠道状态枚举（active 已核验可用 / pending_review 待复核 / placeholder 号码待补充 / retired 已停用） */
export type ChannelStatus = 'active' | 'pending_review' | 'placeholder' | 'retired'

/** 危机渠道条目（GET /admin/channels → items 元素） */
export interface ChannelItem {
  /** 主键 */
  id: number
  /** 版本号（后端以 id 派生） */
  version: number
  /** 渠道编码（业务唯一键） */
  channel_code: string
  /** 渠道名称 */
  channel_name: string
  /** 类目编码 */
  category: string
  /** 类目中文名 */
  category_label: string
  /** 号码（占位/超期/脱敏场景为 null） */
  phone_number: string | null
  /** 是否已对当前角色脱敏（true 时号码展示为 ***） */
  phone_masked: boolean
  /** 引导话术 */
  script: string | null
  /** 覆盖地域 */
  region: string
  /** 服务时段 */
  service_hours: string | null
  /** 适用的风险类别编码清单 */
  applicable_categories: string[]
  /** 状态 */
  status: ChannelStatus
  /** 是否为占位卡（号码不可对外展示） */
  placeholder: boolean
  /** 占位/待复核提示文案 */
  notice: string | null
  /** 最近核验时间 */
  verified_at: string | null
  /** 最近核验人 */
  verified_by: string | null
  /** 复核到期时间 */
  review_due_at: string | null
  /** 是否已超期未复核 */
  expired: boolean
  /** 数据源标识（固定 crisis_channel） */
  source: string
}

/** 渠道核验汇总（GET /admin/channels → summary） */
export interface ChannelSummary {
  /** 总数 */
  total: number
  /** active 数 */
  active: number
  /** 占位数 */
  placeholder: number
  /** 待复核数 */
  pending_review: number
  /** 已停用数 */
  retired: number
  /** 已核验数（有号码且 active） */
  verified: number
  /** 按类目统计 */
  by_category: Record<string, { total: number; verified: number }>
  /** 未达标的必备类别（类目 → 缺失类别编码清单） */
  missing_required: Record<string, string[]> | string[]
}

/** GET /admin/channels 返回 */
export interface ChannelListResult {
  /** 渠道条目 */
  items: ChannelItem[]
  /** 核验汇总 */
  summary: ChannelSummary
  /** 类目字典（编码 → 中文名） */
  categories: Record<string, string>
  /** 单一数据源标识 */
  data_source: string
}

/** POST /admin/channels 请求体 */
export interface ChannelCreateBody {
  channel_code: string
  channel_name: string
  category: string
  phone_number?: string
  region: string
  service_hours?: string
  applicable_categories: string[]
  script?: string
  sort_weight: number
}

/** PUT /admin/channels/{channel_code} 请求体（改号码时必须带 confirm_token + 后 4 位 + 原因） */
export interface ChannelUpdateBody {
  channel_name?: string
  phone_number?: string
  category?: string
  region?: string
  service_hours?: string
  applicable_categories?: string[]
  script?: string
  sort_weight?: number
  status?: ChannelStatus
  /** 变更原因（改号码必填） */
  reason: string
  /** 改号码二次确认：渠道编码后 4 位 */
  channel_code_suffix?: string
  /** 危险操作二次确认凭证 */
  confirm_token?: string
}

/** POST /admin/channels/{channel_code}/review 请求体 */
export interface ChannelReviewBody {
  /** 核验方式：电话拨测 / 官网核对 / 口头确认 / 书面文件 */
  review_method: 'call_dial' | 'official_site' | 'verbal' | 'document'
  /** 核验结论 */
  review_result: 'reachable' | 'unreachable' | 'changed' | 'pending'
  conclusion?: string
  note?: string
}

/** 渠道核验记录（GET /admin/channels/{channel_code}/reviews → items 元素） */
export interface ChannelReviewRecord {
  review_no: string
  review_method: string
  review_result: string
  reviewer: string
  conclusion: string | null
  note: string | null
  channel_version: number | null
  reviewed_at: string | null
}

/** POST /admin/channels/{channel_code}/review 返回 */
export interface ChannelReviewResult {
  review_no: string
  channel: ChannelItem
  summary: ChannelSummary
}

/** 分级规则（GET /admin/triage-rules → items 元素） */
export interface TriageRuleItem {
  rule_id: string
  scene: string
  domain: string
  title: string
  age_min_months: number | null
  age_max_months: number | null
  conditions: Record<string, any>
  /** 档位：red / yellow / green */
  level: string
  /** 优先级（大者优先） */
  priority: number
  /** 循证依据 */
  basis: string | null
  observations: string[]
  escalation_flags: string[]
  contraindications: string[]
  disclaimers: string[]
  source_ref: string | null
  /** 专家签署（空串/None 视为未签） */
  expert_signoff: string | null
  expert_reviewed_at: string | null
  status: string
  version: number
}

/** 规则快照摘要（triage_engine.rule_summary） */
export interface TriageSnapshot {
  source?: string
  rule_version?: string | number
  total?: number
  by_scene?: Record<string, number>
  signed?: number
}

/** GET /admin/triage-rules 返回 */
export interface TriageRuleListResult {
  items: TriageRuleItem[]
  snapshot: TriageSnapshot
  signed: number
  total: number
  /** 全量会签完成才为 true（发布门禁前置条件） */
  gate_ready: boolean
}

/** PUT /admin/triage-rules/{rule_id} 请求体（必须带 confirm_token） */
export interface TriageRuleUpdateBody {
  title?: string
  level?: string
  priority?: number
  conditions?: Record<string, any>
  basis?: string
  observations?: string[]
  escalation_flags?: string[]
  contraindications?: string[]
  disclaimers?: string[]
  status?: string
  reason: string
  confirm_token?: string
}

/** POST /admin/triage-rules/{rule_id}/review 请求体 */
export interface TriageRuleReviewBody {
  /** 专家签署（姓名/工号） */
  expert_signoff: string
  note?: string
}

/** POST /admin/triage-rules/{rule_id}/review 返回 */
export interface TriageRuleReviewResult {
  rule: TriageRuleItem
  signed: number
  total: number
  gate_ready: boolean
}

/** 专题包（GET /admin/topics → items 元素） */
export interface TopicItem {
  topic_code: string
  title: string
  domain: string
  summary: string | null
  price_micro: number
  product_code: string | null
  redflag_first: boolean
  redflag_blocks: Array<Record<string, any>>
  content_blocks: Array<Record<string, any>>
  review_child_signoff: string | null
  review_pet_signoff: string | null
  status: string
  /** 上架校验问题（status=on 时须为空） */
  publish_issues: string[]
  disclaimer?: string | null
}

/** POST /admin/topics 请求体（按 topic_code upsert） */
export interface TopicUpsertBody {
  topic_code: string
  title: string
  domain: string
  summary?: string
  price_micro: number
  product_code?: string
  redflag_first: boolean
  redflag_blocks: Array<Record<string, any>>
  content_blocks: Array<Record<string, any>>
  review_child_signoff?: string
  review_pet_signoff?: string
  status: 'draft' | 'on' | 'off'
}

/** 轻工具（GET /admin/tools → items 元素） */
export interface ToolItem {
  tool_code: string
  title: string
  tool_type: string
  domain: string
  summary: string | null
  kb_refs: string[]
  status: string
  version?: number
  sort_order: number
  /** 工具正文内容（后台编辑回显用；对话端不外泄） */
  content?: Record<string, any>
  /** 内容合规问题（确定性进食结论等） */
  issues: string[]
}

/** POST /admin/tools 请求体（按 tool_code upsert） */
export interface ToolUpsertBody {
  tool_code: string
  title: string
  tool_type: 'checklist' | 'parser'
  domain: string
  summary?: string
  kb_refs: string[]
  content: Record<string, any>
  sort_order: number
  status: string
}

/** 文案扫描命中项 */
export interface CopyScanHit {
  phrase: string
  path: string
  line: number
  snippet: string
  suggestion: string | null
}

/** 文案扫描结果 */
export interface CopyScanResult {
  hits: CopyScanHit[]
  hit_count: number
  scanned_files: number
  blocked: boolean
  errors: string[]
}

/** 文案扫描检查清单项 */
export interface CopyScanChecklistItem {
  id: string
  question: string
}

/** POST /admin/copy-scan 返回 */
export interface CopyScanResponse {
  /** repository（全仓库扫描）/ texts（指定文案扫描） */
  mode: string
  result: CopyScanResult
  checklist: CopyScanChecklistItem[]
}

/** 触达任务统计（GET /admin/reminders/stats） */
export interface ReminderStats {
  total: number
  by_type: Record<string, number>
  by_status: Record<string, number>
  delivered_by_channel: Record<string, number>
  send_fail: number
  privacy_note: string
}

/** 发布门禁项（GET /admin/gates/summary → gates 元素） */
export interface GateItem {
  id: string
  title: string
  passed: boolean
  detail: Record<string, any>
}

/** GET /admin/gates/summary 返回 */
export interface GatesSummary {
  gates: GateItem[]
  /** 四项全通过才为 true */
  passed: boolean
}

/**
 * 对象级注释：后台管理端业务 API 集合（按模块分组）。
 * 所有方法返回包络 data；失败时抛出 ApiError。
 */
export const adminApi = {
  // ─────────────── 登录与账号（PA-01） ───────────────

  /**
   * 函数级注释：管理员账号密码登录
   * @param username 账号
   * @param password 密码
   * @returns {mfa_required, mfa_ticket, token?}；mfa_required=false 时可能直接携带 token
   * @throws ApiError 密码错误/连续失败锁定时抛出（文案来自后端）
   */
  async login(username: string, password: string) {
    return request('POST', '/admin/login', { body: { username, password } })
  },

  /**
   * 函数级注释：MFA 二次验证（开发模式验证码 123456）
   * @param mfa_ticket 登录第一步返回的 MFA 票据
   * @param code 短信验证码
   * @returns {token, role, display_name, domain_scope, menus}
   * @throws ApiError 验证码错误/过期时抛出
   */
  async mfaVerify(mfaTicket: string, code: string) {
    return request('POST', '/admin/mfa/verify', { body: { mfa_ticket: mfaTicket, code } })
  },

  /**
   * 函数级注释：获取当前登录管理员信息
   * @returns 当前账号信息（role/display_name/menus 等）
   * @throws ApiError 未登录/令牌失效时抛出
   */
  async getMe() {
    return request('GET', '/admin/me')
  },

  // ─────────────── 知识库（PA-02 / PA-03） ───────────────

  /**
   * 函数级注释：知识库条目分页列表
   * @param params {kb_kind, status, keyword, page, page_size}
   * @returns {list, total, page, page_size}（以实际包络为准）
   * @throws ApiError 请求失败时抛出
   */
  async kbList(params: Record<string, any> = {}) {
    return request('GET', '/admin/kb/entries', { params })
  },

  /**
   * 函数级注释：新建知识库条目
   * @param body 条目内容（标题/领域/正文/标签/变更说明等）
   * @returns 新建条目（含 kb_id 与初始 version）
   * @throws ApiError 校验失败时抛出
   */
  async kbCreate(body: Record<string, any>) {
    return request('POST', '/admin/kb/entries', { body })
  },

  /**
   * 函数级注释：更新知识库条目（携带 version 乐观锁）
   * @param kbId 条目 ID
   * @param body 更新内容，必须包含 version 字段
   * @returns 更新后的条目
   * @throws ApiError 并发冲突（409/code=1003/1601）时抛出
   */
  async kbUpdate(kbId: string, body: Record<string, any>) {
    return request('PUT', `/admin/kb/entries/${encodeURIComponent(kbId)}`, { body })
  },

  /**
   * 函数级注释：提交条目进入审核流
   * @param kbId 条目 ID
   * @returns 提交结果（可能携带 warnings 发布前校验提示）
   * @throws ApiError 状态不允许提交时抛出
   */
  async kbSubmit(kbId: string) {
    return request('POST', `/admin/kb/entries/${encodeURIComponent(kbId)}/submit`)
  },

  /**
   * 函数级注释：审核条目（通过/驳回）
   * @param kbId 条目 ID
   * @param body {verdict, score?, reject_code?, confirm_token}
   * @returns 审核结果
   * @throws ApiError 缺少二次确认（1602）时抛出，可配合 withConfirm 重发
   */
  async kbReview(kbId: string, body: Record<string, any>) {
    return request('POST', `/admin/kb/entries/${encodeURIComponent(kbId)}/review`, { body })
  },

  /**
   * 函数级注释：下架条目
   * @param kbId 条目 ID
   * @param body {reason, confirm_token}
   * @returns 下架结果
   * @throws ApiError 缺少二次确认（1602）时抛出
   */
  async kbUnpublish(kbId: string, body: Record<string, any>) {
    return request('POST', `/admin/kb/entries/${encodeURIComponent(kbId)}/unpublish`, { body })
  },

  /**
   * 函数级注释：回滚条目到历史版本（触发内容追溯处置）
   * @param kbId 条目 ID
   * @param body {target_version, reason, confirm_token}
   * @returns 回滚结果
   * @throws ApiError 目标版本不存在/缺少二次确认时抛出
   */
  async kbRollback(kbId: string, body: Record<string, any>) {
    return request('POST', `/admin/kb/entries/${encodeURIComponent(kbId)}/rollback`, { body })
  },

  /**
   * 函数级注释：获取条目版本历史
   * @param kbId 条目 ID
   * @returns 版本列表（version/操作人/时间/变更摘要）
   * @throws ApiError 条目不存在时抛出
   */
  async kbVersions(kbId: string) {
    return request('GET', `/admin/kb/entries/${encodeURIComponent(kbId)}/versions`)
  },

  /**
   * 函数级注释：审核工单列表
   * @param params {status, kb_kind, page}
   * @returns 工单列表
   * @throws ApiError 请求失败时抛出
   */
  async kbReviews(params: Record<string, any> = {}) {
    return request('GET', '/admin/kb/reviews', { params })
  },

  /**
   * 函数级注释：内容追溯任务列表（回滚/下架触发）
   * @param params {status, page}
   * @returns 追溯任务列表
   * @throws ApiError 请求失败时抛出
   */
  async traceTaskList(params: Record<string, any> = {}) {
    return request('GET', '/admin/trace-tasks', { params })
  },

  /**
   * 函数级注释：执行内容追溯分级处置（A/B/C）
   * @param taskId 追溯任务 ID
   * @param body {disposal_level:'A'|'B'|'C', confirm_token}
   * @returns 处置结果
   * @throws ApiError 缺少二次确认/分级非法时抛出
   */
  async traceTaskDispose(taskId: string, body: Record<string, any>) {
    return request('POST', `/admin/trace-tasks/${encodeURIComponent(taskId)}/dispose`, { body })
  },

  // ─────────────── 词库（PA-04） ───────────────

  /**
   * 函数级注释：词库词条列表
   * @param params {type:'risk'|'sensitive', page, page_size≤100}
   * @returns 词条列表 {items, total, page, page_size}
   * @throws ApiError 请求失败时抛出
   */
  async lexiconTermList(params: Record<string, any> = {}) {
    return request('GET', '/admin/lexicon/terms', { params })
  },

  /**
   * 函数级注释：新增词条
   * @param body {term, lexicon_type:'risk'|'sensitive', strategy, threshold_band?, category_code?, effective?}
   * @returns 新增词条 {id, term_hash, lexicon_type, strategy}
   * @throws ApiError 词条重复（1001）/参数非法时抛出
   */
  async lexiconTermCreate(body: Record<string, any>) {
    return request('POST', '/admin/lexicon/terms', { body })
  },

  /**
   * 函数级注释：更新词条（部分更新：term / strategy / threshold_band / category_code / effective）
   * @param id 词条 ID
   * @param body 更新内容
   * @returns 更新后词条
   * @throws ApiError 参数非法时抛出
   */
  async lexiconTermUpdate(id: string | number, body: Record<string, any>) {
    return request('PUT', `/admin/lexicon/terms/${encodeURIComponent(String(id))}`, { body })
  },

  /**
   * 函数级注释：删除词条（高危操作，需 confirm_token）
   * @param id 词条 ID
   * @returns 删除结果
   * @throws ApiError 缺少二次确认（1602）时抛出
   */
  async lexiconTermDelete(id: string | number) {
    return request('DELETE', `/admin/lexicon/terms/${encodeURIComponent(String(id))}`, {
      body: { confirm_token: CONFIRM_TOKEN },
    })
  },

  /**
   * 函数级注释：读取风险规则配置列表（two_level_threshold 与各模式正则）
   * @returns 配置项列表 {items:[{config_key, config_value, effective_at, version, updated_by}]}
   * @throws ApiError 请求失败时抛出
   */
  async lexiconConfigList() {
    return request('GET', '/admin/lexicon/config')
  },

  /**
   * 函数级注释：保存风险规则配置（按 config_key upsert，变更影响线上拦截行为）
   * @param configKey 配置键（two_level_threshold / medicine_dosage_pattern / diagnosis_pattern / efficacy_pattern）
   * @param body {config_value, reason?, confirm_token?}
   * @returns 保存结果 {config_key, config_value}
   * @throws ApiError 缺少二次确认（1602）时抛出
   */
  async lexiconConfigPut(configKey: string, body: Record<string, any>) {
    return request('PUT', `/admin/lexicon/config/${encodeURIComponent(configKey)}`, { body })
  },

  /**
   * 函数级注释：词库/规则测试器
   * @param text 待检测样例文本
   * @returns {hit, matched_terms, matched_patterns}
   * @throws ApiError 规则语法错误时抛出
   */
  async lexiconTest(text: string) {
    return request('POST', '/admin/lexicon/test', { body: { text } })
  },

  // ─────────────── Agent 调用日志（PA-05） ───────────────

  /**
   * 函数级注释：Agent 调用日志分页列表
   * @param params {session_id, agent_id, status, time_start, time_end, page, page_size}
   * @returns 日志列表（隐私字段已脱敏）
   * @throws ApiError 请求失败时抛出
   */
  async agentLogList(params: Record<string, any> = {}) {
    return request('GET', '/admin/agent-logs', { params })
  },

  /**
   * 函数级注释：单条日志详情（调度决策/参与 Agent/引用/冲突比对/风险层级）
   * @param id 日志 ID
   * @returns 日志详情
   * @throws ApiError 不存在或无权限时抛出
   */
  async agentLogDetail(id: string | number) {
    return request('GET', `/admin/agent-logs/${encodeURIComponent(String(id))}`)
  },

  // ─────────────── 反馈与举报（PA-06） ───────────────

  /**
   * 函数级注释：用户反馈列表
   * @param params {status, page}
   * @returns 反馈列表
   * @throws ApiError 请求失败时抛出
   */
  async feedbackList(params: Record<string, any> = {}) {
    return request('GET', '/admin/feedback', { params })
  },

  /**
   * 函数级注释：回复用户反馈
   * @param id 反馈 ID
   * @param body {reply_content}（必填）
   * @returns 回复结果
   * @throws ApiError 回复内容为空时抛出
   */
  async feedbackReply(id: string | number, body: Record<string, any>) {
    return request('PUT', `/admin/feedback/${encodeURIComponent(String(id))}`, { body })
  },

  /**
   * 函数级注释：投诉举报列表
   * @param params {status, page}
   * @returns 举报列表
   * @throws ApiError 请求失败时抛出
   */
  async reportList(params: Record<string, any> = {}) {
    return request('GET', '/admin/reports', { params })
  },

  /**
   * 函数级注释：处置投诉举报
   * @param reportNo 举报编号
   * @param body {action:'dismiss'|'removed'|'escalated', basis, evidence?}
   * @returns 处置结果
   * @throws ApiError 依据缺失/状态不允许时抛出
   */
  async reportHandle(reportNo: string, body: Record<string, any>) {
    return request('PUT', `/admin/reports/${encodeURIComponent(reportNo)}`, { body })
  },

  // ─────────────── 高风险事件（PA-07） ───────────────

  /**
   * 函数级注释：高风险事件列表
   * @param params {status, level, page}
   * @returns 事件列表
   * @throws ApiError 请求失败时抛出
   */
  async riskEventList(params: Record<string, any> = {}) {
    return request('GET', '/admin/risk-events', { params })
  },

  /**
   * 函数级注释：高风险事件详情
   * @param eventNo 事件编号
   * @returns 事件详情（含上下文快照）
   * @throws ApiError 不存在时抛出
   */
  async riskEventDetail(eventNo: string) {
    return request('GET', `/admin/risk-events/${encodeURIComponent(eventNo)}`)
  },

  /**
   * 函数级注释：值班复核风险事件
   * @param eventNo 事件编号
   * @param body {conclusion:'upheld'|'misreport'|'need_more', reason_code}
   * @returns 复核结果（出具后 disposal_result 有值，方可上报）
   * @throws ApiError 理由缺失时抛出
   */
  async riskEventReview(eventNo: string, body: Record<string, any>) {
    return request('POST', `/admin/risk-events/${encodeURIComponent(eventNo)}/review`, { body })
  },

  /**
   * 函数级注释：上报监管部门（复核结论出具前调用将返回 1103）
   * @param eventNo 事件编号
   * @param body {reported_target} 上报对象
   * @returns 上报结果
   * @throws ApiError 结论未出具（1103）时抛出
   */
  async riskEventReportAuthority(eventNo: string, body: Record<string, any>) {
    return request('POST', `/admin/risk-events/${encodeURIComponent(eventNo)}/report-authority`, { body })
  },

  // ─────────────── 权利请求 / 配置 / 审计（PA-08） ───────────────

  /**
   * 函数级注释：个人信息权利请求列表
   * @param params {status, page}
   * @returns 权利请求列表
   * @throws ApiError 请求失败时抛出
   */
  async rightsList(params: Record<string, any> = {}) {
    return request('GET', '/admin/rights', { params })
  },

  /**
   * 函数级注释：处理权利请求
   * @param no 请求编号
   * @param body {action:'generate_export'|'mark_done'|'reject', format?, reject_reason_code?}
   * @returns 处理结果（generate_export 可能返回下载地址）
   * @throws ApiError 拒绝理由缺失/状态不允许时抛出
   */
  async rightsProcess(no: string, body: Record<string, any>) {
    return request('POST', `/admin/rights/${encodeURIComponent(no)}/process`, { body })
  },

  /**
   * 函数级注释：系统配置列表（入口开关/价格/AI 文案/危机渠道等）
   * @param params 预留筛选参数
   * @returns 配置项列表 {key, value, value_type, description, updated_at, updated_by}
   * @throws ApiError 请求失败时抛出
   */
  async configList(params: Record<string, any> = {}) {
    return request('GET', '/admin/configs', { params })
  },

  /**
   * 函数级注释：更新系统配置（需 reason 留痕，通常还需二次确认）
   * @param key 配置键
   * @param body {snapshot, reason, confirm_token?}
   * @returns 更新结果
   * @throws ApiError 缺少二次确认（1602）时抛出
   */
  async configUpdate(key: string, body: Record<string, any>) {
    return request('PUT', `/admin/configs/${encodeURIComponent(key)}`, { body })
  },

  /**
   * 函数级注释：回滚配置到历史版本
   * @param key 配置键
   * @param body {target_version, confirm_token}
   * @returns 回滚结果
   * @throws ApiError 版本不存在/缺少二次确认时抛出
   */
  async configRollback(key: string, body: Record<string, any>) {
    return request('POST', `/admin/configs/${encodeURIComponent(key)}/rollback`, { body })
  },

  /**
   * 函数级注释：配置变更历史
   * @param key 配置键
   * @returns 版本历史列表
   * @throws ApiError 配置不存在时抛出
   */
  async configHistory(key: string) {
    return request('GET', `/admin/configs/${encodeURIComponent(key)}/history`)
  },

  /**
   * 函数级注释：读取 Agent 展示权重（当前生效版本）
   * @returns {weights, version, updated_at, defaults, safety_pinned}
   * @throws ApiError 无权限（缺 cfg:write）时抛出
   */
  async agentWeights() {
    return request('GET', '/admin/agent-weights')
  },

  /**
   * 函数级注释：更新 Agent 展示权重（超管 + 二次确认）
   * @param body {weights, reason, confirm_token}
   * @returns {weights, version, before, diff}
   * @throws ApiError 权重非法/缺少二次确认时抛出
   */
  async updateAgentWeights(body: Record<string, any>) {
    return request('PUT', '/admin/agent-weights', { body })
  },

  /**
   * 函数级注释：读取 Agent 权重历史版本
   * @param limit 最大条数
   * @returns {items}
   * @throws ApiError 无权限时抛出
   */
  async agentWeightHistory(limit = 20) {
    return request('GET', '/admin/agent-weights/history', { params: { limit } })
  },

  /**
   * 函数级注释：按版本回滚 Agent 权重
   * @param body {version, reason, confirm_token}
   * @returns 回滚后新版本结果
   * @throws ApiError 目标版本不存在/缺少二次确认时抛出
   */
  async rollbackAgentWeight(body: Record<string, any>) {
    return request('POST', '/admin/agent-weights/rollback', { body })
  },

  /**
   * 函数级注释：商品列表（价格配置卡数据源）
   * @returns 商品列表 items（product_code/name/price_micro 等）
   * @throws ApiError 未登录后台时抛出
   */
  async productList() {
    return request('GET', '/admin/products')
  },

  /**
   * 函数级注释：更新商品价格（仅超管，需 reason 留痕 + 二次确认）
   * @param productCode 商品编码（如 member_monthly）
   * @param body {price_micro, reason, confirm_token}
   * @returns 更新后的价格
   * @throws ApiError 商品不存在/非超管/缺少二次确认时抛出
   */
  async productUpdate(productCode: string, body: Record<string, any>) {
    return request('PUT', `/admin/products/${encodeURIComponent(productCode)}`, { body })
  },

  /**
   * 函数级注释：审计日志列表（仅超管/运营可见）
   * @param params {page, page_size, operator, action}
   * @returns 审计日志列表
   * @throws ApiError 无权限（403）时抛出
   */
  async auditLogList(params: Record<string, any> = {}) {
    return request('GET', '/admin/audit-logs', { params })
  },

  // ─────────────── V3.1 危机渠道清单（RQ-03 单一数据源） ───────────────

  /**
   * 函数级注释：危机渠道清单（问答渠道卡与后台维护读同一张 crisis_channel 表）
   * @returns {items, summary, categories, data_source}
   * @throws ApiError 缺 channel:view（1103）时抛出
   */
  async channelList(params: Record<string, any> = {}) {
    return request<ChannelListResult>('GET', '/admin/channels', { params })
  },

  /**
   * 函数级注释：新增危机渠道（号码未核验时留空，禁止编造）
   * @param body 渠道创建请求体
   * @returns 新建渠道条目
   * @throws ApiError 编码已存在（1001/409）、缺 channel:edit（1103）时抛出
   */
  async channelCreate(body: ChannelCreateBody) {
    return request<ChannelItem>('POST', '/admin/channels', { body })
  },

  /**
   * 函数级注释：编辑危机渠道（改号码需 confirm_token + 渠道编码后 4 位 + 原因）
   * @param channelCode 渠道编码
   * @param body 更新请求体
   * @returns 更新后渠道条目
   * @throws ApiError 缺二次确认（1602）、后 4 位不符/原因为空（1001）、不存在（1002）时抛出
   */
  async channelUpdate(channelCode: string, body: ChannelUpdateBody) {
    return request<ChannelItem>('PUT', `/admin/channels/${encodeURIComponent(channelCode)}`, { body })
  },

  /**
   * 函数级注释：提交渠道核验记录（人工拨测/官网核对结论留痕）
   * @param channelCode 渠道编码
   * @param body 核验方式/结论/说明
   * @returns {review_no, channel, summary}
   * @throws ApiError 方式或结论非法（1001）、缺 channel:review（1103）时抛出
   */
  async channelReview(channelCode: string, body: ChannelReviewBody) {
    return request<ChannelReviewResult>(
      'POST',
      `/admin/channels/${encodeURIComponent(channelCode)}/review`,
      { body }
    )
  },

  /**
   * 函数级注释：渠道核验记录（按时间倒序，最近 50 条）
   * @param channelCode 渠道编码
   * @returns {items:[{review_no, review_method, review_result, reviewer, ...}]}
   * @throws ApiError 缺 channel:view（1103）时抛出
   */
  async channelReviews(channelCode: string) {
    return request<{ items: ChannelReviewRecord[] }>(
      'GET',
      `/admin/channels/${encodeURIComponent(channelCode)}/reviews`
    )
  },

  // ─────────────── V3.1 分级规则（RQ-06） ───────────────

  /**
   * 函数级注释：分级规则列表（含专家会签状态与 gate_ready）
   * @param params {scene?} 场景过滤
   * @returns {items, snapshot, signed, total, gate_ready}
   * @throws ApiError 缺 triage:view（1103）时抛出
   */
  async triageRuleList(params: Record<string, any> = {}) {
    return request<TriageRuleListResult>('GET', '/admin/triage-rules', { params })
  },

  /**
   * 函数级注释：编辑分级规则（阈值/档位变更需二次确认 + 原因）
   * @param ruleId 规则编码
   * @param body 更新请求体（必须含 confirm_token）
   * @returns {rule, snapshot}
   * @throws ApiError 缺二次确认（1602）、档位非法（1001）、不存在（1002）时抛出
   */
  async triageRuleUpdate(ruleId: string, body: TriageRuleUpdateBody) {
    return request<{ rule: TriageRuleItem; snapshot: TriageSnapshot }>(
      'PUT',
      `/admin/triage-rules/${encodeURIComponent(ruleId)}`,
      { body }
    )
  },

  /**
   * 函数级注释：分级规则专家会签（发布门禁前置条件）
   * @param ruleId 规则编码
   * @param body {expert_signoff, note?}
   * @returns {rule, signed, total, gate_ready}
   * @throws ApiError 缺 triage:review（1103）、不存在（1002）时抛出
   */
  async triageRuleReview(ruleId: string, body: TriageRuleReviewBody) {
    return request<TriageRuleReviewResult>(
      'POST',
      `/admin/triage-rules/${encodeURIComponent(ruleId)}/review`,
      { body }
    )
  },

  // ─────────────── V3.1 内容运营：专题包 / 轻工具（RQ-12/13/14） ───────────────

  /**
   * 函数级注释：专题包列表（含草稿、双签状态与上架校验问题）
   * @returns {items}
   * @throws ApiError 缺 content:view（1103）时抛出
   */
  async topicList() {
    return request<{ items: TopicItem[] }>('GET', '/admin/topics')
  },

  /**
   * 函数级注释：新增或更新专题包（按 topic_code upsert）
   * @param body 专题包请求体
   * @returns {topic, publish_issues}
   * @throws ApiError 上架条件不满足（422/code=1001，message 列出问题）、领域非法时抛出
   */
  async topicUpsert(body: TopicUpsertBody) {
    return request<{ topic: TopicItem; publish_issues: string[] }>('POST', '/admin/topics', { body })
  },

  /**
   * 函数级注释：轻工具列表（含未上架条目与内容合规问题）
   * @returns {items}
   * @throws ApiError 缺 content:view（1103）时抛出
   */
  async toolList() {
    return request<{ items: ToolItem[] }>('GET', '/admin/tools')
  },

  /**
   * 函数级注释：新增或更新轻工具（按 tool_code upsert）
   * @param body 工具请求体
   * @returns {tool_code, status}
   * @throws ApiError 内容含确定性进食结论（422/code=1001）、类型非法时抛出
   */
  async toolUpsert(body: ToolUpsertBody) {
    return request<{ tool_code: string; status: string }>('POST', '/admin/tools', {
      body: { confirm_token: CONFIRM_TOKEN, ...body },
    })
  },

  // ─────────────── V3.1 文案合规扫描 / 触达统计 / 发布门禁 ───────────────

  /**
   * 函数级注释：文案合规扫描（texts 为空时扫描全仓库）
   * @param texts {名称: 文案} 具名文案，缺省/空对象时全仓库扫描
   * @returns {mode, result, checklist}
   * @throws ApiError 缺 content:view（1103）时抛出
   */
  async copyScan(texts: Record<string, string> = {}) {
    return request<CopyScanResponse>('POST', '/admin/copy-scan', { body: { texts } })
  },

  /**
   * 函数级注释：触达任务统计（仅统计与状态，不含问答原文）
   * @returns {total, by_type, by_status, delivered_by_channel, send_fail, privacy_note}
   * @throws ApiError 缺 content:view（1103）时抛出
   */
  async reminderStats() {
    return request<ReminderStats>('GET', '/admin/reminders/stats')
  },

  /**
   * 函数级注释：V3.1 发布门禁自检（四项阻塞门禁当前状态）
   * @returns {gates:[{id, title, passed, detail}], passed}
   * @throws ApiError 缺 content:view（1103）时抛出
   */
  async gatesSummary() {
    return request<GatesSummary>('GET', '/admin/gates/summary')
  },

  // ─────────────── 系统监控 ───────────────

  /**
   * 函数级注释：运行指标与告警快照（系统监控页数据源）
   * @returns {counters, latency:{p50,p95,samples}, rates, alerts}
   * @throws ApiError 请求失败时抛出
   */
  async metrics() {
    return request('GET', '/metrics')
  },

  /**
   * 函数级注释：告警历史列表（alert_watch 任务留痕，最近 50 条倒序）
   * @returns {items:[{id, metric, value, threshold, message, status, started_at}]}
   * @throws ApiError 请求失败时抛出
   */
  async alertHistory() {
    return request('GET', '/admin/metrics/alert-history')
  },

  // ─────────────── 退款 ───────────────

  /**
   * 函数级注释：退款单列表
   * @param params {status, page}
   * @returns 退款单列表
   * @throws ApiError 请求失败时抛出
   */
  async refundList(params: Record<string, any> = {}) {
    return request('GET', '/admin/refunds', { params })
  },

  /**
   * 函数级注释：处理退款单（通过/拒绝）
   * @param no 退款单号
   * @param body {action:'approve'|'reject', reject_reason_code?}
   * @returns 处理结果
   * @throws ApiError 拒绝理由缺失时抛出
   */
  async refundHandle(no: string, body: Record<string, any>) {
    return request('PUT', `/admin/refunds/${encodeURIComponent(no)}`, { body })
  },
}

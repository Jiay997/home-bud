import { createEndpointResolver, type EndpointResolver } from '../platform/endpoint'
import { resolveMediaUrl } from '../platform/media-url'
import { createRequestClient, createUploadClient } from '../platform/request'
import { isMiniProgram, runtime } from '../platform/runtime'

/**
 * API 根地址。
 * 小程序端：取构建期注入的绝对地址（局域网候选探测依赖绝对地址）；
 * H5 端：固定同源相对路径 /api/v1，由 nginx 反代（生产）或 vite proxy（开发）承接。
 */
export const BASE_URL = isMiniProgram
  ? import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
  : '/api/v1'
export const TOKEN_KEY = 'jiaban_access_token'

// 端点解析器仅在小程序端创建（H5 同源直连无需候选探测）。
// 候选列表内联在 DEV 三元内：生产构建时整支被常量折叠移除，不残留 VITE_API_BASE_URLS 访问。
export const apiEndpoint: EndpointResolver | null = (() => {
  // #ifdef MP-WEIXIN
  return import.meta.env.DEV
    ? createEndpointResolver({
        runtime,
        primary: BASE_URL,
        candidates: String(import.meta.env.VITE_API_BASE_URLS || '')
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean)
      })
    : null
  // #endif
  // #ifndef MP-WEIXIN
  return null
  // #endif
})()

export function activeBaseUrl(): string {
  return apiEndpoint ? apiEndpoint.current() : BASE_URL
}

// 媒体文件 URL（后端 /media 静态挂载）：path 为接口返回的 /media/... 相对路径，
// 拼上当前生效的 API origin；path 为空时返回空串（组件按未设置展示兜底）。
export function mediaUrl(path?: string | null): string {
  return resolveMediaUrl(activeBaseUrl(), path)
}

const request = createRequestClient({
  runtime,
  baseUrl: BASE_URL,
  ...(apiEndpoint
    ? { resolveBaseUrl: () => apiEndpoint.ensure(), onNetworkFailure: () => apiEndpoint.invalidate() }
    : {})
})

const upload = createUploadClient({
  runtime,
  baseUrl: BASE_URL,
  ...(apiEndpoint
    ? { resolveBaseUrl: () => apiEndpoint.ensure(), onNetworkFailure: () => apiEndpoint.invalidate() }
    : {})
})

export type ChildProfileView = {
  profile_uid: string
  nickname: string
  birth_date: string
  gender: 'male' | 'female' | 'unknown' | null
  height_cm: number | null
  weight_kg: number | null
  premature_flag: boolean
  allergy: string[]
  solid_food_month: number | null
  age_months: number
  age_band: '0-6m' | '6-12m' | '1-3y' | '3-6y'
  status: 'active' | 'disabled'
  version: number
  created_at: string | null
  avatar_url: string | null
}

export type PetProfileView = {
  pet_uid: string
  pet_type: 'cat' | 'dog'
  breed: string | null
  age_band: 'junior' | 'adult' | 'senior'
  neutered_flag: boolean | null
  weight_kg: number | null
  main_food: string | null
  version: number
  created_at?: string | null
  avatar_url: string | null
}

export type ProfilePhotoView = {
  photo_uid: string
  url: string
  size: number | null
  created_at: string | null
}

export type ProfileKind = 'children' | 'pets'

export type ChildPayload = {
  nickname: string
  birth_date: string
  gender?: 'male' | 'female' | 'unknown'
  height_cm?: number
  weight_kg?: number
  premature_flag?: boolean
  allergy?: string[]
  solid_food_month?: number
}

export type PetPayload = {
  pet_type: 'cat' | 'dog'
  breed?: string | null
  age_band: 'junior' | 'adult' | 'senior'
  neutered_flag?: boolean | null
  weight_kg?: number | null
  main_food?: string | null
}

export type MeView = {
  user_uid: string
  /** 账号昵称：未设置时为空串，由页面按默认称呼兜底 */
  nickname: string
  /** 账号头像对外 URL（/media/...）；未设置时为 null */
  avatar_url: string | null
  member_status: string
  member_expire_at: string | null
  child_profile_count: number
  pet_profile_count: number
  register_at: string | null
}

/** 账号资料可编辑字段（保存后立即生效） */
export type MeProfileView = {
  nickname: string
  avatar_url: string | null
}

export type HealthRecordView = {
  record_uid: string
  subject_type: 'child' | 'pet'
  subject_uid: string
  record_date: string
  title: string
  next_checkup_date: string | null
  due_status: 'overdue' | 'soon' | 'upcoming' | 'none'
  has_file: boolean
  file_url: string | null
  updated_at: string | null
  notes?: string | null
  next_checkup_note?: string | null
  file_name?: string | null
  file_size?: number | null
  created_at?: string | null
}

export type NoteView = {
  note_uid: string
  title: string
  version: number
  updated_at: string | null
  excerpt?: string
  content?: string
  created_at?: string | null
}

// ---- V3.1 合规与内容资产契约（RQ-01 / RQ-06 / RQ-07 / RQ-08 / RQ-11 / RQ-12 / RQ-13） ----

/** AI 生成标识契约：前端只渲染 text_id 对应文案，禁止自造 */
export type AiLabelView = {
  visible: boolean
  text_id: string
  position: string
  fallback_text: string
  filing_no: string | null
  pages?: Record<string, string>
  min_ratio?: number
  min_count?: number
}

/** 来源等级徽标（DR-10：权威指南 / 学术 / 机构 / 媒体；missing=等级未标注） */
export type TrustSourceLevel = {
  kb_id: string
  title: string
  level: string | null
  level_label: string
  badge: string
  applicable: string | null
  missing: boolean
  low_level: boolean
}

/** 适用月龄 / 宠龄标识（generic=按通用区间回答） */
export type TrustAgeAdaptation = {
  label: string
  hint: string | null
  source: string
  band: string | null
  months: number | null
  generic: boolean
}

/** 首答信任条（RQ-07）：missing 非空表示要素待补，不得静默隐藏 */
export type TrustBarView = {
  ai_label: AiLabelView
  age_adaptation: TrustAgeAdaptation
  source_levels: TrustSourceLevel[]
  triage_badge: { level: string | null; label: string | null; icon: string | null; color: string | null } | null
  elements: Record<string, { status: string; [key: string]: unknown }>
  missing: string[]
  complete: boolean
  checklist: Record<string, boolean>
  checklist_total: number
  checklist_passed: number
}

/** 单条分级规则命中（rule_id 可还原判定依据） */
export type TriageRuleHit = {
  rule_id: string
  title: string
  level: string
  priority: number
  version: number
  source_ref?: string
}

/** 分级档位（RQ-06）：level=null 表示信息不足或服务不可用 */
export type TriageView = {
  level: 'red' | 'yellow' | 'green' | null
  level_label: string
  level_color: string
  icon: string
  action_hint: string
  scene: string | null
  insufficient: boolean
  unavailable: boolean
  missing_info: string[]
  rule_hits: TriageRuleHit[]
  basis: string
  observations: string[]
  escalation_flags: string[]
  contraindications: string[]
  disclaimers: string[]
  night_mode: boolean
  night_notice: string | null
  decided_at: string
}

/** 追问重判结果（档位变化与置顶强提醒） */
export type TriageRecheckView = {
  session_uid?: string
  triage: TriageView | null
  previous_level: string | null
  level_changed: boolean
  escalate_banner: boolean
  banner_text: string | null
}

/** 隐私承诺（RQ-11）：只含已实现能力，每条附可操作跳转 */
export type PrivacyPledgeItem = {
  id: string
  title: string
  promise: string
  implemented: boolean
  evidence: string
  action: { label: string; route: string }
}

export type PrivacyPledgeView = {
  version: string
  items: PrivacyPledgeItem[]
  training_statement: string
  honesty_note: string
  first_boot_hint: string
}

/** 提醒任务（RQ-08）：delivery=inbox 走站内补达 */
export type ReminderTaskView = {
  task_uid: string
  type: string
  title: string
  body: string
  planned_at: string | null
  status: string
  trace_id: string
  sent_at: string | null
  opened_at: string | null
  delivery: string
  /** 任务所属档案类型：child / pet / none（决定问答入口，RQ-08） */
  profile_type?: string | null
}

export type ReminderPrefView = {
  type: string
  enabled: boolean
  configured: boolean
  cap: number | null
  updated_at: string | null
}

export type ReminderPrefsView = {
  items: ReminderPrefView[]
  any_enabled: boolean
  weekly_max: number
  template_reported: boolean
}

export type ReminderListView = {
  items: ReminderTaskView[]
  prefs: ReminderPrefsView
  due_count: number
  weekly_cap: { weekly_max: number }
}

export type WeeklyReportProfile = {
  profile_type: string
  nickname_masked: string
  age_months?: number | null
  age_band?: string | null
  delta_label: string
}

export type WeeklySuggestedQuestion = {
  title: string
  question: string
  kb_id: string
}

export type WeeklyReportView = {
  period: { start: string; end: string }
  profiles: WeeklyReportProfile[]
  last_week_topics: string[]
  suggested_questions: WeeklySuggestedQuestion[]
  privacy_note: string
  generated_at?: string
}

export type WeeklyQuestionView = {
  title: string
  question: string
  kb_id: string
  trace_id: string
  enabled: boolean
}

/** 轻工具内容（清单步骤 / 解析口径）；不判定能否喂食 */
export type ToolContentView = {
  steps?: Array<{ key: string; title: string; detail: string }>
  escalation?: string[]
  how_to_read?: string[]
  common_hazards?: string[]
  caveat?: string
}

export type ToolView = {
  tool_code: string
  title: string
  tool_type: string
  domain: string
  summary: string
  kb_refs: string[]
  content: ToolContentView
  disclaimer: string
  ai_label: AiLabelView
  quota_cost: number
  source: string
}

/** 专题包内容块（红旗块由服务端前置拼入 content_blocks，前端需按 redflag 段宽去重） */
export type TopicBlockView = {
  key?: string
  title?: string
  content?: string
}

export type TopicView = {
  topic_code: string
  title: string
  domain: string
  summary: string
  price_micro: number
  product_code: string | null
  redflag_first: boolean
  redflag_blocks: TopicBlockView[]
  content_blocks: TopicBlockView[]
  member_included: boolean
  purchasable: boolean
  disclaimer: string
  ai_label: AiLabelView
  review_child_signoff?: boolean
  review_pet_signoff?: boolean
}

// ---- 知识科普（每日一则小知识 / 科普全书） ----

/** 科普业务模块：母婴 / 幼儿 / 宠物 / 家庭共处 */
export type KnowledgeCategory = 'infant' | 'toddler' | 'pet' | 'family'

/** 科普分类计数（科普全书顶部 tab 使用） */
export type KnowledgeCategoryView = {
  code: KnowledgeCategory
  label: string
  hint: string
  count: number
}

/** 单条科普知识（首页卡片与科普全书共用） */
export type KnowledgeEntryView = {
  kb_id: string
  title: string
  summary: string
  content: string
  category: KnowledgeCategory
  category_label: string
  topic: string | null
  stage_label: string | null
  preconditions: string | null
  source_level: string | null
  source_name: string | null
}

/** 每日小知识响应：entry=null 表示知识库暂无内容，由客户端展示内置提示 */
export type DailyKnowledgeView = {
  date: string
  entry: KnowledgeEntryView | null
  total: number
}

/** 科普全书响应 */
export type KnowledgeListView = {
  categories: KnowledgeCategoryView[]
  items: KnowledgeEntryView[]
  total: number
}

/** 图片提问场景说明（RQ-05） */
export type PhotoGuideScene = { scene: string; label: string; guide: string }

export type PhotoGuideView = {
  scenes: PhotoGuideScene[]
  selected: PhotoGuideScene | null
  privacy_notice: string
  max_count: number
  ttl_hours: number
  degradation: string
}

export type QaPhotoView = {
  photo_uid: string
  scene: string
  moderation_result: string
  expires_at: string | null
  notice: string
  parse_notice: string
}

/** 就近就医转介（RQ-04 预留：POI 未接入时降级为城市级急诊指引） */
export type ReferralItemView = {
  name: string | null
  address: string | null
  service_hours: string | null
  distance_band: string | null
  data_source: string
  updated_at: string | null
}

export type ReferralView = {
  available: boolean
  enabled: boolean
  items: ReferralItemView[]
  notice: string
  fallback_guide: string | null
  region: { city: string | null; district: string | null }
  reason?: string
}

/** 创建会话请求体（V3.1 增补图片形态与触达归因） */
export type QaSessionBody = {
  entry: 'child' | 'pet' | 'family'
  question: string
  client_request_id: string
  profile_uid?: string
  input_mode?: 'text' | 'voice' | 'photo'
  photo_uids?: string[]
  reminder_trace_id?: string
}

export const api = {
  request,
  consentStatus: () => request<Record<string, { agreed: boolean; version?: string }>>('/consent/status'),
  agreeConsent: () => request('/consent/agree', { method: 'POST', body: { consent_type: 'base' } }),
  quota: () => request<{ used: number; limit: number | null; remaining: number | null; unlimited?: boolean }>('/billing/quota'),
  history: (query: { type?: 'all' | 'qa' | 'report'; profile_type?: 'child' | 'pet' | 'family'; record_date?: string; page?: number; page_size?: number } = {}) =>
    request<{ total: number; page: number; page_size: number; items: Array<{
      item_type: 'qa' | 'report'; uid: string; created_at: string; summary: string;
      is_member_content: boolean; profile_type: 'child' | 'pet' | 'family'; entry?: 'child' | 'pet' | 'family'
    }> }>('/history', { query }),
  historyQa: (sessionUid: string) => request<any>(`/history/qa/${sessionUid}`),
  historyReport: (reportUid: string) => request<any>(`/history/report/${reportUid}`),
  historyItemImage: (reportUid: string) => request<{
    report_uid: string
    sections: Array<{ key: string; title: string; content: string }>
    disclaimer_ratio: number
    disclaimer_count: number
    qr_placeholder: string
    scale: number
  }>(`/history/report/${reportUid}/image`),
  createQaSession: (body: QaSessionBody) =>
    request<{ session_uid: string; status?: string }>('/qa/sessions', { method: 'POST', body }),
  triggerQaGeneration: (sessionUid: string) => {
    const token = runtime.getStorageSync(TOKEN_KEY)
    let immediateError: string | null = null
    runtime.request({
      url: `${activeBaseUrl()}/qa/sessions/${sessionUid}/stream`,
      method: 'POST',
      header: {
        Accept: 'text/event-stream',
        ...(typeof token === 'string' && token ? { Authorization: `Bearer ${token}` } : {})
      },
      timeout: 120000,
      success: (response: { statusCode: number; data?: any }) => {
        if (response.statusCode >= 400) {
          const body = response.data as any
          immediateError = body?.message || `问答服务返回 HTTP ${response.statusCode}`
        }
      },
      fail: (error: { errMsg?: string }) => { immediateError = error?.errMsg || '问答服务连接失败' }
    })
    return () => immediateError
  },
  refreshSession: (refreshToken: string) => request<any>('/auth/refresh', {
    method: 'POST', body: { refresh_token: refreshToken }
  }),
  getQaSession: (sessionUid: string) => request<any>(`/qa/sessions/${sessionUid}`),
  regenerateQaSession: (sessionUid: string, body: { section?: 'safety' | 'child' | 'pet'; client_request_id: string }) =>
    request<{ session_uid: string; section: string | null; section_versions: Record<string, number>; status: string }>(
      `/qa/sessions/${sessionUid}/regenerate`,
      { method: 'POST', body, timeout: 90000 }
    ),
  assessmentQuestions: (ageBand = '1-3y') => request<any>('/assessment/questions', { query: { age_band: ageBand } }),
  startAssessment: () => request<any>('/assessment/start', { method: 'POST', body: {} }),
  putAnswer: (uid: string, qNo: number, rawScore: number) => request(`/assessment/${uid}/answer`, {
    method: 'PUT', body: { q_no: qNo, raw_score: rawScore }
  }),
  submitAssessment: (uid: string, clientRequestId?: string) => request<any>(`/assessment/${uid}/submit`, {
    method: 'POST', body: { client_request_id: clientRequestId || `mp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}` }
  }),
  assessmentReport: (uid: string) => request<any>(`/assessment/${uid}/report`),
  me: () => request<MeView>('/me'),
  updateMeProfile: (body: { nickname: string }) =>
    request<MeProfileView>('/me/profile', { method: 'PUT', body }),
  uploadMeAvatar: (filePath: string | Blob) =>
    // POST 而非 PUT：uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（实测）
    upload<{ avatar_url: string; width: number; height: number; size: number }>(
      '/me/avatar', filePath, { method: 'POST' }
    ),
  removeMeAvatar: () => request<{ deleted: boolean }>('/me/avatar', { method: 'DELETE' }),
  myConsents: () => request<{ consents: Record<string, boolean> }>('/me/consents'),
  subscription: () => request<{
    member_status: string
    member_expire_at: string | null
    subscription: { start_at: string | null; expire_at: string | null; status: string } | null
  }>('/billing/subscription'),
  children: () => request<{ children: ChildProfileView[] }>('/profiles/children'),
  createChild: (body: ChildPayload) => request<ChildProfileView>('/profiles/children', { method: 'POST', body }),
  updateChild: (uid: string, body: ChildPayload & { version: number }) =>
    request<ChildProfileView>(`/profiles/children/${uid}`, { method: 'PUT', body }),
  deleteChild: (uid: string, body: { mode: 'purge_all' | 'profile_only'; confirm_nickname: string }) =>
    request<{ deleted: boolean; mode: string }>(`/profiles/children/${uid}`, { method: 'DELETE', body }),
  pets: () => request<{ pets: PetProfileView[] }>('/profiles/pets'),
  createPet: (body: PetPayload) => request<PetProfileView>('/profiles/pets', { method: 'POST', body }),
  updatePet: (uid: string, body: PetPayload & { version: number }) =>
    request<PetProfileView>(`/profiles/pets/${uid}`, { method: 'PUT', body }),
  deletePet: (uid: string) => request<{ deleted: boolean }>(`/profiles/pets/${uid}`, { method: 'DELETE' }),
  setCurrentProfile: (body: { profile_type: 'child' | 'pet'; profile_uid: string }) =>
    request<{ profile_type: string; profile_uid: string }>('/profiles/current', { method: 'POST', body }),
  uploadProfileAvatar: (kind: ProfileKind, uid: string, filePath: string | Blob) =>
    // POST 而非 PUT：uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（实测）
    upload<{ avatar_url: string; width: number; height: number; size: number }>(
      `/profiles/${kind}/${uid}/avatar`, filePath, { method: 'POST' }
    ),
  removeProfileAvatar: (kind: ProfileKind, uid: string) =>
    request<{ deleted: boolean }>(`/profiles/${kind}/${uid}/avatar`, { method: 'DELETE' }),
  profilePhotos: (kind: ProfileKind, uid: string) =>
    request<{ photos: ProfilePhotoView[]; limit: number }>(`/profiles/${kind}/${uid}/photos`),
  addProfilePhoto: (kind: ProfileKind, uid: string, filePath: string | Blob) =>
    upload<{ photo: ProfilePhotoView; count: number; limit: number }>(
      `/profiles/${kind}/${uid}/photos`, filePath, { method: 'POST' }
    ),
  deleteProfilePhoto: (kind: ProfileKind, uid: string, photoUid: string) =>
    request<{ deleted: boolean }>(`/profiles/${kind}/${uid}/photos/${photoUid}`, { method: 'DELETE' }),
  // ---- 健康档案（甲方需求 2026-10-15：体检报告 + 纯应用内复查提醒） ----
  healthRecords: (query: { subject_type?: 'child' | 'pet'; subject_uid?: string } = {}) =>
    request<{ records: HealthRecordView[]; today: string }>('/health/records', { query }),
  healthRecord: (uid: string) => request<{ record: HealthRecordView }>(`/health/records/${uid}`),
  createHealthRecord: (body: {
    subject_type: 'child' | 'pet'
    subject_uid: string
    record_date: string
    title: string
    notes?: string
    next_checkup_date?: string
    next_checkup_note?: string
  }) => request<{ record: HealthRecordView }>('/health/records', { method: 'POST', body }),
  updateHealthRecord: (uid: string, body: {
    record_date: string
    title: string
    notes?: string
    next_checkup_date?: string
    next_checkup_note?: string
  }) => request<{ record: HealthRecordView }>(`/health/records/${uid}`, { method: 'PUT', body }),
  uploadHealthRecordFile: (uid: string, filePath: string | Blob) =>
    // POST 而非 PUT：uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（实测）
    upload<{ file_url: string; file_name: string; file_size: number }>(
      `/health/records/${uid}/file`, filePath, { method: 'POST', timeout: 120000 }
    ),
  deleteHealthRecord: (uid: string) =>
    request<{ deleted: boolean }>(`/health/records/${uid}`, { method: 'DELETE' }),
  // ---- 个人笔记（甲方需求 2026-10-15：Markdown 知识手册，正文加密） ----
  notes: (keyword?: string) =>
    request<{ notes: NoteView[] }>('/notes', { query: keyword ? { keyword } : {} }),
  note: (uid: string) => request<{ note: NoteView }>(`/notes/${uid}`),
  createNote: (body: { title: string; content: string }) =>
    request<{ note: NoteView }>('/notes', { method: 'POST', body }),
  updateNote: (uid: string, body: { title: string; content: string; version: number }) =>
    request<{ note: NoteView }>(`/notes/${uid}`, { method: 'PUT', body }),
  deleteNote: (uid: string) => request<{ deleted: boolean }>(`/notes/${uid}`, { method: 'DELETE' }),
  agreeChildConsent: () => request('/consent/agree', { method: 'POST', body: { consent_type: 'child_personal_info' } }),
  feedback: (content: string) => request<{ feedback_no: string; receipt_hours: number; audit_result: string }>(
    '/feedback', { method: 'POST', body: { content } }
  ),
  rightsRequest: (requestType: 'access' | 'correct' | 'export' | 'withdraw' | 'delete' | 'deactivate') =>
    request<{ request_no: string; sla_due_at: string | null }>('/rights/requests', {
      method: 'POST', body: { request_type: requestType }
    }),
  rightsRequests: () => request<{ requests: Array<{
    request_no: string
    request_type: string
    scope: Record<string, unknown> | null
    status: string
    delivery_method: string | null
    sla_due_at: string | null
    reject_reason_code: string | null
    created_at: string | null
    handled_at: string | null
  }> }>('/rights/requests'),
  rightsDownloadUrl: (requestNo: string) => `${activeBaseUrl()}/rights/requests/${requestNo}/download`,
  withdrawConsent: (consentType: string) => request('/consent/withdraw', { method: 'POST', body: { consent_type: consentType } }),
  billingProduct: (platform: 'android' | 'ios') => request<{
    purchasable: boolean
    reason_code?: string
    products?: Array<{
      product_code: string
      name: string
      price_micro: number
      duration_days: number
      platform_scope: string | null
      entitlements: unknown
    }>
  }>('/billing/product', { query: { platform } }),
  billingOrders: () => request<{ orders: Array<{
    order_no: string
    amount_micro: number
    platform: string
    status: string
    paid_at: string | null
    created_at: string | null
    product_code?: string
  }> }>('/billing/orders'),
  createReport: (body: {
    object_type: 'qa_answer' | 'assessment'
    object_id: string
    category: 'illegal' | 'medical_misleading' | 'harmful_to_minor' | 'other'
    description?: string
  }) => request<{ report_no: string; sla_due_at: string | null }>('/reports', { method: 'POST', body }),
  // ---- V3.1 合规要素（RQ-01 标识 / RQ-11 隐私承诺） ----
  fetchAiLabel: (page: 'home' | 'answer' | 'report' | 'blocked' | 'history' | 'share_image' = 'answer') =>
    request<AiLabelView>('/compliance/ai-label', { query: { page } }),
  fetchPrivacyPledge: () => request<PrivacyPledgeView>('/compliance/privacy-pledge'),
  // ---- V3.1 留存与主动触达（RQ-08） ----
  listReminders: () => request<ReminderListView>('/reminders'),
  updateReminderPref: (body: { pref_type: string; enabled: boolean }) =>
    request<{ pref_type: string; enabled: boolean; prefs: ReminderPrefsView }>('/reminders/prefs', { method: 'PUT', body }),
  disableAllReminders: () =>
    request<{ disabled: boolean; canceled_tasks: number; prefs: ReminderPrefsView }>('/reminders/prefs/off', { method: 'POST', body: {} }),
  openReminder: (taskUid: string) =>
    request<{ task_uid: string; status: string; trace_id: string }>(
      `/reminders/${taskUid}/open`, { method: 'POST', body: {} }
    ),
  fetchWeeklyReport: () => request<WeeklyReportView>('/reminders/weekly-report'),
  fetchWeeklyQuestion: () => request<WeeklyQuestionView>('/reminders/weekly-question'),
  // ---- V3.1 轻工具（RQ-12） ----
  listTools: (domain?: 'child' | 'pet') =>
    request<{ items: ToolView[]; quota_cost: number; entry: string }>('/tools', { query: domain ? { domain } : {} }),
  fetchTool: (toolCode: string) => request<ToolView>(`/tools/${toolCode}`),
  completeTool: (toolCode: string, body: { completed_items: number; next?: 'qa' | 'topic' | 'done' }) =>
    request<{ tool_code: string; completed_items: number; next: string | null; quota_cost: number }>(
      `/tools/${toolCode}/complete`, { method: 'POST', body }
    ),
  // ---- V3.1 专题包（RQ-13 / RQ-14） ----
  listTopics: (domain?: 'cross' | 'behavior' | 'child' | 'pet') =>
    request<{ items: TopicView[]; member_included: boolean }>('/topics', { query: domain ? { domain } : {} }),
  fetchTopic: (topicCode: string) => request<TopicView>(`/topics/${topicCode}`),
  fetchRecommendedTopics: (entry: 'child' | 'pet' | 'family' = 'family', limit = 2) =>
    request<{ items: TopicView[] }>('/topics/recommended', { query: { entry, limit } }),
  // ---- 知识科普（每日一则小知识 / 科普全书） ----
  fetchDailyKnowledge: () => request<DailyKnowledgeView>('/knowledge/daily'),
  fetchKnowledgeEntries: (category?: KnowledgeCategory) =>
    request<KnowledgeListView>('/knowledge/entries', {
      query: category ? { category } : {}
    }),
  // ---- V3.1 图片提问（RQ-05：无原图返回，只有元数据） ----
  fetchPhotoGuide: (scene = 'unknown') =>
    request<PhotoGuideView>('/qa/photos/guide', { query: { scene } }),
  uploadQaPhoto: (filePath: string | Blob, scene: string) =>
    upload<QaPhotoView>('/qa/photos', filePath, { method: 'POST', formData: { scene } }),
  // ---- V3.1 追问重判（RQ-06） ----
  recheckTriage: (sessionUid: string, body: {
    followup: string
    temperature?: number
    mental_state?: 'normal' | 'poor'
    duration_hours?: number
  }) => request<TriageRecheckView>(`/qa/sessions/${sessionUid}/triage/recheck`, { method: 'POST', body }),
  // ---- V3.1 分享长图与近医转介（RQ-09 / RQ-04 预留） ----
  qaShareCardUrl: (sessionUid: string) =>
    `${activeBaseUrl()}/qa/sessions/${encodeURIComponent(sessionUid)}/share-card.png`,
  fetchReferral: (body: {
    scene: 'emergency_block' | 'triage_red' | 'pet_redflag'
    region_city?: string
    region_district?: string
    session_uid?: string
  }) => request<ReferralView>('/risk/referral', { method: 'POST', body })
}

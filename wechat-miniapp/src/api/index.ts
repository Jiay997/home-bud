import { createEndpointResolver, type EndpointResolver } from '../platform/endpoint'
import { resolveMediaUrl } from '../platform/media-url'
import { createRequestClient, createUploadClient } from '../platform/request'

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
export const TOKEN_KEY = 'jiaban_access_token'

// 候选列表内联在 DEV 三元内：生产构建时整支被常量折叠移除，不残留 VITE_API_BASE_URLS 访问。
export const apiEndpoint: EndpointResolver | null = import.meta.env.DEV
  ? createEndpointResolver({
      runtime: uni,
      primary: BASE_URL,
      candidates: String(import.meta.env.VITE_API_BASE_URLS || '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    })
  : null

export function activeBaseUrl(): string {
  return apiEndpoint ? apiEndpoint.current() : BASE_URL
}

// 媒体文件 URL（后端 /media 静态挂载）：path 为接口返回的 /media/... 相对路径，
// 拼上当前生效的 API origin；path 为空时返回空串（组件按未设置展示兜底）。
export function mediaUrl(path?: string | null): string {
  return resolveMediaUrl(activeBaseUrl(), path)
}

const request = createRequestClient({
  runtime: uni,
  baseUrl: BASE_URL,
  ...(apiEndpoint
    ? { resolveBaseUrl: () => apiEndpoint.ensure(), onNetworkFailure: () => apiEndpoint.invalidate() }
    : {})
})

const upload = createUploadClient({
  runtime: uni,
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
  member_status: string
  member_expire_at: string | null
  child_profile_count: number
  pet_profile_count: number
  register_at: string | null
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
  createQaSession: (body: { entry: 'child' | 'pet' | 'family'; question: string; client_request_id: string; profile_uid?: string }) =>
    request<{ session_uid: string }>('/qa/sessions', { method: 'POST', body }),
  triggerQaGeneration: (sessionUid: string) => {
    const token = uni.getStorageSync(TOKEN_KEY)
    let immediateError: string | null = null
    uni.request({
      url: `${activeBaseUrl()}/qa/sessions/${sessionUid}/stream`,
      method: 'POST',
      header: {
        Accept: 'text/event-stream',
        ...(typeof token === 'string' && token ? { Authorization: `Bearer ${token}` } : {})
      },
      timeout: 120000,
      success: (response) => {
        if (response.statusCode >= 400) {
          const body = response.data as any
          immediateError = body?.message || `问答服务返回 HTTP ${response.statusCode}`
        }
      },
      fail: (error) => { immediateError = error.errMsg || '问答服务连接失败' }
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
  uploadProfileAvatar: (kind: ProfileKind, uid: string, filePath: string) =>
    // POST 而非 PUT：uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（实测）
    upload<{ avatar_url: string; width: number; height: number; size: number }>(
      `/profiles/${kind}/${uid}/avatar`, filePath, { method: 'POST' }
    ),
  removeProfileAvatar: (kind: ProfileKind, uid: string) =>
    request<{ deleted: boolean }>(`/profiles/${kind}/${uid}/avatar`, { method: 'DELETE' }),
  profilePhotos: (kind: ProfileKind, uid: string) =>
    request<{ photos: ProfilePhotoView[]; limit: number }>(`/profiles/${kind}/${uid}/photos`),
  addProfilePhoto: (kind: ProfileKind, uid: string, filePath: string) =>
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
  uploadHealthRecordFile: (uid: string, filePath: string) =>
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
  }) => request<{ report_no: string; sla_due_at: string | null }>('/reports', { method: 'POST', body })
}

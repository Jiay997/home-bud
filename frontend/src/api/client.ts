/**
 * 后端 API 客户端：按契约逐端点封装
 * 所有函数返回包络中的 data；失败抛 ApiError{code, message}。
 */
import { request } from './request'

/* ================= 认证 ================= */

/**
 * 开发环境设备登录
 * @param deviceId 设备唯一标识（localStorage 持久化）
 * @returns token 对与用户信息
 */
export function devLogin(deviceId: string) {
  return request<{ access_token: string; refresh_token: string; user_uid: string; member_status: string }>(
    '/auth/dev-login',
    { method: 'POST', body: { device_id: deviceId } }
  )
}

/** 获取当前用户信息 */
export function getMe() {
  return request('/me')
}

/* ================= 多文案 ================= */

/**
 * 批量获取文案
 * @param ids 文案 id 列表
 * @returns {texts: {id: content}}
 */
export function getTexts(ids: string[]) {
  return request<{ texts: Record<string, string> }>('/texts', {
    query: { ids: ids.join(',') }
  })
}

/* ================= 知情同意 ================= */

/** 查询同意状态 */
export function getConsentStatus() {
  return request('/consent/status')
}

/**
 * 同意协议
 * @param consentType 协议类型（base/child_info 等）
 * @param guardianName 监护人姓名（儿童信息同意时必填）
 */
export function agreeConsent(consentType: string, guardianName?: string) {
  return request('/consent/agree', {
    method: 'POST',
    body: { consent_type: consentType, guardian_name: guardianName }
  })
}

/**
 * 撤回同意
 * @param consentType 协议类型
 */
export function withdrawConsent(consentType: string) {
  return request('/consent/withdraw', {
    method: 'POST',
    body: { consent_type: consentType }
  })
}

/* ================= 档案 ================= */

/**
 * 归一化档案列表项
 * 后端对外标识字段为 profile_uid/pet_uid，前端页面统一消费 uid；
 * 后端宠物档案无昵称字段（数据模型 V1.1），展示名以类型中文兜底。
 * @param item 原始列表项
 * @param uidField 对外标识字段名（profile_uid / pet_uid）
 * @returns 归一化后的列表项
 */
function normalizeProfileItem(item: any, uidField: string): any {
  const normalized = { ...item, uid: item?.[uidField] || item?.uid }
  if (uidField === 'pet_uid') {
    normalized.nickname = item?.nickname || (item?.pet_type === 'dog' ? '狗' : '猫')
  }
  return normalized
}

/** 获取孩子档案列表（uid = profile_uid） */
export function getChildren() {
  return request('/profiles/children').then((d: any) => ({
    ...d,
    children: (d?.children || []).map((c: any) => normalizeProfileItem(c, 'profile_uid'))
  }))
}

/**
 * 新建孩子档案
 * @param payload 档案字段
 */
export function createChild(payload: any) {
  return request('/profiles/children', { method: 'POST', body: payload })
}

/**
 * 更新孩子档案（乐观锁）
 * @param uid 档案 uid
 * @param payload 含 version 的档案字段
 */
export function updateChild(uid: string, payload: any) {
  return request(`/profiles/children/${uid}`, { method: 'PUT', body: payload })
}

/**
 * 删除孩子档案
 * @param uid 档案 uid
 * @param body {mode, confirm_nickname} 级联模式与昵称校验
 */
export function deleteChild(uid: string, body: { mode: string; confirm_nickname: string }) {
  return request(`/profiles/children/${uid}`, { method: 'DELETE', body })
}

/** 获取宠物档案列表（uid = pet_uid；展示昵称缺失时以类型中文兜底） */
export function getPets() {
  return request('/profiles/pets').then((d: any) => ({
    ...d,
    pets: (d?.pets || []).map((p: any) => normalizeProfileItem(p, 'pet_uid'))
  }))
}

/**
 * 新建宠物档案
 * @param payload 档案字段
 */
export function createPet(payload: any) {
  return request('/profiles/pets', { method: 'POST', body: payload })
}

/**
 * 更新宠物档案
 * @param uid 档案 uid
 * @param payload 含 version 的档案字段
 */
export function updatePet(uid: string, payload: any) {
  return request(`/profiles/pets/${uid}`, { method: 'PUT', body: payload })
}

/**
 * 删除宠物档案
 * @param uid 档案 uid
 * @param body {mode, confirm_nickname}
 */
export function deletePet(uid: string, body: { mode: string; confirm_nickname: string }) {
  return request(`/profiles/pets/${uid}`, { method: 'DELETE', body })
}

/**
 * 设为当前问答对象
 * @param body {profile_type: child|pet, profile_uid} 后端按对外 uid 解析档案，不暴露内部主键
 */
export function setCurrentProfile(body: { profile_type: 'child' | 'pet'; profile_uid: string }) {
  return request('/profiles/current', { method: 'POST', body })
}

/* ================= 计费 ================= */

/** 获取当日额度（会员不限次：limit/remaining 为 null 且 unlimited=true） */
export function getQuota() {
  return request<{
    used: number
    limit: number | null
    remaining: number | null
    is_member: boolean
    unlimited?: boolean
  }>('/billing/quota')
}

/**
 * 获取商品信息
 * @param platform 平台标识（web）
 */
export function getProduct(platform = 'web') {
  return request('/billing/product', { query: { platform } })
}

/**
 * 创建订单
 * @param body 商品码/平台/退款告知确认/幂等 id
 */
export function createOrder(body: {
  product_code: string
  platform: string
  contract_confirm: boolean
  client_request_id: string
}) {
  return request('/billing/orders', { method: 'POST', body })
}

/**
 * 模拟支付回调
 * @param orderNo 订单号
 * @param transactionId 交易号
 * @param sign SHA256(transactionId + 'jiaban-pay-mock-sign-key')
 */
export function mockPay(orderNo: string, transactionId: string, sign: string) {
  return request(`/billing/orders/${orderNo}/mock-pay`, {
    method: 'POST',
    body: { transaction_id: transactionId, sign }
  })
}

/** 获取订单列表 */
export function getOrders() {
  return request('/billing/orders')
}

/** 获取订阅状态 */
export function getSubscription() {
  return request('/billing/subscription')
}

/* ================= 问答会话 ================= */

/**
 * 创建问答会话
 * @param body 入口/问题/对象档案/幂等 id
 * @returns {session_uid, status}
 */
export function createQaSession(body: {
  entry: string
  question: string
  profile_uid?: string
  client_request_id: string
}) {
  return request<{ session_uid: string; status: string }>('/qa/sessions', {
    method: 'POST',
    body
  })
}

/**
 * 取消生成
 * @param uid 会话 uid
 * @param cancelToken started 事件下发的取消令牌
 */
export function cancelQaSession(uid: string, cancelToken: string) {
  return request(`/qa/sessions/${uid}/cancel`, {
    method: 'POST',
    body: { cancel_token: cancelToken }
  })
}

/**
 * 获取会话详情（断线重连/回看）
 * @param uid 会话 uid
 */
export function getQaSession(uid: string) {
  return request(`/qa/sessions/${uid}`)
}

/**
 * 重新生成回答
 * @param uid 会话 uid
 */
export function regenerateQa(uid: string) {
  return request(`/qa/sessions/${uid}/regenerate`, { method: 'POST' })
}

/* ================= 风险申诉 ================= */

/**
 * 提交申诉
 * @param body 会话 uid 与申诉说明（≤500 字）
 * @returns {appeal_no, sla_due_at}
 */
export function createAppeal(body: { session_uid: string; appeal_note: string }) {
  return request<{ appeal_no: string; sla_due_at: string }>('/risk/appeals', {
    method: 'POST',
    body
  })
}

/**
 * 查询申诉状态
 * @param appealNo 受理编号（APL-xxx）
 */
export function getAppeal(appealNo: string) {
  return request(`/risk/appeals/${appealNo}`)
}

/* ================= 测评 ================= */

/**
 * 获取测评题目
 * @param ageBand 年龄段（如 1-3y）
 */
export function getAssessmentQuestions(ageBand: string) {
  return request('/assessment/questions', { query: { age_band: ageBand } })
}

/**
 * 开始/继续测评（断点续答）
 * @param profileId 关联孩子档案（可选）
 */
export function startAssessment(profileId?: string) {
  return request('/assessment/start', {
    method: 'POST',
    body: profileId ? { profile_id: profileId } : {}
  })
}

/**
 * 提交单题作答
 * @param uid 测评实例 uid
 * @param qNo 题号
 * @param rawScore 1-5 分（null 清除）
 */
export function putAnswer(uid: string, qNo: number, rawScore: number | null) {
  return request(`/assessment/${uid}/answer`, {
    method: 'PUT',
    body: { q_no: qNo, raw_score: rawScore }
  })
}

/**
 * 提交并计分
 * @param uid 测评实例 uid
 * @param requestId 幂等 id
 */
export function submitAssessment(uid: string, requestId: string) {
  return request(`/assessment/${uid}/submit`, {
    method: 'POST',
    body: { client_request_id: requestId }
  })
}

/**
 * 获取测评报告
 * @param uid 测评实例 uid
 */
export function getAssessmentReport(uid: string) {
  return request(`/assessment/${uid}/report`)
}

/* ================= 历史 ================= */

/**
 * 历史列表（分页）
 * @param type 类型筛选（all/child/pet/qa/report）
 * @param page 页码（从 1 起）
 */
export function getHistory(type = 'all', page = 1) {
  // 后端契约：type 仅接受 all/qa/report，「孩子/宠物」筛选是独立的 profile_type 参数（child/pet）。
  // 若把筛选键直接塞进 type，后端正则校验会返回 422，页面表现为「加载失败」。
  const profileType = type === 'child' || type === 'pet' ? type : undefined
  const query: Record<string, string | number> = { type: profileType ? 'all' : type, page }
  if (profileType) query.profile_type = profileType
  return request('/history', { query })
}

/**
 * 问答详情
 * @param uid 会话 uid
 */
export function getQaHistory(uid: string) {
  return request(`/history/qa/${uid}`)
}

/**
 * 报告详情
 * @param uid 测评 uid
 */
export function getReportHistory(uid: string) {
  return request(`/history/report/${uid}`)
}

/**
 * 报告长图地址
 * @param uid 测评 uid
 */
export function getReportImage(uid: string) {
  return request(`/history/report/${uid}/image`)
}

/* ================= 权利 ================= */

/**
 * 提交权利请求
 * @param body 请求类型与备注
 */
export function createRightsRequest(body: any) {
  return request('/rights/requests', { method: 'POST', body })
}

/** 获取权利请求列表 */
export function getRightsRequests() {
  return request('/rights/requests')
}

/* ================= 反馈与举报 ================= */

/**
 * 提交反馈
 * @param body 内容与可选关联会话
 */
export function submitFeedback(body: { content: string; linked_session_id?: string }) {
  return request('/feedback', { method: 'POST', body })
}

/**
 * 提交举报
 * @param body 对象类型/对象 id/分类/说明
 */
export function submitReport(body: {
  object_type: string
  object_id: string
  category: string
  description?: string
}) {
  return request('/reports', { method: 'POST', body })
}

/* ================= 哈希工具 ================= */

/**
 * 简易 SHA-256（用于 mock-pay 签名）
 * @param message 原文
 * @returns 十六进制哈希串
 */
export async function sha256Hex(message: string): Promise<string> {
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const data = new TextEncoder().encode(message)
    const digest = await crypto.subtle.digest('SHA-256', data)
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
  }
  throw new Error('当前环境不支持 Web Crypto SHA-256')
}

/**
 * 计算 mock-pay 签名
 * @param transactionId 交易号
 * @returns sign = SHA256(transactionId + 密钥后缀)
 */
export async function mockPaySign(transactionId: string): Promise<string> {
  return sha256Hex(transactionId + 'jiaban-pay-mock-sign-key')
}

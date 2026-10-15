/**
 * fetch 请求封装
 * 职责：
 * 1. 统一 Base URL 与 JSON 头；
 * 2. 自动注入 Bearer token；
 * 3. 解析统一响应包络 {code, message, data, request_id, trace_id}，code=0 取 data，非 0 抛 ApiError；
 * 4. 提供 newRequestId() 供写操作幂等（uuid v4 简化实现）。
 */

/** 后端 API 基础地址 */
const BASE_URL = '/api/v1'

/** token 在 localStorage 的键名 */
export const TOKEN_KEY = 'jiaban_access_token'

/**
 * 生成 uuid v4（crypto 随机数实现，兼容非安全上下文回退 Math.random）
 * @returns 36 位 uuid 字符串
 */
export function newRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * 读取当前登录 token
 * @returns token 字符串，未登录返回 null
 */
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * 持久化保存 token
 * @param token 访问令牌
 */
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * 清除 token（登出/换号）
 */
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** 会话失效业务码（后端 1101：会话缺失或已失效） */
const ERR_NO_SESSION = 1101

/**
 * 会话失效全局处理：清凭证 → 整页跳回启动页（带提示位）。
 * 约束：仅在有 token 的请求上触发；/app/start 自身不触发（该页有自己的 1101 重登重试逻辑）。
 * 用整页跳转而非路由跳转：顺带清空内存态，且避免 request → router 循环依赖。
 */
function handleSessionExpired(): void {
  if (typeof window === 'undefined') return
  if (!getToken()) return
  if (window.location.pathname.startsWith('/app/start')) return
  clearToken()
  window.location.assign('/app/start?session=expired')
}

/** API 业务错误：code 为后端业务码，非 0 即失败 */
export class ApiError extends Error {
  /** 后端业务错误码（如 1302/1202/1401 等） */
  code: number
  /** 后端返回的错误消息 */
  message: string

  /**
   * @param code 业务码
   * @param message 错误消息
   */
  constructor(code: number, message: string) {
    super(message)
    this.code = code
    this.message = message
  }
}

/** 请求选项 */
interface RequestOptions {
  /** 请求方法，默认 GET */
  method?: string
  /** 请求体对象（自动 JSON 序列化） */
  body?: unknown
  /** URL 查询参数（自动拼接，值为 undefined 的项跳过） */
  query?: Record<string, string | number | undefined>
  /** 额外请求头 */
  headers?: Record<string, string>
}

/**
 * 统一请求函数
 * @param path 相对 /api/v1 的路径（如 /auth/dev-login）
 * @param options 请求选项
 * @returns 包络中的 data 字段
 * @throws ApiError 业务码非 0；网络失败抛原始 Error
 */
export async function request<T = any>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = 'GET', body, query, headers = {} } = options

  let url = BASE_URL + path
  if (query) {
    const qs = Object.entries(query)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(
        ([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`
      )
      .join('&')
    if (qs) url += `?${qs}`
  }

  const token = getToken()
  const res = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers
    },
    body: body !== undefined ? JSON.stringify(body) : undefined
  })

  let envelope: any
  try {
    envelope = await res.json()
  } catch {
    throw new ApiError(res.status, `HTTP ${res.status}: 响应解析失败`)
  }

  // 兼容未走包络的裸响应
  if (envelope && typeof envelope.code === 'number') {
    if (envelope.code !== 0) {
      if (envelope.code === ERR_NO_SESSION) handleSessionExpired()
      throw new ApiError(envelope.code, envelope.message || '请求失败')
    }
    return envelope.data as T
  }
  return envelope as T
}

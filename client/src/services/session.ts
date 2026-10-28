/**
 * 会话装配模块：登录（含 refresh 兜底）与同意状态读取。
 *
 * 平台差异全部经 platform/runtime 抹平，本模块不直接调用 uni API，
 * 因此小程序与 H5 复用同一套逻辑。
 */
import { api } from '../api'
import { isMiniProgram, runtime } from '../platform/runtime'
import { DEVICE_KEY, createAuthService } from './auth'
import { needsBaseConsent } from './consent'

const TOKEN_KEY = 'jiaban_access_token'
const REFRESH_TOKEN_KEY = 'jiaban_refresh_token'
/** 主动退出登录标记：置位后所有页面不再静默登录，统一回首页登录态 */
const SIGNED_OUT_KEY = 'jiaban_signed_out'
/** 与账号绑定的本地缓存键：退出登录/切换账号时一并清除，避免串号 */
const ACCOUNT_CACHE_KEYS = [
  'jiaban_user_uid',
  'jiaban_member_status',
  'jiaban_current_profile'
]

// 登录模式：小程序端生产构建走微信静默登录（wx.login → /auth/wx-login）；
// 其余情况（含 H5 全部环境）走设备号登录 /auth/dev-login —— H5 无微信登录能力，
// 在接入公众号网页授权前统一以此联调，不新增后端契约。
const auth = createAuthService({
  runtime,
  request: api.request,
  mode: isMiniProgram && !import.meta.env.DEV ? 'production' : 'development'
})

/**
 * 确保具备可用登录态：已有 token 直接返回；否则先尝试 refresh 换取，最后回落正式登录。
 * 并发去重（D-16）：首屏多个页面同时触发时会重复 dev-login，后一次登录会使
 * 前一次 token 失效，导致 consent/status 偶发 401；这里用共享 Promise 合并。
 * @throws Error 登录或刷新均失败时抛出（由调用方决定用户态提示）
 */
let authInFlight: Promise<void> | null = null

async function doAuthenticate(): Promise<void> {
  const token = runtime.getStorageSync(TOKEN_KEY)
  if (token) return
  const refreshToken = runtime.getStorageSync(REFRESH_TOKEN_KEY)
  if (typeof refreshToken === 'string' && refreshToken) {
    try {
      const result = await api.refreshSession(refreshToken)
      runtime.setStorageSync(TOKEN_KEY, result.access_token)
      runtime.setStorageSync(REFRESH_TOKEN_KEY, result.refresh_token)
      return
    } catch {
      // refresh 失效：清理后走完整登录流程
      runtime.removeStorageSync(REFRESH_TOKEN_KEY)
    }
  }
  await auth.login()
}

/**
 * 判断当前是否处于主动退出登录态。
 * @returns true 表示用户已退出，页面不应再触发静默登录
 */
export function isSignedOut(): boolean {
  return runtime.getStorageSync(SIGNED_OUT_KEY) === '1'
}

/**
 * 退出登录 / 切换账号：清理本机登录凭证与账号缓存，并置位退出标记。
 * 服务端数据不受影响；切换账号额外清除设备身份，供开发态/H5 生成新账号。
 * @param options.switchAccount 是否按切换账号处理（清除设备号）
 */
export function signOut(options: { switchAccount?: boolean } = {}): void {
  runtime.removeStorageSync(TOKEN_KEY)
  runtime.removeStorageSync(REFRESH_TOKEN_KEY)
  ACCOUNT_CACHE_KEYS.forEach((key) => runtime.removeStorageSync(key))
  if (options.switchAccount) runtime.removeStorageSync(DEVICE_KEY)
  runtime.setStorageSync(SIGNED_OUT_KEY, '1')
}

/**
 * 退出后手动登录：清除退出标记并按当前平台重新建立登录态。
 * 登录失败时恢复退出标记，避免用户被意外带回自动登录。
 * @throws Error 登录失败时抛出，由页面展示错误提示
 */
export async function loginAfterSignOut(): Promise<void> {
  runtime.removeStorageSync(SIGNED_OUT_KEY)
  try {
    await auth.login()
  } catch (error) {
    runtime.setStorageSync(SIGNED_OUT_KEY, '1')
    throw error
  }
}

async function authenticate(): Promise<void> {
  if (runtime.getStorageSync(TOKEN_KEY)) return
  if (!authInFlight) {
    authInFlight = doAuthenticate().finally(() => {
      authInFlight = null
    })
  }
  await authInFlight
}

/**
 * 读取同意状态：先确保登录态，遇会话失效（1101 或 HTTP 401）时重登并重试一次。
 * @returns 各同意类型的同意情况映射
 * @throws Error 非会话失效类错误原样抛出
 */
export async function loadConsentState() {
  await authenticate()
  try {
    return await api.consentStatus()
  } catch (error: any) {
    if (error?.code !== 1101 && error?.statusCode !== 401) throw error
    runtime.removeStorageSync(TOKEN_KEY)
    await authenticate()
    return await api.consentStatus()
  }
}

/**
 * 确保基础同意已完成。
 * @returns 已完成返回 true，否则 false（调用方据此展示同意引导）
 */
export async function ensureBaseConsent() {
  // 已主动退出：不触发静默登录，交由各页面按 false 回首页登录态
  if (isSignedOut()) return false
  const status = await loadConsentState()
  return !needsBaseConsent(status)
}

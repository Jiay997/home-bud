import { api } from '../api'
import { createAuthService } from './auth'
import { needsBaseConsent } from './consent'

const TOKEN_KEY = 'jiaban_access_token'
const auth = createAuthService({
  runtime: uni,
  request: api.request,
  mode: import.meta.env.DEV ? 'development' : 'production'
})

async function authenticate() {
  const token = uni.getStorageSync(TOKEN_KEY)
  if (token) return
  const refreshToken = uni.getStorageSync('jiaban_refresh_token')
  if (typeof refreshToken === 'string' && refreshToken) {
    try {
      const result = await api.refreshSession(refreshToken)
      uni.setStorageSync(TOKEN_KEY, result.access_token)
      uni.setStorageSync('jiaban_refresh_token', result.refresh_token)
      return
    } catch {
      uni.removeStorageSync('jiaban_refresh_token')
    }
  }
  await auth.login()
}

export async function loadConsentState() {
  await authenticate()
  try {
    return await api.consentStatus()
  } catch (error: any) {
    if (error?.code !== 1101) throw error
    uni.removeStorageSync(TOKEN_KEY)
    await auth.login()
    return await api.consentStatus()
  }
}

export async function ensureBaseConsent() {
  const status = await loadConsentState()
  return !needsBaseConsent(status)
}

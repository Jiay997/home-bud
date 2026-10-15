type LoginResult = {
  access_token: string
  refresh_token?: string
  user_uid: string
  member_status: string
}

type Runtime = {
  getStorageSync?(key: string): unknown
  setStorageSync(key: string, value: unknown): void
  login(options: Record<string, unknown>): unknown
}

type AuthConfig = {
  runtime: Runtime
  request: (path: string, options: { method: string; body: Record<string, string> }) => Promise<LoginResult>
  mode: 'development' | 'production'
  makeDeviceId?: () => string
}

const TOKEN_KEY = 'jiaban_access_token'
const REFRESH_TOKEN_KEY = 'jiaban_refresh_token'
const DEVICE_KEY = 'jiaban_device_id'

function createDeviceId() {
  return `mp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`
}

function getWeChatCode(runtime: Runtime): Promise<string> {
  return new Promise((resolve, reject) => {
    runtime.login({
      provider: 'weixin',
      onlyAuthorize: true,
      success: (result: any) => result?.code ? resolve(result.code) : reject(new Error('微信登录凭证为空')),
      fail: (error: any) => reject(new Error(error?.errMsg || '微信登录失败'))
    })
  })
}

export function createAuthService({ runtime, request, mode, makeDeviceId = createDeviceId }: AuthConfig) {
  return {
    async login() {
      let path = '/auth/wx-login'
      let body: Record<string, string>

      if (mode === 'development') {
        const existing = runtime.getStorageSync?.(DEVICE_KEY)
        const deviceId = typeof existing === 'string' && existing ? existing : makeDeviceId()
        runtime.setStorageSync(DEVICE_KEY, deviceId)
        path = '/auth/dev-login'
        body = { device_id: deviceId }
      } else {
        body = { code: await getWeChatCode(runtime) }
      }

      const result = await request(path, { method: 'POST', body })
      runtime.setStorageSync(TOKEN_KEY, result.access_token)
      if (result.refresh_token) runtime.setStorageSync(REFRESH_TOKEN_KEY, result.refresh_token)
      runtime.setStorageSync('jiaban_user_uid', result.user_uid)
      runtime.setStorageSync('jiaban_member_status', result.member_status)
      return result
    }
  }
}

// dev 专用运行时端点解析：按候选顺序探测 {base}/health，选中首个可达地址。
// 纯逻辑 + 依赖注入，可被 node --test 直接导入；不得访问 import.meta.env（生产短路由接线层负责）。
export interface EndpointRuntime {
  getStorageSync(key: string): unknown
  setStorageSync?(key: string, value: unknown): void
  removeStorageSync?(key: string): void
  getSystemInfoSync?(): { platform?: string }
  request(options: Record<string, unknown>): unknown
}

export type EndpointAttempt = { url: string; ok: boolean; err?: string; ms: number }

export type EndpointResolver = {
  ensure(): Promise<string>
  current(): string
  invalidate(): void
  setOverride(url: string): void
  clearOverride(): void
  attempts(): EndpointAttempt[]
}

type EndpointResolverConfig = {
  runtime: EndpointRuntime
  primary: string
  candidates: string[]
  timeoutMs?: number
  overrideKey?: string
  lastKey?: string
}

export function normalizeBaseUrl(value: unknown): string {
  const trimmed = String(value ?? '').trim().replace(/\/+$/, '')
  if (!trimmed) return ''
  return /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`
}

function loopbackBaseUrl(primary: string): string {
  const match = /^(https?:\/\/)[^/:]+(:\d+)?(\/.*)?$/.exec(primary)
  if (!match) return 'http://127.0.0.1:8000/api/v1'
  return `${match[1]}127.0.0.1${match[2] || ''}${match[3] || ''}`
}

export function createEndpointResolver({
  runtime,
  primary,
  candidates,
  timeoutMs = 1500,
  overrideKey = 'jiaban_debug_api_base',
  lastKey = 'jiaban_last_api_base'
}: EndpointResolverConfig): EndpointResolver {
  const primaryUrl = normalizeBaseUrl(primary) || 'http://127.0.0.1:8000/api/v1'
  const loopbackUrl = loopbackBaseUrl(primaryUrl)
  const fallbackCandidates = (candidates || []).map(normalizeBaseUrl).filter(Boolean)

  let resolved: string | null = null
  let probing: Promise<string> | null = null
  let log: EndpointAttempt[] = []
  let epoch = 0

  function readStorage(key: string): string {
    try {
      return normalizeBaseUrl(runtime.getStorageSync(key))
    } catch {
      return ''
    }
  }

  function writeStorage(key: string, value: string) {
    try {
      runtime.setStorageSync?.(key, value)
    } catch {
      // 本地缓存写入失败不影响本次解析结果
    }
  }

  function removeStorage(key: string) {
    try {
      runtime.removeStorageSync?.(key)
    } catch {
      // 同上
    }
  }

  function isDevtools(): boolean {
    try {
      return String(runtime.getSystemInfoSync?.()?.platform || '') === 'devtools'
    } catch {
      return false
    }
  }

  function candidateOrder(): string[] {
    const override = readStorage(overrideKey)
    if (override) return [override]
    const seen = new Set<string>()
    const order: string[] = []
    const push = (url: string) => {
      if (url && !seen.has(url)) {
        seen.add(url)
        order.push(url)
      }
    }
    if (isDevtools()) push(loopbackUrl)
    push(readStorage(lastKey))
    for (const candidate of fallbackCandidates) push(candidate)
    push(primaryUrl)
    push(loopbackUrl)
    return order
  }

  function probe(url: string): Promise<{ ok: boolean; err?: string; ms: number }> {
    const started = Date.now()
    return new Promise((resolve) => {
      const finish = (ok: boolean, err?: string) => resolve({ ok, err, ms: Date.now() - started })
      try {
        runtime.request({
          url: `${url}/health`,
          method: 'GET',
          timeout: timeoutMs,
          success: (response: any) => {
            const statusCode = Number(response?.statusCode || 0)
            finish(statusCode > 0 && statusCode < 400, statusCode >= 400 ? `HTTP ${statusCode}` : undefined)
          },
          fail: (error: any) => finish(false, String(error?.errMsg || '网络连接失败'))
        })
      } catch (error: any) {
        finish(false, String(error?.message || '请求发起失败'))
      }
    })
  }

  async function probeRound(myEpoch: number): Promise<string> {
    const entries: EndpointAttempt[] = []
    for (const url of candidateOrder()) {
      const result = await probe(url)
      entries.push(result.err ? { url, ok: result.ok, err: result.err, ms: result.ms } : { url, ok: result.ok, ms: result.ms })
      if (result.ok) {
        if (epoch === myEpoch) {
          log = entries
          resolved = url
          writeStorage(lastKey, url)
        }
        return url
      }
    }
    if (epoch === myEpoch) log = entries
    return primaryUrl
  }

  function ensure(): Promise<string> {
    if (resolved) return Promise.resolve(resolved)
    if (probing) return probing
    const myEpoch = epoch
    const round = probeRound(myEpoch)
    probing = round
    return round.then((url) => {
      if (probing === round) probing = null
      if (epoch !== myEpoch) return ensure()
      return url
    })
  }

  function invalidate() {
    epoch += 1
    resolved = null
    probing = null
  }

  return {
    ensure,
    // invalidate 后的重探窗口内，current() 用于同步拼接媒体地址，读上次成功地址比直接回落主地址更稳
    current: () => resolved || readStorage(lastKey) || primaryUrl,
    invalidate,
    setOverride(url: string) {
      const normalized = normalizeBaseUrl(url)
      if (normalized) writeStorage(overrideKey, normalized)
      else removeStorage(overrideKey)
      invalidate()
    },
    clearOverride() {
      removeStorage(overrideKey)
      invalidate()
    },
    attempts: () => log.map((entry) => ({ ...entry }))
  }
}

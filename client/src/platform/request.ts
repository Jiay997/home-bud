export interface MiniRuntime {
  getStorageSync(key: string): unknown
  removeStorageSync?(key: string): void
  request(options: Record<string, unknown>): unknown
}

export interface MiniUploadRuntime extends MiniRuntime {
  uploadFile(options: Record<string, unknown>): unknown
}

export class ApiError extends Error {
  code: number
  statusCode: number

  constructor(code: number, message: string, statusCode = 200) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.statusCode = statusCode
  }
}

type RequestConfig = {
  runtime: MiniRuntime
  baseUrl: string
  tokenKey?: string
  resolveBaseUrl?: () => Promise<string>
  onNetworkFailure?: () => void
}

type RequestOptions = {
  method?: string
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  headers?: Record<string, string>
  timeout?: number
}

export function createRequestClient({
  runtime,
  baseUrl,
  tokenKey = 'jiaban_access_token',
  resolveBaseUrl,
  onNetworkFailure
}: RequestConfig) {
  const staticOrigin = baseUrl.replace(/\/$/, '')

  return function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, query, headers = {}, timeout = 20000 } = options
    const queryString = query
      ? Object.entries(query)
          .filter(([, value]) => value !== undefined && value !== '')
          .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
          .join('&')
      : ''
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    const token = runtime.getStorageSync(tokenKey)

    const originPromise = resolveBaseUrl
      ? resolveBaseUrl().then((value) => String(value || '').replace(/\/$/, '') || staticOrigin)
      : Promise.resolve(staticOrigin)

    return new Promise<T>((resolve, reject) => {
      originPromise.then(
        (origin) => {
          runtime.request({
            url: `${origin}${normalizedPath}${queryString ? `?${queryString}` : ''}`,
            method,
            timeout,
            data: body,
            header: {
              'Content-Type': 'application/json',
              ...(typeof token === 'string' && token ? { Authorization: `Bearer ${token}` } : {}),
              ...headers
            },
            success: (response: any) => {
              const envelope = response?.data
              const statusCode = Number(response?.statusCode || 0)
              if (envelope && typeof envelope.code === 'number') {
                if (envelope.code !== 0) {
                  reject(new ApiError(envelope.code, envelope.message || '请求失败', statusCode))
                  return
                }
                resolve(envelope.data as T)
                return
              }
              if (statusCode >= 400) {
                reject(new ApiError(statusCode, `HTTP ${statusCode}: 请求失败`, statusCode))
                return
              }
              resolve(envelope as T)
            },
            fail: (error: any) => {
              const errMsg = String(error?.errMsg || '')
              if (onNetworkFailure && errMsg.includes('fail')) onNetworkFailure()
              reject(new Error(errMsg || '网络连接失败'))
            }
          })
        },
        (error) => reject(error instanceof Error ? error : new Error('服务地址解析失败'))
      )
    })
  }
}

type UploadConfig = {
  runtime: MiniUploadRuntime
  baseUrl: string
  tokenKey?: string
  resolveBaseUrl?: () => Promise<string>
  onNetworkFailure?: () => void
}

type UploadOptions = {
  method?: 'POST' | 'PUT'
  headers?: Record<string, string>
  formData?: Record<string, string>
  timeout?: number
}

// 上传客户端：uni.uploadFile 单文件 multipart（字段名固定 file）。
// 注意：uploadFile 的 success.data 是 JSON 字符串（并非对象），需先解析再走包络。
export function createUploadClient({
  runtime,
  baseUrl,
  tokenKey = 'jiaban_access_token',
  resolveBaseUrl,
  onNetworkFailure
}: UploadConfig) {
  const staticOrigin = baseUrl.replace(/\/$/, '')

  // filePath：小程序为临时文件路径字符串；H5 为 File/Blob 对象（由 platform/runtime 装配成 FormData）
  return function upload<T = unknown>(
    path: string,
    filePath: string | Blob,
    options: UploadOptions = {}
  ): Promise<T> {
    const { method = 'POST', headers = {}, formData = {}, timeout = 60000 } = options
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    const token = runtime.getStorageSync(tokenKey)

    const originPromise = resolveBaseUrl
      ? resolveBaseUrl().then((value) => String(value || '').replace(/\/$/, '') || staticOrigin)
      : Promise.resolve(staticOrigin)

    return new Promise<T>((resolve, reject) => {
      originPromise.then(
        (origin) => {
          runtime.uploadFile({
            url: `${origin}${normalizedPath}`,
            filePath,
            name: 'file',
            method,
            timeout,
            formData,
            header: {
              ...(typeof token === 'string' && token ? { Authorization: `Bearer ${token}` } : {}),
              ...headers
            },
            success: (response: any) => {
              const statusCode = Number(response?.statusCode || 0)
              let envelope = response?.data
              if (typeof envelope === 'string') {
                try {
                  envelope = JSON.parse(envelope)
                } catch {
                  envelope = null
                }
              }
              if (envelope && typeof envelope.code === 'number') {
                if (envelope.code !== 0) {
                  reject(new ApiError(envelope.code, envelope.message || '上传失败', statusCode))
                  return
                }
                resolve(envelope.data as T)
                return
              }
              if (statusCode >= 400) {
                reject(new ApiError(statusCode, `HTTP ${statusCode}: 上传失败`, statusCode))
                return
              }
              resolve(envelope as T)
            },
            fail: (error: any) => {
              const errMsg = String(error?.errMsg || '')
              if (onNetworkFailure && errMsg.includes('fail')) onNetworkFailure()
              reject(new Error(errMsg || '网络连接失败'))
            }
          })
        },
        (error) => reject(error instanceof Error ? error : new Error('服务地址解析失败'))
      )
    })
  }
}

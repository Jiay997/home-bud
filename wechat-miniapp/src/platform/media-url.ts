// 媒体相对路径 → 绝对地址：后端 /media 静态挂载与 API 同源，origin 由 API base 去掉 /api/v1 后缀得到。
// 已是绝对地址的入参原样返回（兼容后续切 OSS/签名 URL 的形态）；空值返回空串（组件按未设置兜底展示）。
export function resolveMediaUrl(origin: string, path?: string | null): string {
  const value = String(path || '').trim()
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  const base = String(origin || '').replace(/\/+$/, '').replace(/\/api\/v1$/i, '')
  return `${base}${value.startsWith('/') ? '' : '/'}${value}`
}

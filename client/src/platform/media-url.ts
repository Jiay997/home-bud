// 媒体相对路径 → 绝对地址：后端 /media 静态挂载与 API 同源，origin 由 API base 去掉 /api/v1 后缀得到。
// 已是绝对地址的入参原样返回（兼容后续切 OSS/签名 URL 的形态）；空值返回空串（组件按未设置兜底展示）。
export function resolveMediaUrl(origin: string, path?: string | null): string {
  const value = String(path || '').trim()
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  const rawOrigin = String(origin || '').trim()
  const normalized = rawOrigin.replace(/\/+$/, '').replace(/\/api\/v1$/i, '')
  // H5 下 API base 是根相对路径（/api/v1）。uni-app 的 <image> 会把根相对 src
  // 再拼上 H5 base（/app/），导致 /app/media/... 404；这里直接补全为同源绝对地址。
  // 注意判断必须用 rawOrigin：'/api/v1' 去掉后缀后是空串，不能再用 normalized 判断。
  const originPrefix =
    rawOrigin.startsWith('/') && typeof window !== 'undefined' && window.location
      ? window.location.origin
      : ''
  const base = `${originPrefix}${normalized}`
  return `${base}${value.startsWith('/') ? '' : '/'}${value}`
}

// 媒体图片「自愈」下载器：真机（iOS ATS 等）直连 http 图片失败时，
// 改经 downloadFile 拉到本地临时文件再渲染——该通道与 request/uploadFile 相同，
// 被真机调试的「不校验合法域名」覆盖（2026-10-14 真机实测：上传/请求可用而 <image> 直连空白）。
// 纯逻辑 + 依赖注入，可被 node --test 直接导入。
export interface MediaImageRuntime {
  downloadFile(options: Record<string, unknown>): void
}

export interface MediaImageLoader {
  cached(url: string): string
  resolve(url: string): Promise<string>
  preferLocal(url: string): Promise<string>
}

export function isRemoteUrl(url: string): boolean {
  return /^https?:\/\//i.test(String(url || ''))
}

export function createMediaImageLoader({ runtime }: { runtime: MediaImageRuntime }): MediaImageLoader {
  const cache = new Map<string, string>()
  const inflight = new Map<string, Promise<string>>()

  function cached(url: string): string {
    return cache.get(String(url || '')) || ''
  }

  function resolve(url: string): Promise<string> {
    const value = String(url || '')
    if (!value) return Promise.reject(new Error('图片地址为空'))
    const hit = cache.get(value)
    if (hit) return Promise.resolve(hit)
    const pending = inflight.get(value)
    if (pending) return pending

    const task = new Promise<string>((resolvePromise, rejectPromise) => {
      const fail = (message: string) => rejectPromise(new Error(message))
      try {
        runtime.downloadFile({
          url: value,
          timeout: 30000,
          success: (response: any) => {
            const statusCode = Number(response?.statusCode || 0)
            const path = String(response?.tempFilePath || '')
            if (!path) fail('图片下载失败：未取得本地文件')
            else if (statusCode < 200 || statusCode >= 400) fail(`图片下载失败：HTTP ${statusCode}`)
            else {
              cache.set(value, path)
              resolvePromise(path)
            }
          },
          fail: (error: any) => fail(String(error?.errMsg || '图片下载失败：网络异常'))
        })
      } catch (error: any) {
        fail(String(error?.message || '图片下载发起失败'))
      }
    })

    inflight.set(value, task)
    void task.catch(() => undefined).then(() => {
      if (inflight.get(value) === task) inflight.delete(value)
    })
    return task
  }

  // 预览等场景：能本地化就本地化，失败退回原地址（尽力而为，不抛错）
  function preferLocal(url: string): Promise<string> {
    const value = String(url || '')
    if (!value || !isRemoteUrl(value)) return Promise.resolve(value)
    return resolve(value).catch(() => value)
  }

  return { cached, resolve, preferLocal }
}

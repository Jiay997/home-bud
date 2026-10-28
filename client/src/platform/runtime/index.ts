/**
 * 平台运行时适配层（uni-app 跨端：微信小程序 + H5）。
 *
 * 设计意图：
 * - 上层模块（platform/request.ts、platform/endpoint.ts、services/*）一律通过「注入 runtime」
 *   的方式使用平台能力；本模块负责按编译目标提供同一组接口的实现，上层无需感知平台差异；
 * - 微信小程序端逐项转发 uni 对象（uni API 即小程序原生 API 的转义），行为与改造前完全一致；
 * - H5 端复用 uni-h5 runtime 已有的 request/storage/提示能力，仅自实现 uni 在 H5 缺失或语义
 *   不同的四类能力：uploadFile（File/Blob → FormData）、downloadFile（浏览器无本地临时文件概念）、
 *   chooseMedia（input[type=file]）、login（H5 无微信登录，由 auth 走设备号登录路径）。
 *
 * 条件编译说明：`// #ifdef` 指令在编译期按目标平台剔除失效分支，因此 H5 实现不会进入小程序产物。
 */

/** 平台文件引用：小程序为临时文件路径字符串；H5 为浏览器 File/Blob 对象 */
export type PlatformFileRef = string | Blob

/** 平台 runtime 接口：为各注入式模块所需的平台能力并集（可选能力以 ? 标注） */
export interface PlatformRuntime {
  /**
   * 读取本地存储。
   * @param key 存储键
   * @returns 存储值；键不存在时返回空字符串（与 uni.getStorageSync 语义一致）
   */
  getStorageSync(key: string): unknown

  /**
   * 写入本地存储（支持任意可序列化值）。
   * @param key 存储键
   * @param value 存储值
   */
  setStorageSync(key: string, value: unknown): void

  /**
   * 删除本地存储键。
   * @param key 存储键
   */
  removeStorageSync(key: string): void

  /**
   * 发起网络请求（回调式，签名与 uni.request 一致）。
   * @param options uni.request 形式的参数对象
   * @returns 请求任务对象（部分平台可 abort）
   */
  request(options: Record<string, unknown>): unknown

  /**
   * 上传文件（multipart，字段名固定 file）。
   * @param options uni.uploadFile 形式的参数对象
   */
  uploadFile(options: Record<string, unknown>): unknown

  /**
   * 下载文件到本地。
   * @param options uni.downloadFile 形式的参数对象
   */
  downloadFile(options: Record<string, unknown>): void

  /**
   * 读取系统信息（platform 用于区分运行环境）。
   * @returns 含 platform / pixelRatio / SDKVersion 的系统信息
   */
  getSystemInfoSync(): { platform?: string; pixelRatio?: number; SDKVersion?: string }

  /**
   * 显示加载提示。
   * @param options 提示标题与是否遮罩
   */
  showLoading(options: { title: string; mask?: boolean }): void

  /** 关闭加载提示。 */
  hideLoading(): void

  /**
   * 显示轻提示。
   * @param options 提示标题、图标类型与时长
   */
  showToast(options: { title: string; icon?: string; duration?: number }): void

  /**
   * 选择媒体文件（图片）。
   * @param options uni.chooseMedia 形式的参数对象（含 count/success/fail）
   */
  chooseMedia(options: Record<string, unknown>): void

  /**
   * 获取登录凭证（仅微信小程序提供，H5 无该能力）。
   * @param options uni.login 形式的参数对象
   */
  login?(options: Record<string, unknown>): unknown
}

/**
 * 判定当前编译目标是否为微信小程序。
 * 条件编译保证编译后只保留一个分支；非 uni 编译环境（如 node 单测）下首分支生效，
 * 但本模块不参与纯逻辑单测，故无实际影响。
 * @returns 微信小程序目标返回 true，其余返回 false
 */
function detectMiniProgram(): boolean {
  // #ifdef MP-WEIXIN
  return true
  // #endif
  // #ifndef MP-WEIXIN
  return false
  // #endif
}

/** 当前编译目标是否为微信小程序 */
export const isMiniProgram = detectMiniProgram()

// #ifdef H5
/**
 * H5 端文件上传：把 File/Blob 装入 FormData 后以 fetch 提交。
 * @param options uni.uploadFile 形式的参数对象（url/filePath/name/formData/header/success/fail）
 */
function h5UploadFile(options: Record<string, unknown>): void {
  const { url, filePath, name = 'file', formData = {}, header = {}, success, fail } =
    options as {
      url?: string
      filePath?: PlatformFileRef
      name?: string
      formData?: Record<string, unknown>
      header?: Record<string, string>
      success?: (response: { statusCode: number; data: string }) => void
      fail?: (error: { errMsg: string }) => void
    }

  if (!(filePath instanceof Blob)) {
    fail?.({ errMsg: 'uploadFile:fail H5 端 filePath 需为 File/Blob 对象' })
    return
  }

  const form = new FormData()
  // 文件名用于服务端识别扩展名（File 有 name，裸 Blob 退化为通用名）
  form.append(String(name), filePath, (filePath as File).name || 'upload.bin')
  for (const [key, value] of Object.entries(formData)) form.append(key, String(value))

  fetch(String(url), {
    method: 'POST',
    headers: header,
    body: form
  })
    .then(async (response) => {
      // 与 uni.uploadFile 一致：data 为 JSON 字符串，交由 createUploadClient 解析包络
      success?.({ statusCode: response.status, data: await response.text() })
    })
    .catch((error: unknown) => {
      fail?.({ errMsg: `uploadFile:fail ${(error as Error)?.message || ''}` })
    })
}

/**
 * H5 端下载文件：浏览器可直接渲染远程图片，无「本地临时文件」概念，
 * 等价返回原地址，使 media-image 的自愈链路在 H5 退化为直连展示。
 * @param options uni.downloadFile 形式的参数对象（url/success）
 */
function h5DownloadFile(options: Record<string, unknown>): void {
  const { url, success } = options as {
    url?: string
    success?: (response: { statusCode: number; tempFilePath: string }) => void
  }
  success?.({ statusCode: 200, tempFilePath: String(url || '') })
}

/**
 * H5 端媒体选择：以 input[type=file] 替代 uni.chooseMedia（H5 未实现该 API）。
 * 取消时返回 errMsg 含 cancel，与 uni 取消语义对齐（上层按取消而非失败处理）。
 * @param options uni.chooseMedia 形式的参数对象（count/success/fail）
 */
function h5ChooseMedia(options: Record<string, unknown>): void {
  const { count = 1, success, fail } = options as {
    count?: number
    success?: (result: { tempFiles: Array<{ tempFilePath: File; size: number }> }) => void
    fail?: (error: { errMsg: string }) => void
  }
  const limit = Math.max(1, Number(count) || 1)
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  if (limit > 1) input.multiple = true

  input.onchange = () => {
    const picked = Array.from(input.files || []).slice(0, limit)
    if (!picked.length) {
      fail?.({ errMsg: 'chooseMedia:fail cancel' })
      return
    }
    success?.({
      tempFiles: picked.map((file) => ({ tempFilePath: file, size: file.size }))
    })
  }

  input.click()
}
// #endif

/**
 * 按编译目标选择 runtime 实现。
 * 小程序端逐项转发 uni（惰性调用，避免模块加载期即访问全局对象）。
 * @returns 当前平台可用的 PlatformRuntime 实例
 */
function selectRuntime(): PlatformRuntime {
  // #ifdef MP-WEIXIN
  return {
    getStorageSync: (key: string) => uni.getStorageSync(key),
    setStorageSync: (key: string, value: unknown) => uni.setStorageSync(key, value),
    removeStorageSync: (key: string) => uni.removeStorageSync(key),
    request: (options: Record<string, unknown>) => uni.request(options as any),
    uploadFile: (options: Record<string, unknown>) => uni.uploadFile(options as any),
    downloadFile: (options: Record<string, unknown>) => uni.downloadFile(options as any),
    getSystemInfoSync: () => uni.getSystemInfoSync(),
    login: (options: Record<string, unknown>) => uni.login(options as any),
    chooseMedia: (options: Record<string, unknown>) => uni.chooseMedia(options as any),
    showLoading: (options: { title: string; mask?: boolean }) => uni.showLoading(options),
    hideLoading: () => uni.hideLoading(),
    showToast: (options: { title: string; icon?: string; duration?: number }) =>
      uni.showToast(options as any)
  }
  // #endif
  // #ifndef MP-WEIXIN
  return {
    getStorageSync: (key: string) => uni.getStorageSync(key),
    setStorageSync: (key: string, value: unknown) => uni.setStorageSync(key, value),
    removeStorageSync: (key: string) => uni.removeStorageSync(key),
    request: (options: Record<string, unknown>) => {
      // uni-h5 的 request 在个别响应类型下可能回传未解析的字符串，此处统一为对象后再交给上层
      const originalSuccess = (options as { success?: (response: any) => void }).success
      return uni.request({
        ...options,
        success: (response: any) => {
          let data = response?.data
          if (typeof data === 'string') {
            try {
              data = JSON.parse(data)
            } catch {
              // 非 JSON 响应保留原文字，交由上层按 HTTP 状态判定
            }
          }
          originalSuccess?.({ ...response, data })
        }
      } as any)
    },
    uploadFile: h5UploadFile,
    downloadFile: h5DownloadFile,
    getSystemInfoSync: () => uni.getSystemInfoSync() as { platform?: string; pixelRatio?: number },
    chooseMedia: h5ChooseMedia,
    showLoading: (options: { title: string; mask?: boolean }) => uni.showLoading(options),
    hideLoading: () => uni.hideLoading(),
    showToast: (options: { title: string; icon?: string; duration?: number }) =>
      uni.showToast(options as any)
  }
  // #endif
}

/** 全局唯一的平台 runtime 实例，供 api 层与各注入点使用 */
export const runtime: PlatformRuntime = selectRuntime()

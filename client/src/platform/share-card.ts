/**
 * 分享长图保存的平台适配层（RQ-09 + RQ-01 三链路标识）。
 *
 * 与 `platform/long-image.ts` 的区别：长图**由服务端渲染**（模板 + 显式双标识 +
 * PNG `tEXt` 隐式标识，缺项即渲染失败），客户端只负责取 PNG 并落盘，不在本地
 * 拼装正文，因此不存在「客户端导出无标识版本」的口子。
 *
 * 两端差异：
 * - H5：`fetch` 带鉴权取 `blob` → `<a download>` 触发浏览器下载；
 * - 小程序：`uni.downloadFile` 落到临时文件 → `uni.saveImageToPhotosAlbum` 存入相册。
 *
 * 403（code 1102）表示会话不可分享（被拦截 / 未完成），既不重试也不降级导出。
 */
import { userFacingMessage } from '../services/user-message.ts'

/** 保存结果：saved=已保存；denied=不可分享或相册权限被拒；failed=其他失败 */
export type ShareCardOutcome = 'saved' | 'denied' | 'failed'

export interface ShareCardOptions {
  /** 服务端长图地址（含 /api/v1 前缀的绝对地址） */
  url: string
  /** 访问令牌（小程序自行拼 header；H5 走 fetch 头） */
  token?: string
  /** 下载文件名（H5 生效，扩展名由调用方保证） */
  fileName?: string
}

/** 403 / 1102：会话不可分享 */
const DENIED_STATUS = 403

// #ifdef MP-WEIXIN
/**
 * 小程序端：下载 PNG 并存入系统相册。
 * @param options 保存参数
 * @returns 保存结果
 */
function mpSave(options: ShareCardOptions): Promise<ShareCardOutcome> {
  return new Promise((resolve) => {
    uni.downloadFile({
      url: options.url,
      header: options.token ? { Authorization: `Bearer ${options.token}` } : {},
      success: (response: any) => {
        const statusCode = Number(response?.statusCode || 0)
        if (statusCode === DENIED_STATUS) {
          resolve('denied')
          return
        }
        if (statusCode !== 200 || !response?.tempFilePath) {
          resolve('failed')
          return
        }
        uni.saveImageToPhotosAlbum({
          filePath: String(response.tempFilePath),
          success: () => resolve('saved'),
          fail: (error: any) => {
            const message = String(error?.errMsg || '')
            if (/auth|deny|authorize/i.test(message)) resolve('denied')
            else resolve('failed')
          }
        } as any)
      },
      fail: () => resolve('failed')
    } as any)
  })
}
// #endif

// #ifdef H5
/**
 * H5 端：鉴权取 PNG blob 并触发浏览器下载。
 * @param options 保存参数
 * @returns 保存结果
 */
async function h5Save(options: ShareCardOptions): Promise<ShareCardOutcome> {
  try {
    const response = await fetch(options.url, {
      method: 'GET',
      headers: options.token ? { Authorization: `Bearer ${options.token}` } : {}
    })
    if (response.status === DENIED_STATUS) return 'denied'
    if (!response.ok) return 'failed'
    const blob = await response.blob()
    if (!blob || blob.size === 0) return 'failed'
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = options.fileName || 'babe-share.png'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    // 释放 blob URL，避免长会话下内存堆积
    setTimeout(() => URL.revokeObjectURL(objectUrl), 2000)
    return 'saved'
  } catch {
    return 'failed'
  }
}
// #endif

/**
 * 保存服务端分享长图（按编译目标自动选择实现）。
 * @param options 保存参数
 * @returns 保存结果（由调用方转用户提示）
 */
export function saveShareCardImage(options: ShareCardOptions): Promise<ShareCardOutcome> {
  // #ifdef MP-WEIXIN
  return mpSave(options)
  // #endif
  // #ifndef MP-WEIXIN
  return h5Save(options)
  // #endif
}

/** 分享长图相关用户提示文案（含拉丁字母的文案不得进模板） */
export const shareCardCopy = {
  saved: '长图已保存',
  denied: '本次回答不可生成长图（被拦截或未完成）',
  failed: '长图生成失败，请稍后重试',
  busy: '正在生成长图…'
}

/**
 * 把保存结果转为可直接展示的提示文案。
 * @param outcome 保存结果
 * @param error 异常对象（failed 时用于取服务端说明）
 * @returns 提示文案
 */
export function shareCardMessage(outcome: ShareCardOutcome, error?: unknown): string {
  if (outcome === 'saved') return shareCardCopy.saved
  if (outcome === 'denied') return shareCardCopy.denied
  return userFacingMessage(error, shareCardCopy.failed)
}

/**
 * 分块流式请求适配层（uni-app 跨端：微信小程序 + H5）。
 *
 * 背景：AI 问答的 SSE 流式输出需要「边收边渲染」，但两端可达能力不同——
 * 微信小程序依赖 `wx.request` 的 `enableChunked` 分块接收（基础库 ≥ 2.20.2）；
 * H5 侧改用 `fetch` + `ReadableStream` 逐块读取。
 * 两者对上层暴露同一个 `ChunkedRequest` 契约，因此 services/qa-stream.ts 的
 * SSE 解析与状态机完全复用，无需改动。
 */
import type { ChunkedRequest, ChunkedRequestOptions } from '../services/qa-stream'

/** 微信小程序支持 enableChunked 分块接收的最低基础库版本 */
const CHUNKED_MIN_SDK_VERSION = '2.20.2'

/**
 * 比较两个版本号字符串。
 * @param left 左侧版本号，形如 3.17.4
 * @param right 右侧版本号，形如 2.20.2
 * @returns 左大返回 1，相等返回 0，左小返回 -1
 */
function compareVersion(left: string, right: string): number {
  const leftParts = left.split('.').map((part) => parseInt(part, 10) || 0)
  const rightParts = right.split('.').map((part) => parseInt(part, 10) || 0)
  const length = Math.max(leftParts.length, rightParts.length)
  for (let index = 0; index < length; index += 1) {
    const a = leftParts[index] || 0
    const b = rightParts[index] || 0
    if (a !== b) return a > b ? 1 : -1
  }
  return 0
}

// #ifdef MP-WEIXIN
/**
 * 判断微信小程序当前基础库是否支持分块接收（不支持时页面回落到轮询式生成）。
 * @returns 支持返回 true
 */
function miniProgramChunkedSupported(): boolean {
  try {
    const wxApi = (globalThis as { wx?: any }).wx
    if (!wxApi || typeof wxApi.request !== 'function') return false
    const info = typeof wxApi.getAppBaseInfo === 'function' ? wxApi.getAppBaseInfo() : wxApi.getSystemInfoSync?.()
    return compareVersion(String(info?.SDKVersion || ''), CHUNKED_MIN_SDK_VERSION) >= 0
  } catch {
    return false
  }
}

/**
 * 微信小程序分块请求实现：委托 wx.request 的 enableChunked + onChunkReceived。
 * @returns ChunkedRequest 实现
 */
function createMiniProgramChunkedRequest(): ChunkedRequest {
  return (options: ChunkedRequestOptions) => {
    const wxApi = (globalThis as { wx?: any }).wx
    if (!wxApi || typeof wxApi.request !== 'function') {
      options.handlers.onFail('当前环境不支持流式传输')
      return { abort: () => undefined }
    }
    const task = wxApi.request({
      url: options.url,
      method: options.method,
      header: options.header,
      timeout: options.timeout,
      enableChunked: true,
      responseType: 'arraybuffer',
      success: (response: any) => {
        options.handlers.onComplete({ statusCode: Number(response?.statusCode || 0), body: '' })
      },
      fail: (error: any) => {
        options.handlers.onFail(error?.errMsg || '网络连接失败')
      }
    })
    if (task && typeof task.onChunkReceived === 'function') {
      task.onChunkReceived((response: any) => {
        options.handlers.onChunk(response.data)
      })
    }
    return { abort: () => task?.abort?.() }
  }
}
// #endif

// #ifdef H5
/**
 * H5 分块请求实现：fetch + ReadableStream 逐块读取。
 * 语义与小程序实现对齐：非 2xx 走 onComplete（携带响应体供上层提取错误文案），
 * 主动 abort 不计为失败（页面卸载/重试场景），其余异常走 onFail。
 * @returns ChunkedRequest 实现
 */
function createH5ChunkedRequest(): ChunkedRequest {
  return (options: ChunkedRequestOptions) => {
    const controller = new AbortController()
    let settled = false

    /**
     * 结束请求（幂等：完成与失败二者只允许其一先到达）。
     * @param statusCode HTTP 状态码
     * @param body 响应体原文（错误分支用于提取业务文案）
     */
    const complete = (statusCode: number, body = '') => {
      if (settled) return
      settled = true
      options.handlers.onComplete({ statusCode, body })
    }

    fetch(options.url, {
      method: options.method,
      headers: options.header,
      signal: controller.signal
    })
      .then(async (response) => {
        if (response.status >= 400) {
          let body = ''
          try {
            body = await response.text()
          } catch {
            // 响应体读取失败不影响状态判定
          }
          complete(response.status, body)
          return
        }
        const reader = response.body?.getReader()
        if (!reader) {
          complete(response.status)
          return
        }
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          if (value && value.byteLength) {
            // 传入精确切片：避免多字节字符跨块续接时受 buffer 尾部的冗余字节干扰
            options.handlers.onChunk(
              value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength)
            )
          }
        }
        complete(response.status)
      })
      .catch((error: unknown) => {
        if (settled) return
        settled = true
        if ((error as Error)?.name === 'AbortError') return
        options.handlers.onFail((error as Error)?.message || '网络连接失败')
      })

    return { abort: () => controller.abort() }
  }
}
// #endif

/**
 * 按编译目标选择分块请求实现。
 * @returns 当前平台的 ChunkedRequest 实现
 */
function pickChunkedRequest(): ChunkedRequest {
  // #ifdef MP-WEIXIN
  return createMiniProgramChunkedRequest()
  // #endif
  // #ifndef MP-WEIXIN
  return createH5ChunkedRequest()
  // #endif
}

/**
 * 当前环境是否具备分块流式能力。
 * 小程序按基础库版本判定（不支持时页面回落轮询）；H5 按 fetch + ReadableStream 可用性判定。
 * @returns 支持返回 true
 */
export function chunkedSupported(): boolean {
  // #ifdef MP-WEIXIN
  return miniProgramChunkedSupported()
  // #endif
  // #ifndef MP-WEIXIN
  return typeof fetch === 'function' && typeof ReadableStream !== 'undefined'
  // #endif
}

/** 全局唯一的分块请求实现，交由页面注入 createQaStreamService 使用 */
export const chunkedRequest: ChunkedRequest = pickChunkedRequest()

/**
 * SSE（Server-Sent Events）流式解析器
 * 职责：读取 ReadableStream，按 `event: X\ndata: {json}\n\n` 帧切分，
 * 逐帧回调 onEvent(eventName, dataJson)。
 */

/**
 * 逐帧解析 SSE 流
 * @param reader fetch body 的 ReadableStream reader
 * @param onEvent 每解析出一帧的回调（事件名、原始 data 字符串）
 * @throws 流读取中断时抛出原始错误
 */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (event: string, data: string) => void
): Promise<void> {
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // 帧以空行（\n\n）分隔
    let sepIdx: number
    while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, sepIdx)
      buffer = buffer.slice(sepIdx + 2)
      let eventName = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          // 多行 data 以 \n 连接（本契约均为单行 JSON，兼容处理）
          data += (data ? '\n' : '') + line.slice(5).trim()
        }
      }
      if (data || eventName !== 'message') {
        onEvent(eventName, data)
      }
    }
  }
}

/** QA 流式事件处理器集合（可选订阅） */
export interface QaStreamHandlers {
  /** started：开始生成，含 render_order 与 cancel_token */
  onStarted?: (data: { render_order: string[]; cancel_token: string }) => void
  /** section_delta：分节增量文本 */
  onSectionDelta?: (data: {
    section_key: string
    title?: string
    delta: string
  }) => void
  /** section_done：分节完成，替换为完整 blocks */
  onSectionDone?: (data: {
    section_key: string
    title?: string
    blocks: any[]
    status: string
    /** 分节是否置顶（缓存回放帧携带，正常流可能缺省） */
    pinned?: boolean
    /** 分节是否不可变（缓存回放帧携带，正常流可能缺省） */
    immutable?: boolean
    /** 是否缓存回放帧：回放流只发 started→section_done×N→completed，无 section_delta */
    cached?: boolean
  }) => void
  /** blocked：风险拦截（调用方必须清空全部已渲染正文） */
  onBlocked?: (data: any) => void
  /** degraded：部分分节失败 */
  onDegraded?: (data: { failed_sections: string[] }) => void
  /** completed：整体完成 */
  onCompleted?: (data: any) => void
  /** error：流错误 */
  onError?: (data: any) => void
}

/**
 * 启动 QA 流式会话消费
 * @param sessionUid 会话 uid
 * @param handlers 事件处理器集合
 * @throws 网络失败 / HTTP 非 2xx 时抛出 Error
 */
export async function startQaStream(
  sessionUid: string,
  handlers: QaStreamHandlers
): Promise<void> {
  const { getToken } = await import('./request')
  const token = getToken()
  const res = await fetch(
    `/api/v1/qa/sessions/${sessionUid}/stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    }
  )
  if (!res.ok || !res.body) {
    throw new Error(`SSE 连接失败：HTTP ${res.status}`)
  }
  const reader = res.body.getReader()
  await parseSSEStream(reader, (event, data) => {
    let payload: any = {}
    try {
      payload = data ? JSON.parse(data) : {}
    } catch {
      payload = { raw: data }
    }
    switch (event) {
      case 'started':
        handlers.onStarted?.(payload)
        break
      case 'section_delta':
        handlers.onSectionDelta?.(payload)
        break
      case 'section_done':
        handlers.onSectionDone?.(payload)
        break
      case 'blocked':
        handlers.onBlocked?.(payload)
        break
      case 'degraded':
        handlers.onDegraded?.(payload)
        break
      case 'completed':
        handlers.onCompleted?.(payload)
        break
      case 'error':
        handlers.onError?.(payload)
        break
      default:
        // ping 等心跳事件忽略
        break
    }
  })
}

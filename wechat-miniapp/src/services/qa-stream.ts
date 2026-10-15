import { createSseParser, decodeUtf8Chunk, type SseFrame } from './sse.ts'

export type QaStreamPhase = 'waiting' | 'checking' | 'streaming' | 'done' | 'blocked' | 'failed'

export interface QaStreamBlock {
  block_key?: string
  title?: string
  content?: string
  summary?: string
  is_member_content?: boolean
  access_tier?: string
  immutable?: boolean
  partial?: boolean
}

export interface QaStreamSection {
  section_key: string
  title: string
  blocks: QaStreamBlock[]
  done: boolean
  cached?: boolean
  pinned?: boolean
  immutable?: boolean
  // 历史详情（GET /history/qa）为分节级门控：access_tier=block 时整节无 blocks
  access_tier?: string
}

export interface QaBlockedInfo {
  reason: string
  channels: unknown[]
  appealAllowed: boolean
}

export interface QaStreamState {
  phase: QaStreamPhase
  sessionUid: string
  renderOrder: string[]
  riskLevel: string
  degradedReason: string | null
  conflictNote: string | null
  sections: QaStreamSection[]
  quota: { used: number; limit: number | null } | null
  blocked: QaBlockedInfo | null
  errorMessage: string
}

export function createQaStreamState(): QaStreamState {
  return {
    phase: 'waiting',
    sessionUid: '',
    renderOrder: [],
    riskLevel: '',
    degradedReason: null,
    conflictNote: null,
    sections: [],
    quota: null,
    blocked: null,
    errorMessage: ''
  }
}

// 非会员不得提前看到会员块正文：delta 帧不过滤 access_tier，客户端仅对恒免费的安全节
// 渐进渲染，其余分节等 section_done 下发门控裁剪后的权威内容。
export function canRenderStreamContent(sectionKey: string, isMember: boolean) {
  return isMember || sectionKey === 'safety'
}

function parseData(raw: string): Record<string, any> | null {
  try {
    const value = JSON.parse(raw)
    return value && typeof value === 'object' ? value : null
  } catch {
    return null
  }
}

function findSection(sections: QaStreamSection[], sectionKey: string) {
  return sections.find((section) => section.section_key === sectionKey)
}

export function applyQaStreamEvent(state: QaStreamState, frame: SseFrame): QaStreamState {
  const data = parseData(frame.data)
  if (!data) return state

  if (frame.event === 'started') {
    const renderOrder: string[] = Array.isArray(data.render_order) ? data.render_order : []
    return {
      ...state,
      phase: 'checking',
      sessionUid: String(data.session_uid || state.sessionUid),
      renderOrder,
      sections: renderOrder.map((key) => ({
        section_key: key,
        title: '',
        blocks: [],
        done: false
      }))
    }
  }

  if (frame.event === 'section_delta') {
    const sectionKey = String(data.section_key || '')
    if (!sectionKey) return state
    const sections = [...state.sections]
    let section = findSection(sections, sectionKey)
    if (!section) {
      section = { section_key: sectionKey, title: '', blocks: [], done: false }
      sections.push(section)
    }
    if (data.stage === 'skeleton') {
      const blockTitles: unknown[] = Array.isArray(data.block_titles) ? data.block_titles : []
      const next: QaStreamSection = {
        ...section,
        title: String(data.title || section.title || ''),
        blocks: blockTitles.map((title) => ({ title: String(title || ''), content: '', partial: true }))
      }
      return { ...state, phase: 'streaming', sections: sections.map((item) => item.section_key === sectionKey ? next : item) }
    }
    if (data.stage === 'content') {
      const blockKey = String(data.block_key || '')
      const delta = String(data.delta || '')
      const blocks = section.done
        ? section.blocks.map((block) => block.block_key === blockKey ? { ...block, content: (block.content || '') + delta } : block)
        : appendPartialContent(section.blocks, blockKey, delta)
      const next: QaStreamSection = { ...section, blocks }
      return { ...state, phase: 'streaming', sections: sections.map((item) => item.section_key === sectionKey ? next : item) }
    }
    return { ...state, phase: 'streaming', sections }
  }

  if (frame.event === 'section_done') {
    const sectionKey = String(data.section_key || '')
    if (!sectionKey) return state
    const blocks: QaStreamBlock[] = Array.isArray(data.blocks)
      ? data.blocks.map((block: Record<string, any>) => ({ ...block }))
      : []
    const section: QaStreamSection = {
      section_key: sectionKey,
      title: String(data.title || ''),
      blocks,
      done: true,
      cached: data.cached === true,
      pinned: data.pinned === true,
      immutable: data.immutable === true
    }
    const exists = state.sections.some((item) => item.section_key === sectionKey)
    return {
      ...state,
      phase: state.phase === 'done' || state.phase === 'blocked' ? state.phase : 'streaming',
      sections: exists
        ? state.sections.map((item) => item.section_key === sectionKey ? section : item)
        : [...state.sections, section]
    }
  }

  if (frame.event === 'degraded') {
    return {
      ...state,
      degradedReason: typeof data.degraded_reason === 'string' ? data.degraded_reason : state.degradedReason,
      conflictNote: typeof data.conflict_note === 'string' ? data.conflict_note : state.conflictNote
    }
  }

  if (frame.event === 'completed') {
    const quota = data.quota && typeof data.quota === 'object'
      ? { used: Number(data.quota.used) || 0, limit: data.quota.limit === null || data.quota.limit === undefined ? null : Number(data.quota.limit) }
      : state.quota
    return {
      ...state,
      phase: 'done',
      degradedReason: typeof data.degraded_reason === 'string' ? data.degraded_reason : state.degradedReason,
      conflictNote: typeof data.conflict_note === 'string' ? data.conflict_note : state.conflictNote,
      quota
    }
  }

  if (frame.event === 'blocked') {
    return {
      ...state,
      phase: 'blocked',
      sections: [],
      blocked: {
        reason: String(data.reason || ''),
        channels: Array.isArray(data.channels) ? data.channels : [],
        appealAllowed: data.appeal_allowed !== false
      }
    }
  }

  if (frame.event === 'error') {
    return {
      ...state,
      phase: 'failed',
      errorMessage: String(data.message || '生成中断，请稍后重试')
    }
  }

  return state
}

function appendPartialContent(blocks: QaStreamBlock[], blockKey: string, delta: string): QaStreamBlock[] {
  const sameBlock = blocks.findIndex((block) => block.block_key === blockKey && block.partial !== false)
  if (sameBlock !== -1) {
    return blocks.map((block, position) => position === sameBlock
      ? { ...block, content: (block.content || '') + delta }
      : block)
  }
  // 骨架占位（有标题无 block_key）按顺序接收首个内容切片，保持标题与正文对齐
  const placeholder = blocks.findIndex((block) => block.partial === true && !block.block_key)
  if (placeholder !== -1) {
    return blocks.map((block, position) => position === placeholder
      ? { ...block, block_key: blockKey, content: delta }
      : block)
  }
  return [...blocks, { block_key: blockKey, content: delta, partial: true }]
}

export interface ChunkedRequestHandlers {
  onChunk: (chunk: ArrayBuffer) => void
  onComplete: (result: { statusCode: number; body?: string }) => void
  onFail: (message: string) => void
}

export interface ChunkedRequestOptions {
  url: string
  method: 'POST'
  header: Record<string, string>
  timeout?: number
  handlers: ChunkedRequestHandlers
}

export type ChunkedRequest = (options: ChunkedRequestOptions) => { abort?: () => void }

type QaStreamStorage = { getStorageSync(key: string): unknown }

export interface QaStreamFinish {
  phase: QaStreamPhase
  hadFrames: boolean
  statusCode?: number
  message?: string
}

export function createQaStreamService({ request, storage, baseUrl, tokenKey = 'jiaban_access_token' }: {
  request: ChunkedRequest
  storage: QaStreamStorage
  baseUrl: string
  tokenKey?: string
}) {
  const origin = baseUrl.replace(/\/$/, '')

  function buildRequest(sessionUid: string) {
    const token = storage.getStorageSync(tokenKey)
    return {
      url: `${origin}/qa/sessions/${encodeURIComponent(sessionUid)}/stream`,
      method: 'POST' as const,
      header: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(typeof token === 'string' && token ? { Authorization: `Bearer ${token}` } : {})
      },
      timeout: 180000
    }
  }

  return {
    start(sessionUid: string, { onUpdate, onFinish }: {
      onUpdate: (state: QaStreamState) => void
      onFinish?: (result: QaStreamFinish) => void
    }) {
      let state = createQaStreamState()
      let frameCount = 0
      let bodyText = ''
      let finished = false
      let carry: number[] = []
      const parser = createSseParser({
        onFrame(frame) {
          frameCount += 1
          state = applyQaStreamEvent(state, frame)
          onUpdate(state)
        }
      })
      const finish = (result: QaStreamFinish) => {
        if (finished) return
        finished = true
        onFinish?.(result)
      }
      const handle = request({
        ...buildRequest(sessionUid),
        handlers: {
          onChunk(chunk) {
            const decoded = decodeUtf8Chunk(carry, chunk)
            carry = decoded.carry
            if (!decoded.text) return
            bodyText += decoded.text
            parser.push(decoded.text)
          },
          onComplete(result) {
            finish({
              phase: state.phase,
              hadFrames: frameCount > 0,
              statusCode: result.statusCode,
              message: frameCount === 0 && result.statusCode >= 400
                ? extractErrorMessage(result.body || bodyText)
                : undefined
            })
          },
          onFail(message) {
            finish({ phase: state.phase, hadFrames: frameCount > 0, message })
          }
        }
      })
      return {
        current: () => state,
        abort: () => handle?.abort?.()
      }
    }
  }
}

function extractErrorMessage(body: string | undefined) {
  if (!body) return '问答服务连接失败'
  try {
    const envelope = JSON.parse(body)
    if (envelope && typeof envelope.message === 'string' && envelope.message) return envelope.message
  } catch {
    // 非 JSON 响应体，回退默认文案
  }
  return '问答服务连接失败'
}

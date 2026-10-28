import { createSseParser, decodeUtf8Chunk, type SseFrame } from './sse.ts'
import type { AiLabelView, TriageView, TrustBarView } from '../api'

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
  aiLabel: AiLabelView | null
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
  // V3.1 合规要素：completed 帧（含缓存路径）与轮询/历史详情同口径下发
  aiLabel: AiLabelView | null
  trustBar: TrustBarView | null
  triage: TriageView | null
  inputMode: string
  photoMeta: Record<string, unknown> | null
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
    errorMessage: '',
    aiLabel: null,
    trustBar: null,
    triage: null,
    inputMode: '',
    photoMeta: null
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

/** AI 标识契约归一化：仅取契约字段，缺 text_id 视为未下发（保持上一帧状态） */
function pickAiLabel(raw: unknown): AiLabelView | null {
  if (!raw || typeof raw !== 'object') return null
  const value = raw as Record<string, unknown>
  const textId = String(value.text_id || '')
  if (!textId) return null
  return {
    visible: value.visible !== false,
    text_id: textId,
    position: String(value.position || ''),
    fallback_text: String(value.fallback_text || ''),
    filing_no: typeof value.filing_no === 'string' ? value.filing_no : null
  }
}

// triage 显式为 null 是合法状态（无分级场景），需与「未下发」区分：
// completed 帧带 triage 键时按帧覆盖，未带则沿用上一状态。
function pickTriage(raw: unknown, previous: TriageView | null): TriageView | null {
  if (raw === null) return null
  if (!raw || typeof raw !== 'object') return previous
  const value = raw as Record<string, unknown>
  const level = value.level === 'red' || value.level === 'yellow' || value.level === 'green'
    ? value.level
    : null
  return {
    level,
    level_label: String(value.level_label || ''),
    level_color: String(value.level_color || ''),
    icon: String(value.icon || ''),
    action_hint: String(value.action_hint || ''),
    scene: typeof value.scene === 'string' ? value.scene : null,
    insufficient: value.insufficient === true,
    unavailable: value.unavailable === true,
    missing_info: Array.isArray(value.missing_info) ? value.missing_info.map(String) : [],
    rule_hits: Array.isArray(value.rule_hits) ? (value.rule_hits as TriageView['rule_hits']) : [],
    basis: String(value.basis || ''),
    observations: Array.isArray(value.observations) ? value.observations.map(String) : [],
    escalation_flags: Array.isArray(value.escalation_flags) ? value.escalation_flags.map(String) : [],
    contraindications: Array.isArray(value.contraindications) ? value.contraindications.map(String) : [],
    disclaimers: Array.isArray(value.disclaimers) ? value.disclaimers.map(String) : [],
    night_mode: value.night_mode === true,
    night_notice: typeof value.night_notice === 'string' ? value.night_notice : null,
    decided_at: String(value.decided_at || '')
  }
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
      quota,
      aiLabel: pickAiLabel(data.ai_label) || state.aiLabel,
      trustBar: data.trust_bar && typeof data.trust_bar === 'object'
        ? (data.trust_bar as TrustBarView)
        : state.trustBar,
      triage: pickTriage(data.triage, state.triage),
      inputMode: typeof data.input_mode === 'string' ? data.input_mode : state.inputMode
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
        appealAllowed: data.appeal_allowed !== false,
        aiLabel: pickAiLabel(data.ai_label)
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

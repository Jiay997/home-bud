import test from 'node:test'
import assert from 'node:assert/strict'
import { applyQaStreamEvent, canRenderStreamContent, createQaStreamState, createQaStreamService } from '../src/services/qa-stream.ts'

function frame(event, data) {
  return { event, data: JSON.stringify(data) }
}

test('started frame seeds skeleton sections in render order', () => {
  const state = applyQaStreamEvent(
    createQaStreamState(),
    frame('started', { session_uid: 's-1', render_order: ['safety', 'child'] })
  )
  assert.equal(state.phase, 'checking')
  assert.equal(state.sessionUid, 's-1')
  assert.deepEqual(state.sections.map((section) => section.section_key), ['safety', 'child'])
  assert.equal(state.sections[0].done, false)
})

test('skeleton and content deltas accumulate with placeholder title alignment', () => {
  let state = applyQaStreamEvent(createQaStreamState(), frame('started', { session_uid: 's-1', render_order: ['child'] }))
  state = applyQaStreamEvent(state, frame('section_delta', {
    section_key: 'child', stage: 'skeleton', title: '喂养建议', block_titles: ['要点']
  }))
  assert.equal(state.phase, 'streaming')
  assert.equal(state.sections[0].title, '喂养建议')
  assert.equal(state.sections[0].blocks[0].title, '要点')

  state = applyQaStreamEvent(state, frame('section_delta', {
    section_key: 'child', stage: 'content', block_key: 'b1', delta: '第一段'
  }))
  assert.equal(state.sections[0].blocks[0].block_key, 'b1')
  assert.equal(state.sections[0].blocks[0].content, '第一段')
  assert.equal(state.sections[0].blocks[0].title, '要点')

  state = applyQaStreamEvent(state, frame('section_delta', {
    section_key: 'child', stage: 'content', block_key: 'b1', delta: '续写'
  }))
  assert.equal(state.sections[0].blocks[0].content, '第一段续写')
})

test('section_done replaces streamed content with gated authoritative blocks', () => {
  let state = applyQaStreamEvent(createQaStreamState(), frame('started', { session_uid: 's-1', render_order: ['child'] }))
  state = applyQaStreamEvent(state, frame('section_delta', {
    section_key: 'child', stage: 'content', block_key: 'b1', delta: '临时正文'
  }))
  state = applyQaStreamEvent(state, frame('section_done', {
    section_key: 'child',
    title: '喂养建议',
    blocks: [
      { block_key: 'b1', title: '要点', content: '权威正文' },
      { block_key: 'b2', title: '深度方案', is_member_content: true, access_tier: 'block' }
    ],
    pinned: false,
    immutable: false
  }))
  const section = state.sections[0]
  assert.equal(section.done, true)
  assert.equal(section.blocks.length, 2)
  assert.equal(section.blocks[0].content, '权威正文')
  assert.equal(section.blocks[1].is_member_content, true)
  assert.equal(section.blocks[1].content, undefined)
})

test('blocked frame clears rendered content and switches to intercept view state', () => {
  let state = applyQaStreamEvent(createQaStreamState(), frame('started', { session_uid: 's-1', render_order: ['safety'] }))
  state = applyQaStreamEvent(state, frame('blocked', {
    reason: 'policy_hit', channels: [{ title: '心理援助热线' }], appeal_allowed: true
  }))
  assert.equal(state.phase, 'blocked')
  assert.deepEqual(state.sections, [])
  assert.equal(state.blocked.reason, 'policy_hit')
  assert.equal(state.blocked.appealAllowed, true)
})

test('degraded and completed frames carry reason, quota and final phase', () => {
  let state = createQaStreamState()
  state = applyQaStreamEvent(state, frame('degraded', { degraded_reason: 'safety_check_failed', conflict_note: 'safety 未通过' }))
  assert.equal(state.degradedReason, 'safety_check_failed')
  assert.equal(state.conflictNote, 'safety 未通过')

  state = applyQaStreamEvent(state, frame('completed', {
    status: 'degraded', quota: { used: 2, limit: 5 }
  }))
  assert.equal(state.phase, 'done')
  assert.deepEqual(state.quota, { used: 2, limit: 5 })
  assert.equal(state.degradedReason, 'safety_check_failed')
})

test('error frames and unknown events are handled without throwing', () => {
  let state = createQaStreamState()
  const untouched = applyQaStreamEvent(state, frame('mystery', { a: 1 }))
  assert.equal(untouched, state)
  assert.equal(applyQaStreamEvent(state, { event: 'completed', data: 'not-json' }), state)

  state = applyQaStreamEvent(state, frame('error', { code: 1902, message: '生成中断，请稍后重试' }))
  assert.equal(state.phase, 'failed')
  assert.equal(state.errorMessage, '生成中断，请稍后重试')
})

test('completed frame carries the V3.1 compliance contract (label / trust bar / triage / input mode)', () => {
  let state = createQaStreamState()
  state = applyQaStreamEvent(state, frame('completed', {
    status: 'done',
    input_mode: 'photo',
    ai_label: { visible: true, text_id: 'AI_GEN_LABEL_V1', position: 'page_top', fallback_text: '内容由 AI 生成，仅供参考', filing_no: null },
    trust_bar: {
      age_adaptation: { label: '适用：1–3 岁', hint: null, source: 'profile.child', band: '1-3y', months: 20, generic: false },
      source_levels: [{ kb_id: 'kb_1', title: '发热护理', level: 'guide', level_label: '权威指南', badge: 'A', applicable: null, missing: false, low_level: false }],
      triage_badge: { level: 'yellow', label: '建议尽快评估', icon: '🟡', color: 'warning' },
      missing: ['source_level'],
      complete: false,
      checklist: { ai_label_visible: true },
      checklist_total: 10,
      checklist_passed: 9
    },
    triage: {
      level: 'yellow',
      level_label: '建议尽快评估',
      level_color: 'warning',
      icon: '🟡',
      action_hint: '建议 24 小时内评估',
      scene: 'fever',
      insufficient: false,
      unavailable: false,
      missing_info: [],
      rule_hits: [{ rule_id: 'fever_child_high', title: '高热', level: 'yellow', priority: 700, version: 3 }],
      basis: '高热伴不适建议 24 小时内评估',
      observations: ['每 4 小时测体温'],
      escalation_flags: ['抽搐'],
      contraindications: ['不要捂汗'],
      disclaimers: ['不构成诊断'],
      night_mode: false,
      night_notice: null,
      decided_at: '2026-10-16T10:00:00+08:00'
    }
  }))

  assert.equal(state.phase, 'done')
  assert.equal(state.aiLabel.text_id, 'AI_GEN_LABEL_V1')
  assert.equal(state.trustBar.checklist_passed, 9)
  assert.deepEqual(state.trustBar.missing, ['source_level'])
  assert.equal(state.triage.level, 'yellow')
  assert.deepEqual(state.triage.rule_hits.map((hit) => hit.rule_id), ['fever_child_high'])
  assert.equal(state.inputMode, 'photo')
})

test('insufficient triage keeps missing info and an explicit null triage clears the card', () => {
  let state = applyQaStreamEvent(createQaStreamState(), frame('completed', {
    status: 'done',
    triage: {
      level: null,
      level_label: '信息不足，暂不定档',
      level_color: 'neutral',
      insufficient: true,
      unavailable: false,
      missing_info: ['体温读数与测量方式', '症状持续时间']
    }
  }))
  assert.equal(state.triage.insufficient, true)
  assert.equal(state.triage.level, null)
  assert.equal(state.triage.missing_info.length, 2)

  // completed 帧显式 triage=null 表示「无分级场景」，必须清空上一状态而非保留旧档位
  state = applyQaStreamEvent(state, frame('completed', { status: 'done', triage: null }))
  assert.equal(state.triage, null)
})

test('blocked frame keeps the AI label for the intercept view', () => {
  const state = applyQaStreamEvent(createQaStreamState(), frame('blocked', {
    reason: 'policy_hit',
    channels: [{ channel_code: 'crisis_110', channel_name: '紧急报警', phone_number: '110' }],
    appeal_allowed: true,
    ai_label: { visible: true, text_id: 'AI_GEN_LABEL_V1', position: 'page_top', fallback_text: '内容由 AI 生成，仅供参考', filing_no: 'TEST-1' }
  }))
  assert.equal(state.phase, 'blocked')
  assert.equal(state.blocked.aiLabel.text_id, 'AI_GEN_LABEL_V1')
  assert.equal(state.blocked.aiLabel.filing_no, 'TEST-1')
  assert.equal(state.blocked.channels.length, 1)
})

test('non-member stream content is limited to the always-free safety section', () => {
  assert.equal(canRenderStreamContent('safety', false), true)
  assert.equal(canRenderStreamContent('child', false), false)
  assert.equal(canRenderStreamContent('child', true), true)
})

test('stream service builds an authorized chunked request and reports frames', () => {
  const sent = []
  const service = createQaStreamService({
    request: (options) => {
      sent.push(options)
      return { abort: () => {} }
    },
    storage: { getStorageSync: (key) => key === 'jiaban_access_token' ? 'token-1' : undefined },
    baseUrl: 'http://api.test/api/v1/'
  })

  let latest = null
  let finish = null
  service.start('sess-1', {
    onUpdate: (state) => { latest = state },
    onFinish: (result) => { finish = result }
  })

  assert.equal(sent[0].url, 'http://api.test/api/v1/qa/sessions/sess-1/stream')
  assert.equal(sent[0].method, 'POST')
  assert.equal(sent[0].header.Authorization, 'Bearer token-1')
  assert.equal(sent[0].header.Accept, 'text/event-stream')

  const encoder = new TextEncoder()
  const payload = 'event: started\ndata: {"session_uid":"sess-1","render_order":["safety"]}\n\n' +
    'event: completed\ndata: {"status":"done","quota":{"used":1,"limit":5}}\n\n'
  const bytes = encoder.encode(payload)
  sent[0].handlers.onChunk(bytes.slice(0, 30))
  assert.equal(latest, null)
  sent[0].handlers.onChunk(bytes.slice(30))
  assert.equal(latest.phase, 'done')
  assert.deepEqual(latest.quota, { used: 1, limit: 5 })

  sent[0].handlers.onComplete({ statusCode: 200 })
  assert.equal(finish.hadFrames, true)
  assert.equal(finish.statusCode, 200)
})

test('stream service surfaces HTTP errors without frames as failure message', () => {
  const sent = []
  const service = createQaStreamService({
    request: (options) => {
      sent.push(options)
      return { abort: () => {} }
    },
    storage: { getStorageSync: () => undefined },
    baseUrl: 'http://api.test/api/v1'
  })

  let finish = null
  service.start('sess-2', { onUpdate: () => {}, onFinish: (result) => { finish = result } })
  sent[0].handlers.onComplete({ statusCode: 401, body: '{"code":1101,"message":"登录状态已失效"}' })
  assert.equal(finish.hadFrames, false)
  assert.equal(finish.message, '登录状态已失效')

  service.start('sess-3', { onUpdate: () => {}, onFinish: (result) => { finish = result } })
  sent[1].handlers.onFail('request:fail timeout')
  assert.equal(finish.message, 'request:fail timeout')
})

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

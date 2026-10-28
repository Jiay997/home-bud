import test from 'node:test'
import assert from 'node:assert/strict'
import {
  FALLBACK_KNOWLEDGE,
  dayNumber,
  formatKnowledgeDate,
  localDateStamp,
  pickFallback,
  resolveDailyKnowledge
} from '../src/services/daily-knowledge.ts'

function createStorage() {
  const map = new Map()
  return {
    getStorageSync: (key) => map.get(key),
    setStorageSync: (key, value) => map.set(key, JSON.parse(JSON.stringify(value)))
  }
}

function remoteEntry(kbId, title = '接口知识') {
  return {
    kb_id: kbId,
    title,
    summary: '摘要',
    content: '正文',
    category: 'infant',
    category_label: '母婴',
    topic: '回应性照护',
    stage_label: '0–6 月',
    preconditions: '0–36 月龄',
    source_level: 'guide',
    source_name: '国家卫健委指南'
  }
}

function payload(date, entry) {
  return { date, entry, total: entry ? 1 : 0 }
}

test('fallback knowledge is stable per date and changes across consecutive days', () => {
  const first = pickFallback('2026-10-22')
  assert.equal(pickFallback('2026-10-22').kb_id, first.kb_id)
  assert.notEqual(pickFallback('2026-10-23').kb_id, first.kb_id)
  assert.equal(dayNumber('2026-10-22') + 1, dayNumber('2026-10-23'))
})

test('fallback rotates through every built-in entry without repeat', () => {
  const seen = new Set()
  for (let offset = 0; offset < FALLBACK_KNOWLEDGE.length; offset += 1) {
    const date = new Date(Date.UTC(2026, 0, 1 + offset)).toISOString().slice(0, 10)
    seen.add(pickFallback(date).kb_id)
  }
  assert.equal(seen.size, FALLBACK_KNOWLEDGE.length)
})

test('resolver caches daily payload and reuses it within the same day', async () => {
  const storage = createStorage()
  let calls = 0
  const load = async () => {
    calls += 1
    return payload('2026-10-22', remoteEntry('kb-1'))
  }

  const first = await resolveDailyKnowledge({ storage, load, todayStamp: () => '2026-10-22' })
  assert.equal(first.source, 'daily')
  assert.equal(first.entry.kb_id, 'kb-1')

  const second = await resolveDailyKnowledge({ storage, load, todayStamp: () => '2026-10-22' })
  assert.equal(second.source, 'cache')
  assert.equal(second.entry.kb_id, 'kb-1')
  assert.equal(calls, 1)
})

test('resolver falls back when knowledge base is empty', async () => {
  const storage = createStorage()
  const result = await resolveDailyKnowledge({
    storage,
    load: async () => payload('2026-10-22', null),
    todayStamp: () => '2026-10-22'
  })
  assert.equal(result.source, 'fallback')
  assert.equal(result.entry.kb_id, pickFallback('2026-10-22').kb_id)
})

test('resolver falls back on request failure and ignores stale cache', async () => {
  const storage = createStorage()
  storage.setStorageSync('jiaban_daily_knowledge', {
    checked_date: '2026-10-21',
    payload: payload('2026-10-21', remoteEntry('kb-stale'))
  })

  const result = await resolveDailyKnowledge({
    storage,
    load: async () => {
      throw new Error('network down')
    },
    todayStamp: () => '2026-10-22'
  })
  assert.equal(result.source, 'fallback')
  assert.notEqual(result.entry.kb_id, 'kb-stale')
})

test('date helpers use Beijing date and render month-day copy', () => {
  assert.equal(localDateStamp(new Date('2026-10-21T16:30:00Z')), '2026-10-22')
  assert.equal(formatKnowledgeDate('2026-10-22'), '10月22日')
  assert.equal(formatKnowledgeDate('bad'), '')
})

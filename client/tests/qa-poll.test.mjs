import test from 'node:test'
import assert from 'node:assert/strict'
import { pollQaSession } from '../src/services/qa-poll.ts'

test('QA polling keeps waiting long enough for a completed backend generation', async () => {
  let calls = 0
  const result = await pollQaSession({
    getSession: async () => {
      calls += 1
      return calls < 24
        ? { status: 'streaming', sections: [] }
        : { status: 'done', sections: [{ section_key: 'child' }] }
    },
    getTriggerError: () => null,
    sleep: async () => undefined
  })

  assert.equal(calls, 24)
  assert.equal(result.status, 'done')
  assert.equal(result.sections.length, 1)
})

test('QA polling surfaces a failed stream trigger immediately', async () => {
  await assert.rejects(pollQaSession({
    getSession: async () => ({ status: 'pending', sections: [] }),
    getTriggerError: () => '问答服务连接失败',
    sleep: async () => undefined
  }), /问答服务连接失败/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { createAssessmentProgressStore } from '../src/services/assessment-progress.ts'

function createStorage() {
  const map = new Map()
  return {
    getStorageSync: (key) => map.get(key),
    setStorageSync: (key, value) => map.set(key, JSON.parse(JSON.stringify(value)))
  }
}

test('assessment progress mirror round-trips per user', () => {
  const store = createAssessmentProgressStore({ storage: createStorage() })
  store.write('user-a', { assessment_uid: 'as-1', answered: 5, total: 16, updated_at: 100 })
  assert.deepEqual(store.read('user-a'), { assessment_uid: 'as-1', answered: 5, total: 16, updated_at: 100 })
})

test('assessment progress mirror is isolated between accounts', () => {
  const store = createAssessmentProgressStore({ storage: createStorage() })
  store.write('user-a', { assessment_uid: 'as-1', answered: 5, total: 16, updated_at: 100 })
  assert.equal(store.read('user-b'), null)
})

test('assessment progress mirror clears after submit and survives corrupt data', () => {
  const storage = createStorage()
  const store = createAssessmentProgressStore({ storage })
  store.write('user-a', { assessment_uid: 'as-1', answered: 16, total: 16, updated_at: 200 })
  store.clear('user-a')
  assert.equal(store.read('user-a'), null)

  storage.setStorageSync('jiaban_assessment_progress', 42)
  assert.equal(store.read('user-a'), null)
})

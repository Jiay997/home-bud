import test from 'node:test'
import assert from 'node:assert/strict'
import { createQaTargetStore } from '../src/services/qa-target.ts'

function createStorage() {
  const map = new Map()
  return {
    getStorageSync: (key) => map.get(key),
    setStorageSync: (key, value) => map.set(key, JSON.parse(JSON.stringify(value)))
  }
}

test('QA target selection persists per entry for the same user', () => {
  const store = createQaTargetStore({ storage: createStorage() })
  store.write('child', 'user-a', { profile_uid: 'c-1', name: '宝宝A' })
  store.write('pet', 'user-a', { profile_uid: 'p-1', name: '咪咪' })

  assert.deepEqual(store.read('child', 'user-a'), { profile_uid: 'c-1', name: '宝宝A' })
  assert.deepEqual(store.read('pet', 'user-a'), { profile_uid: 'p-1', name: '咪咪' })
  assert.equal(store.read('family', 'user-a'), null)
})

test('QA target selection is isolated between accounts on the same device', () => {
  const store = createQaTargetStore({ storage: createStorage() })
  store.write('child', 'user-a', { profile_uid: 'c-1', name: '宝宝A' })
  assert.equal(store.read('child', 'user-b'), null)

  store.write('child', 'user-b', { profile_uid: 'c-9', name: '宝宝B' })
  assert.equal(store.read('child', 'user-a').profile_uid, 'c-1')
  assert.equal(store.read('child', 'user-b').profile_uid, 'c-9')
})

test('QA target selection can be cleared and tolerates corrupt storage', () => {
  const storage = createStorage()
  const store = createQaTargetStore({ storage })
  store.write('child', 'user-a', { profile_uid: 'c-1', name: '宝宝A' })
  store.clear('child', 'user-a')
  assert.equal(store.read('child', 'user-a'), null)

  storage.setStorageSync('jiaban_qa_target', 'broken')
  assert.equal(store.read('child', 'user-a'), null)
})

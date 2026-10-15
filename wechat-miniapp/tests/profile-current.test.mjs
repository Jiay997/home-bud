import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileCurrentStore } from '../src/services/profile-current.ts'

function createStorage() {
  const map = new Map()
  return {
    getStorageSync: (key) => map.get(key),
    setStorageSync: (key, value) => map.set(key, JSON.parse(JSON.stringify(value)))
  }
}

test('current profile persists and can be overwritten', () => {
  const store = createProfileCurrentStore({ storage: createStorage() })
  assert.equal(store.read(), null)

  store.write({ profile_type: 'child', profile_uid: 'c-1' })
  assert.deepEqual(store.read(), { profile_type: 'child', profile_uid: 'c-1' })

  store.write({ profile_type: 'pet', profile_uid: 'p-9' })
  assert.deepEqual(store.read(), { profile_type: 'pet', profile_uid: 'p-9' })
})

test('current profile can be cleared', () => {
  const store = createProfileCurrentStore({ storage: createStorage() })
  store.write({ profile_type: 'child', profile_uid: 'c-1' })
  store.clear()
  assert.equal(store.read(), null)
})

test('current profile tolerates corrupt storage and invalid fields', () => {
  const storage = createStorage()
  const store = createProfileCurrentStore({ storage })

  storage.setStorageSync('jiaban_current_profile', 'broken')
  assert.equal(store.read(), null)

  storage.setStorageSync('jiaban_current_profile', { profile_type: 'family', profile_uid: 'x-1' })
  assert.equal(store.read(), null)

  storage.setStorageSync('jiaban_current_profile', { profile_type: 'child', profile_uid: '' })
  assert.equal(store.read(), null)

  storage.setStorageSync('jiaban_current_profile', { profile_type: 'child' })
  assert.equal(store.read(), null)
})

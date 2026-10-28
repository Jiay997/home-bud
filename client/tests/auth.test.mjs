import test from 'node:test'
import assert from 'node:assert/strict'
import { createAuthService } from '../src/services/auth.ts'

test('development login uses device identity and never requests a WeChat code', async () => {
  const calls = []
  const storage = new Map()
  const runtime = {
    getStorageSync: (key) => storage.get(key),
    setStorageSync: (key, value) => storage.set(key, value),
    login: () => assert.fail('development mode must not invoke WeChat login')
  }
  const auth = createAuthService({
    runtime,
    request: async (path, options) => {
      calls.push({ path, options })
      return { access_token: 'dev-token', user_uid: 'usr_dev', member_status: 'free' }
    },
    mode: 'development',
    makeDeviceId: () => 'device-1'
  })

  await auth.login()

  assert.equal(calls[0].path, '/auth/dev-login')
  assert.deepEqual(calls[0].options.body, { device_id: 'device-1' })
  assert.equal(storage.get('jiaban_access_token'), 'dev-token')
})

test('production login exchanges a temporary WeChat code with the backend', async () => {
  const calls = []
  const storage = new Map()
  const runtime = {
    setStorageSync: (key, value) => storage.set(key, value),
    login: (options) => options.success({ code: 'wx-code-once' })
  }
  const auth = createAuthService({
    runtime,
    request: async (path, options) => {
      calls.push({ path, options })
      return { access_token: 'wx-token', user_uid: 'usr_wx', member_status: 'free' }
    },
    mode: 'production'
  })

  await auth.login()

  assert.equal(calls[0].path, '/auth/wx-login')
  assert.deepEqual(calls[0].options.body, { code: 'wx-code-once' })
  assert.equal(storage.get('jiaban_access_token'), 'wx-token')
})

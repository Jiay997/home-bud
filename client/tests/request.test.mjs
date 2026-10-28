import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequestClient } from '../src/platform/request.ts'

function createRuntime(response) {
  const calls = []
  const storage = new Map([['jiaban_access_token', 'token-123']])
  return {
    calls,
    storage,
    runtime: {
      getStorageSync: (key) => storage.get(key),
      removeStorageSync: (key) => storage.delete(key),
      request: (options) => {
        calls.push(options)
        options.success(response)
      }
    }
  }
}

test('request client unwraps the API envelope and sends the stored bearer token', async () => {
  const { runtime, calls } = createRuntime({
    statusCode: 200,
    data: { code: 0, data: { user_uid: 'usr_1' }, message: 'ok' }
  })
  const request = createRequestClient({ runtime, baseUrl: 'https://api.example.test/api/v1' })

  const data = await request('/me')

  assert.deepEqual(data, { user_uid: 'usr_1' })
  assert.equal(calls[0].url, 'https://api.example.test/api/v1/me')
  assert.equal(calls[0].header.Authorization, 'Bearer token-123')
})

test('request client rejects business errors with the backend code and message', async () => {
  const { runtime } = createRuntime({
    statusCode: 409,
    data: { code: 1202, message: '今日额度已用完' }
  })
  const request = createRequestClient({ runtime, baseUrl: 'https://api.example.test/api/v1' })

  await assert.rejects(request('/qa/sessions'), (error) => {
    assert.equal(error.code, 1202)
    assert.equal(error.message, '今日额度已用完')
    return true
  })
})

test('request client applies a bounded timeout to each platform request', async () => {
  const { runtime, calls } = createRuntime({
    statusCode: 200,
    data: { code: 0, data: { ok: true } }
  })
  const request = createRequestClient({ runtime, baseUrl: 'https://api.example.test/api/v1' })

  await request('/health')

  assert.equal(calls[0].timeout, 20000)
})

test('request client resolves the base url per request and strips its trailing slash', async () => {
  const { runtime, calls } = createRuntime({
    statusCode: 200,
    data: { code: 0, data: { ok: true } }
  })
  let resolutions = 0
  const request = createRequestClient({
    runtime,
    baseUrl: 'https://api.example.test/api/v1',
    resolveBaseUrl: async () => {
      resolutions += 1
      return 'http://127.0.0.1:8000/api/v1/'
    }
  })

  await request('/me')

  assert.equal(resolutions, 1)
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/me')
})

test('request client notifies endpoint invalidation on network failures only', async () => {
  const invalidations = []
  const failingRuntime = {
    getStorageSync: () => undefined,
    request: (options) => options.fail({ errMsg: 'request:fail timeout' })
  }
  const failingRequest = createRequestClient({
    runtime: failingRuntime,
    baseUrl: 'https://api.example.test/api/v1',
    onNetworkFailure: () => invalidations.push('network')
  })
  await assert.rejects(failingRequest('/me'))

  const { runtime } = createRuntime({
    statusCode: 409,
    data: { code: 1202, message: '今日额度已用完' }
  })
  const businessRequest = createRequestClient({
    runtime,
    baseUrl: 'https://api.example.test/api/v1',
    onNetworkFailure: () => invalidations.push('business')
  })
  await assert.rejects(businessRequest('/qa/sessions'))

  assert.deepEqual(invalidations, ['network'])
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { createEndpointResolver, normalizeBaseUrl } from '../src/platform/endpoint.ts'

function createRuntime({ platform = 'ios', storage = {}, reachable = [] } = {}) {
  const probeCalls = []
  const runtime = {
    getStorageSync: (key) => storage[key],
    setStorageSync: (key, value) => { storage[key] = value },
    removeStorageSync: (key) => { delete storage[key] },
    getSystemInfoSync: () => ({ platform }),
    request: (options) => {
      probeCalls.push(String(options.url))
      const base = String(options.url).replace(/\/health$/, '')
      if (reachable.includes(base)) options.success({ statusCode: 200, data: { ok: true } })
      else options.fail({ errMsg: 'request:fail timeout' })
    }
  }
  return { runtime, probeCalls, storage }
}

test('devtools platform probes the loopback address first', async () => {
  const { runtime, probeCalls, storage } = createRuntime({
    platform: 'devtools',
    reachable: ['http://127.0.0.1:8000/api/v1', 'http://192.168.1.5:8000/api/v1']
  })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://192.168.1.5:8000/api/v1', 'http://10.0.0.2:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://127.0.0.1:8000/api/v1')
  assert.deepEqual(probeCalls, ['http://127.0.0.1:8000/api/v1/health'])
  assert.equal(storage.jiaban_last_api_base, 'http://127.0.0.1:8000/api/v1')
})

test('device builds probe candidates before the primary and stop at the first reachable one', async () => {
  const { runtime, probeCalls } = createRuntime({
    platform: 'ios',
    reachable: ['http://10.0.0.2:8000/api/v1']
  })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://10.0.0.2:8000/api/v1', 'http://192.168.1.9:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://10.0.0.2:8000/api/v1')
  assert.deepEqual(probeCalls, ['http://10.0.0.2:8000/api/v1/health'])
})

test('device builds fall through unreachable candidates to the primary', async () => {
  const { runtime, probeCalls } = createRuntime({
    platform: 'ios',
    reachable: ['http://192.168.1.5:8000/api/v1']
  })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://10.0.0.2:8000/api/v1', 'http://192.168.1.9:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://192.168.1.5:8000/api/v1')
  assert.deepEqual(probeCalls, [
    'http://10.0.0.2:8000/api/v1/health',
    'http://192.168.1.9:8000/api/v1/health',
    'http://192.168.1.5:8000/api/v1/health'
  ])
})

test('resolution falls back to the primary when everything fails without caching the failure', async () => {
  const { runtime, probeCalls, storage } = createRuntime({ platform: 'ios', reachable: [] })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://10.0.0.2:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://192.168.1.5:8000/api/v1')
  const attempts = resolver.attempts()
  assert.equal(attempts.length, 3)
  assert.equal(attempts.every((item) => !item.ok), true)
  assert.equal(attempts.every((item) => item.err && item.ms >= 0), true)
  assert.equal(storage.jiaban_last_api_base, undefined)

  const before = probeCalls.length
  await resolver.ensure()
  assert.equal(probeCalls.length > before, true)
})

test('invalidate re-probes and picks the newly reachable address', async () => {
  const reachable = ['http://192.168.1.10:8000/api/v1']
  const { runtime, probeCalls } = createRuntime({ platform: 'ios', reachable })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://192.168.1.10:8000/api/v1', 'http://192.168.1.11:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://192.168.1.10:8000/api/v1')
  const before = probeCalls.length
  assert.equal(await resolver.ensure(), 'http://192.168.1.10:8000/api/v1')
  assert.equal(probeCalls.length, before)

  reachable.splice(0, reachable.length, 'http://192.168.1.11:8000/api/v1')
  resolver.invalidate()
  assert.equal(await resolver.ensure(), 'http://192.168.1.11:8000/api/v1')
  assert.equal(probeCalls.length > before, true)
})

test('manual override is exclusive and reports its own failure without probing other candidates', async () => {
  const { runtime, probeCalls, storage } = createRuntime({
    platform: 'ios',
    storage: { jiaban_debug_api_base: 'http://192.168.9.9:8000/api/v1' },
    reachable: ['http://192.168.1.10:8000/api/v1']
  })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://192.168.1.10:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://192.168.1.5:8000/api/v1')
  assert.deepEqual(probeCalls, ['http://192.168.9.9:8000/api/v1/health'])
  assert.equal(resolver.attempts()[0].url, 'http://192.168.9.9:8000/api/v1')

  resolver.setOverride('192.168.9.9:8000/api/v1/')
  assert.equal(storage.jiaban_debug_api_base, 'http://192.168.9.9:8000/api/v1')
  resolver.clearOverride()
  assert.equal(storage.jiaban_debug_api_base, undefined)
  assert.equal(await resolver.ensure(), 'http://192.168.1.10:8000/api/v1')
})

test('the last known good address outranks baked candidates', async () => {
  const { runtime, probeCalls, storage } = createRuntime({
    platform: 'ios',
    storage: { jiaban_last_api_base: 'http://192.168.1.20:8000/api/v1' },
    reachable: ['http://192.168.1.20:8000/api/v1', 'http://192.168.1.10:8000/api/v1']
  })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://192.168.1.10:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://192.168.1.20:8000/api/v1')
  assert.deepEqual(probeCalls, ['http://192.168.1.20:8000/api/v1/health'])
  assert.equal(storage.jiaban_last_api_base, 'http://192.168.1.20:8000/api/v1')
})

test('storage and platform failures do not break resolution', async () => {
  const runtime = {
    getStorageSync: () => { throw new Error('storage down') },
    setStorageSync: () => { throw new Error('storage down') },
    removeStorageSync: () => { throw new Error('storage down') },
    getSystemInfoSync: () => { throw new Error('system info down') },
    request: (options) => options.fail({ errMsg: 'request:fail timeout' })
  }
  const resolver = createEndpointResolver({ runtime, primary: 'http://192.168.1.5:8000/api/v1', candidates: [] })

  assert.equal(await resolver.ensure(), 'http://192.168.1.5:8000/api/v1')
  assert.equal(resolver.current(), 'http://192.168.1.5:8000/api/v1')
})

test('base url normalization adds the scheme and strips trailing slashes', () => {
  assert.equal(normalizeBaseUrl('192.168.1.5:8000/api/v1'), 'http://192.168.1.5:8000/api/v1')
  assert.equal(normalizeBaseUrl(' http://192.168.1.5:8000/api/v1// '), 'http://192.168.1.5:8000/api/v1')
  assert.equal(normalizeBaseUrl(''), '')
  assert.equal(normalizeBaseUrl(null), '')
})

test('current stays on the last known good address during the invalidate window', async () => {
  const { runtime, storage } = createRuntime({
    platform: 'devtools',
    reachable: ['http://127.0.0.1:8000/api/v1']
  })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: ['http://192.168.1.5:8000/api/v1']
  })

  assert.equal(await resolver.ensure(), 'http://127.0.0.1:8000/api/v1')
  assert.equal(resolver.current(), 'http://127.0.0.1:8000/api/v1')

  resolver.invalidate()
  assert.equal(storage.jiaban_last_api_base, 'http://127.0.0.1:8000/api/v1')
  assert.equal(resolver.current(), 'http://127.0.0.1:8000/api/v1')
})

test('current falls back to the primary when nothing was ever resolved', () => {
  const { runtime } = createRuntime({ platform: 'ios', reachable: [] })
  const resolver = createEndpointResolver({
    runtime,
    primary: 'http://192.168.1.5:8000/api/v1',
    candidates: []
  })

  assert.equal(resolver.current(), 'http://192.168.1.5:8000/api/v1')
})

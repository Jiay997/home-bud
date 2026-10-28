import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveMediaUrl } from '../src/platform/media-url.ts'
import { createUploadClient } from '../src/platform/request.ts'

test('media urls join the api origin with the media path', () => {
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000/api/v1', '/media/children/a.jpg'), 'http://127.0.0.1:8000/media/children/a.jpg')
})

test('media urls strip the api suffix and trailing slash before joining', () => {
  assert.equal(resolveMediaUrl('http://192.168.1.5:8000/api/v1/', '/media/pets/b.jpg'), 'http://192.168.1.5:8000/media/pets/b.jpg')
})

test('media urls accept paths without the leading slash', () => {
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000/api/v1', 'media/children/a.jpg'), 'http://127.0.0.1:8000/media/children/a.jpg')
})

test('media urls pass absolute urls through untouched', () => {
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000/api/v1', 'https://cdn.example.test/media/a.jpg'), 'https://cdn.example.test/media/a.jpg')
})

test('media urls collapse empty values to an empty string', () => {
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000/api/v1', null), '')
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000/api/v1', ''), '')
})

test('media urls become same-origin absolute urls in the browser (D-01)', () => {
  const previous = globalThis.window
  globalThis.window = { location: { origin: 'http://localhost' } }
  try {
    // H5 API base 为根相对路径时，必须补全 origin，避免 uni-image 二次拼接 /app/
    assert.equal(
      resolveMediaUrl('/api/v1', '/media/users/a.jpg'),
      'http://localhost/media/users/a.jpg'
    )
  } finally {
    globalThis.window = previous
  }
})

function createUploadRuntime(response) {
  const calls = []
  const storage = new Map([['jiaban_access_token', 'token-upload']])
  return {
    calls,
    runtime: {
      getStorageSync: (key) => storage.get(key),
      uploadFile: (options) => {
        calls.push(options)
        options.success(response)
      }
    }
  }
}

test('upload client parses the stringified envelope and sends the stored bearer token', async () => {
  const { runtime, calls } = createUploadRuntime({
    statusCode: 200,
    data: JSON.stringify({ code: 0, data: { avatar_url: '/media/children/a.jpg' }, message: 'ok' })
  })
  const upload = createUploadClient({ runtime, baseUrl: 'https://api.example.test/api/v1' })

  const data = await upload('/profiles/children/c_1/avatar', 'wxfile://tmp_a.jpg', { method: 'PUT' })

  assert.deepEqual(data, { avatar_url: '/media/children/a.jpg' })
  assert.equal(calls[0].url, 'https://api.example.test/api/v1/profiles/children/c_1/avatar')
  assert.equal(calls[0].name, 'file')
  assert.equal(calls[0].filePath, 'wxfile://tmp_a.jpg')
  assert.equal(calls[0].method, 'PUT')
  assert.equal(calls[0].header.Authorization, 'Bearer token-upload')
})

test('upload client rejects business errors with the backend code and message', async () => {
  const { runtime } = createUploadRuntime({
    statusCode: 409,
    data: JSON.stringify({ code: 1007, message: '相册数量已达上限' })
  })
  const upload = createUploadClient({ runtime, baseUrl: 'https://api.example.test/api/v1' })

  await assert.rejects(upload('/profiles/children/c_1/photos', 'wxfile://tmp_a.jpg'), (error) => {
    assert.equal(error.code, 1007)
    assert.equal(error.message, '相册数量已达上限')
    return true
  })
})

test('upload client rejects http failures without an envelope', async () => {
  const { runtime } = createUploadRuntime({ statusCode: 500, data: '<html>oops</html>' })
  const upload = createUploadClient({ runtime, baseUrl: 'https://api.example.test/api/v1' })

  await assert.rejects(upload('/profiles/children/c_1/photos', 'wxfile://tmp_a.jpg'), (error) => {
    assert.equal(error.statusCode, 500)
    return true
  })
})

test('upload client notifies endpoint invalidation on network failures', async () => {
  const invalidations = []
  const runtime = {
    getStorageSync: () => undefined,
    uploadFile: (options) => options.fail({ errMsg: 'uploadFile:fail timeout' })
  }
  const upload = createUploadClient({
    runtime,
    baseUrl: 'https://api.example.test/api/v1',
    onNetworkFailure: () => invalidations.push('network')
  })

  await assert.rejects(upload('/profiles/children/c_1/avatar', 'wxfile://tmp_a.jpg'))
  assert.deepEqual(invalidations, ['network'])
})

test('upload client resolves the base url per upload and strips its trailing slash', async () => {
  const { runtime, calls } = createUploadRuntime({
    statusCode: 200,
    data: JSON.stringify({ code: 0, data: { ok: true } })
  })
  let resolutions = 0
  const upload = createUploadClient({
    runtime,
    baseUrl: 'https://api.example.test/api/v1',
    resolveBaseUrl: async () => {
      resolutions += 1
      return 'http://127.0.0.1:8000/api/v1/'
    }
  })

  await upload('/profiles/pets/p_1/photos', 'wxfile://tmp_p.jpg')

  assert.equal(resolutions, 1)
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/profiles/pets/p_1/photos')
})

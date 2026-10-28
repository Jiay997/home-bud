import test from 'node:test'
import assert from 'node:assert/strict'
import { createMediaImageLoader, isRemoteUrl } from '../src/services/media-image.ts'

function createRuntime(handler) {
  const calls = []
  const runtime = {
    downloadFile: (options) => {
      calls.push(options)
      handler(options, calls.length)
    }
  }
  return { runtime, calls }
}

test('resolve downloads once and serves later calls from cache', async () => {
  const { runtime, calls } = createRuntime((options) => {
    options.success({ statusCode: 200, tempFilePath: 'wxfile://tmp_a.jpg' })
  })
  const loader = createMediaImageLoader({ runtime })
  const url = 'http://192.168.1.5:8000/media/children/a.jpg'

  assert.equal(await loader.resolve(url), 'wxfile://tmp_a.jpg')
  assert.equal(loader.cached(url), 'wxfile://tmp_a.jpg')
  assert.equal(await loader.resolve(url), 'wxfile://tmp_a.jpg')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, url)
  assert.equal(calls[0].timeout, 30000)
})

test('concurrent resolves share a single in-flight download', async () => {
  const pending = []
  const { runtime, calls } = createRuntime((options) => { pending.push(options) })
  const loader = createMediaImageLoader({ runtime })
  const url = 'http://192.168.1.5:8000/media/pets/b.jpg'

  const first = loader.resolve(url)
  const second = loader.resolve(url)
  assert.equal(calls.length, 1)

  pending[0].success({ statusCode: 200, tempFilePath: 'wxfile://tmp_b.jpg' })
  assert.equal(await first, 'wxfile://tmp_b.jpg')
  assert.equal(await second, 'wxfile://tmp_b.jpg')
  assert.equal(calls.length, 1)
})

test('failures reject with the runtime error and allow a later retry', async () => {
  let attempt = 0
  const { runtime, calls } = createRuntime((options) => {
    attempt += 1
    if (attempt === 1) options.fail({ errMsg: 'downloadFile:fail timeout' })
    else options.success({ statusCode: 200, tempFilePath: 'wxfile://tmp_c.jpg' })
  })
  const loader = createMediaImageLoader({ runtime })
  const url = 'http://192.168.1.5:8000/media/children/c.jpg'

  await assert.rejects(loader.resolve(url), (error) => {
    assert.equal(error.message, 'downloadFile:fail timeout')
    return true
  })
  assert.equal(loader.cached(url), '')
  assert.equal(await loader.resolve(url), 'wxfile://tmp_c.jpg')
  assert.equal(calls.length, 2)
})

test('missing temp files and http error statuses reject without caching', async () => {
  const { runtime } = createRuntime((options, index) => {
    if (index === 1) options.success({ statusCode: 200, tempFilePath: '' })
    else options.success({ statusCode: 404, tempFilePath: 'wxfile://tmp_404.jpg' })
  })
  const loader = createMediaImageLoader({ runtime })

  await assert.rejects(loader.resolve('http://192.168.1.5:8000/media/children/d.jpg'), (error) => {
    assert.equal(error.message, '图片下载失败：未取得本地文件')
    return true
  })
  await assert.rejects(loader.resolve('http://192.168.1.5:8000/media/children/e.jpg'), (error) => {
    assert.equal(error.message, '图片下载失败：HTTP 404')
    return true
  })
  assert.equal(loader.cached('http://192.168.1.5:8000/media/children/d.jpg'), '')
  assert.equal(loader.cached('http://192.168.1.5:8000/media/children/e.jpg'), '')
})

test('empty urls reject immediately without touching the runtime', async () => {
  const { runtime, calls } = createRuntime(() => undefined)
  const loader = createMediaImageLoader({ runtime })

  await assert.rejects(loader.resolve(''), () => true)
  assert.equal(calls.length, 0)
})

test('preferLocal passes local urls through and falls back to the remote url on failure', async () => {
  const { runtime, calls } = createRuntime((options) => {
    if (String(options.url).includes('good')) options.success({ statusCode: 200, tempFilePath: 'wxfile://tmp_g.jpg' })
    else options.fail({ errMsg: 'downloadFile:fail timeout' })
  })
  const loader = createMediaImageLoader({ runtime })

  assert.equal(await loader.preferLocal('wxfile://tmp_local.jpg'), 'wxfile://tmp_local.jpg')
  assert.equal(await loader.preferLocal(''), '')
  assert.equal(await loader.preferLocal('http://192.168.1.5:8000/media/good/g.jpg'), 'wxfile://tmp_g.jpg')
  assert.equal(await loader.preferLocal('http://192.168.1.5:8000/media/bad/b.jpg'), 'http://192.168.1.5:8000/media/bad/b.jpg')
  assert.equal(calls.length, 2)
})

test('isRemoteUrl only accepts http and https addresses', () => {
  assert.equal(isRemoteUrl('http://192.168.1.5:8000/media/a.jpg'), true)
  assert.equal(isRemoteUrl('HTTPS://cdn.example.test/a.jpg'), true)
  assert.equal(isRemoteUrl('wxfile://tmp_a.jpg'), false)
  assert.equal(isRemoteUrl('/media/children/a.jpg'), false)
  assert.equal(isRemoteUrl(''), false)
})

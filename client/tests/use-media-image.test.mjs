import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, ref } from 'vue'
import { useMediaImage } from '../src/services/use-media-image.ts'

const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

function createLoader({ cached = '', resolved = '', reject = false } = {}) {
  const calls = []
  return {
    calls,
    cached: () => cached,
    resolve: (url) => {
      calls.push(url)
      return reject ? Promise.reject(new Error('download failed')) : Promise.resolve(resolved)
    },
    preferLocal: (url) => Promise.resolve(resolved || url)
  }
}

test('a cached download swaps to the local path immediately without downloading again', () => {
  const source = ref('http://192.168.1.5:8000/media/children/a.jpg')
  const loader = createLoader({ cached: 'wxfile://tmp_cached.jpg' })
  const image = useMediaImage(() => source.value, loader)

  assert.equal(image.src.value, source.value)
  assert.equal(image.showImage.value, true)

  image.onError()
  assert.equal(image.src.value, 'wxfile://tmp_cached.jpg')
  assert.equal(image.showImage.value, true)
  assert.equal(image.failed.value, false)
  assert.equal(loader.calls.length, 0)
})

test('a failed direct load re-renders from the downloaded local file', async () => {
  const source = ref('http://192.168.1.5:8000/media/children/b.jpg')
  const loader = createLoader({ resolved: 'wxfile://tmp_b.jpg' })
  const image = useMediaImage(() => source.value, loader)

  image.onError()
  await flush()

  assert.deepEqual(loader.calls, [source.value])
  assert.equal(image.src.value, 'wxfile://tmp_b.jpg')
  assert.equal(image.showImage.value, true)
  assert.equal(image.failed.value, false)
})

test('a failed download and non-remote urls fall back to the placeholder state', async () => {
  const remote = ref('http://192.168.1.5:8000/media/children/c.jpg')
  const loader = createLoader({ reject: true })
  const image = useMediaImage(() => remote.value, loader)

  image.onError()
  await flush()
  assert.equal(image.failed.value, true)
  assert.equal(image.showImage.value, false)

  const local = ref('wxfile://tmp_local.jpg')
  const localLoader = createLoader({})
  const localImage = useMediaImage(() => local.value, localLoader)
  localImage.onError()
  assert.equal(localImage.failed.value, true)
  assert.equal(localLoader.calls.length, 0)
})

test('changing the url resets the failure and localised state', async () => {
  const source = ref('http://192.168.1.5:8000/media/children/d.jpg')
  const loader = createLoader({ reject: true })
  const image = useMediaImage(() => source.value, loader)

  image.onError()
  await flush()
  assert.equal(image.failed.value, true)

  source.value = 'http://192.168.1.5:8000/media/children/e.jpg'
  await nextTick()
  assert.equal(image.failed.value, false)
  assert.equal(image.showImage.value, true)
  assert.equal(image.src.value, source.value)
})

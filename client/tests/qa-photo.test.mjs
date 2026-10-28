import test from 'node:test'
import assert from 'node:assert/strict'
import { createQaPhotoService, isQaPhotoRejected, qaPhotoLimitCopy } from '../src/services/qa-photo.ts'

function createRuntime(toasts) {
  return {
    chooseMedia() {},
    showLoading() {},
    hideLoading() {},
    showToast: (options) => { toasts.push(options.title) }
  }
}

test('photo upload collects uids and reports partial failures without blocking the question', async () => {
  const toasts = []
  const service = createQaPhotoService({
    runtime: createRuntime(toasts),
    upload: {
      uploadQaPhoto: async (filePath) => {
        if (filePath === 'bad.jpg') throw new Error('图片上传失败，请稍后重试。')
        return { photo_uid: `photo-${filePath}` }
      }
    }
  })

  const batch = await service.upload(
    [{ tempFilePath: 'a.jpg' }, { tempFilePath: 'bad.jpg' }, { tempFilePath: 'c.jpg' }],
    'rash'
  )
  assert.deepEqual(batch.photoUids, ['photo-a.jpg', 'photo-c.jpg'])
  assert.equal(batch.uploaded, 2)
  assert.equal(batch.failed, 1)
  assert.equal(batch.rejected, false)
  assert.deepEqual(toasts, ['部分图片上传失败，已跳过'])
})

test('1303 moderation/quota rejection stops immediately and keeps no quota-consuming intent', async () => {
  const toasts = []
  let calls = 0
  const service = createQaPhotoService({
    runtime: createRuntime(toasts),
    upload: {
      uploadQaPhoto: async () => {
        calls += 1
        const error = new Error('图片未通过内容安全送检')
        error.code = 1303
        throw error
      }
    }
  })

  const batch = await service.upload([{ tempFilePath: 'a.jpg' }, { tempFilePath: 'b.jpg' }], 'rash')
  assert.equal(batch.rejected, true)
  assert.deepEqual(batch.photoUids, [])
  // 首张被拒即停止，不再继续上传剩余图片（避免继续消耗送检配额）
  assert.equal(calls, 1)
  assert.equal(toasts.length, 1)
  assert.match(toasts[0], /不计提问次数/)
})

test('rejection detection recognises the backend business code only', () => {
  const rejected = new Error('x')
  rejected.code = 1303
  assert.equal(isQaPhotoRejected(rejected), true)
  assert.equal(isQaPhotoRejected(new Error('x')), false)
  assert.equal(isQaPhotoRejected(null), false)
})

test('picker caps the remaining count and treats user cancel as canceled', async () => {
  const service = createQaPhotoService({
    runtime: {
      chooseMedia: (options) => {
        assert.equal(options.count, 2)
        assert.deepEqual(options.sourceType, ['camera'])
        options.fail({ errMsg: 'chooseMedia:fail cancel' })
      },
      showLoading() {},
      hideLoading() {},
      showToast() {}
    },
    upload: { uploadQaPhoto: async () => ({ photo_uid: 'p' }) }
  })

  assert.equal(await service.pick('camera', 3, 2), null)
  assert.equal(qaPhotoLimitCopy, '单次最多参考三张图片')
})

test('picker surfaces a hard failure with user-facing Chinese copy', async () => {
  const service = createQaPhotoService({
    runtime: {
      chooseMedia: (options) => { options.fail({ errMsg: 'chooseMedia:fail auth deny' }) },
      showLoading() {},
      hideLoading() {},
      showToast() {}
    },
    upload: { uploadQaPhoto: async () => ({ photo_uid: 'p' }) }
  })

  await assert.rejects(() => service.pick('album', 3, 3), /无法打开相机或相册/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileMediaService, PHOTO_BATCH_LIMIT } from '../src/services/profile-media.ts'

function createHarness(pick) {
  const calls = { choose: [], loading: [], toasts: [], uploads: [] }
  const runtime = {
    chooseMedia: (options) => {
      calls.choose.push(options)
      if (pick === 'cancel') options.fail({ errMsg: 'chooseMedia:fail cancel' })
      else if (pick === 'deny') options.fail({ errMsg: 'chooseMedia:fail auth deny' })
      else options.success({ tempFiles: pick })
    },
    showLoading: (options) => calls.loading.push(`show:${options.title}`),
    hideLoading: () => calls.loading.push('hide'),
    showToast: (options) => calls.toasts.push(options.title)
  }
  return { calls, runtime }
}

function createUploadStub(calls, { avatar, photo } = {}) {
  return {
    uploadProfileAvatar: async (kind, uid, filePath) => {
      calls.uploads.push({ type: 'avatar', kind, uid, filePath })
      if (avatar instanceof Error) throw avatar
      return avatar || { avatar_url: '/media/children/a.jpg' }
    },
    addProfilePhoto: async (kind, uid, filePath) => {
      calls.uploads.push({ type: 'photo', kind, uid, filePath })
      if (photo instanceof Error) throw photo
      return photo || { count: calls.uploads.length, limit: 30 }
    }
  }
}

test('avatar flow uploads the picked image and reports the new url', async () => {
  const { calls, runtime } = createHarness([{ tempFilePath: 'wxfile://tmp_a.jpg' }])
  const service = createProfileMediaService({ runtime, upload: createUploadStub(calls) })

  const result = await service.changeAvatar('children', 'c_1', 'album')

  assert.deepEqual(result, { status: 'updated', url: '/media/children/a.jpg' })
  assert.deepEqual(calls.uploads, [{ type: 'avatar', kind: 'children', uid: 'c_1', filePath: 'wxfile://tmp_a.jpg' }])
  assert.equal(calls.choose[0].count, 1)
  assert.deepEqual(calls.choose[0].sourceType, ['album'])
  assert.deepEqual(calls.loading, ['show:正在上传头像…', 'hide'])
  assert.deepEqual(calls.toasts, ['头像已更新'])
  assert.deepEqual(calls.choose[0].sizeType, ['compressed'])
})

test('avatar flow stays silent when the user cancels the picker', async () => {
  const { calls, runtime } = createHarness('cancel')
  const service = createProfileMediaService({ runtime, upload: createUploadStub(calls) })

  const result = await service.changeAvatar('children', 'c_1', 'camera')

  assert.deepEqual(result, { status: 'canceled' })
  assert.deepEqual(calls.uploads, [])
  assert.deepEqual(calls.toasts, [])
})

test('avatar flow surfaces backend validation messages and hides the loading mask', async () => {
  const { calls, runtime } = createHarness([{ tempFilePath: 'wxfile://tmp_bad.gif' }])
  const service = createProfileMediaService({
    runtime,
    upload: createUploadStub(calls, { avatar: new Error('图片格式不支持或文件过大，请换一张试试。') })
  })

  const result = await service.changeAvatar('children', 'c_1', 'album')

  assert.deepEqual(result, { status: 'failed' })
  assert.deepEqual(calls.loading, ['show:正在上传头像…', 'hide'])
  assert.deepEqual(calls.toasts, ['图片格式不支持或文件过大，请换一张试试。'])
})

test('avatar flow falls back to a plain copy for non-chinese upload errors', async () => {
  const { calls, runtime } = createHarness([{ tempFilePath: 'wxfile://tmp_c.jpg' }])
  const service = createProfileMediaService({
    runtime,
    upload: createUploadStub(calls, { avatar: new Error('uploadFile:fail timeout') })
  })

  const result = await service.changeAvatar('pets', 'p_1', 'album')

  assert.deepEqual(result, { status: 'failed' })
  assert.deepEqual(calls.toasts, ['上传失败，请稍后重试。'])
})

test('photo batch uploads sequentially and reports partial failures', async () => {
  const files = [{ tempFilePath: 'wxfile://a.jpg' }, { tempFilePath: 'wxfile://b.jpg' }, { tempFilePath: 'wxfile://c.jpg' }]
  const { calls, runtime } = createHarness(files)
  const upload = createUploadStub(calls)
  const service = createProfileMediaService({
    runtime,
    upload: {
      uploadProfileAvatar: upload.uploadProfileAvatar,
      addProfilePhoto: async (kind, uid, filePath) => {
        calls.uploads.push({ type: 'photo', kind, uid, filePath })
        if (filePath === 'wxfile://b.jpg') throw new Error('request:fail timeout')
        return { count: calls.uploads.length, limit: 30 }
      }
    }
  })

  const result = await service.addPhotos('children', 'c_1', 10)

  assert.deepEqual(result, { canceled: false, added: 2, failed: 1 })
  assert.deepEqual(calls.uploads.map((item) => item.filePath), ['wxfile://a.jpg', 'wxfile://b.jpg', 'wxfile://c.jpg'])
  assert.equal(calls.choose[0].count, PHOTO_BATCH_LIMIT)
  assert.deepEqual(calls.choose[0].sourceType, ['album', 'camera'])
  assert.deepEqual(calls.loading, ['show:正在上传 1/3…', 'show:正在上传 2/3…', 'show:正在上传 3/3…', 'hide'])
  assert.deepEqual(calls.toasts, ['已添加 2 张，1 张失败'])
})

test('photo batch clamps the picker count to the remaining quota and the per-batch limit', async () => {
  const { calls, runtime } = createHarness([{ tempFilePath: 'wxfile://a.jpg' }])
  const service = createProfileMediaService({ runtime, upload: createUploadStub(calls) })

  await service.addPhotos('children', 'c_1', PHOTO_BATCH_LIMIT + 5)
  await service.addPhotos('children', 'c_1', 2)

  assert.equal(calls.choose[0].count, PHOTO_BATCH_LIMIT)
  assert.equal(calls.choose[1].count, 2)
})

test('photo batch refuses to open the picker when the quota is exhausted', async () => {
  const { calls, runtime } = createHarness([{ tempFilePath: 'wxfile://a.jpg' }])
  const service = createProfileMediaService({ runtime, upload: createUploadStub(calls) })

  const result = await service.addPhotos('children', 'c_1', 0)

  assert.deepEqual(result, { canceled: true, added: 0, failed: 0 })
  assert.deepEqual(calls.choose, [])
  assert.deepEqual(calls.toasts, ['相册数量已达上限'])
})

test('photo batch reports a single fallback toast when every upload fails', async () => {
  const { calls, runtime } = createHarness([{ tempFilePath: 'wxfile://a.jpg' }, { tempFilePath: 'wxfile://b.jpg' }])
  const service = createProfileMediaService({
    runtime,
    upload: createUploadStub(calls, { photo: new Error('request:fail timeout') })
  })

  const result = await service.addPhotos('pets', 'p_1', 5)

  assert.deepEqual(result, { canceled: false, added: 0, failed: 2 })
  assert.deepEqual(calls.toasts, ['上传失败，请稍后重试。'])
})

test('photo batch stays silent when the user cancels the picker', async () => {
  const { calls, runtime } = createHarness('cancel')
  const service = createProfileMediaService({ runtime, upload: createUploadStub(calls) })

  const result = await service.addPhotos('children', 'c_1', 6)

  assert.deepEqual(result, { canceled: true, added: 0, failed: 0 })
  assert.deepEqual(calls.toasts, [])
})

test('picker failures that are not cancellations surface a permission hint', async () => {
  const { calls, runtime } = createHarness('deny')
  const service = createProfileMediaService({ runtime, upload: createUploadStub(calls) })

  const result = await service.changeAvatar('children', 'c_1', 'album')

  assert.deepEqual(result, { status: 'failed' })
  assert.deepEqual(calls.toasts, ['无法打开相册或相机，请检查权限后重试。'])
})

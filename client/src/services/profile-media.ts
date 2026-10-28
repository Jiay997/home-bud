import { userFacingMessage } from './user-message.ts'

export type ProfileKind = 'children' | 'pets'
export type MediaSource = 'album' | 'camera'

export interface ChosenFile {
  /** 平台文件引用：小程序为临时文件路径；H5 为 File 对象 */
  tempFilePath: string | Blob
}

export interface ProfileMediaRuntime {
  chooseMedia(options: Record<string, unknown>): void
  showLoading(options: { title: string; mask?: boolean }): void
  hideLoading(): void
  showToast(options: { title: string; icon: 'none' }): void
}

export interface ProfileMediaUpload {
  uploadProfileAvatar(kind: ProfileKind, uid: string, filePath: string | Blob): Promise<{ avatar_url: string }>
  addProfilePhoto(kind: ProfileKind, uid: string, filePath: string | Blob): Promise<{ count: number; limit: number }>
}

export type AvatarChangeResult =
  | { status: 'updated'; url: string }
  | { status: 'canceled' }
  | { status: 'failed' }

export interface PhotoBatchResult {
  canceled: boolean
  added: number
  failed: number
}

// chooseMedia 单次最多 9 张；批量上传逐张串行，避免并发打满弱网
export const PHOTO_BATCH_LIMIT = 9

const UPLOAD_FAILED_COPY = '上传失败，请稍后重试。'
const PICK_FAILED_COPY = '无法打开相册或相机，请检查权限后重试。'
const LIMIT_COPY = '相册数量已达上限'

function isCancelError(error: unknown): boolean {
  const message = error instanceof Error
    ? error.message
    : typeof error === 'string'
      ? error
      : String((error as { errMsg?: string } | null)?.errMsg || '')
  return message.includes('cancel')
}

function chooseFiles(
  runtime: ProfileMediaRuntime,
  options: { count: number; sources: MediaSource[] }
): Promise<ChosenFile[] | null> {
  return new Promise((resolve, reject) => {
    runtime.chooseMedia({
      count: options.count,
      mediaType: ['image'],
      sourceType: options.sources,
      sizeType: ['compressed'],
      success: (result: any) => {
        const files: ChosenFile[] = Array.isArray(result?.tempFiles)
          // tempFilePath 小程序为路径字符串、H5 为 File 对象，此处只做真值校验
          ? result.tempFiles.filter((file: any) => file && file.tempFilePath)
          : []
        resolve(files)
      },
      fail: (error: any) => {
        if (isCancelError(error)) resolve(null)
        else reject(new Error(String(error?.errMsg || PICK_FAILED_COPY)))
      }
    })
  })
}

export function createProfileMediaService({
  runtime,
  upload
}: {
  runtime: ProfileMediaRuntime
  upload: ProfileMediaUpload
}) {
  return {
    // 头像：ActionSheet 选定来源后单张选择 → 立即上传（覆盖旧图由服务端处理）
    async changeAvatar(kind: ProfileKind, uid: string, source: MediaSource): Promise<AvatarChangeResult> {
      let files: ChosenFile[] | null
      try {
        files = await chooseFiles(runtime, { count: 1, sources: [source] })
      } catch (error) {
        runtime.showToast({ title: userFacingMessage(error, PICK_FAILED_COPY), icon: 'none' })
        return { status: 'failed' }
      }
      const file = files && files[0]
      if (!file) return { status: 'canceled' }

      runtime.showLoading({ title: '正在上传头像…', mask: true })
      try {
        const result = await upload.uploadProfileAvatar(kind, uid, file.tempFilePath)
        runtime.hideLoading()
        runtime.showToast({ title: '头像已更新', icon: 'none' })
        return { status: 'updated', url: result.avatar_url }
      } catch (error) {
        runtime.hideLoading()
        runtime.showToast({ title: userFacingMessage(error, UPLOAD_FAILED_COPY), icon: 'none' })
        return { status: 'failed' }
      }
    },

    // 相册：多选（受剩余配额与单批 9 张上限约束）→ 逐张串行上传 → 汇总结果
    async addPhotos(kind: ProfileKind, uid: string, remaining: number): Promise<PhotoBatchResult> {
      const count = Math.min(PHOTO_BATCH_LIMIT, Math.max(0, Math.floor(remaining)))
      if (count <= 0) {
        runtime.showToast({ title: LIMIT_COPY, icon: 'none' })
        return { canceled: true, added: 0, failed: 0 }
      }

      let files: ChosenFile[] | null
      try {
        files = await chooseFiles(runtime, { count, sources: ['album', 'camera'] })
      } catch (error) {
        runtime.showToast({ title: userFacingMessage(error, PICK_FAILED_COPY), icon: 'none' })
        return { canceled: false, added: 0, failed: 0 }
      }
      if (!files || !files.length) return { canceled: true, added: 0, failed: 0 }

      const total = files.length
      let added = 0
      let failed = 0
      let lastError: unknown = null
      for (let index = 0; index < total; index += 1) {
        runtime.showLoading({ title: `正在上传 ${index + 1}/${total}…`, mask: true })
        try {
          await upload.addProfilePhoto(kind, uid, files[index].tempFilePath)
          added += 1
        } catch (error) {
          failed += 1
          lastError = error
        }
      }
      runtime.hideLoading()

      if (failed === 0) {
        runtime.showToast({ title: `已添加 ${added} 张照片`, icon: 'none' })
      } else if (added > 0) {
        runtime.showToast({ title: `已添加 ${added} 张，${failed} 张失败`, icon: 'none' })
      } else {
        runtime.showToast({ title: userFacingMessage(lastError, UPLOAD_FAILED_COPY), icon: 'none' })
      }
      return { canceled: false, added, failed }
    }
  }
}

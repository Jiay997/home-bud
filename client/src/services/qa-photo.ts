/**
 * 图片提问编排（RQ-05）：
 *
 * 顺序为「场景说明 → 选图（相机 / 相册）→ 逐张上传送检 → 以图片形态创建会话」。
 * 平台差异（chooseMedia / loading / toast）全部经注入的 runtime 抹平，本模块不直接
 * 调用 uni API，因此小程序与 H5 复用同一套编排逻辑，且可在 node 下单测。
 *
 * 合规口径（AC-RQ05-2 / AC-RQ05-8）：
 * - 单次最多 3 张，由服务端下发的 `max_count` 约束，超出即截断并提示；
 * - 图片只用于本次解析，服务端 24 小时内删除原图，本模块不上传、不展示、不缓存原图；
 * - 送检未通过或配额超限（1303）立即停止且**不扣额度**，不回退为「跳过送检直接提问」。
 */
import { userFacingMessage } from './user-message.ts'

/** 选图来源：相机 / 相册（H5 均退化为文件选择器） */
export type QaPhotoSource = 'camera' | 'album'

/** 平台文件引用：小程序为临时文件路径；H5 为 File 对象 */
export interface QaPhotoFile {
  tempFilePath: string | Blob
}

export interface QaPhotoRuntime {
  chooseMedia(options: Record<string, unknown>): void
  showLoading(options: { title: string; mask?: boolean }): void
  hideLoading(): void
  showToast(options: { title: string; icon: 'none' }): void
}

export interface QaPhotoUploader {
  uploadQaPhoto(filePath: string | Blob, scene: string): Promise<{ photo_uid: string }>
}

export interface QaPhotoBatch {
  /** 送检通过的图片标识（≤ maxCount） */
  photoUids: string[]
  /** 是否因送检未通过 / 配额超限被拒（此时不得继续创建会话） */
  rejected: boolean
  /** 是否用户取消选图 */
  canceled: boolean
  /** 已上传成功张数 */
  uploaded: number
  /** 逐张上传失败张数（非 1303） */
  failed: number
  /** 可直接展示的结果文案（空串表示无需提示） */
  message: string
}

const PICK_FAILED_COPY = '无法打开相机或相册，可改用文字提问。'
const UPLOAD_FAILED_COPY = '图片上传失败，请稍后重试。'
const REJECTED_COPY = '图片未通过内容安全送检或今日额度不足，本次不计提问次数。'
const PARTIAL_COPY = '部分图片上传失败，已跳过'
const LIMIT_COPY = '单次最多参考三张图片'

/** 1303：送检未通过 / 图片配额超限（不扣额度） */
export function isQaPhotoRejected(error: unknown): boolean {
  const code = Number((error as { code?: unknown } | null)?.code)
  return code === 1303
}

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return String((error as { errMsg?: string } | null)?.errMsg || '')
}

function isCancelError(error: unknown): boolean {
  return errorText(error).includes('cancel')
}

export function createQaPhotoService({
  runtime,
  upload
}: {
  runtime: QaPhotoRuntime
  upload: QaPhotoUploader
}) {
  return {
    /**
     * 选择图片（受单次张数上限约束）。
     * @param source 选图来源
     * @param maxCount 单次上限（服务端下发）
     * @param remaining 还可用张数（已选张数扣减后）
     * @returns 选中的文件；取消返回 null（失败抛错由调用方提示）
     */
    pick(source: QaPhotoSource, maxCount: number, remaining: number): Promise<QaPhotoFile[] | null> {
      const count = Math.max(0, Math.min(maxCount, remaining))
      if (count <= 0) return Promise.resolve([])
      return new Promise((resolve, reject) => {
        runtime.chooseMedia({
          count,
          mediaType: ['image'],
          sourceType: [source],
          sizeType: ['compressed'],
          success: (result: any) => {
            const files: QaPhotoFile[] = Array.isArray(result?.tempFiles)
              ? result.tempFiles
                  .filter((file: any) => file && file.tempFilePath)
                  .map((file: any) => ({ tempFilePath: file.tempFilePath }))
              : []
            resolve(files)
          },
          fail: (error: any) => {
            if (isCancelError(error)) resolve(null)
            else reject(new Error(PICK_FAILED_COPY))
          }
        })
      })
    },

    /**
     * 逐张上传并送检（串行，避免并发打满弱网）。
     * @param files 待上传文件
     * @param scene 场景枚举
     * @returns 上传批次结果（1303 立即停止且 rejected=true）
     */
    async upload(files: QaPhotoFile[], scene: string): Promise<QaPhotoBatch> {
      const photoUids: string[] = []
      let failed = 0
      let message = ''
      const total = files.length
      for (let index = 0; index < total; index += 1) {
        runtime.showLoading({ title: `正在上传 ${index + 1}/${total}…`, mask: true })
        try {
          const result = await upload.uploadQaPhoto(files[index].tempFilePath, scene)
          if (result?.photo_uid) photoUids.push(result.photo_uid)
        } catch (error: unknown) {
          runtime.hideLoading()
          if (isQaPhotoRejected(error)) {
            // 1303：服务端已拒绝（送检未通过 / 配额超限），明确告知本次不计提问次数
            const detail = userFacingMessage(error, '').replace(/[。.]$/, '')
            const title = detail ? `${detail}；本次不计提问次数` : REJECTED_COPY
            runtime.showToast({ title, icon: 'none' })
            return { photoUids, rejected: true, canceled: false, uploaded: photoUids.length, failed, message }
          }
          // 非 1303：记录失败并继续下一张（已有成功项时仍可提问）
          failed += 1
          message = userFacingMessage(error, UPLOAD_FAILED_COPY)
        }
      }
      runtime.hideLoading()
      if (failed > 0) {
        runtime.showToast({
          title: photoUids.length ? PARTIAL_COPY : message || UPLOAD_FAILED_COPY,
          icon: 'none'
        })
      }
      return { photoUids, rejected: false, canceled: false, uploaded: photoUids.length, failed, message }
    }
  }
}

/** 单次张数上限提示文案（供页面在超限时展示） */
export const qaPhotoLimitCopy = LIMIT_COPY

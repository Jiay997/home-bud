import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { createMediaImageLoader, isRemoteUrl, type MediaImageLoader } from './media-image.ts'
// 显式写全 index.ts：node --test 以原生 ESM 直接导入本模块时不做目录解析
import { runtime } from '../platform/runtime/index.ts'

// 全局共享一份图片地址缓存：跨页面/跨实例复用已本地化地址，避免重复下载。
// 平台差异由 runtime 抹平：小程序真机经 downloadFile 本地化，H5 直接复用原地址。
export const mediaImages = createMediaImageLoader({
  runtime: { downloadFile: (options) => runtime.downloadFile(options) }
})

export interface MediaImageBinding {
  src: ComputedRef<string>
  showImage: ComputedRef<boolean>
  failed: Ref<boolean>
  onError(): void
}

// 单个图片位（头像等）的自愈绑定：直连失败 → 下载到本地 → 换 src 重渲染；
// 本地文件仍失败或非网络地址时置 failed，由调用方回退默认样式。
export function useMediaImage(url: () => string, loader: MediaImageLoader = mediaImages): MediaImageBinding {
  const local = ref('')
  const failed = ref(false)

  watch(url, () => {
    local.value = ''
    failed.value = false
  })

  const src = computed(() => local.value || url() || '')
  const showImage = computed(() => Boolean(url()) && !failed.value)

  function onError() {
    const remote = String(url() || '')
    if (!remote) return
    if (local.value || !isRemoteUrl(remote)) {
      failed.value = true
      return
    }
    const hit = loader.cached(remote)
    if (hit) {
      local.value = hit
      return
    }
    void loader
      .resolve(remote)
      .then((path) => {
        if (url() === remote) local.value = path
      })
      .catch(() => {
        if (url() === remote) failed.value = true
      })
  }

  return { src, showImage, failed, onError }
}

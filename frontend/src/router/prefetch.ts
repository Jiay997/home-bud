/**
 * 空闲预取：首屏渲染后利用浏览器空闲时间预加载主要页面的懒加载分包，
 * 让首次进入各 Tab / 问答 / 测评页不再等待 chunk 请求（页面切换更顺畅）。
 * - 尊重 saveData（省流模式）：开启时不预取；
 * - 单个分包加载失败静默忽略，不影响路由的正常按需加载。
 */
const PREFETCH_TASKS: Array<() => Promise<unknown>> = [
  () => import('@/views/app/HomePage.vue'),
  () => import('@/views/app/ProfileListPage.vue'),
  () => import('@/views/app/HistoryListPage.vue'),
  () => import('@/views/app/MePage.vue'),
  () => import('@/views/app/QaSessionPage.vue'),
  () => import('@/views/app/PetQaSessionPage.vue'),
  () => import('@/views/app/FamilyQaPage.vue'),
  () => import('@/views/app/AssessmentIntroPage.vue')
]

export function prefetchAppRoutes(): void {
  const nav = navigator as Navigator & { connection?: { saveData?: boolean } }
  if (nav.connection?.saveData) return
  const run = () => {
    for (const load of PREFETCH_TASKS) void load().catch(() => undefined)
  }
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(run, { timeout: 4000 })
  } else {
    window.setTimeout(run, 1500)
  }
}

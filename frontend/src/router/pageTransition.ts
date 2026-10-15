/**
 * 页面切换过渡：方向判定与滚动补偿
 * - 方向（forward/back/fade）由前后路由的层级深度决定：更深=前进、更浅=返回、同级=淡入；
 *   特例路由可用 meta.transition 强制覆盖（如风险拦截页不编排方向动效）。
 * - 退场页冻结补偿（styles/motion.scss 以 top 消费）：导航开始时把当前滚动记为
 *   --page-leave-top（来源滚动），scrollBehavior 触发时把本次跳转目标位置记为
 *   --page-leave-dest（目的滚动，前进/同级为 0，返回为历史保存位置）。
 *   两个值都不为 0 时相差即补偿量：退场页 top = dest − src，恰好抵消同帧发生的
 *   滚动跳转，画面保持在导航瞬间所见的滚动位置（原生返回手势的"页面冻结"效果）。
 *   时序保证：scrollBehavior 在 DOM 更新后的微任务里执行、早于绘制，变量写回
 *   与过渡类是同一帧生效，首帧即正确。
 */
import type { RouteLocationNormalized, Router, RouterScrollBehavior } from 'vue-router'
import { reactive } from 'vue'

export type PageTransitionDirection = 'forward' | 'back' | 'fade'

/** 当前导航的过渡方向（MobileLayout 的 <Transition :name> 消费） */
export const pageTransition = reactive({
  direction: 'fade' as PageTransitionDirection,
})

/** 退场页冻结偏移的 CSS 变量（styles/motion.scss 消费） */
const LEAVE_TOP_VAR = '--page-leave-top'
/** 本次导航滚动跳转的目标位置（返回=历史保存位置；前进/同级=0） */
const LEAVE_DEST_VAR = '--page-leave-dest'
/** 上次写入的滚动值：相同则不重写，避免每次导航都触发 :root 全量样式重算 */
let lastLeaveTop = -1
let lastLeaveDest = -1

/** 路由层级深度：只看路径段数，多段子路由（如 /app/qa/parenting）也单调递增 */
function depth(path: string): number {
  return path.split('/').filter(Boolean).length
}

/**
 * 判定本次导航的过渡方向。
 * 层级关系是页面结构自身的事实，无需逐页手工标注。
 */
function resolveDirection(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized
): PageTransitionDirection {
  const forced = to.meta?.transition as PageTransitionDirection | undefined
  if (forced === 'forward' || forced === 'back' || forced === 'fade') return forced
  if (!from.matched.length) return 'fade' // 首次进入（含深链）不做方向编排
  const dTo = depth(to.path)
  const dFrom = depth(from.path)
  if (dTo > dFrom) return 'forward'
  if (dTo < dFrom) return 'back'
  return 'fade'
}

/** 注册导航守卫：每次导航前捕获方向与滚动位置（先于布局渲染与过渡类应用） */
export function installPageTransition(router: Router): void {
  router.beforeEach((to, from) => {
    // 新导航立即作废旧页面的返回恢复复补：避免旧目标跳转到新页面
    reassertCleanup?.()
    pageTransition.direction = resolveDirection(to, from)
    const top = window.scrollY || 0
    if (top !== lastLeaveTop) {
      document.documentElement.style.setProperty(LEAVE_TOP_VAR, `${top}px`)
      lastLeaveTop = top
    }
  })
}

/**
 * router 的 scrollBehavior 实现（在 router 配置里直接引用）。
 * 先把本次跳转的目标滚动位置写回 CSS 变量再定位：该函数在 DOM 更新后的
 * 微任务里执行、早于首帧绘制，与退场类同帧生效。
 * 定位策略：有历史位置则恢复（返回时回到离开时的滚动），否则回顶。
 */
export const pageScrollBehavior: RouterScrollBehavior = (_to, _from, savedPosition) => {
  const dest = savedPosition?.top ?? 0
  if (dest !== lastLeaveDest) {
    document.documentElement.style.setProperty(LEAVE_DEST_VAR, `${dest}px`)
    lastLeaveDest = dest
  }
  if (dest > 0) scheduleScrollReassert(dest)
  if (savedPosition) return savedPosition
  return { top: 0 }
}

/** 上一轮恢复复补的收尾句柄（新导航到来时先收尾，避免叠加） */
let reassertCleanup: (() => void) | null = null
/** 钳制判断的容差：scrollHeight 取整、恢复值可能带小数，差一点也要算“高度已允许” */
const TOLERANCE = 2

/**
 * 返回恢复的位置会被"骨架屏"阶段的瞬时矮高度钳制（数据到达后页面变高、
 * 位置却停在低处）。随后窗口内（40×100ms，约 4s，覆盖弱网首屏 2–4s 的到达）
 * 按需复补到目标位置：文档高度一旦允许就补跳；用户主动滚动（滚轮/触摸）
 * 或新的导航（beforeEach 里取消）立即放弃，让位给用户/新页面意图。
 */
function scheduleScrollReassert(dest: number): void {
  reassertCleanup?.()
  const docEl = document.documentElement
  let timer = 0
  let ticks = 0
  const finish = () => {
    window.removeEventListener('wheel', finish)
    window.removeEventListener('touchstart', finish)
    window.clearTimeout(timer)
    if (reassertCleanup === finish) reassertCleanup = null
  }
  const tick = () => {
    const y = window.scrollY
    if (y >= dest - TOLERANCE) {
      finish() // 已就位（首跳未被钳制，或被用户/浏览器自行修正）
      return
    }
    if (docEl.scrollHeight - window.innerHeight >= dest - TOLERANCE) {
      window.scrollTo(0, dest)
      finish()
      return
    }
    if (++ticks < 40) timer = window.setTimeout(tick, 100)
    else finish()
  }
  window.addEventListener('wheel', finish, { passive: true })
  window.addEventListener('touchstart', finish, { passive: true })
  reassertCleanup = finish
  timer = window.setTimeout(tick, 120)
}

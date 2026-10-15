/**
 * 安全返回（web-view 场景）
 * 微信小程序 web-view 没有浏览器返回栏：外部深链直达时站内无历史
 * （history.state.back 为空），裸 router.back() 会直接退出 web-view。
 * 统一走此函数：有站内历史则回退，否则兜底跳转到首页。
 */
import type { Router } from 'vue-router'

export function safeBack(router: Router, fallback = '/app/home'): void {
  if (window.history.state?.back) {
    router.back()
  } else {
    void router.replace(fallback)
  }
}

/**
 * 软键盘避让
 * 小程序 web-view 内软键盘弹出时可视视口收窄，但布局视口不变，
 * 底部 fixed 输入区会被键盘盖住。这里用 visualViewport 计算被遮挡高度，
 * 供输入区抬升；键盘收起（遮挡 ≤ 40px 视为浏览器工具栏变化）时归零。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useKeyboardOffset() {
  const keyboardOffset = ref(0)

  function update(): void {
    const vv = window.visualViewport
    if (!vv) return
    const hidden = window.innerHeight - vv.height - vv.offsetTop
    keyboardOffset.value = hidden > 40 ? Math.round(hidden) : 0
  }

  onMounted(() => {
    const vv = window.visualViewport
    if (!vv) return
    vv.addEventListener('resize', update)
    vv.addEventListener('scroll', update)
    update()
  })

  onBeforeUnmount(() => {
    const vv = window.visualViewport
    if (!vv) return
    vv.removeEventListener('resize', update)
    vv.removeEventListener('scroll', update)
  })

  return { keyboardOffset }
}

/**
 * 主题 Store
 * 职责：深色模式开关；切换 html.dark class；
 * 首次跟随 prefers-color-scheme，用户手动切换后持久化选择。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 主题偏好键名：'light' | 'dark' | null（null = 跟随系统） */
const THEME_KEY = 'jiaban_theme'

export const useThemeStore = defineStore('theme', () => {
  /** 当前是否深色 */
  const isDark = ref(false)

  /**
   * 初始化：读取持久化偏好，否则跟随系统
   */
  function init(): void {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'dark') {
      isDark.value = true
    } else if (saved === 'light') {
      isDark.value = false
    } else {
      isDark.value =
        typeof matchMedia !== 'undefined' &&
        matchMedia('(prefers-color-scheme: dark)').matches
    }
    apply()
  }

  /**
   * 将 isDark 应用到 html 根节点 class
   */
  function apply(): void {
    document.documentElement.classList.toggle('dark', isDark.value)
  }

  /**
   * 切换深浅模式并持久化
   */
  function toggle(): void {
    isDark.value = !isDark.value
    localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
    apply()
  }

  return { isDark, init, toggle }
})

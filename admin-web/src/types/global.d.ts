/**
 * 全局属性类型声明（main.ts 注册的 $safeBack 等）
 */
declare module 'vue' {
  interface ComponentCustomProperties {
    /** 安全返回：有站内历史回退，深链直达兜底跳首页 */
    $safeBack: (fallback?: string) => void
  }
}

export {}

/**
 * 后台管理端 Vite 配置（Web-only 工程）。
 * - base 固定 /admin/：与 nginx 托管路径、vue-router history base 保持一致
 * - server.proxy：/api 同源代理到后端 8000（与生产 nginx 反代形态一致）
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  base: '/admin/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    // D-17：端口可配置（ADMIN_PORT），并启用 strictPort：端口被占用时
    // 直接失败而不是静默漂移到其它端口，避免误连到其他项目。
    port: Number(process.env.ADMIN_PORT || 5175),
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})

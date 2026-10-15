/**
 * Vite 构建配置
 * - alias: @ → src，统一模块引用路径
 * - server.port 5173：开发服务器端口
 * - server.proxy：/api 同源代理转发到后端 8000（与生产 nginx 反代形态一致，
 *   避免浏览器侧跨域与系统代理对 localhost:8000 直连的干扰）
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SSE 流式端点关闭缓冲，保证分帧即时下发
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        }
      }
    }
  }
})

/**
 * uni-app 跨端构建配置（H5 与微信小程序共用同一份工程配置）。
 *
 * 职责：
 * - 装配 uni 官方 vite 插件，由 uni CLI 按 -p 参数切换目标平台；
 * - H5 生产构建的 publicPath 固定为 /app/（nginx 以 /app/ 托管 H5 产物，小程序构建不受影响）；
 * - H5 开发服务器把 /api 代理到本地后端，避免浏览器侧跨域与系统代理干扰。
 */
import { defineConfig } from 'vite'
import * as uniModule from '@dcloudio/vite-plugin-uni'

// uni CLI 以 node 进程运行构建，此处仅声明用到的 process 形态，
// 避免为构建配置额外引入 @types/node 依赖。
declare const process: { env: Record<string, string | undefined> }

/** uni 插件导出形态兼容处理（兼容 default / default.default / 命名空间三种打包结果） */
const uniPlugin = (uniModule as any).default?.default ?? (uniModule as any).default ?? uniModule

/** 当前构建目标平台，由 uni CLI 注入（h5 / mp-weixin） */
const platform = process.env.UNI_PLATFORM

/** H5 开发期后端代理目标：可用 H5_API_PROXY 环境变量覆盖，默认本机 8000 */
const apiProxyTarget = process.env.H5_API_PROXY || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [uniPlugin()],
  // H5 产物部署在 /app/ 子路径；小程序构建下该字段不参与产物生成
  base: platform === 'h5' ? '/app/' : '/',
  server: {
    // 5173 常被本机其他前端项目占用，此处固定 5174 避免端口争用
    port: 5174,
    host: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true
      },
      // 档案头像/相册：后端 /media 静态挂载，开发期同样需要同源代理
      '/media': {
        target: apiProxyTarget,
        changeOrigin: true
      }
    }
  }
})

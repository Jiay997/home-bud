/**
 * 后台管理端应用入口。
 * 职责：创建 Vue 实例，装配 Pinia、Router 与 Element Plus（完整引入简化），
 * 并引入设计令牌样式 tokens.scss 与根级过渡样式 motion.scss。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Element Plus 深色变量层：tokens.scss 的 html.dark 覆盖在其后引入，可继续覆写
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/theme'
import './styles/tokens.scss'
import './styles/motion.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 恢复持久化的主题偏好（首次跟随系统）；必须在 mount 前应用，避免深色用户看到白屏闪烁
useThemeStore(pinia).init()

app.mount('#app')

/**
 * 后台管理端路由表（Web-only 工程）。
 *
 * 说明：C 端用户端已由 uni-app 跨端工程 `client/` 统一提供（一套代码编译到微信小程序与 H5），
 * 本工程只承载 `/admin/*` 后台页面，并以 base `/admin/` 部署在 nginx 的 /admin/ 路径下。
 *
 * 守卫：除登录页外需登录，并按后端下发 menus（meta.menuKey）做路由级角色校验；
 * 越权直访提示无权限并回退到该角色首个可用菜单页（服务端接口仍为真边界）。
 *
 * ⚠️ 路径书写约定（缺陷 D3 根因）：vue-router 的 `base` 只负责「浏览器地址栏前缀」，
 * `router.push/resolve` 的入参必须是 **base 之后的相对路径**（如 `/lexicon`），
 * 不得再带 `/admin` 前缀——带前缀会被解析成 `/admin/admin/lexicon`，命中兜底路由被
 * 重定向回 `/kb`，表现为「后台除知识库外菜单全部点不动」。
 * 因此所有编程式导航统一引用下方 `ADMIN_ROUTE` 常量，禁止在各视图里手写路径字面量。
 */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAdminInfo, getToken as getAdminToken } from '@/api/admin'

/** 路由基路径：与 vite base、nginx 托管路径保持一致 */
const ROUTER_BASE = '/admin/'

/**
 * 后台路由路径常量（base 之后的相对路径，与下方 routes 表逐字一致）。
 * 编程式导航一律使用本常量，避免再次出现 `/admin/admin/...` 的重复前缀缺陷。
 */
export const ADMIN_ROUTE = {
  login: '/login',
  kb: '/kb',
  kbEdit: (kbId: string) => `/kb/${encodeURIComponent(kbId)}/edit`,
  kbNew: '/kb/new/edit',
  lexicon: '/lexicon',
  logs: '/logs',
  feedback: '/feedback',
  risk: '/risk',
  /** 个人信息权利请求（N4：与系统开关配置拆分后的独立页） */
  rights: '/rights',
  /** 系统开关 / 价格 / AI 标识 / 灰度 / 配置同步（N4 拆分） */
  config: '/config',
  /** V3.1 危机渠道清单（RQ-03 单一数据源） */
  channels: '/channels',
  /** V3.1 分级规则（RQ-06） */
  triageRules: '/triage-rules',
  /** V3.1 内容运营（专题包 + 轻工具） */
  content: '/content',
  /** V3.1 Agent 展示权重（F12.7，仅超管） */
  weight: '/agent-weights',
  auditLogs: '/audit-logs',
  monitor: '/monitor'
} as const

/**
 * 后台菜单 key → 默认落地路径（语义与 AdminLayout MENU_DEFS 一致）。
 * 仅用于路由守卫越权回退跳转；菜单渲染仍以后端下发 menus 为单一事实来源。
 */
const ADMIN_MENU_PATHS: Record<string, string> = {
  kb: ADMIN_ROUTE.kb,
  lexicon: ADMIN_ROUTE.lexicon,
  logs: ADMIN_ROUTE.logs,
  feedback: ADMIN_ROUTE.feedback,
  risk: ADMIN_ROUTE.risk,
  rights: ADMIN_ROUTE.rights,
  config: ADMIN_ROUTE.config,
  channel: ADMIN_ROUTE.channels,
  triage: ADMIN_ROUTE.triageRules,
  content: ADMIN_ROUTE.content,
  weight: ADMIN_ROUTE.weight,
  audit: ADMIN_ROUTE.auditLogs
}

const router = createRouter({
  history: createWebHistory(ROUTER_BASE),
  routes: [
    {
      path: '/login',
      name: 'admin-login',
      component: () => import('@/views/admin/AdminLoginPage.vue'),
      meta: { title: '后台登录' }
    },
    {
      path: '/',
      component: () => import('@/views/admin/AdminLayout.vue'),
      redirect: '/kb',
      children: [
        {
          path: 'kb',
          name: 'admin-kb',
          component: () => import('@/views/admin/KbListPage.vue'),
          meta: { title: '知识库管理', menuKey: 'kb' }
        },
        {
          path: 'kb/:kbId/edit',
          name: 'admin-kb-edit',
          component: () => import('@/views/admin/KbEditPage.vue'),
          meta: { title: '条目编辑', menuKey: 'kb' }
        },
        {
          path: 'lexicon',
          name: 'admin-lexicon',
          component: () => import('@/views/admin/LexiconPage.vue'),
          meta: { title: '词库管理', menuKey: 'lexicon' }
        },
        {
          path: 'logs',
          name: 'admin-logs',
          component: () => import('@/views/admin/AgentLogPage.vue'),
          meta: { title: 'Agent 调用日志', menuKey: 'logs' }
        },
        {
          path: 'feedback',
          name: 'admin-feedback',
          component: () => import('@/views/admin/FeedbackPage.vue'),
          meta: { title: '反馈与举报', menuKey: 'feedback' }
        },
        {
          path: 'risk',
          name: 'admin-risk',
          component: () => import('@/views/admin/RiskEventPage.vue'),
          meta: { title: '高风险事件', menuKey: 'risk' }
        },
        {
          path: 'rights',
          name: 'admin-rights',
          component: () => import('@/views/admin/RightsConfigPage.vue'),
          props: { mode: 'rights' },
          meta: { title: '权利请求', menuKey: 'rights' }
        },
        {
          path: 'config',
          name: 'admin-config',
          component: () => import('@/views/admin/RightsConfigPage.vue'),
          props: { mode: 'config' },
          meta: { title: '系统开关与配置', menuKey: 'config' }
        },
        {
          path: 'channels',
          name: 'admin-channels',
          component: () => import('@/views/admin/ChannelManagePage.vue'),
          meta: { title: '危机渠道清单', menuKey: 'channel' }
        },
        {
          path: 'triage-rules',
          name: 'admin-triage-rules',
          component: () => import('@/views/admin/TriageRulePage.vue'),
          meta: { title: '分级规则', menuKey: 'triage' }
        },
        {
          path: 'content',
          name: 'admin-content',
          component: () => import('@/views/admin/ContentOpsPage.vue'),
          meta: { title: '内容运营', menuKey: 'content' }
        },
        {
          path: 'agent-weights',
          name: 'admin-agent-weights',
          component: () => import('@/views/admin/AgentWeightPage.vue'),
          meta: { title: 'Agent 展示权重', menuKey: 'weight' }
        },
        /* 兼容旧书签：原「权利请求与系统开关」合页已按 N4 拆分为 /rights 与 /config，
           旧地址（页面职责已不存在）重定向到权利请求页，不保留第三份逻辑 */
        { path: 'rights-config', redirect: ADMIN_ROUTE.rights },
        {
          path: 'audit-logs',
          name: 'admin-audit-logs',
          component: () => import('@/views/admin/AuditLogPage.vue'),
          meta: { title: '审计记录', menuKey: 'audit' }
        },
        {
          path: 'monitor',
          name: 'admin-monitor',
          component: () => import('@/views/admin/MonitorPage.vue'),
          meta: { title: '系统监控' }
        }
      ]
    },
    /* 兜底：未匹配路径回到首个可用菜单页（相对 base 的 /kb） */
    { path: '/:pathMatch(.*)*', redirect: ADMIN_ROUTE.kb }
  ]
})

/* ---------- 全局守卫 ---------- */
router.beforeEach((to) => {
  // 设置标题
  if (to.meta?.title) {
    document.title = `${to.meta.title} · Babe宝伴后台`
  }
  // 除登录页外需登录
  if (to.path !== ADMIN_ROUTE.login && !getAdminToken()) {
    return { path: ADMIN_ROUTE.login }
  }
  // 按后端下发 menus 做路由级角色校验（防越权直访）
  const menuKey = to.meta?.menuKey as string | undefined
  if (menuKey) {
    const info = getAdminInfo()
    const menus: string[] = Array.isArray(info?.menus) ? info.menus : []
    if (!menus.includes(menuKey)) {
      ElMessage.warning('当前角色无此权限')
      const fallback = menus.map((k) => ADMIN_MENU_PATHS[k]).find(Boolean)
      return fallback ? { path: fallback } : { path: ADMIN_ROUTE.login }
    }
  }
  return true
})

export default router

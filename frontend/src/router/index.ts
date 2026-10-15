/**
 * 路由表
 * 结构：
 * - / → redirect /app/home
 * - /app/* 用户端：MobileLayout 布局，meta.tab 标记底部 Tab 页；
 *   守卫：除 /app/start 外未登录跳 /app/start
 * - /admin/* 后台：真实页面（AdminLayout 布局）；
 *   守卫：除 /admin/login 外需登录，并按后端下发 menus（meta.menuKey）做路由级角色校验，
 *   越权直访提示无权限并回退到该角色首个可用菜单页（服务端接口仍为真边界）
 */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import MobileLayout from '@/layouts/MobileLayout.vue'
import { getToken } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { getAdminInfo, getToken as getAdminToken } from '@/api/admin'
import { installPageTransition, pageScrollBehavior } from './pageTransition'

const router = createRouter({
  history: createWebHistory(),
  /**
   * 滚动行为：新导航回到顶部、浏览器前进后退恢复原位置。
   * 跳转与页面切换过渡同帧发生；退场页用 --page-leave-top / --page-leave-dest
   * 冻结偏移补偿，因此在切换过程中看到的仍是原位置（见 styles/motion.scss）。
   */
  scrollBehavior: pageScrollBehavior,
  routes: [
    { path: '/', redirect: '/app/home' },
    {
      path: '/app',
      component: MobileLayout,
      children: [
        /* ---------- 启动与首页 ---------- */
        {
          path: 'start',
          name: 'start',
          component: () => import('@/views/app/StartPage.vue'),
          meta: { title: '欢迎使用小光景' }
        },
        {
          path: 'home',
          name: 'home',
          component: () => import('@/views/app/HomePage.vue'),
          meta: { tab: 'home', title: '小光景' }
        },
        /* ---------- 档案 ---------- */
        {
          path: 'profiles',
          name: 'profiles',
          component: () => import('@/views/app/ProfileListPage.vue'),
          meta: { tab: 'profiles', title: '档案' }
        },
        {
          path: 'profiles/child/new',
          name: 'child-new',
          component: () => import('@/views/app/ChildProfileForm.vue'),
          meta: { title: '新建儿童档案' }
        },
        {
          path: 'profiles/child/:uid/edit',
          name: 'child-edit',
          component: () => import('@/views/app/ChildProfileForm.vue'),
          meta: { title: '编辑儿童档案' }
        },
        {
          path: 'profiles/pet/new',
          name: 'pet-new',
          component: () => import('@/views/app/PetProfileForm.vue'),
          meta: { title: '新建宠物档案' }
        },
        {
          path: 'profiles/pet/:uid/edit',
          name: 'pet-edit',
          component: () => import('@/views/app/PetProfileForm.vue'),
          meta: { title: '编辑宠物档案' }
        },
        /* ---------- 问答 ---------- */
        {
          path: 'qa/parenting',
          name: 'qa-parenting',
          component: () => import('@/views/app/QaSessionPage.vue'),
          meta: { title: '育儿问答' }
        },
        {
          path: 'qa/pet',
          name: 'qa-pet',
          component: () => import('@/views/app/PetQaSessionPage.vue'),
          meta: { title: '宠物问答' }
        },
        {
          path: 'qa/family',
          name: 'qa-family',
          component: () => import('@/views/app/FamilyQaPage.vue'),
          meta: { title: '家庭综合问答' }
        },
        {
          path: 'risk-blocked',
          name: 'risk-blocked',
          component: () => import('@/views/app/RiskBlockPage.vue'),
          // 基线 §2.8：风险拦截无编排动效，直接呈现（禁方向滑动）
          meta: { title: '已停止生成', transition: 'fade' }
        },
        {
          path: 'appeal',
          name: 'appeal',
          component: () => import('@/views/app/AppealPage.vue'),
          meta: { title: '申诉' }
        },
        {
          path: 'answer-demo',
          name: 'answer-demo',
          component: () => import('@/views/app/AnswerCardDemo.vue'),
          meta: { title: '回答卡规范' }
        },
        /* ---------- 测评 ---------- */
        {
          path: 'assessment',
          name: 'assessment-intro',
          component: () => import('@/views/app/AssessmentIntroPage.vue'),
          meta: { title: '养育测评' }
        },
        {
          path: 'assessment/run/:uid',
          name: 'assessment-run',
          component: () => import('@/views/app/AssessmentRunPage.vue'),
          meta: { title: '测评作答' }
        },
        {
          path: 'assessment/report/:uid',
          name: 'assessment-report',
          component: () => import('@/views/app/AssessmentReportPage.vue'),
          meta: { title: '测评报告' }
        },
        {
          path: 'assessment/report/:uid/image',
          name: 'report-image',
          component: () => import('@/views/app/ReportImagePage.vue'),
          meta: { title: '报告长图' }
        },
        /* ---------- 记录 ---------- */
        {
          path: 'history',
          name: 'history',
          component: () => import('@/views/app/HistoryListPage.vue'),
          meta: { tab: 'history', title: '记录' }
        },
        {
          path: 'history/qa/:uid',
          name: 'history-qa',
          component: () => import('@/views/app/HistoryDetailPage.vue'),
          meta: { title: '问答详情' }
        },
        {
          path: 'history/report/:uid',
          name: 'history-report',
          component: () => import('@/views/app/HistoryDetailPage.vue'),
          meta: { title: '报告详情' }
        },
        /* ---------- 会员 ---------- */
        {
          path: 'member',
          name: 'member',
          component: () => import('@/views/app/MemberPage.vue'),
          meta: { title: '会员' }
        },
        {
          path: 'member/ios',
          name: 'member-ios',
          component: () => import('@/views/app/MemberIosPage.vue'),
          meta: { title: '会员 · 当前设备' }
        },
        {
          path: 'member/order',
          name: 'order',
          component: () => import('@/views/app/OrderPage.vue'),
          meta: { title: '确认订单' }
        },
        /* ---------- 我的 ---------- */
        {
          path: 'me',
          name: 'me',
          component: () => import('@/views/app/MePage.vue'),
          meta: { tab: 'me', title: '我的' }
        },
        {
          path: 'me/security',
          name: 'security',
          component: () => import('@/views/app/AccountSecurityPage.vue'),
          meta: { title: '账号安全' }
        },
        {
          path: 'me/rights',
          name: 'rights',
          component: () => import('@/views/app/RightsCenterPage.vue'),
          meta: { title: '权利中心' }
        },
        {
          path: 'me/feedback',
          name: 'feedback',
          component: () => import('@/views/app/FeedbackPage.vue'),
          meta: { title: '反馈与举报' }
        }
      ]
    },
    /* ---------- 后台管理端（真实页面） ---------- */
    {
      path: '/admin/login',
      name: 'admin-login',
      component: () => import('@/views/admin/AdminLoginPage.vue'),
      meta: { title: '后台登录' }
    },
    {
      path: '/admin',
      component: () => import('@/views/admin/AdminLayout.vue'),
      redirect: '/admin/kb',
      children: [
        {
          path: 'dashboard',
          name: 'admin-dashboard',
          component: () => import('@/views/admin/KbListPage.vue'),
          meta: { title: '后台总览', menuKey: 'kb' }
        },
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
          path: 'rights-config',
          name: 'admin-rights-config',
          component: () => import('@/views/admin/RightsConfigPage.vue'),
          meta: { title: '权利请求与系统开关', menuKey: 'rights' }
        },
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
    /* 兜底 */
    { path: '/:pathMatch(.*)*', redirect: '/app/home' }
  ]
})

/**
 * 后台菜单 key → 默认落地路径（语义与 AdminLayout MENU_DEFS paths 一致）。
 * 仅用于路由守卫越权回退跳转；菜单渲染仍以后端下发 menus 为单一事实来源。
 */
const ADMIN_MENU_PATHS: Record<string, string> = {
  kb: '/admin/kb',
  lexicon: '/admin/lexicon',
  logs: '/admin/logs',
  feedback: '/admin/feedback',
  risk: '/admin/risk',
  rights: '/admin/rights-config',
  config: '/admin/rights-config',
  audit: '/admin/audit-logs',
}

/* ---------- 全局守卫 ---------- */
// 页面切换过渡：方向判定 + 滚动位置捕获（须在布局渲染前注册）
installPageTransition(router)

router.beforeEach((to) => {
  // 设置标题
  if (to.meta?.title) {
    document.title = `${to.meta.title} · 小光景`
  }
  // /app 下除 /app/start 外需登录
  if (to.path.startsWith('/app') && to.path !== '/app/start') {
    if (!getToken()) {
      return { path: '/app/start', query: { redirect: to.fullPath } }
    }
    // 直达页面（非 StartPage 进入）时会员态未初始化，补齐一次（isMember 依赖 memberStatus）
    const user = useUserStore()
    if (!user.memberInited) void user.refreshMe()
  }
  // /admin 后台：除登录页外需登录，且按后端下发 menus 做路由级角色校验（防越权直访）。
  // 服务端接口仍是真边界：此处仅做体验层拦截，越权跳转工作台/首个可用菜单。
  if (to.path.startsWith('/admin') && to.path !== '/admin/login') {
    if (!getAdminToken()) {
      return { path: '/admin/login' }
    }
    const menuKey = to.meta?.menuKey as string | undefined
    if (menuKey) {
      const info = getAdminInfo()
      const menus: string[] = Array.isArray(info?.menus) ? info.menus : []
      if (!menus.includes(menuKey)) {
        ElMessage.warning('当前角色无此权限')
        // 回退到该角色首个可用菜单页；无任何可用菜单时回到登录页
        const fallback = menus.map((k) => ADMIN_MENU_PATHS[k]).find(Boolean)
        return fallback ? { path: fallback } : { path: '/admin/login' }
      }
    }
  }
  return true
})

export default router

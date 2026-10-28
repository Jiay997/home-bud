<!--
  文件级注释：后台管理端框架（Stitch 高保真形态：左栏 232px + 顶栏 + 内容区 router-view）
  - 左栏：品牌深色块（盾徽 + Babe宝伴管理中心 / 内容审核与风险处置台）+「新建知识文档」主按钮
          + 主菜单（图标+文字，高亮=浅绿底+左 accent 竖条）+ 次要组（审计记录/系统监控）+ 版本角标
  - 顶栏：面包屑（Babe宝伴 / 当前页名）+ 铃铛 / 问号 + 账号 + 角色浅绿标签 + 退出（红字）
  - 角色过滤：以后端下发 menus 为单一事实来源（挂载时经 /me 刷新，失败沿用登录缓存）；
    key 精确匹配，无权限的菜单一律不渲染（super_admin 为全量 11 键 + 系统监控，菜单完整不变）。
  - 徽章：高风险事件/权利请求用真实 pending 数（加载失败隐藏）；反馈与举报红点可配置
          （localStorage 写入 jiaban_feedback_dot=1 显示）。
  - 审计记录无独立路由时以内置抽屉兜底展示（GET /admin/audit-logs）。
-->
<template>
  <div class="admin-shell">
    <!-- 左侧栏 232px -->
    <aside class="admin-aside">
      <!-- 品牌深色块 -->
      <div class="st-side aside-brand">
        <svg class="brand-shield" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2L4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z"
            fill="currentColor"
          />
          <path
            d="M8.6 12l2.4 2.4 4.6-4.6"
            fill="none"
            stroke="#fff"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <div class="brand-text">
          <div class="brand-name">Babe宝伴管理中心</div>
          <div class="brand-sub">内容审核与风险处置台</div>
        </div>
      </div>

      <!-- 快捷创建 -->
      <button class="new-doc-btn" type="button" @click="goNewDoc">
        <el-icon><Plus /></el-icon>
        <span>新建知识文档</span>
      </button>

      <!-- 主导航（primaryMenus 已按当前角色 menus 过滤，无权限项不渲染） -->
      <nav class="aside-nav">
        <button
          v-for="item in primaryMenus"
          :key="item.key"
          class="nav-item"
          :class="{ active: activeMenu === item.path }"
          type="button"
          @click="onMenuClick(item)"
        >
          <el-icon class="nav-ico"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
          <!-- 高风险事件：真实 pending 数徽章（无数据/失败时隐藏） -->
          <span v-if="item.key === 'risk' && riskPending" class="st-kpi">{{ riskPending > 99 ? '99+' : riskPending }}</span>
          <!-- 权利请求：真实 pending 数徽章 -->
          <span v-else-if="item.key === 'rights' && rightsPending" class="st-kpi">{{ rightsPending > 99 ? '99+' : rightsPending }}</span>
          <!-- 反馈与举报：可配置红点 -->
          <span v-else-if="item.key === 'feedback' && feedbackDot" class="nav-dot" />
        </button>
      </nav>

      <!-- 次要组 + 版本角标（审计记录同样按当前角色 menus 过滤，无权限不渲染） -->
      <div class="aside-foot">
        <div class="foot-divider"></div>
        <button
          v-if="canSee('audit')"
          class="nav-item minor"
          type="button"
          @click="onAuditClick"
        >
          <el-icon class="nav-ico"><Clock /></el-icon>
          <span class="nav-label">审计记录</span>
        </button>
        <button class="nav-item minor" type="button" @click="onMonitorClick">
          <el-icon class="nav-ico"><TrendCharts /></el-icon>
          <span class="nav-label">系统监控</span>
        </button>
        <div class="version-tag">版本 v0.1.0</div>
      </div>
    </aside>

    <!-- 右侧主体 -->
    <div class="admin-body">
      <!-- 顶栏 -->
      <header class="admin-header">
        <div class="crumb">
          <span class="crumb-root">Babe宝伴</span>
          <span class="crumb-sep">/</span>
          <span class="crumb-page">{{ pageTitle }}</span>
        </div>
        <div class="header-spacer"></div>
        <button class="icon-btn" type="button" title="通知提醒" @click="onBellClick">
          <el-icon :size="18"><Bell /></el-icon>
        </button>
        <button class="icon-btn" type="button" title="操作指引" @click="onHelpClick">
          <el-icon :size="18"><QuestionFilled /></el-icon>
        </button>
        <div class="header-divider"></div>
        <span class="account">{{ adminName }}</span>
        <span class="st-role-tag">{{ roleName }}</span>
        <button class="logout-btn" type="button" @click="handleLogout">退出</button>
      </header>

      <!-- 内容区（router-view，max-width 1200px 居中）；页面切换淡入 + 8px 上浮（styles/motion.scss） -->
      <main class="admin-main">
        <div class="page-wrap">
          <router-view v-slot="{ Component, route: r }">
            <Transition name="admin-page">
              <component :is="Component" :key="r.path" />
            </Transition>
          </router-view>
        </div>
      </main>
    </div>

    <!-- 审计日志兜底抽屉：/admin/audit-logs 路由未注册时使用（列字段对齐 GET /admin/audit-logs 返回） -->
    <el-drawer v-model="auditDrawerVisible" title="审计日志" size="720px">
      <el-table :data="auditRows" v-loading="auditLoading" size="small">
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ fmtAuditTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="operator_role" label="操作角色" width="100" />
        <el-table-column prop="action" label="动作" width="150" />
        <el-table-column prop="object_type" label="对象类型" width="110" />
        <el-table-column prop="object_id" label="对象 ID" min-width="140" show-overflow-tooltip />
        <el-table-column prop="reason" label="原因" min-width="110" show-overflow-tooltip />
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。负责登录态校验、菜单权限过滤（单一事实来源为后端下发 menus，
 * 挂载时经 /me 刷新）、侧栏徽章数据加载与整体 Stitch 布局。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Bell, Clock, EditPen, Files, FirstAidKit, Flag, Monitor, Phone, Plus, QuestionFilled,
  Reading, Setting, TrendCharts, User, Warning,
} from '@element-plus/icons-vue'
import { adminApi, clearAuth, getAdminInfo, setAdminInfo, getToken, ApiError } from '../../api/admin'
import { ADMIN_ROUTE } from '../../router'

const route = useRoute()
const router = useRouter()

/** 当前登录管理员信息（MFA 成功时已写入 localStorage） */
const info: any = getAdminInfo()
/** 当前角色（localStorage 缺失时兜底 super_admin，实际鉴权在服务端） */
const role = ref<string>(info?.role || 'super_admin')
/** 账号显示名 */
const adminName = ref<string>(info?.display_name || '管理员')
/** 后端下发的菜单 key 列表（单一事实来源；空数组一律视为无权限，未命中菜单置灰） */
const backendMenus = ref<string[]>(Array.isArray(info?.menus) ? info.menus : [])

/** 高风险事件 pending 数（null=未加载到，隐藏徽章） */
const riskPending = ref<number | null>(null)
/** 权利请求 pending 数（null=未加载到，隐藏徽章） */
const rightsPending = ref<number | null>(null)
/** 反馈与举报红点（可配置：localStorage 写入 jiaban_feedback_dot=1 显示） */
const feedbackDot = ref(localStorage.getItem('jiaban_feedback_dot') === '1')

/** 角色中文名映射 */
const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  operator: '内容运营',
  support: '客服',
  expert: '专家',
}

/** 角色中文名（未知角色原样展示） */
const roleName = computed(() => ROLE_LABELS[role.value] || role.value)

/**
 * 菜单项定义：key/展示名/图标/路由路径数组。
 * paths 使用 router 的 base 之后的相对路径（来自 ADMIN_ROUTE 常量，单一事实来源），
 * 禁止手写 `/admin/...` 前缀——vue-router 的 base='`/admin/`' 会自动拼接前缀，
 * 再写 `/admin/lexicon` 会解析成 `/admin/admin/lexicon`，命中兜底路由后
 * 被 redirect 回 /kb（缺陷 D3：后台除知识库外菜单全部点不动）。
 * N4：权利请求（/rights）与系统开关与配置（/config）已拆为两个独立路由与菜单项，
 * 不再共用 rights-config 页面，避免两个入口落到同一页导致职责混淆。
 * V3.1：新增 channel（危机渠道清单）/ triage（分级规则）/ content（内容运营）三个键，
 * 键集合与后端 ROLE_MENUS 逐字一致（backend/tests/test_admin_menus.py 校验）。
 */
const MENU_DEFS = [
  { key: 'kb', label: '知识库管理', icon: Reading, paths: [ADMIN_ROUTE.kb] },
  { key: 'lexicon', label: '词库维护', icon: EditPen, paths: [ADMIN_ROUTE.lexicon] },
  { key: 'logs', label: 'Agent调用日志', icon: Monitor, paths: [ADMIN_ROUTE.logs] },
  { key: 'feedback', label: '反馈与举报', icon: Flag, paths: [ADMIN_ROUTE.feedback] },
  { key: 'risk', label: '高风险事件', icon: Warning, paths: [ADMIN_ROUTE.risk] },
  { key: 'rights', label: '权利请求', icon: User, paths: [ADMIN_ROUTE.rights] },
  { key: 'config', label: '系统开关与配置', icon: Setting, paths: [ADMIN_ROUTE.config] },
  { key: 'channel', label: '危机渠道清单', icon: Phone, paths: [ADMIN_ROUTE.channels] },
  { key: 'triage', label: '分级规则', icon: FirstAidKit, paths: [ADMIN_ROUTE.triageRules] },
  { key: 'content', label: '内容运营', icon: Files, paths: [ADMIN_ROUTE.content] },
  { key: 'weight', label: 'Agent 展示权重', icon: TrendCharts, paths: [ADMIN_ROUTE.weight] },
  { key: 'audit', label: '审计记录', icon: Clock, paths: [ADMIN_ROUTE.auditLogs] },
]

/**
 * 函数级注释：解析菜单可用路径
 * 注意：路由表存在兜底路由 /:pathMatch(.*)*，router.resolve 对任意路径都会命中兜底，
 * 因此必须排除仅匹配兜底路由的候选，否则会把未注册路径误判为可用并跳到 C 端 /app/home。
 * @param paths 候选路径数组
 * @returns 第一个已在路由表注册的路径；全部未注册时返回第一个候选
 */
function resolveMenuPath(paths: string[]): string {
  for (const p of paths) {
    const matched = router.resolve(p).matched
    if (matched.length > 0 && !matched.some((r) => String(r.path).includes(':pathMatch'))) return p
  }
  return paths[0]
}

/**
 * 函数级注释：判断当前角色是否允许某菜单
 * 权限唯一来源为后端下发 menus（键与 MENU_DEFS 逐字一致，无别名/兜底映射）；
 * 与侧边栏过滤口径一致：无权限的菜单不渲染。
 * @param key 菜单 key
 * @returns 是否允许
 */
function canSee(key: string): boolean {
  return backendMenus.value.includes(key)
}

/** 带权限标记的菜单列表（path 为解析后的可用路径，allowed 供点击防御校验） */
const menuItems = computed(() =>
  MENU_DEFS.map((m) => ({ ...m, path: resolveMenuPath(m.paths), allowed: canSee(m.key) }))
)

/** 主导航菜单：仅渲染当前角色有权限的项（无权限不渲染）；次要组"审计记录"单独渲染在底部 */
const primaryMenus = computed(() => menuItems.value.filter((m) => m.key !== 'audit' && m.allowed))

/** 当前激活菜单（编辑页 /kb/* 归入"知识库管理"） */
const activeMenu = computed(() => {
  const p = route.path
  if (p.startsWith(ADMIN_ROUTE.kb)) return resolveMenuPath(MENU_DEFS[0].paths)
  const hit = MENU_DEFS.find((m) => m.paths.some((cand) => p === cand || p.startsWith(cand + '/')))
  return hit ? resolveMenuPath(hit.paths) : p
})

/** 页面标题（与菜单一致；编辑页归入知识库管理；系统监控为次要组独立页） */
const pageTitle = computed(() => {
  if (route.path.startsWith(ADMIN_ROUTE.kb)) return '知识库管理'
  if (route.path === ADMIN_ROUTE.monitor) return '系统监控'
  const hit = MENU_DEFS.find((m) => m.paths.some((cand) => route.path === cand || route.path.startsWith(cand + '/')))
  return hit ? hit.label : '知识库管理'
})

/** 审计日志兜底抽屉可见性 */
const auditDrawerVisible = ref(false)
/** 审计日志数据 */
const auditRows = ref<any[]>([])
/** 审计日志加载中 */
const auditLoading = ref(false)

/**
 * 函数级注释：菜单点击处理（含 C-22 无权限提示与审计抽屉兜底）
 * @param item 带权限标记的菜单项
 */
async function onMenuClick(item: { path: string; allowed: boolean }): Promise<void> {
  if (!item.allowed) {
    // C-22：提示无权限而非静默
    ElMessage.warning('当前角色无此权限')
    return
  }
  // 审计日志：若骨架路由未注册该路径，则以抽屉兜底展示
  if (item.path === ADMIN_ROUTE.auditLogs && router.resolve(item.path).matched.length === 0) {
    openAuditDrawer()
    return
  }
  router.push(item.path)
}

/**
 * 函数级注释：审计时间格式化（ISO → YYYY-MM-DD HH:mm:ss；空值回退 --）
 * @param iso ISO8601 字符串
 * @returns 展示时间
 */
function fmtAuditTime(iso?: string): string {
  if (!iso) return '--'
  return String(iso).slice(0, 19).replace('T', ' ')
}

/**
 * 函数级注释：打开审计日志抽屉并加载数据
 */
async function openAuditDrawer(): Promise<void> {
  auditDrawerVisible.value = true
  auditLoading.value = true
  try {
    const data: any = await adminApi.auditLogList({ page: 1, page_size: 50 })
    auditRows.value = data?.list || data?.items || data || []
  } catch (e) {
    // 无权限/失败时不中断布局，仅提示
    ElMessage.error(e instanceof ApiError ? e.message : '审计日志加载失败')
    auditRows.value = []
  } finally {
    auditLoading.value = false
  }
}

/**
 * 函数级注释：次要组「审计记录」点击（权限校验后走抽屉兜底/路由跳转）
 */
function onAuditClick(): void {
  if (!canSee('audit')) {
    ElMessage.warning('当前角色无此权限')
    return
  }
  const path = resolveMenuPath(MENU_DEFS.find((m) => m.key === 'audit')!.paths)
  if (router.resolve(path).matched.length === 0) {
    openAuditDrawer()
    return
  }
  router.push(path)
}

/**
 * 函数级注释：系统监控点击（跳转监控页；路由未注册时占位提示兜底）
 */
function onMonitorClick(): void {
  if (router.resolve(ADMIN_ROUTE.monitor).matched.length === 0) {
    ElMessage.info('系统监控页尚未接入')
    return
  }
  router.push(ADMIN_ROUTE.monitor)
}

/**
 * 函数级注释：新建知识文档（与知识库列表"新建条目"一致，进入新建编辑页 /kb/new/edit，
 * 该路径匹配路由 kb/:kbId/edit；路径不带 /admin 前缀——router base 已含 /admin/）
 */
function goNewDoc(): void {
  router.push(ADMIN_ROUTE.kbNew)
}

/**
 * 函数级注释：顶栏铃铛点击（暂无通知中心，占位提示）
 */
function onBellClick(): void {
  ElMessage.info('暂无新通知')
}

/**
 * 函数级注释：顶栏问号点击（操作指引占位提示）
 */
function onHelpClick(): void {
  ElMessage.info('操作指引整理中')
}

/**
 * 函数级注释：退出登录（清除本地登录态并回到登录页）
 */
function handleLogout(): void {
  clearAuth()
  ElMessage.success('已退出登录')
  router.push(ADMIN_ROUTE.login)
}

/**
 * 函数级注释：刷新后端账号信息与菜单（菜单单一事实来源为后端 /me）
 * 失败时静默沿用登录时缓存，不阻塞布局。
 */
async function refreshMenus(): Promise<void> {
  try {
    const data: any = await adminApi.getMe()
    if (Array.isArray(data?.menus)) backendMenus.value = data.menus
    if (data?.role) role.value = data.role
    if (data?.display_name) adminName.value = data.display_name
    setAdminInfo({ ...(getAdminInfo() || {}), ...data })
  } catch {
    /* 静默：沿用登录缓存 */
  }
}

/**
 * 函数级注释：加载侧栏徽章数据（高风险事件/权利请求 pending 数）
 * 徽章属辅助信息：请求失败时置 null 静默隐藏，不阻塞布局。
 */
async function loadBadges(): Promise<void> {
  try {
    const data: any = await adminApi.riskEventList({ status: 'pending', page: 1, page_size: 1 })
    const list: any[] = data?.list || data?.items || []
    riskPending.value = Number(data?.total ?? list.length) || null
  } catch {
    riskPending.value = null
  }
  try {
    const data: any = await adminApi.rightsList({ status: 'pending', page: 1, page_size: 1 })
    const list: any[] = data?.list || data?.items || []
    rightsPending.value = Number(data?.total ?? list.length) || null
  } catch {
    rightsPending.value = null
  }
}

onMounted(() => {
  // 未登录直接回到登录页
  if (!getToken()) {
    router.replace(ADMIN_ROUTE.login)
    return
  }
  refreshMenus()
  loadBadges()
})
</script>

<style scoped>
/* 整体骨架：左栏 232px + 右侧自适应 */
.admin-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

/* ---------- 左侧栏 ---------- */
.admin-aside {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  flex: none;
  width: 232px;
  height: 100vh;
  background: var(--surface);
  border-right: 1px solid var(--line);
}

/* 品牌深色块 */
.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 16px 14px;
}

.brand-shield {
  flex: none;
  width: 28px;
  height: 28px;
  color: var(--st-side-accent);
}

.brand-name {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--st-side-ink);
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.brand-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--st-side-ink-dim);
  letter-spacing: 0.5px;
  white-space: nowrap;
}

/* 新建知识文档主按钮 */
.new-doc-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  margin: 2px 16px 12px;
  border: none;
  border-radius: var(--radius-ctl);
  background: var(--accent);
  color: #fff;
  font-size: var(--fs-sub);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
}

.new-doc-btn:hover {
  background: var(--accent-press);
}

.new-doc-btn:active {
  transform: scale(0.99);
}

/* 主导航 */
.aside-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  padding: 4px 12px;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 38px;
  padding: 0 12px;
  border: none;
  border-radius: var(--radius-ctl);
  background: transparent;
  color: var(--ink-2);
  font-size: var(--fs-sub);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-item:hover:not(.disabled) {
  background: var(--surface-2);
  color: var(--ink-1);
}

/* 高亮态：浅绿底 + 左侧 accent 竖条 */
.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 500;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 0;
  width: 3px;
  border-radius: 2px;
  background: var(--accent);
}

/* 无权限置灰（C-22） */
.nav-item.disabled {
  color: var(--ink-3);
  opacity: 0.55;
  cursor: not-allowed;
}

.nav-ico {
  flex: none;
  font-size: 16px;
}

.nav-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 反馈与举报可配置红点 */
.nav-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger);
}

/* 次要组：灰色小项 */
.nav-item.minor {
  height: 32px;
  font-size: 13px;
  color: var(--ink-3);
}

/* 底部：分隔 + 版本角标 */
.aside-foot {
  padding: 0 12px 6px;
}

.foot-divider {
  margin: 8px 4px;
  border-top: 1px solid var(--line);
}

.version-tag {
  padding: 6px 12px 8px;
  font-family: var(--font-numeric);
  font-size: 11px;
  color: var(--ink-3);
}

/* ---------- 顶栏 ---------- */
.admin-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.admin-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 56px;
  padding: 0 24px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}

/* 面包屑：Babe宝伴 / 当前页名 */
.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.crumb-root {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.crumb-sep {
  color: var(--line-strong);
}

.crumb-page {
  font-size: var(--fs-sub);
  color: var(--ink-2);
}

.header-spacer {
  flex: 1;
}

/* 顶栏图标按钮（铃铛/问号） */
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-ctl);
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.icon-btn:hover {
  background: var(--surface-2);
  color: var(--ink-1);
}

.header-divider {
  width: 1px;
  height: 20px;
  margin: 0 4px;
  background: var(--line);
}

.account {
  font-family: var(--font-numeric);
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-1);
}

/* 角色浅绿标签 */
.st-role-tag {
  padding: 2px 8px;
  border: 1px solid var(--accent-line);
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-caption);
  white-space: nowrap;
}

/* 退出：红字 */
.logout-btn {
  border: none;
  background: transparent;
  color: var(--danger);
  font-size: var(--fs-sub);
  font-weight: 500;
  cursor: pointer;
}

.logout-btn:hover {
  text-decoration: underline;
}

/* ---------- 内容区 ---------- */
.admin-main {
  flex: 1;
  padding: 24px;
}

.page-wrap {
  max-width: 1200px;
  margin: 0 auto;
}

/* 窄屏：隐藏左栏文字防溢出（后续代理统一处理响应式） */
@media (max-width: 900px) {
  .admin-aside {
    width: 64px;
  }
  .brand-text,
  .nav-label,
  .new-doc-btn span,
  .version-tag {
    display: none;
  }
  .new-doc-btn {
    margin: 2px 12px 12px;
  }
}

/* 手机窄屏（375 视口）：顶栏精简 + 内容区收紧，消除横向滚动 */
@media (max-width: 640px) {
  .admin-header {
    gap: 6px;
    padding: 0 10px;
  }
  .crumb {
    min-width: 0;
  }
  .crumb-root,
  .crumb-sep,
  .account,
  .st-role-tag,
  .header-divider {
    display: none;
  }
  .crumb-page {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .icon-btn {
    flex: none;
    width: 28px;
    height: 28px;
  }
  .logout-btn {
    flex: none;
  }
  .admin-main {
    padding: 12px;
  }
}
</style>

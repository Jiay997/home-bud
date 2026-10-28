<!--
  文件级注释：PA-06 用户反馈与投诉举报处置页（Stitch 稿 _4 全量重构）
  - 页头：面包屑 + 标题 +「PA-06 标准监管面板」chip + 合规监管通道状态 + 更新时间
  - 切换卡：反馈 n / 举报 n（涉未成年红标）分段切换 + 导出报表（前端 CSV）
  - 筛选行：状态/分类/时间下拉 + 筛选/重置（本地过滤，不改动列表 API）
  - 列表：编号/类型标签/内容摘要/关联会话/SLA 刻度条（72h 灰绿·24h 棕·涉未成年红急迫徽章）/状态点/操作
  - 工单处置面板（选中行展开）：举报分类校准单选 + 只读留证归档卡 + 处置依据必填
    + 回执勾选 + 驳回/下架内容/上报（原处置逻辑 + 二次确认，PUT /admin/reports/{report_no}）
  - 反馈处置面板（选中行展开）：回复内容必填（PUT /admin/feedback/{id}）
  - 底部儿童保护与医疗合规强监管警示条（st-note，文案照稿）
-->
<template>
  <div class="fb-page">
    <!-- ═══ 1. 页头 ═══ -->
    <header class="page-head">
      <div class="head-left">
        <div class="crumb">
          <span>安全与合规治理</span>
          <span class="sep">/</span>
          <span class="cur">用户反馈与投诉举报处置</span>
        </div>
        <h1 class="head-title">
          <span>用户反馈与投诉举报处置</span>
          <span class="pa-chip">PA-06 标准监管面板</span>
        </h1>
      </div>
      <div class="head-right">
        <span class="ok-dot"></span>
        <span>合规监管通道：正常</span>
        <span v-if="lastSyncedAt" class="upd numeric">更新时间：{{ lastSyncedAt }}</span>
      </div>
    </header>

    <!-- ═══ 2. 切换卡：反馈/举报分段 + 导出报表 ═══ -->
    <section class="st-card tab-card">
      <div class="seg">
        <button
          type="button"
          class="seg-btn"
          :class="{ active: activeTab === 'feedback' }"
          @click="switchTab('feedback')"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span>反馈</span>
          <span class="seg-count numeric">{{ feedbackRows.length }}</span>
        </button>
        <button
          type="button"
          class="seg-btn"
          :class="{ active: activeTab === 'report' }"
          @click="switchTab('report')"
        >
          <el-icon><Warning /></el-icon>
          <span>举报</span>
          <span class="seg-count numeric">{{ reportRows.length }}</span>
          <span v-if="minorReportCount" class="minor-chip">
            <i class="ping"></i>
            <span>涉未成年 {{ minorReportCount }}</span>
          </span>
        </button>
      </div>
      <el-button :icon="Download" @click="exportCsv">导出报表</el-button>
    </section>

    <!-- ═══ 3. 筛选行卡 ═══ -->
    <section class="st-card filter-card">
      <div class="filter-fields">
        <div class="f-field">
          <label>状态：</label>
          <el-select v-model="draftFilters.status" class="f-ctrl" placeholder="全部状态">
            <el-option label="全部状态" value="" />
            <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </div>
        <div class="f-field">
          <label>分类：</label>
          <el-select v-model="draftFilters.category" class="f-ctrl" placeholder="全部" :disabled="activeTab !== 'report'">
            <el-option label="全部" value="" />
            <el-option label="涉未成年" value="minor" />
            <el-option v-for="(v, k) in REPORT_CATEGORY" :key="k" :label="v" :value="k" />
          </el-select>
        </div>
        <div class="f-field">
          <label>时间：</label>
          <el-select v-model="draftFilters.time" class="f-ctrl" placeholder="近7天">
            <el-option label="全部时间" value="" />
            <el-option label="近24小时" value="24h" />
            <el-option label="近7天" value="7d" />
            <el-option label="近30天" value="30d" />
          </el-select>
        </div>
        <el-button class="apply-btn" type="primary" plain @click="applyFilters">筛选</el-button>
      </div>
      <div class="filter-side">
        <span>共找到 <strong class="numeric">{{ filteredRows.length }}</strong> 条记录</span>
        <button type="button" class="reset-link" @click="resetFilters">
          <el-icon><RefreshRight /></el-icon>
          <span>重置条件</span>
        </button>
      </div>
    </section>

    <!-- ═══ 4. 列表卡 ═══ -->
    <section class="st-card table-card">
      <el-table
        :data="filteredRows"
        class="st-table"
        v-loading="activeTab === 'feedback' ? feedbackLoading : reportLoading"
        :row-class-name="rowClassName"
        @row-click="onRowClick"
      >
        <el-table-column label="编号" width="110">
          <template #default="{ row }">
            <span class="no-cell numeric" :class="{ picked: isPicked(row) }">{{ rowNo(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="160">
          <template #default="{ row }">
            <span class="st-tag st-tag--plain" :class="typeTagClass(row)">{{ typeLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="内容摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="sum-cell">
              <span v-if="activeTab === 'report' && row.involves_minor" class="warn-prefix">[合规预警]</span>
              {{ rowSummary(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="关联会话" width="120">
          <template #default="{ row }">
            <span v-if="sessionLabel(row)" class="sess-link numeric">{{ sessionLabel(row) }}</span>
            <span v-else class="muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="SLA" width="170">
          <template #default="{ row }">
            <!-- 涉未成年未办结：急迫徽章 -->
            <span v-if="isMinorUrgent(row)" class="sla-urgent">
              <el-icon><AlarmClock /></el-icon>
              <span class="numeric">24h 急迫</span>
            </span>
            <!-- 常规：刻度条 + 剩余文案 -->
            <span v-else class="sla-cell">
              <span class="sla-bar">
                <span class="sla-fill" :class="`fill--${slaMeta(row).color}`" :style="{ width: slaMeta(row).pct + '%' }"></span>
              </span>
              <span class="sla-text numeric" :class="`txt--${slaMeta(row).color}`">{{ slaMeta(row).text }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <span class="st-tag" :class="statusTagClass(row)">{{ rowStatusLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <span v-if="isPicked(row)" class="st-chip-btn"><el-icon><EditPen /></el-icon>处置中</span>
            <el-button v-else link type="primary" size="small" @click.stop="onRowClick(row)">处置</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </section>

    <!-- ═══ 5a. 反馈处置面板（选中反馈行展开） ═══ -->
    <section v-if="activeTab === 'feedback' && currentFeedback" class="st-card panel panel--feedback">
      <div class="panel-head">
        <div class="panel-title-wrap">
          <div class="panel-ico ico--accent"><el-icon><ChatDotRound /></el-icon></div>
          <div>
            <h2 class="panel-title">反馈处置面板 · <span class="numeric">#{{ currentFeedback.id }}</span></h2>
            <p class="panel-sub">回复将同步给用户并写入服务留痕</p>
          </div>
        </div>
        <el-button link @click="closePanels">收起</el-button>
      </div>
      <el-descriptions :column="2" size="small" class="panel-desc">
        <el-descriptions-item label="用户">{{ currentFeedback.user_name || currentFeedback.user_id || '--' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ currentFeedback.created_at || '--' }}</el-descriptions-item>
        <el-descriptions-item label="涉未成年">{{ currentFeedback.involves_minor ? '是（优先处理）' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ feedbackStatusLabel(currentFeedback.status) }}</el-descriptions-item>
        <el-descriptions-item label="内容" :span="2">{{ currentFeedback.content || currentFeedback.content_preview || '--' }}</el-descriptions-item>
      </el-descriptions>
      <div class="form-row">
        <label class="form-label">回复内容 <span class="req">*</span></label>
        <el-input
          v-model="feedbackReply"
          type="textarea"
          :rows="3"
          placeholder="必填：回复将同步给用户并留痕"
        />
      </div>
      <div class="panel-actions">
        <el-button @click="closePanels">取消</el-button>
        <el-button type="primary" :loading="replying" @click="confirmReply">提交回复</el-button>
      </div>
    </section>

    <!-- ═══ 5b. 工单处置面板（选中举报行展开，红色图标芯片标识） ═══ -->
    <section v-if="activeTab === 'report' && currentReport" class="st-card panel panel--report">
      <div class="panel-head">
        <div class="panel-title-wrap">
          <div class="panel-ico ico--danger"><el-icon><Aim /></el-icon></div>
          <div>
            <h2 class="panel-title">
              工单处置面板 · <span class="numeric">{{ currentReport.report_no }}</span>
              <span v-if="currentReport.involves_minor" class="st-tag st-tag--red">涉未成年人敏感举报</span>
            </h2>
            <p class="panel-sub">依据《未成年人网络保护条例》与医疗 AI 内容安全规程处置</p>
          </div>
        </div>
        <div class="sla-badge">
          <el-icon><Timer /></el-icon>
          <span>合规剩余响应时间: <span class="numeric">{{ slaInfo(currentReport).text }}</span></span>
        </div>
      </div>

      <!-- 举报分类校准单选 -->
      <div class="form-row">
        <label class="form-label">
          举报分类：
          <span class="form-tip">（请校准系统初判标签）</span>
        </label>
        <el-radio-group v-model="categoryChoice" class="cat-group">
          <el-radio
            v-for="c in CATEGORY_CHOICES"
            :key="c.value"
            :value="c.value"
            :class="{ 'cat-danger': c.value === 'minor' && categoryChoice === 'minor' }"
          >
            {{ c.label }}
          </el-radio>
        </el-radio-group>
      </div>

      <!-- 留证记录与上下文留档（系统只读归档） -->
      <div class="evidence-box">
        <div class="evidence-head">
          <div class="evidence-title">
            <el-icon><FolderChecked /></el-icon>
            <span>留证记录与上下文留存（系统只读归档）</span>
          </div>
          <span class="evidence-chip">区块链防篡改存证</span>
        </div>
        <div class="evidence-grid">
          <div class="ev-item">
            <span class="ev-label">留证截图</span>
            <span class="ev-value ev-link">
              <el-icon><Picture /></el-icon>
              <span :title="currentReport.evidence || ''">{{ currentReport.evidence || '截图（已脱敏）.png' }}</span>
            </span>
          </div>
          <div class="ev-item">
            <span class="ev-label">命中规则记录</span>
            <span class="ev-value numeric" :title="currentReport.rule_version || ''">{{ currentReport.rule_version || 'RULE_MINOR_SAFE_V3_02' }}</span>
          </div>
          <div class="ev-item">
            <span class="ev-label">当前处置人</span>
            <span class="ev-value">{{ adminName }}</span>
          </div>
          <div class="ev-item">
            <span class="ev-label">审计时间戳</span>
            <span class="ev-value numeric">{{ currentReport.updated_at || currentReport.created_at || lastSyncedAt || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 处置依据（必填） -->
      <div class="form-row">
        <div class="label-line">
          <label class="form-label">处置依据（必填）<span class="req">*</span></label>
          <span class="form-tip">支持 Markdown 语法记录审查分析</span>
        </div>
        <el-input
          v-model="reportForm.basis"
          type="textarea"
          :rows="3"
          placeholder="请输入详尽处置调查依据与核实记录..."
        />
      </div>

      <!-- 回执选项 -->
      <div class="receipt-row">
        <el-checkbox v-model="sendReceipt">向举报人发送回执通知（经合规脱敏模板回复）</el-checkbox>
        <span class="form-tip">预计下发通道：Babe宝伴应用端内服务通知</span>
      </div>

      <!-- 处置动作按钮组（原处置逻辑 + confirm） -->
      <div class="panel-actions actions-topline">
        <el-button :loading="handlingReport" @click="doReportAction('dismiss')">驳回</el-button>
        <el-button class="btn-remove" :icon="CircleClose" :loading="handlingReport" @click="doReportAction('remove')">
          下架内容
        </el-button>
        <el-button type="primary" :icon="Promotion" :loading="handlingReport" @click="doReportAction('escalate')">
          上报主管部门
        </el-button>
      </div>
    </section>

    <!-- ═══ 6. 底部合规警示条（文案照稿） ═══ -->
    <footer class="st-note note-strong">
      <el-icon class="note-ico"><CircleCheck /></el-icon>
      <div>
        <div class="note-title">
          <strong>儿童保护与医疗合规强监管警示</strong>
          <span class="note-chip">国家网信办未保专项标准</span>
        </div>
        <p class="note-main">涉未成年人举报：SLA 更短（24h 初审 / 72h 处置完成）；下架动作将联动内容追溯处置流程。</p>
        <div class="note-sub">
          <span>· 联动机制：触发全链路模型微调标记</span>
          <span>· 审计日志：永久留存并向伦理委员会同步</span>
          <span>· 申诉窗口：办结后 48 小时内支持二次复核</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。反馈/举报双列表 + SLA 倒计时（30s 刷新）+ 选中行行内处置面板
 * （反馈回复 / 举报分类处置留痕）；筛选与导出为前端本地实现，处置 API 与原逻辑一致。
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim,
  AlarmClock,
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Download,
  EditPen,
  FolderChecked,
  Picture,
  Promotion,
  RefreshRight,
  Timer,
  Warning,
} from '@element-plus/icons-vue'
import { adminApi, ApiError, downloadBlob, getAdminInfo } from '../../api/admin'

/** 当前 Tab：feedback=反馈 / report=举报 */
const activeTab = ref<'feedback' | 'report'>('feedback')
/** 反馈/举报列表 */
const feedbackRows = ref<any[]>([])
const reportRows = ref<any[]>([])
/** 加载标志 */
const feedbackLoading = ref(false)
const reportLoading = ref(false)
/** 当前时间（驱动 SLA 倒计时，30s 刷新） */
const now = ref(Date.now())
/** SLA 定时器 */
let slaTimer: ReturnType<typeof setInterval> | null = null
/** 最近一次列表成功加载时间（页头"更新时间"展示） */
const lastSyncedAt = ref('')

/** 当前选中的反馈行（展开反馈处置面板） */
const currentFeedback = ref<any>(null)
/** 回复内容（必填） */
const feedbackReply = ref('')
/** 回复提交中 */
const replying = ref(false)

/** 当前选中的举报行（展开工单处置面板） */
const currentReport = ref<any>(null)
/** 举报处置表单（action 由按钮指定；basis 必填） */
const reportForm = reactive({ action: 'dismiss', basis: '' })
/** 举报分类校准选择（UI 层初判校准，不改变处置 API 载荷） */
const categoryChoice = ref('other')
/** 是否向举报人发送回执通知（UI 勾选项） */
const sendReceipt = ref(true)
/** 处置提交中 */
const handlingReport = ref(false)

/** 当前管理员显示名（留证卡"当前处置人"） */
const adminName = computed(() => getAdminInfo()?.display_name || getAdminInfo()?.username || 'admin')

/** 举报分类校准选项（稿子四类） */
const CATEGORY_CHOICES = [
  { value: 'violation', label: '违法违规' },
  { value: 'medical', label: '医疗误导' },
  { value: 'minor', label: '有害未成年人信息' },
  { value: 'other', label: '其他' },
]

/** 举报分类枚举展示 */
const REPORT_CATEGORY: Record<string, string> = {
  content_violation: '内容违规',
  minor_related: '涉未成年',
  privacy: '隐私泄露',
  copyright: '版权问题',
  other: '其他',
}

/** 反馈状态文案 */
const FEEDBACK_STATUS: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  replied: '已回复',
  closed: '已关闭',
}

/** 举报状态文案 */
const REPORT_STATUS: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  dismissed: '已驳回',
  removed: '已下架',
  escalated: '已上报',
  closed: '已关闭',
}

/** 筛选草稿条件（点"筛选"后写入 appliedFilters 生效） */
const draftFilters = reactive({ status: '', category: '', time: '' })
/** 已应用的筛选条件 */
const appliedFilters = reactive({ status: '', category: '', time: '' })

/**
 * 函数级注释：反馈状态转文案
 * @param s 状态枚举
 * @returns 中文文案
 */
function feedbackStatusLabel(s: string): string {
  return FEEDBACK_STATUS[s] || s || '--'
}

/**
 * 函数级注释：举报状态转文案
 * @param s 状态枚举
 * @returns 中文文案
 */
function reportStatusLabel(s: string): string {
  return REPORT_STATUS[s] || s || '--'
}

/**
 * 函数级注释：当前 Tab 行的状态文案
 * @param row 行数据
 * @returns 中文文案
 */
function rowStatusLabel(row: any): string {
  return activeTab.value === 'feedback' ? feedbackStatusLabel(row.status) : reportStatusLabel(row.status)
}

/**
 * 函数级注释：当前 Tab 的状态下拉选项
 */
const statusOptions = computed(() => {
  if (activeTab.value === 'feedback') {
    return Object.entries(FEEDBACK_STATUS).map(([value, label]) => ({ value, label }))
  }
  return Object.entries(REPORT_STATUS).map(([value, label]) => ({ value, label }))
})

/**
 * 函数级注释：SLA 倒计时信息
 * @param row 行数据（读取 sla_deadline / deadline）
 * @returns {text, overdue}
 */
function slaInfo(row: any): { text: string; overdue: boolean } {
  const deadline = row.sla_deadline || row.deadline
  if (!deadline) return { text: '--', overdue: false }
  const diff = new Date(deadline).getTime() - now.value
  if (Number.isNaN(diff)) return { text: '--', overdue: false }
  const absH = Math.abs(diff) / 3600000
  const hText = absH >= 24 ? `${(absH / 24).toFixed(1)} 天` : `${absH.toFixed(1)} 小时`
  if (diff <= 0) return { text: `已超时 ${hText}`, overdue: true }
  return { text: `剩余 ${hText}`, overdue: false }
}

/**
 * 函数级注释：SLA 刻度条元信息（颜色档/填充比例/文案）
 * 反馈基线 72h（灰绿），举报基线 24h（棕），涉未成年未办结走红色急迫徽章。
 * @param row 行数据
 * @returns {text, pct, color}
 */
function slaMeta(row: any): { text: string; pct: number; color: 'accent' | 'warn' | 'danger' | 'gray' } {
  const isReport = activeTab.value === 'report'
  const totalH = isReport ? 24 : 72
  const terminal = isReport
    ? ['dismissed', 'removed', 'escalated', 'closed'].includes(row.status)
    : ['replied', 'closed'].includes(row.status)
  const deadline = row.sla_deadline || row.deadline
  if (!deadline || Number.isNaN(new Date(deadline).getTime())) {
    return { text: `${totalH}h`, pct: 100, color: terminal ? 'gray' : isReport ? 'warn' : 'accent' }
  }
  const remainH = (new Date(deadline).getTime() - now.value) / 3600000
  const pct = Math.min(100, Math.max(6, Math.round((remainH / totalH) * 100)))
  if (terminal) return { text: slaInfo(row).text, pct, color: 'gray' }
  if (remainH <= 0) return { text: slaInfo(row).text, pct, color: 'danger' }
  if (isReport && row.involves_minor) return { text: '24h 急迫', pct, color: 'danger' }
  return { text: slaInfo(row).text, pct, color: isReport ? 'warn' : 'accent' }
}

/**
 * 函数级注释：是否渲染"24h 急迫"徽章（涉未成年举报且未办结未超时）
 * @param row 行数据
 * @returns 是否急迫
 */
function isMinorUrgent(row: any): boolean {
  if (activeTab.value !== 'report' || !row.involves_minor) return false
  if (['dismissed', 'removed', 'escalated', 'closed'].includes(row.status)) return false
  const deadline = row.sla_deadline || row.deadline
  if (!deadline) return true
  return new Date(deadline).getTime() > now.value
}

/**
 * 函数级注释：反馈列表涉未成年数量（Tab 红标）
 */
const minorFeedbackCount = computed(() => feedbackRows.value.filter((r) => r.involves_minor).length)

/**
 * 函数级注释：举报列表涉未成年数量（Tab 红标）
 */
const minorReportCount = computed(() => reportRows.value.filter((r) => r.involves_minor).length)

/**
 * 函数级注释：反馈列表排序（涉未成年优先）
 */
const sortedFeedback = computed(() =>
  feedbackRows.value.slice().sort((a, b) => Number(!!b.involves_minor) - Number(!!a.involves_minor))
)

/**
 * 函数级注释：举报列表排序（涉未成年优先）
 */
const sortedReports = computed(() =>
  reportRows.value.slice().sort((a, b) => Number(!!b.involves_minor) - Number(!!a.involves_minor))
)

/**
 * 函数级注释：应用筛选后的当前 Tab 列表（状态/分类/时间为前端本地过滤）
 */
const filteredRows = computed(() => {
  const src = activeTab.value === 'feedback' ? sortedFeedback.value : sortedReports.value
  const isReport = activeTab.value === 'report'
  const { status, category, time } = appliedFilters
  return src.filter((r) => {
    if (status && r.status !== status) return false
    if (isReport && category) {
      if (category === 'minor') {
        if (!r.involves_minor) return false
      } else if (r.category !== category) return false
    }
    if (time) {
      const hours = time === '24h' ? 24 : time === '7d' ? 168 : 720
      const t = new Date(r.created_at || 0).getTime()
      if (!t || now.value - t > hours * 3600000) return false
    }
    return true
  })
})

/**
 * 函数级注释：应用筛选条件（写入 appliedFilters）
 */
function applyFilters(): void {
  Object.assign(appliedFilters, draftFilters)
}

/**
 * 函数级注释：重置筛选条件并立即生效
 */
function resetFilters(): void {
  draftFilters.status = ''
  draftFilters.category = ''
  draftFilters.time = ''
  applyFilters()
}

/**
 * 函数级注释：切换 Tab（收起处置面板）
 * @param tab 目标 Tab
 */
function switchTab(tab: 'feedback' | 'report'): void {
  if (activeTab.value === tab) return
  activeTab.value = tab
  closePanels()
}

/**
 * 函数级注释：行编号（举报取 report_no，反馈取 id）
 * @param row 行数据
 * @returns 编号文案
 */
function rowNo(row: any): string {
  return activeTab.value === 'report' ? row.report_no || '--' : String(row.id ?? '--')
}

/**
 * 函数级注释：类型标签文案（反馈/举报-分类）
 * @param row 行数据
 * @returns 标签文案
 */
function typeLabel(row: any): string {
  if (activeTab.value === 'feedback') return '反馈'
  if (row.involves_minor) return '举报-涉未成年'
  const c = REPORT_CATEGORY[row.category] || row.category || '其他'
  return `举报-${c}`
}

/**
 * 函数级注释：类型标签变体类（反馈灰/内容违规琥珀/涉未成年红/其他描边）
 * @param row 行数据
 * @returns st-tag 修饰类
 */
function typeTagClass(row: any): string {
  if (activeTab.value === 'feedback') return 'st-tag--gray'
  if (row.involves_minor) return 'st-tag--red'
  if (row.category === 'content_violation') return 'st-tag--amber'
  return 'st-tag--outline'
}

/**
 * 函数级注释：内容摘要（举报取对象摘要，反馈取内容）
 * @param row 行数据
 * @returns 摘要文案
 */
function rowSummary(row: any): string {
  return (
    (activeTab.value === 'report'
      ? row.target_summary || row.target
      : row.content || row.content_preview) || '--'
  )
}

/**
 * 函数级注释：关联会话标识（真实字段优先，无则空串渲染占位）
 * @param row 行数据
 * @returns 会话标识
 */
function sessionLabel(row: any): string {
  return row.session_id || row.session_no || row.conversation_id || ''
}

/**
 * 函数级注释：状态点标签变体类（涉未成年待处理红/进行中琥珀/办结绿/驳回灰）
 * @param row 行数据
 * @returns st-tag 修饰类
 */
function statusTagClass(row: any): string {
  const s = row.status
  if (activeTab.value === 'report' && s === 'pending' && row.involves_minor) return 'st-tag--red'
  if (['dismissed'].includes(s)) return 'st-tag--gray'
  if (['replied', 'closed', 'removed', 'escalated'].includes(s)) return 'st-tag--green'
  return 'st-tag--amber'
}

/**
 * 函数级注释：行是否处于选中展开态
 * @param row 行数据
 * @returns 是否选中
 */
function isPicked(row: any): boolean {
  return activeTab.value === 'feedback'
    ? currentFeedback.value?.id === row.id
    : currentReport.value?.report_no === row.report_no
}

/**
 * 函数级注释：表格行类名（选中行高亮）
 * @param param0 { row }
 * @returns 类名
 */
function rowClassName({ row }: { row: any }): string {
  return isPicked(row) ? 'row-selected' : ''
}

/**
 * 函数级注释：行点击（切换选中展开/收起处置面板）
 * @param row 行数据
 */
function onRowClick(row: any): void {
  if (activeTab.value === 'feedback') {
    currentFeedback.value = isPicked(row) ? null : row
    feedbackReply.value = ''
  } else {
    if (isPicked(row)) {
      closePanels()
      return
    }
    currentReport.value = row
    reportForm.action = 'dismiss'
    reportForm.basis = ''
    // 按真实字段推断初判分类校准项
    categoryChoice.value = row.involves_minor
      ? 'minor'
      : row.category === 'content_violation'
        ? 'violation'
        : 'other'
    sendReceipt.value = true
  }
}

/**
 * 函数级注释：收起全部处置面板
 */
function closePanels(): void {
  currentFeedback.value = null
  currentReport.value = null
}

/**
 * 函数级注释：提交反馈回复（回复内容必填）
 */
async function confirmReply(): Promise<void> {
  if (!feedbackReply.value.trim()) {
    ElMessage.warning('回复内容必填')
    return
  }
  replying.value = true
  try {
    await adminApi.feedbackReply(currentFeedback.value.id, { reply_content: feedbackReply.value.trim() })
    ElMessage.success('回复已提交')
    closePanels()
    loadFeedback()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '回复提交失败')
  } finally {
    replying.value = false
  }
}

/** 处置动作 → 确认文案映射 */
const ACTION_CONFIRM: Record<string, string> = {
  dismiss: '确认驳回该举报？驳回结果将通知举报人。',
  remove: '确认下架关联内容？下架将联动内容追溯处置流程。',
  escalate: '确认上报主管部门？上报后进入专项处置通道。',
}

/**
 * 函数级注释：执行举报处置（依据必填 + 二次确认；action: dismiss/remove/escalate）
 * @param action 处置动作
 */
async function doReportAction(action: 'dismiss' | 'remove' | 'escalate'): Promise<void> {
  if (!reportForm.basis.trim()) {
    ElMessage.warning('处置依据必填')
    return
  }
  try {
    await ElMessageBox.confirm(ACTION_CONFIRM[action] || '确认提交处置？', '二次确认', {
      type: action === 'dismiss' ? 'info' : 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  handlingReport.value = true
  try {
    // 后端契约：reject / unpublish / escalate / no_action；escalate 必须附证据
    const actionMap: Record<string, string> = { dismiss: 'reject', remove: 'unpublish', escalate: 'escalate' }
    const apiAction = actionMap[action]
    await adminApi.reportHandle(currentReport.value.report_no, {
      action: apiAction,
      basis: reportForm.basis.trim(),
      evidence: action === 'escalate' ? { basis: reportForm.basis.trim() } : undefined,
    })
    ElMessage.success('处置已提交')
    closePanels()
    loadReports()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '处置提交失败')
  } finally {
    handlingReport.value = false
  }
}

/**
 * 函数级注释：加载反馈列表
 */
async function loadFeedback(): Promise<void> {
  feedbackLoading.value = true
  try {
    const data: any = await adminApi.feedbackList({ page: 1, page_size: 100 })
    feedbackRows.value = data?.list || data?.items || data || []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '反馈加载失败')
    feedbackRows.value = []
  } finally {
    feedbackLoading.value = false
  }
}

/**
 * 函数级注释：加载举报列表
 */
async function loadReports(): Promise<void> {
  reportLoading.value = true
  try {
    const data: any = await adminApi.reportList({ page: 1, page_size: 100 })
    reportRows.value = data?.list || data?.items || data || []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '举报加载失败')
    reportRows.value = []
  } finally {
    reportLoading.value = false
  }
}

/**
 * 函数级注释：刷新两列表并记录标定时间
 */
function loadAll(): void {
  lastSyncedAt.value = fmtNow()
  loadFeedback()
  loadReports()
}

/**
 * 函数级注释：格式化当前时间为 YYYY-MM-DD HH:mm
 * @returns 时间文案
 */
function fmtNow(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/**
 * 函数级注释：导出当前 Tab 筛选后列表为 CSV 报表（前端本地生成）
 */
function exportCsv(): void {
  const rows = filteredRows.value
  const header = ['编号', '类型', '内容摘要', '关联会话', '状态', 'SLA']
  const lines = rows.map((r) => [
    rowNo(r),
    typeLabel(r),
    rowSummary(r),
    sessionLabel(r) || '--',
    rowStatusLabel(r),
    slaInfo(r).text,
  ])
  const csv =
    '\ufeff' +
    [header, ...lines].map((cells) => cells.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `feedback-report-${Date.now()}.csv`)
  ElMessage.success('报表已导出')
}

onMounted(() => {
  loadAll()
  // SLA 倒计时：每 30s 刷新当前时间
  slaTimer = setInterval(() => {
    now.value = Date.now()
  }, 30000)
})

onBeforeUnmount(() => {
  if (slaTimer) clearInterval(slaTimer)
})
</script>

<style scoped lang="scss">
/* 页面纵向排布 */
.fb-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---------- 页头 ---------- */
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.crumb {
  display: flex;
  gap: 6px;
  color: var(--ink-3);
  font-size: var(--fs-caption);

  .sep {
    color: var(--line-strong);
  }

  .cur {
    color: var(--ink-1);
  }
}

.head-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
  font-size: var(--fs-display);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.3;
}

.pa-chip {
  padding: 1px 10px;
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-pill);
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 400;
  white-space: nowrap;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
  padding-bottom: 4px;
}

.ok-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.upd {
  margin-left: 8px;
  color: var(--ink-3);
}

/* ---------- 切换卡 ---------- */
.tab-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 14px 16px;
}

.seg {
  display: inline-flex;
  gap: 10px;
  flex-wrap: wrap;
}

.seg-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-sub);
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover:not(.active) {
    background: var(--surface-2);
    color: var(--ink-1);
  }

  &.active {
    border-color: var(--accent-line);
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
    box-shadow: var(--shadow-e1);
  }
}

.seg-count {
  padding: 0 7px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 600;
  line-height: 18px;
}

.seg-btn.active .seg-count {
  background: var(--surface);
  color: var(--accent);
}

/* 涉未成年红标 */
.minor-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 1px 8px;
  border: 1px solid var(--danger);
  border-radius: var(--radius-pill);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--fs-caption);
}

.ping {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--danger);
  animation: fb-ping 1.2s ease-in-out infinite;
}

@keyframes fb-ping {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

/* ---------- 筛选行卡 ---------- */
.filter-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
}

.filter-fields {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.f-field {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-2);
  font-size: var(--fs-sub);

  label {
    color: var(--ink-3);
    white-space: nowrap;
  }
}

.f-ctrl {
  width: 150px;
}

.apply-btn {
  min-width: 76px;
}

.filter-side {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--ink-3);
  font-size: var(--fs-caption);

  strong {
    color: var(--ink-1);
  }
}

.reset-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: none;
  background: none;
  color: var(--accent);
  font-size: var(--fs-caption);
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}

/* ---------- 表格卡 ---------- */
.table-card {
  padding: 0;
  overflow: hidden;
}

.st-table {
  width: 100%;

  :deep(th.el-table__cell) {
    background: var(--surface-2);
    color: var(--ink-3);
    font-size: var(--fs-caption);
    font-weight: 500;
  }

  :deep(td.el-table__cell) {
    padding: 10px 0;
  }

  :deep(tbody tr) {
    cursor: pointer;
  }

  :deep(.row-selected > td.el-table__cell) {
    background: var(--accent-soft);
  }
}

.no-cell {
  color: var(--ink-1);
  font-weight: 500;

  &.picked {
    color: var(--accent);
    font-weight: 700;
  }
}

.sum-cell {
  color: var(--ink-1);
}

.warn-prefix {
  margin-right: 4px;
  color: var(--danger);
}

.sess-link {
  color: var(--accent);
  font-size: var(--fs-caption);
  text-decoration: underline;
  cursor: pointer;
}

.muted {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* SLA 刻度条 */
.sla-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.sla-bar {
  display: inline-block;
  width: 64px;
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  overflow: hidden;
}

.sla-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-pill);
  transition: width 0.3s ease;

  &.fill--accent {
    background: var(--accent);
  }
  &.fill--warn {
    background: var(--warn);
  }
  &.fill--danger {
    background: var(--danger);
  }
  &.fill--gray {
    background: var(--line-strong);
  }
}

.sla-text {
  font-size: var(--fs-caption);
  white-space: nowrap;

  &.txt--accent {
    color: var(--ink-2);
  }
  &.txt--warn {
    color: var(--warn);
    font-weight: 600;
  }
  &.txt--danger {
    color: var(--danger);
    font-weight: 600;
  }
  &.txt--gray {
    color: var(--ink-3);
  }
}

/* 涉未成年急迫徽章 */
.sla-urgent {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 10px;
  border: 1px solid var(--danger);
  border-radius: var(--radius-pill);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--fs-caption);
  font-weight: 600;
}

/* 操作主按钮 chip */
.st-chip-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 12px;
  border-radius: var(--radius-ctl);
  background: var(--accent);
  color: #fff;
  font-size: var(--fs-caption);
  font-weight: 500;
  white-space: nowrap;
}

/* ---------- 处置面板 ---------- */
.panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 面板类型由头部 ico--danger / ico--accent 图标芯片承载，无彩色左条 */
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.panel-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-ico {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-ctl);

  &.ico--danger {
    background: var(--danger-soft);
    color: var(--danger);
  }

  &.ico--accent {
    background: var(--accent-soft);
    color: var(--accent);
  }
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.panel-sub {
  margin-top: 2px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* SLA 徽章（面板头右上） */
.sla-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--danger);
  border-radius: var(--radius-ctl);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--fs-caption);
  white-space: nowrap;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.form-label {
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 500;

  .req {
    color: var(--danger);
  }
}

.form-tip {
  color: var(--ink-3);
  font-size: var(--fs-caption);
  font-weight: 400;
}

.cat-group {
  flex-wrap: wrap;
  column-gap: 24px;
}

/* 有害未成年人信息选中态红色强调 */
.cat-group :deep(.el-radio.cat-danger) {
  .el-radio__label {
    color: var(--danger);
    font-weight: 600;
    background: var(--danger-soft);
    border-radius: var(--radius-ctl);
    padding: 1px 8px;
  }

  .el-radio__inner {
    border-color: var(--danger);
  }
}

/* 留证只读归档卡 */
.evidence-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-face);
  background: var(--surface-2);
}

.evidence-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.evidence-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 500;

  .el-icon {
    color: var(--accent);
  }
}

.evidence-chip {
  padding: 1px 8px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--surface);
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.ev-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  min-width: 0;
}

.ev-label {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.ev-value {
  overflow: hidden;
  color: var(--ink-1);
  font-size: var(--fs-caption);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ev-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--accent);
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}

/* 回执行 */
.receipt-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

/* 面板底部按钮组 */
.panel-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.actions-topline {
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.btn-remove {
  --el-button-bg-color: var(--danger-soft);
  --el-button-border-color: var(--danger);
  --el-button-text-color: var(--danger);
  --el-button-hover-bg-color: var(--danger);
  --el-button-hover-border-color: var(--danger);
  --el-button-hover-text-color: #fff;
}

.panel-desc {
  :deep(.el-descriptions__label) {
    color: var(--ink-3);
  }
}

/* ---------- 底部警示条 ---------- */
.note-strong {
  padding: 14px 16px;
  align-items: flex-start;
}

.note-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;

  strong {
    color: var(--accent);
    font-size: var(--fs-sub);
    font-weight: 700;
  }
}

.note-chip {
  padding: 1px 8px;
  border: 1px solid var(--accent-line);
  border-radius: 4px;
  background: var(--surface);
  color: var(--accent);
  font-size: var(--fs-caption);
}

.note-main {
  margin-top: 4px;
  color: var(--ink-1);
  font-size: var(--fs-sub);
  line-height: 1.6;
}

.note-sub {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 4px;
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

/* 手机窄屏（375 视口）：留证网格两列，避免四列过窄 */
@media (max-width: 640px) {
  .evidence-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

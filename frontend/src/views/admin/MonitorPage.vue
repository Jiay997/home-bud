<!--
  文件级注释：系统监控页（运行指标与告警快照，数据源 GET /metrics）
  - 页头卡：标题 + 说明（进程内视角：多实例部署各进程独立聚合）+ 手动刷新 + 自动刷新开关（30s）
  - 告警区：alerts 逐条展示（超阈值项）；无告警时展示"运行正常"
  - KPI 区：请求/错误/Agent 调用与失败/降级/拦截/额度用尽 7 项计数
  - 延迟卡：P50 / P95 / 样本数（最近 1000 条环形采样）
  - 比率卡：agent_fail_rate / timeout_rate / degraded_rate（百分比展示，超阈值红色标注）
  - 告警历史卡：alert_watch 任务留痕最近 50 条（GET /admin/metrics/alert-history），失败静默
  - 阈值口径：后端按 METRIC_ALERT_* 环境变量（缺省 0.03/0.05/0.03）评估，仅超阈值项进入 alerts
-->
<template>
  <div class="monitor-page">
    <!-- 1. 页头卡 -->
    <section class="st-card head-card">
      <div class="head-text">
        <h2 class="head-title">系统监控</h2>
        <p class="head-sub">
          进程内运行指标 · 请求/Agent/降级/拦截/额度计数 · P50/P95 延迟 · 超阈值告警
          <span v-if="lastUpdated" class="head-time">最近刷新 {{ lastUpdated }}</span>
        </p>
      </div>
      <div class="head-actions">
        <el-switch v-model="autoRefresh" active-text="自动刷新 30s" />
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </section>

    <!-- 2. 告警区 -->
    <section class="alert-zone" v-if="loaded">
      <el-alert
        v-for="a in alerts"
        :key="a.metric"
        :title="a.message"
        type="error"
        :closable="false"
        show-icon
      />
      <div v-if="alerts.length === 0" class="st-card ok-banner">
        <span class="st-tag st-tag--green">运行正常</span>
        <span class="ok-text">当前无触发告警的指标（阈值口径见后端 METRIC_ALERT_* 配置）</span>
      </div>
    </section>

    <!-- 3. KPI 计数卡 -->
    <section class="kpi-grid">
      <div v-for="k in kpiDefs" :key="k.key" class="st-card kpi-tile">
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-value" :class="k.tone">{{ counters[k.key] ?? 0 }}</div>
        <div class="kpi-foot">{{ k.hint }}</div>
      </div>
    </section>

    <!-- 4. 延迟与比率 -->
    <section class="two-col">
      <div class="st-card">
        <h3 class="card-title">延迟分位（毫秒）</h3>
        <div class="lat-row">
          <div class="lat-cell">
            <div class="lat-label">P50</div>
            <div class="lat-value">{{ latency.p50 ?? 0 }}</div>
          </div>
          <div class="lat-cell">
            <div class="lat-label">P95</div>
            <div class="lat-value">{{ latency.p95 ?? 0 }}</div>
          </div>
          <div class="lat-cell">
            <div class="lat-label">样本数</div>
            <div class="lat-value">{{ latency.samples ?? 0 }}</div>
          </div>
        </div>
        <p class="card-note">延迟采样为最近 1000 条请求的环形缓冲；冷启动无样本时分位为 0。</p>
      </div>
      <div class="st-card">
        <h3 class="card-title">关键比率</h3>
        <div v-for="r in rateDefs" :key="r.key" class="rate-row">
          <span class="rate-label">{{ r.label }}</span>
          <span class="rate-value">{{ fmtRate(rates[r.key]) }}</span>
          <span
            class="st-tag"
            :class="alertMetrics.has(r.key) ? 'st-tag--red' : 'st-tag--green'"
          >
            {{ alertMetrics.has(r.key) ? '超阈值' : '正常' }}
          </span>
        </div>
        <p class="card-note">超阈值判定以后端告警评估为准（分母为 0 时不计触发）。</p>
      </div>
    </section>

    <!-- 5. 告警历史 -->
    <section class="st-card">
      <h3 class="card-title">告警历史</h3>
      <el-table :data="alertHistory" empty-text="暂无告警记录" size="small">
        <el-table-column prop="started_at" label="时间" width="200" />
        <el-table-column prop="metric" label="指标" width="170" />
        <el-table-column prop="value" label="数值" width="110" />
        <el-table-column prop="threshold" label="阈值" width="110" />
        <el-table-column prop="message" label="消息" min-width="220" />
      </el-table>
      <p class="card-note">
        告警由 alert_watch 任务每分钟评估留痕，同一指标 10 分钟窗口内去重；仅保留最近 50 条。
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。加载 GET /metrics 渲染指标与告警；挂载时拉取告警历史；
 * 支持手动刷新与 30s 自动刷新（仅刷新指标快照）。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { adminApi, ApiError } from '../../api/admin'

/** 加载中 */
const loading = ref(false)
/** 首次加载完成标记（告警区加载前不渲染） */
const loaded = ref(false)
/** 自动刷新开关（默认开启） */
const autoRefresh = ref(true)
/** 最近刷新时间（HH:mm:ss） */
const lastUpdated = ref('')
/** 指标包络数据（counters/latency/rates/alerts） */
const metrics = ref<any>(null)
/** 告警历史列表（alert_watch 任务留痕，最近 50 条） */
const alertHistory = ref<any[]>([])

/** 计数区便捷引用 */
const counters = computed<Record<string, number>>(() => metrics.value?.counters || {})
/** 延迟分位 */
const latency = computed<any>(() => metrics.value?.latency || {})
/** 比率 */
const rates = computed<Record<string, number>>(() => metrics.value?.rates || {})
/** 告警列表 */
const alerts = computed<any[]>(() => (Array.isArray(metrics.value?.alerts) ? metrics.value.alerts : []))
/** 已触发告警的指标名集合（比率卡着色用） */
const alertMetrics = computed<Set<string>>(() => new Set(alerts.value.map((a) => a.metric)))

/** KPI 定义（计数 + 展示提示；fail 类计数用红色调） */
const kpiDefs = [
  { key: 'request_count', label: '请求总数', hint: 'HTTP 请求累计计数', tone: '' },
  { key: 'error_count', label: '错误数（5xx）', hint: '故障代理指标 → timeout_rate', tone: 'warn' },
  { key: 'agent_total_count', label: 'Agent 调用', hint: '路由/检索节点调用累计', tone: '' },
  { key: 'agent_fail_count', label: 'Agent 失败', hint: '失败率 → agent_fail_rate', tone: 'warn' },
  { key: 'degraded_count', label: '降级交付', hint: '存在失败分节但整体可用', tone: 'warn' },
  { key: 'blocked_count', label: '风险拦截', hint: 'blocked 帧下发次数', tone: '' },
  { key: 'quota_exhausted_count', label: '额度用尽', hint: '免费额度用尽拒绝（1202）', tone: '' },
]

/** 比率定义（与后端 rates 键对齐） */
const rateDefs = [
  { key: 'agent_fail_rate', label: 'Agent 失败率' },
  { key: 'timeout_rate', label: '请求错误率' },
  { key: 'degraded_rate', label: '降级率' },
]

/**
 * 函数级注释：比率格式化为百分比（小数 2 位；空值回退 0.00%）
 * @param v 0~1 的比率值
 * @returns 百分比字符串
 */
function fmtRate(v?: number): string {
  return `${((v || 0) * 100).toFixed(2)}%`
}

/**
 * 函数级注释：加载指标快照（GET /metrics）并更新刷新时间
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data: any = await adminApi.metrics()
    metrics.value = data
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '指标加载失败')
  } finally {
    loading.value = false
    loaded.value = true
  }
}

/**
 * 函数级注释：加载告警历史（GET /admin/metrics/alert-history）；失败静默仅 console.warn
 */
async function loadAlertHistory(): Promise<void> {
  try {
    const data: any = await adminApi.alertHistory()
    alertHistory.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    console.warn('告警历史加载失败', e)
  }
}

/** 自动刷新定时器句柄 */
let timer: ReturnType<typeof setInterval> | null = null

/**
 * 函数级注释：按开关启停 30s 自动刷新
 * @param on 开关状态
 */
function applyAutoRefresh(on: boolean): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (on) {
    timer = setInterval(load, 30000)
  }
}

watch(autoRefresh, applyAutoRefresh)

onMounted(() => {
  load()
  loadAlertHistory()
  applyAutoRefresh(autoRefresh.value)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.monitor-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 页头 */
.head-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 24px;
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.head-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.head-time {
  margin-left: 8px;
  font-family: var(--font-numeric);
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

/* 告警区 */
.alert-zone {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ok-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
}

.ok-text {
  font-size: var(--fs-sub);
  color: var(--ink-2);
}

/* KPI 网格 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.kpi-tile {
  padding: 14px 16px;
}

.kpi-label {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.kpi-value {
  margin-top: 6px;
  font-family: var(--font-numeric);
  font-size: 26px;
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.2;
}

.kpi-value.warn {
  color: var(--warn);
}

.kpi-foot {
  margin-top: 6px;
  font-size: 11px;
  color: var(--ink-3);
}

/* 延迟与比率双栏 */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 900px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}

.card-title {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
  margin-bottom: 12px;
}

.card-note {
  margin-top: 10px;
  font-size: 11px;
  color: var(--ink-3);
}

.lat-row {
  display: flex;
  gap: 12px;
}

.lat-cell {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--sc-low, var(--surface-2));
}

.lat-label {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.lat-value {
  margin-top: 4px;
  font-family: var(--font-numeric);
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-1);
}

.rate-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--line);
}

.rate-row:last-of-type {
  border-bottom: none;
}

.rate-label {
  flex: 1;
  font-size: var(--fs-sub);
  color: var(--ink-2);
}

.rate-value {
  font-family: var(--font-numeric);
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
}

/* 手机窄屏（375 视口）：页头按钮与延迟格换行，消除横向滚动 */
@media (max-width: 640px) {
  .head-card {
    padding: 16px;
  }
  .head-actions {
    flex-wrap: wrap;
  }
  .lat-row {
    flex-wrap: wrap;
  }
}
</style>

<template>
  <view class="reminder-page tex">
    <MiniPageHeader :title="pageTitle" :subtitle="pageSubtitle" />

    <view class="page-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />
      <StateSkeleton
        v-else-if="state === 'error'"
        mode="empty"
        :title="errorTitle"
        :copy="errorMessage"
        :action-text="retryCopy"
        @action="load(true)"
      />

      <template v-else>
        <!-- 提醒类型开关 -->
        <text class="group-title">{{ groupPrefs }}</text>
        <view class="card">
          <view v-for="pref in prefRows" :key="pref.type" class="switch-row">
            <view class="switch-main">
              <text class="switch-title">{{ pref.label }}</text>
              <text class="switch-sub">{{ pref.sub }}</text>
            </view>
            <button
              class="switch-btn"
              :class="{ on: pref.enabled, busy: pref.busy }"
              :disabled="pref.busy"
              hover-class="pressed"
              @tap="togglePref(pref.type, !pref.enabled)"
            >
              {{ pref.enabled ? switchOn : switchOff }}
            </button>
          </view>
          <view class="card-note">
            <text class="note-copy">{{ weeklyCapCopy }}</text>
            <text v-if="!templateReported" class="note-warn">{{ templateMissingCopy }}</text>
          </view>
        </view>

        <button
          class="off-button"
          :class="{ disabled: offBusy || !anyEnabled }"
          :disabled="offBusy || !anyEnabled"
          hover-class="pressed"
          @tap="disableAll"
        >
          {{ offBusy ? offBusyCopy : (anyEnabled ? offCopy : offDoneCopy) }}
        </button>

        <!-- 任务列表（含站内补达） -->
        <text class="group-title">{{ groupTasks }}</text>
        <view v-if="!tasks.length" class="card empty-card">
          <text class="note-copy">{{ tasksEmptyCopy }}</text>
        </view>
        <view v-else class="card">
          <view
            v-for="task in tasks"
            :key="task.task_uid"
            class="task-row"
            hover-class="row-pressed"
            @tap="openTask(task)"
          >
            <view class="task-main">
              <view class="task-head">
                <text class="task-title">{{ task.title }}</text>
                <text class="task-tag" :class="deliveryTone(task)">{{ deliveryLabel(task) }}</text>
              </view>
              <text v-if="task.body" class="task-body">{{ task.body }}</text>
              <text class="task-meta">{{ taskMeta(task) }}</text>
            </view>
            <view class="row-arrow" />
          </view>
        </view>

        <!-- 成长周报 -->
        <text class="group-title">{{ groupWeekly }}</text>
        <view class="card">
          <view class="weekly-head">
            <text class="weekly-title">{{ weeklyTitle }}</text>
            <text v-if="reportPeriod" class="weekly-period">{{ reportPeriod }}</text>
          </view>
          <view v-if="weeklyLoading" class="weekly-loading">
            <text class="note-copy">{{ weeklyLoadingCopy }}</text>
          </view>
          <view v-else-if="weeklyError" class="weekly-error">
            <text class="note-warn">{{ weeklyError }}</text>
            <button class="mini-link" hover-class="pressed" @tap="loadWeeklyReport">{{ retryCopy }}</button>
          </view>
          <template v-else-if="report">
            <view v-if="report.profiles.length" class="profile-list">
              <view v-for="(profile, profileIndex) in report.profiles" :key="profileIndex" class="profile-row">
                <text class="profile-name">{{ profile.nickname_masked || profileTitleFallback }}</text>
                <text class="profile-delta">{{ profile.delta_label }}</text>
              </view>
            </view>
            <text v-else class="note-copy">{{ profilesEmptyCopy }}</text>

            <view v-if="report.last_week_topics.length" class="topic-row">
              <text class="topic-label">{{ lastWeekTopicsCopy }}</text>
              <view class="topic-chips">
                <text v-for="(topic, topicIndex) in report.last_week_topics" :key="topicIndex" class="topic-chip">{{ topic }}</text>
              </view>
            </view>

            <view v-if="report.suggested_questions.length" class="suggest-list">
              <text class="suggest-label">{{ suggestCopy }}</text>
              <view
                v-for="(suggest, suggestIndex) in report.suggested_questions"
                :key="suggestIndex"
                class="suggest-row"
                hover-class="row-pressed"
                @tap="askQuestion(suggest.question)"
              >
                <text class="suggest-title">{{ suggest.title }}</text>
                <text class="suggest-question">{{ suggest.question }}</text>
              </view>
            </view>

            <text v-if="report.privacy_note" class="privacy-note">{{ report.privacy_note }}</text>
          </template>
        </view>

        <!-- 每周一问 -->
        <text class="group-title">{{ groupWeeklyQuestion }}</text>
        <view class="card">
          <view v-if="weeklyQuestionLoading" class="weekly-loading">
            <text class="note-copy">{{ weeklyLoadingCopy }}</text>
          </view>
          <view v-else-if="weeklyQuestion && weeklyQuestion.enabled" class="question-card" hover-class="row-pressed" @tap="openWeeklyQuestion">
            <text class="question-title">{{ weeklyQuestion.title }}</text>
            <text class="question-copy">{{ weeklyQuestion.question }}</text>
            <view class="question-foot">
              <text class="question-action">{{ weeklyQuestionAction }}</text>
              <text class="question-arrow">→</text>
            </view>
          </view>
          <view v-else class="weekly-loading">
            <text class="note-copy">{{ weeklyQuestionOffCopy }}</text>
          </view>
        </view>

        <MiniComplianceBar />
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import {
  api,
  type ReminderPrefView,
  type ReminderTaskView,
  type WeeklyQuestionView,
  type WeeklyReportView
} from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const pageTitle = '提醒设置'
const pageSubtitle = '疫苗 / 复查 / 每周成长周报'
const errorTitle = '提醒设置暂时无法打开'
const retryCopy = '重新加载'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'
const groupPrefs = '提醒类型'
const groupTasks = '提醒任务'
const groupWeekly = '成长周报'
const groupWeeklyQuestion = '每周一问'
const switchOn = '已开启'
const switchOff = '已关闭'
const offCopy = '一键关闭全部触达'
const offBusyCopy = '正在关闭…'
const offDoneCopy = '全部触达已关闭'
const offDoneToast = '已关闭全部触达'
const offFailedCopy = '关闭失败，请稍后重试。'
const prefFailedCopy = '设置失败，请稍后重试。'
const tasksEmptyCopy = '暂无提醒任务。建立孩子或宠物档案后会按疫苗接种与复查节点生成提醒。'
const profilesEmptyCopy = '还没有孩子或宠物档案，建立档案后可查看月龄变化。'
const weeklyLoadingCopy = '正在读取…'
const weeklyTitle = '本月龄变化与可问主题'
const weeklyQuestionAction = '带着这个问题去提问'
const weeklyQuestionOffCopy = '每周一问当前未开启，可在上方提醒类型中开启。'
const templateMissingCopy = '订阅消息模板尚未配置，当前提醒只在站内补达。'
const lastWeekTopicsCopy = '上周关注的题目标签'
const suggestCopy = '本周可问'
const profileTitleFallback = '档案'
const openFailedCopy = '提醒打开失败，请稍后重试。'
const weeklyCapLabel = (weekly: number) => `提醒按周合并发送，每周最多 ${weekly || 2} 条，可在下方逐项关闭。`

const taskTypeLabels: Record<string, string> = {
  vaccine: '疫苗',
  checkup: '复查',
  deworm: '驱虫',
  report: '报告',
  weekly_q: '每周一问',
  all: '全部提醒'
}

const taskTypeSubs: Record<string, string> = {
  vaccine: '按疫苗接种节点提醒',
  checkup: '按体检与复查节点提醒',
  deworm: '按驱虫周期提醒',
  report: '成长周报与报告节点提醒',
  weekly_q: '每周一条分龄话题',
  all: '总开关，关闭后不发送任何提醒'
}

const statusLabels: Record<string, string> = {
  pending: '待发送',
  sent: '已发送',
  opened: '已打开',
  skipped: '已跳过',
  canceled: '已取消'
}

const deliveryLabels: Record<string, string> = {
  inbox: '站内补达',
  subscribe_message: '订阅消息'
}

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const loading = ref(false)
const prefs = ref<ReminderPrefView[]>([])
const tasks = ref<ReminderTaskView[]>([])
const weeklyMax = ref(2)
const templateReported = ref(true)
const busyTypes = ref<Record<string, boolean>>({})
const offBusy = ref(false)
const report = ref<WeeklyReportView | null>(null)
const weeklyLoading = ref(false)
const weeklyError = ref('')
const weeklyQuestion = ref<WeeklyQuestionView | null>(null)
const weeklyQuestionLoading = ref(false)

const prefRows = computed(() => prefs.value.map((pref) => ({
  type: pref.type,
  label: taskTypeLabels[pref.type] || pref.type,
  sub: taskTypeSubs[pref.type] || '',
  enabled: pref.enabled,
  busy: busyTypes.value[pref.type] === true
})))
const anyEnabled = computed(() => prefs.value.some((pref) => pref.type !== 'all' && pref.enabled))
const reportPeriod = computed(() => {
  const period = report.value?.period
  if (!period?.start) return ''
  return `${String(period.start).slice(0, 10)} 至 ${String(period.end || period.start).slice(0, 10)}`
})
const weeklyCapCopy = computed(() => weeklyCapLabel(weeklyMax.value))

function deliveryLabel(task: ReminderTaskView) {
  return deliveryLabels[task.delivery] || deliveryLabels.inbox
}

function deliveryTone(task: ReminderTaskView) {
  return task.delivery === 'inbox' ? 'tone-inbox' : 'tone-message'
}

function taskMeta(task: ReminderTaskView) {
  const parts: string[] = []
  if (task.planned_at) parts.push(`计划 ${String(task.planned_at).slice(0, 10)}`)
  if (task.status) parts.push(statusLabels[task.status] || '待发送')
  return parts.join(' · ')
}

async function load(showLoading = false) {
  if (showLoading) state.value = 'loading'
  if (loading.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const result = await api.listReminders()
    prefs.value = result.prefs?.items || []
    tasks.value = result.items || []
    weeklyMax.value = Number(result.prefs?.weekly_max) || Number(result.weekly_cap?.weekly_max) || 2
    templateReported.value = result.prefs?.template_reported !== false
    state.value = 'ready'
    void loadWeeklyReport()
    void loadWeeklyQuestion()
  } catch (error: any) {
    if (state.value === 'ready') {
      uni.showToast({ title: userFacingMessage(error, refreshFailedCopy), icon: 'none' })
    } else {
      errorMessage.value = userFacingMessage(error, connectFailedCopy)
      state.value = 'error'
    }
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

async function loadWeeklyReport() {
  if (weeklyLoading.value) return
  weeklyLoading.value = true
  weeklyError.value = ''
  try {
    report.value = await api.fetchWeeklyReport()
  } catch (error: any) {
    weeklyError.value = userFacingMessage(error, refreshFailedCopy)
  } finally {
    weeklyLoading.value = false
  }
}

async function loadWeeklyQuestion() {
  if (weeklyQuestionLoading.value) return
  weeklyQuestionLoading.value = true
  try {
    weeklyQuestion.value = await api.fetchWeeklyQuestion()
  } catch {
    weeklyQuestion.value = null
  } finally {
    weeklyQuestionLoading.value = false
  }
}

async function togglePref(type: string, enabled: boolean) {
  if (busyTypes.value[type]) return
  busyTypes.value = { ...busyTypes.value, [type]: true }
  try {
    const result = await api.updateReminderPref({ pref_type: type, enabled })
    prefs.value = result.prefs?.items || prefs.value
    if (type === 'all' && !enabled) {
      uni.showToast({ title: offDoneToast, icon: 'none' })
      void load()
    }
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, prefFailedCopy), icon: 'none' })
  } finally {
    busyTypes.value = { ...busyTypes.value, [type]: false }
  }
}

async function disableAll() {
  if (offBusy.value || !anyEnabled.value) return
  offBusy.value = true
  try {
    const result = await api.disableAllReminders()
    prefs.value = result.prefs?.items || prefs.value
    uni.showToast({ title: offDoneToast, icon: 'none' })
    void load()
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, offFailedCopy), icon: 'none' })
  } finally {
    offBusy.value = false
  }
}

// 任务的归因链起点：标记已打开后带 reminder_trace_id 进入问答（RQ-08 AC-RQ08-8）
// 入口按任务所属档案类型选择（宠物类提醒不应落到育儿入口）
function entryOfTask(task: ReminderTaskView): string {
  const profileType = String(task.profile_type || '').toLowerCase()
  if (profileType === 'pet') return 'pet'
  if (profileType === 'child') return 'child'
  return 'family'
}

async function openTask(task: ReminderTaskView) {
  try {
    const result = await api.openReminder(task.task_uid)
    const trace = result.trace_id || task.trace_id || ''
    const entry = entryOfTask(task)
    uni.navigateTo({
      url: `/pages/qa/index?entry=${entry}&reminder_trace_id=${encodeURIComponent(trace)}`,
      fail: () => uni.showToast({ title: openFailedCopy, icon: 'none' })
    })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, openFailedCopy), icon: 'none' })
  }
}

function askQuestion(question: string) {
  const text = String(question || '').trim()
  if (!text) return
  uni.navigateTo({
    url: `/pages/qa/index?entry=child&q=${encodeURIComponent(text)}`,
    fail: () => uni.showToast({ title: openFailedCopy, icon: 'none' })
  })
}

function openWeeklyQuestion() {
  const current = weeklyQuestion.value
  if (!current?.question) return
  const trace = encodeURIComponent(current.trace_id || '')
  uni.navigateTo({
    url: `/pages/qa/index?entry=child&q=${encodeURIComponent(current.question)}&reminder_trace_id=${trace}`,
    fail: () => uni.showToast({ title: openFailedCopy, icon: 'none' })
  })
}

onLoad(() => { void load(true) })
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.reminder-page { min-height: 100vh; padding-bottom: 40rpx; background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }

.group-title { display: block; margin: 30rpx 0 14rpx; color: var(--ink-3); font-size: 24rpx; }
.card { padding: 8rpx 24rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.card + .card { margin-top: 18rpx; }
.empty-card { padding: 26rpx 24rpx; }

.switch-row { display: flex; align-items: center; gap: 18rpx; padding: 22rpx 0; }
.switch-row + .switch-row { border-top: 1px solid var(--line); }
.switch-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 6rpx; }
.switch-title { color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.switch-sub { color: var(--ink-3); font-size: 22rpx; line-height: 1.5; }
.switch-btn { flex: none; display: inline-flex; align-items: center; justify-content: center; min-width: 132rpx; min-height: 60rpx; margin: 0; padding: 0 24rpx; color: var(--ink-3); background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 23rpx; line-height: 1; }
.switch-btn.on { color: var(--on-primary); background: var(--primary); border-color: var(--primary); }
.switch-btn.busy { opacity: .6; }
.card-note { padding: 4rpx 0 20rpx; }
.note-copy { display: block; color: var(--ink-3); font-size: 22rpx; line-height: 1.65; }
.note-warn { display: block; margin-top: 8rpx; color: var(--warn); font-size: 22rpx; line-height: 1.65; }

.off-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 84rpx; margin: 20rpx 0 0; color: var(--danger); background: var(--danger-soft); border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 26rpx; font-weight: 650; }
.off-button.disabled { color: var(--ink-3); background: var(--surface-warm); border-color: var(--line); }

.task-row { display: flex; align-items: center; gap: 16rpx; padding: 22rpx 0; }
.task-row + .task-row { border-top: 1px solid var(--line); }
.row-pressed { background: var(--surface-warm); }
.task-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 8rpx; }
.task-head { display: flex; align-items: center; gap: 12rpx; }
.task-title { flex: 1; color: var(--ink-1); font-size: 27rpx; font-weight: 650; }
.task-tag { flex: none; padding: 4rpx 14rpx; border-radius: var(--r-control); font-size: 20rpx; line-height: 1.5; }
.tone-inbox { color: var(--primary-press); background: var(--primary-soft); }
.tone-message { color: var(--info); background: var(--info-soft); }
.task-body { color: var(--ink-2); font-size: 24rpx; line-height: 1.6; }
.task-meta { color: var(--ink-3); font-size: 21rpx; }
.row-arrow { flex: none; width: 12rpx; height: 12rpx; border-top: 1rpx solid var(--ink-3); border-right: 1rpx solid var(--ink-3); transform: rotate(45deg); }

.weekly-head { display: flex; align-items: baseline; justify-content: space-between; gap: 14rpx; padding: 20rpx 0 6rpx; }
.weekly-title { color: var(--ink-1); font-size: 27rpx; font-weight: 650; }
.weekly-period { color: var(--ink-3); font-size: 21rpx; font-variant-numeric: tabular-nums; }
.weekly-loading { padding: 16rpx 0 22rpx; }
.weekly-error { display: flex; flex-direction: column; gap: 12rpx; padding: 16rpx 0 22rpx; }
.mini-link { align-self: flex-start; margin: 0; padding: 6rpx 0; color: var(--primary-press); background: transparent; border: 0; font-size: 23rpx; line-height: 1.4; }
.profile-list { padding: 10rpx 0 4rpx; }
.profile-row { display: flex; align-items: baseline; gap: 14rpx; padding: 8rpx 0; }
.profile-name { color: var(--ink-1); font-size: 25rpx; font-weight: 650; }
.profile-delta { flex: 1; color: var(--ink-2); font-size: 23rpx; line-height: 1.6; }
.topic-row { padding: 12rpx 0 4rpx; }
.topic-label { display: block; color: var(--ink-3); font-size: 22rpx; }
.topic-chips { display: flex; flex-wrap: wrap; gap: 10rpx; margin-top: 10rpx; }
.topic-chip { padding: 6rpx 16rpx; color: var(--ink-2); background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 21rpx; }
.suggest-list { padding: 16rpx 0 0; }
.suggest-label { display: block; color: var(--ink-3); font-size: 22rpx; }
.suggest-row { margin-top: 12rpx; padding: 16rpx 18rpx; background: var(--surface-warm); border: 1px solid var(--line-warm); border-radius: var(--r-inner); }
.suggest-title { display: block; color: var(--ink-1); font-size: 25rpx; font-weight: 650; }
.suggest-question { display: block; margin-top: 6rpx; color: var(--ink-2); font-size: 23rpx; line-height: 1.6; }
.privacy-note { display: block; padding: 18rpx 0 20rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.6; }

.question-card { padding: 20rpx 0 22rpx; }
.question-title { display: block; color: var(--ink-3); font-size: 22rpx; }
.question-copy { display: block; margin-top: 10rpx; color: var(--ink-1); font-size: 28rpx; font-weight: 650; line-height: 1.6; }
.question-foot { display: flex; align-items: baseline; justify-content: flex-end; gap: 8rpx; margin-top: 16rpx; }
.question-action { color: var(--primary-press); font-size: 24rpx; }
.question-arrow { color: var(--primary-press); font-size: 24rpx; }
</style>

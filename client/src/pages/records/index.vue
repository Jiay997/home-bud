<template>
  <view class="records-page tex">
    <MiniPageHeader title="记录" />

    <view class="records-body">
      <view class="chip-row" role="tablist" aria-label="记录筛选">
        <button
          v-for="preset in presets"
          :key="preset.key"
          class="chip"
          :class="{ active: activePreset === preset.key }"
          :aria-pressed="activePreset === preset.key"
          hover-class="chip-pressed"
          @tap="setPreset(preset.key)"
        >{{ preset.label }}</button>
      </view>

      <StateSkeleton v-if="loading && !items.length" mode="skeleton" />

      <StateSkeleton
        v-else-if="errorMessage"
        mode="empty"
        :title="errorTitle"
        :copy="errorMessage"
        :action-text="retryCopy"
        @action="retryLoad"
      />

      <StateSkeleton
        v-else-if="!items.length && activePreset === 'all'"
        mode="empty"
        :title="emptyTitle"
        :copy="emptyCopy"
        :action-text="emptyAction"
        @action="goAsk"
      />

      <StateSkeleton
        v-else-if="!items.length"
        mode="empty"
        :title="filteredEmptyTitle"
        :copy="filteredEmptyCopy"
        :action-text="filteredEmptyAction"
        @action="clearFilter"
      />

      <template v-else>
        <view class="record-list">
          <view
            v-for="item in items"
            :key="`${item.item_type}-${item.uid}`"
            class="record-card"
            :aria-label="item.summary"
            hover-class="card-pressed"
            @tap="openRecord(item)"
          >
            <view class="record-head">
              <text class="record-time">{{ relativeTime(item.created_at) }}</text>
              <view class="record-type" :class="item.item_type === 'report' ? 'type-report' : 'type-qa'">
                <view class="type-glyph" :class="item.item_type === 'report' ? 'glyph-bars' : 'glyph-bubble'">
                  <view v-if="item.item_type === 'report'" /><view v-if="item.item_type === 'report'" /><view v-if="item.item_type === 'report'" />
                </view>
                <text>{{ typeLabel(item) }}</text>
              </view>
            </view>
            <text class="record-summary">{{ summaryLine(item) }}</text>
            <view class="record-foot">
              <text class="record-full-time">{{ fullTime(item.created_at) }}</text>
              <text class="record-access" :class="accessTone(item)">{{ accessLabel(item) }}</text>
            </view>
          </view>
        </view>

        <view v-if="loading" class="more-note"><text>{{ loadingMoreCopy }}</text></view>
        <button v-else-if="moreError" class="more-error" hover-class="card-pressed" @tap="loadMoreRetry">
          <text>{{ moreError }}</text><text class="more-retry">{{ retryCopy }}</text>
        </button>
        <text v-else-if="!hasMore" class="end-note">{{ endCopy }}</text>
      </template>
    </view>

    <MiniComplianceBar fixed />
    <MiniTabBar active="records" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { api, type MeView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniTabBar from '../../components/MiniTabBar.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

type RecordItem = {
  item_type: 'qa' | 'report'
  uid: string
  created_at: string
  summary: string
  is_member_content: boolean
  profile_type: 'child' | 'pet' | 'family'
}

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const errorTitle = '记录暂时无法打开'
const retryCopy = '重新加载'
const emptyTitle = '还没有记录'
const emptyCopy = '先问第一个问题，对话与报告都会留在这里。'
const emptyAction = '去提问'
const filteredEmptyTitle = '没有符合条件的记录'
const filteredEmptyCopy = '换一个筛选条件看看，或清空筛选查看全部记录。'
const filteredEmptyAction = '清空筛选'
const loadingMoreCopy = '正在加载更早记录…'
const accessFree = '免费内容'
const accessMember = '会员内容'
const accessReadonly = '已到期 · 只读'
const objectLabels: Record<string, string> = { child: '孩子', pet: '宠物', family: '家庭' }
const reportSummaryLabel = '阶段测评报告'
// 跳转失败兜底提示
const askFallbackCopy = '对话页打开失败，请稍后重试。'

type Preset = { key: string; label: string; query: { type: 'all' | 'qa' | 'report'; profile_type?: 'child' | 'pet' | 'family' } }
const presets: Preset[] = [
  { key: 'all', label: '全部', query: { type: 'all' } },
  { key: 'child', label: '孩子', query: { type: 'all', profile_type: 'child' } },
  { key: 'pet', label: '宠物', query: { type: 'all', profile_type: 'pet' } },
  { key: 'qa', label: '问答', query: { type: 'qa' } },
  { key: 'report', label: '报告', query: { type: 'report' } }
]

const items = ref<RecordItem[]>([])
const activePreset = ref('all')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const moreError = ref('')
const hasMore = ref(false)
const isMember = ref(false)

const endCopy = computed(() => `共 ${total.value} 条记录 · 已全部加载`)

function applyMembership(meView: MeView | null) {
  if (!meView) return
  const expireMs = meView.member_expire_at ? new Date(meView.member_expire_at).getTime() : 0
  isMember.value = meView.member_status === 'member' && (!expireMs || expireMs > Date.now())
}

async function load(reset = false) {
  if (loading.value) return
  if (reset) {
    page.value = 1
    items.value = []
  }
  loading.value = true
  errorMessage.value = ''
  moreError.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const preset = presets.find((item) => item.key === activePreset.value) || presets[0]
    const [result, meResult] = await Promise.allSettled([
      api.history({ ...preset.query, page: page.value, page_size: pageSize }),
      api.me().catch(() => null)
    ])
    if (meResult.status === 'fulfilled') applyMembership(meResult.value)
    if (result.status === 'rejected') throw result.reason
    items.value = page.value === 1 ? result.value.items : [...items.value, ...result.value.items]
    total.value = result.value.total
    hasMore.value = items.value.length < result.value.total
  } catch (error: any) {
    if (page.value === 1) {
      errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
    } else {
      moreError.value = userFacingMessage(error, '更早的记录暂时加载失败。')
    }
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function setPreset(key: string) {
  if (activePreset.value === key) return
  activePreset.value = key
  uni.pageScrollTo({ scrollTop: 0, duration: 0 })
  void load(true)
}

function clearFilter() {
  setPreset('all')
}

function retryLoad() {
  void load(true)
}

function loadMoreRetry() {
  void load()
}

function loadMore() {
  if (!hasMore.value || loading.value) return
  page.value += 1
  void load()
}

function typeLabel(item: RecordItem) {
  return item.item_type === 'report' ? '报告' : '问答'
}

function summaryLine(item: RecordItem) {
  const prefix = objectLabels[item.profile_type] || ''
  if (item.item_type === 'report') {
    return [prefix, reportSummaryLabel, item.summary].filter(Boolean).join(' · ')
  }
  return [prefix, item.summary || '未填写记录摘要'].filter(Boolean).join(' · ')
}

function accessLabel(item: RecordItem) {
  if (!item.is_member_content) return accessFree
  return isMember.value ? accessMember : accessReadonly
}

function accessTone(item: RecordItem) {
  if (!item.is_member_content) return 'tone-free'
  return isMember.value ? 'tone-member' : 'tone-readonly'
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function relativeTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未记录'
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const stamp = date.getTime()
  const clock = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (stamp >= startOfToday) return `今天 ${clock}`
  if (stamp >= startOfToday - 86400000) return `昨天 ${clock}`
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日 ${clock}`
}

function fullTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未记录'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function openRecord(item: RecordItem) {
  if (item.item_type === 'report') {
    uni.navigateTo({ url: `/pages/report/index?uid=${encodeURIComponent(item.uid)}&history=1` })
    return
  }
  uni.navigateTo({ url: `/pages/qa/index?uid=${encodeURIComponent(item.uid)}&history=1` })
}

/**
 * 空态「去提问」：直接打开 AI 对话页（不再 redirectTo 回首页）。
 * 缺陷修复：先前实现为 `uni.redirectTo({ url: '/pages/index/index' })`，
 * 点击后只是回到首页、并不进入对话，用户观感即「点了没反应/没打开 AI 对话」；
 * 且 redirectTo 会顶掉记录页（丢失底部 Tab 上下文）。改为 navigateTo 进入
 * 家庭综合问答（孩子+宠物同场景，任意用户都可用），返回键可回到记录列表。
 */
function goAsk() {
  uni.navigateTo({
    url: '/pages/qa/index?entry=family',
    fail: () => {
      // 极端情况（页面栈满/路由异常）兜底回首页，保证点击一定有响应
      uni.showToast({ title: askFallbackCopy, icon: 'none' })
      uni.redirectTo({ url: '/pages/index/index' })
    }
  })
}

onLoad(() => { void load(true) })
onPullDownRefresh(() => { void load(true) })
onReachBottom(() => { loadMore() })
</script>

<style scoped>
.records-page { min-height: 100vh; padding-bottom: calc(272rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.records-body { padding: 24rpx 32rpx 0; }
.card-pressed { opacity: .88; }

.chip-row { display: flex; gap: 16rpx; padding-bottom: 26rpx; }
.chip { flex: none; display: inline-flex; align-items: center; justify-content: center; min-height: 66rpx; margin: 0; padding: 0 26rpx; color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 24rpx; line-height: 1; }
.chip.active { color: var(--primary-press); background: var(--primary-soft); border-color: var(--primary); font-weight: 650; }
.chip-pressed { opacity: .78; }

.record-list { display: flex; flex-direction: column; gap: 20rpx; }
.record-card { padding: 26rpx 28rpx 24rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-inner); box-shadow: var(--shadow-card); }
.record-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.record-time { color: var(--ink-1); font-size: 27rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.record-type { display: inline-flex; align-items: center; gap: 8rpx; padding: 6rpx 16rpx; border-radius: var(--r-control); font-size: 21rpx; line-height: 1.4; }
.type-qa { color: var(--info); background: var(--info-soft); }
.type-report { color: var(--primary-press); background: var(--primary-soft); }
.type-glyph { position: relative; width: 22rpx; height: 22rpx; flex: none; }
.glyph-bubble::before { position: absolute; top: 2rpx; left: 0; width: 20rpx; height: 14rpx; border: 2rpx solid currentColor; border-radius: 6rpx; content: ''; }
.glyph-bubble::after { position: absolute; bottom: 0; left: 5rpx; width: 7rpx; height: 7rpx; border-bottom: 2rpx solid currentColor; border-left: 2rpx solid currentColor; content: ''; transform: skewX(-12deg); }
.glyph-bars { display: flex; align-items: flex-end; justify-content: space-between; padding: 4rpx 1rpx 1rpx; }
.glyph-bars view { width: 4rpx; background: currentColor; border-radius: 2rpx; }
.glyph-bars view:nth-child(1) { height: 9rpx; }
.glyph-bars view:nth-child(2) { height: 16rpx; }
.glyph-bars view:nth-child(3) { height: 12rpx; }
.record-summary { display: block; margin-top: 16rpx; overflow: hidden; color: var(--ink-1); font-size: 29rpx; line-height: 1.5; text-overflow: ellipsis; white-space: nowrap; }
.record-foot { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; margin-top: 16rpx; }
.record-full-time { color: var(--ink-3); font-size: 22rpx; font-variant-numeric: tabular-nums; }
.record-access { flex: none; padding: 4rpx 14rpx; border-radius: var(--r-control); font-size: 21rpx; }
.tone-free { color: var(--ink-3); background: var(--surface-warm); border: 1px solid var(--line); }
.tone-member { color: var(--warn); background: var(--warn-soft); }
.tone-readonly { color: var(--danger); background: var(--danger-soft); }

.more-note { display: block; padding: 30rpx 0 10rpx; color: var(--ink-3); font-size: 24rpx; text-align: center; }
.more-error { display: flex; align-items: center; justify-content: center; gap: 14rpx; width: 100%; min-height: 76rpx; margin: 24rpx 0 0; padding: 0 24rpx; color: var(--ink-2); background: var(--warn-soft); border: 0; border-radius: var(--r-control); font-size: 24rpx; }
.more-retry { color: var(--warn); font-size: 24rpx; font-weight: 650; }
.end-note { display: block; padding: 32rpx 0 10rpx; color: var(--ink-3); font-size: 23rpx; font-variant-numeric: tabular-nums; text-align: center; }
</style>

<template>
  <view class="pledge-page tex">
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

      <template v-else-if="pledge">
        <view class="pledge-head">
          <text class="pledge-title">{{ headTitle(pledge.items.length) }}</text>
          <text class="pledge-meta">{{ versionCopy(pledge.version) }}</text>
        </view>

        <view v-for="(item, index) in pledge.items" :key="item.id" class="pledge-card">
          <view class="pledge-row">
            <text class="pledge-index">{{ indexLabel(index) }}</text>
            <text class="pledge-item-title">{{ item.title }}</text>
          </view>
          <text class="pledge-promise">{{ item.promise }}</text>
          <text class="pledge-evidence">{{ evidenceCopy(item.evidence) }}</text>
          <button
            v-if="item.action && item.action.route"
            class="pledge-action"
            hover-class="pressed"
            @tap="openAction(item)"
          >
            {{ item.action.label }}
          </button>
        </view>

        <view class="pledge-block" :class="{ highlight: highlightTraining }">
          <text class="pledge-block-title">{{ trainingTitle }}</text>
          <text class="pledge-block-copy">{{ pledge.training_statement }}</text>
        </view>

        <view class="pledge-block">
          <text class="pledge-block-title">{{ honestyTitle }}</text>
          <text class="pledge-block-copy">{{ pledge.honesty_note }}</text>
        </view>

        <text v-if="pledge.first_boot_hint" class="pledge-hint">{{ pledge.first_boot_hint }}</text>

        <MiniComplianceBar />
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import { api, type PrivacyPledgeItem, type PrivacyPledgeView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { decodeRouteValue } from '../../services/route'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const pageTitle = '隐私承诺'
const pageSubtitle = '只写已经做到的事'
const errorTitle = '隐私承诺暂时无法打开'
const retryCopy = '重新加载'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'
const headTitle = (count: number) => `${count} 条承诺，逐条可核对`
const versionCopy = (version: string) => `承诺版本 ${version || '—'}`
const indexLabel = (index: number) => `承诺 ${index + 1}`
const evidenceCopy = (evidence: string) => `实现证据：${evidence || '待补充'}`
const trainingTitle = '训练口径声明'
const honestyTitle = '诚实说明'
const selfRouteHint = '已定位到本页对应段落'

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const pledge = ref<PrivacyPledgeView | null>(null)
const highlightTraining = ref(false)
const loading = ref(false)

/**
 * 打开承诺项的可操作跳转。
 * 指向本页的路由不重复跳转，改为高亮对应段落（避免页面栈自嵌套）。
 * @param item 承诺项
 */
function openAction(item: PrivacyPledgeItem) {
  const route = String(item.action?.route || '')
  if (!route) return
  if (route.includes('/pages/privacy-pledge/')) {
    highlightTraining.value = route.includes('section=training')
    if (highlightTraining.value) uni.showToast({ title: selfRouteHint, icon: 'none' })
    return
  }
  uni.navigateTo({
    url: route,
    fail: () => uni.reLaunch({ url: '/pages/index/index' })
  })
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
    pledge.value = await api.fetchPrivacyPledge()
    state.value = 'ready'
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

onLoad((query) => {
  highlightTraining.value = decodeRouteValue(query?.section) === 'training'
  void load(true)
})
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.pledge-page { min-height: 100vh; padding-bottom: 40rpx; background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }

.pledge-head { padding: 6rpx 0 18rpx; }
.pledge-title { display: block; color: var(--ink-1); font-size: 34rpx; font-weight: 700; line-height: 1.4; }
.pledge-meta { display: block; margin-top: 8rpx; color: var(--ink-3); font-size: 23rpx; }

.pledge-card { margin-bottom: 20rpx; padding: 26rpx 26rpx 22rpx; background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.pledge-row { display: flex; align-items: center; gap: 14rpx; }
.pledge-index { flex: none; padding: 4rpx 16rpx; color: var(--primary-press); background: var(--primary-soft); border-radius: var(--r-control); font-size: 21rpx; line-height: 1.6; }
.pledge-item-title { flex: 1; color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.pledge-promise { display: block; margin-top: 14rpx; color: var(--ink-2); font-size: 27rpx; line-height: 1.75; }
.pledge-evidence { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.pledge-action { display: inline-flex; align-items: center; justify-content: center; margin: 18rpx 0 0; padding: 0 30rpx; min-height: 68rpx; color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 24rpx; }

.pledge-block { margin-top: 24rpx; padding: 24rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-card); }
.pledge-block.highlight { background: var(--primary-soft); border-color: var(--primary); }
.pledge-block-title { display: block; color: var(--ink-1); font-size: 27rpx; font-weight: 650; }
.pledge-block-copy { display: block; margin-top: 10rpx; color: var(--ink-2); font-size: 25rpx; line-height: 1.75; }
.pledge-hint { display: block; margin-top: 22rpx; color: var(--ink-3); font-size: 23rpx; line-height: 1.6; }
</style>

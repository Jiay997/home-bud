<template>
  <view class="topics-page tex">
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
        <view class="page-tag">
          <view class="tag-dot" />
          <text class="tag-text">{{ aiLabelText }}</text>
        </view>
        <text class="page-note">{{ memberNote }}</text>

        <view v-if="!topics.length" class="card empty-card">
          <text class="note-copy">{{ emptyCopy }}</text>
        </view>

        <view v-for="topic in topics" :key="topic.topic_code" class="card">
          <view class="topic-head" hover-class="row-pressed" @tap="toggleTopic(topic)">
            <view class="topic-main">
              <view class="topic-title-row">
                <text class="topic-title">{{ topic.title }}</text>
                <text v-if="topic.redflag_first" class="redflag-tag">{{ redflagTagCopy }}</text>
              </view>
              <text class="topic-summary">{{ topic.summary }}</text>
              <view class="topic-meta">
                <text class="topic-domain">{{ domainLabel(topic.domain) }}</text>
                <text class="topic-price">{{ priceText(topic.price_micro) }}</text>
              </view>
            </view>
            <text class="topic-caret">{{ expandedCode === topic.topic_code ? collapseCopy : expandCopy }}</text>
          </view>

          <view v-if="expandedCode === topic.topic_code" class="topic-detail">
            <view v-if="detailLoading" class="detail-loading"><text class="note-copy">{{ detailLoadingCopy }}</text></view>

            <template v-else>
              <view v-if="redflagBlocks.length" class="redflag-box">
                <view class="redflag-head">
                  <view class="redflag-mark" />
                  <text class="redflag-title">{{ redflagTitle }}</text>
                </view>
                <view v-for="(block, blockIndex) in redflagBlocks" :key="blockIndex" class="redflag-block">
                  <text v-if="block.title" class="redflag-block-title">{{ block.title }}</text>
                  <MiniMarkdown v-if="block.content" :content="block.content" />
                </view>
              </view>

              <view v-for="(block, blockIndex) in bodyBlocks" :key="blockIndex" class="body-block">
                <text v-if="block.title" class="body-block-title">{{ block.title }}</text>
                <MiniMarkdown v-if="block.content" :content="block.content" />
              </view>

              <view class="price-box">
                <view class="price-line">
                  <text class="price-label">{{ priceLabel }}</text>
                  <text class="price-amount">{{ priceText(currentDetail?.price_micro || 0) }}</text>
                </view>
                <text class="price-note">{{ memberExcludedNote }}</text>
                <text class="price-note">{{ purchaseNote(currentDetail) }}</text>
              </view>

              <text v-if="currentDetail?.disclaimer" class="disclaimer-copy">{{ currentDetail.disclaimer }}</text>

              <view class="detail-actions">
                <button class="detail-button ghost" hover-class="pressed" @tap="askAboutTopic(topic)">{{ askCopy }}</button>
              </view>
            </template>
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
import { api, type TopicBlockView, type TopicView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniMarkdown from '../../components/MiniMarkdown.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { qaAiLabelText } from '../../services/qa-copy'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const pageTitle = '专题'
const pageSubtitle = '交叉主题与行为内容线'
const errorTitle = '专题暂时无法打开'
const retryCopy = '重新加载'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'
const emptyCopy = '专题内容准备中，可先使用问答。'
const memberNote = '专题独立计费，会员权益不含专题内容'
const memberExcludedNote = '会员权益不包含专题内容，专题需单独获取'
const redflagTagCopy = '红旗前置'
const redflagTitle = '先看红旗：何时需要就医而不是继续观察'
const expandCopy = '展开'
const collapseCopy = '收起'
const detailLoadingCopy = '正在读取专题内容…'
const priceLabel = '专题价格'
const askCopy = '就这个主题提问'
const detailFailedCopy = '专题内容读取失败，请稍后重试。'
const navFailedCopy = '页面打开失败，请稍后重试。'
const priceUnavailableCopy = '价格待配置'
const purchasableCopy = '可获取：购买入口以线上商品配置为准'
const unpurchasableCopy = '暂未上架，仅可查看介绍'

const domainLabels: Record<string, string> = {
  cross: '育儿 × 宠物交叉',
  behavior: '宠物行为',
  child: '育儿',
  pet: '宠物'
}

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const topics = ref<TopicView[]>([])
const loading = ref(false)
const expandedCode = ref('')
const detailLoading = ref(false)
const detailCache = ref<Record<string, TopicView>>({})

const currentDetail = computed(() => (expandedCode.value ? detailCache.value[expandedCode.value] || null : null))
const aiLabelText = computed(() => qaAiLabelText(topics.value[0]?.ai_label || null))
const redflagBlocks = computed<TopicBlockView[]>(() => currentDetail.value?.redflag_blocks || [])
// 服务端把红旗块拼在 content_blocks 前部：正文需按红旗段宽切片，避免重复展示
const bodyBlocks = computed<TopicBlockView[]>(() => {
  const detail = currentDetail.value
  if (!detail) return []
  const blocks = detail.content_blocks || []
  if (!detail.redflag_first || !redflagBlocks.value.length) return blocks
  return blocks.slice(redflagBlocks.value.length)
})

function domainLabel(value: string) {
  return domainLabels[String(value || '')] || domainLabels.child
}

function priceText(priceMicro: number) {
  const yuan = Number(priceMicro) / 1e6
  if (!Number.isFinite(yuan) || yuan <= 0) return priceUnavailableCopy
  return `${parseFloat(yuan.toFixed(2)).toString()} 元`
}

function purchaseNote(detail: TopicView | null) {
  if (!detail) return ''
  return detail.purchasable ? purchasableCopy : unpurchasableCopy
}

function toggleTopic(topic: TopicView) {
  if (expandedCode.value === topic.topic_code) {
    expandedCode.value = ''
    return
  }
  expandedCode.value = topic.topic_code
  void ensureDetail(topic)
}

async function ensureDetail(topic: TopicView) {
  if (detailCache.value[topic.topic_code]) return
  detailLoading.value = true
  try {
    const detail = await api.fetchTopic(topic.topic_code)
    detailCache.value = { ...detailCache.value, [topic.topic_code]: detail }
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, detailFailedCopy), icon: 'none' })
    detailCache.value = { ...detailCache.value, [topic.topic_code]: topic }
  } finally {
    detailLoading.value = false
  }
}

function askAboutTopic(topic: TopicView) {
  const question = `${topic.title}：需要注意什么？`
  uni.navigateTo({
    url: `/pages/qa/index?entry=${encodeURIComponent(topic.domain === 'pet' || topic.domain === 'behavior' ? 'pet' : 'child')}&q=${encodeURIComponent(question)}`,
    fail: () => uni.showToast({ title: navFailedCopy, icon: 'none' })
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
    const result = await api.listTopics()
    topics.value = result.items || []
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

onLoad(() => { void load(true) })
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.topics-page { min-height: 100vh; padding-bottom: 40rpx; background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }

.page-tag { display: inline-flex; align-items: center; gap: 10rpx; padding: 8rpx 18rpx; background: var(--info-soft); border-radius: var(--r-control); }
.tag-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: var(--info); }
.tag-text { color: var(--ink-2); font-size: 22rpx; }
.page-note { display: block; margin: 12rpx 0 20rpx; color: var(--ink-3); font-size: 22rpx; }

.card { margin-bottom: 20rpx; padding: 6rpx 24rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.empty-card { padding: 26rpx 24rpx; }
.note-copy { display: block; color: var(--ink-3); font-size: 23rpx; line-height: 1.65; }

.topic-head { display: flex; align-items: center; gap: 16rpx; padding: 22rpx 0; }
.row-pressed { background: var(--surface-warm); }
.topic-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 8rpx; }
.topic-title-row { display: flex; align-items: center; gap: 12rpx; }
.topic-title { color: var(--ink-1); font-size: 29rpx; font-weight: 650; }
.redflag-tag { flex: none; padding: 4rpx 14rpx; color: var(--danger); background: var(--danger-soft); border-radius: var(--r-control); font-size: 20rpx; }
.topic-summary { color: var(--ink-2); font-size: 24rpx; line-height: 1.6; }
.topic-meta { display: flex; align-items: baseline; gap: 16rpx; }
.topic-domain { color: var(--ink-3); font-size: 21rpx; }
.topic-price { color: var(--warn); font-size: 23rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.topic-caret { flex: none; color: var(--primary-press); font-size: 23rpx; }

.topic-detail { padding: 4rpx 0 22rpx; border-top: 1px solid var(--line); }
.detail-loading { padding: 20rpx 0; }

.redflag-box { margin-top: 20rpx; padding: 20rpx; background: var(--danger-soft); border: 2rpx solid var(--danger); border-radius: var(--r-inner); }
.redflag-head { display: flex; align-items: center; gap: 12rpx; }
.redflag-mark { width: 16rpx; height: 16rpx; flex: none; border-radius: 50%; background: var(--danger); }
.redflag-title { flex: 1; color: var(--danger); font-size: 26rpx; font-weight: 700; line-height: 1.6; }
.redflag-block { margin-top: 14rpx; }
.redflag-block-title { display: block; color: var(--ink-1); font-size: 25rpx; font-weight: 650; }

.body-block { margin-top: 22rpx; }
.body-block-title { display: block; margin-bottom: 6rpx; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }

.price-box { margin-top: 24rpx; padding: 18rpx; background: var(--surface-warm); border: 1px solid var(--line-warm); border-radius: var(--r-inner); }
.price-line { display: flex; align-items: baseline; justify-content: space-between; gap: 14rpx; }
.price-label { color: var(--ink-2); font-size: 24rpx; }
.price-amount { color: var(--warn); font-size: 30rpx; font-weight: 700; font-variant-numeric: tabular-nums; }
.price-note { display: block; margin-top: 10rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.6; }
.disclaimer-copy { display: block; margin-top: 16rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.65; }

.detail-actions { display: flex; gap: 16rpx; margin-top: 22rpx; }
.detail-button { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 78rpx; margin: 0; color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 24rpx; }
</style>

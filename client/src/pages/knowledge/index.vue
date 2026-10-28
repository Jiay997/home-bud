<template>
  <view class="book-page tex">
    <MiniPageHeader :title="pageTitle" :subtitle="pageSubtitle" />

    <view class="page-body">
      <view class="page-tag">
        <view class="tag-dot" />
        <text class="tag-text">{{ sourceNote }}</text>
      </view>

      <scroll-view class="tab-scroll" scroll-x :show-scrollbar="false">
        <view class="tab-row">
          <view
            v-for="tab in tabs"
            :key="tab.code"
            class="tab-item"
            :class="{ active: selected === tab.code }"
            hover-class="tab-pressed"
            @tap="selectTab(tab.code)"
          >
            <text class="tab-label">{{ tab.label }}</text>
            <text class="tab-count">{{ tab.count }}</text>
          </view>
        </view>
      </scroll-view>

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
        <view v-if="!filteredItems.length" class="card empty-card">
          <text class="empty-title">{{ emptyTitle }}</text>
          <text class="empty-copy">{{ emptyCopy }}</text>
        </view>

        <view
          v-for="item in filteredItems"
          :key="item.kb_id"
          class="card knowledge-entry"
          hover-class="entry-pressed"
          @tap="toggleEntry(item.kb_id)"
        >
          <view class="entry-head">
            <view class="entry-tags">
              <view class="entry-tag"><text>{{ item.category_label }}</text></view>
              <view v-if="item.stage_label" class="entry-tag ghost"><text>{{ item.stage_label }}</text></view>
              <view v-if="item.topic" class="entry-tag plain"><text>{{ item.topic }}</text></view>
            </view>
            <text class="entry-toggle">{{ expandedId === item.kb_id ? collapseCopy : expandCopy }}</text>
          </view>

          <text class="entry-title">{{ item.title }}</text>
          <text class="entry-summary">{{ item.summary }}</text>

          <view v-if="expandedId === item.kb_id" class="entry-detail">
            <text class="entry-content">{{ item.content }}</text>
            <view v-if="item.preconditions" class="detail-block">
              <text class="detail-label">{{ preconditionsLabel }}</text>
              <text class="detail-copy">{{ item.preconditions }}</text>
            </view>
            <view v-if="item.source_name" class="detail-block">
              <text class="detail-label">{{ sourceLabel }}</text>
              <text class="detail-copy">{{ item.source_name }}</text>
            </view>
          </view>
        </view>

        <text class="page-disclaimer">{{ disclaimer }}</text>
      </template>
    </view>

    <MiniComplianceBar />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import { api, type KnowledgeCategory, type KnowledgeCategoryView, type KnowledgeEntryView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

type TabCode = 'all' | KnowledgeCategory

type TabItem = {
  code: TabCode
  label: string
  count: number
}

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const pageTitle = '科普全书'
const pageSubtitle = '按业务模块分类的养育科普'
const sourceNote = '知识来源 · 公开指南与机构资料'
const errorTitle = '科普内容暂时无法打开'
const retryCopy = '重新加载'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'
const emptyTitle = '这个分类还没有内容'
const emptyCopy = '知识库正在补充中，可先切换到其他分类看看。'
const expandCopy = '展开'
const collapseCopy = '收起'
const preconditionsLabel = '适用前提'
const sourceLabel = '来源'
const disclaimer = '内容为养育科普参考，不替代医生或兽医的诊断与治疗。'

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const loading = ref(false)
const items = ref<KnowledgeEntryView[]>([])
const categories = ref<KnowledgeCategoryView[]>([])
const selected = ref<TabCode>('all')
const expandedId = ref('')

/**
 * 顶部 tab 列表：全部 + 后端下发的业务模块（母婴 / 幼儿 / 宠物 / 家庭共处）。
 */
const tabs = computed<TabItem[]>(() => [
  { code: 'all', label: '全部', count: items.value.length },
  ...categories.value.map((item) => ({
    code: item.code as TabCode,
    label: item.label,
    count: item.count
  }))
])

/**
 * 当前分类下的知识条目（分类切换为前端本地筛选，避免每次切换重复请求）。
 */
const filteredItems = computed(() =>
  selected.value === 'all' ? items.value : items.value.filter((item) => item.category === selected.value)
)

/**
 * 切换业务模块分类。
 *
 * @param code 目标分类编码（all 或后端下发的分类）
 */
function selectTab(code: TabCode) {
  if (selected.value === code) return
  selected.value = code
  expandedId.value = ''
}

/**
 * 展开 / 收起单条知识。
 *
 * @param kbId 知识条目业务编号
 */
function toggleEntry(kbId: string) {
  expandedId.value = expandedId.value === kbId ? '' : kbId
}

/**
 * 加载科普全书内容。
 *
 * @param showLoading 是否展示首屏骨架（下拉刷新时保持原内容）
 */
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
    const result = await api.fetchKnowledgeEntries()
    items.value = result.items || []
    categories.value = result.categories || []
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
.book-page { min-height: 100vh; padding-bottom: 40rpx; background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }

.page-tag { display: inline-flex; align-items: center; gap: 10rpx; padding: 8rpx 18rpx; background: var(--info-soft); border-radius: var(--r-control); }
.tag-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: var(--info); }
.tag-text { color: var(--ink-2); font-size: 22rpx; }

.tab-scroll { width: 100%; margin: 18rpx 0 18rpx; white-space: nowrap; }
.tab-row { display: inline-flex; gap: 12rpx; padding-bottom: 6rpx; }
.tab-item { display: inline-flex; align-items: center; gap: 8rpx; padding: 12rpx 22rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-control); }
.tab-pressed { opacity: .82; }
.tab-label { color: var(--ink-2); font-size: 24rpx; line-height: 1.3; }
.tab-count { min-width: 30rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.3; text-align: center; font-variant-numeric: tabular-nums; }
.tab-item.active { background: var(--primary); border-color: var(--primary); }
.tab-item.active .tab-label,
.tab-item.active .tab-count { color: var(--on-primary); }

.card { margin-bottom: 20rpx; padding: 24rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.empty-card { padding: 32rpx 28rpx; }
.empty-title { display: block; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.empty-copy { display: block; margin-top: 10rpx; color: var(--ink-3); font-size: 23rpx; line-height: 1.65; }

.knowledge-entry { transition: background-color 160ms ease-out; }
.entry-pressed { background: var(--surface-warm); }
.entry-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.entry-tags { display: flex; flex-wrap: wrap; gap: 8rpx; min-width: 0; }
.entry-tag { padding: 6rpx 16rpx; color: var(--primary-press); background: var(--primary-soft); border-radius: var(--r-control); font-size: 20rpx; line-height: 1.3; }
.entry-tag.ghost { color: var(--ink-2); background: var(--surface-warm); }
.entry-tag.plain { color: var(--ink-3); background: transparent; padding-left: 0; }
.entry-toggle { flex: none; color: var(--primary-press); font-size: 22rpx; }
.entry-title { display: block; margin-top: 16rpx; color: var(--ink-1); font-size: 30rpx; font-weight: 650; line-height: 1.45; }
.entry-summary { display: block; margin-top: 10rpx; color: var(--ink-2); font-size: 24rpx; line-height: 1.68; }
.entry-detail { margin-top: 18rpx; padding-top: 18rpx; border-top: 1px solid var(--line); }
.entry-content { display: block; color: var(--ink-1); font-size: 25rpx; line-height: 1.8; }
.detail-block { margin-top: 16rpx; padding: 16rpx 18rpx; background: var(--surface-warm); border-radius: var(--r-inner); }
.detail-label { display: block; color: var(--primary-press); font-size: 21rpx; font-weight: 650; }
.detail-copy { display: block; margin-top: 6rpx; color: var(--ink-2); font-size: 22rpx; line-height: 1.65; }

.page-disclaimer { display: block; padding: 24rpx 0 8rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.65; text-align: center; }

@media (prefers-reduced-motion: reduce) {
  .knowledge-entry { transition: none; }
}
</style>

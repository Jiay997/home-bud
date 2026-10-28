<template>
  <view class="tools-page tex">
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
        <text class="page-note">{{ quotaNote }}</text>

        <view v-if="!tools.length" class="card empty-card">
          <text class="note-copy">{{ emptyCopy }}</text>
        </view>

        <view v-for="tool in tools" :key="tool.tool_code" class="card">
          <view class="tool-head" hover-class="row-pressed" @tap="toggleTool(tool)">
            <view class="tool-main">
              <view class="tool-title-row">
                <text class="tool-title">{{ tool.title }}</text>
                <text class="tool-tag">{{ typeLabel(tool.tool_type) }}</text>
              </view>
              <text class="tool-summary">{{ tool.summary }}</text>
              <text class="tool-domain">{{ domainLabel(tool.domain) }}</text>
            </view>
            <text class="tool-caret">{{ expandedCode === tool.tool_code ? collapseCopy : expandCopy }}</text>
          </view>

          <view v-if="expandedCode === tool.tool_code" class="tool-detail">
            <view v-if="detailLoading" class="detail-loading"><text class="note-copy">{{ detailLoadingCopy }}</text></view>

            <template v-else>
              <view v-if="currentDetail?.content?.steps?.length" class="detail-block">
                <text class="detail-title">{{ stepsTitle }}</text>
                <view
                  v-for="(step, stepIndex) in (currentDetail?.content?.steps || [])"
                  :key="step.key || stepIndex"
                  class="step-row"
                  hover-class="pressed"
                  @tap="toggleStep(tool.tool_code, step.key || String(stepIndex))"
                >
                  <view class="step-box" :class="{ checked: stepChecked(tool.tool_code, step.key || String(stepIndex)) }">
                    <view v-if="stepChecked(tool.tool_code, step.key || String(stepIndex))" class="step-tick" />
                  </view>
                  <view class="step-main">
                    <text class="step-title">{{ step.title }}</text>
                    <text v-if="step.detail" class="step-detail">{{ step.detail }}</text>
                  </view>
                </view>
              </view>

              <view v-if="currentDetail?.content?.escalation?.length" class="detail-block">
                <text class="detail-title">{{ escalationTitle }}</text>
                <view v-for="(flag, flagIndex) in (currentDetail?.content?.escalation || [])" :key="flagIndex" class="flag-row">
                  <view class="flag-dot" />
                  <text class="flag-text">{{ flag }}</text>
                </view>
              </view>

              <view v-if="currentDetail?.content?.how_to_read?.length" class="detail-block">
                <text class="detail-title">{{ howToReadTitle }}</text>
                <view v-for="(line, lineIndex) in (currentDetail?.content?.how_to_read || [])" :key="lineIndex" class="flag-row">
                  <view class="flag-dot" />
                  <text class="flag-text">{{ line }}</text>
                </view>
              </view>

              <view v-if="currentDetail?.content?.common_hazards?.length" class="detail-block">
                <text class="detail-title">{{ hazardTitle }}</text>
                <view v-for="(line, lineIndex) in (currentDetail?.content?.common_hazards || [])" :key="lineIndex" class="flag-row">
                  <view class="flag-dot warn" />
                  <text class="flag-text">{{ line }}</text>
                </view>
              </view>

              <text v-if="currentDetail?.content?.caveat" class="caveat-copy">{{ currentDetail.content.caveat }}</text>
              <text v-if="currentDetail?.disclaimer" class="disclaimer-copy">{{ currentDetail.disclaimer }}</text>

              <view class="detail-actions">
                <button
                  class="detail-button"
                  :class="{ disabled: completeBusy === tool.tool_code }"
                  :disabled="completeBusy === tool.tool_code"
                  hover-class="pressed"
                  @tap="completeTool(tool)"
                >
                  {{ completeBusy === tool.tool_code ? completeBusyCopy : completeCopy(checkedCount(tool.tool_code)) }}
                </button>
                <button class="detail-button ghost" hover-class="pressed" @tap="askFromTool(tool)">{{ askCopy }}</button>
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
import { api, type ToolView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { qaAiLabelText } from '../../services/qa-copy'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const pageTitle = '工具'
const pageSubtitle = '自查清单与配料表解析'
const errorTitle = '工具暂时无法打开'
const retryCopy = '重新加载'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'
const emptyCopy = '工具内容准备中，可先使用问答。'
const quotaNote = '工具内容不消耗问答次数'
const expandCopy = '展开'
const collapseCopy = '收起'
const stepsTitle = '自查步骤（可勾选）'
const escalationTitle = '出现以下情况请就医'
const howToReadTitle = '配料表怎么看'
const hazardTitle = '常见禁忌成分'
const detailLoadingCopy = '正在读取工具内容…'
const completeBusyCopy = '记录中…'
const askCopy = '深入问问'
const completeDoneCopy = '已记录本次自查'
const completeFailedCopy = '记录失败，请稍后重试。'
const detailFailedCopy = '工具内容读取失败，请稍后重试。'
const navFailedCopy = '页面打开失败，请稍后重试。'
/** D-12：深入问问二次确认文案（明确告知会消耗提问额度） */
const deepAskTitle = '深入问问'
const deepAskConfirmCopy = '将带入该工具的问题并自动发起提问，会消耗 1 次免费提问额度，是否继续？'
const deepAskConfirmAction = '继续提问'
const deepAskCancelAction = '取消'
const completeCopy = (count: number) => (count ? `完成自查（已勾选 ${count} 项）` : '完成自查')

const typeLabels: Record<string, string> = {
  checklist: '自查清单',
  parser: '解析工具'
}
const domainLabels: Record<string, string> = {
  child: '育儿',
  pet: '宠物'
}

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const tools = ref<ToolView[]>([])
const loading = ref(false)
const expandedCode = ref('')
const detailLoading = ref(false)
const detailCache = ref<Record<string, ToolView>>({})
const checkedSteps = ref<Record<string, Record<string, boolean>>>({})
const completeBusy = ref('')

const currentDetail = computed(() => (expandedCode.value ? detailCache.value[expandedCode.value] || null : null))
const aiLabelText = computed(() => qaAiLabelText(tools.value[0]?.ai_label || null))

function typeLabel(value: string) {
  return typeLabels[String(value || '')] || typeLabels.checklist
}
function domainLabel(value: string) {
  return domainLabels[String(value || '')] || ''
}

function stepChecked(code: string, key: string) {
  return checkedSteps.value[code]?.[key] === true
}

function toggleStep(code: string, key: string) {
  const current = checkedSteps.value[code] || {}
  checkedSteps.value = { ...checkedSteps.value, [code]: { ...current, [key]: !current[key] } }
}

function checkedCount(code: string) {
  const current = checkedSteps.value[code] || {}
  return Object.values(current).filter(Boolean).length
}

function toggleTool(tool: ToolView) {
  if (expandedCode.value === tool.tool_code) {
    expandedCode.value = ''
    return
  }
  expandedCode.value = tool.tool_code
  void ensureDetail(tool)
}

async function ensureDetail(tool: ToolView) {
  if (detailCache.value[tool.tool_code]) return
  detailLoading.value = true
  try {
    // 详情接口同时记录一次「查看」行为（服务端归因），列表数据较简，故按需拉取
    const detail = await api.fetchTool(tool.tool_code)
    detailCache.value = { ...detailCache.value, [tool.tool_code]: detail }
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, detailFailedCopy), icon: 'none' })
    detailCache.value = { ...detailCache.value, [tool.tool_code]: tool }
  } finally {
    detailLoading.value = false
  }
}

async function completeTool(tool: ToolView) {
  if (completeBusy.value) return
  completeBusy.value = tool.tool_code
  try {
    await api.completeTool(tool.tool_code, { completed_items: checkedCount(tool.tool_code), next: 'done' })
    uni.showToast({ title: completeDoneCopy, icon: 'none' })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, completeFailedCopy), icon: 'none' })
  } finally {
    completeBusy.value = ''
  }
}

function askFromTool(tool: ToolView) {
  const question = `${tool.title}：${tool.summary}`
  // D-12：带入问题会自动发起提问并消耗 1 次免费额度，必须先二次确认；
  // 问题通过本地存储传递，避免 URL query 反复编码（H5 地址栏出现双重编码）。
  uni.showModal({
    title: deepAskTitle,
    content: deepAskConfirmCopy,
    confirmText: deepAskConfirmAction,
    cancelText: deepAskCancelAction,
    success: (result) => {
      if (!result.confirm) return
      try {
        uni.setStorageSync('qa:prefill', question)
      } catch {
        // 存储不可用时回退 URL 传参（单次编码，QA 页按需解码）
      }
      uni.navigateTo({
        url: `/pages/qa/index?entry=${encodeURIComponent(tool.domain || 'child')}`,
        fail: () => uni.showToast({ title: navFailedCopy, icon: 'none' })
      })
    }
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
    const result = await api.listTools()
    tools.value = result.items || []
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
.tools-page { min-height: 100vh; padding-bottom: 40rpx; background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }

.page-tag { display: inline-flex; align-items: center; gap: 10rpx; padding: 8rpx 18rpx; background: var(--info-soft); border-radius: var(--r-control); }
.tag-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: var(--info); }
.tag-text { color: var(--ink-2); font-size: 22rpx; }
.page-note { display: block; margin: 12rpx 0 20rpx; color: var(--ink-3); font-size: 22rpx; }

.card { margin-bottom: 20rpx; padding: 6rpx 24rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.empty-card { padding: 26rpx 24rpx; }
.note-copy { display: block; color: var(--ink-3); font-size: 23rpx; line-height: 1.65; }

.tool-head { display: flex; align-items: center; gap: 16rpx; padding: 22rpx 0; }
.row-pressed { background: var(--surface-warm); }
.tool-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 8rpx; }
.tool-title-row { display: flex; align-items: center; gap: 12rpx; }
.tool-title { color: var(--ink-1); font-size: 29rpx; font-weight: 650; }
.tool-tag { flex: none; padding: 4rpx 14rpx; color: var(--primary-press); background: var(--primary-soft); border-radius: var(--r-control); font-size: 20rpx; }
.tool-summary { color: var(--ink-2); font-size: 24rpx; line-height: 1.6; }
.tool-domain { color: var(--ink-3); font-size: 21rpx; }
.tool-caret { flex: none; color: var(--primary-press); font-size: 23rpx; }

.tool-detail { padding: 4rpx 0 22rpx; border-top: 1px solid var(--line); }
.detail-loading { padding: 20rpx 0; }
.detail-block { margin-top: 20rpx; }
.detail-title { display: block; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.step-row { display: flex; align-items: flex-start; gap: 14rpx; margin-top: 14rpx; }
.step-box { display: flex; align-items: center; justify-content: center; width: 34rpx; height: 34rpx; margin-top: 4rpx; flex: none; background: var(--surface-warm); border: 2rpx solid var(--line); border-radius: 8rpx; }
.step-box.checked { background: var(--primary); border-color: var(--primary); }
.step-tick { width: 14rpx; height: 8rpx; border-left: 3rpx solid var(--on-primary); border-bottom: 3rpx solid var(--on-primary); transform: rotate(-45deg) translateY(-2rpx); }
.step-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 4rpx; }
.step-title { color: var(--ink-1); font-size: 25rpx; font-weight: 650; line-height: 1.6; }
.step-detail { color: var(--ink-2); font-size: 23rpx; line-height: 1.65; }
.flag-row { display: flex; align-items: flex-start; gap: 10rpx; margin-top: 10rpx; }
.flag-dot { width: 8rpx; height: 8rpx; margin-top: 14rpx; flex: none; border-radius: 50%; background: var(--primary); }
.flag-dot.warn { background: var(--warn); }
.flag-text { flex: 1; color: var(--ink-2); font-size: 23rpx; line-height: 1.65; }
.caveat-copy { display: block; margin-top: 18rpx; padding: 16rpx; color: var(--ink-2); background: var(--warn-soft); border-radius: var(--r-inner); font-size: 23rpx; line-height: 1.7; }
.disclaimer-copy { display: block; margin-top: 14rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.65; }

.detail-actions { display: flex; gap: 16rpx; margin-top: 22rpx; }
.detail-button { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 78rpx; margin: 0; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 24rpx; }
.detail-button.disabled { opacity: .55; }
.detail-button.ghost { color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); }
</style>

<template>
  <view class="report-page tex">
    <MiniPageHeader :title="pageTitle" />
    <view class="report-body">
      <StateSkeleton v-if="loading" mode="skeleton" />
      <view v-else-if="errorMessage" class="error-panel">
        <text class="error-title">报告暂不可用</text>
        <text class="error-copy">{{ errorMessage }}</text>
        <button class="primary-button" hover-class="pressed" @tap="load">重新加载</button>
        <button class="plain-button" hover-class="pressed" @tap="goRecords">稍后在历史记录查看</button>
      </view>
      <template v-else-if="payload">
        <view class="meta-row">
          <text class="meta-copy">{{ metaLine }}</text>
          <text v-if="readonlyMark" class="readonly-pill">{{ readonlyMark }}</text>
        </view>

        <view class="type-hero tex">
          <view class="hero-illustration" aria-hidden="true">
            <view class="hero-moon"><view class="moon-cut" /></view>
            <view class="hero-sprout">
              <view class="sprout-stem" />
              <view class="sprout-leaf sprout-left" />
              <view class="sprout-leaf sprout-right" />
            </view>
          </view>
          <text class="hero-label">{{ heroLabel }}</text>
          <text class="hero-type">{{ typeName }}</text>
          <view class="type-badges">
            <view v-for="item in typeBadges" :key="item.code" class="type-badge" :class="{ active: item.code === typeCode }">
              <text>{{ item.name }}</text>
            </view>
          </view>
        </view>

        <view v-if="bands.length" class="report-card">
          <view class="card-title-row">
            <view class="card-dash" />
            <text class="card-title">{{ bandsTitle }}</text>
          </view>
          <view v-for="(item, index) in bands" :key="item.dimension || index" class="dimension-row">
            <view class="dimension-head">
              <text class="dimension-name">{{ dimensionTitle(item.dimension) }}</text>
              <text class="dimension-band" :class="{ partial: bandText(item) === partialCopy }">{{ bandText(item) }}</text>
            </view>
            <view class="dimension-track" :aria-label="`${dimensionTitle(item.dimension)} ${bandText(item)}`">
              <view v-for="seg in 3" :key="seg" class="dimension-seg" :class="{ filled: segFilled(item, seg) }" />
            </view>
          </view>
          <text v-if="bandsNote" class="card-note">{{ bandsNote }}</text>
        </view>

        <view v-if="typeDesc" class="report-card">
          <view class="card-title-row">
            <view class="card-dash" />
            <text class="card-title">{{ conclusionTitle }}</text>
          </view>
          <text class="paragraph">{{ typeDesc }}</text>
        </view>

        <view v-if="adviceItems.length" class="report-card">
          <view class="card-title-row">
            <view class="card-dash" />
            <text class="card-title">{{ adviceTitle }}</text>
          </view>
          <view v-for="(advice, index) in adviceItems" :key="index" class="advice-row">
            <view class="advice-dot" />
            <text class="advice-copy">{{ advice }}</text>
          </view>
          <text v-if="adviceNote" class="card-note">{{ adviceNote }}</text>
        </view>

        <view v-if="communicationBlock" class="report-card">
          <view class="card-title-row">
            <view class="card-dash" />
            <text class="card-title">{{ communicationTitle }}</text>
          </view>
          <text v-if="communicationText" class="paragraph">{{ communicationText }}</text>
          <view v-else class="gated-block">
            <text v-if="communicationSummary" class="gated-summary">{{ communicationSummary }}</text>
            <button class="gated-action" hover-class="pressed" @tap="goMember">{{ unlockCopy }}</button>
          </view>
        </view>

        <view v-if="waveTriggered" class="wave-notice">
          <view class="notice-head">
            <view class="notice-mark" />
            <text class="notice-title">{{ waveTitle }}</text>
          </view>
          <text class="notice-copy">{{ waveCopy }}</text>
        </view>

        <view class="fatalism-notice">
          <text class="notice-title">{{ nonFatalismTitle }}</text>
          <text class="notice-copy">{{ nonFatalismText }}</text>
        </view>

        <view v-if="memberBlocks.length" class="report-card">
          <view class="card-title-row">
            <view class="card-dash" />
            <text class="card-title">{{ memberSectionTitle }}</text>
          </view>
          <view v-for="block in memberBlocks" :key="block.key" class="member-row">
            <template v-if="block.text">
              <text class="member-title">{{ block.title }}</text>
              <text class="paragraph">{{ block.text }}</text>
            </template>
            <view v-else class="gated-block">
              <text class="gated-title">{{ block.title }}</text>
              <text v-if="block.summary" class="gated-summary">{{ block.summary }}</text>
              <button class="gated-action" hover-class="pressed" @tap="goMember">{{ unlockCopy }}</button>
            </view>
          </view>
        </view>

        <view class="privacy-line">
          <text class="privacy-copy">{{ sharePrivacy }}</text>
        </view>
        <view class="ops-grid">
          <button class="op-item" hover-class="pressed" @tap="saveLongImage">{{ saveCopy }}</button>
          <button class="op-item" open-type="share" hover-class="pressed">{{ shareCopy }}</button>
          <button class="op-item" hover-class="pressed" @tap="feedbackVisible = true">{{ feedbackCopy }}</button>
          <button class="op-item" hover-class="pressed" @tap="reportVisible = true">{{ reportCopy }}</button>
        </view>
        <button class="primary-button" hover-class="pressed" @tap="restartAssessment">{{ retakeCopy }}</button>

        <MiniComplianceBar />
      </template>
    </view>

    <ReportSheet :visible="reportVisible" object-type="assessment" :object-id="reportObjectId" @close="reportVisible = false" />
    <FeedbackSheet :visible="feedbackVisible" @close="feedbackVisible = false" />
    <MiniDialog
      :visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :confirm-text="dialog.confirmText"
      :cancel-text="dialog.cancelText"
      :show-cancel="dialog.showCancel"
      :danger="dialog.danger"
      :input="dialog.input"
      @confirm="onDialogConfirm"
      @cancel="onDialogCancel"
    />
    <canvas type="2d" id="report-export-canvas" class="export-canvas" />
  </view>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, ref } from 'vue'
import { onLoad, onShareAppMessage } from '@dcloudio/uni-app'
import { api } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import ReportSheet from '../../components/ReportSheet.vue'
import FeedbackSheet from '../../components/FeedbackSheet.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { ensureBaseConsent } from '../../services/session'
import { type LongImageDoc } from '../../services/image-export'
import { renderAndSaveLongImage } from '../../platform/long-image'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const pageTitle = '测评报告'
const heroLabel = '阶段观察倾向'
const typeFallback = '阶段气质观察'
const dimensionFallback = '观察维度'
const partialCopy = '信息不足'
const bandTexts = ['偏低', '中等', '偏高']
const childLabel = '被测孩子'
const timeLabel = '生成时间'
const readonlyCopy = '已到期 · 只读'
const unlockCopy = '解锁会员'
const memberSectionTitle = '会员专属内容'
const saveCopy = '保存长图'
const shareCopy = '分享'
const feedbackCopy = '反馈'
const reportCopy = '举报'
const retakeCopy = '再次测评'
const sharePrivacy = '分享前请留意：请勿在分享中暴露孩子的可识别信息（正脸照、姓名、园所、门牌等）。'
const savedCopy = '已保存到相册'
const imageFallback = '图片生成失败，请稍后重试。'
const missingCopy = '缺少报告参数，请从记录中重新进入。'
const defaultNonFatalism = '气质没有好坏，不是宿命判定，只是行为倾向参考'
const disclaimerLine = '本报告由人工智能生成，仅供养育参考，不构成医疗、心理等专业意见或诊断。'

const typeBadges = [
  { code: 'easy', name: '随和型' },
  { code: 'active', name: '活跃型' },
  { code: 'sensitive', name: '敏感型' },
  { code: 'slow_warm', name: '慢热型' }
]
const dimensionNames: Record<string, string> = {
  ACT: '活动水平',
  APP: '趋近-退缩',
  ADP: '适应性',
  EMO: '情绪强度'
}
const memberKeys = ['member_plan_detail', 'member_scores', 'member_history'] as const

const instance = getCurrentInstance()
const uid = ref('')
const historyMode = ref(false)
const loading = ref(true)
const errorMessage = ref('')
const payload = ref<any>(null)
const reportVisible = ref(false)
const feedbackVisible = ref(false)
const savingImage = ref(false)
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

const blocks = computed<any[]>(() => payload.value?.blocks || [])
function blockOf(key: string) {
  return blocks.value.find((item) => item?.key === key) || null
}
function contentOf(key: string) {
  return blockOf(key)?.content || null
}
function titleOf(key: string, fallback: string) {
  return blockOf(key)?.title || fallback
}

const reportHeader = computed<any>(() => contentOf('report_header') || {})
const typeName = computed(() => String(reportHeader.value.type_name || typeFallback))
const typeCode = computed(() => String(contentOf('type_conclusion')?.type_code || ''))
const typeDesc = computed(() => String(contentOf('type_conclusion')?.type_desc || ''))
const bands = computed<any[]>(() => {
  const list = contentOf('dimension_bands')?.bands
  return Array.isArray(list) ? list : []
})
const bandsNote = computed(() => String(contentOf('dimension_bands')?.note || ''))
const bandsTitle = computed(() => titleOf('dimension_bands', '维度档位'))
const conclusionTitle = computed(() => titleOf('type_conclusion', '气质类型解读'))
const adviceTitle = computed(() => titleOf('basic_advice', '通用养育建议'))
const adviceItems = computed<string[]>(() => {
  const items = contentOf('basic_advice')?.items
  return Array.isArray(items) ? items.map((item: unknown) => String(item)) : []
})
const adviceNote = computed(() => String(contentOf('basic_advice')?.note || ''))
const communicationBlock = computed(() => blockOf('member_communication'))
const communicationTitle = computed(() => communicationBlock.value?.title || '亲子沟通建议')
const communicationSummary = computed(() => String(communicationBlock.value?.summary || ''))
const communicationText = computed(() => String(communicationBlock.value?.content?.text || ''))
const memberBlocks = computed(() => memberKeys
  .map((key) => {
    const block = blockOf(key)
    if (!block) return null
    return {
      key,
      title: String(block.title || '深度内容'),
      summary: String(block.summary || ''),
      text: String(block.content?.text || '')
    }
  })
  .filter(Boolean) as Array<{ key: string; title: string; summary: string; text: string }>)
const waveContent = computed<any>(() => contentOf('wave_notice') || {})
const waveTriggered = computed(() => waveContent.value.triggered === true)
const waveTitle = computed(() => titleOf('wave_notice', '成长波动提示'))
const waveCopy = computed(() => {
  const days = Number(waveContent.value.window_days) || 30
  const previous = typeBadges.find((item) => item.code === waveContent.value.previous_type_code)
  const lead = previous
    ? `与 ${days} 天内的前一次观察结果（${previous.name}）存在差异。`
    : `与 ${days} 天内的前一次观察结果存在差异。`
  return `${lead}本次结果仅反映近期行为倾向，单次结果不代表长期特质。`
})
const nonFatalismTitle = computed(() => titleOf('non_fatalism', '关于气质'))
const nonFatalismText = computed(() => String(contentOf('non_fatalism')?.text || defaultNonFatalism))
const readonlyMark = computed(() => (historyMode.value && payload.value?.readonly ? readonlyCopy : ''))
const reportObjectId = computed(() => String(payload.value?.report_uid || uid.value))
const metaLine = computed(() => {
  const nickname = String(reportHeader.value.child_nickname || '—')
  const stamp = reportHeader.value.completed_at || payload.value?.created_at
  return `${childLabel} ${nickname} · ${timeLabel} ${formatTime(stamp)}`
})
const shareTitle = computed(() => `Babe宝伴 · ${typeName.value}阶段观察报告`)

function formatTime(value: unknown) {
  if (!value) return '--'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return '--'
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function dimensionTitle(key: unknown) {
  return dimensionNames[String(key || '')] || dimensionFallback
}

function bandIndex(item: any) {
  const raw = String(item?.band || '').toLowerCase()
  if (raw === 'low') return 0
  if (raw === 'middle' || raw === 'mid' || raw === 'moderate') return 1
  if (raw === 'high') return 2
  return -1
}

function bandText(item: any) {
  const index = bandIndex(item)
  if (item?.partial || index === -1) return partialCopy
  return bandTexts[index]
}

function segFilled(item: any, seg: number) {
  return bandIndex(item) >= seg - 1
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    if (!uid.value) {
      errorMessage.value = missingCopy
      return
    }
    payload.value = historyMode.value ? await api.historyReport(uid.value) : await api.assessmentReport(uid.value)
  } catch (error: any) {
    errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
  } finally {
    loading.value = false
  }
}

function goRecords() {
  uni.redirectTo({ url: '/pages/records/index', fail: () => uni.reLaunch({ url: '/pages/records/index' }) })
}

function goMember() {
  uni.navigateTo({ url: '/pages/member/index', fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
}

function restartAssessment() {
  uni.navigateTo({ url: '/pages/assessment-intro/index', fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
}

function buildReportDoc(): LongImageDoc {
  const sections: Array<{ heading: string; body: string }> = []
  if (typeDesc.value) sections.push({ heading: conclusionTitle.value, body: typeDesc.value })
  if (adviceItems.value.length) {
    sections.push({ heading: adviceTitle.value, body: adviceItems.value.map((item) => `· ${item}`).join('\n') })
  }
  if (waveTriggered.value) sections.push({ heading: waveTitle.value, body: waveCopy.value })
  sections.push({ heading: nonFatalismTitle.value, body: nonFatalismText.value })
  return {
    brand: 'Babe宝伴',
    title: `${typeName.value} · 成长气质观察`,
    meta: metaLine.value,
    dimensions: bands.value.map((item) => ({ label: dimensionTitle(item.dimension), band: bandText(item) })),
    sections,
    disclaimers: [disclaimerLine],
    badge: '内容由 AI 生成'
  }
}

// 长图的取画布、导出与落盘已抽至 platform/long-image（小程序存相册 / H5 触发下载），
// 本页只保留文档构建与交互编排。

async function promptAlbumSetting() {
  const result = await openDialog({
    title: '需要相册权限',
    message: '请在设置中允许保存图片到相册，然后重试。',
    confirmText: '去设置'
  })
  if (result.confirm) uni.openSetting({})
}

function saveLongImage() {
  if (savingImage.value) return
  savingImage.value = true
  uni.showLoading({ title: '正在生成图片…', mask: true })
  void (async () => {
    try {
      const doc = buildReportDoc()
      const outcome = await renderAndSaveLongImage({
        doc,
        selector: '#report-export-canvas',
        instance
      })
      uni.hideLoading()
      if (outcome === 'saved') uni.showToast({ title: savedCopy, icon: 'none' })
      else promptAlbumSetting()
    } catch (error: any) {
      uni.hideLoading()
      uni.showToast({ title: userFacingMessage(error, imageFallback), icon: 'none' })
    } finally {
      savingImage.value = false
      uni.hideLoading()
    }
  })()
}

onShareAppMessage(() => ({
  title: shareTitle.value,
  path: historyMode.value
    ? `/pages/report/index?uid=${uid.value}&history=1`
    : `/pages/report/index?uid=${uid.value}`
}))

onLoad((query) => {
  uid.value = String(query?.uid || '')
  historyMode.value = String(query?.history || '') === '1'
  void load()
})
</script>

<style scoped>
.report-page { min-height: 100vh; padding-bottom: calc(48rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.report-body { padding: 0 32rpx; }
.meta-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16rpx; padding: 24rpx 0 4rpx; }
.meta-copy { flex: 1; color: var(--ink-2); font-size: 26rpx; line-height: 1.6; }
.readonly-pill { flex: none; padding: 6rpx 18rpx; color: var(--ink-3); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-control); font-size: 22rpx; line-height: 1.5; }

.type-hero { position: relative; min-height: 260rpx; margin-top: 20rpx; padding: 36rpx 32rpx 32rpx; background-color: var(--primary-soft); border-radius: var(--r-card); overflow: hidden; box-sizing: border-box; }
.hero-illustration { position: absolute; top: 30rpx; right: 34rpx; width: 132rpx; height: 116rpx; }
.hero-moon { position: relative; width: 58rpx; height: 58rpx; margin-left: 66rpx; background: #F0D9B8; border-radius: 50%; }
.moon-cut { position: absolute; top: -6rpx; left: -10rpx; width: 50rpx; height: 50rpx; background: var(--primary-soft); border-radius: 50%; }
.hero-sprout { position: absolute; bottom: 0; left: 0; width: 84rpx; height: 76rpx; }
.sprout-stem { position: absolute; bottom: 0; left: 40rpx; width: 3rpx; height: 40rpx; background: var(--primary); border-radius: 2rpx; }
.sprout-leaf { position: absolute; width: 34rpx; height: 22rpx; background: var(--surface); border: 1px solid var(--line-warm); border-radius: 0 20rpx 0 20rpx; }
.sprout-left { bottom: 28rpx; left: 6rpx; transform: rotate(-16deg); }
.sprout-right { bottom: 44rpx; left: 44rpx; transform: scaleX(-1) rotate(-16deg); background: var(--primary-soft); }
.hero-label { display: block; padding-right: 150rpx; color: var(--ink-2); font-size: 24rpx; }
.hero-type { display: block; margin-top: 8rpx; padding-right: 150rpx; color: var(--ink-1); font-size: 52rpx; font-weight: 700; line-height: 1.3; }
.type-badges { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 24rpx; }
.type-badge { padding: 8rpx 24rpx; color: var(--ink-3); background: rgba(255, 255, 255, .62); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 24rpx; line-height: 1.5; }
.type-badge.active { color: var(--on-primary); background: var(--primary); border-color: var(--primary); font-weight: 650; }

.report-card { margin-top: 24rpx; padding: 28rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.card-title-row { display: flex; align-items: center; gap: 12rpx; margin-bottom: 16rpx; }
.card-dash { width: 28rpx; height: 4rpx; flex: none; border-radius: 2rpx; background: var(--primary); }
.card-title { color: var(--ink-1); font-size: 32rpx; font-weight: 700; }
.paragraph { display: block; color: var(--ink-2); font-size: 30rpx; line-height: 1.75; white-space: pre-wrap; }
.card-note { display: block; margin-top: 16rpx; color: var(--ink-3); font-size: 24rpx; line-height: 1.6; }

.dimension-row { margin-top: 20rpx; }
.dimension-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.dimension-name { color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.dimension-band { color: var(--primary); font-size: 26rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.dimension-band.partial { color: var(--ink-3); font-weight: 400; }
.dimension-track { display: flex; gap: 8rpx; height: 16rpx; margin-top: 12rpx; }
.dimension-seg { flex: 1; background: var(--line); border-radius: 8rpx; }
.dimension-seg.filled { background: var(--primary); }

.advice-row { display: flex; align-items: flex-start; gap: 14rpx; margin-top: 14rpx; }
.advice-dot { width: 12rpx; height: 12rpx; flex: none; margin-top: 16rpx; border-radius: 50%; background: var(--primary); }
.advice-copy { flex: 1; color: var(--ink-2); font-size: 30rpx; line-height: 1.7; }

.gated-block { margin-top: 8rpx; padding: 24rpx; background: #EDECE8; border-radius: var(--r-inner); }
.gated-title { display: block; color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.gated-summary { display: block; margin-top: 8rpx; color: var(--ink-3); font-size: 26rpx; line-height: 1.6; }
.gated-action { display: inline-flex; align-items: center; justify-content: center; min-height: 72rpx; margin: 18rpx 0 0; padding: 0 36rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 26rpx; }
.member-row { margin-top: 16rpx; }
.member-title { display: block; margin-bottom: 6rpx; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }

.wave-notice { margin-top: 24rpx; padding: 24rpx 28rpx; background: var(--surface); border: 1px solid var(--line-warm); border-left: 6rpx solid var(--warn); border-radius: var(--r-inner); }
.fatalism-notice { margin-top: 24rpx; padding: 24rpx 28rpx; background: var(--warn-soft); border-radius: var(--r-card); }
.notice-head { display: flex; align-items: center; gap: 12rpx; }
.notice-mark { width: 14rpx; height: 14rpx; border-radius: 50%; background: var(--warn); }
.notice-title { display: block; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.notice-copy { display: block; margin-top: 10rpx; color: var(--ink-2); font-size: 26rpx; line-height: 1.7; }

.privacy-line { margin-top: 28rpx; }
.privacy-copy { color: var(--ink-3); font-size: 24rpx; line-height: 1.6; }
.ops-grid { display: flex; flex-wrap: wrap; gap: 16rpx; margin-top: 18rpx; }
.op-item { flex: 1 1 calc(50% - 8rpx); display: flex; align-items: center; justify-content: center; min-height: 88rpx; margin: 0; padding: 0 24rpx; color: var(--ink-1); background: var(--surface); border: var(--border-warm); border-radius: var(--r-control); font-size: 28rpx; line-height: 1.4; }
.primary-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 92rpx; margin-top: 20rpx; padding: 0 32rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }
.plain-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 88rpx; margin-top: 16rpx; color: var(--ink-2); background: transparent; border: var(--border-warm); border-radius: var(--r-control); font-size: 28rpx; }
.pressed { opacity: .82; }

.error-panel { padding: 48rpx 0 24rpx; }
.error-title { display: block; color: var(--ink-1); font-size: 34rpx; font-weight: 700; }
.error-copy { display: block; margin-top: 12rpx; color: var(--ink-2); font-size: 28rpx; line-height: 1.7; }

.export-canvas { position: fixed; left: -2000rpx; top: 0; width: 375px; height: 1px; }
</style>

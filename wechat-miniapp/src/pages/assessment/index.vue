<template>
  <view class="assessment-page tex">
    <MiniPageHeader title="阶段测评" />
    <view class="assessment-body">
      <StateSkeleton v-if="loading" mode="skeleton" />

      <view v-else-if="emptyQuestions" class="empty-panel">
        <text class="empty-title">{{ emptyTitle }}</text>
        <text class="body-copy">{{ emptyCopy }}</text>
        <button class="primary-button" hover-class="pressed" @tap="goHome">返回</button>
      </view>

      <view v-else-if="errorMessage" class="error-panel">
        <text class="error-title">{{ errorTitle }}</text>
        <text class="body-copy">{{ errorMessage }}</text>
        <button class="primary-button" hover-class="pressed" @tap="load">重新加载</button>
      </view>

      <view v-else-if="questionItem" class="question-wrap">
        <view class="progress-head">
          <text class="progress-copy">{{ progressIndexLabel }}</text>
          <text class="progress-copy progress-percent">{{ progressPercentLabel }}</text>
        </view>
        <view class="progress-track">
          <view class="progress-fill" :style="{ width: progressWidth }" />
        </view>
        <text class="progress-hint">{{ exitHint }}</text>

        <view class="question-card">
          <view class="question-head">
            <text class="question-tag">{{ questionLabel }}</text>
            <text class="question-kind">{{ singleChoiceLabel }}</text>
          </view>
          <text class="question-title">{{ questionItem.stem }}</text>
          <text class="body-copy">{{ answerHint }}</text>
          <view class="options-list">
            <button
              v-for="option in questionItem.options"
              :key="option.score"
              class="option-row"
              :class="{ selected: selectedScore === option.score, disabled: saving }"
              :disabled="saving"
              hover-class="pressed"
              @tap="choose(option.score)"
            >
              <view class="option-notch" />
              <text class="option-text">{{ option.label }}</text>
              <text v-if="selectedScore === option.score" class="option-state">{{ recordedCopy }}</text>
            </button>
          </view>
        </view>

        <view v-if="breakpointSaved" class="save-banner">
          <text class="save-copy">{{ savedBreakpointCopy }}</text>
          <text class="save-time">{{ justNowCopy }}</text>
        </view>

        <view class="nav-row">
          <button
            class="secondary-button"
            :class="{ disabled: currentIndex === 0 }"
            :disabled="currentIndex === 0"
            hover-class="pressed"
            @tap="prev"
          >
            {{ prevCopy }}
          </button>
          <button
            class="primary-button"
            :class="{ disabled: !currentAnswered || saving }"
            :disabled="!currentAnswered || saving"
            hover-class="pressed"
            @tap="next"
          >
            {{ nextLabel }}
          </button>
        </view>

        <view v-if="submitting" class="scoring-panel">
          <view class="scoring-spinner" />
          <text class="scoring-copy">{{ scoringCopy }}</text>
        </view>

        <text class="footnote">{{ footnoteCopy }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { createAssessmentProgressStore } from '../../services/assessment-progress'
import { hasAssessmentAnswer } from '../../services/assessment-answer'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const emptyTitle = '暂无可作答题目'
const emptyCopy = '题目暂时无法获取，请稍后再来。'
const errorTitle = '暂时无法开始'
const exitHint = '退出即自动保存断点，可随时回来继续'
const singleChoiceLabel = '单选'
const answerHint = '没有对错，选最接近平时表现的一项即可'
const recordedCopy = '已记录'
const savedBreakpointCopy = '已保存断点'
const justNowCopy = '刚刚'
const prevCopy = '上一题'
const nextCopy = '下一题'
const submitCopy = '提交并计分'
const scoringCopy = '正在生成报告…'
const footnoteCopy = '这是一次阶段观察，不用于给孩子贴上固定标签。'
const saveFallback = '答案暂未保存，请稍后重试。'
const submitFallback = '报告生成失败，请稍后重试。'

const progressStore = createAssessmentProgressStore({
  storage: {
    getStorageSync: (key: string) => uni.getStorageSync(key),
    setStorageSync: (key: string, value: unknown) => uni.setStorageSync(key, value)
  }
})

const loading = ref(true)
const saving = ref(false)
const submitting = ref(false)
const emptyQuestions = ref(false)
const breakpointSaved = ref(false)
const errorMessage = ref('')
const assessmentUid = ref('')
const userUid = ref('')
const questions = ref<any[]>([])
const currentIndex = ref(0)
const answers = reactive<Record<number, number>>({})
let saveHideTimer: ReturnType<typeof setTimeout> | null = null
let submitRequestId = ''

const questionItem = computed(() => questions.value[currentIndex.value])
const selectedScore = computed(() => (questionItem.value ? answers[questionItem.value.q_no] : undefined))
const currentAnswered = computed(() => !!questionItem.value && hasAssessmentAnswer(answers, questionItem.value.q_no))
const answeredCount = computed(() => questions.value.filter((item: any) => hasAssessmentAnswer(answers, item.q_no)).length)
const questionLabel = computed(() => `第 ${currentIndex.value + 1} 题`)
const progressIndexLabel = computed(() => `第 ${currentIndex.value + 1} / ${questions.value.length} 题`)
const progressPercent = computed(() => {
  if (!questions.value.length) return 0
  return Math.round((answeredCount.value / questions.value.length) * 100)
})
const progressPercentLabel = computed(() => `进度 ${progressPercent.value}%`)
const progressWidth = computed(() => `${progressPercent.value}%`)
const nextLabel = computed(() => {
  if (submitting.value) return scoringCopy
  if (!questions.value.length) return nextCopy
  return currentIndex.value === questions.value.length - 1 ? submitCopy : nextCopy
})

async function resolveAgeBand() {
  try {
    const view = await api.children()
    const children = Array.isArray(view?.children) ? view.children : []
    const active = children.find((item: any) => item?.status === 'active')
    return active?.age_band || '1-3y'
  } catch {
    return '1-3y'
  }
}

function persistProgress() {
  if (!userUid.value || !assessmentUid.value || !questions.value.length) return
  progressStore.write(userUid.value, {
    assessment_uid: assessmentUid.value,
    answered: answeredCount.value,
    total: questions.value.length,
    updated_at: Date.now()
  })
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  emptyQuestions.value = false
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const ageBand = await resolveAgeBand()
    const [questionData, assessment, meView] = await Promise.all([
      api.assessmentQuestions(ageBand),
      api.startAssessment(),
      api.me().catch(() => null)
    ])
    questions.value = questionData.questions || []
    assessmentUid.value = assessment.assessment_uid || ''
    userUid.value = meView?.user_uid || ''
    for (const key of Object.keys(answers)) delete answers[Number(key)]
    for (const answer of assessment.answers || []) {
      if (answer?.raw_score != null) answers[Number(answer.q_no)] = Number(answer.raw_score)
    }
    if (!questions.value.length) {
      emptyQuestions.value = true
      return
    }
    currentIndex.value = firstUnansweredIndex()
    persistProgress()
  } catch (error: any) {
    errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
  } finally {
    loading.value = false
  }
}

function firstUnansweredIndex() {
  const index = questions.value.findIndex((item: any) => !hasAssessmentAnswer(answers, item.q_no))
  return index === -1 ? questions.value.length - 1 : index
}

function showSavedHint() {
  breakpointSaved.value = true
  if (saveHideTimer) clearTimeout(saveHideTimer)
  saveHideTimer = setTimeout(() => { breakpointSaved.value = false }, 2000)
}

async function choose(score: number) {
  if (saving.value || !questionItem.value) return
  const questionNo = questionItem.value.q_no
  saving.value = true
  try {
    await api.putAnswer(assessmentUid.value, questionNo, score)
    answers[questionNo] = score
    showSavedHint()
    persistProgress()
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, saveFallback), icon: 'none' })
  } finally {
    saving.value = false
  }
}

function prev() {
  if (saving.value || currentIndex.value === 0) return
  currentIndex.value -= 1
}

function submitId() {
  if (!submitRequestId) submitRequestId = `mp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  return submitRequestId
}

async function next() {
  if (!questionItem.value || !currentAnswered.value || saving.value) return
  if (currentIndex.value < questions.value.length - 1) {
    currentIndex.value += 1
    return
  }
  saving.value = true
  submitting.value = true
  try {
    await api.submitAssessment(assessmentUid.value, submitId())
    if (userUid.value) progressStore.clear(userUid.value)
    uni.redirectTo({ url: `/pages/report/index?uid=${encodeURIComponent(assessmentUid.value)}` })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, submitFallback), icon: 'none' })
  } finally {
    saving.value = false
    submitting.value = false
  }
}

function goHome() {
  uni.reLaunch({ url: '/pages/index/index' })
}

onLoad(() => { void load() })
</script>

<style scoped>
.assessment-page { min-height: 100vh; padding-bottom: calc(48rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.assessment-body { padding: 24rpx 32rpx 0; }

.progress-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.progress-copy { color: var(--ink-1); font-size: 27rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.progress-percent { color: var(--ink-3); font-weight: 400; }
.progress-track { height: 14rpx; margin-top: 14rpx; background: var(--line); border-radius: 7rpx; overflow: hidden; }
.progress-fill { height: 100%; background: var(--primary); border-radius: 7rpx; transition: width .24s ease; }
.progress-hint { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 23rpx; line-height: 1.5; }

.question-card { margin-top: 24rpx; padding: 30rpx 28rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.question-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.question-tag { color: var(--primary); font-size: 26rpx; font-weight: 700; font-variant-numeric: tabular-nums; }
.question-kind { padding: 4rpx 16rpx; color: var(--ink-3); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-control); font-size: 22rpx; }
.question-title { display: block; margin-top: 16rpx; color: var(--ink-1); font-size: 36rpx; font-weight: 650; line-height: 1.55; }
.body-copy { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 25rpx; line-height: 1.6; }

.options-list { margin-top: 24rpx; border-top: 1px solid var(--line); }
.option-row { display: flex; align-items: center; width: 100%; min-height: 104rpx; margin: 0; padding: 0 8rpx; color: var(--ink-2); background: transparent; border: 0; border-bottom: 1px solid var(--line); text-align: left; font-size: 30rpx; line-height: 1.5; }
.option-notch { width: 30rpx; height: 30rpx; flex: none; margin-right: 20rpx; border: 2rpx solid var(--line-warm); border-radius: 50%; box-sizing: border-box; }
.option-row.selected { color: var(--ink-1); font-weight: 600; }
.option-row.selected .option-notch { border: 9rpx solid var(--primary); background: var(--surface); }
.option-text { flex: 1; }
.option-state { flex: none; margin-left: 16rpx; color: var(--primary); font-size: 23rpx; }
.option-row.disabled { opacity: .7; }

.save-banner { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; margin-top: 24rpx; padding: 18rpx 26rpx; background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-card); }
.save-copy { color: var(--ink-2); font-size: 25rpx; }
.save-time { color: var(--ink-3); font-size: 23rpx; }

.nav-row { display: flex; gap: 18rpx; margin-top: 30rpx; }
.primary-button, .secondary-button { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 92rpx; margin: 0; padding: 0 24rpx; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }
.primary-button { color: var(--on-primary); background: var(--primary); border: 0; }
.secondary-button { color: var(--ink-1); background: var(--surface); border: var(--border-warm); }
.primary-button.disabled, .secondary-button.disabled { opacity: .5; }

.scoring-panel { display: flex; align-items: center; justify-content: center; gap: 18rpx; margin-top: 26rpx; padding: 26rpx; background: var(--info-soft); border-radius: var(--r-card); }
.scoring-spinner { width: 34rpx; height: 34rpx; border: 4rpx solid rgba(143, 166, 188, .35); border-top-color: var(--info); border-radius: 50%; animation: scoring-rotate 1s linear infinite; }
@keyframes scoring-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) {
  .scoring-spinner { animation: none; }
}
.scoring-copy { color: var(--ink-1); font-size: 27rpx; }

.footnote { display: block; margin-top: 30rpx; color: var(--ink-3); font-size: 23rpx; line-height: 1.6; }
.pressed { opacity: .82; }

.empty-panel, .error-panel { padding: 48rpx 0 24rpx; }
.empty-title, .error-title { display: block; color: var(--ink-1); font-size: 34rpx; font-weight: 700; }
.error-panel .primary-button, .empty-panel .primary-button { width: 100%; margin-top: 28rpx; }
</style>

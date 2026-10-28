<template>
  <view class="intro-page tex">
    <MiniPageHeader title="阶段测评" />
    <view class="intro-body">
      <StateSkeleton v-if="phase === 'loading'" mode="skeleton" />

      <template v-else>
        <view class="boundary-card">
          <view class="boundary-head">
            <view class="boundary-badge" aria-hidden="true">
              <view class="badge-stem" />
              <view class="badge-leaf badge-leaf-left" />
              <view class="badge-leaf badge-leaf-right" />
            </view>
            <text class="boundary-title">{{ titleCopy }}</text>
          </view>
          <view class="boundary-group">
            <text class="group-label group-ok">{{ okLabel }}</text>
            <text class="group-copy">{{ okCopy }}</text>
          </view>
          <view class="boundary-group">
            <text class="group-label group-no">{{ noLabel }}</text>
            <text class="group-copy">{{ noCopy }}</text>
          </view>
        </view>

        <view class="fact-card">
          <text class="fact-line">{{ factLine }}</text>
          <text class="fact-line">{{ formatLine }}</text>
        </view>

        <view v-if="resumeVisible" class="resume-card">
          <view class="resume-head">
            <text class="resume-title">{{ resumeTitle }}</text>
            <text class="resume-index">{{ resumeIndexCopy }}</text>
          </view>
          <text class="resume-copy">{{ resumeCopy }}</text>
        </view>

        <view v-if="phase === 'closed'" class="state-note">
          <text class="state-copy">{{ closedCopy }}</text>
        </view>
        <view v-else-if="phase === 'error'" class="state-note">
          <text class="state-copy">{{ errorMessage }}</text>
          <button class="retry-button" hover-class="pressed" @tap="load">{{ retryCopy }}</button>
        </view>

        <button
          class="primary-button"
          :class="{ disabled: !canStart }"
          :disabled="!canStart"
          hover-class="pressed"
          @tap="startOrResume"
        >
          {{ startLabel }}
        </button>
        <text v-if="phase === 'ready'" class="start-hint">{{ startHint }}</text>

        <view v-if="!hasChildProfile && phase === 'ready'" class="profile-guide">
          <text class="guide-copy">{{ guideCopy }}</text>
          <button class="guide-action" hover-class="pressed" @tap="goProfiles">{{ guideAction }}</button>
        </view>

        <MiniComplianceBar />
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ApiError } from '../../platform/request'
import { api } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { createAssessmentProgressStore } from '../../services/assessment-progress'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const titleCopy = '开始之前，先了解一下'
const okLabel = '这是什么'
const okCopy = '一份面向 0-6 岁孩子的通俗情境问卷，用来了解孩子近期的行为倾向，帮助你选择更合适的养育方式与亲子沟通方法。'
const noLabel = '这不是什么'
const noCopy = '不是心理测评工具，也不是终身性格判定；不做诊断、治疗与心理评估；不算命，不判定「天生注定」。'
const formatLine = '题型：5 点李克特式情境选择题，按孩子平时表现选择即可'
const resumeTitle = '继续上次填写'
const resumeCopy = '断点已保存，可随时继续；断点保留 90 天。'
const closedCopy = '测评暂未开放，请稍后再来。'
const retryCopy = '重新加载'
const startCopy = '开始测评'
const resumeStartCopy = '继续填写'
const startHint = '开始前建议先选好孩子档案'
const guideCopy = '还没有孩子档案？可以先按通用月龄区间答题，稍后补充档案即可。'
const guideAction = '先去建档'
const fallbackQuestions = 16
const fallbackDimensions = 4
const estimateMinutes = 3
// 未完成首启同意时进入测评：明确提示并回到首页同意门禁（N1 不可绕过）
const consentRequiredCopy = '请先同意用户协议与免责声明'

const progressStore = createAssessmentProgressStore({
  storage: {
    getStorageSync: (key: string) => uni.getStorageSync(key),
    setStorageSync: (key: string, value: unknown) => uni.setStorageSync(key, value)
  }
})

const phase = ref<'loading' | 'ready' | 'closed' | 'error'>('loading')
const errorMessage = ref('')
const questions = ref<any[]>([])
const assessmentUid = ref('')
const userUid = ref('')
const resumed = ref(false)
const answeredCount = ref(0)
const nextNo = ref(1)
const hasChildProfile = ref(true)

const questionCount = computed(() => questions.value.length || fallbackQuestions)
const dimensionCount = computed(() => {
  const set = new Set(questions.value.map((item: any) => item?.dimension).filter(Boolean))
  return set.size || fallbackDimensions
})
const factLine = computed(() => `预计 ${estimateMinutes} 分钟 · ${questionCount.value} 题 · ${dimensionCount.value} 个维度`)
const resumeVisible = computed(() => phase.value === 'ready' && resumed.value && answeredCount.value > 0)
const resumeIndexCopy = computed(() => `第 ${nextNo.value} / ${questionCount.value} 题`)
const canStart = computed(() => phase.value === 'ready' && !!assessmentUid.value)
const startLabel = computed(() => (resumed.value ? resumeStartCopy : startCopy))

async function resolveAgeBand() {
  try {
    const view = await api.children()
    const children = Array.isArray(view?.children) ? view.children : []
    const active = children.find((item: any) => item?.status === 'active')
    hasChildProfile.value = !!active
    return active?.age_band || '1-3y'
  } catch {
    hasChildProfile.value = true
    return '1-3y'
  }
}

function computeNextNo(answerList: any[]) {
  const done = new Set(
    answerList
      .filter((item: any) => item?.raw_score != null)
      .map((item: any) => Number(item?.q_no))
  )
  const index = questions.value.findIndex((item: any) => !done.has(Number(item?.q_no)))
  if (!questions.value.length) return 1
  return index === -1 ? questions.value.length : index + 1
}

function syncMirror() {
  if (!userUid.value || !assessmentUid.value) return
  if (!questions.value.length || !resumed.value || !answeredCount.value) {
    progressStore.clear(userUid.value)
    return
  }
  progressStore.write(userUid.value, {
    assessment_uid: assessmentUid.value,
    answered: answeredCount.value,
    total: questions.value.length,
    updated_at: Date.now()
  })
}

async function load() {
  phase.value = 'loading'
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      // 缺陷 D4：原先直接 reLaunch 回首页且无任何提示，用户看到的是
      // 「点了没反应」。改为先提示原因，再回到首页的同意门禁页。
      uni.showToast({ title: consentRequiredCopy, icon: 'none' })
      setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 600)
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
    resumed.value = assessment.resumed === true
    const answerList = Array.isArray(assessment.answers) ? assessment.answers : []
    answeredCount.value = answerList.filter((item: any) => item?.raw_score != null).length
    nextNo.value = computeNextNo(answerList)
    syncMirror()
    phase.value = 'ready'
  } catch (error: any) {
    if (error instanceof ApiError && (error.code === 1406 || error.code === 1002)) {
      phase.value = 'closed'
      return
    }
    errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
    phase.value = 'error'
  }
}

function startOrResume() {
  if (!canStart.value) return
  uni.navigateTo({
    url: `/pages/assessment/index?uid=${encodeURIComponent(assessmentUid.value)}`,
    fail: () => uni.reLaunch({ url: '/pages/index/index' })
  })
}

function goProfiles() {
  uni.redirectTo({ url: '/pages/profiles/index', fail: () => uni.reLaunch({ url: '/pages/profiles/index' }) })
}

onLoad(() => { void load() })
</script>

<style scoped>
.intro-page { min-height: 100vh; padding-bottom: calc(48rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.intro-body { padding: 24rpx 32rpx 0; }

.boundary-card { padding: 32rpx 28rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.boundary-head { display: flex; align-items: center; gap: 18rpx; }
.boundary-badge { position: relative; width: 72rpx; height: 72rpx; flex: none; background: var(--primary-soft); border: 1px solid var(--line-warm); border-radius: 50%; }
.badge-stem { position: absolute; bottom: 12rpx; left: 34rpx; width: 3rpx; height: 26rpx; background: var(--primary); border-radius: 2rpx; }
.badge-leaf { position: absolute; width: 20rpx; height: 13rpx; background: var(--primary); border-radius: 0 12rpx 0 12rpx; }
.badge-leaf-left { top: 18rpx; left: 18rpx; transform: rotate(-14deg); }
.badge-leaf-right { top: 25rpx; left: 38rpx; transform: scaleX(-1) rotate(-14deg); background: #9DB0A2; }
.boundary-title { color: var(--ink-1); font-size: 34rpx; font-weight: 700; }
.boundary-group { margin-top: 26rpx; }
.group-label { display: inline-block; padding: 4rpx 18rpx; border-radius: var(--r-control); font-size: 24rpx; font-weight: 650; }
.group-ok { color: var(--primary); background: var(--primary-soft); }
.group-no { color: var(--warn); background: var(--warn-soft); }
.group-copy { display: block; margin-top: 12rpx; color: var(--ink-2); font-size: 28rpx; line-height: 1.75; }

.fact-card { margin-top: 24rpx; padding: 24rpx 28rpx; background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-card); }
.fact-line { display: block; color: var(--ink-2); font-size: 27rpx; line-height: 1.8; }
.fact-line:first-child { color: var(--ink-1); font-weight: 650; font-variant-numeric: tabular-nums; }

.resume-card { margin-top: 24rpx; padding: 24rpx 28rpx; background: var(--info-soft); border-radius: var(--r-card); }
.resume-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.resume-title { color: var(--ink-1); font-size: 30rpx; font-weight: 700; }
.resume-index { color: var(--info); font-size: 26rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.resume-copy { display: block; margin-top: 10rpx; color: var(--ink-2); font-size: 25rpx; line-height: 1.6; }

.state-note { margin-top: 24rpx; padding: 24rpx 28rpx; background: var(--warn-soft); border-radius: var(--r-card); }
.state-copy { display: block; color: var(--ink-1); font-size: 27rpx; line-height: 1.7; }
.retry-button { display: inline-flex; align-items: center; justify-content: center; min-height: 72rpx; margin: 18rpx 0 0; padding: 0 36rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 26rpx; }

.primary-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 96rpx; margin: 32rpx 0 0; padding: 0 32rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 32rpx; font-weight: 650; }
.primary-button.disabled { opacity: .5; }
.start-hint { display: block; margin-top: 14rpx; color: var(--ink-3); font-size: 24rpx; text-align: center; }

.profile-guide { display: flex; align-items: center; gap: 20rpx; margin-top: 28rpx; padding: 22rpx 26rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); }
.guide-copy { flex: 1; color: var(--ink-2); font-size: 25rpx; line-height: 1.6; }
.guide-action { flex: none; margin: 0; padding: 10rpx 26rpx; color: var(--primary); background: var(--primary-soft); border: 0; border-radius: var(--r-control); font-size: 25rpx; }

.pressed { opacity: .82; }
</style>

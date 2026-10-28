<template>
  <view class="page-shell tex">
    <MiniPageHeader home :subtitle="brandSubtitle" />

    <view class="page-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />
      <view v-else-if="state === 'error'" class="error-wrap">
        <StateSkeleton
          mode="empty"
          :title="errorTitle"
          :copy="errorMessage"
          :action-text="retryCopy"
          @action="retry"
        />
        <view v-if="debugEntry" class="debug-entry" hover-class="link-pressed" @tap="openDebugDialog">
          <text class="debug-entry-copy">{{ debugEntry.linkCopy }}</text>
        </view>
      </view>

      <view v-else-if="state === 'consent'" class="consent-wrap">
        <view class="consent-medallion tex" aria-hidden="true">
          <view class="medallion-stem" />
          <view class="medallion-leaf medallion-leaf-left" />
          <view class="medallion-leaf medallion-leaf-right" />
        </view>
        <view class="consent-panel">
          <view class="consent-tag"><text>{{ consentEyebrow }}</text></view>
          <text class="consent-title">{{ consentTitle }}</text>
          <text class="consent-copy">{{ consentCopy }}</text>
          <view class="consent-links">
            <view class="consent-link" hover-class="link-pressed" @tap="showPolicy(agreementLabel)"><text>《{{ agreementLabel }}》</text></view>
            <view class="consent-link" hover-class="link-pressed" @tap="showPolicy(policyLabel)"><text>《{{ policyLabel }}》</text></view>
          </view>
          <view class="agree-row" @tap="consented = !consented">
            <view class="check-mark" :class="{ checked: consented }"><view v-if="consented" class="check-tick" /></view>
            <text class="agree-copy">{{ consentAgree }}</text>
          </view>
          <button class="primary-button" :class="{ disabled: !consented || busy }" :disabled="!consented || busy" hover-class="primary-pressed" @tap="acceptConsent">
            {{ busy ? consentBusy : consentAction }}
          </button>
        </view>
      </view>

      <view v-else-if="state === 'login'" class="consent-wrap">
        <view class="consent-medallion tex" aria-hidden="true">
          <view class="medallion-stem" />
          <view class="medallion-leaf medallion-leaf-left" />
          <view class="medallion-leaf medallion-leaf-right" />
        </view>
        <view class="consent-panel">
          <view class="consent-tag"><text>{{ loginEyebrow }}</text></view>
          <text class="consent-title">{{ loginTitle }}</text>
          <text class="consent-copy">{{ loginCopy }}</text>
          <text v-if="loginError" class="login-error">{{ loginError }}</text>
          <button class="primary-button" :class="{ disabled: busy }" :disabled="busy" hover-class="primary-pressed" @tap="doLogin">
            {{ busy ? loginBusy : loginAction }}
          </button>
          <text class="login-note">{{ loginNote }}</text>
        </view>
      </view>

      <template v-else>
        <view v-if="dailyTipVisible" class="daily-tip" hover-class="card-pressed" @tap="dismissDailyTip">
          <view class="tip-dot" />
          <text class="tip-copy">{{ dailyTipCopy }}</text>
          <text class="tip-action">{{ dailyTipAction }}</text>
        </view>

        <view v-if="!isMember" class="quota-card tex" :class="{ exhausted: quotaExhausted }" aria-label="今日提问额度" hover-class="card-pressed" @tap="openMember">
          <view class="quota-head">
            <view class="quota-badge"><view class="quota-badge-dot" /><text>{{ quotaBadge }}</text></view>
            <text class="quota-readout">{{ quotaReadout }}</text>
          </view>
          <view v-if="quotaLimit !== null" class="quota-track"><view class="quota-fill" :style="{ width: quotaPercentValue }" /></view>
          <text class="quota-note">{{ quotaNote }}</text>
        </view>

        <!-- 轻工具次级文字入口（RQ-12 AC-RQ12-5：四入口布局与顺序不变，轻工具收纳于此） -->
        <view class="tools-entry" hover-class="link-pressed" @tap="openTools">
          <text class="tools-entry-copy">{{ toolsEntryCopy }}</text>
          <text class="tools-entry-arrow">→</text>
        </view>

        <view class="knowledge-card tex" aria-label="每日一则小知识" hover-class="card-pressed" @tap="openKnowledgeBook">
          <view class="knowledge-copy">
            <view class="knowledge-eyebrow">
              <text class="knowledge-label">{{ knowledgeLabel }}</text>
              <text class="knowledge-date">{{ dailyKnowledgeDate }}</text>
            </view>
            <text class="knowledge-title">{{ dailyKnowledge.title }}</text>
            <text class="knowledge-summary">{{ dailyKnowledge.summary }}</text>
          </view>
          <view class="knowledge-illustration" aria-hidden="true">
            <view class="knowledge-ring" />
            <view class="knowledge-ground" />
            <view class="knowledge-stem" />
            <view class="knowledge-leaf leaf-up" />
            <view class="knowledge-leaf leaf-down" />
          </view>
          <view class="knowledge-foot">
            <view class="knowledge-tags">
              <template v-if="dailyKnowledgeSource !== 'loading'">
                <view class="knowledge-tag"><text>{{ dailyKnowledge.category_label }}</text></view>
                <view v-if="dailyKnowledge.stage_label" class="knowledge-tag ghost"><text>{{ dailyKnowledge.stage_label }}</text></view>
                <view v-if="dailyKnowledgeSource === 'fallback'" class="knowledge-tag note"><text>{{ fallbackTag }}</text></view>
              </template>
            </view>
            <view class="knowledge-action"><text>{{ knowledgeAction }}</text><text class="knowledge-arrow">→</text></view>
          </view>
        </view>

        <view class="entry-card">
          <view
            v-for="row in entryRows"
            :key="row.entry"
            class="entry-row"
            :aria-label="row.title"
            hover-class="row-pressed"
            @tap="openEntry(row.entry)"
          >
            <view class="entry-icon" :class="'icon-' + row.tone">
              <view class="glyph" :class="'glyph-' + row.entry" />
            </view>
            <view class="entry-main">
              <text class="entry-title">{{ row.title }}</text>
              <text class="entry-sub">{{ row.sub }}</text>
            </view>
            <text class="entry-arrow">→</text>
          </view>
        </view>

        <view class="member-card" aria-label="会员权益入口" hover-class="card-pressed" @tap="openMember">
          <view class="member-main">
            <text class="member-title">{{ memberCardTitle }}</text>
            <text class="member-sub">{{ memberCardSub }}</text>
          </view>
          <view class="member-pill"><text>{{ memberPill }}</text></view>
        </view>

        <text class="footer-note">{{ footerNote }}</text>
      </template>
    </view>

    <template v-if="state === 'ready'">
      <MiniComplianceBar fixed />
      <MiniTabBar active="home" />
    </template>

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
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { api, apiEndpoint, type KnowledgeEntryView, type MeView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniTabBar from '../../components/MiniTabBar.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { ensureBaseConsent, isSignedOut, loginAfterSignOut } from '../../services/session'
import { isMiniProgram } from '../../platform/runtime'
import {
  formatKnowledgeDate,
  localDateStamp,
  pickFallback,
  resolveDailyKnowledge,
  type DailyKnowledgeSource
} from '../../services/daily-knowledge'
import { userFacingMessage } from '../../services/user-message'

type Entry = 'child' | 'pet' | 'family'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
// RQ-02 / MR5：副标题采用「养育科普参考工具」定位，去除拟人化情感表述
const brandSubtitle = 'AI 多智能体，家庭养育科普参考工具'
const errorTitle = '暂时无法连接'
const retryCopy = '重新连接'
const consentEyebrow = '首次使用 · 隐私确认'
const consentTitle = '先了解信息如何被使用'
const consentCopy = 'Babe宝伴会根据你主动提交的问题提供养育与共居建议。内容仅用于生成本次服务，不替代医生、兽医或其他专业人员的诊断。'
const agreementLabel = '服务协议'
const policyLabel = '隐私政策'
const consentAgree = '我已阅读并同意以上协议'
const consentBusy = '正在保存…'
const consentAction = '同意并继续'
const loginEyebrow = '账号登录'
const loginTitle = '登录后继续使用'
const loginCopy = '你已退出登录。登录成功后将加载当前微信或设备对应的账号数据；服务端原有数据不会被清除。'
const loginBusy = '正在登录…'
const loginAction = isMiniProgram && !import.meta.env.DEV ? '微信一键登录' : '使用本机身份登录'
const loginNote = '如需使用其他账号，请先在微信中切换账号（小程序端）后重新登录。'
const quotaBadge = '今日可用'
const quotaNoteOpen = '额度用尽后可次日再来，或开通会员不受额度限制'
const quotaNoteEmpty = '今日额度已用完，可次日再来，或开通会员不受额度限制'
// 每日一则小知识（知识库数据源与轮换规则见 services/daily-knowledge.ts）
const knowledgeLabel = '每日一则小知识'
const knowledgeAction = '查看科普全书'
const fallbackTag = '通用提示'
const knowledgeLoadingCopy = '正在准备今日小知识…'
const knowledgeLoadingSummary = '每天从知识库挑选一条养育科普，按日期稳定轮换。'
const memberFallbackTitle = '会员权益'
const memberFallbackSub = '深度方案 · 月度计划 · 专属档案'
const memberActiveSub = '续费可延长有效期'
const memberPillOpen = '了解会员'
const memberPillActive = '查看会员'
const dailyTipCopy = '回应与报告由人工智能生成，仅供参考，不替代医疗或专业诊断。'
const dailyTipAction = '知道了'
// 轻工具入口（RQ-12）：四入口布局与顺序不变，工具作为次级文字入口
const toolsEntryCopy = '工具 · 自查清单与配料表解析'
const footerNote = '观察帮助理解，不给家庭贴标签。'
const policyModalCopy = 'Babe宝伴仅处理你为使用相关功能主动提交的信息。具体收集范围、使用方式与信息权利，以正式公布的隐私政策为准。'
const navFailedCopy = '页面打开失败，请稍后重试。'
const DAILY_TIP_KEY = 'jiaban_home_daily_tip'
// dev 构建专用：连接诊断入口（生产构建下整块被常量折叠移除）
const debugEntry = import.meta.env.DEV
  ? {
      linkCopy: '调试连接',
      dialogTitle: '调试连接',
      inputPlaceholder: 'http://192.168.x.x:8000/api/v1',
      confirmCopy: '保存并重连',
      emptyNote: '留空保存将清除手动地址。'
    }
  : null

const entryRows: { entry: Entry; title: string; sub: string; tone: 'info' | 'warn' | 'primary' }[] = [
  { entry: 'child', title: '0-6 岁宝宝养育', sub: '喂养 / 睡眠 / 敏感期 / 行为引导', tone: 'info' },
  { entry: 'pet', title: '猫狗宠物饲养', sub: '喂养 / 护理 / 行为解读 / 应激', tone: 'warn' },
  { entry: 'family', title: '家庭综合问答', sub: '孩子 + 宠物同场景，一次答全', tone: 'primary' }
]

const state = ref<'loading' | 'error' | 'consent' | 'login' | 'ready'>('loading')
const errorMessage = ref('连接失败，请检查网络后重试。')
const loginError = ref('')
const consented = ref(false)
const busy = ref(false)
const quotaUsed = ref(0)
const quotaLimit = ref<number | null>(4)
const isMember = ref(false)
const memberExpireText = ref('')
const productPriceText = ref('')
const dailyTipVisible = ref(false)
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

// 首页知识卡片：加载中先用占位文案，取数完成后替换为知识库内容或内置降级提示
const dailyKnowledge = ref<KnowledgeEntryView>({
  kb_id: '',
  title: knowledgeLoadingCopy,
  summary: knowledgeLoadingSummary,
  content: '',
  category: 'infant',
  category_label: '',
  topic: null,
  stage_label: null,
  preconditions: null,
  source_level: null,
  source_name: null
})
const dailyKnowledgeDate = ref(formatKnowledgeDate(localDateStamp()))
const dailyKnowledgeSource = ref<DailyKnowledgeSource | 'loading'>('loading')
let dailyKnowledgeBusy = false

const quotaRemaining = computed(() => (quotaLimit.value === null ? null : Math.max(0, quotaLimit.value - quotaUsed.value)))
const quotaExhausted = computed(() => quotaLimit.value !== null && quotaUsed.value >= quotaLimit.value)
const quotaPercentValue = computed(() => (quotaLimit.value ? `${Math.min(100, Math.round((quotaUsed.value / quotaLimit.value) * 100))}%` : '0%'))
const quotaReadout = computed(() => (quotaLimit.value === null ? '不限次数' : `剩余 ${quotaRemaining.value} / ${quotaLimit.value} 次`))
const quotaNote = computed(() => (quotaExhausted.value ? quotaNoteEmpty : quotaNoteOpen))

const memberCardTitle = computed(() => {
  if (isMember.value) return memberExpireText.value ? `会员有效期至 ${memberExpireText.value}` : '你已是会员'
  return productPriceText.value ? `会员月卡 ${productPriceText.value}` : memberFallbackTitle
})
const memberCardSub = computed(() => (isMember.value ? memberActiveSub : memberFallbackSub))
const memberPill = computed(() => (isMember.value ? memberPillActive : memberPillOpen))

function currentPlatform(): 'android' | 'ios' {
  try {
    return uni.getSystemInfoSync()?.platform === 'ios' ? 'ios' : 'android'
  } catch {
    return 'android'
  }
}

function formatPriceText(product: { price_micro: number; duration_days: number }): string {
  const yuan = Number(product.price_micro) / 1e6
  if (!Number.isFinite(yuan) || yuan <= 0) return ''
  const amount = parseFloat(yuan.toFixed(2)).toString()
  const days = Number(product.duration_days) || 0
  const suffix = days >= 360 ? '元/年' : days >= 28 && days <= 31 ? '元/月' : days > 0 ? `元 / ${days} 天` : '元'
  return `${amount} ${suffix}`
}

function applyMembership(meView: MeView | null) {
  if (!meView) {
    isMember.value = false
    memberExpireText.value = ''
    return
  }
  const expireMs = meView.member_expire_at ? new Date(meView.member_expire_at).getTime() : 0
  const active = meView.member_status === 'member' && (!expireMs || expireMs > Date.now())
  isMember.value = active
  memberExpireText.value = active && meView.member_expire_at ? String(meView.member_expire_at).slice(0, 10) : ''
}

function todayStamp() {
  const now = new Date()
  return `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`
}

function maybeShowDailyTip() {
  let seen = ''
  try {
    seen = String(uni.getStorageSync(DAILY_TIP_KEY) || '')
  } catch {
    seen = ''
  }
  if (seen === todayStamp()) return
  dailyTipVisible.value = true
  try {
    uni.setStorageSync(DAILY_TIP_KEY, todayStamp())
  } catch {
    // 本地记录失败不阻塞展示
  }
}

function dismissDailyTip() {
  dailyTipVisible.value = false
}

async function boot(options: { silent?: boolean } = {}) {
  if (!options.silent) state.value = 'loading'
  try {
    // 主动退出登录后不自动恢复会话，先展示登录入口
    if (isSignedOut()) {
      state.value = 'login'
      return
    }
    if (!(await ensureBaseConsent())) {
      state.value = 'consent'
      return
    }
    const [quotaResult, meResult, productResult] = await Promise.allSettled([
      api.quota(),
      api.me(),
      api.billingProduct(currentPlatform())
    ])
    if (quotaResult.status === 'fulfilled') {
      quotaUsed.value = quotaResult.value.used || 0
      quotaLimit.value = quotaResult.value.limit
    } else {
      quotaUsed.value = 0
      quotaLimit.value = 4
    }
    applyMembership(meResult.status === 'fulfilled' ? meResult.value : null)
    if (productResult.status === 'fulfilled' && productResult.value.purchasable && productResult.value.products?.length) {
      productPriceText.value = formatPriceText(productResult.value.products[0])
    } else {
      productPriceText.value = ''
    }
    maybeShowDailyTip()
    state.value = 'ready'
    // 知识卡片不阻塞首页首屏：先渲染占位，再异步替换为知识库内容或降级提示
    void loadDailyKnowledge()
  } catch (error: any) {
    errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
    state.value = 'error'
  } finally {
    uni.stopPullDownRefresh()
  }
}

async function retry() {
  apiEndpoint?.invalidate()
  await boot()
}

function endpointDiagnostics(): string {
  if (!apiEndpoint) return ''
  const attempts = apiEndpoint.attempts()
  const lines = attempts.length
    ? attempts.map((item, index) => `${index + 1}. ${item.url} ${item.ok ? '可达' : `不可达：${item.err || '未知原因'}`}（${item.ms} 毫秒）`)
    : ['本轮尚未探测。']
  return `当前生效：${apiEndpoint.current()}\n最近探测：\n${lines.join('\n')}\n${debugEntry?.emptyNote || ''}`
}

async function openDebugDialog() {
  if (!apiEndpoint || !debugEntry) return
  const result = await openDialog({
    title: debugEntry.dialogTitle,
    message: endpointDiagnostics(),
    confirmText: debugEntry.confirmCopy,
    input: { placeholder: debugEntry.inputPlaceholder }
  })
  if (!result.confirm) return
  const typed = result.value.trim()
  if (typed) apiEndpoint.setOverride(typed)
  else apiEndpoint.clearOverride()
  await boot()
}

async function acceptConsent() {
  if (!consented.value || busy.value) return
  busy.value = true
  try {
    await api.agreeConsent()
    await boot()
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '同意记录保存失败，请稍后重试。'), icon: 'none' })
    state.value = 'consent'
  } finally {
    busy.value = false
  }
}

/**
 * 退出登录后的手动登录：重建登录态并重新加载首页数据。
 * 登录失败停留在登录态并给出可读提示，不覆盖原有错误页。
 */
async function doLogin() {
  if (busy.value) return
  busy.value = true
  loginError.value = ''
  try {
    await loginAfterSignOut()
    await boot()
  } catch (error: any) {
    loginError.value = userFacingMessage(error, '登录失败，请检查网络后重试。')
    state.value = 'login'
  } finally {
    busy.value = false
  }
}

function showPolicy(title: string) {
  void openDialog({ title, message: policyModalCopy, showCancel: false })
}

function openMember() {
  const suffix = quotaExhausted.value ? '?reason=quota' : ''
  uni.navigateTo({ url: `/pages/member/index${suffix}` })
}

function openEntry(entry: Entry) {
  uni.navigateTo({ url: `/pages/qa/index?entry=${entry}` })
}

function openTools() {
  navigateWithFeedback('/pages/tools/index')
}

/**
 * 跳转并兜底提示：跳转失败（页面未注册/被拦截）时给出可见反馈，
 * 避免入口「点了没反应」（缺陷 D4）。
 */
function navigateWithFeedback(url: string) {
  uni.navigateTo({
    url,
    fail: () => {
      uni.showToast({ title: navFailedCopy, icon: 'none' })
    }
  })
}

/**
 * 加载每日一则小知识。
 *
 * 取数顺序：当日本地缓存 → 知识库接口 → 内置通用提示。
 * 任何异常都在服务内降级，不改变首页其他模块的状态。
 */
async function loadDailyKnowledge() {
  if (dailyKnowledgeBusy) return
  dailyKnowledgeBusy = true
  try {
    const result = await resolveDailyKnowledge({
      storage: {
        getStorageSync: (key: string) => uni.getStorageSync(key),
        setStorageSync: (key: string, value: unknown) => uni.setStorageSync(key, value)
      },
      load: () => api.fetchDailyKnowledge()
    })
    dailyKnowledge.value = result.entry
    dailyKnowledgeDate.value = formatKnowledgeDate(result.date)
    dailyKnowledgeSource.value = result.source
  } catch {
    // 兜底：取数服务自身异常时仍保证卡片可读，不把首页卡在占位态
    const today = localDateStamp()
    dailyKnowledge.value = pickFallback(today)
    dailyKnowledgeDate.value = formatKnowledgeDate(today)
    dailyKnowledgeSource.value = 'fallback'
  } finally {
    dailyKnowledgeBusy = false
  }
}

/**
 * 打开科普全书页面（首页知识卡片点击入口）。
 *
 * 页面未注册或被拦截时给出可见提示，避免「点了没反应」。
 */
function openKnowledgeBook() {
  navigateWithFeedback('/pages/knowledge/index')
}

onShow(() => { void boot({ silent: state.value === 'ready' }) })
onPullDownRefresh(() => { void boot({ silent: state.value === 'ready' }) })
</script>

<style scoped>
.page-shell { min-height: 100vh; padding-bottom: calc(272rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.card-pressed { opacity: .88; }

.debug-entry { display: flex; align-items: center; justify-content: center; margin-top: 4rpx; padding: 16rpx 0 24rpx; }
.debug-entry-copy { padding-bottom: 4rpx; color: var(--ink-3); border-bottom: 1rpx solid var(--line); font-size: 24rpx; }

.daily-tip { display: flex; align-items: center; gap: 14rpx; margin-bottom: 24rpx; padding: 22rpx 24rpx; background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-card); box-shadow: var(--shadow-float); animation: tip-in 240ms ease-out; }
@keyframes tip-in {
  from { opacity: 0; transform: translateY(-8rpx); }
  to { opacity: 1; transform: translateY(0); }
}
.tip-dot { flex: none; width: 12rpx; height: 12rpx; border-radius: 50%; background: var(--info); }
.tip-copy { flex: 1; color: var(--ink-2); font-size: 24rpx; line-height: 1.55; }
.tip-action { flex: none; color: var(--primary-press); font-size: 24rpx; font-weight: 650; }

.quota-card { margin-bottom: 24rpx; padding: 26rpx 28rpx 24rpx; background-color: var(--warn-soft); border-radius: var(--r-card); }
.quota-card.exhausted { background-color: var(--warn); }
.quota-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.quota-badge { display: inline-flex; align-items: center; gap: 10rpx; color: var(--ink-2); font-size: 24rpx; }
.quota-badge-dot { width: 12rpx; height: 12rpx; border-radius: 50%; background: var(--warn); }
.quota-readout { color: var(--ink-1); font-size: 26rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.quota-track { height: 12rpx; margin-top: 20rpx; overflow: hidden; background: rgba(192, 138, 80, .22); border-radius: var(--r-control); }
.quota-fill { height: 100%; background: var(--warn); border-radius: var(--r-control); transition: width 220ms ease-out; }
.quota-note { display: block; margin-top: 16rpx; color: var(--ink-2); font-size: 22rpx; line-height: 1.5; }
.quota-card.exhausted .quota-badge,
.quota-card.exhausted .quota-readout,
.quota-card.exhausted .quota-note { color: var(--on-primary); }
.quota-card.exhausted .quota-badge-dot { background: var(--on-primary); }
.quota-card.exhausted .quota-track { background: rgba(255, 255, 255, .35); }
.quota-card.exhausted .quota-fill { background: var(--on-primary); }

.tools-entry { display: inline-flex; align-items: baseline; gap: 8rpx; margin: -6rpx 0 20rpx; padding: 8rpx 0; }
.tools-entry-copy { color: var(--primary-press); font-size: 24rpx; line-height: 1.5; }
.tools-entry-arrow { color: var(--primary-press); font-size: 24rpx; }

.knowledge-card { position: relative; margin-bottom: 24rpx; padding: 32rpx 30rpx 26rpx; background-color: var(--primary-soft); border-radius: var(--r-card); overflow: hidden; }
.knowledge-copy { position: relative; z-index: 1; padding-right: 178rpx; }
.knowledge-eyebrow { display: flex; align-items: baseline; gap: 14rpx; }
.knowledge-label { color: var(--ink-2); font-size: 24rpx; }
.knowledge-date { color: var(--ink-3); font-size: 22rpx; font-variant-numeric: tabular-nums; }
.knowledge-title { display: block; margin-top: 10rpx; color: var(--ink-1); font-size: 38rpx; font-weight: 700; line-height: 1.35; letter-spacing: 1rpx; }
.knowledge-summary {
  display: -webkit-box;
  margin-top: 12rpx;
  overflow: hidden;
  color: var(--ink-2);
  font-size: 25rpx;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
.knowledge-illustration { position: absolute; top: 24rpx; right: 20rpx; width: 160rpx; height: 160rpx; }
.knowledge-ring { position: absolute; top: 10rpx; right: 4rpx; width: 126rpx; height: 108rpx; border: 1px solid var(--line-warm); border-radius: 50%; transform: rotate(-16deg); }
.knowledge-ground { position: absolute; bottom: 14rpx; left: 32rpx; width: 96rpx; height: 12rpx; background: rgba(124, 144, 130, .18); border-radius: 50%; }
.knowledge-stem { position: absolute; bottom: 24rpx; left: 76rpx; width: 4rpx; height: 58rpx; background: var(--primary); border-radius: 3rpx; }
.knowledge-leaf { position: absolute; width: 46rpx; height: 30rpx; border-radius: 0 26rpx 0 26rpx; }
.leaf-up { bottom: 58rpx; left: 32rpx; background: var(--surface); border: 1px solid var(--line-warm); transform: rotate(-12deg); }
.leaf-down { bottom: 34rpx; left: 78rpx; background: var(--primary); transform: scaleX(-1) rotate(-12deg); }
.knowledge-foot { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 16rpx; margin-top: 24rpx; }
.knowledge-tags { display: flex; flex-wrap: wrap; gap: 10rpx; min-height: 8rpx; }
.knowledge-tag { padding: 8rpx 20rpx; color: var(--primary-press); background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-control); font-size: 22rpx; line-height: 1.3; }
.knowledge-tag.ghost { color: var(--ink-2); background: transparent; }
.knowledge-tag.note { color: var(--ink-3); background: var(--surface-warm); border-style: dashed; }
.knowledge-action { display: inline-flex; flex: none; align-items: baseline; gap: 10rpx; color: var(--primary-press); font-size: 28rpx; font-weight: 650; }
.knowledge-arrow { font-size: 30rpx; }

.entry-card { margin-bottom: 24rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); overflow: hidden; }
.entry-row { display: flex; align-items: center; gap: 22rpx; min-height: 148rpx; padding: 22rpx 28rpx; }
.entry-row + .entry-row { border-top: 1px solid var(--line); }
.row-pressed { background: var(--surface-warm); }
.entry-icon { position: relative; width: 72rpx; height: 72rpx; flex: none; border-radius: 50%; }
.icon-info { background: var(--info-soft); }
.icon-warn { background: var(--warn-soft); }
.icon-primary { background: var(--primary-soft); }
.glyph { position: absolute; top: 0; right: 0; bottom: 0; left: 0; }
.glyph-child::before { position: absolute; top: 17rpx; left: 26rpx; width: 14rpx; height: 14rpx; border: 3rpx solid var(--info); border-radius: 50%; content: ''; }
.glyph-child::after { position: absolute; top: 38rpx; left: 17rpx; width: 32rpx; height: 15rpx; border: 3rpx solid var(--info); border-bottom: 0; border-radius: 17rpx 17rpx 0 0; content: ''; }
.glyph-pet::before { position: absolute; top: 34rpx; left: 22rpx; width: 28rpx; height: 22rpx; background: var(--warn); border-radius: 50% 50% 45% 45% / 60% 60% 40% 40%; content: ''; }
.glyph-pet::after { position: absolute; top: 18rpx; left: 20rpx; width: 13rpx; height: 13rpx; background: var(--warn); border-radius: 50%; box-shadow: 19rpx 2rpx 0 var(--warn); content: ''; }
.glyph-family::before { position: absolute; top: 20rpx; left: 29rpx; width: 14rpx; height: 14rpx; background: var(--primary); border-radius: 50%; content: ''; }
.glyph-family::after { position: absolute; top: 36rpx; left: 20rpx; width: 14rpx; height: 14rpx; background: var(--primary); border-radius: 50%; box-shadow: 18rpx 0 0 var(--primary); content: ''; }
.entry-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 8rpx; }
.entry-title { color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.entry-sub { color: var(--ink-3); font-size: 24rpx; line-height: 1.5; }
.entry-arrow { flex: none; color: var(--ink-3); font-size: 30rpx; }

.member-card { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; padding: 28rpx; background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.member-main { display: flex; flex-direction: column; min-width: 0; gap: 8rpx; }
.member-title { color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.member-sub { color: var(--ink-3); font-size: 24rpx; }
.member-pill { flex: none; padding: 12rpx 30rpx; color: var(--primary-press); border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 26rpx; }
.footer-note { display: block; padding: 44rpx 0 8rpx; color: var(--ink-3); font-size: 24rpx; text-align: center; }

.consent-wrap { padding-top: 16rpx; }
.consent-medallion { position: relative; width: 176rpx; height: 176rpx; margin: 0 auto; background-color: var(--primary-soft); border-radius: 50%; }
.consent-medallion::before { position: absolute; top: -20rpx; right: -20rpx; bottom: -20rpx; left: -20rpx; border: 1px solid var(--line-warm); border-radius: 50%; content: ''; }
.medallion-stem { position: absolute; bottom: 32rpx; left: 84rpx; width: 7rpx; height: 56rpx; background: var(--primary); border-radius: 4rpx; }
.medallion-leaf { position: absolute; width: 44rpx; height: 29rpx; border-radius: 0 24rpx 0 24rpx; }
.medallion-leaf-left { top: 44rpx; left: 48rpx; background: var(--primary); transform: rotate(-14deg); }
.medallion-leaf-right { top: 58rpx; left: 88rpx; background: #9DB0A2; transform: scaleX(-1) rotate(-14deg); }
.consent-panel { margin-top: 44rpx; padding: 40rpx 34rpx 36rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-float); }
.consent-tag { display: inline-flex; padding: 8rpx 20rpx; background: var(--primary-soft); border-radius: var(--r-control); }
.consent-tag text { color: var(--primary-press); font-size: 22rpx; line-height: 1.3; }
.consent-title { display: block; margin-top: 20rpx; color: var(--ink-1); font-size: 38rpx; font-weight: 700; line-height: 1.35; }
.consent-copy { display: block; margin-top: 18rpx; color: var(--ink-2); font-size: 28rpx; line-height: 1.75; }
.consent-links { display: flex; gap: 16rpx; margin-top: 26rpx; }
.consent-link { padding: 12rpx 22rpx; background: var(--surface-warm); border: 1px solid var(--line-warm); border-radius: var(--r-control); }
.consent-link text { color: var(--primary-press); font-size: 26rpx; line-height: 1.3; }
.link-pressed { background: var(--primary-soft); }
.agree-row { display: flex; align-items: center; gap: 16rpx; margin-top: 28rpx; padding: 22rpx 24rpx; background: var(--surface-warm); border: 1px solid var(--line-warm); border-radius: var(--r-inner); }
.agree-copy { color: var(--ink-2); font-size: 26rpx; }
.check-mark { display: flex; align-items: center; justify-content: center; width: 40rpx; height: 40rpx; flex: none; color: var(--on-primary); background: var(--surface); border: 2rpx solid var(--line); border-radius: 10rpx; }
.check-mark.checked { background: var(--primary); border-color: var(--primary); }
.check-tick { width: 18rpx; height: 10rpx; border-left: 3rpx solid var(--on-primary); border-bottom: 3rpx solid var(--on-primary); transform: rotate(-45deg) translateY(-2rpx); }
.primary-button { display: flex; align-items: center; justify-content: center; min-height: 96rpx; margin-top: 30rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; letter-spacing: 2rpx; }
.primary-button.disabled { opacity: .55; }
.primary-pressed { opacity: .92; }
.login-error { display: block; margin-top: 20rpx; color: var(--danger); font-size: 24rpx; line-height: 1.6; }
.login-note { display: block; margin-top: 22rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }

@media screen and (max-width: 350px) {
  .knowledge-illustration { transform: scale(.88); transform-origin: right top; }
  .knowledge-copy { padding-right: 148rpx; }
}
@media (prefers-reduced-motion: reduce) {
  .quota-fill { transition: none; }
  .daily-tip { animation: none; }
}
</style>

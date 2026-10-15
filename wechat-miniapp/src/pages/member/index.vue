<template>
  <view class="member-page tex">
    <MiniPageHeader :title="pageTitle" />

    <view class="page-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />

      <template v-else>
        <view class="hero tex">
          <view class="hero-copy">
            <text class="hero-title">{{ heroTitle }}</text>
            <text class="hero-sub">{{ heroSub }}</text>
          </view>
          <view class="hero-badge"><text>{{ heroBadge }}</text></view>
        </view>

        <text class="section-label">{{ tableCaption }}</text>
        <view class="benefit-table">
          <view class="table-row table-head">
            <text class="cell-label">{{ tableColBenefit }}</text>
            <text class="cell-free">{{ tableColFree }}</text>
            <view class="cell-member">
              <text class="cell-member-text">{{ tableColMember }}</text>
            </view>
          </view>
          <view v-for="row in benefitRows" :key="row.label" class="table-row">
            <text class="cell-label">{{ row.label }}</text>
            <text class="cell-free">{{ row.free }}</text>
            <view class="cell-member">
              <view class="check-circle"><view class="check-mark-inner" /></view>
              <text class="cell-member-text">{{ row.member }}</text>
            </view>
          </view>
        </view>

        <template v-if="canPurchase">
          <view class="price-card">
            <view class="price-head">
              <text class="price-name">{{ productName }}</text>
              <view v-if="isMember" class="price-expire">
                <text class="expire-label">{{ expireLabel }}</text>
                <text class="expire-value">{{ memberExpireText }}</text>
              </view>
              <view v-else class="price-amount">
                <text class="amount">{{ priceAmount }}</text>
                <text class="amount-unit">{{ priceUnit }}</text>
              </view>
            </view>

            <view v-if="!isMember" class="badge-row">
              <view v-for="badge in priceBadges" :key="badge" class="price-badge"><text>{{ badge }}</text></view>
            </view>
            <text class="price-note">{{ priceNote }}</text>

            <template v-if="!isMember">
              <view class="refund-row" @tap="refundAgreed = !refundAgreed">
                <view class="check-mark" :class="{ checked: refundAgreed }"><view v-if="refundAgreed" class="check-tick" /></view>
                <text class="refund-copy">{{ refundCopy }}</text>
              </view>
              <button class="primary-button" :class="{ disabled: !refundAgreed || paying }" :disabled="!refundAgreed || paying" hover-class="pressed" @tap="startPurchase">{{ ctaOpenCopy }}</button>
            </template>
            <button v-else class="primary-button" hover-class="pressed" @tap="startPurchase">{{ ctaRenewCopy }}</button>
          </view>
        </template>

        <StateSkeleton
          v-else-if="loadFailed"
          mode="degraded"
          :title="loadFailTitle"
          :action-text="retryCopy"
          @action="load(true)"
        />

        <view v-else class="notice-card">
          <text class="notice-title">{{ unavailableTitle }}</text>
          <text class="notice-copy">{{ unavailableCopy }}</text>
          <button class="ghost-button" hover-class="pressed" @tap="openBenefitDoc">{{ benefitDetailCopy }}</button>
        </view>

        <view class="readonly-card">
          <text class="readonly-title">{{ readonlyTitle }}</text>
          <text class="readonly-copy">{{ readonlyCopy }}</text>
        </view>

        <view class="link-row">
          <button v-if="canPurchase" class="link-button" hover-class="pressed" @tap="openOrders">{{ ordersLinkCopy }}</button>
          <button class="link-button" hover-class="pressed" @tap="openBenefitDoc">{{ benefitDetailCopy }}</button>
        </view>

        <MiniComplianceBar />
      </template>
    </view>

    <view v-if="sheet.visible" class="sheet-mask" @tap="closeSheet">
      <view class="sheet" @tap.stop>
        <view class="sheet-head">
          <text class="sheet-title">{{ sheetTitle }}</text>
          <button class="sheet-close" hover-class="pressed" @tap="closeSheet">{{ closeCopy }}</button>
        </view>

        <scroll-view v-if="sheet.kind === 'orders'" scroll-y class="sheet-scroll">
          <view v-if="ordersLoading" class="list-note">
            <text class="list-sub">{{ ordersLoadingCopy }}</text>
          </view>
          <view v-else-if="ordersError" class="list-note">
            <text class="note-error">{{ ordersError }}</text>
            <button class="mini-link" hover-class="pressed" @tap="loadOrders">{{ retryCopy }}</button>
          </view>
          <view v-else-if="!orders.length" class="list-note">
            <text class="list-sub">{{ ordersEmptyCopy }}</text>
          </view>
          <view v-else class="order-list">
            <view v-for="order in orders" :key="order.order_no" class="order-row">
              <view class="order-head">
                <text class="order-title">{{ orderTitle }}</text>
                <text class="order-status" :class="orderStatusTone(order.status)">{{ orderStatusLabel(order.status) }}</text>
              </view>
              <text class="list-sub">{{ orderMeta(order) }}</text>
              <text class="order-no">{{ order.order_no }}</text>
            </view>
          </view>
          <view class="sheet-gap" />
        </scroll-view>

        <scroll-view v-else scroll-y class="sheet-scroll">
          <text v-for="(para, index) in benefitParagraphs" :key="index" class="doc-para">{{ para }}</text>
          <view class="sheet-gap" />
        </scroll-view>
      </view>
    </view>

    <view v-if="quotaPopupVisible" class="modal-mask" @tap="quotaPopupVisible = false">
      <view class="quota-modal" @tap.stop>
        <text class="quota-title">{{ quotaTitle }}</text>
        <text class="quota-copy">{{ quotaCopy }}</text>
        <view class="quota-actions">
          <button class="ghost-button" hover-class="pressed" @tap="openBenefitDocFromQuota">{{ benefitDetailCopy }}</button>
          <button class="primary-button" hover-class="pressed" @tap="quotaPopupVisible = false">{{ quotaDismissCopy }}</button>
        </view>
      </view>
    </view>

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
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

type OrderItem = {
  order_no: string
  amount_micro: number
  platform: string
  status: string
  paid_at: string | null
  created_at: string | null
  product_code?: string
}

const pageTitle = '会员权益'
const heroTitle = '解锁深度养育内容'
const heroSub = '深度方案 · 月度计划 · 完整复合场景'
const heroBadgeFallback = '月卡'
const tableCaption = '免费与会员权益对照'
const tableColBenefit = '权益'
const tableColFree = '免费'
const tableColMember = '会员'
const expireLabel = '有效期至'
const priceNote = '价格以服务端商品配置为准；单次购买、不自动续费，到期不自动扣费。'
const refundCopy = '虚拟内容一经解锁不支持退款，我已阅读并知悉上述说明'
const ctaRenewCopy = '续费'
const unavailableTitle = '当前设备暂不支持购买'
const unavailableCopy = '可在 Android 设备开通；iOS 不开放虚拟支付入口，本页仅展示权益说明。'
const benefitDetailCopy = '查看权益说明'
const readonlyTitle = '会员到期后'
const readonlyCopy = '深度内容保留只读（不可新增），续费后恢复。'
const ordersLinkCopy = '订单记录'
const retryCopy = '点此重试'
const loadFailTitle = '价格加载失败'
const closeCopy = '关闭'
const ordersLoadingCopy = '正在读取订单记录…'
const ordersEmptyCopy = '暂无订单'
const orderTitle = '会员订单'
const quotaTitle = '今日免费额度已用完'
const quotaCopy = '免费额度每日恢复，次日 00:00 重新开始；开通会员后不受额度限制。'
const quotaDismissCopy = '知道了'
const payModalTitle = '开通会员'
const payModalCopy = '微信支付接入后开放，当前版本暂无法完成支付；可先了解权益说明。'
const agreedTip = '请先勾选退款说明'

const benefitRows: { label: string; free: string; member: string }[] = [
  { label: '深度养育方案', free: '无', member: '有' },
  { label: '月度养育计划', free: '无', member: '有' },
  { label: '宠物长期规划', free: '无', member: '有' },
  { label: '复合场景方案', free: '部分', member: '完整' }
]

const benefitParagraphs = [
  '会员权益：深度养育方案、月度养育计划、宠物长期规划与完整复合场景方案；免费版仅提供基础参考与部分复合场景内容。',
  '有效期与续费：单次购买、不自动续费；有效期按购买时长顺延，到期后深度内容保留只读，可续费恢复。',
  '免费额度：免费用户每日可提问的次数以当日页面显示为准，次日 00:00 恢复；会员不受额度限制。',
  '退款说明：虚拟内容一经解锁不支持退款；购买前请阅读并勾选确认。'
]

const orderStatusLabels: Record<string, string> = { pending: '待支付', paid: '已支付' }

const state = ref<'loading' | 'ready'>('loading')
const loadFailed = ref(false)
const canPurchase = ref(false)
const productName = ref('')
const priceMicro = ref(0)
const durationDays = ref(0)
const isMember = ref(false)
const memberExpireText = ref('')
const refundAgreed = ref(false)
const paying = ref(false)
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()
const sheet = reactive({ visible: false, kind: 'orders' as 'orders' | 'benefit' })
const orders = ref<OrderItem[]>([])
const ordersLoading = ref(false)
const ordersError = ref('')
const quotaPopupVisible = ref(false)
const quotaWanted = ref(false)

const priceAmount = computed(() => {
  const yuan = priceMicro.value / 1e6
  if (!Number.isFinite(yuan) || yuan <= 0) return ''
  return parseFloat(yuan.toFixed(2)).toString()
})
const priceUnit = computed(() => {
  const days = durationDays.value
  if (days >= 360) return '元/年'
  if (days >= 28 && days <= 31) return '元/月'
  return days > 0 ? `元 / ${days} 天` : '元'
})
const ctaOpenCopy = computed(() => (priceAmount.value ? `立即开通 ${priceAmount.value} 元` : '立即开通'))
const priceBadges = computed(() => {
  const badges = ['单次购买', '不自动续费']
  if (durationDays.value > 0) badges.push(`有效期 ${durationDays.value} 天`)
  return badges
})
const heroBadge = computed(() => productName.value || heroBadgeFallback)
const sheetTitle = computed(() => (sheet.kind === 'orders' ? ordersLinkCopy : benefitDetailCopy))

function detectQueryPlatform(): 'android' | 'ios' {
  try {
    const platform = String(uni.getSystemInfoSync()?.platform || '')
    if (platform === 'ios') return 'ios'
    if (platform) return 'android'
    return 'ios'
  } catch {
    return 'ios'
  }
}

function orderStatusLabel(value: string) {
  return orderStatusLabels[value] || value
}
function orderStatusTone(value: string) {
  if (value === 'paid') return 'tone-ok'
  if (value === 'pending') return 'tone-wait'
  return 'tone-done'
}
function orderMeta(order: OrderItem) {
  const parts: string[] = []
  const amount = order.amount_micro / 1e6
  if (Number.isFinite(amount) && amount >= 0) parts.push(`¥ ${parseFloat(amount.toFixed(2))}`)
  if (order.created_at) parts.push(String(order.created_at).slice(0, 10))
  if (order.paid_at) parts.push(`支付于 ${String(order.paid_at).slice(0, 10)}`)
  return parts.join(' · ')
}

async function load(showLoading = false) {
  if (showLoading) state.value = 'loading'
  loadFailed.value = false
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const platform = detectQueryPlatform()
    const [meResult, productResult] = await Promise.allSettled([
      api.me(),
      api.billingProduct(platform)
    ])
    if (meResult.status === 'fulfilled') {
      const expireMs = meResult.value.member_expire_at ? new Date(meResult.value.member_expire_at).getTime() : 0
      isMember.value = meResult.value.member_status === 'member' && (!expireMs || expireMs > Date.now())
      memberExpireText.value = isMember.value && meResult.value.member_expire_at
        ? String(meResult.value.member_expire_at).slice(0, 10)
        : ''
    }
    if (productResult.status === 'rejected') throw productResult.reason
    const productView = productResult.value
    const product = productView.purchasable ? (productView.products || [])[0] : undefined
    if (productView.purchasable && !product) {
      loadFailed.value = true
    } else {
      canPurchase.value = Boolean(productView.purchasable && product)
      productName.value = product?.name || ''
      priceMicro.value = product?.price_micro || 0
      durationDays.value = product?.duration_days || 0
    }
    state.value = 'ready'
    if (quotaWanted.value && !isMember.value) quotaPopupVisible.value = true
  } catch (error: any) {
    loadFailed.value = true
    state.value = 'ready'
    uni.showToast({ title: userFacingMessage(error, '价格加载失败，请稍后重试。'), icon: 'none' })
  }
}

function startPurchase() {
  if (paying.value) return
  if (!isMember.value && !refundAgreed.value) {
    uni.showToast({ title: agreedTip, icon: 'none' })
    return
  }
  paying.value = true
  void openDialog({
    title: payModalTitle,
    message: payModalCopy,
    showCancel: false,
    confirmText: '知道了'
  }).finally(() => { paying.value = false })
}

function openSheet(kind: 'orders' | 'benefit') {
  sheet.kind = kind
  sheet.visible = true
  if (kind === 'orders') void loadOrders()
}
function closeSheet() {
  sheet.visible = false
}
function openBenefitDoc() {
  openSheet('benefit')
}
function openBenefitDocFromQuota() {
  quotaPopupVisible.value = false
  openBenefitDoc()
}
function openOrders() {
  openSheet('orders')
}

async function loadOrders() {
  if (ordersLoading.value) return
  ordersLoading.value = true
  ordersError.value = ''
  try {
    const result = await api.billingOrders()
    orders.value = (result.orders || []) as OrderItem[]
  } catch (error: any) {
    ordersError.value = userFacingMessage(error, '订单记录读取失败，请稍后重试。')
  } finally {
    ordersLoading.value = false
  }
}

onLoad((query) => {
  quotaWanted.value = String(query?.reason || '') === 'quota'
  void load()
})
</script>

<style scoped>
.member-page { min-height: 100vh; padding-bottom: calc(48rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }

.hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 20rpx; padding: 34rpx 30rpx; background-color: var(--primary-soft); border-radius: var(--r-card); }
.hero-copy { display: flex; flex-direction: column; min-width: 0; gap: 10rpx; }
.hero-title { color: var(--ink-1); font-size: 42rpx; font-weight: 700; letter-spacing: 1rpx; }
.hero-sub { color: var(--ink-2); font-size: 24rpx; }
.hero-badge { flex: none; padding: 10rpx 24rpx; color: var(--primary-press); background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-control); font-size: 24rpx; font-weight: 650; }

.section-label { display: block; margin: 36rpx 0 14rpx; color: var(--ink-3); font-size: 24rpx; }
.benefit-table { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); overflow: hidden; }
.table-row { display: flex; align-items: stretch; min-height: 92rpx; border-top: 1px solid var(--line); }
.table-row:first-child { border-top: 0; }
.table-head { background: var(--surface-warm); min-height: 76rpx; }
.cell-label { display: flex; flex: 2.2; align-items: center; padding: 18rpx 24rpx; color: var(--ink-1); font-size: 26rpx; }
.table-head .cell-label { color: var(--ink-3); font-size: 23rpx; }
.cell-free { display: flex; flex: 1; align-items: center; justify-content: center; color: var(--ink-3); font-size: 25rpx; }
.cell-member { display: flex; flex: 1.3; align-items: center; justify-content: center; gap: 10rpx; background: var(--primary-soft); }
.table-head .cell-member { background: var(--primary-soft); }
.cell-member-text { color: var(--primary-press); font-size: 25rpx; font-weight: 650; }
.check-circle { display: flex; align-items: center; justify-content: center; width: 30rpx; height: 30rpx; flex: none; background: var(--primary); border-radius: 50%; }
.check-mark-inner { width: 12rpx; height: 7rpx; border-left: 3rpx solid var(--on-primary); border-bottom: 3rpx solid var(--on-primary); transform: rotate(-45deg) translateY(-1rpx); }

.price-card { margin-top: 24rpx; padding: 30rpx; background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.price-head { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; }
.price-name { color: var(--ink-1); font-size: 32rpx; font-weight: 650; }
.price-amount { display: flex; align-items: baseline; gap: 8rpx; }
.amount { color: var(--ink-1); font-size: 56rpx; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: 1rpx; }
.amount-unit { color: var(--ink-2); font-size: 24rpx; }
.price-expire { display: flex; align-items: baseline; gap: 10rpx; }
.expire-label { color: var(--ink-3); font-size: 24rpx; }
.expire-value { color: var(--primary-press); font-size: 30rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.badge-row { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 22rpx; }
.price-badge { padding: 8rpx 20rpx; color: var(--ink-2); background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 22rpx; }
.price-note { display: block; margin-top: 20rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.refund-row { display: flex; align-items: flex-start; gap: 14rpx; margin-top: 26rpx; }
.refund-copy { flex: 1; color: var(--ink-2); font-size: 24rpx; line-height: 1.6; }
.check-mark { display: flex; align-items: center; justify-content: center; width: 36rpx; height: 36rpx; flex: none; color: var(--on-primary); border: 2rpx solid var(--line); border-radius: 8rpx; font-size: 24rpx; }
.check-mark.checked { background: var(--primary); border-color: var(--primary); }
.check-tick { width: 16rpx; height: 9rpx; border-left: 3rpx solid var(--on-primary); border-bottom: 3rpx solid var(--on-primary); transform: rotate(-45deg) translateY(-2rpx); }
.primary-button { display: flex; align-items: center; justify-content: center; min-height: 92rpx; margin-top: 28rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }
.primary-button.disabled { opacity: .55; }

.notice-card { margin-top: 24rpx; padding: 30rpx; background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-card); }
.notice-title { display: block; color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.notice-copy { display: block; margin-top: 12rpx; color: var(--ink-2); font-size: 24rpx; line-height: 1.65; }
.ghost-button { display: inline-flex; align-items: center; justify-content: center; min-height: 80rpx; margin: 24rpx 0 0; padding: 0 40rpx; color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 26rpx; }

.readonly-card { margin-top: 24rpx; padding: 26rpx 30rpx; background: var(--info-soft); border-radius: var(--r-inner); }
.readonly-title { display: block; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.readonly-copy { display: block; margin-top: 8rpx; color: var(--ink-2); font-size: 23rpx; line-height: 1.6; }

.link-row { display: flex; gap: 44rpx; margin-top: 34rpx; padding: 0 6rpx; }
.link-button { margin: 0; padding: 6rpx 0; color: var(--primary-press); background: transparent; border: 0; font-size: 27rpx; line-height: 1.4; }

.sheet-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 80; background: rgba(46, 51, 46, .4); }
.sheet { position: fixed; right: 0; bottom: 0; left: 0; z-index: 90; display: flex; flex-direction: column; max-height: 88vh; padding-bottom: env(safe-area-inset-bottom); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; }
.sheet-head { display: flex; align-items: center; justify-content: space-between; padding: 28rpx 28rpx 16rpx; }
.sheet-title { color: var(--ink-1); font-size: 31rpx; font-weight: 650; }
.sheet-close { margin: 0; padding: 4rpx 0; color: var(--ink-3); background: transparent; border: 0; font-size: 25rpx; line-height: 1.4; }
.sheet-scroll { height: 58vh; padding: 0 28rpx; box-sizing: border-box; }
.sheet-gap { height: 34rpx; }
.list-note { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; margin-top: 18rpx; padding: 22rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); }
.list-sub { color: var(--ink-3); font-size: 23rpx; line-height: 1.55; }
.note-error { color: var(--danger); font-size: 23rpx; line-height: 1.5; }
.mini-link { margin: 0; padding: 6rpx 0; color: var(--primary-press); background: transparent; border: 0; font-size: 24rpx; line-height: 1.4; }
.order-list { margin-top: 18rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); overflow: hidden; }
.order-row { display: flex; flex-direction: column; gap: 8rpx; padding: 20rpx 22rpx; }
.order-row + .order-row { border-top: 1px solid var(--line); }
.order-head { display: flex; align-items: center; justify-content: space-between; gap: 14rpx; }
.order-title { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.order-status { flex: none; padding: 4rpx 16rpx; border-radius: var(--r-control); font-size: 20rpx; line-height: 1.5; }
.tone-ok { color: var(--primary-press); background: var(--primary-soft); }
.tone-wait { color: var(--info); background: var(--info-soft); }
.tone-done { color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); }
.order-no { color: var(--ink-3); font-size: 21rpx; }
.doc-para { display: block; margin-top: 20rpx; color: var(--ink-2); font-size: 26rpx; line-height: 1.75; }

.modal-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 120; display: flex; align-items: center; justify-content: center; background: rgba(46, 51, 46, .45); }
.quota-modal { width: 82%; padding: 40rpx 34rpx 32rpx; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--shadow-float); }
.quota-title { display: block; color: var(--ink-1); font-size: 34rpx; font-weight: 700; }
.quota-copy { display: block; margin-top: 18rpx; color: var(--ink-2); font-size: 26rpx; line-height: 1.7; }
.quota-actions { display: flex; gap: 18rpx; margin-top: 32rpx; }
.quota-actions .ghost-button { flex: 1; margin: 0; }
.quota-actions .primary-button { flex: 1; min-height: 88rpx; margin: 0; font-size: 27rpx; }
</style>

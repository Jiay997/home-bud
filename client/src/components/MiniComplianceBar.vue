<script setup lang="ts">
import MiniDialog from './MiniDialog.vue'
import { useDialog } from '../services/dialog'

const props = withDefaults(defineProps<{
  fixed?: boolean
}>(), {
  fixed: false
})

// 含拉丁字母文案一律经 script 常量 + 插值渲染（route.test 静态文案零英文约束）
const disclaimer = '内容由人工智能生成，仅供参考，不替代医疗或专业诊断'
const badge = '内容由 AI 生成'
const modalTitle = 'AI 生成内容说明'
const modalCopy = '本服务中的回应与报告由人工智能模型生成，仅作为家庭养育与共居参考，不构成医疗、心理、兽医等专业意见或诊断。如有健康、安全方面的疑虑，请及时咨询具备资质的专业人员。'

const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

function showDetail() {
  void openDialog({ title: modalTitle, message: modalCopy, showCancel: false, confirmText: '知道了' })
}
</script>

<template>
  <view class="compliance" :class="{ fixed: props.fixed }" @tap="showDetail">
    <text class="compliance-copy">{{ disclaimer }}</text>
    <view class="badge">
      <view class="badge-mark" />
      <text class="badge-text">{{ badge }}</text>
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
</template>

<style scoped>
.compliance { display: flex; flex-direction: column; gap: 10rpx; padding: 22rpx 32rpx 26rpx; border-top: 1px solid var(--line); }
.compliance.fixed { position: fixed; right: 0; bottom: calc(112rpx + env(safe-area-inset-bottom)); left: 0; z-index: 40; padding: 14rpx 32rpx 16rpx; background: rgba(244, 243, 240, .97); }
.compliance-copy { color: var(--ink-3); font-size: 24rpx; line-height: 1.5; }
.badge { display: inline-flex; align-items: center; gap: 8rpx; align-self: flex-start; padding: 6rpx 16rpx; background: var(--info-soft); border-radius: var(--r-control); }
.badge-mark { width: 10rpx; height: 10rpx; border-radius: 50%; background: var(--info); }
.badge-text { color: var(--ink-2); font-size: 22rpx; line-height: 1; }
</style>

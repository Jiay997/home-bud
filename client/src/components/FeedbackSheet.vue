<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import { userFacingMessage } from '../services/user-message'

const props = defineProps<{
  visible: boolean
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const sheetTitle = '意见反馈'
const sheetCopy = '反馈仅用于产品改进；如涉及内容违规，请使用举报入口。'
const placeholderText = '写下你遇到的问题或建议（500 字以内）'
const receiptTitle = '感谢你的反馈'
const receiptCopy = '我们将在受理时限内完成查看，处理结果通过消息渠道告知。'

const content = ref('')
const submitting = ref(false)
const receipt = ref<{ no: string; hours: number } | null>(null)

watch(() => props.visible, (value) => {
  if (!value) return
  content.value = ''
  submitting.value = false
  receipt.value = null
})

async function submit() {
  const text = content.value.trim()
  if (!text || submitting.value) return
  submitting.value = true
  try {
    const result = await api.feedback(text)
    receipt.value = { no: result.feedback_no, hours: result.receipt_hours }
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '提交失败，请稍后重试。'), icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <view v-if="props.visible" class="feedback-mask" @tap="emit('close')">
    <view class="feedback-sheet" @tap.stop>
      <template v-if="receipt">
        <view class="receipt-mark"><view class="receipt-check" /></view>
        <text class="sheet-title">{{ receiptTitle }}</text>
        <text class="receipt-no">编号 {{ receipt.no }}</text>
        <text class="sheet-copy">{{ receiptCopy }}</text>
        <text class="sheet-copy">预计 {{ receipt.hours }} 小时内完成查看。</text>
        <button class="sheet-primary" @tap="emit('close')">知道了</button>
      </template>
      <template v-else>
        <text class="sheet-title">{{ sheetTitle }}</text>
        <text class="sheet-copy">{{ sheetCopy }}</text>
        <textarea
          v-model="content"
          class="feedback-input"
          maxlength="500"
          :placeholder="placeholderText"
          :auto-height="true"
        />
        <button
          class="sheet-primary"
          :class="{ disabled: !content.trim() || submitting }"
          :disabled="!content.trim() || submitting"
          @tap="submit"
        >
          {{ submitting ? '正在提交…' : '提交反馈' }}
        </button>
        <button class="sheet-plain" @tap="emit('close')">取消</button>
      </template>
    </view>
  </view>
</template>

<style scoped>
.feedback-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 80; display: flex; align-items: flex-end; background: rgba(46, 51, 46, .34); }
.feedback-sheet { width: 100%; padding: 40rpx 32rpx calc(40rpx + env(safe-area-inset-bottom)); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; box-sizing: border-box; }
.sheet-title { display: block; color: var(--ink-1); font-size: 36rpx; font-weight: 700; }
.sheet-copy { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 26rpx; line-height: 1.6; }
.feedback-input { width: 100%; min-height: 200rpx; margin-top: 28rpx; padding: 20rpx 24rpx; color: var(--ink-1); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-inner); font-size: 28rpx; line-height: 1.6; box-sizing: border-box; }
.feedback-input::placeholder { color: var(--ink-3); }
.sheet-primary { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 92rpx; margin: 32rpx 0 0; padding: 0 24rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }
.sheet-primary.disabled { opacity: .5; }
.sheet-plain { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 88rpx; margin: 12rpx 0 0; color: var(--ink-2); background: transparent; border: 0; font-size: 28rpx; }
.receipt-mark { display: flex; align-items: center; justify-content: center; width: 88rpx; height: 88rpx; margin: 8rpx auto 24rpx; background: var(--primary-soft); border-radius: 50%; }
.receipt-check { width: 24rpx; height: 14rpx; border-bottom: 4rpx solid var(--primary); border-left: 4rpx solid var(--primary); transform: rotate(-45deg) translateY(-2rpx); }
.receipt-no { display: block; margin-top: 20rpx; color: var(--ink-1); font-size: 30rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
</style>

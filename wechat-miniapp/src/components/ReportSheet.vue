<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import { userFacingMessage } from '../services/user-message'

const props = defineProps<{
  visible: boolean
  objectType: 'qa_answer' | 'assessment'
  objectId: string
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const categories: { value: 'illegal' | 'medical_misleading' | 'harmful_to_minor' | 'other'; label: string; hint: string }[] = [
  { value: 'illegal', label: '违法违规内容', hint: '' },
  { value: 'medical_misleading', label: '医疗误导信息', hint: '' },
  { value: 'harmful_to_minor', label: '可能危害未成年人', hint: '加急处理' },
  { value: 'other', label: '其他不当内容', hint: '' }
]

const selected = ref<'' | 'illegal' | 'medical_misleading' | 'harmful_to_minor' | 'other'>('')
const description = ref('')
const submitting = ref(false)
const receipt = ref<{ reportNo: string; hours: number } | null>(null)

watch(() => props.visible, (value) => {
  if (!value) return
  selected.value = ''
  description.value = ''
  submitting.value = false
  receipt.value = null
})

const urgentNote = computed(() => selected.value === 'harmful_to_minor'
  ? '涉未成年人举报将加急核查（24 小时内启动）'
  : '')
const receiptNote = computed(() => receipt.value
  ? `我们将在 ${receipt.value.hours} 小时内完成核查`
  : '')

async function submit() {
  if (!selected.value || submitting.value) return
  submitting.value = true
  const category = selected.value
  try {
    const result = await api.createReport({
      object_type: props.objectType,
      object_id: props.objectId,
      category,
      description: description.value.trim() || undefined
    })
    receipt.value = {
      reportNo: result.report_no,
      hours: category === 'harmful_to_minor' ? 24 : 72
    }
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '举报提交失败，请稍后重试。'), icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <view v-if="props.visible" class="report-mask" @tap="emit('close')">
    <view class="report-sheet" @tap.stop>
      <template v-if="receipt">
        <view class="receipt-mark"><view class="receipt-check" /></view>
        <text class="sheet-title">举报已受理</text>
        <text class="receipt-no">受理编号 {{ receipt.reportNo }}</text>
        <text class="receipt-copy">{{ receiptNote }}</text>
        <text class="receipt-copy">核查结果将通过反馈渠道告知，感谢你的帮助。</text>
        <button class="sheet-primary" @tap="emit('close')">知道了</button>
      </template>
      <template v-else>
        <text class="sheet-title">举报该内容</text>
        <text class="sheet-copy">请选择最符合的一项，我们会尽快核查。</text>
        <view class="category-list">
          <button
            v-for="item in categories"
            :key="item.value"
            class="category-row"
            :class="{ active: selected === item.value }"
            @tap="selected = item.value"
          >
            <view class="radio" :class="{ checked: selected === item.value }" />
            <text class="category-label">{{ item.label }}</text>
            <text v-if="item.hint" class="category-hint">{{ item.hint }}</text>
          </button>
        </view>
        <textarea
          v-model="description"
          class="report-input"
          maxlength="500"
          placeholder="补充说明（选填）"
          :auto-height="true"
        />
        <text v-if="urgentNote" class="urgent-note">{{ urgentNote }}</text>
        <button
          class="sheet-primary"
          :class="{ disabled: !selected || submitting }"
          :disabled="!selected || submitting"
          @tap="submit"
        >
          {{ submitting ? '正在提交…' : '提交举报' }}
        </button>
        <button class="sheet-plain" @tap="emit('close')">取消</button>
      </template>
    </view>
  </view>
</template>

<style scoped>
.report-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 80; display: flex; align-items: flex-end; background: rgba(46, 51, 46, .34); }
.report-sheet { width: 100%; padding: 40rpx 32rpx calc(40rpx + env(safe-area-inset-bottom)); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; box-sizing: border-box; }
.sheet-title { display: block; color: var(--ink-1); font-size: 36rpx; font-weight: 700; }
.sheet-copy { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 26rpx; line-height: 1.6; }
.category-list { margin-top: 28rpx; border-top: 1px solid var(--line); }
.category-row { display: flex; align-items: center; gap: 20rpx; width: 100%; min-height: 96rpx; margin: 0; padding: 0 8rpx; color: var(--ink-1); background: transparent; border: 0; border-bottom: 1px solid var(--line); font-size: 30rpx; text-align: left; line-height: 1.4; }
.category-row.active { color: var(--ink-1); }
.radio { width: 32rpx; height: 32rpx; flex: none; border: 2rpx solid var(--line-warm); border-radius: 50%; }
.radio.checked { border: 10rpx solid var(--primary); background: var(--surface); }
.category-label { flex: 1; }
.category-hint { color: var(--warn); font-size: 24rpx; }
.report-input { width: 100%; min-height: 120rpx; margin-top: 24rpx; padding: 20rpx 24rpx; color: var(--ink-1); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-inner); font-size: 28rpx; line-height: 1.6; box-sizing: border-box; }
.report-input::placeholder { color: var(--ink-3); }
.urgent-note { display: block; margin-top: 16rpx; padding: 14rpx 20rpx; color: var(--warn); background: var(--warn-soft); border-radius: var(--r-inner); font-size: 24rpx; }
.sheet-primary { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 92rpx; margin: 32rpx 0 0; padding: 0 24rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }
.sheet-primary.disabled { opacity: .5; }
.sheet-plain { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 88rpx; margin: 12rpx 0 0; color: var(--ink-2); background: transparent; border: 0; font-size: 28rpx; }
.receipt-mark { display: flex; align-items: center; justify-content: center; width: 88rpx; height: 88rpx; margin: 8rpx auto 24rpx; background: var(--primary-soft); border-radius: 50%; }
.receipt-check { width: 24rpx; height: 14rpx; border-bottom: 4rpx solid var(--primary); border-left: 4rpx solid var(--primary); transform: rotate(-45deg) translateY(-2rpx); }
.receipt-no { display: block; margin-top: 20rpx; color: var(--ink-1); font-size: 30rpx; font-weight: 650; font-variant-numeric: tabular-nums; }
.receipt-copy { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 26rpx; line-height: 1.6; }
</style>

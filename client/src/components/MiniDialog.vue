<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  visible: boolean
  title: string
  message?: string
  confirmText?: string
  cancelText?: string
  showCancel?: boolean
  danger?: boolean
  input?: { placeholder: string; match?: string } | null
}>(), {
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  showCancel: true,
  danger: false,
  input: null
})

const emit = defineEmits<{
  (e: 'confirm', value: string): void
  (e: 'cancel'): void
}>()

const typed = ref('')
const focused = ref(false)

watch(() => props.visible, (value) => {
  if (!value) return
  typed.value = ''
  focused.value = false
})

const matched = computed(() => {
  if (!props.input?.match) return true
  return typed.value.trim() === props.input.match
})

function onInput(event: any) {
  typed.value = String(event?.detail?.value ?? '')
}
function onConfirmTap() {
  if (!matched.value) return
  emit('confirm', typed.value)
}
function onMaskTap() {
  if (props.showCancel) emit('cancel')
}
</script>

<template>
  <view v-if="visible" class="dialog-mask" @tap="onMaskTap">
    <view class="dialog-card" @tap.stop>
      <view v-if="danger" class="dialog-mark mark-danger">
        <view class="mark-bar" />
        <view class="mark-dot" />
      </view>
      <view v-else-if="!showCancel" class="dialog-mark mark-ok">
        <view class="mark-check" />
      </view>
      <text class="dialog-title">{{ title }}</text>
      <text v-if="message" class="dialog-message">{{ message }}</text>
      <input
        v-if="input"
        class="dialog-input"
        :class="{ focused }"
        :value="typed"
        :placeholder="input.placeholder"
        placeholder-style="color:#8A9088"
        @input="onInput"
        @focus="focused = true"
        @blur="focused = false"
      />
      <text v-if="input && input.match && typed && !matched" class="dialog-hint">输入不一致，请核对后重试</text>
      <view class="dialog-actions">
        <button v-if="showCancel" class="dialog-btn btn-ghost" hover-class="btn-pressed" @tap="emit('cancel')">{{ cancelText }}</button>
        <button
          class="dialog-btn btn-solid"
          :class="{ 'btn-danger': danger, 'btn-disabled': !matched }"
          :disabled="!matched"
          hover-class="btn-pressed"
          @tap="onConfirmTap"
        >{{ confirmText }}</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.dialog-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 120; display: flex; align-items: center; justify-content: center; padding: 0 88rpx; background: rgba(46, 51, 46, .34); box-sizing: border-box; animation: dialog-fade .18s ease-out both; }
.dialog-card { width: 100%; max-width: 560rpx; padding: 48rpx 40rpx 40rpx; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--shadow-float); box-sizing: border-box; animation: dialog-pop .22s cubic-bezier(.22, .9, .32, 1.18) both; }
.dialog-mark { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 88rpx; height: 88rpx; margin: 0 auto 24rpx; border-radius: 50%; }
.mark-danger { background: var(--danger-soft); }
.mark-bar { width: 8rpx; height: 30rpx; background: var(--danger); border-radius: 4rpx; }
.mark-dot { width: 8rpx; height: 8rpx; margin-top: 8rpx; background: var(--danger); border-radius: 50%; }
.mark-ok { background: var(--primary-soft); }
.mark-check { width: 24rpx; height: 14rpx; border-bottom: 4rpx solid var(--primary); border-left: 4rpx solid var(--primary); transform: rotate(-45deg) translateY(-2rpx); }
.dialog-title { display: block; color: var(--ink-1); font-size: 34rpx; font-weight: 700; text-align: center; }
.dialog-message { display: block; margin-top: 18rpx; color: var(--ink-2); font-size: 27rpx; line-height: 1.7; text-align: center; }
.dialog-input { width: 100%; height: 88rpx; margin-top: 28rpx; padding: 0 24rpx; color: var(--ink-1); background: var(--surface-warm); border: 1rpx solid var(--line-warm); border-radius: var(--r-inner); font-size: 28rpx; box-sizing: border-box; }
.dialog-input.focused { border-color: var(--primary); background: var(--surface); }
.dialog-hint { display: block; margin-top: 12rpx; color: var(--warn); font-size: 24rpx; text-align: center; }
.dialog-actions { display: flex; margin-top: 40rpx; }
.dialog-btn { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 88rpx; padding: 0 24rpx; border: 0; border-radius: var(--r-control); font-size: 30rpx; line-height: 1; }
.btn-ghost { color: var(--ink-2); background: var(--surface-warm); border: 1rpx solid var(--line-warm); font-weight: 600; }
.dialog-btn + .dialog-btn { margin-left: 20rpx; }
.btn-solid { color: var(--on-primary); background: var(--primary); font-weight: 650; }
.btn-solid.btn-danger { background: var(--danger); }
.btn-solid.btn-disabled { opacity: .45; }
.btn-pressed { opacity: .82; }
@keyframes dialog-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes dialog-pop { from { opacity: 0; transform: scale(.94); } to { opacity: 1; transform: scale(1); } }
</style>

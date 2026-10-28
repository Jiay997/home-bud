<script setup lang="ts">
withDefaults(defineProps<{
  visible: boolean
  items: string[]
  title?: string
}>(), { title: '' })

const emit = defineEmits<{
  (e: 'select', index: number): void
  (e: 'close'): void
}>()
</script>

<template>
  <view v-if="visible" class="sheet-mask" @tap="emit('close')">
    <view class="sheet-panel" @tap.stop>
      <text v-if="title" class="sheet-head">{{ title }}</text>
      <view class="sheet-list">
        <button
          v-for="(item, index) in items"
          :key="index"
          class="sheet-item"
          hover-class="item-pressed"
          @tap="emit('select', index)"
        >{{ item }}</button>
      </view>
      <button class="sheet-cancel" hover-class="item-pressed" @tap="emit('close')">取消</button>
    </view>
  </view>
</template>

<style scoped>
.sheet-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 120; display: flex; align-items: flex-end; background: rgba(46, 51, 46, .34); animation: sheet-fade .18s ease-out both; }
.sheet-panel { width: 100%; padding: 24rpx 24rpx calc(24rpx + env(safe-area-inset-bottom)); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; box-sizing: border-box; animation: sheet-rise .22s cubic-bezier(.22, .9, .32, 1.06) both; }
.sheet-head { display: block; padding: 12rpx 0 20rpx; color: var(--ink-3); font-size: 26rpx; text-align: center; }
.sheet-list { overflow: hidden; background: var(--surface-warm); border: 1rpx solid var(--line-warm); border-radius: var(--r-inner); }
.sheet-item { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 100rpx; padding: 0 32rpx; color: var(--ink-1); font-size: 30rpx; font-weight: 600; border: 0; border-radius: 0; box-sizing: border-box; }
.sheet-item + .sheet-item { border-top: 1rpx solid var(--line-warm); }
.item-pressed { background: rgba(46, 51, 46, .05); }
.sheet-cancel { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 96rpx; margin-top: 20rpx; color: var(--ink-2); background: var(--surface-warm); border: 1rpx solid var(--line-warm); border-radius: var(--r-control); font-size: 30rpx; font-weight: 600; }
@keyframes sheet-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes sheet-rise { from { opacity: 0; transform: translateY(24rpx); } to { opacity: 1; transform: translateY(0); } }
</style>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  mode?: 'skeleton' | 'empty' | 'degraded'
  title?: string
  copy?: string
  actionText?: string
}>(), {
  mode: 'skeleton',
  title: '',
  copy: '',
  actionText: ''
})
const emit = defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <view v-if="props.mode === 'skeleton'" class="skeleton" aria-label="内容加载中">
    <view class="skeleton-bar bar-a" />
    <view class="skeleton-bar bar-b" />
    <view class="skeleton-bar bar-c" />
    <view class="skeleton-bar bar-d" />
  </view>
  <view v-else-if="props.mode === 'empty'" class="empty">
    <view class="empty-illustration">
      <view class="empty-ring" />
      <view class="empty-leaf leaf-one" />
      <view class="empty-leaf leaf-two" />
    </view>
    <text class="empty-title">{{ props.title }}</text>
    <text class="empty-copy">{{ props.copy }}</text>
    <button v-if="props.actionText" class="empty-action" hover-class="pressed" @tap="emit('action')">{{ props.actionText }}</button>
  </view>
  <view v-else class="degraded">
    <view class="degraded-dot" />
    <view class="degraded-body">
      <text class="degraded-title">{{ props.title }}</text>
      <text v-if="props.copy" class="degraded-copy">{{ props.copy }}</text>
    </view>
    <button v-if="props.actionText" class="degraded-action" hover-class="pressed" @tap="emit('action')">{{ props.actionText }}</button>
  </view>
</template>

<style scoped>
.skeleton { display: flex; flex-direction: column; gap: 20rpx; padding: 8rpx 0; }
.skeleton-bar { height: 30rpx; border-radius: 8rpx; background: linear-gradient(90deg, #ECEAE6 25%, #F4F3F0 37%, #ECEAE6 63%); background-size: 400% 100%; animation: skeleton-sweep 1.4s ease infinite; }
.bar-a { width: 62%; }
.bar-b { width: 100%; }
.bar-c { width: 92%; }
.bar-d { width: 46%; }
@keyframes skeleton-sweep {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
@media (prefers-reduced-motion: reduce) {
  .skeleton-bar { animation: none; }
}
.empty { display: flex; flex-direction: column; align-items: center; padding: 72rpx 40rpx 48rpx; text-align: center; }
.empty-illustration { position: relative; width: 176rpx; height: 140rpx; }
.empty-ring { position: absolute; top: 12rpx; left: 24rpx; width: 128rpx; height: 108rpx; border: 1px solid var(--line-warm); border-radius: 50%; transform: rotate(-18deg); }
.empty-leaf { position: absolute; width: 44rpx; height: 28rpx; border-radius: 0 24rpx 0 24rpx; background: var(--primary-soft); border: 1px solid var(--line-warm); }
.leaf-one { top: 44rpx; left: 44rpx; transform: rotate(-16deg); }
.leaf-two { top: 66rpx; left: 82rpx; transform: scaleX(-1) rotate(-16deg); background: var(--warn-soft); }
.empty-title { display: block; margin-top: 20rpx; color: var(--ink-1); font-size: 32rpx; font-weight: 650; }
.empty-copy { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 26rpx; line-height: 1.6; }
.empty-action { display: flex; align-items: center; justify-content: center; min-width: 280rpx; min-height: 84rpx; margin: 32rpx 0 0; padding: 0 48rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 28rpx; font-weight: 650; }
.pressed { opacity: .82; }
.degraded { display: flex; align-items: center; gap: 16rpx; padding: 20rpx 24rpx; background: var(--warn-soft); border-radius: var(--r-inner); }
.degraded-dot { width: 12rpx; height: 12rpx; flex: none; border-radius: 50%; background: var(--warn); }
.degraded-body { display: flex; flex-direction: column; flex: 1; min-width: 0; gap: 4rpx; }
.degraded-title { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.degraded-copy { color: var(--ink-2); font-size: 24rpx; line-height: 1.5; }
.degraded-action { flex: none; margin: 0; padding: 8rpx 20rpx; color: var(--warn); background: transparent; border: 1rpx solid var(--warn); border-radius: var(--r-control); font-size: 24rpx; }
</style>

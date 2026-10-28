<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  home?: boolean
}>(), {
  title: '',
  subtitle: '',
  home: false
})

const systemInfo = (() => {
  try {
    const info = uni.getWindowInfo()
    return { statusBarHeight: info.statusBarHeight, windowWidth: info.windowWidth }
  } catch {
    try {
      return uni.getSystemInfoSync()
    } catch {
      return { statusBarHeight: 20, windowWidth: 375 }
    }
  }
})()
const statusBarHeight = systemInfo.statusBarHeight || 20
const miniProgram = (globalThis as typeof globalThis & {
  wx?: { getMenuButtonBoundingClientRect?: () => { left: number } }
}).wx
let menuButton: { left: number } | undefined
try {
  menuButton = miniProgram?.getMenuButtonBoundingClientRect?.()
} catch {
  menuButton = undefined
}
const menuLeft = Number(menuButton?.left)
const rightInset = Number.isFinite(menuLeft) && menuLeft > 0
  ? Math.max(24, (systemInfo.windowWidth || 375) - menuLeft + 8)
  : 32
const headerHeight = `${statusBarHeight + 44}px`
const rowStyle = computed(() => ({ paddingRight: `${rightInset}px` }))
const canGoBack = (() => {
  try {
    return getCurrentPages().length > 1
  } catch {
    return true
  }
})()

function goBack() {
  uni.navigateBack({
    delta: 1,
    fail: () => uni.reLaunch({ url: '/pages/index/index' })
  })
}

let meSwitching = false
function openMe() {
  if (meSwitching) return
  meSwitching = true
  const release = () => { meSwitching = false }
  uni.redirectTo({ url: '/pages/me/index', fail: release, complete: release })
  setTimeout(release, 800)
}
</script>

<template>
  <view class="mini-header" :style="{ height: headerHeight }">
    <view class="status-space" :style="{ height: `${statusBarHeight}px` }" />
    <view class="header-row" :style="rowStyle">
      <template v-if="props.home">
        <view class="header-copy home-copy">
          <text class="header-title brand-title">Babe宝伴</text>
          <text v-if="props.subtitle" class="header-subtitle">{{ props.subtitle }}</text>
        </view>
        <button class="avatar-button" aria-label="进入我的" hover-class="avatar-pressed" @tap="openMe">
          <view class="avatar">
            <view class="avatar-leaf leaf-left" />
            <view class="avatar-leaf leaf-right" />
            <view class="avatar-stem" />
          </view>
        </button>
      </template>
      <template v-else>
        <button v-if="canGoBack" class="back-button" hover-class="back-pressed" aria-label="返回" @tap="goBack">
          <view class="back-chevron" />
        </button>
        <view v-else class="back-placeholder" />
        <view class="header-copy pushed-copy">
          <text class="header-title">{{ props.title }}</text>
          <text v-if="props.subtitle" class="header-subtitle">{{ props.subtitle }}</text>
        </view>
        <slot name="action">
          <view v-if="canGoBack" class="header-spacer" />
        </slot>
      </template>
    </view>
  </view>
</template>

<style scoped>
.mini-header { position: sticky; top: 0; z-index: 30; width: 100%; overflow: hidden; color: var(--ink-1); background: var(--surface); border-bottom: 1px solid var(--line); box-sizing: border-box; }
.status-space { width: 100%; }
.header-row { display: flex; align-items: center; height: 44px; padding-left: 32rpx; box-sizing: border-box; }
.header-copy { display: flex; flex-direction: column; min-width: 0; gap: 2px; }
.home-copy { flex: 1; }
.pushed-copy { flex: 1; align-items: center; text-align: center; }
.header-title { overflow: hidden; color: var(--ink-1); font-size: 34rpx; font-weight: 650; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
.brand-title { font-size: 36rpx; letter-spacing: 1rpx; }
.header-subtitle { overflow: hidden; color: var(--ink-3); font-size: 22rpx; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.back-button { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; flex: none; margin: 0 4px 0 -8px; padding: 0; color: var(--ink-1); background: transparent; border: 0; }
.back-pressed { opacity: .6; }
.back-placeholder { width: 36px; height: 44px; flex: none; }
.back-chevron { width: 10px; height: 10px; border-top: 1.5px solid currentColor; border-left: 1.5px solid currentColor; transform: rotate(-45deg); }
.header-spacer { width: 44px; height: 44px; flex: none; margin-left: 4px; }
.avatar-button { display: flex; align-items: center; justify-content: center; width: 88rpx; height: 88rpx; flex: none; margin: 0; padding: 0; background: transparent; border: 0; }
.avatar-pressed { opacity: .7; }
.avatar { position: relative; width: 72rpx; height: 72rpx; border-radius: 50%; background: var(--primary-soft); border: 1px solid var(--line-warm); }
.avatar-stem { position: absolute; bottom: 14rpx; left: 34rpx; width: 3rpx; height: 24rpx; border-radius: 2rpx; background: var(--primary); }
.avatar-leaf { position: absolute; width: 18rpx; height: 12rpx; border-radius: 0 10rpx 0 10rpx; background: var(--primary); }
.leaf-left { top: 18rpx; left: 20rpx; transform: rotate(-14deg); }
.leaf-right { top: 24rpx; left: 36rpx; transform: scaleX(-1) rotate(-14deg); background: #9DB0A2; }
</style>

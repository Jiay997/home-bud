<script setup lang="ts">
import { ref } from 'vue'

type TabKey = 'home' | 'profiles' | 'records' | 'me'

const props = defineProps<{ active: TabKey }>()

const tabs: { key: TabKey; label: string; url: string }[] = [
  { key: 'home', label: '首页', url: '/pages/index/index' },
  { key: 'profiles', label: '档案', url: '/pages/profiles/index' },
  { key: 'records', label: '记录', url: '/pages/records/index' },
  { key: 'me', label: '我的', url: '/pages/me/index' }
]

const switching = ref(false)

function open(page: TabKey) {
  if (page === props.active || switching.value) return
  const target = tabs.find((tab) => tab.key === page)
  if (!target) return
  switching.value = true
  const release = () => { switching.value = false }
  uni.redirectTo({ url: target.url, fail: release, complete: release })
  // complete 在个别环境下可能不回调，兜底释放重入锁，避免导航永久失效
  setTimeout(release, 800)
}
</script>

<template>
  <view class="tab-safe-area">
    <view class="tab-bar" role="navigation" aria-label="底部导航">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: props.active === tab.key }"
        :aria-current="props.active === tab.key ? 'page' : undefined"
        :aria-label="tab.label"
        @tap="open(tab.key)"
      >
        <view class="tab-icon" :class="`${tab.key}-icon`">
          <view v-if="tab.key === 'home'" class="home-door" />
          <template v-else-if="tab.key === 'records'">
            <view class="record-line" /><view class="record-line" /><view class="record-line" />
          </template>
        </view>
        <text>{{ tab.label }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped>
.tab-safe-area { position: fixed; right: 0; bottom: 0; left: 0; z-index: 50; padding-bottom: env(safe-area-inset-bottom); background: rgba(255, 255, 255, .97); border-top: 1px solid var(--line); }
.tab-bar { display: flex; justify-content: center; gap: 24rpx; height: 112rpx; }
.tab-item { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 8rpx; max-width: 220rpx; margin: 0; padding: 8rpx 0 6rpx; color: var(--ink-3); background: transparent; border: 0; font-size: 22rpx; line-height: 1; }
.tab-item.active { color: var(--primary); }
.tab-item.active > text { font-weight: 650; }
.tab-icon { position: relative; width: 38rpx; height: 34rpx; color: currentColor; }
.home-icon::before { position: absolute; top: 4rpx; left: 7rpx; width: 21rpx; height: 21rpx; border-top: 2rpx solid currentColor; border-left: 2rpx solid currentColor; content: ''; transform: rotate(45deg); }
.home-icon::after { position: absolute; right: 4rpx; bottom: 1rpx; left: 4rpx; height: 18rpx; border: 2rpx solid currentColor; border-top: 0; content: ''; }
.tab-item.active .home-icon::after { background: var(--primary-soft); }
.home-door { position: absolute; z-index: 1; bottom: 1rpx; left: 16rpx; width: 8rpx; height: 13rpx; border: 1rpx solid currentColor; border-bottom: 0; }
.tab-item.active .home-door { background: currentColor; }
.records-icon { display: flex; flex-direction: column; justify-content: space-between; padding: 3rpx 2rpx; box-sizing: border-box; }
.record-line { height: 2rpx; margin-left: 8rpx; background: currentColor; }
.record-line::before { position: absolute; left: 2rpx; width: 3rpx; height: 3rpx; border: 1rpx solid currentColor; content: ''; }
.tab-item.active .record-line::before { background: currentColor; }
.profiles-icon::before { position: absolute; top: 6rpx; left: 6rpx; width: 26rpx; height: 22rpx; border: 2rpx solid currentColor; border-radius: 3rpx; content: ''; }
.profiles-icon::after { position: absolute; top: 13rpx; left: 11rpx; width: 16rpx; height: 8rpx; border-top: 2rpx solid currentColor; border-bottom: 2rpx solid currentColor; content: ''; }
.tab-item.active .profiles-icon::after { background: var(--primary-soft); }
.me-icon::before { position: absolute; top: 2rpx; left: 14rpx; width: 10rpx; height: 10rpx; border: 2rpx solid currentColor; border-radius: 50%; content: ''; }
.tab-item.active .me-icon::before { background: currentColor; }
.me-icon::after { position: absolute; bottom: 2rpx; left: 7rpx; width: 20rpx; height: 10rpx; border: 2rpx solid currentColor; border-bottom: 0; border-radius: 11rpx 11rpx 0 0; content: ''; }
</style>

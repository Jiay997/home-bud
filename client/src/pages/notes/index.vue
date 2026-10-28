<template>
  <view class="notes-page tex">
    <MiniPageHeader title="我的笔记" subtitle="经验心得 · 知识手册" />

    <view class="notes-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />

      <StateSkeleton
        v-else-if="state === 'error'"
        mode="empty"
        :title="errorTitle"
        :copy="errorMessage"
        :action-text="retryCopy"
        @action="reload"
      />

      <StateSkeleton
        v-else-if="!notes.length"
        mode="empty"
        :title="emptyTitle"
        :copy="emptyCopy"
        :action-text="addCopy"
        @action="goCreate"
      />

      <template v-else>
        <view class="note-card">
          <view
            v-for="item in notes"
            :key="item.note_uid"
            class="note-row"
            hover-class="row-pressed"
            @tap="openNote(item)"
          >
            <view class="note-main">
              <text class="note-title">{{ item.title }}</text>
              <text v-if="item.excerpt" class="note-excerpt">{{ item.excerpt }}</text>
              <text class="note-meta">{{ shortTime(item.updated_at) }}</text>
            </view>
            <view class="row-arrow" />
          </view>
        </view>

        <button class="fab-add" hover-class="fab-pressed" @tap="goCreate">{{ addCopy }}</button>
        <MiniComplianceBar />
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { api, type NoteView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const errorTitle = '笔记暂时无法打开'
const retryCopy = '重新加载'
const emptyTitle = '还没有笔记'
const emptyCopy = '把日常的养育心得、技巧整理成册，随时翻看。'
const addCopy = '新建笔记'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const notes = ref<NoteView[]>([])
const loading = ref(false)

function shortTime(value: string | null): string {
  return value ? String(value).slice(0, 10) : ''
}

function openNote(item: NoteView) {
  uni.navigateTo({ url: `/pages/notes/edit?uid=${item.note_uid}` })
}

function goCreate() {
  uni.navigateTo({ url: '/pages/notes/edit' })
}

async function load(showLoading = false) {
  if (showLoading) state.value = 'loading'
  if (loading.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const result = await api.notes()
    notes.value = result.notes || []
    state.value = 'ready'
  } catch (error: any) {
    if (state.value === 'ready') {
      uni.showToast({ title: userFacingMessage(error, refreshFailedCopy), icon: 'none' })
    } else {
      errorMessage.value = userFacingMessage(error, connectFailedCopy)
      state.value = 'error'
    }
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function reload() {
  void load(true)
}

onLoad(() => { void load(true) })
onShow(() => { if (state.value === 'ready') void load() })
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.notes-page { min-height: 100vh; padding-bottom: calc(200rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.notes-body { padding: 24rpx 32rpx 0; }
.row-pressed { opacity: .88; }

.note-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); overflow: hidden; }
.note-row { display: flex; align-items: center; gap: 16rpx; padding: 26rpx; }
.note-row + .note-row { border-top: 1px solid var(--line); }
.note-main { flex: 1; min-width: 0; }
.note-title { display: block; color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.note-excerpt { display: block; margin-top: 6rpx; color: var(--ink-2); font-size: 24rpx; line-height: 1.6; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.note-meta { display: block; margin-top: 8rpx; color: var(--ink-3); font-size: 22rpx; }
.row-arrow { width: 16rpx; height: 16rpx; border-top: 4rpx solid var(--ink-3); border-right: 4rpx solid var(--ink-3); transform: rotate(45deg); flex: none; }

.fab-add { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(48rpx + env(safe-area-inset-bottom)); width: 400rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: var(--primary); color: #FFFFFF; font-size: 30rpx; font-weight: 650; box-shadow: var(--shadow-card); }
.fab-pressed { opacity: .88; }
</style>

<template>
  <view class="health-page tex">
    <MiniPageHeader title="健康档案" subtitle="体检报告与复查提醒" />

    <view class="health-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />

      <StateSkeleton
        v-else-if="state === 'error'"
        mode="empty"
        :title="errorTitle"
        :copy="errorMessage"
        :action-text="retryCopy"
        @action="reload"
      />

      <template v-else>
        <view v-if="dueRecords.length" class="due-card">
          <view class="due-head">
            <view class="due-icon"><view class="due-glyph" /></view>
            <text class="due-title">{{ dueTitle }}</text>
          </view>
          <view v-for="item in dueRecords" :key="item.record_uid" class="due-row" hover-class="row-pressed" @tap="openRecord(item)">
            <view class="due-main">
              <text class="due-name">{{ subjectName(item) }}</text>
              <text class="due-copy">{{ item.title }} · {{ item.next_checkup_date }}</text>
            </view>
            <text class="due-badge" :class="{ 'due-badge-late': item.due_status === 'overdue' }">{{ dueLabel(item) }}</text>
          </view>
        </view>

        <StateSkeleton
          v-if="!records.length"
          mode="empty"
          :title="emptyTitle"
          :copy="emptyCopy"
          :action-text="addCopy"
          @action="goCreate"
        />

        <template v-else>
          <view v-for="group in grouped" :key="group.key" class="subject-group">
            <text class="group-title">{{ group.name }}</text>
            <view class="record-card">
              <view
                v-for="item in group.items"
                :key="item.record_uid"
                class="record-row"
                hover-class="row-pressed"
                @tap="openRecord(item)"
              >
                <view class="record-main">
                  <text class="record-title">{{ item.title }}</text>
                  <text class="record-meta">{{ item.record_date }}<text v-if="item.has_file"> · 报告已存</text></text>
                </view>
                <text v-if="item.due_status === 'overdue' || item.due_status === 'soon'" class="due-badge" :class="{ 'due-badge-late': item.due_status === 'overdue' }">{{ dueLabel(item) }}</text>
                <view class="row-arrow" />
              </view>
            </view>
          </view>
        </template>

        <button class="fab-add" hover-class="fab-pressed" @tap="goCreate">{{ addCopy }}</button>
        <MiniComplianceBar />
      </template>
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
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { api, type HealthRecordView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const errorTitle = '健康档案暂时无法打开'
const retryCopy = '重新加载'
const emptyTitle = '还没有健康记录'
const emptyCopy = '上传体检报告、记下医生建议，复查时间到了会在这里提醒你。'
const addCopy = '新建健康记录'
const dueTitle = '复查提醒'
const childGroupTitle = '孩子的健康记录'
const petGroupTitle = '宠物的健康记录'
const subjectGoneCopy = '原档案已删除'
const badgeTodayCopy = '今天复查'
const badgeOverdueCopy = '复查已到期'
const badgeSoonDays = (days: number) => `还有 ${days} 天复查`
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const records = ref<HealthRecordView[]>([])
const todayRef = ref('')
const nameMap = ref<Record<string, string>>({})
const loading = ref(false)
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

const dueRecords = computed(() =>
  records.value
    .filter((item) => item.due_status === 'overdue' || item.due_status === 'soon')
    .slice(0, 5)
)

const grouped = computed(() => {
  const groups: Array<{ key: string; name: string; items: HealthRecordView[] }> = []
  const childItems = records.value.filter((item) => item.subject_type === 'child')
  const petItems = records.value.filter((item) => item.subject_type === 'pet')
  if (childItems.length) groups.push({ key: 'child', name: childGroupTitle, items: childItems })
  if (petItems.length) groups.push({ key: 'pet', name: petGroupTitle, items: petItems })
  return groups
})

function subjectName(item: HealthRecordView): string {
  return nameMap.value[item.subject_uid] || subjectGoneCopy
}

function dueLabel(item: HealthRecordView): string {
  if (item.due_status === 'overdue') return badgeOverdueCopy
  if (!item.next_checkup_date || !todayRef.value) return ''
  const diff = Math.round(
    (new Date(`${item.next_checkup_date}T00:00:00`).getTime()
      - new Date(`${todayRef.value}T00:00:00`).getTime()) / 86400000
  )
  if (diff <= 0) return badgeTodayCopy
  return badgeSoonDays(diff)
}

function openRecord(item: HealthRecordView) {
  uni.navigateTo({ url: `/pages/health/edit?uid=${item.record_uid}` })
}

function goCreate() {
  uni.navigateTo({ url: '/pages/health/edit' })
}

async function loadProfiles() {
  try {
    const [childrenResult, petsResult] = await Promise.all([
      api.children().catch(() => ({ children: [] })),
      api.pets().catch(() => ({ pets: [] }))
    ])
    const map: Record<string, string> = {}
    for (const child of childrenResult.children || []) {
      if (child.status === 'active') map[child.profile_uid] = child.nickname
    }
    for (const pet of petsResult.pets || []) {
      map[pet.pet_uid] = pet.pet_type === 'cat' ? '猫咪' : '狗狗'
    }
    nameMap.value = map
  } catch (error) {
    // 名字映射失败不阻塞列表展示（回落到“原档案已删除”前不出现，仅少名字）
  }
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
    const [result] = await Promise.all([api.healthRecords(), loadProfiles()])
    records.value = result.records || []
    todayRef.value = result.today || ''
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
.health-page { min-height: 100vh; padding-bottom: calc(200rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.health-body { padding: 24rpx 32rpx 0; }
.row-pressed { opacity: .88; }

.due-card { margin-bottom: 28rpx; padding: 26rpx; background: #FDF3E7; border: 1px solid #F2DFC8; border-radius: var(--r-card); }
.due-head { display: flex; align-items: center; gap: 14rpx; }
.due-icon { width: 44rpx; height: 44rpx; border-radius: 50%; background: #F6E3C8; display: flex; align-items: center; justify-content: center; }
.due-glyph { width: 16rpx; height: 16rpx; border-radius: 50%; background: #C98A3D; }
.due-title { color: #8A5B22; font-size: 28rpx; font-weight: 650; }
.due-row { display: flex; align-items: center; gap: 16rpx; margin-top: 18rpx; }
.due-main { flex: 1; min-width: 0; }
.due-name { display: block; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.due-copy { display: block; margin-top: 2rpx; color: #8A5B22; font-size: 24rpx; }
.due-badge { flex: none; padding: 6rpx 16rpx; border-radius: 999rpx; background: #F6E3C8; color: #8A5B22; font-size: 22rpx; }
.due-badge-late { background: #F7DED8; color: #A2452F; }

.subject-group { margin-bottom: 8rpx; }
.group-title { display: block; margin: 20rpx 4rpx 12rpx; color: var(--ink-3); font-size: 24rpx; }
.record-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); overflow: hidden; }
.record-row { display: flex; align-items: center; gap: 16rpx; min-height: 118rpx; padding: 20rpx 26rpx; }
.record-row + .record-row { border-top: 1px solid var(--line); }
.record-main { flex: 1; min-width: 0; }
.record-title { display: block; color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.record-meta { display: block; margin-top: 4rpx; color: var(--ink-3); font-size: 24rpx; }
.row-arrow { width: 16rpx; height: 16rpx; border-top: 4rpx solid var(--ink-3); border-right: 4rpx solid var(--ink-3); transform: rotate(45deg); flex: none; }

.fab-add { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(48rpx + env(safe-area-inset-bottom)); width: 400rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: var(--primary); color: #FFFFFF; font-size: 30rpx; font-weight: 650; box-shadow: var(--shadow-card); }
.fab-pressed { opacity: .88; }
</style>

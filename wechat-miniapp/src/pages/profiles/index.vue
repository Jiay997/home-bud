<template>
  <view class="profiles-page tex">
    <MiniPageHeader title="家庭档案" />

    <view class="profiles-body">
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
        <view class="segment" role="tablist" aria-label="档案类型">
          <button
            class="segment-item"
            :class="{ active: activeTab === 'child' }"
            :aria-pressed="activeTab === 'child'"
            hover-class="segment-pressed"
            @tap="activeTab = 'child'"
          >孩子 {{ children.length }}/{{ childLimit }}</button>
          <button
            class="segment-item"
            :class="{ active: activeTab === 'pet' }"
            :aria-pressed="activeTab === 'pet'"
            hover-class="segment-pressed"
            @tap="activeTab = 'pet'"
          >宠物 {{ pets.length }}/{{ petLimit }}</button>
        </view>

        <template v-if="activeTab === 'child'">
          <view v-if="!childConsent" class="consent-notice">
            <text class="consent-title">{{ consentNoticeTitle }}</text>
            <text class="consent-copy">{{ consentNoticeCopy }}</text>
            <button class="consent-button" :class="{ disabled: consentBusy }" :disabled="consentBusy" hover-class="pressed" @tap="agreeChildConsent">
              {{ consentBusy ? consentBusyCopy : consentAction }}
            </button>
          </view>

          <template v-if="children.length">
            <view class="card-list">
              <view
                v-for="child in children"
                :key="child.profile_uid"
                class="profile-card"
                :aria-label="child.nickname"
                hover-class="card-pressed"
                @tap="openDetail('child', child.profile_uid)"
              >
                <view class="card-head">
                  <ProfileAvatar kind="child" :url="avatarOf(child.avatar_url)" />
                  <view class="head-main">
                    <view class="name-row">
                      <text class="card-name">{{ child.nickname }}</text>
                      <text v-if="isCurrent('child', child.profile_uid)" class="card-tag tag-current">{{ currentTag }}</text>
                      <text v-else-if="child.status === 'disabled'" class="card-tag tag-muted">{{ revokedTag }}</text>
                    </view>
                    <text class="card-meta">{{ childMeta(child) }}</text>
                  </view>
                </view>
              </view>
            </view>
            <button class="add-button" :class="{ disabled: childAtLimit }" hover-class="pressed" @tap="startAddChild">{{ addChildCopy }}</button>
          </template>
          <StateSkeleton
            v-else
            mode="empty"
            :title="emptyChildTitle"
            :copy="emptyChildCopy"
            :action-text="addChildCopy"
            @action="startAddChild"
          />
        </template>

        <template v-else>
          <template v-if="pets.length">
            <view class="card-list">
              <view
                v-for="pet in pets"
                :key="pet.pet_uid"
                class="profile-card"
                :aria-label="petTypeLabel(pet.pet_type)"
                hover-class="card-pressed"
                @tap="openDetail('pet', pet.pet_uid)"
              >
                <view class="card-head">
                  <ProfileAvatar kind="pet" :url="avatarOf(pet.avatar_url)" />
                  <view class="head-main">
                    <view class="name-row">
                      <text class="card-name">{{ petTypeLabel(pet.pet_type) }}</text>
                      <text v-if="isCurrent('pet', pet.pet_uid)" class="card-tag tag-current">{{ currentTag }}</text>
                    </view>
                    <text class="card-meta">{{ petMeta(pet) }}</text>
                  </view>
                </view>
              </view>
            </view>
            <button class="add-button" :class="{ disabled: petAtLimit }" hover-class="pressed" @tap="startAddPet">{{ addPetCopy }}</button>
          </template>
          <StateSkeleton
            v-else
            mode="empty"
            :title="emptyPetTitle"
            :copy="emptyPetCopy"
            :action-text="addPetCopy"
            @action="startAddPet"
          />
        </template>

        <text class="limits-note">{{ limitsNote }}</text>
        <text class="footer-note">{{ footerNote }}</text>
      </template>
    </view>

    <MiniComplianceBar fixed />
    <MiniTabBar active="profiles" />

    <ProfileFormSheet
      :visible="sheetVisible"
      :kind="sheetKind"
      :profile="null"
      @close="sheetVisible = false"
      @saved="onSheetSaved"
      @stale="onSheetStale"
      @consent-granted="childConsent = true"
    />

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
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { api, mediaUrl, type ChildProfileView, type MeView, type PetProfileView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniTabBar from '../../components/MiniTabBar.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import ProfileAvatar from '../../components/ProfileAvatar.vue'
import ProfileFormSheet from '../../components/ProfileFormSheet.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { createProfileCurrentStore } from '../../services/profile-current'
import { childMeta, petMeta, petTypeLabel } from '../../services/profile-labels'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const errorTitle = '档案暂时无法打开'
const retryCopy = '重新加载'
const consentNoticeTitle = '建立孩子档案前，需要单独同意儿童信息处理'
const consentNoticeCopy = '儿童昵称、出生日期、过敏项会加密保存，仅用于生成养育与共居建议；不建立档案不影响问答与测评。可在「我的 - 个人信息权利中心」随时撤回。'
const consentAction = '同意并继续'
const consentBusyCopy = '正在保存…'
const currentTag = '当前'
const revokedTag = '同意已撤回'
const addChildCopy = '新建孩子档案'
const addPetCopy = '新建宠物档案'
const emptyChildTitle = '还没有孩子档案'
const emptyChildCopy = '建立后，问答与测评会结合月龄与日常信息，建议更贴合。'
const emptyPetTitle = '还没有宠物档案'
const emptyPetCopy = '记录猫狗的类型与日常习惯，饲养与行为问题更有依据。'
const limitsNote = '免费版每类可建 3 个档案，会员可建 10 个'
const footerNote = '观察帮助理解，不给家庭贴标签。'
const limitModalTitleChild = '孩子档案已达上限'
const limitModalTitlePet = '宠物档案已达上限'
const limitModalCopy = '免费版每类最多 3 个档案，开通会员可扩展到 10 个。'
const limitModalConfirm = '了解会员'
const limitModalCancel = '暂不'
const consentModalTitle = '先完成儿童信息同意'
const consentModalCopy = '建立孩子档案前，需要单独同意儿童信息处理。'
const consentModalConfirm = '去同意'

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref('连接失败，请检查网络后重试。')
const activeTab = ref<'child' | 'pet'>('child')
const children = ref<ChildProfileView[]>([])
const pets = ref<PetProfileView[]>([])
const childConsent = ref(true)
const consentBusy = ref(false)
const isMember = ref(false)
const currentKey = ref('')
const loading = ref(false)
const sheetVisible = ref(false)
const sheetKind = ref<'child' | 'pet'>('child')
const currentStore = createProfileCurrentStore({ storage: uni })
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

const childLimit = computed(() => (isMember.value ? 10 : 3))
const petLimit = computed(() => (isMember.value ? 10 : 3))
const childAtLimit = computed(() => children.value.length >= childLimit.value)
const petAtLimit = computed(() => pets.value.length >= petLimit.value)

function applyMembership(meView: MeView | null) {
  if (!meView) {
    isMember.value = false
    return
  }
  const expireMs = meView.member_expire_at ? new Date(meView.member_expire_at).getTime() : 0
  isMember.value = meView.member_status === 'member' && (!expireMs || expireMs > Date.now())
}

function syncCurrentKey() {
  const stored = currentStore.read()
  if (!stored) {
    currentKey.value = ''
    return
  }
  const existsInList = stored.profile_type === 'child'
    ? children.value.some((item) => item.profile_uid === stored.profile_uid)
    : pets.value.some((item) => item.pet_uid === stored.profile_uid)
  if (!existsInList) {
    currentStore.clear()
    currentKey.value = ''
    return
  }
  currentKey.value = `${stored.profile_type}-${stored.profile_uid}`
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
    const [childResult, petResult, consentResult, meResult] = await Promise.allSettled([
      api.children(),
      api.pets(),
      api.myConsents(),
      api.me()
    ])
    if (childResult.status === 'rejected') throw childResult.reason
    if (petResult.status === 'rejected') throw petResult.reason
    children.value = childResult.value.children || []
    pets.value = petResult.value.pets || []
    if (consentResult.status === 'fulfilled') {
      childConsent.value = Boolean(consentResult.value.consents?.child_personal_info)
    }
    applyMembership(meResult.status === 'fulfilled' ? meResult.value : null)
    syncCurrentKey()
    state.value = 'ready'
  } catch (error: any) {
    if (state.value === 'ready') {
      uni.showToast({ title: userFacingMessage(error, '刷新失败，请稍后重试。'), icon: 'none' })
    } else {
      errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
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

async function agreeChildConsent() {
  if (consentBusy.value) return
  consentBusy.value = true
  try {
    await api.agreeChildConsent()
    childConsent.value = true
    uni.showToast({ title: '已记录同意', icon: 'none' })
  } catch (error) {
    uni.showToast({ title: userFacingMessage(error, '同意保存失败，请稍后重试。'), icon: 'none' })
  } finally {
    consentBusy.value = false
  }
}

async function askConsent() {
  const result = await openDialog({
    title: consentModalTitle,
    message: consentModalCopy,
    confirmText: consentModalConfirm
  })
  if (result.confirm) void agreeChildConsent()
}

async function askUpgrade(kind: 'child' | 'pet') {
  const result = await openDialog({
    title: kind === 'child' ? limitModalTitleChild : limitModalTitlePet,
    message: limitModalCopy,
    confirmText: limitModalConfirm,
    cancelText: limitModalCancel
  })
  if (result.confirm) void uni.navigateTo({ url: '/pages/member/index' })
}

function startAddChild() {
  if (!childConsent.value) {
    askConsent()
    return
  }
  if (children.value.length >= childLimit.value) {
    askUpgrade('child')
    return
  }
  sheetKind.value = 'child'
  sheetVisible.value = true
}

function startAddPet() {
  if (pets.value.length >= petLimit.value) {
    askUpgrade('pet')
    return
  }
  sheetKind.value = 'pet'
  sheetVisible.value = true
}

function onSheetSaved() {
  void load()
}

function onSheetStale() {
  void load()
}

function openDetail(kind: 'child' | 'pet', uid: string) {
  uni.navigateTo({ url: `/pages/profile-detail/index?kind=${kind}&uid=${encodeURIComponent(uid)}` })
}

function avatarOf(path: string | null) {
  return path ? mediaUrl(path) : ''
}

function isCurrent(kind: 'child' | 'pet', uid: string) {
  return currentKey.value === `${kind}-${uid}`
}

onShow(() => { void load() })
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.profiles-page { min-height: 100vh; padding-bottom: calc(272rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.profiles-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }
.card-pressed { opacity: .88; }

.segment { display: flex; gap: 16rpx; }
.segment-item { flex: 1; display: inline-flex; align-items: center; justify-content: center; min-height: 76rpx; margin: 0; color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 26rpx; line-height: 1; }
.segment-item.active { color: var(--primary-press); background: var(--primary-soft); border-color: var(--primary); font-weight: 650; }
.segment-pressed { opacity: .8; }

.consent-notice { margin-top: 22rpx; padding: 26rpx 24rpx; background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-inner); }
.consent-title { display: block; color: var(--ink-1); font-size: 26rpx; font-weight: 650; line-height: 1.5; }
.consent-copy { display: block; margin-top: 12rpx; color: var(--ink-2); font-size: 23rpx; line-height: 1.65; }
.consent-button { display: flex; align-items: center; justify-content: center; min-height: 76rpx; margin-top: 22rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 26rpx; font-weight: 650; }
.consent-button.disabled { opacity: .55; }

.card-list { display: flex; flex-direction: column; gap: 20rpx; margin-top: 24rpx; }
.profile-card { padding: 26rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-inner); box-shadow: var(--shadow-card); }
.card-head { display: flex; align-items: center; gap: 20rpx; }
.head-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 8rpx; }
.name-row { display: flex; align-items: center; gap: 14rpx; }
.card-name { overflow: hidden; color: var(--ink-1); font-size: 31rpx; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.card-tag { flex: none; padding: 4rpx 16rpx; border-radius: var(--r-control); font-size: 20rpx; line-height: 1.5; }
.tag-current { color: var(--primary-press); background: var(--primary-soft); border: 1rpx solid var(--primary); }
.tag-muted { color: var(--ink-3); background: var(--surface-warm); border: 1px solid var(--line); }
.card-meta { color: var(--ink-3); font-size: 24rpx; }

.add-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 88rpx; margin-top: 24rpx; color: var(--primary-press); background: var(--surface); border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 27rpx; }
.add-button.disabled { color: var(--ink-3); border-color: var(--line); }

.limits-note { display: block; margin-top: 30rpx; color: var(--ink-3); font-size: 22rpx; text-align: center; }
.footer-note { display: block; padding: 30rpx 0 8rpx; color: var(--ink-3); font-size: 24rpx; text-align: center; }

@media (prefers-reduced-motion: reduce) {
  .segment-item { transition: none; }
}
</style>

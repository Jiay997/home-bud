<template>
  <view class="detail-page tex">
    <MiniPageHeader title="档案详情">
      <template #action>
        <button v-if="state === 'ready' && profile" class="header-edit" aria-label="编辑档案" hover-class="header-pressed" @tap="openEdit">
          <view class="pencil-icon"><view class="pencil-body" /><view class="pencil-tip" /></view>
        </button>
      </template>
    </MiniPageHeader>

    <view class="detail-body">
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
        v-else-if="state === 'missing'"
        mode="empty"
        :title="missingTitle"
        :copy="missingCopy"
        :action-text="missingAction"
        @action="backToList"
      />

      <template v-else-if="profile">
        <view class="hero-card">
          <view class="avatar-wrap" :hover-class="mediaLocked ? 'none' : 'avatar-pressed'" @tap="openAvatarSheet">
            <view class="avatar-ring">
              <ProfileAvatar :kind="kindRef === 'child' ? 'child' : 'pet'" :url="avatarAbsolute" :size="140" :badge="!mediaLocked" />
            </view>
          </view>
          <view class="hero-name-row">
            <text class="hero-name">{{ heroName }}</text>
            <text v-for="tag in heroTags" :key="tag.label" class="hero-tag" :class="tag.tone">{{ tag.label }}</text>
          </view>
          <text class="hero-meta">{{ heroMeta }}</text>
        </view>

        <view v-if="!mediaLocked" class="album-block">
          <view class="album-head">
            <text class="album-title">{{ albumTitleText }}</text>
            <view v-if="photos.length" class="album-more" hover-class="pressed" @tap="goAlbum">
              <text class="album-more-text">{{ viewAllCopy }}</text>
              <view class="chevron" />
            </view>
          </view>
          <scroll-view scroll-x class="album-strip" :show-scrollbar="false">
            <view class="strip-track">
              <view
                v-for="(photo, index) in stripPhotos"
                :key="photo.photo_uid"
                class="strip-tile"
                hover-class="tile-pressed"
                @tap="previewPhoto(index)"
              >
                <image class="strip-image" :src="photoSrc(photo)" mode="aspectFill" @error="onPhotoError(photo)" />
              </view>
              <view v-if="!photosAtLimit" class="strip-add" hover-class="tile-pressed" @tap="quickAddPhotos">
                <view class="plus"><view class="plus-h" /><view class="plus-v" /></view>
                <text class="strip-add-label">{{ addTileCopy }}</text>
              </view>
            </view>
          </scroll-view>
        </view>

        <view class="info-card">
          <view class="info-head">
            <text class="info-title">{{ infoTitle }}</text>
            <view class="info-rule" />
          </view>
          <view class="fact-list">
            <template v-if="kindRef === 'child' && childView">
              <view class="fact-row">
                <text class="fact-label">出生日期</text>
                <view class="fact-main">
                  <text class="fact-value">{{ birthDisplay }}</text>
                </view>
                <button class="eye-button" hover-class="eye-pressed" :aria-label="revealedBirth ? hideBirthLabel : showBirthLabel" @tap="toggleBirth">
                  <view class="eye-icon"><view v-if="!revealedBirth" class="eye-slash" /></view>
                </button>
              </view>
              <view class="fact-row">
                <text class="fact-label">年龄段</text>
                <view class="fact-main"><text class="fact-value">{{ ageBandLabel(childView.age_band) }}</text></view>
              </view>
              <view class="fact-row">
                <text class="fact-label">身高</text>
                <view class="fact-main">
                  <text class="fact-value" :class="{ empty: childView.height_cm === null }">{{ childView.height_cm !== null ? childView.height_cm : emptyCopy }}</text>
                  <text v-if="childView.height_cm !== null" class="fact-unit">厘米</text>
                </view>
              </view>
              <view class="fact-row">
                <text class="fact-label">体重</text>
                <view class="fact-main">
                  <text class="fact-value" :class="{ empty: childView.weight_kg === null }">{{ childView.weight_kg !== null ? childView.weight_kg : emptyCopy }}</text>
                  <text v-if="childView.weight_kg !== null" class="fact-unit">千克</text>
                </view>
              </view>
              <view class="fact-row">
                <text class="fact-label">辅食</text>
                <view class="fact-main">
                  <text class="fact-value" :class="{ empty: childView.solid_food_month === null }">{{ childView.solid_food_month !== null ? childView.solid_food_month : emptyCopy }}</text>
                  <text v-if="childView.solid_food_month !== null" class="fact-unit">月龄起</text>
                </view>
              </view>
              <view class="fact-row">
                <text class="fact-label">早产</text>
                <view class="fact-main"><text class="fact-value">{{ childView.premature_flag ? '是' : '否' }}</text></view>
              </view>
              <view class="fact-row">
                <text class="fact-label">过敏</text>
                <view class="fact-main"><text class="fact-value">{{ childView.allergy.length ? childView.allergy.join('、') : '无' }}</text></view>
              </view>
            </template>

            <template v-else-if="kindRef === 'pet' && petView">
              <view class="fact-row">
                <text class="fact-label">品种</text>
                <view class="fact-main">
                  <text class="fact-value" :class="{ empty: !petView.breed }">{{ petView.breed || emptyCopy }}</text>
                </view>
              </view>
              <view class="fact-row">
                <text class="fact-label">年龄</text>
                <view class="fact-main"><text class="fact-value">{{ petAgeBandLabel(petView.age_band) }}</text></view>
              </view>
              <view class="fact-row">
                <text class="fact-label">体重</text>
                <view class="fact-main">
                  <text class="fact-value" :class="{ empty: petView.weight_kg === null }">{{ petView.weight_kg !== null ? petView.weight_kg : emptyCopy }}</text>
                  <text v-if="petView.weight_kg !== null" class="fact-unit">千克</text>
                </view>
              </view>
              <view class="fact-row">
                <text class="fact-label">主粮</text>
                <view class="fact-main">
                  <text class="fact-value" :class="{ empty: !petView.main_food }">{{ petView.main_food || emptyCopy }}</text>
                </view>
              </view>
              <view class="fact-row">
                <text class="fact-label">绝育</text>
                <view class="fact-main"><text class="fact-value">{{ neuteredShortLabel(petView.neutered_flag) }}</text></view>
              </view>
            </template>
          </view>
        </view>

        <view class="action-area">
          <button v-if="!current" class="secondary-button" hover-class="pressed" @tap="setCurrent">{{ setCurrentCopy }}</button>
          <button class="danger-button" hover-class="pressed" @tap="confirmDelete">{{ deleteCopy }}</button>
        </view>

        <MiniComplianceBar />
      </template>
    </view>

    <MiniActionSheet
      :visible="avatarSheetVisible"
      :title="avatarSheetTitle"
      :items="avatarSheetItems"
      @select="onAvatarSheetSelect"
      @close="avatarSheetVisible = false"
    />

    <ProfileFormSheet
      :visible="sheetVisible"
      :kind="sheetKind"
      :profile="profile"
      @close="sheetVisible = false"
      @saved="onSaved"
      @stale="onStale"
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
import { onLoad, onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { api, mediaUrl, type ChildProfileView, type PetProfileView, type ProfileKind, type ProfilePhotoView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniActionSheet from '../../components/MiniActionSheet.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import ProfileAvatar from '../../components/ProfileAvatar.vue'
import ProfileFormSheet from '../../components/ProfileFormSheet.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { createProfileCurrentStore } from '../../services/profile-current'
import { createProfileMediaService } from '../../services/profile-media'
import { ageBandLabel, childMeta, maskBirth, neuteredShortLabel, petAgeBandLabel, petMeta, petTypeLabel } from '../../services/profile-labels'
import { isRemoteUrl } from '../../services/media-image'
import { mediaImages } from '../../services/use-media-image'
import { decodeRouteValue } from '../../services/route'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const errorTitle = '档案暂时无法打开'
const retryCopy = '重新加载'
const missingTitle = '档案不存在或已删除'
const missingCopy = '可能已在其他设备删除，返回档案列表看看。'
const missingAction = '返回档案列表'
const currentTag = '当前'
const revokedTag = '同意已撤回'
const viewAllCopy = '查看全部'
const addTileCopy = '添加'
const infoTitle = '档案信息'
const emptyCopy = '未填写'
const avatarSheetTitle = '设置头像'
const avatarPickAlbumCopy = '从相册选择'
const avatarPickCameraCopy = '拍照'
const avatarViewCopy = '查看大图'
const avatarRemoveCopy = '移除头像'
const avatarRemoveConfirmTitle = '移除头像'
const avatarRemoveConfirmCopy = '移除后档案将显示默认图标，可随时重新设置。'
const avatarRemoveConfirmAction = '移除'
const avatarRemovedCopy = '已移除头像'
const avatarRemoveFailedCopy = '移除失败，请稍后重试。'
const mediaLockedCopy = '儿童信息同意已撤回，重新同意后可管理头像与相册'
const setCurrentCopy = '设为当前观察对象'
const setCurrentDoneCopy = '已设为当前观察对象'
const setCurrentFailedCopy = '设置失败，请稍后重试。'
const deleteCopy = '删除档案'
const deleteChildCopy = '删除后档案不再展示，关联问答记录不再可见（合规留档数据不可删除）。请输入昵称确认。'
const deletePetCopy = '删除后档案不再展示，关联问答记录保留历史引用。'
const mismatchCopy = '昵称不一致，未删除'
const deletedCopy = '档案已删除'
const deleteFailedCopy = '删除失败，请稍后重试。'
const staleCopy = '档案已在其他设备更新，已为你刷新'
const refreshFailedCopy = '刷新失败，请稍后重试。'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const showBirthLabel = '显示出生日期'
const hideBirthLabel = '隐藏出生日期'
const photoUnitCopy = '张'
// 详情缩略条只展示最近 8 张，全量在相册页
const STRIP_PHOTO_LIMIT = 8

const kindRef = ref<'' | 'child' | 'pet'>('')
const uid = ref('')
const state = ref<'loading' | 'error' | 'missing' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const childView = ref<ChildProfileView | null>(null)
const petView = ref<PetProfileView | null>(null)
const photos = ref<ProfilePhotoView[]>([])
const photoLimit = ref(30)
const mediaLocked = ref(false)
const current = ref(false)
const revealedBirth = ref(false)
const sheetVisible = ref(false)
const avatarSheetVisible = ref(false)
const loading = ref(false)
const currentStore = createProfileCurrentStore({ storage: uni })
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()
const media = createProfileMediaService({ runtime: uni, upload: api })

const profile = computed<ChildProfileView | PetProfileView | null>(() =>
  kindRef.value === 'child' ? childView.value : kindRef.value === 'pet' ? petView.value : null
)
const mediaKind = computed<ProfileKind>(() => (kindRef.value === 'pet' ? 'pets' : 'children'))
const sheetKind = computed<'child' | 'pet'>(() => (kindRef.value === 'pet' ? 'pet' : 'child'))
const birthDisplay = computed(() => {
  const item = childView.value
  if (!item) return ''
  return revealedBirth.value ? item.birth_date : maskBirth(item.birth_date)
})
const heroName = computed(() => {
  if (kindRef.value === 'child') return childView.value?.nickname || ''
  return petView.value ? petTypeLabel(petView.value.pet_type) : ''
})
const heroMeta = computed(() => {
  if (kindRef.value === 'child') return childView.value ? childMeta(childView.value) : ''
  return petView.value ? petMeta(petView.value) : ''
})
const heroTags = computed(() => {
  const tags: Array<{ label: string; tone: string }> = []
  if (current.value) tags.push({ label: currentTag, tone: 'tag-current' })
  else if (kindRef.value === 'child' && childView.value?.status === 'disabled') tags.push({ label: revokedTag, tone: 'tag-muted' })
  return tags
})
const avatarAbsolute = computed(() => {
  const value = profile.value?.avatar_url
  return value ? mediaUrl(value) : ''
})
const albumTitleText = computed(() =>
  photos.value.length ? `相册 · ${photos.value.length} ${photoUnitCopy}` : '相册'
)
const stripPhotos = computed(() => photos.value.slice(0, STRIP_PHOTO_LIMIT))
const photosAtLimit = computed(() => photos.value.length >= photoLimit.value)
// 真机直连 http 图片失败时经 downloadFile 落到本地临时文件后重渲染
const photoSrcs = ref<Record<string, string>>({})
function photoSrc(photo: ProfilePhotoView): string {
  const url = mediaUrl(photo.url)
  return photoSrcs.value[url] || url
}
function onPhotoError(photo: ProfilePhotoView) {
  const url = mediaUrl(photo.url)
  if (!url || !isRemoteUrl(url)) return
  if (photoSrcs.value[url] && photoSrcs.value[url] !== url) return
  void mediaImages
    .resolve(url)
    .then((path) => { photoSrcs.value = { ...photoSrcs.value, [url]: path } })
    .catch(() => undefined)
}
const avatarSheetItems = computed(() => {
  const items = [avatarPickAlbumCopy, avatarPickCameraCopy]
  if (avatarAbsolute.value) items.push(avatarViewCopy, avatarRemoveCopy)
  return items
})

async function loadPhotos() {
  if (kindRef.value === 'child' && childView.value?.status === 'disabled') {
    mediaLocked.value = true
    photos.value = []
    return
  }
  try {
    const result = await api.profilePhotos(mediaKind.value, uid.value)
    mediaLocked.value = false
    photos.value = result.photos || []
    photoLimit.value = result.limit || photoLimit.value
  } catch (error: any) {
    // 撤回同意后孩子档案媒体为 1302：媒体区隐藏并保留数据（停止展示与使用）
    if (error?.code === 1302) {
      mediaLocked.value = true
      photos.value = []
    }
  }
}

async function load(showLoading = false) {
  if (showLoading) state.value = 'loading'
  if (loading.value) return
  if (!kindRef.value || !uid.value) {
    state.value = 'missing'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    if (kindRef.value === 'child') {
      const result = await api.children()
      childView.value = result.children.find((item) => item.profile_uid === uid.value) || null
      petView.value = null
    } else {
      const result = await api.pets()
      petView.value = result.pets.find((item) => item.pet_uid === uid.value) || null
      childView.value = null
    }
    if (!profile.value) {
      state.value = 'missing'
      return
    }
    const stored = currentStore.read()
    current.value = Boolean(stored && stored.profile_type === kindRef.value && stored.profile_uid === uid.value)
    await loadPhotos()
    state.value = 'ready'
  } catch (error: any) {
    if (state.value === 'ready' && profile.value) {
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

function backToList() {
  uni.navigateBack({ delta: 1, fail: () => uni.reLaunch({ url: '/pages/profiles/index' }) })
}

function toggleBirth() {
  revealedBirth.value = !revealedBirth.value
}

function openEdit() {
  if (!profile.value) return
  sheetVisible.value = true
}

function onSaved(view: ChildProfileView | PetProfileView) {
  if (kindRef.value === 'child') childView.value = view as ChildProfileView
  else petView.value = view as PetProfileView
  void load()
}

function onStale() {
  uni.showToast({ title: staleCopy, icon: 'none' })
  void load()
}

function openAvatarSheet() {
  if (mediaLocked.value) {
    uni.showToast({ title: mediaLockedCopy, icon: 'none' })
    return
  }
  avatarSheetVisible.value = true
}

function applyAvatar(url: string) {
  if (kindRef.value === 'child' && childView.value) childView.value.avatar_url = url
  if (kindRef.value === 'pet' && petView.value) petView.value.avatar_url = url
}

function previewAvatar() {
  if (!avatarAbsolute.value) return
  void mediaImages.preferLocal(avatarAbsolute.value).then((url) => {
    uni.previewImage({ urls: [url] })
  })
}

async function removeAvatar() {
  const result = await openDialog({
    title: avatarRemoveConfirmTitle,
    message: avatarRemoveConfirmCopy,
    confirmText: avatarRemoveConfirmAction,
    danger: true
  })
  if (!result.confirm) return
  try {
    await api.removeProfileAvatar(mediaKind.value, uid.value)
    applyAvatar('')
    uni.showToast({ title: avatarRemovedCopy, icon: 'none' })
  } catch (error) {
    uni.showToast({ title: userFacingMessage(error, avatarRemoveFailedCopy), icon: 'none' })
  }
}

async function onAvatarSheetSelect(index: number) {
  avatarSheetVisible.value = false
  if (index === 0 || index === 1) {
    if (!profile.value) return
    const result = await media.changeAvatar(mediaKind.value, uid.value, index === 0 ? 'album' : 'camera')
    if (result.status === 'updated') applyAvatar(result.url)
    return
  }
  if (index === 2) {
    previewAvatar()
    return
  }
  if (index === 3) void removeAvatar()
}

function previewPhoto(index: number) {
  const urls = photos.value.map((photo) => mediaUrl(photo.url))
  if (!urls.length) return
  // 预览走本地化优先：真机直连 http 失败的图片在预览里同样加载不出
  void Promise.all(urls.map((url) => mediaImages.preferLocal(url))).then((ready) => {
    uni.previewImage({ urls: ready, current: ready[index] })
  })
}

function goAlbum() {
  uni.navigateTo({
    url: `/pages/profile-album/index?kind=${kindRef.value}&uid=${encodeURIComponent(uid.value)}&name=${encodeURIComponent(heroName.value)}`
  })
}

async function quickAddPhotos() {
  if (!profile.value) return
  const remaining = photoLimit.value - photos.value.length
  const result = await media.addPhotos(mediaKind.value, uid.value, remaining)
  if (result.added > 0) await loadPhotos()
}

async function setCurrent() {
  if (!profile.value || !kindRef.value) return
  try {
    await api.setCurrentProfile({ profile_type: kindRef.value, profile_uid: uid.value })
    currentStore.write({ profile_type: kindRef.value, profile_uid: uid.value })
    current.value = true
    uni.showToast({ title: setCurrentDoneCopy, icon: 'none' })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, setCurrentFailedCopy), icon: 'none' })
  }
}

function afterDelete(deletedUid: string) {
  const stored = currentStore.read()
  if (stored && stored.profile_uid === deletedUid) currentStore.clear()
  uni.showToast({ title: deletedCopy, icon: 'none' })
  backToList()
}

async function performDeleteChild(item: ChildProfileView) {
  try {
    await api.deleteChild(item.profile_uid, { mode: 'purge_all', confirm_nickname: item.nickname })
    afterDelete(item.profile_uid)
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, deleteFailedCopy), icon: 'none' })
  }
}

async function performDeletePet(item: PetProfileView) {
  try {
    await api.deletePet(item.pet_uid)
    afterDelete(item.pet_uid)
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, deleteFailedCopy), icon: 'none' })
  }
}

async function confirmDelete() {
  if (kindRef.value === 'child') {
    const item = childView.value
    if (!item) return
    const result = await openDialog({
      title: '删除孩子档案',
      message: `${deleteChildCopy}「${item.nickname}」`,
      confirmText: '删除',
      danger: true,
      input: { placeholder: `输入「${item.nickname}」`, match: item.nickname }
    })
    if (!result.confirm) return
    if (result.value.trim() !== item.nickname) {
      uni.showToast({ title: mismatchCopy, icon: 'none' })
      return
    }
    void performDeleteChild(item)
    return
  }
  const item = petView.value
  if (!item) return
  const result = await openDialog({
    title: '删除宠物档案',
    message: deletePetCopy,
    confirmText: '删除',
    danger: true
  })
  if (result.confirm) void performDeletePet(item)
}

onLoad((query) => {
  const kind = String(query?.kind || '')
  kindRef.value = kind === 'child' || kind === 'pet' ? kind : ''
  uid.value = decodeRouteValue(query?.uid)
})
// 首载由 onShow 触发（onLoad 后紧随 onShow，只发一次）；从相册页返回时自动刷新缩略条
onShow(() => {
  if (uid.value) void load()
})
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.detail-page { min-height: 100vh; padding-bottom: calc(48rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.detail-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }
.tile-pressed { opacity: .88; }

.header-edit { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; flex: none; margin: 0 -8px 0 4px; padding: 0; color: var(--ink-1); background: transparent; border: 0; }
.header-pressed { opacity: .6; }
.pencil-icon { position: relative; width: 34rpx; height: 34rpx; transform: rotate(-45deg); }
.pencil-body { position: absolute; top: 12rpx; left: 2rpx; width: 22rpx; height: 10rpx; background: var(--ink-1); border-radius: 2rpx; }
.pencil-tip { position: absolute; top: 12rpx; left: 24rpx; width: 0; height: 0; border-top: 5rpx solid transparent; border-bottom: 5rpx solid transparent; border-left: 8rpx solid var(--ink-1); }

.hero-card { display: flex; flex-direction: column; align-items: center; padding: 40rpx 28rpx 34rpx; background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.avatar-wrap { display: flex; }
.avatar-pressed { opacity: .85; }
.avatar-ring { padding: 6rpx; background: var(--surface); border-radius: 50%; }
.hero-name-row { display: flex; align-items: center; gap: 14rpx; max-width: 100%; margin-top: 24rpx; }
.hero-name { overflow: hidden; color: var(--ink-1); font-size: 38rpx; font-weight: 650; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.hero-tag { flex: none; padding: 4rpx 16rpx; border-radius: var(--r-control); font-size: 20rpx; line-height: 1.5; }
.tag-current { color: var(--primary-press); background: var(--primary-soft); border: 1rpx solid var(--primary); }
.tag-muted { color: var(--ink-3); background: var(--surface); border: 1px solid var(--line); }
.hero-meta { margin-top: 12rpx; color: var(--ink-3); font-size: 25rpx; }

.album-block { margin-top: 34rpx; }
.album-head { display: flex; align-items: center; justify-content: space-between; padding: 0 4rpx; }
.album-title { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.album-more { display: flex; align-items: center; gap: 8rpx; padding: 8rpx 0 8rpx 16rpx; }
.album-more-text { color: var(--ink-3); font-size: 24rpx; }
.chevron { width: 12rpx; height: 12rpx; border-top: 2rpx solid var(--ink-3); border-right: 2rpx solid var(--ink-3); transform: rotate(45deg); }
.album-strip { margin-top: 20rpx; white-space: nowrap; }
.strip-track { display: inline-flex; gap: 16rpx; }
.strip-tile { overflow: hidden; width: 150rpx; height: 150rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-inner); box-sizing: border-box; }
.strip-image { display: block; width: 100%; height: 100%; }
.strip-add { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10rpx; width: 150rpx; height: 150rpx; background: var(--surface-warm); border: 1rpx dashed var(--line-warm); border-radius: var(--r-inner); box-sizing: border-box; }
.strip-add-label { color: var(--ink-3); font-size: 22rpx; line-height: 1; }
.plus { position: relative; width: 40rpx; height: 40rpx; }
.plus-h { position: absolute; top: 19rpx; left: 6rpx; width: 28rpx; height: 2rpx; background: var(--ink-3); }
.plus-v { position: absolute; top: 6rpx; left: 19rpx; width: 2rpx; height: 28rpx; background: var(--ink-3); }

.info-card { margin-top: 34rpx; padding: 30rpx 28rpx 16rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); }
.info-head { display: flex; align-items: center; gap: 20rpx; }
.info-title { flex: none; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.info-rule { flex: 1; height: 1rpx; background: var(--line); }
.fact-list { margin-top: 8rpx; }
.fact-row { display: flex; align-items: center; min-height: 92rpx; padding: 16rpx 0; box-sizing: border-box; }
.fact-row + .fact-row { border-top: 1rpx solid var(--line); }
.fact-label { flex: none; width: 170rpx; color: var(--ink-2); font-size: 24rpx; }
.fact-main { display: flex; flex: 1; flex-wrap: wrap; align-items: baseline; gap: 6rpx; min-width: 0; }
.fact-value { color: var(--ink-1); font-size: 28rpx; font-weight: 650; line-height: 1.4; }
.fact-value.empty { color: var(--ink-3); font-weight: 500; }
.fact-unit { color: var(--ink-3); font-size: 22rpx; }
.eye-button { display: flex; flex: none; align-items: center; justify-content: center; width: 64rpx; height: 64rpx; margin: 0 0 0 16rpx; padding: 0; background: var(--primary-soft); border: 0; border-radius: 50%; }
.eye-button::after { border: 0; }
.eye-pressed { opacity: .68; }
.eye-icon { position: relative; width: 32rpx; height: 32rpx; }
.eye-icon::before { position: absolute; top: 8rpx; left: 2rpx; width: 28rpx; height: 16rpx; border: 2.4rpx solid var(--primary); border-radius: 50%; box-sizing: border-box; content: ''; }
.eye-icon::after { position: absolute; top: 12rpx; left: 12rpx; width: 8rpx; height: 8rpx; background: var(--primary); border-radius: 50%; content: ''; }
.eye-slash { position: absolute; top: 1rpx; left: 15rpx; width: 2.4rpx; height: 30rpx; background: var(--primary); border-radius: 2rpx; transform: rotate(45deg); }

.action-area { display: flex; flex-direction: column; align-items: stretch; gap: 18rpx; margin-top: 44rpx; }
.secondary-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 88rpx; margin: 0; color: var(--primary-press); background: var(--surface); border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 27rpx; }
.danger-button { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 76rpx; margin: 20rpx 0 0; color: var(--danger); background: transparent; border: 0; font-size: 26rpx; }

@media (prefers-reduced-motion: reduce) {
  .chevron { transition: none; }
}
</style>

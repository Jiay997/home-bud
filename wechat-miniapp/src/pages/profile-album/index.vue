<template>
  <view class="album-page tex">
    <MiniPageHeader title="相册" :subtitle="nameRef" />

    <view class="album-body">
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
        v-else-if="!photos.length"
        mode="empty"
        :title="emptyTitle"
        :copy="emptyCopy"
        :action-text="addPhotosCopy"
        @action="addPhotos"
      />

      <template v-else>
        <view class="overview">
          <view class="count-line">
            <text class="count-now">{{ photos.length }}</text>
            <text class="count-rest"> / {{ photoLimit }}</text>
          </view>
          <text class="hint">{{ longPressHint }}</text>
        </view>

        <view class="photo-grid">
          <view
            v-for="(photo, index) in photos"
            :key="photo.photo_uid"
            class="photo-tile"
            hover-class="tile-pressed"
            @tap="previewPhoto(index)"
            @longpress="openManage(photo)"
          >
            <image class="photo-image" :src="photoSrc(photo)" mode="aspectFill" @error="onPhotoError(photo)" />
          </view>
          <view v-if="!photosAtLimit" class="photo-add" hover-class="tile-pressed" @tap="addPhotos">
            <view class="plus"><view class="plus-h" /><view class="plus-v" /></view>
            <text class="photo-add-label">{{ addCopy }}</text>
          </view>
        </view>

        <text v-if="photosAtLimit" class="full-note">{{ fullNote }}</text>
        <MiniComplianceBar />
      </template>
    </view>

    <MiniActionSheet
      :visible="manageVisible"
      :items="manageItems"
      @select="onManageSelect"
      @close="manageVisible = false"
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
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import { api, mediaUrl, type ProfileKind, type ProfilePhotoView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniActionSheet from '../../components/MiniActionSheet.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { isRemoteUrl } from '../../services/media-image'
import { mediaImages } from '../../services/use-media-image'
import { createProfileMediaService } from '../../services/profile-media'
import { decodeRouteValue } from '../../services/route'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const errorTitle = '相册暂时无法打开'
const retryCopy = '重新加载'
const emptyTitle = '还没有照片'
const emptyCopy = '把宝宝或毛孩子的日常留在档案里，翻看起来也更有温度。'
const addPhotosCopy = '添加照片'
const addCopy = '添加'
const longPressHint = '长按照片可预览或删除'
const fullNote = '相册已满，删除后可继续添加'
const previewItemCopy = '预览'
const deleteItemCopy = '删除'
const deletePhotoTitle = '删除照片'
const deletePhotoCopy = '删除后无法恢复，确定删除这张照片吗？'
const deletePhotoAction = '删除'
const photoDeletedCopy = '照片已删除'
const deleteFailedCopy = '删除失败，请稍后重试。'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const refreshFailedCopy = '刷新失败，请稍后重试。'

const kindRef = ref<'' | 'child' | 'pet'>('')
const uid = ref('')
const nameRef = ref('')
const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref(connectFailedCopy)
const photos = ref<ProfilePhotoView[]>([])
const photoLimit = ref(30)
const manageVisible = ref(false)
const managePhoto = ref<ProfilePhotoView | null>(null)
const busy = ref(false)
const loading = ref(false)
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()
const media = createProfileMediaService({ runtime: uni, upload: api })

const mediaKind = computed<ProfileKind>(() => (kindRef.value === 'pet' ? 'pets' : 'children'))
const photosAtLimit = computed(() => photos.value.length >= photoLimit.value)
const manageItems = [previewItemCopy, deleteItemCopy]

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
  void mediaImages.resolve(url)
    .then((path) => { photoSrcs.value = { ...photoSrcs.value, [url]: path } })
    .catch(() => undefined)
}

async function load(showLoading = false) {
  if (showLoading) state.value = 'loading'
  if (loading.value) return
  if (!kindRef.value || !uid.value) {
    state.value = 'error'
    errorMessage.value = '档案信息缺失，请返回重新进入。'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const result = await api.profilePhotos(mediaKind.value, uid.value)
    photos.value = result.photos || []
    photoLimit.value = result.limit || photoLimit.value
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

function previewPhoto(index: number) {
  const urls = photos.value.map((photo) => mediaUrl(photo.url))
  if (!urls.length) return
  // 真机上 previewImage 对 http 直链同样可能失败，先本地化再预览
  void Promise.all(urls.map((url) => mediaImages.preferLocal(url))).then((ready) => {
    uni.previewImage({ urls: ready, current: ready[index] })
  })
}

function openManage(photo: ProfilePhotoView) {
  if (busy.value) return
  managePhoto.value = photo
  manageVisible.value = true
}

async function addPhotos() {
  if (busy.value) return
  busy.value = true
  try {
    const result = await media.addPhotos(mediaKind.value, uid.value, photoLimit.value - photos.value.length)
    if (result.added > 0) await load()
  } finally {
    busy.value = false
  }
}

async function removePhoto(photo: ProfilePhotoView) {
  const result = await openDialog({
    title: deletePhotoTitle,
    message: deletePhotoCopy,
    confirmText: deletePhotoAction,
    danger: true
  })
  if (!result.confirm) return
  busy.value = true
  try {
    await api.deleteProfilePhoto(mediaKind.value, uid.value, photo.photo_uid)
    uni.showToast({ title: photoDeletedCopy, icon: 'none' })
    await load()
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, deleteFailedCopy), icon: 'none' })
  } finally {
    busy.value = false
  }
}

function onManageSelect(index: number) {
  manageVisible.value = false
  const photo = managePhoto.value
  if (!photo) return
  if (index === 0) {
    const position = photos.value.findIndex((item) => item.photo_uid === photo.photo_uid)
    previewPhoto(position >= 0 ? position : 0)
    return
  }
  if (index === 1) void removePhoto(photo)
}

onLoad((query) => {
  const kind = String(query?.kind || '')
  kindRef.value = kind === 'child' || kind === 'pet' ? kind : ''
  uid.value = decodeRouteValue(query?.uid)
  nameRef.value = decodeRouteValue(query?.name)
  void load()
})
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.album-page { min-height: 100vh; padding-bottom: calc(48rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.album-body { padding: 24rpx 32rpx 0; }
.tile-pressed { opacity: .88; }

.overview { display: flex; align-items: baseline; justify-content: space-between; padding: 2rpx 4rpx 0; }
.count-now { color: var(--ink-1); font-size: 34rpx; font-weight: 650; }
.count-rest { color: var(--ink-3); font-size: 24rpx; }
.hint { color: var(--ink-3); font-size: 22rpx; }

.photo-grid { display: flex; flex-wrap: wrap; gap: 16rpx; margin-top: 24rpx; }
.photo-tile { overflow: hidden; width: 218rpx; height: 218rpx; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-inner); box-sizing: border-box; }
.photo-image { display: block; width: 100%; height: 100%; }
.photo-add { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10rpx; width: 218rpx; height: 218rpx; background: var(--surface-warm); border: 1rpx dashed var(--line-warm); border-radius: var(--r-inner); box-sizing: border-box; }
.photo-add-label { color: var(--ink-3); font-size: 22rpx; line-height: 1; }
.plus { position: relative; width: 40rpx; height: 40rpx; }
.plus-h { position: absolute; top: 19rpx; left: 6rpx; width: 28rpx; height: 2rpx; background: var(--ink-3); }
.plus-v { position: absolute; top: 6rpx; left: 19rpx; width: 2rpx; height: 28rpx; background: var(--ink-3); }

.full-note { display: block; margin-top: 24rpx; color: var(--ink-3); font-size: 24rpx; text-align: center; }
</style>

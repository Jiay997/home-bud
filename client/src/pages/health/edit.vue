<template>
  <view class="hedit-page tex">
    <MiniPageHeader :title="pageTitle" :subtitle="mode === 'edit' ? subjectNameText : ''" />

    <view class="hedit-body">
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
        <view class="form-card">
          <view v-if="mode === 'create'" class="form-row">
            <text class="form-label">{{ subjectLabel }}</text>
            <picker class="form-picker" :range="subjectOptionsText" @change="onSubjectChange">
              <view class="picker-value" :class="{ 'picker-empty': !subjectUid }">
                <text>{{ subjectText || subjectPlaceholder }}</text>
                <view class="picker-arrow" />
              </view>
            </picker>
          </view>

          <view class="form-row">
            <text class="form-label">{{ dateLabel }}</text>
            <picker class="form-picker" mode="date" :value="form.recordDate" @change="onRecordDateChange">
              <view class="picker-value"><text>{{ form.recordDate || datePlaceholder }}</text><view class="picker-arrow" /></view>
            </picker>
          </view>

          <view class="form-row">
            <text class="form-label">{{ titleLabel }}</text>
            <input v-model="form.title" class="form-input" :maxlength="64" :placeholder="titlePlaceholder" />
          </view>

          <view class="form-col">
            <text class="form-label">{{ notesLabel }}</text>
            <textarea
              v-model="form.notes"
              class="form-textarea"
              :maxlength="500"
              :cursor-spacing="120"
              :placeholder="notesPlaceholder"
            />
          </view>
        </view>

        <view class="form-card">
          <view class="form-row">
            <text class="form-label">{{ dueLabel }}</text>
            <view class="due-picker-row">
              <picker class="form-picker" mode="date" :value="form.nextCheckupDate" @change="onDueDateChange">
                <view class="picker-value" :class="{ 'picker-empty': !form.nextCheckupDate }">
                  <text>{{ form.nextCheckupDate || duePlaceholder }}</text>
                  <view class="picker-arrow" />
                </view>
              </picker>
              <text v-if="form.nextCheckupDate" class="due-clear" @tap="clearDueDate">{{ clearCopy }}</text>
            </view>
          </view>
          <view class="form-col">
            <text class="form-label">{{ dueNoteLabel }}</text>
            <input v-model="form.nextCheckupNote" class="form-input" :maxlength="200" :placeholder="dueNotePlaceholder" />
          </view>
          <text class="due-hint">{{ dueHint }}</text>
        </view>

        <view v-if="mode === 'edit'" class="form-card">
          <view class="file-head">
            <text class="form-label">{{ fileLabel }}</text>
            <text class="file-hint">{{ fileHint }}</text>
          </view>
          <view v-if="record && record.has_file" class="file-row">
            <text class="file-name">{{ record.file_name || fileFallbackName }}</text>
            <view class="file-actions">
              <text class="file-action" @tap="openReportFile">{{ fileOpenCopy }}</text>
              <text class="file-action" @tap="pickReportFile">{{ fileReplaceCopy }}</text>
            </view>
          </view>
          <view v-else class="file-empty" hover-class="row-pressed" @tap="pickReportFile">
            <view class="plus"><view class="plus-h" /><view class="plus-v" /></view>
            <text class="file-empty-copy">{{ fileUploadCopy }}</text>
          </view>
        </view>

        <button class="primary-btn" :class="{ disabled: saving }" :disabled="saving" hover-class="btn-pressed" @tap="save">
          {{ mode === 'create' ? createCopy : saveCopy }}
        </button>
        <button v-if="mode === 'edit'" class="danger-btn" :class="{ disabled: saving }" :disabled="saving" hover-class="btn-pressed" @tap="removeRecord">
          {{ deleteCopy }}
        </button>
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
import { onLoad } from '@dcloudio/uni-app'
import { api, mediaUrl, type HealthRecordView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { isRemoteUrl } from '../../services/media-image'
import { mediaImages } from '../../services/use-media-image'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const createTitle = '新建健康记录'
const editTitle = '健康记录'
const errorTitle = '记录暂时无法打开'
const retryCopy = '重新加载'
const subjectLabel = '档案对象'
const subjectPlaceholder = '选择孩子或宠物'
const dateLabel = '体检日期'
const datePlaceholder = '选择日期'
const titleLabel = '记录标题'
const titlePlaceholder = '如：2026 年秋季体检'
const notesLabel = '医生建议 / 备注'
const notesPlaceholder = '可记录体检结论、医生叮嘱等（选填）'
const dueLabel = '下次复查日期'
const duePlaceholder = '选择日期（选填，用于提醒）'
const dueNoteLabel = '复查项目说明'
const dueNotePlaceholder = '如：复查血常规、视力（选填）'
const dueHint = '填写复查日期后，档案页会提前 7 天提醒你。'
const fileLabel = '体检报告'
const fileHint = '支持 PDF/JPG/PNG，PDF ≤10MB'
const fileUploadCopy = '上传报告文件'
const fileReplaceCopy = '替换'
const fileOpenCopy = '预览'
const fileFallbackName = '体检报告文件'
const clearCopy = '清除'
const createCopy = '保存记录'
const saveCopy = '保存修改'
const deleteCopy = '删除记录'
const deleteTitle = '删除健康记录'
const deleteCopyDialog = '删除后无法恢复，确定删除这条记录吗？'
const savedCopy = '已保存'
const deletedCopy = '已删除'
const pickFailedCopy = '未选择文件'
const connectFailedCopy = '连接失败，请检查网络后重试。'
const catName = '猫咪'
const dogName = '狗狗'

const uid = ref('')
const mode = ref<'create' | 'edit'>('create')
const state = ref<'loading' | 'error' | 'ready'>('ready')
const errorMessage = ref(connectFailedCopy)
const record = ref<HealthRecordView | null>(null)
const saving = ref(false)
const subjects = ref<Array<{ type: 'child' | 'pet'; uid: string; name: string }>>([])
const subjectUid = ref('')
const form = ref({
  recordDate: '',
  title: '',
  notes: '',
  nextCheckupDate: '',
  nextCheckupNote: ''
})
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

const pageTitle = computed(() => (mode.value === 'create' ? createTitle : editTitle))
const subjectNameText = computed(() => {
  if (!record.value) return ''
  return subjects.value.find((s) => s.uid === record.value?.subject_uid)?.name || ''
})
const subjectText = computed(() => subjects.value.find((s) => s.uid === subjectUid.value)?.name || '')
const subjectOptionsText = computed(() => subjects.value.map((s) => s.name))

async function loadSubjects() {
  const [childrenResult, petsResult] = await Promise.all([
    api.children().catch(() => ({ children: [] })),
    api.pets().catch(() => ({ pets: [] }))
  ])
  const list: Array<{ type: 'child' | 'pet'; uid: string; name: string }> = []
  for (const child of childrenResult.children || []) {
    if (child.status === 'active') list.push({ type: 'child', uid: child.profile_uid, name: child.nickname })
  }
  for (const pet of petsResult.pets || []) {
    list.push({ type: 'pet', uid: pet.pet_uid, name: pet.pet_type === 'cat' ? catName : dogName })
  }
  subjects.value = list
}

async function loadRecord(showLoading = false) {
  if (!uid.value) {
    mode.value = 'create'
    state.value = 'ready'
    return
  }
  mode.value = 'edit'
  if (showLoading) state.value = 'loading'
  try {
    const result = await api.healthRecord(uid.value)
    record.value = result.record
    form.value = {
      recordDate: result.record.record_date,
      title: result.record.title,
      notes: result.record.notes || '',
      nextCheckupDate: result.record.next_checkup_date || '',
      nextCheckupNote: result.record.next_checkup_note || ''
    }
    state.value = 'ready'
  } catch (error: any) {
    errorMessage.value = userFacingMessage(error, connectFailedCopy)
    state.value = 'error'
  }
}

function onSubjectChange(event: any) {
  const index = Number(event?.detail?.value)
  subjectUid.value = subjects.value[index]?.uid || ''
}
function onRecordDateChange(event: any) {
  form.value.recordDate = String(event?.detail?.value || '')
}
function onDueDateChange(event: any) {
  form.value.nextCheckupDate = String(event?.detail?.value || '')
}
function clearDueDate() {
  form.value.nextCheckupDate = ''
}

function validate(): string {
  if (mode.value === 'create' && !subjectUid.value) return '请选择档案对象'
  if (!form.value.recordDate) return '请选择体检日期'
  if (!form.value.title.trim()) return '请填写记录标题'
  return ''
}

async function save() {
  if (saving.value) return
  const problem = validate()
  if (problem) {
    uni.showToast({ title: problem, icon: 'none' })
    return
  }
  saving.value = true
  try {
    const payload = {
      record_date: form.value.recordDate,
      title: form.value.title.trim(),
      notes: form.value.notes.trim() || undefined,
      next_checkup_date: form.value.nextCheckupDate || undefined,
      next_checkup_note: form.value.nextCheckupNote.trim() || undefined
    }
    if (mode.value === 'create') {
      const subject = subjects.value.find((s) => s.uid === subjectUid.value)
      const result = await api.createHealthRecord({
        subject_type: subject!.type,
        subject_uid: subject!.uid,
        ...payload
      })
      uid.value = result.record.record_uid
      await loadRecord()
      uni.showToast({ title: savedCopy, icon: 'none' })
    } else {
      await api.updateHealthRecord(uid.value, payload)
      await loadRecord()
      uni.showToast({ title: savedCopy, icon: 'none' })
    }
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, connectFailedCopy), icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function removeRecord() {
  if (saving.value) return
  const result = await openDialog({
    title: deleteTitle,
    message: deleteCopyDialog,
    confirmText: deleteCopy,
    danger: true
  })
  if (!result.confirm) return
  saving.value = true
  try {
    await api.deleteHealthRecord(uid.value)
    uni.showToast({ title: deletedCopy, icon: 'none' })
    setTimeout(() => uni.navigateBack(), 400)
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, connectFailedCopy), icon: 'none' })
  } finally {
    saving.value = false
  }
}

function pickReportFile() {
  if (saving.value || !uid.value) return
  // #ifdef MP-WEIXIN
  // 小程序：从聊天记录选择文件（体检报告 PDF/JPG/PNG）
  uni.chooseMessageFile({
    count: 1,
    type: 'file',
    extension: ['.pdf', '.jpg', '.jpeg', '.png'],
    success: (result) => {
      const file = (result.tempFiles || [])[0]
      if (!file) {
        uni.showToast({ title: pickFailedCopy, icon: 'none' })
        return
      }
      void uploadReport(file.path)
    },
    fail: () => uni.showToast({ title: pickFailedCopy, icon: 'none' })
  })
  // #endif
  // #ifdef H5
  // H5：uni.chooseMessageFile 未实现，改用原生 input[type=file] 选择本地文件
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf,.jpg,.jpeg,.png'
  input.onchange = () => {
    const file = (input.files || [])[0]
    if (!file) {
      uni.showToast({ title: pickFailedCopy, icon: 'none' })
      return
    }
    void uploadReport(file)
  }
  input.click()
  // #endif
}

async function uploadReport(filePath: string | Blob) {
  saving.value = true
  uni.showLoading({ title: '正在上传…', mask: true })
  try {
    await api.uploadHealthRecordFile(uid.value, filePath)
    await loadRecord()
    uni.hideLoading()
    uni.showToast({ title: savedCopy, icon: 'none' })
  } catch (error: any) {
    uni.hideLoading()
    uni.showToast({ title: userFacingMessage(error, connectFailedCopy), icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function openReportFile() {
  const url = mediaUrl(record.value?.file_url)
  if (!url) return
  if (/\.pdf$/i.test(url)) {
    // #ifdef MP-WEIXIN
    uni.showLoading({ title: '正在打开…', mask: true })
    uni.downloadFile({
      url,
      success: (result) => {
        uni.hideLoading()
        if (result.statusCode !== 200) {
          uni.showToast({ title: connectFailedCopy, icon: 'none' })
          return
        }
        uni.openDocument({ filePath: result.tempFilePath, showMenu: true })
      },
      fail: () => {
        uni.hideLoading()
        uni.showToast({ title: connectFailedCopy, icon: 'none' })
      }
    })
    return
    // #endif
    // #ifdef H5
    // H5：无 openDocument 能力，交浏览器直接打开 PDF（同源地址由 nginx 反代提供）
    window.open(url, '_blank')
    return
    // #endif
  }
  // 图片：真机 http 直链可能失败，先本地化再预览（与相册同口径）
  const target = isRemoteUrl(url) ? await mediaImages.preferLocal(url).catch(() => url) : url
  uni.previewImage({ urls: [target] })
}

function reload() {
  void loadRecord(true)
}

onLoad((query) => {
  uid.value = String(query?.uid || '')
  void (async () => {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    try {
      await loadSubjects()
    } catch (error) {
      // 对象列表拉取失败不阻塞编辑（编辑态不需要）
    }
    await loadRecord(true)
  })()
})
</script>

<style scoped>
.hedit-page { min-height: 100vh; padding-bottom: calc(64rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.hedit-body { padding: 24rpx 32rpx 0; }
.row-pressed { opacity: .88; }

.form-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); padding: 10rpx 26rpx; margin-bottom: 24rpx; }
.form-row { display: flex; align-items: center; gap: 20rpx; min-height: 110rpx; }
.form-row + .form-row, .form-row + .form-col, .form-col + .form-row { border-top: 1px solid var(--line); }
.form-col { padding: 20rpx 0; }
.form-label { width: 190rpx; flex: none; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.form-col .form-label { display: block; width: auto; margin-bottom: 12rpx; }
.form-picker { flex: 1; min-width: 0; }
.picker-value { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; color: var(--ink-1); font-size: 28rpx; }
.picker-empty { color: var(--ink-3); }
.picker-arrow { width: 14rpx; height: 14rpx; border-top: 4rpx solid var(--ink-3); border-right: 4rpx solid var(--ink-3); transform: rotate(135deg); flex: none; }
.form-input { flex: 1; min-width: 0; color: var(--ink-1); font-size: 28rpx; }
.form-textarea { width: 100%; box-sizing: border-box; min-height: 140rpx; color: var(--ink-1); font-size: 28rpx; line-height: 1.6; }
.due-picker-row { flex: 1; display: flex; align-items: center; gap: 20rpx; min-width: 0; }
.due-clear { flex: none; color: var(--primary); font-size: 26rpx; }
.due-hint { display: block; padding: 0 0 20rpx; color: var(--ink-3); font-size: 22rpx; }

.file-head { display: flex; align-items: center; justify-content: space-between; padding: 20rpx 0 6rpx; }
.file-hint { color: var(--ink-3); font-size: 22rpx; }
.file-row { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 16rpx 0 20rpx; }
.file-name { flex: 1; min-width: 0; color: var(--ink-2); font-size: 26rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-actions { display: flex; gap: 28rpx; flex: none; }
.file-action { color: var(--primary); font-size: 26rpx; font-weight: 650; }
.file-empty { display: flex; align-items: center; justify-content: center; gap: 14rpx; margin: 10rpx 0 24rpx; padding: 40rpx 0; background: var(--surface-warm); border: 1rpx dashed var(--line-warm); border-radius: var(--r-inner); }
.file-empty-copy { color: var(--ink-3); font-size: 26rpx; }
.plus { position: relative; width: 36rpx; height: 36rpx; }
.plus-h { position: absolute; top: 17rpx; left: 4rpx; width: 28rpx; height: 2rpx; background: var(--ink-3); }
.plus-v { position: absolute; top: 4rpx; left: 17rpx; width: 2rpx; height: 28rpx; background: var(--ink-3); }

.primary-btn { margin-top: 36rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: var(--primary); color: #FFFFFF; font-size: 30rpx; font-weight: 650; }
.danger-btn { margin-top: 20rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: transparent; color: #A2452F; border: 1px solid #E5C4BA; font-size: 30rpx; }
.btn-pressed { opacity: .88; }
.disabled { opacity: .55; }
</style>

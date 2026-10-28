<template>
  <view class="nedit-page tex">
    <MiniPageHeader :title="pageTitle" />

    <view class="nedit-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />

      <StateSkeleton
        v-else-if="state === 'error'"
        mode="empty"
        :title="errorTitle"
        :copy="errorMessage"
        :action-text="retryCopy"
        @action="reload"
      />

      <!-- 查看态 -->
      <template v-else-if="mode === 'view' && note">
        <view class="view-card">
          <text class="view-title">{{ note.title }}</text>
          <text class="view-meta">{{ shortTime(note.updated_at) }}</text>
          <view class="view-divider" />
          <MiniMarkdown :content="note.content || ''" />
        </view>

        <button class="primary-btn" :class="{ disabled: saving }" :disabled="saving" hover-class="btn-pressed" @tap="startEdit">
          {{ editCopy }}
        </button>
        <button class="danger-btn" :class="{ disabled: saving }" :disabled="saving" hover-class="btn-pressed" @tap="removeNote">
          {{ deleteCopy }}
        </button>
        <MiniComplianceBar />
      </template>

      <!-- 编辑态（新建 / 修改共用） -->
      <template v-else>
        <view class="form-card">
          <view class="form-col">
            <text class="form-label">{{ titleLabel }}</text>
            <input
              v-model="form.title"
              class="form-input"
              :maxlength="60"
              :placeholder="titlePlaceholder"
            />
          </view>
          <view class="form-col">
            <text class="form-label">{{ contentLabel }}</text>
            <textarea
              v-model="form.content"
              class="form-textarea"
              :maxlength="20000"
              :cursor-spacing="120"
              :placeholder="contentPlaceholder"
            />
            <text class="form-hint">{{ markdownHint }}</text>
          </view>
        </view>

        <button class="primary-btn" :class="{ disabled: saving }" :disabled="saving" hover-class="btn-pressed" @tap="save">
          {{ saveCopy }}
        </button>
        <button v-if="mode === 'edit'" class="ghost-btn" :disabled="saving" hover-class="btn-pressed" @tap="cancelEdit">
          {{ cancelCopy }}
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
import { api, type NoteView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import MiniMarkdown from '../../components/MiniMarkdown.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useDialog } from '../../services/dialog'
import { ensureBaseConsent } from '../../services/session'
import { userFacingMessage } from '../../services/user-message'

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const createTitle = '新建笔记'
const detailTitle = '笔记详情'
const editTitle = '编辑笔记'
const errorTitle = '笔记暂时无法打开'
const retryCopy = '重新加载'
const titleLabel = '标题'
const titlePlaceholder = '给这条笔记起个名字'
const contentLabel = '正文'
const contentPlaceholder = '记录你的经验心得，支持 Markdown 排版…'
const markdownHint = '支持「## 标题」「- 列表」「**加粗**」「| 表格 |」等写法'
const saveCopy = '保存'
const editCopy = '编辑'
const cancelCopy = '取消'
const deleteCopy = '删除笔记'
const deleteTitle = '删除笔记'
const deleteDialogCopy = '删除后无法恢复，确定删除这条笔记吗？'
const savedCopy = '已保存'
const deletedCopy = '已删除'
const titleEmptyCopy = '请填写标题'
const contentEmptyCopy = '请填写正文'
const conflictTitle = '内容已更新'
const conflictCopy = '这条笔记已在其他地方被修改，加载最新内容会覆盖当前编辑，是否继续？'
const conflictConfirmCopy = '加载最新'
const connectFailedCopy = '连接失败，请检查网络后重试。'

const uid = ref('')
const mode = ref<'view' | 'edit'>('edit')
const state = ref<'loading' | 'error' | 'ready'>('ready')
const errorMessage = ref(connectFailedCopy)
const note = ref<NoteView | null>(null)
const saving = ref(false)
const form = ref({ title: '', content: '' })
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

const pageTitle = computed(() => {
  if (!uid.value) return createTitle
  return mode.value === 'view' ? detailTitle : editTitle
})

function shortTime(value: string | null): string {
  return value ? String(value).slice(0, 10) : ''
}

async function loadNote(showLoading = false) {
  if (!uid.value) {
    mode.value = 'edit'
    state.value = 'ready'
    return
  }
  if (showLoading) state.value = 'loading'
  try {
    const result = await api.note(uid.value)
    note.value = result.note
    form.value = { title: result.note.title, content: result.note.content || '' }
    mode.value = 'view'
    state.value = 'ready'
  } catch (error: any) {
    errorMessage.value = userFacingMessage(error, connectFailedCopy)
    state.value = 'error'
  }
}

function reload() {
  void loadNote(true)
}

function startEdit() {
  if (!note.value) return
  form.value = { title: note.value.title, content: note.value.content || '' }
  mode.value = 'edit'
}

function cancelEdit() {
  if (!note.value) {
    uni.navigateBack()
    return
  }
  form.value = { title: note.value.title, content: note.value.content || '' }
  mode.value = 'view'
}

async function save() {
  if (saving.value) return
  const title = form.value.title.trim()
  const content = form.value.content
  if (!title) {
    uni.showToast({ title: titleEmptyCopy, icon: 'none' })
    return
  }
  if (!content.trim()) {
    uni.showToast({ title: contentEmptyCopy, icon: 'none' })
    return
  }
  saving.value = true
  try {
    if (!uid.value) {
      const result = await api.createNote({ title, content })
      // redirectTo 替换当前页，避免返回栈里残留一个无 uid 的编辑页
      uni.redirectTo({ url: `/pages/notes/edit?uid=${result.note.note_uid}` })
      return
    }
    const result = await api.updateNote(uid.value, { title, content, version: note.value!.version })
    note.value = result.note
    uni.showToast({ title: savedCopy, icon: 'none' })
    mode.value = 'view'
  } catch (error: any) {
    if (error?.code === 1003) {
      await openDialog({
        title: conflictTitle,
        message: conflictCopy,
        confirmText: conflictConfirmCopy,
        cancelText: cancelCopy
      })
      await loadNote()
    } else {
      uni.showToast({ title: userFacingMessage(error, connectFailedCopy), icon: 'none' })
    }
  } finally {
    saving.value = false
  }
}

async function removeNote() {
  if (saving.value) return
  const result = await openDialog({
    title: deleteTitle,
    message: deleteDialogCopy,
    confirmText: deleteCopy,
    danger: true
  })
  if (!result.confirm) return
  saving.value = true
  try {
    await api.deleteNote(uid.value)
    uni.showToast({ title: deletedCopy, icon: 'none' })
    setTimeout(() => uni.navigateBack(), 400)
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, connectFailedCopy), icon: 'none' })
  } finally {
    saving.value = false
  }
}

onLoad((query) => {
  uid.value = String(query?.uid || '')
  void (async () => {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    await loadNote(true)
  })()
})
</script>

<style scoped>
.nedit-page { min-height: 100vh; padding-bottom: calc(64rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.nedit-body { padding: 24rpx 32rpx 0; }
.btn-pressed { opacity: .88; }

.view-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); padding: 32rpx 28rpx; }
.view-title { display: block; color: var(--ink-1); font-size: 34rpx; font-weight: 700; line-height: 1.5; }
.view-meta { display: block; margin-top: 10rpx; color: var(--ink-3); font-size: 22rpx; }
.view-divider { height: 1px; background: var(--line); margin: 24rpx 0; }

.form-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); padding: 24rpx 26rpx; }
.form-card + .form-card { margin-top: 24rpx; }
.form-col + .form-col { margin-top: 28rpx; }
.form-label { display: block; color: var(--ink-1); font-size: 28rpx; font-weight: 650; margin-bottom: 12rpx; }
.form-input { width: 100%; box-sizing: border-box; height: 76rpx; padding: 0 20rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); color: var(--ink-1); font-size: 28rpx; }
.form-textarea { width: 100%; box-sizing: border-box; min-height: 520rpx; padding: 20rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); color: var(--ink-1); font-size: 28rpx; line-height: 1.7; }
.form-hint { display: block; margin-top: 12rpx; color: var(--ink-3); font-size: 22rpx; }

.primary-btn { margin-top: 36rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: var(--primary); color: #FFFFFF; font-size: 30rpx; font-weight: 650; }
.ghost-btn { margin-top: 20rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: transparent; color: var(--ink-2); border: 1px solid var(--line); font-size: 30rpx; }
.danger-btn { margin-top: 20rpx; height: 92rpx; line-height: 92rpx; border-radius: 999rpx; background: transparent; color: #A2452F; border: 1px solid #E5C4BA; font-size: 30rpx; }
.disabled { opacity: .55; }
</style>

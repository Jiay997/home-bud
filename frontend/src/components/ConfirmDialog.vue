<!--
  ConfirmDialog 危险操作二次确认
  列出影响 + 必填原因输入（可选开启）+ 危险色确认按钮。
  通过 v-model 控制显隐；confirm 事件在通过校验后触发。
-->
<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="88%"
    :append-to-body="true"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="impact">
      <p class="impact-title">此操作将产生以下影响：</p>
      <ul class="impact-list">
        <li v-for="(item, i) in impacts" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div v-if="needReason" class="reason">
      <label class="reason-label">{{ reasonLabel || '请输入操作原因（必填）' }}</label>
      <el-input
        v-model="reason"
        type="textarea"
        :rows="2"
        maxlength="200"
        :placeholder="reasonPlaceholder"
      />
    </div>
    <template #footer>
      <div class="dlg-actions">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button
          type="danger"
          :disabled="needReason && !reason.trim()"
          :loading="loading"
          @click="onConfirm"
        >
          {{ confirmText || '确认执行' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

/**
 * 组件属性
 * @param modelValue 显隐（v-model）
 * @param title 弹窗标题
 * @param impacts 影响说明列表
 * @param needReason 是否要求填写原因
 * @param reasonLabel 原因输入标签
 * @param reasonPlaceholder 原因输入占位
 * @param confirmText 确认按钮文案
 */
const props = defineProps<{
  modelValue: boolean
  title: string
  impacts: string[]
  needReason?: boolean
  reasonLabel?: string
  reasonPlaceholder?: string
  confirmText?: string
}>()

/** 确认时触发（携带原因） */
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm', reason: string): void
}>()

/** 确认按钮 loading（由父组件完成后关闭弹窗） */
const loading = ref(false)
/** 操作原因输入 */
const reason = ref('')

/**
 * 弹窗打开时重置原因输入
 */
watch(
  () => props.modelValue,
  (v) => {
    if (v) reason.value = ''
  }
)

/**
 * 确认回调：通过必填校验后向父组件抛 confirm
 */
function onConfirm(): void {
  if (props.needReason && !reason.value.trim()) return
  emit('confirm', reason.value.trim())
}

/** 暴露 loading 供父组件控制按钮态 */
defineExpose({ setLoading: (v: boolean) => (loading.value = v) })
</script>

<style lang="scss" scoped>
.impact {
  background: var(--danger-soft);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
  margin-bottom: var(--sp-4);
}

.impact-title {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--danger);
  margin-bottom: var(--sp-2);
}

.impact-list {
  padding-left: 18px;
  font-size: var(--fs-sub);
  color: var(--ink-2);
  line-height: 1.7;
}

.reason-label {
  display: block;
  font-size: var(--fs-sub);
  color: var(--ink-2);
  margin-bottom: var(--sp-2);
}

.dlg-actions {
  display: flex;
  gap: var(--sp-3);

  .el-button {
    flex: 1;
  }
}
</style>

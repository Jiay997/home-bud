<!--
  AppealPanel 申诉面板
  ≤500 字申诉说明 + 提交 + 受理编号展示（APL-xxx）。
-->
<template>
  <div class="appeal">
    <label class="appeal-label">申诉说明（选填补充情境，≤500 字）</label>
    <textarea
      v-model="note"
      class="appeal-textarea"
      rows="5"
      maxlength="500"
      placeholder="补充可能被误判的上下文，例如当时的问题原文…"
    />
    <div class="appeal-foot">
      <span class="numeric">{{ note.length }}/500</span>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        提交申诉
      </el-button>
    </div>
    <div v-if="result" class="appeal-result">
      <p class="appeal-no numeric">受理编号：{{ result.appeal_no }}</p>
      <p class="appeal-sla">承诺 24 小时内人工复核，结果将通过记录页通知</p>
    </div>
    <p v-if="error" class="appeal-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { createAppeal } from '@/api/client'
import { newRequestId } from '@/api/request'

/**
 * 组件属性
 * @param sessionUid 被拦截的会话 uid
 */
const props = defineProps<{ sessionUid: string }>()

/** 申诉说明文本 */
const note = ref('')
/** 提交中 */
const submitting = ref(false)
/** 提交结果 {appeal_no, sla_due_at} */
const result = ref<{ appeal_no: string; sla_due_at: string } | null>(null)
/** 提交错误信息 */
const error = ref('')

/** 是否可提交（sessionUid 必须存在） */
const canSubmit = computed(() => !!props.sessionUid)

/**
 * 提交申诉
 * @throws 网络失败时内联展示错误（幂等 id 每次新生成）
 */
async function submit(): Promise<void> {
  submitting.value = true
  error.value = ''
  try {
    result.value = await createAppeal({
      session_uid: props.sessionUid,
      appeal_note: note.value.trim()
    })
  } catch (e: any) {
    error.value = e?.message || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

// newRequestId 供将来重试复用（当前提交无幂等要求，保留工具引用说明）
void newRequestId
</script>

<style lang="scss" scoped>
.appeal-label {
  display: block;
  font-size: var(--fs-sub);
  color: var(--ink-2);
  margin-bottom: var(--sp-2);
}

.appeal-textarea {
  width: 100%;
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-1);
  font-family: inherit;
  font-size: var(--fs-sub);
  resize: vertical;

  &:focus {
    outline: none;
    border-color: var(--accent);
  }
}

.appeal-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--sp-3);

  span {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }
}

.appeal-result {
  margin-top: var(--sp-4);
  padding: var(--sp-4);
  background: var(--accent-soft);
  border-radius: var(--radius-ctl);

  .appeal-no {
    font-weight: 600;
    color: var(--accent);
  }

  .appeal-sla {
    margin-top: var(--sp-1, 4px);
    font-size: var(--fs-caption);
    color: var(--ink-2);
  }
}

.appeal-error {
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--danger);
}
</style>

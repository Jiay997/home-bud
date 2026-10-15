<!--
  ConflictNote 冲突标注条
  warn-soft 底：两个智能体结论不一致时提示用户甄别。
-->
<template>
  <div class="conflict">
    <svg viewBox="0 0 24 24" class="conflict-icon" fill="none" aria-hidden="true">
      <path
        d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <p class="conflict-text">{{ text || '育儿与家庭安全两个视角给出的建议存在差异，请结合实际情况甄别采纳。' }}</p>
  </div>
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param text 冲突说明文案（可选，默认通用提示）
 */
defineProps<{ text?: string }>()
</script>

<style lang="scss" scoped>
.conflict {
  display: flex;
  gap: var(--sp-3);
  background: var(--warn-soft);
  border: 1px solid var(--warn);
  border-radius: var(--radius-face);
  padding: var(--sp-4) var(--sp-6);
  margin-bottom: var(--sp-4);
}

.conflict-icon {
  width: 20px;
  height: 20px;
  color: var(--warn);
  flex-shrink: 0;
  margin-top: 2px;
}

.conflict-text {
  font-size: var(--fs-sub);
  color: var(--ink-1);
  line-height: 1.5;
}
</style>

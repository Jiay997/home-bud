<!--
  SafetyBanner 安全提示条
  accent-soft 实底，安全分节置顶使用；不可折叠。
-->
<template>
  <div class="safety">
    <svg viewBox="0 0 24 24" class="safety-icon" fill="none" aria-hidden="true">
      <path
        d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Zm0 5v5m0 2.5v.5"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <div class="safety-body">
      <p class="safety-title">{{ title }}</p>
      <p v-if="text" class="safety-text">{{ text }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param title 提示主文案（如"以下建议涉及孩子安全，请优先阅读"）
 * @param text 补充说明（可选）
 */
defineProps<{ title: string; text?: string }>()
</script>

<style lang="scss" scoped>
.safety {
  display: flex;
  gap: var(--sp-3);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-face);
  padding: var(--sp-4) var(--sp-6);
  margin-bottom: var(--sp-4);
}

.safety-icon {
  width: 20px;
  height: 20px;
  color: var(--accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.safety-title {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
}

.safety-text {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.5;
}
</style>

<!--
  AiDisclaimer AI 标识 + 免责常驻条
  不可关闭，caption 字号；合规要求所有 AI 内容页常驻。
-->
<template>
  <div class="disclaimer">
    <span class="ai-badge">AI</span>
    <p class="disclaimer-text">
      <strong>{{ aiLabel }}</strong>
      <span>{{ disclaimer }}</span>
    </p>
  </div>
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param aiLabel AI 标识文案（如"内容由 AI 生成"）
 * @param disclaimer 免责说明（如"仅供参考，不能替代专业医疗或法律意见"）
 */
defineProps<{ aiLabel: string; disclaimer: string }>()
</script>

<style lang="scss" scoped>
.disclaimer {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-3) 0;
}

.ai-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 4px;
  padding: 0 4px;
  line-height: 16px;
}

.disclaimer-text {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.5;

  strong {
    color: var(--ink-2);
    margin-right: 4px;
    font-weight: 600;
  }
}
</style>

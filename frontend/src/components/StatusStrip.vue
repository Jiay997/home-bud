<!--
  StatusStrip 状态条
  类型：readonly 只读 / degraded 降级 / auditing 审核中 / offline 离线。
-->
<template>
  <div class="strip" :class="type">
    <span class="strip-dot" />
    <span class="strip-text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param type 状态类型
 * @param text 状态文案
 */
defineProps<{
  type: 'readonly' | 'degraded' | 'auditing' | 'offline'
  text: string
}>()
</script>

<style lang="scss" scoped>
.strip {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-4);
  border-radius: var(--radius-ctl);
  font-size: var(--fs-caption);
  margin-bottom: var(--sp-4);

  .strip-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  &.readonly {
    background: var(--surface-2);
    color: var(--ink-3);
    .strip-dot { background: var(--ink-3); }
  }

  &.degraded {
    background: var(--warn-soft);
    color: var(--warn);
    .strip-dot { background: var(--warn); }
  }

  &.auditing {
    background: var(--accent-soft);
    color: var(--accent);
    .strip-dot { background: var(--accent); }
  }

  &.offline {
    background: var(--danger-soft);
    color: var(--danger);
    .strip-dot { background: var(--danger); }
  }
}
</style>

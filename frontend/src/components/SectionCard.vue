<!--
  SectionCard 回答卡分节
  普通分节为 surface 白底；pinned（安全置顶）为 accent-soft 实底且不可折叠。
  props: title / pinned? / immutable?
-->
<template>
  <section class="sec" :class="{ pinned }">
    <header class="sec-head">
      <svg v-if="pinned" viewBox="0 0 24 24" class="sec-pin" fill="none" aria-hidden="true">
        <path
          d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linejoin="round"
        />
      </svg>
      <h3 class="sec-title">{{ title }}</h3>
      <span v-if="immutable" class="sec-immutable">不可编辑</span>
    </header>
    <div class="sec-body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param title 分节标题
 * @param pinned 安全置顶（accent-soft 实底）
 * @param immutable 内容不可编辑标记
 */
defineProps<{
  title: string
  pinned?: boolean
  immutable?: boolean
}>()
</script>

<style lang="scss" scoped>
.sec {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  margin-bottom: var(--sp-4);
  box-shadow: var(--shadow-e1);

  &.pinned {
    background: var(--accent-soft);
    border-color: var(--accent-line);
  }
}

.sec-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}

.sec-pin {
  width: 18px;
  height: 18px;
  color: var(--accent);
  flex-shrink: 0;
}

.sec-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
  flex: 1;
}

.sec-immutable {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  flex-shrink: 0;
}

.sec-body {
  font-size: var(--fs-body);
  line-height: 1.6;
  color: var(--ink-2);
  word-break: break-word;
}
</style>

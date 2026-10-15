<!--
  LockedBlock 付费墙锁定块
  surface-2 下沉地面 + 锁图标 + 标题 + 淡出摘要 + 解锁入口 slot；会员无专属色。
-->
<template>
  <div class="locked">
    <div class="locked-head">
      <svg class="locked-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M6.8 10.5V7.8a5.2 5.2 0 0 1 10.4 0v2.7M5.6 10.5h12.8c.9 0 1.6.7 1.6 1.6v7.3c0 .9-.7 1.6-1.6 1.6H5.6c-.9 0-1.6-.7-1.6-1.6v-7.3c0-.9.7-1.6 1.6-1.6Zm6.4 4v2.4"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <h4 class="locked-title">{{ title }}</h4>
    </div>
    <p class="locked-summary fade-mask">{{ summary }}</p>
    <div class="locked-cta">
      <slot name="action">
        <button class="unlock-btn" @click="$emit('unlock')">解锁查看</button>
      </slot>
    </div>
    <p class="locked-note">以下内容为会员权益，开通后可完整查看</p>
  </div>
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param title 锁定区标题
 * @param summary 淡出摘要预览（截断由调用方传入）
 */
defineProps<{ title: string; summary?: string }>()

/** 点击解锁入口时触发 */
defineEmits<{ (e: 'unlock'): void }>()
</script>

<style lang="scss" scoped>
.locked {
  background: var(--surface-2);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  margin-top: var(--sp-4);
}

.locked-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.locked-ico {
  flex: none;
  width: 18px;
  height: 18px;
  color: var(--ink-2);
}

.locked-title {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--ink-1);
}

.locked-summary {
  margin-top: var(--sp-2);
  font-size: var(--fs-sub);
  color: var(--ink-2);
  line-height: 1.6;
  max-height: 3.2em;
  overflow: hidden;
}

.locked-cta {
  margin-top: var(--sp-4);
}

.unlock-btn {
  width: 100%;
  padding: 10px 0;
  border: 1px solid var(--accent);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--accent);
  font-size: var(--fs-sub);
  font-weight: 600;
  cursor: pointer;

  &:active {
    background: var(--accent-soft);
  }
}

.locked-note {
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--ink-3);
  text-align: center;
}
</style>

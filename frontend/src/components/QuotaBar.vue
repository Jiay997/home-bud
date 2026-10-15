<!--
  QuotaBar 额度条
  5 段刻度展示剩余额度；用尽时转橙（warn）并显示图标与文字说明。
-->
<template>
  <div class="quota">
    <div class="quota-head">
      <span class="quota-label">今日额度</span>
      <span v-if="unlimited" class="quota-num numeric">不限次</span>
      <span v-else class="quota-num numeric">{{ used }}/{{ limit }}</span>
    </div>
    <div v-if="!unlimited" class="quota-segments" :class="{ exhausted: isExhausted }">
      <span
        v-for="i in Math.max(limit, 1)"
        :key="i"
        class="seg"
        :class="{ filled: i <= used, over: isExhausted && i <= used }"
      />
    </div>
    <p v-if="!unlimited && isExhausted" class="quota-exhausted">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      今日免费额度已用完，明日 0 点重置；开通会员不限次
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 组件属性
 * @param used 已使用次数
 * @param limit 上限（默认 5）
 * @param unlimited 会员不限次（true 时隐藏刻度并展示"不限次"）
 */
const props = withDefaults(
  defineProps<{ used: number; limit?: number; unlimited?: boolean }>(),
  { limit: 5, unlimited: false }
)

/** 额度是否用尽 */
const isExhausted = computed(() => props.used >= props.limit)
</script>

<style lang="scss" scoped>
.quota-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--sp-2);

  .quota-label {
    font-size: var(--fs-sub);
    color: var(--ink-2);
  }

  .quota-num {
    font-size: var(--fs-sub);
    color: var(--ink-1);
    font-weight: 600;
  }
}

.quota-segments {
  display: flex;
  gap: var(--sp-2);

  .seg {
    flex: 1;
    height: 10px;
    border-radius: var(--radius-pill);
    background: var(--surface-2);

    &.filled {
      background: var(--accent);
    }

    &.over {
      background: var(--warn);
    }
  }

  &.exhausted .seg.filled {
    background: var(--warn);
  }
}

.quota-exhausted {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
  font-size: var(--fs-caption);
  color: var(--warn);

  svg {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }
}
</style>

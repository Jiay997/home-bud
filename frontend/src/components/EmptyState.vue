<!--
  EmptyState 空态
  职责：说明「这里为什么是空的」+「做完什么就会满」+ 一个主操作。
  DESIGN.md 要求每个空态都教界面，因此除主文案外提供 hint（可获得什么）
  与 variant（按场景换插图，避免六处复用同一张图）。
-->
<template>
  <div class="empty">
    <!-- 插图按场景切换；统一 96 网格 / 单一描边；线稿用 --art-line（≥3:1 专用下限） -->
    <svg viewBox="0 0 96 96" class="empty-art" fill="none" role="img" :aria-label="artLabel">
      <!-- 问答：对话气泡 -->
      <template v-if="variant === 'qa'">
        <rect x="14" y="20" width="68" height="44" rx="10" stroke="var(--art-line)" stroke-width="2" />
        <path d="M32 64v12l14-12" stroke="var(--art-line)" stroke-width="2" stroke-linejoin="round" />
        <circle cx="38" cy="42" r="3" fill="var(--art-line-accent)" />
        <circle cx="50" cy="42" r="3" fill="var(--art-line-accent)" />
        <circle cx="62" cy="42" r="3" fill="var(--art-line-accent)" />
      </template>

      <!-- 档案：卡片 + 刻度（量具语汇） -->
      <template v-else-if="variant === 'profile'">
        <rect x="20" y="18" width="56" height="60" rx="10" stroke="var(--art-line)" stroke-width="2" />
        <circle cx="48" cy="38" r="9" stroke="var(--art-line-accent)" stroke-width="2" />
        <path d="M36 62c2.4-6 6.6-9 12-9s9.6 3 12 9" stroke="var(--art-line-accent)" stroke-width="2" stroke-linecap="round" />
        <path d="M26 30h6M26 42h4M26 54h4" stroke="var(--art-line)" stroke-width="2" stroke-linecap="round" />
      </template>

      <!-- 记录：时间轴 + 刻度 -->
      <template v-else-if="variant === 'record'">
        <path d="M30 16v64" stroke="var(--art-line)" stroke-width="2" stroke-linecap="round" />
        <circle cx="30" cy="32" r="5" stroke="var(--art-line-accent)" stroke-width="2" />
        <circle cx="30" cy="64" r="5" stroke="var(--art-line)" stroke-width="2" />
        <path d="M44 32h26M44 64h18" stroke="var(--art-line)" stroke-width="2" stroke-linecap="round" />
        <path d="M44 46h30" stroke="var(--art-line)" stroke-width="2" stroke-linecap="round" opacity="0.7" />
      </template>

      <!-- default：空刻度槽（通用"还没有数据"） -->
      <template v-else>
        <rect x="18" y="42" width="60" height="12" rx="6" stroke="var(--art-line)" stroke-width="2" />
        <path d="M28 42v-6M40 42v-8M52 42v-6M64 42v-8M76 42v-6" stroke="var(--art-line)" stroke-width="2" stroke-linecap="round" />
      </template>
    </svg>

    <p class="empty-text">{{ text }}</p>
    <p v-if="sub" class="empty-sub">{{ sub }}</p>
    <!-- 教界面：说明建档/提问之后能得到什么 -->
    <p v-if="hint" class="empty-hint">{{ hint }}</p>
    <div class="empty-action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 组件属性
 * @param text 空态主文案（如"还没有问答记录"）
 * @param sub 补充说明（可选，通常是输入示例）
 * @param hint 可获得什么（可选，空态"教界面"的那一句话）
 * @param variant 插图场景：qa 问答 / profile 档案 / record 记录 / default 通用刻度槽
 */
const props = withDefaults(
  defineProps<{
    text: string
    sub?: string
    hint?: string
    variant?: 'qa' | 'profile' | 'record' | 'default'
  }>(),
  { variant: 'default' }
)

/** 插图替代文本（装饰性插图也需要可读描述） */
const artLabel = computed(
  () =>
    ({
      qa: '对话气泡插图',
      profile: '档案卡片插图',
      record: '时间轴插图',
      default: '空刻度槽插图'
    })[props.variant]
)
</script>

<style lang="scss" scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--sp-12) var(--sp-6);
  text-align: center;
}

.empty-art {
  width: 96px;
  height: 96px;
  margin-bottom: var(--sp-4);
}

.empty-text {
  font-size: var(--fs-body);
  color: var(--ink-1);
  font-weight: 600;
  line-height: 1.5;
}

.empty-sub {
  margin-top: var(--sp-2);
  font-size: var(--fs-sub);
  color: var(--ink-2);
  line-height: 1.6;
  max-width: 30ch;
}

.empty-hint {
  margin-top: var(--sp-3);
  padding: 6px 12px;
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.7;
  max-width: 32ch;
}

.empty-action {
  margin-top: var(--sp-6);
}
</style>

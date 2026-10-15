<!--
  PageHeader 统一页头
  职责：为非 Tab 页提供带返回入口的页头。用户端在微信小程序 webview 中没有
  浏览器返回栏，缺失返回入口会让人被困在深层页面，只能靠侧滑手势退出小程序。

  用法：
    <PageHeader title="会员权益" sub="解锁深度养育内容">
      <template #right>…</template>
    </PageHeader>
    <PageHeader title="会员权益" :back="false" />

  props
    title  主标题（必填）
    sub    副标（可选，一行说明）
    back   是否渲染返回按钮，默认 true
    to     指定返回目标路由；不传则退回上一页
  插槽
    right  右侧操作区（可选）
-->
<template>
  <header class="ph">
    <div class="ph-line">
      <button v-if="back" class="ph-back touch-target" type="button" aria-label="返回" @click="goBack">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M15 6l-6 6 6 6"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
      <h1 class="page-title ph-title">{{ title }}</h1>
      <div v-if="$slots.right" class="ph-right">
        <slot name="right" />
      </div>
    </div>
    <p v-if="sub" class="page-sub ph-sub" :class="{ 'ph-sub--indent': back }">{{ sub }}</p>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { safeBack } from '@/utils/safeBack'

const props = withDefaults(
  defineProps<{
    title: string
    sub?: string
    back?: boolean
    to?: string
  }>(),
  { back: true, sub: '', to: '' }
)

const router = useRouter()

/**
 * 返回上一页。
 * 外部深链直达（无站内历史）时兜底退回首页，避免点了返回毫无反应或退出 webview。
 */
function goBack() {
  if (props.to) {
    void router.push(props.to)
    return
  }
  safeBack(router)
}
</script>

<style lang="scss" scoped>
.ph {
  /* 吸顶：长页面滚动后返回键仍在手边。
     小程序 webview 里返回键一旦滚出屏幕，用户只能靠左缘侧滑——
     侧滑过头就直接退出小程序，这正是要避免的。 */
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--bg);
  /* 负外边距抵消 .page 的内边距，再以内边距补回：
     静止时页头位置与原先完全一致，吸顶时背景又能盖住滚动内容。 */
  margin: calc(-1 * var(--sp-6)) calc(-1 * var(--sp-6)) var(--sp-4);
  padding: var(--sp-6) var(--sp-6) 0;
}

.ph-line {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}

.ph-back {
  flex: none;
  width: 32px;
  height: 32px;
  /* 视觉 32px；热区由 .touch-target 扩到 44px，不改变排版 */
  margin-left: -6px;
  border: none;
  border-radius: var(--radius-face);
  background: none;
  color: var(--ink-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s ease, background-color 0.15s ease;

  svg {
    width: 20px;
    height: 20px;
  }

  &:hover {
    color: var(--ink-1);
    background: var(--surface-2);
  }

  &:active {
    color: var(--accent);
  }
}

.ph-title {
  min-width: 0;
  font-size: var(--fs-title);
}

.ph-right {
  flex: none;
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.ph-sub {
  margin-top: 2px;
}

/* 与标题左对齐：缩进 = 返回键宽 32 − 负外边距 6 */
.ph-sub--indent {
  padding-left: 26px;
}
</style>

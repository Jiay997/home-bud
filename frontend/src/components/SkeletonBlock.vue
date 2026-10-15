<!--
  SkeletonBlock 骨架块
  surface-2 底 + 1.4s 扫光动画；用于加载态占位（禁用居中转圈）。
  内置 240ms 延迟出现 + 出现时 160ms 淡入：不足 240ms 的等待（页面切换常于
  数十毫秒返回）骨架从未被绘制；慢响应才柔和出现，避免"框框一闪而过"。
-->
<template>
  <div class="skeleton" :style="{ height: height + 'px', borderRadius: round ? '999px' : 'var(--radius-face)' }" />
</template>

<script setup lang="ts">
/**
 * 组件属性
 * @param height 块高度（px，默认 48）
 * @param round 是否胶囊形（默认 false）
 */
withDefaults(defineProps<{ height?: number; round?: boolean }>(), {
  height: 48,
  round: false
})
</script>

<style lang="scss" scoped>
.skeleton {
  width: 100%;
  background: linear-gradient(
    100deg,
    var(--surface-2) 40%,
    color-mix(in srgb, var(--surface) 60%, var(--surface-2)) 50%,
    var(--surface-2) 60%
  );
  background-size: 200% 100%;
  animation: jiaban-shimmer 1.4s linear infinite, sk-fade-in 160ms ease-out 240ms both;
}
</style>

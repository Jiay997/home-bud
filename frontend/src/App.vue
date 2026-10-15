<!--
  App.vue 根组件
  仅承载路由出口（根级布局切换淡入：用户端 ↔ 后台 ↔ 登录页）；
  移动端 375 基准容器与底部 Tab 由 MobileLayout 提供。
-->
<template>
  <router-view v-slot="{ Component }">
    <Transition name="root-page">
      <component :is="Component" />
    </Transition>
  </router-view>
</template>

<script setup lang="ts">
// 无全局逻辑，保持根组件精简；过渡类见 styles/motion.scss
</script>

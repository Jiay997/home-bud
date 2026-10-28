<!--
  App.vue 根组件
  仅承载路由出口（后台布局 ↔ 登录页之间切换的根级淡入）。
  说明：C 端用户端已迁至 uni-app 跨端工程 client/（小程序 + H5），本工程只服务后台管理端。
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

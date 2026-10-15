<!--
  MobileLayout 移动端布局
  375 基准容器（max-width 430 居中），底部 4 Tab：首页/档案/记录/我的；
  SVG 描边图标（24 网格 1.75），选中态 accent 色 + 字重。
-->
<template>
  <div
    class="mobile-shell"
    :class="{ 'has-tabbar': !!route.meta?.tab, 'mobile-shell--start': route.name === 'start' }"
  >
    <main class="mobile-main">
      <!-- 页面切换过渡：方向（前进/返回/同级淡入）由 router/pageTransition.ts 判定，类见 styles/motion.scss -->
      <router-view v-slot="{ Component, route: r }">
        <Transition :name="`pg-${pageTransition.direction}`">
          <component :is="Component" :key="r.path" />
        </Transition>
      </router-view>
    </main>
    <!-- 底部 Tab 仅在标记 meta.tab 的页面渲染（启动页/问答/表单等全屏页不显示，避免遮挡主操作）；
         进出场用上下滑动替代 v-if 硬切换 -->
    <Transition name="tabbar-slide">
      <nav v-if="route.meta?.tab" class="tabbar" aria-label="主导航">
        <router-link
          v-for="t in tabs"
          :key="t.key"
          :to="t.to"
          class="tab-item"
          :class="{ active: isActive(t) }"
        >
          <!-- SVG 图标：24 网格，描边 1.75 -->
          <svg viewBox="0 0 24 24" class="tab-icon" fill="none" aria-hidden="true">
            <path
              :d="t.icon"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span class="tab-label">{{ t.label }}</span>
        </router-link>
      </nav>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { nextTick, onMounted, watch } from 'vue'
import { pageTransition } from '@/router/pageTransition'

const route = useRoute()

/** Tab 配置：key/to/label/图标 path */
const tabs = [
  {
    key: 'home',
    to: '/app/home',
    label: '首页',
    icon: 'M3 10.5 12 3l9 7.5M5.5 9.5V20a1 1 0 0 0 1 1H10v-6h4v6h3.5a1 1 0 0 0 1-1V9.5'
  },
  {
    key: 'profiles',
    to: '/app/profiles',
    label: '档案',
    icon: 'M4 6.5A2.5 2.5 0 0 1 6.5 4h7L18 8.5V19a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 17.5v-11ZM13.5 4v4.5H18M8 13h6M8 16.5h4'
  },
  {
    key: 'history',
    to: '/app/history',
    label: '记录',
    icon: 'M12 7v5l3 2M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18Z'
  },
  {
    key: 'me',
    to: '/app/me',
    label: '我的',
    icon: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20.5a7.5 7.5 0 0 1 15 0'
  }
]

/**
 * 判断当前 Tab 是否选中
 * @param t Tab 配置项
 * @returns 是否选中
 */
function isActive(t: { key: string }): boolean {
  return route.meta?.tab === t.key
}

/**
 * 开发期防护：非 Tab 页必须留站内出口（返回键 / 退出钮 / 标记 data-exit），
 * 否则用户在小程序 web-view 中没有浏览器返回栏，只能靠侧滑手势退出。
 * 只告警不阻断；/app/start 为登录落地页，允许无返回。
 */
if (import.meta.env.DEV) {
  const EXIT_SELECTOR = 'button[aria-label="返回"], .quit-btn, [data-exit]'
  const checkExit = () => {
    if (route.meta?.tab || route.path === '/app/start') return
    void nextTick(() => {
      if (!document.querySelector(EXIT_SELECTOR)) {
        console.warn(
          `[nav] ${route.fullPath} 未找到站内出口：需要 button[aria-label="返回"]、.quit-btn 或 [data-exit] 之一`
        )
      }
    })
  }
  onMounted(checkExit)
  watch(() => route.fullPath, checkExit)
}
</script>

<style lang="scss" scoped>
.mobile-shell {
  max-width: 430px;
  min-height: 100vh;
  margin: 0 auto;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  position: relative;
}

.mobile-shell--start {
  max-width: none;
  min-height: 100dvh;
}

.mobile-main {
  flex: 1;
  min-height: 100vh;
}

/* 有底部 Tab 的页面：内容区预留 Tab 高度，避免底部主操作被遮挡 */
.mobile-shell.has-tabbar .mobile-main {
  padding-bottom: calc(60px + env(safe-area-inset-bottom));
}

.tabbar {
  position: fixed;
  bottom: 0;
  /* 居中用 left/right + margin auto（不用 translateX）：transform 留给进出场滑动 */
  left: 0;
  right: 0;
  margin: 0 auto;
  width: 100%;
  max-width: 430px;
  height: calc(60px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--surface);
  border-top: 1px solid var(--line);
  display: flex;
  z-index: 100;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--ink-3);
  text-decoration: none;
  transition: color 0.15s;

  .tab-icon {
    width: 24px;
    height: 24px;
  }

  .tab-label {
    font-size: var(--fs-caption);
    font-weight: 400;
  }

  &.active {
    color: var(--accent);

    .tab-label {
      font-weight: 600;
    }
  }
}
</style>

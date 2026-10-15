<!--
  QuotaDrawer 额度用尽底部抽屉（SC-21 抽象）
  触发：问答页收到 1202（今日免费额度已用完）时弹出；会员不受限说明 + 权益入口。
  用法：<QuotaDrawer v-model="quotaDrawer" />
  props / emits：v-model 控制显隐（内部关闭与跳转都会同步）。
-->
<template>
  <transition name="drawer-fade">
    <div v-if="modelValue" class="drawer-mask" @click.self="close">
      <div class="drawer" role="dialog" aria-label="额度用尽提示">
        <!-- 顶部拉手 -->
        <span class="drawer-grip touch-target" aria-hidden="true" @click="close" />

        <!-- 标定预警行 -->
        <div class="dw-warn-row">
          <span class="dw-warn-label">● 标定预警 · 用量上限</span>
          <span class="caption numeric">刻度标尺：{{ user.quotaUsed }}/{{ user.quotaLimit }}</span>
        </div>
        <div class="dw-scale" aria-hidden="true">
          <span v-for="i in 30" :key="i" class="dw-tick" :class="{ heavy: i % 5 === 1 }" />
        </div>

        <!-- 今日免费额度已用完卡 -->
        <div class="dw-hero">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 7v5l3 2m-3-13a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
          <p>今日免费额度已用完</p>
        </div>

        <!-- 免费额度说明 + 会员不受限卡 -->
        <div class="dw-info-card">
          <div class="dw-info-row">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M8 3v3m8-3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
            <div>
              <p class="dw-info-title">免费额度：每日 {{ user.quotaLimit }} 次</p>
              <p class="dw-info-sub caption">每日零点（次日 00:00）系统刻度归位后自动恢复使用</p>
            </div>
          </div>
          <div class="dw-info-row">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
            <div>
              <p class="dw-info-title pro">会员用户：不受提问额度限制</p>
              <p class="dw-info-sub caption">享用全生命周期评估报告与无限制科学分析</p>
            </div>
          </div>
        </div>

        <!-- 今日仍可浏览绿条 -->
        <div class="dw-green-strip">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          您今天仍可浏览历史档案、查看已生成测评报告与知识库。
        </div>

        <!-- 操作按钮 -->
        <div class="dw-actions">
          <button class="dw-btn ghost" @click="close">知道了</button>
          <button class="dw-btn main" @click="goMember">
            {{ user.isMember ? '查看权益状态' : '查看权益说明' }}
          </button>
        </div>

        <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const router = useRouter()
const user = useUserStore()

function close(): void {
  emit('update:modelValue', false)
}

function goMember(): void {
  close()
  void router.push('/app/member')
}
</script>

<style lang="scss" scoped>
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.2s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 300;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.drawer {
  width: 100%;
  max-width: 430px;
  background: var(--surface);
  border-radius: 16px 16px 0 0;
  padding: var(--sp-3) var(--sp-6) calc(var(--sp-6) + env(safe-area-inset-bottom));
  max-height: 86vh;
  overflow-y: auto;
}

.drawer-grip {
  display: block;
  width: 44px;
  height: 4px;
  border-radius: var(--radius-pill);
  background: var(--line-strong);
  margin: 0 auto var(--sp-4);
  cursor: pointer;
}

.dw-warn-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-2);

  .dw-warn-label {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--warn);
  }
}

.dw-scale {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 14px;
  margin-bottom: var(--sp-4);

  .dw-tick {
    flex: 1;
    height: 7px;
    background: var(--line);

    &.heavy {
      height: 13px;
      background: var(--line-strong);
    }
  }
}

.dw-hero {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);

  svg {
    flex: none;
    width: 22px;
    height: 22px;
    color: var(--warn);
  }

  p {
    font-size: var(--fs-display);
    font-weight: 700;
    color: var(--ink-1);
  }
}

.dw-info-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-4);
  margin-bottom: var(--sp-3);
}

.dw-info-row {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;

  & + .dw-info-row {
    border-top: 1px dashed var(--line);
  }

  > svg {
    flex: none;
    width: 18px;
    height: 18px;
    color: var(--accent);
    margin-top: 2px;
  }

  .dw-info-title {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);

    &.pro {
      color: var(--accent);
    }
  }

  .dw-info-sub {
    margin-top: 2px;
  }
}

.dw-green-strip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.7;
  margin-bottom: var(--sp-4);

  svg {
    flex: none;
    width: 15px;
    height: 15px;
    color: var(--accent);
    margin-top: 2px;
  }
}

.dw-actions {
  display: flex;
  gap: var(--sp-3);
  margin-bottom: var(--sp-2);
}

.dw-btn {
  flex: 1;
  min-height: var(--touch-min);
  padding: 12px 0;
  border-radius: var(--radius-ctl);
  font-size: var(--fs-sub);
  font-weight: 600;
  cursor: pointer;

  &.ghost {
    background: var(--surface);
    border: 1px solid var(--line-strong);
    color: var(--ink-1);
  }

  &.main {
    background: var(--accent);
    border: 1px solid var(--accent);
    color: var(--on-accent);
  }
}
</style>

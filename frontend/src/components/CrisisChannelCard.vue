<!--
  CrisisChannelCard 危机求助渠道卡
  拨打 tel: + 复制号码；号码为空时显示"待补充"。
-->
<template>
  <div class="channel">
    <div class="channel-info">
      <p class="channel-name">{{ name }}</p>
      <p class="channel-number numeric">{{ number || '待补充' }}</p>
      <p v-if="hours" class="channel-hours caption">{{ hours }}</p>
    </div>
    <div class="channel-actions">
      <a v-if="number" class="act call" :href="`tel:${number}`">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M5 4h4l1.5 4.5L8 10a12 12 0 0 0 6 6l1.5-2.5L20 15v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1Z"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linejoin="round"
          />
        </svg>
        拨打
      </a>
      <button v-if="number" class="act copy" @click="copy">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.75" />
          <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" stroke="currentColor" stroke-width="1.75" />
        </svg>
        {{ copied ? '已复制' : '复制' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

/**
 * 组件属性
 * @param name 渠道名称（如"全国心理援助热线"）
 * @param number 电话号码（空则显示待补充）
 * @param hours 服务时间（可选）
 */
const props = defineProps<{
  name: string
  number?: string
  hours?: string
}>()

/** 复制成功态（2s 复位） */
const copied = ref(false)

/**
 * 复制号码到剪贴板
 */
async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.number || '')
    copied.value = true
    ElMessage.success('号码已复制')
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    ElMessage.error('复制失败，请手动记录号码')
  }
}
</script>

<style lang="scss" scoped>
.channel {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  background: var(--surface);
  border: 1px solid var(--danger);
  border-radius: var(--radius-face);
  padding: var(--sp-4) var(--sp-6);
  margin-bottom: var(--sp-3);
}

.channel-info {
  flex: 1;
  min-width: 0;
}

.channel-name {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
}

.channel-number {
  font-size: var(--fs-title);
  color: var(--danger);
  font-weight: 600;
}

.channel-actions {
  display: flex;
  gap: var(--sp-2);
}

.act {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--radius-ctl);
  font-size: var(--fs-caption);
  text-decoration: none;
  cursor: pointer;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink-1);

  svg {
    width: 14px;
    height: 14px;
  }

  &.call {
    background: var(--danger);
    border-color: var(--danger);
    color: var(--on-danger);
  }
}
</style>

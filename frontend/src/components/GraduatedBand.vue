<!--
  GraduatedBand 签名刻度带
  标尺 + 分区刻度（档位名居中于各自档位区）+ 槽 + 游标（越出槽 5px）。
  props: bands 档位名数组（低→高）、value 归一化 0-1 位置、label 维度名、partial 信息不足态（隐藏游标）。
-->
<template>
  <div class="band" :class="{ 'is-partial': partial, 'tone-danger': tone === 'danger' }">
    <div class="band-head">
      <span class="band-label">{{ label }}</span>
      <span class="band-level">{{ levelName }}</span>
    </div>
    <div
      class="band-scale"
      role="img"
      :aria-label="`${label}：${levelName}，档位由低到高为 ${bands.join('、')}`"
    >
      <i
        v-for="i in Math.max(bands.length - 1, 0)"
        :key="`zone-${i}`"
        class="zone-mark"
        :style="{ left: (i / bands.length) * 100 + '%' }"
      />
      <em
        v-for="(b, i) in bands"
        :key="b"
        class="zone-name"
        :style="{ left: ((i + 0.5) / bands.length) * 100 + '%' }"
      >{{ b }}</em>
    </div>
    <div class="band-track">
      <div v-if="!partial" class="band-cursor" :style="{ left: cursorPct }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 组件属性
 * @param bands 档位名（低→高）
 * @param value 归一化位置 0-1
 * @param label 维度标题
 * @param partial 信息不足态：隐藏游标，档位名显示「信息不足」
 * @param levelLabels 档位展示名覆盖（与刻度分区名不同口径时用，如「低倾向」）
 * @param tone 强调色：accent（默认）/ danger（红色仅落在游标与读数，不染整条）
 */
const props = withDefaults(
  defineProps<{
    bands: string[]
    value: number
    label: string
    partial?: boolean
    levelLabels?: string[]
    tone?: 'accent' | 'danger'
  }>(),
  { partial: false, levelLabels: undefined, tone: 'accent' }
)

/** 游标落点百分比（限幅 0-100） */
const cursorPct = computed(() => {
  const v = Math.min(1, Math.max(0, props.value || 0))
  return `${(v * 100).toFixed(1)}%`
})

/** 当前档位名（levelLabels 优先于分区名） */
const levelName = computed(() => {
  if (props.partial) return '信息不足'
  const v = Math.min(0.999, Math.max(0, props.value || 0))
  const idx = Math.floor(v * props.bands.length)
  return props.levelLabels?.[idx] || props.bands[idx] || ''
})
</script>

<style lang="scss" scoped>
.band {
  padding: var(--sp-3) 0;

  /* 信息不足：档位名沉为中性灰，游标缺席即「没有读数」 */
  &.is-partial .band-level {
    color: var(--ink-3);
  }

  /* 危险语义（风险拦截）：红只落在当前档读数与游标上 */
  &.tone-danger .band-level {
    color: var(--danger);
  }

  &.tone-danger .band-cursor {
    background: var(--danger);
  }
}

.band-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;

  .band-label {
    font-size: var(--fs-body);
    font-weight: 600;
    color: var(--ink-1);
  }

  .band-level {
    font-size: var(--fs-sub);
    color: var(--accent);
    font-weight: 600;
  }
}

/* 分区刻度：边界竖线 + 档位名居中于各区 */
.band-scale {
  position: relative;
  height: 26px;
  margin-top: var(--sp-2);

  .zone-mark {
    position: absolute;
    top: 0;
    width: 1px;
    height: 5px;
    background: var(--line-strong);
    transform: translateX(-50%);
  }

  .zone-name {
    position: absolute;
    top: 7px;
    font-style: normal;
    font-size: var(--fs-caption);
    line-height: 1.4;
    color: var(--ink-3);
    white-space: nowrap;
    transform: translateX(-50%);
  }
}

.band-track {
  margin-top: var(--sp-2);
  height: 12px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  position: relative;
}

.band-cursor {
  position: absolute;
  top: -5px; /* 游标越出槽 5px */
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--accent);
  border: 3px solid var(--surface);
  box-shadow: var(--shadow-e1);
  transform: translateX(-50%);
  transition: left 0.4s ease;
}
</style>

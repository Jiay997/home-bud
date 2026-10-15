<script setup lang="ts">
import { computed } from 'vue'

interface HouseholdProfile {
  uid: string
  nickname?: string
  age_months?: number
  age_label?: string
  species?: string
  species_label?: string
}

const props = defineProps<{
  children: HouseholdProfile[]
  pets: HouseholdProfile[]
  currentUid: string | null
}>()

const emit = defineEmits<{
  select: [uid: string]
  create: [kind: 'child' | 'pet']
}>()

const child = computed(() => props.children[0] || null)
const pet = computed(() => props.pets[0] || null)
const childLabel = computed(() => {
  if (!child.value) return '添加孩子档案'
  return child.value.nickname || '宝宝'
})
const petLabel = computed(() => {
  if (!pet.value) return '添加宠物档案'
  return pet.value.nickname || '宠物'
})
const childMeta = computed(() => {
  if (!child.value) return '育儿观察'
  return child.value.age_label || (typeof child.value.age_months === 'number' ? `${child.value.age_months} 个月` : '孩子档案')
})
const petMeta = computed(() => {
  if (!pet.value) return '宠物观察'
  return pet.value.species_label || pet.value.species || '宠物档案'
})
</script>

<template>
  <section class="household-map" aria-label="家庭档案关系图">
    <div class="map-topline">
      <h3>同住档案</h3>
      <span>{{ children.length + pets.length }} 个观察对象</span>
    </div>

    <div class="map-canvas">
      <svg class="map-lines" viewBox="0 0 360 210" preserveAspectRatio="none" aria-hidden="true">
        <path class="line-child" d="M104 63C147 69 161 87 183 105" />
        <path class="line-pet" d="M257 148C227 140 213 124 183 105" />
        <path class="line-safety" d="M102 162C119 119 139 87 175 61" />
        <circle cx="183" cy="105" r="5" />
      </svg>

      <div class="map-core" aria-hidden="true">
        <span class="core-mark"><i /><i /></span>
        <span class="core-name">共居</span>
      </div>

      <button
        v-if="child"
        class="map-node node-child"
        :class="{ selected: currentUid === child.uid }"
        type="button"
        :aria-pressed="currentUid === child.uid"
        :aria-label="`选择孩子档案：${childLabel}`"
        @click="emit('select', child.uid)"
      >
        <span class="node-symbol child-symbol" aria-hidden="true">童</span>
        <span class="node-copy"><strong>{{ childLabel }}</strong><small>{{ childMeta }}</small></span>
      </button>
      <button
        v-else
        class="map-node node-child node-empty"
        type="button"
        aria-label="添加孩子档案"
        @click="emit('create', 'child')"
      >
        <span class="node-symbol child-symbol" aria-hidden="true">+</span>
        <span class="node-copy"><strong>{{ childLabel }}</strong><small>{{ childMeta }}</small></span>
      </button>

      <button
        v-if="pet"
        class="map-node node-pet"
        :class="{ selected: currentUid === pet.uid }"
        type="button"
        :aria-pressed="currentUid === pet.uid"
        :aria-label="`选择宠物档案：${petLabel}`"
        @click="emit('select', pet.uid)"
      >
        <span class="node-symbol pet-symbol" aria-hidden="true">伴</span>
        <span class="node-copy"><strong>{{ petLabel }}</strong><small>{{ petMeta }}</small></span>
      </button>
      <button
        v-else
        class="map-node node-pet node-empty"
        type="button"
        aria-label="添加宠物档案"
        @click="emit('create', 'pet')"
      >
        <span class="node-symbol pet-symbol" aria-hidden="true">+</span>
        <span class="node-copy"><strong>{{ petLabel }}</strong><small>{{ petMeta }}</small></span>
      </button>
    </div>

    <div class="map-lenses" aria-label="观察视角">
      <span><i class="lens-safety" />安全先行</span>
      <span><i class="lens-child" />育儿观察</span>
      <span><i class="lens-pet" />宠物观察</span>
    </div>
    <p class="map-footnote">点选对象，切换当前问答档案</p>
  </section>
</template>

<style lang="scss" scoped>
.household-map {
  position: relative;
  padding: 14px 14px 12px;
  overflow: hidden;
  border: 1px solid rgb(230 241 235 / 18%);
  border-radius: 14px 14px 14px 4px;
  background: #1d3831;
  color: #f4f7f2;
}

.map-topline {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;

  h3 {
    font-size: 13px;
    font-weight: 600;
  }

  span {
    color: #b9c9c2;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
}

.map-canvas {
  position: relative;
  height: 166px;
  margin: 4px -2px 0;
}

.map-lines {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;

  path {
    fill: none;
    stroke-width: 1.5;
    stroke-dasharray: 3 5;
    vector-effect: non-scaling-stroke;
  }

  .line-child { stroke: #dc8b71; }
  .line-pet { stroke: #80b9a6; }
  .line-safety { stroke: #d8b36a; }

  circle {
    fill: #f4f7f2;
    stroke: #1d3831;
    stroke-width: 3px;
  }
}

.map-core {
  position: absolute;
  left: 50%;
  top: 49%;
  display: grid;
  width: 62px;
  height: 62px;
  place-content: center;
  justify-items: center;
  gap: 3px;
  transform: translate(-50%, -50%);
  border: 1px solid rgb(241 246 240 / 36%);
  border-radius: 50%;
  background: #294b41;
}

.core-mark {
  display: flex;
  gap: 3px;

  i {
    width: 7px;
    height: 7px;
    border: 1px solid #edf3ec;
    border-radius: 2px;
    transform: rotate(45deg);
  }

  i + i { transform: rotate(45deg) translateY(3px); }
}

.core-name {
  color: #e4eee7;
  font-size: 10px;
}

.map-node {
  position: absolute;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 46%;
  min-height: 54px;
  padding: 7px;
  border: 1px solid rgb(230 241 235 / 18%);
  border-radius: 7px;
  background: #28463d;
  color: #f4f7f2;
  text-align: left;
  cursor: pointer;
  transition: transform 220ms cubic-bezier(.2,.8,.2,1), border-color 220ms ease, background 220ms ease;

  &:hover,
  &:focus-visible,
  &.selected {
    border-color: currentColor;
    background: #31564a;
  }

  &:active { transform: scale(.98); }

  &.node-child { left: 0; top: 8px; color: #f2b09a; }
  &.node-pet { right: 0; bottom: 6px; color: #9cd0bd; }

  &.node-empty {
    border-style: dashed;
    background: rgb(255 255 255 / 3%);

    .node-copy strong { color: #e5eee9; }
    .node-copy small { color: #bdcbc5; }
  }
}

.node-symbol {
  display: grid;
  width: 28px;
  height: 28px;
  flex: none;
  place-items: center;
  border-radius: 8px 8px 8px 2px;
  background: currentColor;
  font-size: 13px;
  font-weight: 700;

  &.child-symbol { color: #63382e; }
  &.pet-symbol { color: #21483e; }
}

.node-copy {
  display: grid;
  min-width: 0;

  strong,
  small {
    overflow: hidden;
    color: #fff;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong { font-size: 12px; font-weight: 600; }
  small { margin-top: 2px; color: #d0ddd7; font-size: 10px; }
}

.map-lenses {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 9px;
  border-top: 1px solid rgb(230 241 235 / 18%);

  span {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    color: #e3ece7;
    font-size: 10px;
  }

  i { width: 6px; height: 6px; border-radius: 50%; }
  .lens-safety { background: #d8b36a; }
  .lens-child { background: #dc8b71; }
  .lens-pet { background: #80b9a6; }
}

.map-footnote {
  margin-top: 7px;
  color: #bdcbc5;
  font-size: 10px;
}

@media (prefers-reduced-motion: reduce) {
  .map-node { transition: none; }
}
</style>

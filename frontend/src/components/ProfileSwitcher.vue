<!--
  ProfileSwitcher 问答对象选择弹层（受控）
  由页面提供触发元素：v-model:open 控制弹层开关，v-model 为当前档案 uid。
  打开时实时拉取孩子/宠物档案（保证跨页面编辑后仍是最新）；空态引导去建档。
-->
<template>
  <el-dialog
    v-model="openModel"
    title="选择问答对象"
    width="90%"
    class="profile-dialog"
    :append-to-body="true"
  >
    <template v-if="loadFailed">
      <p class="load-failed">
        <span>档案列表加载失败</span>
        <button class="retry-link" type="button" @click="load">重试</button>
      </p>
    </template>
    <template v-else>
      <div class="group">
        <p class="group-title">孩子</p>
        <div
          v-for="c in children"
          :key="c.uid"
          class="opt"
          :class="{ current: c.uid === modelValue }"
          @click="pick(c.uid)"
        >
          <span class="opt-name">{{ c.nickname }}</span>
          <span class="opt-meta">{{ childMeta(c) }}</span>
          <svg v-if="c.uid === modelValue" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <p v-if="!children.length" class="group-empty">暂无孩子档案</p>
      </div>

      <div class="group">
        <p class="group-title">宠物</p>
        <div
          v-for="p in pets"
          :key="p.uid"
          class="opt"
          :class="{ current: p.uid === modelValue }"
          @click="pick(p.uid)"
        >
          <span class="opt-name">{{ p.nickname }}</span>
          <span class="opt-meta">{{ p.species_label || p.species || '' }}</span>
          <svg v-if="p.uid === modelValue" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <p v-if="!pets.length" class="group-empty">暂无宠物档案</p>
      </div>

      <div v-if="loaded && !children.length && !pets.length" class="empty-cta">
        <p class="cta-text">还没有档案。建档后，回答会按你家宝宝或宠物的年龄与情况来说。</p>
        <router-link class="cta-link" to="/app/profiles" @click="openModel = false">去建档</router-link>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getChildren, getPets } from '@/api/client'

/**
 * 组件属性
 * @param modelValue 当前选中档案 uid（v-model）
 * @param open 弹层开关（v-model:open，由页面触发元素控制）
 */
const props = withDefaults(
  defineProps<{ modelValue: string | null; open?: boolean }>(),
  { open: false }
)

const emit = defineEmits<{
  (e: 'update:modelValue', v: string | null): void
  (e: 'update:open', v: boolean): void
}>()

/** 弹层开关双向绑定 */
const openModel = computed({
  get: () => !!props.open,
  set: (v: boolean) => emit('update:open', v)
})

/** 孩子档案列表 */
const children = ref<any[]>([])
/** 宠物档案列表 */
const pets = ref<any[]>([])
/** 是否已成功拉取过一次 */
const loaded = ref(false)
/** 拉取失败态 */
const loadFailed = ref(false)

/**
 * 孩子档案副注（性别 · 月龄）
 * @param c 孩子档案
 */
function childMeta(c: any): string {
  const g = c.gender_label || c.gender || ''
  const a = c.age_months ? `${c.age_months}个月` : ''
  return [g, a].filter(Boolean).join(' · ')
}

/**
 * 拉取档案列表（失败置失败态，弹层内可重试）
 */
async function load(): Promise<void> {
  loadFailed.value = false
  try {
    const [c, p]: any = await Promise.all([getChildren(), getPets()])
    children.value = c?.children || c?.items || (Array.isArray(c) ? c : [])
    pets.value = p?.pets || p?.items || (Array.isArray(p) ? p : [])
    loaded.value = true
  } catch {
    loadFailed.value = true
  }
}

/** 每次打开都重新拉取（档案可能在别处刚改过） */
watch(
  () => props.open,
  (v) => {
    if (v) void load()
  }
)

/**
 * 选中对象并关闭弹层
 * @param uid 档案 uid
 */
function pick(uid: string): void {
  emit('update:modelValue', uid)
  openModel.value = false
}
</script>

<style lang="scss" scoped>
.group {
  margin-bottom: var(--sp-6);

  .group-title {
    font-size: var(--fs-caption);
    color: var(--ink-3);
    margin-bottom: var(--sp-2);
  }

  .group-empty {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }
}

.opt {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--touch-min);
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  cursor: pointer;

  &:active {
    background: var(--surface-2);
  }

  &.current {
    background: var(--accent-soft);
  }

  .opt-name {
    font-size: var(--fs-body);
    color: var(--ink-1);
  }

  .opt-meta {
    font-size: var(--fs-caption);
    color: var(--ink-3);
    margin-left: auto;
  }

  svg {
    width: 16px;
    height: 16px;
    flex: none;
    color: var(--accent);
  }
}

.load-failed {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
  padding: var(--sp-6) 0;
  font-size: var(--fs-sub);
  color: var(--ink-2);

  .retry-link {
    border: none;
    background: none;
    padding: 0;
    font-family: inherit;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
  }
}

.empty-cta {
  padding-bottom: var(--sp-2);

  .cta-text {
    font-size: var(--fs-sub);
    color: var(--ink-2);
    line-height: 1.7;
    margin-bottom: var(--sp-4);
  }

  .cta-link {
    display: flex;
    align-items: center;
    justify-content: center;
    height: var(--touch-min);
    border: 1px solid var(--accent-line);
    border-radius: var(--radius-ctl);
    color: var(--accent);
    font-size: var(--fs-body);
    font-weight: 600;

    &:hover,
    &:focus-visible {
      background: var(--accent-soft);
      border-color: var(--accent);
    }
  }
}
</style>

<!--
  ProfileListPage SC-03 档案管理列表（Stitch 稿重构）
  版式：页头（返回 + 居中标题）→ 孩子/宠物分段切换（真实计数 n/上限）→ 当前问答对象配额刻度行 →
  档案卡（当前档案绿边高亮 + 脱敏信息块 + chips；非当前「设为当前」描边钮）→ 全宽新建主按钮 →
  档案库容量配额卡（扩容入口）→ AI 免责条。
  儿童信息展示脱敏（昵称首字保留、生日年保留月日打码），容量上限随会员态（免费 3 / 会员 10）。
-->
<template>
  <div class="page pl-page">
    <!-- ===== 页头：返回 + 居中标题 ===== -->
    <header class="list-head">
      <button class="head-back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">档案管理</h1>
      <span class="head-space" aria-hidden="true" />
    </header>

    <!-- ===== 孩子/宠物分段切换 ===== -->
    <div class="seg-tabs" role="tablist">
      <button class="seg" :class="{ on: tab === 'child' }" role="tab" :aria-selected="tab === 'child'" @click="tab = 'child'">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="9" r="4.5" stroke="currentColor" stroke-width="1.75" />
          <path d="M5.5 19.5c1-2.8 3.4-4.5 6.5-4.5s5.5 1.7 6.5 4.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
        </svg>
        孩子 <em class="numeric">{{ children.length }}/{{ capMax }}</em>
      </button>
      <button class="seg" :class="{ on: tab === 'pet' }" role="tab" :aria-selected="tab === 'pet'" @click="tab = 'pet'">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="7.2" cy="9.5" r="1.7" fill="currentColor" />
          <circle cx="12" cy="7.5" r="1.7" fill="currentColor" />
          <circle cx="16.8" cy="9.5" r="1.7" fill="currentColor" />
          <path d="M12 11c2.3 0 4.2 1.8 4.2 3.8 0 1.4-1 2.4-2.3 2.4-.7 0-1.2-.3-1.9-.3s-1.2.3-1.9.3c-1.3 0-2.3-1-2.3-2.4 0-2 1.9-3.8 4.2-3.8Z" fill="currentColor" />
        </svg>
        宠物 <em class="numeric">{{ pets.length }}/{{ capMax }}</em>
      </button>
    </div>

    <!-- ===== 配额刻度行 ===== -->
    <div class="card quota-strip">
      <span class="quota-label"><i class="dot" /> 当前问答对象配额刻度</span>
      <span class="quota-val caption">
        已建 <b class="numeric">{{ currentList.length }}</b> / 上限 {{ capMax }}（{{ user.isMember ? '会员库' : '基础库' }}）
      </span>
    </div>

    <!-- 骨架 -->
    <template v-if="loading">
      <SkeletonBlock :height="150" style="margin-bottom: 12px" />
      <SkeletonBlock :height="150" />
    </template>

    <!-- 失败 -->
    <div v-else-if="loadFailed" class="card retry">
      <p>加载失败</p>
      <el-button type="primary" size="small" @click="load">重试</el-button>
    </div>

    <!-- 空态 -->
    <EmptyState
      v-else-if="currentList.length === 0"
      variant="profile"
      :text="tab === 'child' ? '还没有孩子档案' : '还没有宠物档案'"
      sub="建档后，问答会结合档案信息给出更贴合的建议"
      :hint="tab === 'child' ? '填出生日期即可，会自动换算月龄并锁定对应的发育阶段，建议比通用答案更贴合' : '填种类与年龄即可，疫苗、驱虫与喂养建议会按生命阶段调整'"
    >
      <template #action>
        <el-button type="primary" size="large" @click="goNew">新建{{ tab === 'child' ? '孩子' : '宠物' }}档案</el-button>
      </template>
    </EmptyState>

    <!-- ===== 档案卡列表 ===== -->
    <template v-else>
      <article
        v-for="p in currentList"
        :key="p.uid"
        class="card profile-card"
        :class="{ current: p.uid === user.currentProfileUid }"
      >
        <!-- 卡头：头像 + 名字 + 角色徽章 -->
        <div class="pc-head">
          <div class="avatar" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="9.5" r="4" stroke="currentColor" stroke-width="1.75" />
              <path d="M6 19c1-2.4 3.2-3.8 6-3.8s5 1.4 6 3.8" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            </svg>
          </div>
          <div class="pc-titles">
            <p class="pc-name">
              {{ tab === 'child' ? maskNickname(p.nickname) : p.nickname }}
              <svg v-if="p.uid === user.currentProfileUid" class="verify-ico" viewBox="0 0 24 24" fill="none" aria-label="已认证">
                <path
                  d="m12 2.6 2.1 1.6 2.6-.3 1 2.4 2.3 1.2-.5 2.6 1.5 2.2-1.5 2.2.5 2.6-2.3 1.2-1 2.4-2.6-.3L12 21.4l-2.1-1.6-2.6.3-1-2.4-2.3-1.2.5-2.6L3 12l1.5-2.2-.5-2.6 2.3-1.2 1-2.4 2.6.3L12 2.6Z"
                  fill="var(--accent)"
                />
                <path d="m9 12 2 2 4-4.2" stroke="var(--sc-lowest)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </p>
            <p v-if="p.uid === user.currentProfileUid" class="pc-state">● 正在接受 AI 深度发育监测</p>
            <p v-else class="pc-state dim">次要问答档案</p>
          </div>
          <button v-if="p.uid !== user.currentProfileUid" class="role-btn" @click="setCurrent(p)">设为当前</button>
          <span v-else class="role-btn solid"><i>✓</i> 当前</span>
        </div>

        <!-- 信息块（脱敏） -->
        <div class="pc-info">
          <p class="info-line1">
            <template v-if="tab === 'child'">
              <span>{{ ageText(p) }}</span><i class="sep">·</i><span>{{ genderText(p) }}</span>
              <template v-if="maskBirthdate(p)">
                <i class="sep">·</i><span class="numeric">{{ maskBirthdate(p) }}</span>
                <svg class="mask-ico" viewBox="0 0 24 24" fill="none" aria-label="已脱敏">
                  <path d="M3 3l18 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                  <path d="M10.6 5.1A9.8 9.8 0 0 1 12 5c5 0 8.6 3.6 10 7-.5 1.2-1.3 2.5-2.4 3.6M6.2 6.3C4 7.7 2.6 9.7 2 12c1.4 3.4 5 7 10 7 1.6 0 3-.4 4.3-1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                  <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                </svg>
              </template>
            </template>
            <template v-else>
              <span>{{ petTypeText(p) }}</span>
              <template v-if="p.breed && p.breed !== 'unknown'"><i class="sep">·</i><span>{{ p.breed }}</span></template>
              <template v-if="sterileText(p)"><i class="sep">·</i><span>{{ sterileText(p) }}</span></template>
            </template>
          </p>
          <div class="info-chips">
            <template v-if="tab === 'child'">
              <span v-if="p.height_cm" class="chip plain"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 20h16M7 16V6.5L12 4l5 2.5V16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>{{ p.height_cm }}cm</span>
              <span v-if="p.weight_kg" class="chip plain"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="4" y="8" width="16" height="12" rx="2.5" stroke="currentColor" stroke-width="1.6" /><path d="M8.5 8a3.5 3.5 0 0 1 7 0" stroke="currentColor" stroke-width="1.6" /></svg>{{ p.weight_kg }}kg</span>
              <span class="chip" :class="{ gray: !allergyText(p) }">{{ allergyText(p) || '无过敏' }}</span>
              <span v-if="p.growth_percentile" class="chip plain">生长百分位: {{ p.growth_percentile }}</span>
              <span v-if="p.premature_flag" class="chip amber">早产</span>
              <span v-if="p.solid_food_month" class="chip plain">辅食 {{ p.solid_food_month }} 月龄开始</span>
            </template>
            <template v-else>
              <span v-if="p.weight_kg" class="chip plain">{{ p.weight_kg }}kg</span>
              <span v-if="p.main_food" class="chip plain">{{ p.main_food }}</span>
            </template>
          </div>
        </div>

        <!-- 操作行 -->
        <div class="pc-actions">
          <button class="pc-act danger" @click="askDelete(p)">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 7h14M10 4h4M7 7l.8 12a1.5 1.5 0 0 0 1.5 1.4h5.4a1.5 1.5 0 0 0 1.5-1.4L17 7M10 11v6M14 11v6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
            删除
          </button>
          <button class="pc-act" @click="goEdit(p)">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 20h4l11-11a2.1 2.1 0 0 0-3-3L5 17v3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" /><path d="M13.5 6.5 17 10" stroke="currentColor" stroke-width="1.6" /></svg>
            编辑
          </button>
        </div>
      </article>

      <!-- 新建主按钮 -->
      <el-button v-if="currentList.length < capMax" type="primary" size="large" class="add-btn" @click="goNew">
        <span class="add-plus">＋</span> 新建{{ tab === 'child' ? '孩子' : '宠物' }}档案
      </el-button>
    </template>

    <!-- ===== 档案库容量配额卡 ===== -->
    <div class="card capacity-card">
      <span class="cap-ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <rect x="3.5" y="7" width="17" height="13" rx="2" stroke="currentColor" stroke-width="1.6" />
          <path d="M3.5 11h17M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7" stroke="currentColor" stroke-width="1.6" />
        </svg>
      </span>
      <div class="cap-text">
        <p class="cap-title">档案库容量配额</p>
        <p class="caption">免费 3 个/类 · 会员 10 个/类</p>
      </div>
      <button class="cap-expand touch-target" type="button" @click="$router.push('/app/member')">扩容 →</button>
    </div>

    <!-- AI 免责条 -->
    <p class="ai-note caption">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
      AI 生成内容，仅供参考，不替代医生诊断
    </p>

    <!-- 删除确认弹窗 -->
    <ProfileDeleteDialog
      v-model="delVisible"
      :profile="deleting"
      :kind="tab"
      @deleted="onDeleted"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getChildren, getPets, setCurrentProfile } from '@/api/client'
import { useUserStore } from '@/stores/user'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import EmptyState from '@/components/EmptyState.vue'
import ProfileDeleteDialog from './ProfileDeleteDialog.vue'

const router = useRouter()
const user = useUserStore()

/** 当前 Tab：child | pet */
const tab = ref<'child' | 'pet'>('child')
/** 孩子档案 */
const children = ref<any[]>([])
/** 宠物档案 */
const pets = ref<any[]>([])
/** 加载态 */
const loading = ref(true)
/** 失败态 */
const loadFailed = ref(false)
/** 删除弹窗显隐 */
const delVisible = ref(false)
/** 待删除档案 */
const deleting = ref<any>(null)

/** 当前 Tab 对应列表 */
const currentList = computed(() => (tab.value === 'child' ? children.value : pets.value))

/** 档案容量上限：免费 3 个/类，会员 10 个/类 */
const capMax = computed(() => (user.isMember ? 10 : 3))

/**
 * 昵称脱敏：保留首字，其余以"某"替换（防御性前端处理）
 * @param name 原昵称
 * @returns 脱敏昵称
 */
function maskNickname(name: string): string {
  if (!name) return ''
  return name.length <= 1 ? name : name[0] + '某'.repeat(Math.min(name.length - 1, 2))
}

/**
 * 生日脱敏：仅保留年份，月日打码（2024-**-**）
 * @param p 档案对象（后端字段 birth_date）
 * @returns 脱敏生日字符串（无生日返回空）
 */
function maskBirthdate(p: any): string {
  const b = String(p?.birth_date || '')
  return b.length >= 4 ? `${b.slice(0, 4)}-**-**` : ''
}

/**
 * 儿童月龄文案：≥12 月显示「X 岁 Y 月」，不足 1 岁显示「N 月」
 * @param p 档案对象
 * @returns 月龄文案
 */
function ageText(p: any): string {
  const m = Number(p?.age_months ?? NaN)
  if (Number.isNaN(m)) return '—'
  return m >= 12 ? `${Math.floor(m / 12)} 岁 ${m % 12} 月` : `${m} 月`
}

/**
 * 儿童性别文案
 * @param p 档案对象
 * @returns 男/女/—
 */
function genderText(p: any): string {
  const g = p?.gender_label || p?.gender
  return g === 'male' ? '男' : g === 'female' ? '女' : g || '—'
}

/**
 * 宠物类型中文文案
 * @param p 档案对象（后端字段 pet_type: cat/dog）
 * @returns 猫/狗/—
 */
function petTypeText(p: any): string {
  const t = p?.pet_type
  return t === 'cat' ? '猫' : t === 'dog' ? '狗' : '—'
}

/**
 * 儿童过敏文案（后端 allergy 为字符串数组，无记录视为无过敏）
 * @param p 档案对象
 * @returns 过敏文案（空串代表无过敏）
 */
function allergyText(p: any): string {
  const raw = p?.allergy
  const a = (Array.isArray(raw) ? raw.join('、') : String(raw || '')).trim()
  return !a || a === '无' ? '' : a
}

/**
 * 宠物绝育文案
 * @param p 档案对象（后端字段 neutered_flag）
 * @returns 已绝育/未绝育/不详（未知返回空）
 */
function sterileText(p: any): string {
  if (p?.neutered_flag === true) return '已绝育'
  if (p?.neutered_flag === false) return '未绝育'
  return ''
}

/**
 * 拉取两类档案
 */
async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    const [c, p]: any = await Promise.all([getChildren(), getPets()])
    // 后端契约：GET /profiles/children → data.children（data 为 null 时防御为数组）
    children.value = c?.children || c?.items || (Array.isArray(c) ? c : [])
    pets.value = p?.pets || p?.items || (Array.isArray(p) ? p : [])
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

/**
 * 设为当前问答对象
 * @param p 档案对象
 */
async function setCurrent(p: any): Promise<void> {
  try {
    await setCurrentProfile({ profile_type: tab.value, profile_uid: p.uid })
    user.setCurrentProfile(p.uid)
    ElMessage.success('已设为当前问答对象')
  } catch (e: any) {
    ElMessage.error(e?.message || '设置失败')
  }
}

/**
 * 跳转新建（按当前 tab）
 */
function goNew(): void {
  router.push(tab.value === 'child' ? '/app/profiles/child/new' : '/app/profiles/pet/new')
}

/**
 * 跳转编辑
 * @param p 档案对象
 */
function goEdit(p: any): void {
  router.push(`/app/profiles/${tab.value === 'child' ? 'child' : 'pet'}/${p.uid}/edit`)
}

/**
 * 打开删除确认
 * @param p 档案对象
 */
function askDelete(p: any): void {
  deleting.value = p
  delVisible.value = true
}

/**
 * 删除完成回调：刷新列表
 */
function onDeleted(): void {
  load()
}

watch(tab, () => void 0)
onMounted(load)
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-5);

  .head-back {
    width: 36px;
    height: 36px;
    border: none;
    background: none;
    color: var(--ink-1);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    svg {
      width: 22px;
      height: 22px;
    }
  }

  .head-title {
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }

  .head-space {
    width: 36px;
  }
}

/* ---------- 分段切换 ---------- */
.seg-tabs {
  display: flex;
  gap: var(--sp-2);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: 4px;
  margin-bottom: var(--sp-4);

  .seg {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--sp-2);
    padding: 9px 0;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--ink-2);
    font-size: var(--fs-sub);
    cursor: pointer;

    svg {
      width: 17px;
      height: 17px;
    }

    em {
      font-style: normal;
      font-size: var(--fs-caption);
      color: var(--ink-3);
    }

    &.on {
      background: var(--accent);
      color: var(--sc-lowest);
      font-weight: 600;

      em {
        color: var(--sc-lowest);
        opacity: 0.85;
      }
    }
  }
}

/* ---------- 配额刻度行 ---------- */
.quota-strip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-4) var(--sp-5);
  margin-bottom: var(--sp-4);

  .quota-label {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-caption);
    color: var(--ink-1);
    font-weight: 500;

    .dot {
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: var(--accent);
      flex: none;
    }
  }

  .quota-val b {
    color: var(--ink-1);
  }
}

.retry {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  align-items: center;
  color: var(--ink-2);
}

/* ---------- 档案卡 ---------- */
.profile-card {
  margin-bottom: var(--sp-4);

  &.current {
    border: 1.5px solid var(--accent);
  }
}

.pc-head {
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg {
    width: 26px;
    height: 26px;
  }
}

.pc-titles {
  flex: 1;
  min-width: 0;
}

.pc-name {
  font-size: var(--fs-body);
  font-weight: 700;
  color: var(--ink-1);
  display: flex;
  align-items: center;
  gap: var(--sp-2);

  .verify-ico {
    width: 16px;
    height: 16px;
    flex: none;
  }
}

.pc-state {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--accent);

  &.dim {
    color: var(--ink-3);
  }
}

/* 角色/操作按钮 */
.role-btn {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--accent);
  background: transparent;
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 600;
  cursor: pointer;

  i {
    font-style: normal;
  }

  &.solid {
    background: var(--accent);
    color: var(--sc-lowest);
    cursor: default;
  }
}

/* 信息块 */
.pc-info {
  background: var(--sc-low);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
  margin-top: var(--sp-3);

  .info-line1 {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-size: var(--fs-sub);
    color: var(--ink-1);
    font-weight: 500;

    .sep {
      font-style: normal;
      color: var(--ink-3);
    }

    .mask-ico {
      width: 14px;
      height: 14px;
      color: var(--ink-3);
    }
  }

  .info-chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--sp-2);
    margin-top: var(--sp-3);
  }
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  border-radius: 4px;
  border: 1px solid var(--line);
  background: var(--surface);
  font-size: var(--fs-caption);
  color: var(--ink-2);

  svg {
    width: 13px;
    height: 13px;
    color: var(--ink-3);
  }

  &.gray {
    background: var(--surface-2);
    color: var(--ink-2);
  }

  &.amber {
    background: var(--warn-soft);
    color: var(--warn);
    border-color: transparent;
  }
}

/* 操作行 */
.pc-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-3);
  margin-top: var(--sp-4);

  .pc-act {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 16px;
    border-radius: var(--radius-ctl);
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--ink-2);
    font-size: var(--fs-caption);
    font-weight: 500;
    cursor: pointer;

    svg {
      width: 14px;
      height: 14px;
    }

    &.danger {
      border-color: var(--danger);
      color: var(--danger);
      background: var(--danger-soft);
    }
  }
}

/* ---------- 新建主按钮 ---------- */
.add-btn {
  width: 100%;
  height: 48px;
  font-size: var(--fs-body);
  letter-spacing: 0.04em;
  margin: var(--sp-2) 0 var(--sp-4);

  .add-plus {
    font-weight: 400;
    margin-right: 4px;
  }
}

/* ---------- 容量配额卡 ---------- */
.capacity-card {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-4) var(--sp-5);
  margin-bottom: var(--sp-5);

  .cap-ico {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-ctl);
    background: var(--accent-soft);
    color: var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
    flex: none;

    svg {
      width: 20px;
      height: 20px;
    }
  }

  .cap-text {
    flex: 1;
    min-width: 0;

    .cap-title {
      font-size: var(--fs-sub);
      font-weight: 600;
      color: var(--ink-1);
    }
  }

  .cap-expand {
    flex: none;
    padding: 6px 14px;
    border-radius: var(--radius-ctl);
    border: none;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: var(--fs-caption);
    font-weight: 600;
    cursor: pointer;
  }
}

/* ---------- AI 免责条 ---------- */
/* 页面骨架：内容不足一屏时免责条贴底，不在中部漂浮 */
.pl-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;

  > .empty {
    flex: 1;
    justify-content: center;
  }
}

.ai-note {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 5px;
  margin-top: auto;
  padding-top: var(--sp-4);

  svg {
    width: 14px;
    height: 14px;
  }
}
</style>

<!--
  HomePage SC-02 首页：小光景共居观察图谱。
  主视觉连接真实孩子/宠物档案与安全、育儿、宠物观察视角；下方保留问答、测评和会员功能。
-->
<template>
  <div class="page">
    <!-- ===== 品牌行 ===== -->
    <header class="home-head">
      <div class="head-brand">
        <h1 class="brand-name">小光景</h1>
        <p class="brand-slogan">养娃养宠，先问一句</p>
      </div>
      <div class="head-actions">
        <button
          class="icon-btn touch-target"
          type="button"
          :aria-label="theme.isDark ? '切换到浅色模式' : '切换到深色模式'"
          @click="theme.toggle()"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              v-if="theme.isDark"
              d="M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-13V2m0 20v-2m8-8h2M2 12h2m13.7-5.7 1.4-1.4M4.9 19.1l1.4-1.4m0-11.4L4.9 4.9m14.2 14.2-1.4-1.4"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
            />
            <path
              v-else
              d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linejoin="round"
            />
          </svg>
        </button>
        <router-link to="/app/me" class="icon-btn touch-target" aria-label="我的">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="8.5" r="3.5" stroke="currentColor" stroke-width="1.75" />
            <path d="M5 19.5c1.2-3.2 3.8-5 7-5s5.8 1.8 7 5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </router-link>
      </div>
    </header>

    <main class="home-content">
      <section class="home-scene" aria-labelledby="home-thesis">
        <div class="scene-copy">
          <p class="scene-mark">小光景 · 共居观察</p>
          <h2 id="home-thesis">一个家的事，<br /><span>放在一起看。</span></h2>
          <p class="scene-note">孩子、宠物与日常安全，回到同一个生活场景里。</p>
        </div>
        <HouseholdMap
          :children="children"
          :pets="pets"
          :current-uid="user.currentProfileUid"
          @select="pickSubject"
          @create="$router.push('/app/profiles')"
        />
      </section>

    <!-- ===== 提问工作台 ===== -->
    <section class="ask-card question-desk">
      <!-- 顶边标尺带：1px 竖刻度 @8px 周期（器械物件签名） -->
      <div class="ruler-band" aria-hidden="true" />

      <!-- 范围指示行：当前问答对象 + 今日剩余（点左侧换对象） -->
      <div class="range-row">
        <button class="range-pick" type="button" aria-label="选择问答对象" @click="profileOpen = true">
          <span class="range-dot" aria-hidden="true" />
          <span v-if="loading || loadFailed" class="range-loading" aria-hidden="true" />
          <template v-else>
            <span class="range-name">{{ subjectName }}</span>
            <span v-if="subjectMeta" class="range-meta">{{ subjectMeta }}</span>
          </template>
          <svg class="range-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m8 10 4 4 4-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <span v-if="loading || loadFailed" class="quota-mini" aria-hidden="true">
          <i class="qm-skel" />
        </span>
        <span v-else-if="user.quotaUnlimited" class="quota-mini">
          <span class="qm-text numeric">不限次</span>
        </span>
        <span v-else class="quota-mini">
          <span class="qm-text numeric">今日剩 <b>{{ user.quotaRemaining }}</b>/{{ user.quotaLimit }}</span>
          <span
            v-if="segCount"
            class="qm-segs"
            role="img"
            :aria-label="`今日剩余 ${user.quotaRemaining} 次，共 ${user.quotaLimit} 次`"
          >
            <i v-for="i in segCount" :key="i" :class="{ filled: i <= user.quotaRemaining }" />
          </span>
        </span>
      </div>

      <h2 class="ask-lead">今天发生了什么？</h2>
      <input
        v-model="askText"
        class="ask-input"
        type="text"
        enterkeyhint="send"
        aria-label="输入你的问题"
        placeholder="把情况说得具体一点…"
        @keydown.enter="onEnter"
      />
      <el-button
        type="primary"
        size="large"
        class="ask-btn"
        :disabled="!askText.trim()"
        @click="submitAsk()"
      >
        问一下
      </el-button>
      <div class="ask-chips">
        <button
          v-for="c in exampleChips"
          :key="c"
          class="chip touch-target"
          type="button"
          @click="submitAsk(c)"
        >
          {{ c }}
        </button>
      </div>

      <!-- 远程数据失败：内联降级提示，不挡提问 -->
      <p v-if="loadFailed" class="sync-note">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" />
          <path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
        <span>档案与额度暂未同步，提问不受影响</span>
        <button class="sync-retry" type="button" @click="load">重试</button>
      </p>
    </section>

    <!-- ===== 功能行组：测评 + 三大问答 ===== -->
    <section class="rows">
      <button class="row row--assessment" type="button" @click="goAssessment">
        <span class="row-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M4 17h16" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            <path d="M7 17v-4M12 17v-7M17 17v-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            <circle cx="12" cy="7.5" r="2" fill="currentColor" />
          </svg>
        </span>
        <span class="row-text">
          <span class="row-name">四象宝宝气质测评</span>
          <span class="row-desc">{{ resumeMeta }}</span>
        </span>
        <span class="row-tail">
          <span class="row-action">{{ resumeAction }}</span>
          <svg class="row-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m9.5 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </button>

      <router-link to="/app/qa/parenting" class="row">
        <span class="row-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12.5" r="8.5" stroke="currentColor" stroke-width="1.75" />
            <path d="M8.6 14c.9 1.3 2 2 3.4 2s2.5-.7 3.4-2" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            <path d="M9.2 10h.01M14.8 10h.01" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
          </svg>
        </span>
        <span class="row-text">
          <span class="row-name">0-6岁宝宝养育</span>
          <span class="row-desc">发育里程碑、辅食与行为引导</span>
        </span>
        <span class="row-tail">
          <svg class="row-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m9.5 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </router-link>

      <router-link to="/app/qa/pet" class="row">
        <span class="row-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <ellipse cx="7" cy="8.5" rx="2.1" ry="2.6" stroke="currentColor" stroke-width="1.75" />
            <ellipse cx="12" cy="7" rx="2.1" ry="2.8" stroke="currentColor" stroke-width="1.75" />
            <ellipse cx="17" cy="8.5" rx="2.1" ry="2.6" stroke="currentColor" stroke-width="1.75" />
            <ellipse cx="20" cy="13" rx="1.6" ry="2" stroke="currentColor" stroke-width="1.75" />
            <path
              d="M12 11.4c2.7 0 4.9 2 4.9 4.4 0 1.7-1.3 2.8-2.9 2.8-.8 0-1.4-.3-2-.3s-1.2.3-2 .3c-1.6 0-2.9-1.1-2.9-2.8 0-2.4 2.2-4.4 4.9-4.4Z"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <span class="row-text">
          <span class="row-name">猫狗宠物饲养</span>
          <span class="row-desc">疫苗驱虫、行为纠正与营养配比</span>
        </span>
        <span class="row-tail">
          <svg class="row-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m9.5 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </router-link>

      <router-link to="/app/qa/family" class="row">
        <span class="row-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5v7a2.5 2.5 0 0 1-2.5 2.5H12l-4.5 4v-4h-1A2.5 2.5 0 0 1 4 14.5v-7Z"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linejoin="round"
            />
            <path d="M8 9.5h8M8 12.5h5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </span>
        <span class="row-text">
          <span class="row-name">家庭综合问答</span>
          <span class="row-desc">孩子和宠物同场景的问题，一次答全</span>
        </span>
        <span class="row-tail">
          <svg class="row-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m9.5 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </router-link>
    </section>

    <!-- ===== 会员专属权益卡 ===== -->
    <section class="card member-card">
      <div class="member-head">
        <h2 class="member-title">会员专属权益</h2>
        <span class="st-tag st-tag--outline guard-badge">升级护航</span>
      </div>
      <p class="member-desc">
        深度方案 · 月度计划 · 专属档案，全方位守护多宝家庭健康成长。
      </p>
      <el-button plain class="member-btn" @click="$router.push('/app/member')">
        {{ user.isMember ? '查看' : '了解会员' }}
      </el-button>
    </section>
    </main>

    <!-- 问答对象选择弹层（受控：由范围行唤起） -->
    <ProfileSwitcher
      v-model:open="profileOpen"
      :model-value="user.currentProfileUid"
      @update:model-value="pickSubject"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import { getChildren, getPets, getQuota } from '@/api/client'
import ProfileSwitcher from '@/components/ProfileSwitcher.vue'
import HouseholdMap from '@/components/HouseholdMap.vue'

const router = useRouter()
const user = useUserStore()
const theme = useThemeStore()

/** 测评断点 uid 键名（与测评页共享的 sessionStorage 键） */
const ASSESS_UID_KEY = 'jiaban_assessment_uid'
/** 测评已答数键名 */
const ASSESS_ANSWERED_KEY = 'jiaban_assessment_answered'
/** 测评总题数（真实题数固定 16） */
const ASSESS_TOTAL = 16

/** 白天/夜间示例问题（按当前对象切换；夜间用夜里真的会问的） */
const CHILD_EXAMPLES = ['夜里频繁醒', '不肯吃辅食', '入托分离焦虑']
const PET_EXAMPLES = ['猫哈气不让抱', '狗狗拆家', '驱虫后没精神']
const CHILD_NIGHT = ['夜醒频繁', '发烧怎么办', '不肯睡']
const PET_NIGHT = ['夜里咳嗽', '呕吐', '不肯吃']

/** 加载态（只影响范围行与额度，页面其余部分立即可用） */
const loading = ref(true)
/** 同步失败态（内联提示，不阻塞提问） */
const loadFailed = ref(false)
/** 孩子档案 */
const children = ref<any[]>([])
/** 宠物档案 */
const pets = ref<any[]>([])
/** 提问输入 */
const askText = ref('')
/** 对象选择弹层开关 */
const profileOpen = ref(false)
/** 测评断点（sessionStorage 与测评页共享：uid + 已答数） */
const assessmentResume = ref<{ uid: string; answered: number } | null>(null)

/** 当前问答对象（uid 失效时回落 null → 通用参考） */
const subject = computed<{ kind: 'child' | 'pet'; name: string; meta: string } | null>(() => {
  const uid = user.currentProfileUid
  if (!uid) return null
  const c = children.value.find((x) => x.uid === uid)
  if (c) {
    const g = c.gender_label || c.gender || ''
    const a = c.age_months ? `${c.age_months}个月` : ''
    return { kind: 'child', name: c.nickname || '宝宝', meta: [g, a].filter(Boolean).join(' · ') }
  }
  const p = pets.value.find((x) => x.uid === uid)
  if (p) return { kind: 'pet', name: p.nickname || '宠物', meta: p.species_label || p.species || '' }
  return null
})

/** 范围行左侧显示名（无档案 → 与问答页口径一致的通用回落） */
const subjectName = computed(() => subject.value?.name || '通用 1-3 岁参考')
/** 范围行副注（性别·月龄 / 物种） */
const subjectMeta = computed(() => subject.value?.meta || '')

/** 额度段刻度数量（≤8 直显，超出只留文字） */
const segCount = computed(() => {
  const n = Number(user.quotaLimit || 0)
  return n > 0 && n <= 8 ? n : 0
})

/** 示例问题 chips（按对象与主题切换） */
const exampleChips = computed<string[]>(() => {
  const petMode = subject.value?.kind === 'pet'
  if (theme.isDark) return petMode ? PET_NIGHT : CHILD_NIGHT
  return petMode ? PET_EXAMPLES : CHILD_EXAMPLES
})

/** 测评行副注：诚实说真话（sessionStorage 断点只在本标签页有效，不承诺「已保存」） */
const resumeMeta = computed(() => {
  const r = assessmentResume.value
  if (!r) return '16 题 · 约 3 分钟'
  return `已答 ${Math.min(r.answered, ASSESS_TOTAL)}/${ASSESS_TOTAL}`
})

/** 测评行动作文案：开始 / 继续 / 查看报告 */
const resumeAction = computed(() => {
  if (!assessmentResume.value) return '开始'
  return assessmentResume.value.answered >= ASSESS_TOTAL ? '查看报告' : '继续'
})

/**
 * 测评行点击路由：无断点去介绍页；有断点答满去报告；否则续答
 */
function goAssessment(): void {
  const r = assessmentResume.value
  if (!r) router.push('/app/assessment')
  else if (r.answered >= ASSESS_TOTAL) router.push(`/app/assessment/report/${r.uid}`)
  else router.push(`/app/assessment/run/${r.uid}`)
}

/**
 * 恢复测评断点（与 AssessmentIntroPage/RunPage 的 sessionStorage 约定一致）
 */
function restoreResume(): void {
  const uid = sessionStorage.getItem(ASSESS_UID_KEY) || ''
  if (uid) {
    assessmentResume.value = {
      uid,
      answered: Number(sessionStorage.getItem(ASSESS_ANSWERED_KEY) || 0)
    }
  } else {
    assessmentResume.value = null
  }
}

/**
 * 提交提问：按当前对象路由到对应问答页并携带 ?q=（由问答页预填并自动提问）
 * @param text 显式文本（示例 chips）；缺省取输入框
 */
function submitAsk(text?: string): void {
  const q = (text ?? askText.value).trim()
  if (!q) return
  const base = subject.value?.kind === 'pet' ? '/app/qa/pet' : '/app/qa/parenting'
  askText.value = ''
  router.push({ path: base, query: { q } })
}

/**
 * 回车发送：跳过中文输入法组词确认（isComposing）
 * @param e 键盘事件
 */
function onEnter(e: KeyboardEvent): void {
  if (e.isComposing) return
  submitAsk()
}

/**
 * 切换当前问答对象并持久化
 * @param uid 档案 uid
 */
function pickSubject(uid: string | null): void {
  user.setCurrentProfile(uid)
}

/**
 * 校验/补全当前问答对象：失效则清除；未选且有档案则取第一个孩子，其次第一个宠物
 */
function ensureSubject(): void {
  const all = [...children.value, ...pets.value]
  const cur = user.currentProfileUid
  if (cur && all.some((p) => p.uid === cur)) return
  user.setCurrentProfile(children.value[0]?.uid ?? pets.value[0]?.uid ?? null)
}

/**
 * 加载首页数据：额度 + 档案列表（失败只降级为内联提示，不挡提问）
 */
async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  restoreResume()
  try {
    const [quota, childRes, petRes] = await Promise.all([
      getQuota(),
      getChildren().catch(() => [] as any[]),
      getPets().catch(() => [] as any[])
    ])
    user.quotaUsed = quota.used ?? 0
    user.quotaUnlimited = quota.unlimited === true
    if (typeof quota.limit === 'number') user.quotaLimit = quota.limit
    if (typeof quota.remaining === 'number') user.quotaRemaining = quota.remaining
    const cl: any = (childRes as any)?.children || childRes
    const pl: any = (petRes as any)?.pets || petRes
    children.value = Array.isArray(cl) ? cl : []
    pets.value = Array.isArray(pl) ? pl : []
    ensureSubject()
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
/* ---------- 品牌行 ---------- */
.home-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-6);

  .head-brand {
    min-width: 0;
  }

  .brand-name {
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
    letter-spacing: 0.02em;
  }

  .brand-slogan {
    margin-top: 2px;
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }

  .head-actions {
    display: flex;
    gap: var(--sp-2);
    flex: none;
  }
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--sc-low);
  color: var(--ink-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;

  &:hover,
  &:focus-visible {
    background: var(--accent-soft);
    border-color: var(--accent-line);
    color: var(--accent);
  }

  svg {
    width: 18px;
    height: 18px;
  }
}

/* ---------- 提问卡 ---------- */
.ask-card {
  position: relative;
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  box-shadow: var(--shadow-e1);
  padding: var(--sp-6);
  margin-bottom: var(--sp-4);
}

/* 签名时刻①：提问卡顶边标尺带（--art-line 刻度 @8px 周期，两主题均 ≥3:1） */
.ruler-band {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 8px;
  background-image: repeating-linear-gradient(
    to right,
    var(--art-line) 0 1px,
    transparent 1px 8px
  );
  background-size: 8px 4px;
  background-position: 12px 0;
  background-repeat: repeat-x;
  pointer-events: none;
}

/* 范围指示行：当前对象（可换）+ 今日剩余；底线 = 量具零线 */
.range-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding-top: var(--sp-2);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--line);
  margin-bottom: var(--sp-5);
}

.range-pick {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
  min-height: 28px;
  padding: 0;
  border: none;
  background: none;
  font-family: inherit;
  font-size: var(--fs-sub);
  color: var(--ink-1);
  cursor: pointer;

  .range-dot {
    flex: none;
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }

  .range-name {
    font-weight: 600;
    color: var(--ink-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .range-meta {
    font-size: var(--fs-caption);
    color: var(--ink-3);
    white-space: nowrap;
  }

  .range-chev {
    flex: none;
    width: 16px;
    height: 16px;
    color: var(--ink-3);
    transition: color 0.15s ease;
  }

  &:hover .range-chev,
  &:focus-visible .range-chev {
    color: var(--accent);
  }
}

.range-loading {
  width: 76px;
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--line) 37%, var(--surface-2) 63%);
  background-size: 400% 100%;
  animation: jiaban-shimmer 1.4s ease infinite;
}

/* 额度骨架：同步失败时保留骨架形状，不说假数字 */
.qm-skel {
  display: block;
  width: 64px;
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--line) 37%, var(--surface-2) 63%);
  background-size: 400% 100%;
  animation: jiaban-shimmer 1.4s ease infinite;
}

.quota-mini {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;

  .qm-text {
    font-size: var(--fs-caption);
    color: var(--ink-3);
    white-space: nowrap;

    b {
      font-size: var(--fs-sub);
      font-weight: 700;
      color: var(--ink-1);
    }
  }

  .qm-segs {
    display: flex;
    gap: 3px;

    i {
      width: 10px;
      height: 4px;
      border-radius: 2px;
      background: var(--surface-2);

      &.filled {
        background: var(--accent);
      }
    }
  }
}

.ask-lead {
  margin-bottom: var(--sp-4);
  font-size: var(--fs-sub);
  color: var(--ink-2);
}

.ask-input {
  display: block;
  width: 100%;
  height: 46px;
  padding: 0 var(--sp-6);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  background: var(--bg);
  font-family: inherit;
  font-size: var(--fs-body);
  color: var(--ink-1);

  &::placeholder {
    color: var(--ink-3);
  }
}

.ask-btn {
  width: 100%;
  height: 48px;
  margin-top: var(--sp-4);
  font-size: var(--fs-body);
  letter-spacing: 0.06em;
}

.ask-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
}

.chip {
  display: inline-flex;
  align-items: center;
  height: 32px;
  max-width: 100%;
  padding: 0 var(--sp-6);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-pill);
  background: transparent;
  font-family: inherit;
  font-size: var(--fs-caption);
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;

  &:hover,
  &:focus-visible {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
  }
}

.sync-note {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  margin-top: var(--sp-5);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.5;

  svg {
    flex: none;
    width: 15px;
    height: 15px;
    color: var(--warn);
  }

  span {
    flex: 1;
    min-width: 0;
  }

  .sync-retry {
    flex: none;
    padding: 0;
    border: none;
    background: none;
    font-family: inherit;
    font-size: var(--fs-caption);
    font-weight: 600;
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
  }
}

/* ---------- 功能行组 ----------
   一张面 + 行间发丝线分节（刻意不用多张等大卡片）。 */
.rows {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  box-shadow: var(--shadow-e1);
  margin-bottom: var(--sp-4);
  overflow: hidden;
}

.row {
  display: flex;
  align-items: center;
  gap: var(--sp-6);
  width: 100%;
  padding: var(--sp-6);
  border: none;
  border-top: 1px solid var(--line);
  background: transparent;
  font-family: inherit;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.15s ease;

  &:first-child {
    border-top: none;
  }

  &:hover,
  &:focus-visible {
    background: var(--sc-low);

    .row-chev {
      color: var(--accent);
      transform: translateX(2px);
    }
  }
}

.row-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg {
    width: 24px;
    height: 24px;
  }
}

.row-text {
  flex: 1;
  min-width: 0;
}

.row-name {
  display: block;
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--ink-1);
}

.row-desc {
  display: block;
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.6;
}

.row-tail {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
}

.row-action {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}

.row-chev {
  width: 18px;
  height: 18px;
  color: var(--ink-3);
  flex-shrink: 0;
  transition: color 0.15s ease, transform 0.15s ease;
}

/* ---------- 会员专属权益卡 ---------- */
.member-card {
  .member-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--sp-3);
    margin-bottom: var(--sp-3);

    .member-title {
      font-size: var(--fs-title);
      font-weight: 700;
      color: var(--ink-1);
    }

    .guard-badge {
      flex: none;
      border-color: var(--line);
      background: var(--sc-low);
      font-weight: 500;
      color: var(--ink-2);
    }
  }

  .member-desc {
    font-size: var(--fs-sub);
    color: var(--ink-2);
    line-height: 1.7;
    margin-bottom: var(--sp-6);
  }

  /* 次级操作用描边按钮：主色实底只留给每页唯一的主操作 */
  .member-btn {
    width: 100%;
    height: 44px;
    font-weight: 600;
    background: transparent;
    border-color: var(--accent-line);
    color: var(--accent);

    &:hover,
    &:focus-visible {
      background: var(--accent-soft);
      border-color: var(--accent);
      color: var(--accent);
    }
  }
}

/* 家庭观察档案：首屏像一页正在展开的记录，而不是入口卡片集合。 */
.home-head {
  align-items: flex-start;
  padding: var(--sp-2) 2px 0;
  margin-bottom: var(--sp-8);

  .brand-name {
    font-size: 25px;
    line-height: 1.15;
  }

  .brand-slogan {
    margin-top: 5px;
  }
}

.icon-btn {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-ctl);
  background: var(--surface);
}

.ask-card {
  padding: 28px 20px 20px;
  margin-bottom: var(--sp-8);
  border-radius: 8px 8px 8px 28px;
  box-shadow: none;
}

.ruler-band {
  left: 20px;
  right: 20px;
  height: 10px;
}

.range-row {
  padding-top: var(--sp-3);
  padding-bottom: var(--sp-3);
  margin-bottom: 22px;
}

.ask-lead {
  max-width: 11em;
  margin-bottom: 20px;
  color: var(--ink-1);
  font-size: 25px;
  font-weight: 650;
  line-height: 1.32;
  text-wrap: balance;
}

.ask-input {
  height: 52px;
  padding-inline: 14px;
  background: var(--bg);
}

.ask-btn {
  height: 48px;
  margin-top: 12px;
  letter-spacing: 0;
}

.ask-chips {
  justify-content: flex-end;
  gap: 6px;
  margin-top: 12px;
}

.chip {
  height: auto;
  min-height: 36px;
  padding: 5px 10px;
  border-color: var(--line);
  border-radius: 8px;
  line-height: 1.35;
  white-space: normal;
  text-align: left;
}

.rows {
  margin-bottom: var(--sp-8);
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  overflow: visible;
}

.row {
  min-height: 76px;
  padding: 12px 8px;
  gap: 12px;
}

.row--assessment {
  min-height: 96px;
  margin: 0 0 8px 16px;
  padding: 16px;
  border: 1px solid var(--accent-line);
  border-radius: 8px;
  background: var(--accent-soft);

  .row-icon {
    width: 44px;
    height: 44px;
    color: var(--on-accent);
    background: var(--accent);
  }

  .row-desc {
    color: var(--ink-2);
  }
}

.row:not(.row--assessment) {
  border-top: 1px solid var(--line);
}

.row:not(.row--assessment) .row-icon {
  width: 36px;
  height: 36px;
  background: transparent;
}

.member-card {
  padding: 18px;
  border-radius: 8px;
  background: var(--surface-2);

  .member-desc {
    max-width: 34ch;
  }
}

@media (max-width: 360px) {
  .ask-card {
    padding-inline: 16px;
  }

  .range-row {
    align-items: flex-start;
  }

  .quota-mini .qm-segs {
    display: none;
  }

  .row-action {
    display: none;
  }
}
</style>

<style lang="scss" scoped>
.home-content {
  display: grid;
  gap: 24px;
}

.home-scene {
  display: grid;
  gap: 14px;
  padding: 4px 0 2px;
}

.scene-copy {
  position: relative;
  padding-left: 16px;

  &::before {
    position: absolute;
    top: 4px;
    bottom: 5px;
    left: 0;
    width: 1px;
    background: var(--line-strong);
    content: '';
  }
}

.scene-mark {
  margin-bottom: 8px;
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 600;
}

.scene-copy h2 {
  color: var(--ink-1);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.22;
  text-wrap: balance;

  span { color: var(--accent); }
}

.scene-note {
  max-width: 32ch;
  margin-top: 8px;
  color: var(--ink-2);
  font-size: var(--fs-caption);
  line-height: 1.55;
}

.question-desk {
  padding: 18px 16px 16px;
  border-radius: 4px 14px 14px 14px;
  box-shadow: var(--shadow-e1);
}

.question-desk .range-row {
  margin-bottom: 16px;
}

.question-desk .ask-lead {
  max-width: none;
  margin-bottom: 12px;
  font-size: 20px;
  line-height: 1.3;
}

.question-desk .ask-chips {
  justify-content: flex-start;
  gap: 7px;
}

.question-desk .chip {
  min-height: 34px;
  border-color: var(--line-strong);
}

.rows {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: stretch;
  gap: 0 12px;
}

.row--assessment {
  position: relative;
  grid-column: 1 / -1;
  min-height: 112px;
  margin-left: 18px;
  margin-bottom: 8px;
  overflow: hidden;
  border: 0;
  border-radius: 4px 14px 14px 14px;
  background: var(--accent);
  color: var(--on-accent);

  &::after {
    position: absolute;
    right: 12px;
    bottom: -28px;
    width: 112px;
    height: 112px;
    border: 1px solid rgb(255 255 255 / 24%);
    border-radius: 50%;
    box-shadow: 0 0 0 10px rgb(255 255 255 / 5%), 0 0 0 22px rgb(255 255 255 / 4%);
    content: '';
    pointer-events: none;
  }

  .row-name,
  .row-action,
  .row-chev { color: var(--on-accent); }

  .row-desc { color: #e2f0eb; }

  .row-icon {
    width: 46px;
    height: 46px;
    border-radius: 12px 12px 12px 3px;
    background: rgb(255 255 255 / 14%);
    color: var(--on-accent);
  }

  &:hover,
  &:focus-visible { background: var(--accent-press); }
}

.row:not(.row--assessment) {
  min-height: 84px;
  padding: 10px 4px;
  border-top: 1px solid var(--line);
}

.row:nth-of-type(2) .row-icon { color: var(--perspective-child); }
.row:nth-of-type(3) .row-icon { color: var(--perspective-pet); }

.row:not(.row--assessment) .row-name { font-size: var(--fs-sub); }
.row:not(.row--assessment) .row-desc { font-size: 11px; }

.member-card {
  position: relative;
  margin-left: 18px;
  padding: 16px;
  border-radius: 4px 12px 12px 12px;
}

@media (max-width: 360px) {
  .home-content { gap: 20px; }
  .scene-copy h2 { font-size: 25px; }
  .rows { gap: 0 8px; }
  .row { gap: 8px; }
  .row--assessment { margin-left: 8px; padding: 12px; }
  .row:not(.row--assessment) { padding-inline: 0; }
  .member-card { margin-left: 8px; }
}
</style>

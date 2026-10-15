<!--
  AssessmentIntroPage SC-14 测评引导（Stitch 稿重构）
  版式：页头（‹ 四象宝宝气质测评）→ 继续上次填写卡（进度徽章 + 刻度进度条 + 三段标注 +
  直接恢复链接）→ 主介绍卡（▎标题 + 这是什么绿块 / 这不是什么红块 + 参数矩阵 + 已选档案行）→
  作答建议卡 → 底部固定区（开始测评主按钮 + 引导提示 + AI 免责条）。
  合规：不出现"心理诊断/治疗/科学测评/信效度"等词；四象仅为趣味包装命名。
-->
<template>
  <div class="intro-page">
    <!-- ===== 页头：返回 + 居中标题 ===== -->
    <header class="intro-head">
      <button class="head-back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">四象宝宝气质测评</h1>
    </header>

    <main class="intro-main">
      <!-- ===== 继续上次填写卡（有断点时置顶显示） ===== -->
      <section v-if="resumeUid" class="st-card resume-card" role="button" tabindex="0" @click="resume" @keydown.enter="resume">
        <div class="resume-top">
          <div class="resume-title">
            <span class="dot" />
            <span>继续上次填写 · 第 {{ resumeAnswered + 1 }} / {{ TOTAL }} 题</span>
          </div>
          <span class="resume-badge numeric">{{ resumePct }}%</span>
        </div>
        <!-- 刻度量具进度带 + 三段标注 -->
        <div class="resume-meter">
          <div class="st-meter"><div class="st-meter__fill" :style="{ width: resumePct + '%' }" /></div>
          <div class="meter-marks caption">
            <span>起点 (第 1 题)</span>
            <span class="mark-done">已答 {{ resumeAnswered }} 题</span>
            <span>终点 (第 {{ TOTAL }} 题)</span>
          </div>
        </div>
        <div class="resume-foot">
          <p class="caption">断点已保存，可随时继续；断点保留 90 天</p>
          <span class="resume-link">直接恢复
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
        </div>
      </section>

      <!-- ===== 主介绍卡 ===== -->
      <section class="st-card intro-card">
        <!-- 标题组：图标 + 主标 + 中性命名副标 -->
        <div class="intro-head-group">
          <div class="intro-title">
            <svg class="title-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.75" />
              <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1M7.7 16.3l-2.1 2.1" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            </svg>
            <h2>四象宝宝气质测评</h2>
          </div>
          <p class="intro-sub caption">四象为趣味包装名，四类用中性命名</p>
        </div>

        <!-- 这是什么（绿块：正面定义） -->
        <div class="what-block">
          <div class="what-head is-yes">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.75" />
              <path d="m8.5 12.2 2.4 2.4 4.6-5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>这是什么</span>
          </div>
          <p class="what-body">一份 0-6 岁通俗情境问卷，了解孩子近期的行为倾向，用于选择养育方式与亲子沟通方法。</p>
        </div>

        <!-- 这不是什么（红块：边界排除） -->
        <div class="what-block is-not">
          <div class="what-head">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.75" />
              <path d="M12 7.5v5.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
              <circle cx="12" cy="16.2" r="0.6" fill="currentColor" />
            </svg>
            <span>这不是什么</span>
          </div>
          <p class="what-body">非心理测评工具，非终身性格判定；不做诊断、治疗与心理评估；不算命、不判定天生注定。</p>
        </div>

        <!-- 参数规格矩阵 -->
        <div class="meta-matrix">
          <div class="meta-grid">
            <div class="meta-item">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.75" />
                <path d="M12 7.5V12l3 2" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span>预计 3 分钟 · {{ TOTAL }} 题 · 4 个维度</span>
            </div>
            <div class="meta-item">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <rect x="4" y="4" width="16" height="16" rx="2.5" stroke="currentColor" stroke-width="1.75" />
                <path d="M4 9.5h16M9.5 9.5V20" stroke="currentColor" stroke-width="1.75" />
              </svg>
              <span>题型：5 点情境选择题</span>
            </div>
          </div>
          <div class="meta-foot">
            <div class="meta-note">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.75" />
                <path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
              </svg>
              <span>仅供养育参考，不替代专业人士。</span>
            </div>
            <span class="dyn-chip">动态调整</span>
          </div>
        </div>

        <!-- 已选档案行（无档案显示通用区间出题提示） -->
        <div class="profile-row">
          <template v-if="currentChild">
            <span class="avatar">宝</span>
            <div class="profile-info">
              <span class="profile-name">已选档案：{{ currentChild.nickname }}（{{ ageText(currentChild) }}）</span>
              <span class="profile-birth caption">出生日期：{{ birthText(currentChild) }}<template v-if="genderText(currentChild)"> · {{ genderText(currentChild) }}宝</template></span>
            </div>
            <button class="switch-link" @click.stop="goProfiles">
              切换
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m8 9 4-4 4 4M8 15l4 4 4-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </template>
          <template v-else>
            <span class="avatar is-blank">?</span>
            <div class="profile-info">
              <span class="profile-name">未选择孩子档案</span>
              <span class="profile-birth caption">将以 0-6 岁通用区间出题，可先建立档案再开始</span>
            </div>
            <button class="switch-link touch-target" type="button" @click.stop="goProfiles">去选择</button>
          </template>
        </div>
      </section>

      <!-- ===== 作答建议卡 ===== -->
      <section class="st-card tip-card">
        <svg class="tip-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
          <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="tip-body">
          <span class="tip-title">作答建议</span>
          <p class="caption">请依据孩子近 1-2 个月在日常生活中的自然反应作答，无需追求"完美标准"，中立观察最具参考价值。</p>
        </div>
      </section>
    </main>

    <!-- ===== 底部固定操作区 ===== -->
    <footer class="intro-foot">
      <el-button type="primary" size="large" class="start-btn" :loading="starting" @click="start">
        {{ resumeUid ? '继续作答' : '开始测评' }}
        <svg v-if="!starting" class="btn-arrow" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </el-button>
      <p class="foot-hint caption">开始前建议先选好孩子档案</p>
      <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { startAssessment, getChildren } from '@/api/client'
import { newRequestId } from '@/api/request'
import { useUserStore } from '@/stores/user'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

const router = useRouter()
const userStore = useUserStore()

/** 冻结题量（PRD §12.2：16 题） */
const TOTAL = 16

/** 断点续答 uid（由 start 接口返回；此处从路由缓存恢复演示） */
const resumeUid = ref(sessionStorage.getItem('jiaban_assessment_uid') || '')
const resumeAnswered = ref(Number(sessionStorage.getItem('jiaban_assessment_answered') || 0))
/** 开始中 */
const starting = ref(false)
/** 孩子档案列表（用于"已选档案"行） */
const children = ref<any[]>([])

/** 当前选中的孩子档案（按 store 的 currentProfileUid 匹配） */
const currentChild = computed(() =>
  children.value.find((c) => c.uid === userStore.currentProfileUid) || null
)

/** 断点进度百分比（真实已答 / 16） */
const resumePct = computed(() =>
  Math.min(100, Math.round((resumeAnswered.value / TOTAL) * 100))
)

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
 * 出生日期文案（YYYY-MM-DD → YYYY 年 M 月 D 日）
 * @param p 档案对象
 * @returns 出生日期文案
 */
function birthText(p: any): string {
  const b = String(p?.birthdate || '')
  const [y, m, d] = b.split('-')
  if (!y) return '—'
  return d ? `${y} 年 ${Number(m)} 月 ${Number(d)} 日` : b
}

/**
 * 儿童性别文案
 * @param p 档案对象
 * @returns 男/女/空
 */
function genderText(p: any): string {
  const g = p?.gender_label || p?.gender
  return g === 'male' ? '男' : g === 'female' ? '女' : ''
}

/**
 * 拉取孩子档案（失败静默：仅影响"已选档案"行展示）
 */
async function loadChildren(): Promise<void> {
  try {
    const res: any = await getChildren()
    children.value = res?.children || res?.items || (Array.isArray(res) ? res : [])
  } catch {
    // 静默：档案行回退为"未选择"提示
  }
}

/**
 * 开始测评：调 start 接口拿实例 uid，跳作答页
 * @throws 接口失败消息提示
 */
async function start(): Promise<void> {
  starting.value = true
  try {
    const res: any = await startAssessment(userStore.currentProfileUid || undefined)
    const uid = res?.uid || res?.assessment_uid || newRequestId()
    sessionStorage.setItem('jiaban_assessment_uid', uid)
    sessionStorage.setItem('jiaban_assessment_answered', String(res?.answered_count || 0))
    router.push(`/app/assessment/run/${uid}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '开始失败，请重试')
  } finally {
    starting.value = false
  }
}

/**
 * 断点继续：进入作答页续填
 */
function resume(): void {
  router.push(`/app/assessment/run/${resumeUid.value}`)
}

/**
 * 跳转档案列表页（切换/选择孩子档案）
 */
function goProfiles(): void {
  router.push('/app/profiles')
}

onMounted(loadChildren)
</script>

<style lang="scss" scoped>
/* ===== 页面骨架：头 + 滚动主体 + 固定底部 ===== */
.intro-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

/* 页头：白底 + 居中标题 */
.intro-head {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  height: 48px;
  padding: 0 var(--sp-4);
  background: var(--surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);

  .head-back {
    flex: none;
    width: 32px;
    height: 32px;
    margin-left: -8px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: var(--ink-1);
    border-radius: 50%;
    cursor: pointer;

    svg {
      width: 24px;
      height: 24px;
    }
  }

  .head-title {
    flex: 1;
    text-align: center;
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
    padding-right: 24px; /* 视觉居中补偿 */
  }
}

/* 主体滚动区 */
.intro-main {
  flex: 1;
  padding: var(--sp-3) var(--sp-4) var(--sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

/* ===== 继续上次填写卡 ===== */
.resume-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  cursor: pointer;
  transition: box-shadow 0.2s ease;

  &:active {
    box-shadow: var(--shadow-e2);
  }
}

.resume-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.resume-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }
}

.resume-badge {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 500;
}

.resume-meter {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 三段标注：起点 / 已答 / 终点 */
.meter-marks {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: var(--ink-3);

  .mark-done {
    color: var(--accent);
    font-weight: 500;
  }
}

.resume-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 4px;
  border-top: 1px solid var(--line);

  p {
    color: var(--ink-3);
  }
}

.resume-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--accent);

  svg {
    width: 14px;
    height: 14px;
  }
}

/* ===== 主介绍卡 ===== */
.intro-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.intro-head-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.intro-title {
  display: flex;
  align-items: center;
  gap: 6px;

  .title-ico {
    width: 20px;
    height: 20px;
    color: var(--accent);
  }

  h2 {
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
  }
}

.intro-sub {
  color: var(--ink-3);
}

/* 这是什么 / 这不是什么 对比块 */
.what-block {
  border-radius: var(--radius-face);
  border: 1px solid var(--accent-line);
  background: color-mix(in srgb, var(--accent-soft) 70%, transparent);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 6px;

  /* 红块变体：边界排除 */
  &.is-not {
    background: color-mix(in srgb, var(--danger-soft) 50%, transparent);
    border-color: var(--line);

    .what-head {
      color: var(--danger);
    }
  }
}

.what-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--accent);

  svg {
    width: 16px;
    height: 16px;
  }
}

.what-body {
  padding-left: 20px;
  font-size: var(--fs-sub);
  line-height: 1.6;
  color: var(--ink-1);

  .is-not & {
    color: var(--ink-2);
  }
}

/* 参数规格矩阵 */
.meta-matrix {
  background: var(--sc-low);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-2);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);

  svg {
    flex: none;
    width: 16px;
    height: 16px;
    color: var(--ink-3);
  }
}

.meta-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--sp-2);
  border-top: 1px solid var(--line);
}

.meta-note {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-caption);
  color: var(--ink-3);

  svg {
    width: 14px;
    height: 14px;
    color: var(--warn);
  }
}

/* 「动态调整」chip */
.dyn-chip {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface);
  border: 1px solid var(--line);
  font-size: var(--fs-caption);
  color: var(--accent);
  white-space: nowrap;
}

/* 已选档案行 */
.profile-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  background: var(--sc-lowest);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-2) var(--sp-3);
}

.avatar {
  flex: none;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;

  &.is-blank {
    background: var(--surface-2);
    color: var(--ink-3);
  }
}

.profile-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;

  .profile-name {
    font-size: var(--fs-sub);
    font-weight: 500;
    color: var(--ink-1);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .profile-birth {
    color: var(--ink-3);
  }
}

.switch-link {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: none;
  background: none;
  font-size: var(--fs-caption);
  font-weight: 500;
  color: var(--accent);
  cursor: pointer;

  svg {
    width: 14px;
    height: 14px;
  }

  &:active {
    opacity: 0.7;
  }
}

/* ===== 作答建议卡 ===== */
.tip-card {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3);

  .tip-ico {
    flex: none;
    width: 18px;
    height: 18px;
    margin-top: 2px;
    color: var(--ink-2);
  }
}

.tip-body {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .tip-title {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }

  p {
    color: var(--ink-3);
    line-height: 1.5;
  }
}

/* ===== 底部固定操作区 ===== */
.intro-foot {
  position: sticky;
  bottom: 0;
  z-index: 30;
  background: var(--surface);
  border-top: 1px solid var(--line);
  padding: var(--sp-2) var(--sp-4) calc(var(--sp-4) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.start-btn {
  width: 100%;
  height: 44px;
  font-size: var(--fs-body);
}

.btn-arrow {
  width: 18px;
  height: 18px;
  margin-left: 4px;
}

.foot-hint {
  text-align: center;
  color: var(--ink-3);
}
</style>

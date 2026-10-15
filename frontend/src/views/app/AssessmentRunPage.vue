<!--
  AssessmentRunPage SC-15 测评作答（Stitch 稿重构）
  版式：页头（‹ 退出 + 「气质测评作答」+ 第 N/16 题胶囊）→ 刻度进程行（● 刻度量程 xx% +
  🔒 退出即自动保存断点）+ 刻度进度条 → 已保存断点绿条 → 题目卡（第 N 题·单选 chip +
  维度标签 + 题干）→ 5 点选项列表（选中深色描边 + 数字方标 + 圆圈单选）→
  ⓘ 减负提示 → 底部双按钮（首题禁上一题 / 末题「提交并计分」）+ AI 免责条。
  逻辑：点选即 PUT answer（静默失败不打断）；无即时得分显示。
-->
<template>
  <div class="run-page">
    <!-- ===== 页头：退出 + 标题 + 题号胶囊 + 进度 ===== -->
    <header class="run-head">
      <div class="head-row">
        <button class="quit-btn touch-target" type="button" aria-label="退出测评" @click="confirmQuit = true">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>退出</span>
        </button>
        <h1 class="head-title">气质测评作答</h1>
        <div class="qno-pill numeric">
          <span>第 {{ current + 1 }} / {{ questions.length || TOTAL }} 题</span>
          <i class="pill-sep" />
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="12" r="1.4" fill="currentColor" />
            <circle cx="12" cy="12" r="1.4" fill="currentColor" />
            <circle cx="19" cy="12" r="1.4" fill="currentColor" />
          </svg>
        </div>
      </div>
      <!-- 刻度进程行 -->
      <div class="progress-row">
        <span class="progress-label">
          <i class="dot" />
          刻度量程 {{ progressPct }}
        </span>
        <span class="save-hint caption">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="6" y="10.5" width="12" height="9" rx="2" stroke="currentColor" stroke-width="1.75" />
            <path d="M9 10.5V8a3 3 0 0 1 5.8-1" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            <circle cx="17.5" cy="6" r="3.5" stroke="currentColor" stroke-width="1.5" />
            <path d="m16.2 6 1 1 1.6-1.8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          退出即自动保存断点
        </span>
      </div>
      <!-- 标尺型进度槽（带刻度底纹） -->
      <div class="progress-track">
        <i v-for="n in 5" :key="n" class="tick" :style="{ left: (n * 100) / 6 + '%' }" />
        <div class="progress-fill" :style="{ width: progressPct }" />
      </div>
    </header>

    <!-- ===== 主体滚动区 ===== -->
    <main class="run-main">
      <!-- 退出确认 -->
      <ConfirmDialog
        v-model="confirmQuit"
        title="退出测评？"
        :impacts="['已作答的题目会保留，下次进入可继续', '未提交计分前不会生成报告']"
        confirm-text="退出"
        @confirm="$router.replace('/app/assessment')"
      />

      <!-- 骨架 -->
      <template v-if="loading">
        <SkeletonBlock :height="56" style="margin-bottom: 14px" />
        <SkeletonBlock :height="120" style="margin-bottom: 14px" />
        <SkeletonBlock :height="280" />
      </template>

      <!-- 失败 -->
      <div v-else-if="loadFailed" class="st-card retry">
        <p>题目加载失败</p>
        <el-button type="primary" size="small" @click="load">重试</el-button>
      </div>

      <template v-else>
        <!-- 已保存断点轻提示条（有作答后显示） -->
        <div v-if="answeredCount > 0" class="saved-bar">
          <div class="saved-left">
            <span class="cloud-ico">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M7 18a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 8.3 4.2 4.2 0 0 1 16.8 18H7Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                <path d="m9.5 13 1.8 1.8 3.2-3.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <div class="saved-text">
              <span class="saved-title">已保存断点 · 刚刚</span>
              <span class="saved-sub">已保存，可随时继续；断点保留 90 天</span>
            </div>
          </div>
          <svg class="saved-clock" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" />
            <path d="M12 7.5V12l3 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>

        <!-- 题目卡 -->
        <article class="st-card q-card">
          <div class="q-head">
            <span class="q-chip">第 {{ current + 1 }} 题 · 单选</span>
            <span class="q-dim">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.75" />
                <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1M7.7 16.3l-2.1 2.1" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
              </svg>
              {{ dimText }}
            </span>
          </div>
          <h2 class="q-text">{{ questions[current]?.text || questions[current]?.stem }}</h2>
        </article>

        <!-- 5 点选项列表（点选即保存） -->
        <div class="opt-list">
          <button
            v-for="opt in currentOptions"
            :key="opt.v"
            class="opt"
            :class="{ on: answers[current] === opt.v }"
            @click="choose(opt.v)"
          >
            <span class="opt-num numeric">{{ opt.v }}</span>
            <span class="opt-label">{{ opt.label }}</span>
            <span class="opt-radio" :class="{ on: answers[current] === opt.v }">
              <i v-if="answers[current] === opt.v" class="radio-dot" />
            </span>
          </button>
        </div>

        <!-- 减负提示 -->
        <p class="ease-hint caption">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" />
            <path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
          没有对错，选最接近平时表现的即可
        </p>
      </template>
    </main>

    <!-- ===== 底部双按钮 + 免责 ===== -->
    <footer class="run-foot">
      <div class="nav-grid">
        <button class="nav-btn prev" :disabled="current === 0" @click="prev">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M19 12H5m6-6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          上一题
        </button>
        <button
          v-if="current < questions.length - 1"
          class="nav-btn next"
          :disabled="answers[current] == null"
          @click="next"
        >
          下一题
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <button
          v-else
          class="nav-btn next"
          :disabled="submitting || answers[current] == null"
          @click="submit"
        >
          {{ submitting ? '提交中…' : '提交并计分' }}
          <svg v-if="!submitting" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
      <p class="foot-disclaimer caption">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
        </svg>
        AI 生成内容，仅供参考，不替代医生诊断
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAssessmentQuestions, putAnswer, submitAssessment, startAssessment } from '@/api/client'
import { newRequestId } from '@/api/request'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()

/** 测评实例 uid */
const uid = computed(() => route.params.uid as string)

/** 冻结题量（进度兜底显示用） */
const TOTAL = 16

/** 5 点李克特兜底选项（题目接口未下发 options 时使用） */
const LIKERT = [
  { v: 1, label: '从不' },
  { v: 2, label: '很少' },
  { v: 3, label: '有时' },
  { v: 4, label: '经常' },
  { v: 5, label: '总是' }
]

/** 维度代码 → 对外维度名（PRD §12.2 四维中性命名） */
const DIM_NAMES: Record<string, string> = {
  ACT: '活动水平',
  APP: '趋近-退缩',
  ADP: '适应性',
  EMO: '情绪强度'
}

/** 题目列表（年龄组 1-3y 固定演示） */
const questions = ref<any[]>([])
/** 各题作答（下标 → 分值） */
const answers = ref<(number | null)[]>([])
/** 当前题号 */
const current = ref(0)
/** 加载态 */
const loading = ref(true)
/** 失败态 */
const loadFailed = ref(false)
/** 提交中 */
const submitting = ref(false)
/** 退出确认弹窗 */
const confirmQuit = ref(false)

/** 已答题数（进度条与断点条用） */
const answeredCount = computed(() => answers.value.filter((a) => a != null).length)

/** 进度百分比（真实已答 / 题目总数） */
const progressPct = computed(() => {
  if (!questions.value.length) return '0%'
  return `${((answeredCount.value / questions.value.length) * 100).toFixed(0)}%`
})

/** 当前题维度名（ACT/APP/ADP/EMO → 中性命名） */
const dimText = computed(() => {
  const dim = questions.value[current.value]?.dimension
  return dim ? DIM_NAMES[dim] || dim : '气质维度'
})

/** 当前题选项列表（优先接口下发的 options，缺失时李克特兜底） */
const currentOptions = computed<{ v: number; label: string }[]>(() => {
  const q = questions.value[current.value]
  const opts = q?.options
  if (Array.isArray(opts) && opts.length) {
    return opts.map((o: any) => ({ v: Number(o.score), label: String(o.label) }))
  }
  return LIKERT
})

/**
 * 加载题目（1-3y 年龄段）并恢复断点（SIM-21 修复）
 * 并行拉取题库与断点视图（/assessment/start 幂等：有未过期断点返回 resumed=true
 * 且携带已答明细 answers[{q_no, raw_score, skipped}]）；仅当返回的是当前实例
 * （assessment_uid 与路由 uid 一致）的续填视图时回放已答映射，并把光标定位到
 * 首个未作答且未跳过的题目。计分逻辑不动。
 * @throws 题目接口失败置失败态（断点接口失败不阻断，退化为从第 1 题开始）
 */
async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    const [res, draft]: any[] = await Promise.all([
      getAssessmentQuestions('1-3y'),
      // 断点视图拉取失败不阻断作答（catch 后置 null）
      startAssessment().catch(() => null)
    ])
    questions.value = res?.questions || res || []
    answers.value = questions.value.map(() => null)
    // SIM-21：断点续填恢复——校验是当前实例的续填视图后才回放，避免串实例
    const draftAnswers: any[] =
      draft?.resumed && draft?.assessment_uid === uid.value ? draft?.answers || [] : []
    let firstUnanswered = -1
    questions.value.forEach((q: any, idx: number) => {
      const hit = draftAnswers.find((a: any) => Number(a?.q_no) === idx + 1)
      if (hit && hit.raw_score != null) {
        // 已答题：还原选中态
        answers.value[idx] = Number(hit.raw_score)
      } else if (!hit?.skipped && firstUnanswered < 0) {
        // 首个「未作答且未明确跳过」的题作为恢复定位点
        firstUnanswered = idx
      }
    })
    if (draftAnswers.length) {
      current.value = firstUnanswered >= 0 ? firstUnanswered : Math.max(0, questions.value.length - 1)
    }
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

/**
 * 点选即提交单题作答（静默失败不打断作答）
 * @param v 分值 1-5
 */
async function choose(v: number): Promise<void> {
  answers.value[current.value] = v
  try {
    await putAnswer(uid.value, current.value + 1, v)
    sessionStorage.setItem('jiaban_assessment_answered', String(answers.value.filter((a) => a != null).length))
  } catch {
    // 静默：提交时以本地作答为准
  }
}

/**
 * 下一题
 */
function next(): void {
  if (current.value < questions.value.length - 1) current.value++
}

/**
 * 上一题
 */
function prev(): void {
  if (current.value > 0) current.value--
}

/**
 * 提交并计分 → 跳报告
 * @throws 接口失败消息提示（幂等 id 每次提交新生成）
 */
async function submit(): Promise<void> {
  submitting.value = true
  try {
    const res: any = await submitAssessment(uid.value, newRequestId())
    // report_uid 与 assessment_uid 是两个标识：长图端点按 report_uid 查询，
    // 经 query 透传给报告页，避免「保存长图」时 1002
    const reportUid = res?.report_uid || res?.data?.report_uid || ''
    const q = reportUid ? `?report=${reportUid}` : ''
    router.replace(`/app/assessment/report/${uid.value}${q}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
/* ===== 页面骨架：头 + 滚动主体 + 固定底部 ===== */
.run-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

/* ===== 页头区 ===== */
.run-head {
  position: sticky;
  top: 0;
  z-index: 30;
  background: var(--surface);
  padding: 0 var(--sp-4);
}

.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
}

.quit-btn {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: none;
  background: none;
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-2);
  cursor: pointer;

  svg {
    width: 18px;
    height: 18px;
  }

  &:active {
    transform: scale(0.95);
  }
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

/* 题号胶囊 */
.qno-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: var(--sc-low);
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--accent);

  .pill-sep {
    width: 1px;
    height: 12px;
    background: var(--line);
  }

  svg {
    width: 14px;
    height: 14px;
    color: var(--ink-3);
  }
}

/* 刻度进程行 */
.progress-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0 6px;
}

.progress-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }
}

.save-hint {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--ink-3);

  svg {
    width: 12px;
    height: 12px;
    color: var(--accent);
  }
}

/* 标尺型进度槽：轨道 + 刻度底纹 + 填充 */
.progress-track {
  position: relative;
  height: 8px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  overflow: hidden;
  margin-bottom: 10px;

  .tick {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--line-strong);
    opacity: 0.3;
    pointer-events: none;
  }

  .progress-fill {
    position: relative;
    height: 100%;
    border-radius: var(--radius-pill);
    background: var(--accent);
    transition: width 0.3s ease;

    /* 填充头部高光竖线（量具感） */
    &::after {
      content: '';
      position: absolute;
      right: 0;
      top: 0;
      bottom: 0;
      width: 2px;
      background: rgba(255, 255, 255, 0.45);
    }
  }
}

/* ===== 主体滚动区 ===== */
.run-main {
  flex: 1;
  padding: var(--sp-3) var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

/* 失败重试卡 */
.retry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  color: var(--ink-2);
}

/* ===== 已保存断点轻提示条（绿底） ===== */
.saved-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: color-mix(in srgb, var(--accent-soft) 70%, transparent);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-face);
  padding: var(--sp-2) var(--sp-3);
}

.saved-left {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.cloud-ico {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 13px;
    height: 13px;
  }
}

.saved-text {
  display: flex;
  flex-direction: column;

  .saved-title {
    font-size: var(--fs-caption);
    font-weight: 600;
    color: var(--accent);
  }

  .saved-sub {
    font-size: 11px;
    line-height: 1.3;
    color: var(--ink-2);
  }
}

.saved-clock {
  flex: none;
  width: 14px;
  height: 14px;
  color: var(--ink-3);
}

/* ===== 题目卡 ===== */
.q-card {
  padding: var(--sp-4);
}

.q-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--line);
}

.q-chip {
  padding: 2px 8px;
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: var(--fs-caption);
  font-weight: 500;
  color: var(--accent);
}

.q-dim {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-caption);
  color: var(--ink-3);

  svg {
    width: 13px;
    height: 13px;
    color: var(--accent);
  }
}

.q-text {
  padding-top: var(--sp-3);
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.55;
}

/* ===== 5 点选项列表 ===== */
.opt-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.opt {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  padding: 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, background 0.2s ease;

  &:active {
    background: var(--sc);
  }

  /* 选中态：深色描边 + 浅绿底 */
  &.on {
    border: 2px solid var(--accent);
    background: color-mix(in srgb, var(--accent-soft) 20%, var(--surface));

    .opt-num {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--on-accent);
    }

    .opt-label {
      color: var(--ink-1);
      font-weight: 600;
    }

    .opt-radio {
      border: 2px solid var(--accent);
    }
  }
}

/* 数字方标 */
.opt-num {
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.opt-label {
  flex: 1;
  font-size: var(--fs-sub);
  color: var(--ink-2);
  line-height: 1.4;
}

/* 单选圆圈 */
.opt-radio {
  flex: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;

  .radio-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
  }
}

/* 减负提示 */
.ease-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--ink-3);

  svg {
    width: 13px;
    height: 13px;
    color: var(--accent);
  }
}

/* ===== 底部双按钮 + 免责 ===== */
.run-foot {
  position: sticky;
  bottom: 0;
  z-index: 30;
  background: var(--surface);
  border-top: 1px solid var(--line);
  padding: var(--sp-3) var(--sp-4) calc(var(--sp-4) + env(safe-area-inset-bottom));
}

.nav-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}

/* 上一题（次按钮）/ 下一题（主按钮） */
.nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 44px;
  border-radius: var(--radius-face);
  font-size: var(--fs-sub);
  cursor: pointer;
  transition: transform 0.15s ease, background 0.2s ease;

  &:active:not(:disabled) {
    transform: scale(0.98);
  }

  svg {
    width: 16px;
    height: 16px;
  }

  &.prev {
    border: 1px solid var(--line-strong);
    background: var(--surface);
    color: var(--ink-2);

    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  }

  &.next {
    border: none;
    background: var(--accent);
    color: var(--on-accent);
    font-weight: 600;
    box-shadow: var(--shadow-e1);

    &:disabled {
      background: var(--surface-2);
      color: var(--ink-3);
      box-shadow: none;
      cursor: not-allowed;
    }
  }
}

.foot-disclaimer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 11px;
  color: var(--ink-3);

  svg {
    width: 12px;
    height: 12px;
  }
}
</style>

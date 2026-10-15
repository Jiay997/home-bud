<!--
  AssessmentReportPage SC-16 测评报告（Stitch 稿重构）
  版式：页头 → 档案元数据 → 观察结论封面 → 四维刻度读数 → 解读与养育支持 → 波动提示
  → 非宿命声明 → 会员区块
  （LockedBlock 形态保留）→ 保存长图主按钮 + 分享/反馈/举报操作栏 + AI 免责条。
  数据：报告 13 区块 blocks（dimension_bands 仅含档位 band，禁止渲染 mean 数值）。
-->
<template>
  <div class="report-page">
    <!-- ===== 页头 ===== -->
    <header class="rp-head">
      <button class="head-back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">测评报告</h1>
    </header>

    <div class="rp-main">
      <!-- ===== 元数据行 ===== -->
      <section class="meta-line caption">
        <span class="meta-child">
          <i class="dot" />
          测评孩子：<strong>{{ nickname }}</strong><template v-if="ageLabel"> · {{ ageLabel }}</template>
        </span>
        <span class="meta-time">生成时间：{{ completedAtText }}</span>
      </section>

      <!-- 骨架 -->
      <template v-if="loading">
        <SkeletonBlock :height="180" style="margin-bottom: 12px" />
        <SkeletonBlock :height="260" style="margin-bottom: 12px" />
        <SkeletonBlock :height="140" />
      </template>

      <!-- 失败 -->
      <div v-else-if="loadFailed" class="st-card retry">
        <p>报告加载失败</p>
        <el-button type="primary" @click="load">重试</el-button>
      </div>

      <template v-else>
        <!-- ===== 气质类型核心卡 ===== -->
        <section class="type-card st-card">
          <i class="type-notch" />
          <div class="type-ico">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 2v20M2 12h20" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" />
              <path d="M5 9v6m14-6v6M9 5h6m-6 14h6" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" />
              <circle cx="12" cy="12" r="3.25" stroke="currentColor" stroke-width="1.5" />
              <circle cx="12" cy="12" r=".75" fill="currentColor" />
            </svg>
          </div>
          <h2 class="type-name">{{ typeName }}</h2>
          <p class="type-slogan caption">{{ typeSlogan }}</p>
          <p class="type-reading">按四个行为维度分档呈现，不用单一结论定义孩子</p>
          <div class="type-divider">
            <p class="type-declare caption">四象仅作趣味包装命名 · 四维为非评价表述，不作论断声明</p>
          </div>
        </section>

        <!-- ===== 四维分档刻度带卡 ===== -->
        <section class="st-card bands-card">
          <div class="bands-head">
            <div class="bands-title">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M3 17 9 7l4 6 3-4 5 8" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <h3>四维分档刻度带</h3>
            </div>
          </div>
          <!-- 说明标注 -->
          <p class="bands-note caption">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" />
              <path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            仅分档 · 不采纳精确分数，呈现档位化
          </p>
          <!-- 四维刻度带：签名组件 GraduatedBand（档位化，无精确数值） -->
          <div class="band-list">
            <GraduatedBand
              v-for="d in bandRows"
              :key="d.dimension"
              :label="d.sub ? `${d.name}（${d.sub}）` : d.name"
              :bands="BAND_NAMES"
              :level-labels="BAND_LEVEL_LABELS"
              :value="d.value"
              :partial="d.partial"
            />
          </div>
        </section>

        <!-- ===== 多维解读与养育支持卡 ===== -->
        <section class="st-card insight-card">
          <div class="insight-head">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9.5 3a6.5 6.5 0 0 1 6.5 6.5c0 1.7-.7 3.3-1.8 4.4-.8.8-1.2 1.9-1.2 3.1v.5h-7v-.5c0-1.2-.4-2.3-1.2-3.1A6.5 6.5 0 0 1 9.5 3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M7 21h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <h3>多维解读与养育支持</h3>
          </div>
          <!-- 类型解读 -->
          <div class="insight-block">
            <div class="ib-head is-primary">
              <i class="ib-bar" />
              <h4>类型解读</h4>
            </div>
            <p class="ib-body">{{ typeDesc }}</p>
          </div>
          <!-- 适配养育方式 -->
          <div class="insight-block is-advice">
            <div class="ib-head">
              <i class="ib-bar" />
              <h4>适配养育方式</h4>
            </div>
            <p class="ib-body">{{ adviceText }}</p>
          </div>
          <!-- 沟通技巧 -->
          <div class="insight-block">
            <div class="ib-head is-secondary">
              <i class="ib-bar" />
              <h4>沟通技巧</h4>
            </div>
            <p class="ib-body">{{ talkText }}</p>
          </div>
        </section>

        <!-- ===== 波动提示黄条（条件触发） ===== -->
        <section v-if="waveTriggered" class="wave-bar">
          <svg class="wave-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" />
            <path d="M12 7.5V12l-2.5 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M12 7.5V12l2.5 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.45" />
          </svg>
          <div class="wave-body">
            <span class="wave-title">波动提示</span>
            <p>仅反映近期行为倾向，单次结果不代表长期特质。环境转变或情绪波动均可能带来阶段性差异。</p>
          </div>
        </section>

        <!-- ===== 气质不是宿命判定卡 ===== -->
        <section class="st-card fatalism-card">
          <div class="fatalism-head">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
              <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>气质不是宿命判定</span>
          </div>
          <p class="caption">{{ nonFatalismText }}</p>
        </section>

        <!-- ===== 会员区块（4 项，LockedBlock 形态保留） ===== -->
        <section class="st-card member-card">
          <h3 class="st-section-head member-title">深入解读（会员权益）</h3>
          <div v-for="blk in memberBlocks" :key="blk.key" class="member-item">
            <LockedBlock
              v-if="!blk.unlocked"
              :title="blk.title"
              :summary="blk.summary || '开通会员查看完整方案'"
              @unlock="$router.push('/app/member')"
            />
            <div v-else class="member-open">
              <span class="mo-title">{{ blk.title }}</span>
              <p class="caption">{{ blk.text }}</p>
            </div>
          </div>
        </section>

        <!-- ===== 操作区：保存长图 + 分享/反馈/举报 ===== -->
        <section class="action-area">
          <el-button type="primary" size="large" class="save-btn" @click="goImage">
            <svg class="btn-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 4v11m0 0 4.5-4.5M12 15l-4.5-4.5M5 19h14" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            保存长图
          </el-button>
          <div class="op-bar">
            <button class="op-btn" @click="share">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="6" cy="12" r="2.5" stroke="currentColor" stroke-width="1.6" />
                <circle cx="17.5" cy="5.5" r="2.5" stroke="currentColor" stroke-width="1.6" />
                <circle cx="17.5" cy="18.5" r="2.5" stroke="currentColor" stroke-width="1.6" />
                <path d="m8.3 10.7 7-3.9m-7 6.4 7 3.9" stroke="currentColor" stroke-width="1.6" />
              </svg>
              分享
            </button>
            <i class="op-sep" />
            <button class="op-btn" @click="$router.push('/app/me/feedback')">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-4 4V5.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              </svg>
              反馈
            </button>
            <i class="op-sep" />
            <button class="op-btn is-flag" @click="$router.push('/app/me/feedback')">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M6 21V4m0 1h11l-2.5 3.5L17 12H6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              举报
            </button>
          </div>
        </section>

        <!-- 底部免责 -->
        <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAssessmentReport, getChildren } from '@/api/client'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import LockedBlock from '@/components/LockedBlock.vue'
import GraduatedBand from '@/components/GraduatedBand.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 测评实例 uid */
const uid = computed(() => route.params.uid as string)

/** 加载态 */
const loading = ref(true)
const loadFailed = ref(false)

/** 报告数据（13 区块 blocks 结构） */
const report = ref<any>(null)
/** 孩子档案（用于月龄展示） */
const children = ref<any[]>([])

/** 刻度分区名（低→高，档位化呈现） */
const BAND_NAMES = ['低', '中', '高']
/** 档位展示名（非评价表述口径） */
const BAND_LEVEL_LABELS = ['低倾向', '中等', '高倾向']
/** 档位 → 刻度位置（各档中心；仅档位，不呈现精确分数） */
const BAND_POS: Record<string, number> = { low: 1 / 6, middle: 1 / 2, high: 5 / 6 }

/** 维度代码 → 对外维度名与副注（非评价表述） */
const DIM_META: Record<string, { name: string; sub: string }> = {
  ACT: { name: '活动水平', sub: '体力与节奏' },
  APP: { name: '趋近-退缩', sub: '社交启迪' },
  ADP: { name: '适应性', sub: '环境过渡周期' },
  EMO: { name: '情绪强度', sub: '反应外部强度' }
}

/** 类型代码 → 对外类型名（与后端 TYPE_NAMES 一致） */
const TYPE_NAMES: Record<string, string> = {
  easy: '随和型',
  active: '活跃型',
  sensitive: '敏感型',
  slow_warm: '慢热型'
}

/** 类型代码 → 温馨软语副标（非评价三短语） */
const TYPE_SLOGANS: Record<string, string> = {
  easy: '节奏平稳 · 适应从容 · 情绪温和',
  active: '精力充沛 · 乐于探索 · 动感十足',
  sensitive: '感受细腻 · 反应敏锐 · 情感丰盈',
  slow_warm: '观察敏锐 · 预热充分 · 节奏沉着'
}

/** 类型代码 → 沟通技巧固定映射（后端未单独下发时的展示兜底） */
const TYPE_TALKS: Record<string, string> = {
  easy: '保持稳定的回应节奏即可；孩子表达需求时先确认再行动，例如「你想要这个对吗？我们一起来。」',
  active: '把指令变成游戏，例如「我们先跑一圈，再来搭积木好不好？」先共动、再引导。',
  sensitive: '先描述他的感受，再给两个选择。例如："这里人很多你有点不习惯对吗？我们先在这里看，还是拿玩具去旁边？"',
  slow_warm: '先描述他的感受，再给两个选择。例如："这里人很多你有点不习惯对吗？我们先在这里看，还是拿玩具去旁边？"'
}

/** 区块按 key 索引（blocks → map，便于取用） */
const blockMap = computed<Record<string, any>>(() => {
  const m: Record<string, any> = {}
  for (const b of report.value?.blocks || []) {
    if (b?.key) m[b.key] = b
  }
  return m
})

/** 类型代码（type_conclusion 区块） */
const typeCode = computed(() => blockMap.value.type_conclusion?.content?.type_code || '')

/** 类型名（type_code 映射，回退 report_header.type_name） */
const typeName = computed(
  () => TYPE_NAMES[typeCode.value] || blockMap.value.report_header?.content?.type_name || '—'
)

/** 温馨软语副标 */
const typeSlogan = computed(() => TYPE_SLOGANS[typeCode.value] || '行为倾向参考 · 非评价表述')

/** 类型解读（type_conclusion.type_desc） */
const typeDesc = computed(
  () => blockMap.value.type_conclusion?.content?.type_desc || '结合日常观察了解孩子的行为倾向，仅供参考。'
)

/** 适配养育方式（basic_advice.items 拼接） */
const adviceText = computed(() => {
  const items: string[] = blockMap.value.basic_advice?.content?.items || []
  return items.length ? items.join('；') : '结合孩子的节奏安排日常活动，保持稳定的陪伴与回应。'
})

/** 沟通技巧（type_code 固定映射） */
const talkText = computed(() => TYPE_TALKS[typeCode.value] || TYPE_TALKS.easy)

/** 波动提示是否触发 */
const waveTriggered = computed(() => !!blockMap.value.wave_notice?.content?.triggered)

/** 非宿命论文案（non_fatalism 区块 + 固定补充） */
const nonFatalismText = computed(() => {
  const t = blockMap.value.non_fatalism?.content?.text
  return `${t || '气质没有好坏，不是宿命判定，只是行为倾向参考'}。孩子性格会随成长变化，本报告不作为任何诊断、评价或长期定论，仅供养育参考，不替代专业人士。`
})

/** 测评孩子昵称（报告不落明文，后端占位"宝宝A"） */
const nickname = computed(() => blockMap.value.report_header?.content?.child_nickname || '宝宝')

/** 生成时间（completed_at ISO → YYYY-MM-DD HH:mm） */
const completedAtText = computed(() => {
  const iso = blockMap.value.report_header?.content?.completed_at
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

/** 孩子月龄文案（当前档案匹配时展示） */
const ageLabel = computed(() => {
  const c = children.value.find((x) => x.uid === userStore.currentProfileUid)
  if (!c) return ''
  const m = Number(c?.age_months ?? NaN)
  if (Number.isNaN(m)) return ''
  return m >= 12 ? `${Math.floor(m / 12)} 岁 ${m % 12} 月` : `${m} 月`
})

/** 四维档位行（dimension_bands.bands → GraduatedBand 渲染结构；partial 维标注信息不足） */
const bandRows = computed(() => {
  const bands: any[] = blockMap.value.dimension_bands?.content?.bands || []
  return bands.map((b) => {
    const meta = DIM_META[b.dimension] || { name: b.dimension, sub: '' }
    return {
      dimension: b.dimension,
      name: meta.name,
      sub: meta.sub,
      partial: !!b.partial,
      value: BAND_POS[b.band] ?? 0.5
    }
  })
})

/** 会员区块渲染结构（免费：无 content → LockedBlock；会员：content.text） */
const memberBlocks = computed(() => {
  const keys = ['member_plan_detail', 'member_communication', 'member_scores', 'member_history']
  return keys
    .map((k) => blockMap.value[k])
    .filter(Boolean)
    .map((blk) => ({
      key: blk.key,
      title: blk.title,
      summary: blk.summary,
      text: blk.content?.text || '',
      unlocked: blk.content?.text != null
    }))
})

/**
 * 拉取报告；失败时置失败态可重试
 * @throws 接口失败置失败态
 */
async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    report.value = await getAssessmentReport(uid.value)
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

/**
 * 拉取孩子档案（失败静默：仅影响月龄展示）
 */
async function loadChildren(): Promise<void> {
  try {
    const res: any = await getChildren()
    children.value = res?.children || res?.items || (Array.isArray(res) ? res : [])
  } catch {
    // 静默
  }
}

/**
 * 保存长图：跳转长图页
 * 长图端点按 report_uid 查询（SC-15 提交时经 query.report 透传）；
 * 历史入口（无 query）时回退路由 uid，保持兼容
 */
function goImage(): void {
  const reportUid = route.query.report as string
  router.push(`/app/assessment/report/${reportUid || uid.value}/image`)
}

/**
 * 分享：复制报告链接到剪贴板
 * @throws 剪贴板不可用时提示
 */
async function share(): Promise<void> {
  const url = blockMap.value.share_entry?.content?.share_url
    || `/app/assessment/report/${uid.value}/image`
  try {
    await navigator.clipboard.writeText(location.origin + url)
    ElMessage.success('报告链接已复制')
  } catch {
    ElMessage.info('复制失败，请手动复制地址栏链接')
  }
}

onMounted(() => {
  load()
  loadChildren()
})
</script>

<style lang="scss" scoped>
/* ===== 页面骨架 ===== */
.report-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

/* 页头 */
.rp-head {
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
    width: 32px;
    height: 32px;
    margin-left: -8px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: var(--accent);
    border-radius: 50%;
    cursor: pointer;

    svg {
      width: 24px;
      height: 24px;
    }
  }

  .head-title {
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--accent);
  }
}

/* 主体滚动区 */
.rp-main {
  flex: 1;
  padding: var(--sp-3) var(--sp-4) var(--sp-8);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

/* 失败重试卡 */
.retry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  color: var(--ink-2);
}

/* ===== 元数据行 ===== */
.meta-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: 0 4px;
  color: var(--ink-3);
}

.meta-child {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: var(--ink-2);

  strong {
    color: var(--ink-1);
    font-weight: 600;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }
}

/* ===== 气质类型核心卡 ===== */
.type-card {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--sp-6);

  /* 顶部渐变 notch */
  .type-notch {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(to right, var(--accent), var(--accent-line), var(--accent));
  }
}

.type-ico {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--sp-3);

  svg {
    width: 30px;
    height: 30px;
  }
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  margin-bottom: 4px;

  .chip-dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }
}

.type-name {
  font-size: var(--fs-display);
  font-weight: 700;
  color: var(--accent);
  margin: 4px 0;
}

.type-slogan {
  color: var(--ink-3);
  max-width: 280px;
}

.type-divider {
  width: 100%;
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);

  .type-declare {
    display: inline-block;
    padding: 6px 12px;
    border-radius: var(--radius-ctl);
    background: var(--sc-low);
    border: 1px solid var(--line);
    color: var(--ink-3);
  }
}

/* ===== 四维分档刻度带卡 ===== */
.bands-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
}

.bands-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--line);
}

.bands-title {
  display: flex;
  align-items: center;
  gap: 6px;

  svg {
    width: 20px;
    height: 20px;
    color: var(--accent);
  }

  h3 {
    font-size: var(--fs-body);
    font-weight: 600;
    color: var(--ink-1);
  }
}

/* 说明标注行 */
.bands-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: var(--sp-2);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);
  color: var(--ink-3);

  svg {
    flex: none;
    width: 15px;
    height: 15px;
    margin-top: 2px;
    color: var(--accent);
  }
}

/* 四维刻度带列表（行距用统一 4 倍数刻度：--sp-2） */
.band-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

/* ===== 多维解读与养育支持卡 ===== */
.insight-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-4);
}

.insight-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--line);

  svg {
    width: 20px;
    height: 20px;
    color: var(--accent);
  }

  h3 {
    font-size: var(--fs-body);
    font-weight: 600;
    color: var(--ink-1);
  }
}

/* 解读三块 */
.insight-block {
  background: var(--sc-low);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 6px;

  /* 适配养育方式块：浅绿底变体 */
  &.is-advice {
    background: var(--accent-soft);
    border-color: var(--accent-line);
  }
}

.ib-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--accent);

  .ib-bar {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }

  &.is-primary {
    color: var(--accent);

    .ib-bar {
      background: var(--accent);
    }
  }

  &.is-secondary {
    color: var(--ink-2);

    .ib-bar {
      background: var(--ink-2);
    }
  }
}

.ib-body {
  padding-left: 12px;
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);
}

/* ===== 波动提示黄条 ===== */
.wave-bar {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-face);
  padding: var(--sp-3);
}

.wave-ico {
  flex: none;
  width: 20px;
  height: 20px;
  margin-top: 2px;
  color: var(--warn);
}

.wave-body {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .wave-title {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--warn);
  }

  p {
    font-size: var(--fs-caption);
    line-height: 1.7;
    color: var(--warn);
  }
}

/* ===== 气质不是宿命判定卡 ===== */
.fatalism-card {
  background: var(--surface-2);
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--sp-4);

  .fatalism-head {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);

    svg {
      width: 18px;
      height: 18px;
      color: var(--accent);
    }
  }

  p {
    color: var(--ink-3);
    line-height: 1.7;
  }
}

/* ===== 会员区块 ===== */
.member-card {
  display: flex;
  flex-direction: column;
  padding: var(--sp-4);

  .member-title {
    margin-bottom: var(--sp-2);
  }
}

.member-item {
  & + .member-item {
    margin-top: var(--sp-2);
  }
}

/* 会员已解锁态 */
.member-open {
  background: var(--surface-2);
  border-radius: var(--radius-face);
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: 4px;

  .mo-title {
    font-size: var(--fs-body);
    font-weight: 600;
    color: var(--ink-1);
  }

  p {
    color: var(--ink-2);
    line-height: 1.6;
  }
}

/* ===== 操作区 ===== */
.action-area {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding-top: var(--sp-2);
}

.save-btn {
  width: 100%;
  height: 44px;
  font-size: var(--fs-body);
}

.btn-ico {
  width: 20px;
  height: 20px;
  margin-right: 4px;
}

/* 次级文字按钮群 */
.op-bar {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 4px var(--sp-4);
}

.op-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: none;
  background: none;
  font-size: var(--fs-sub);
  color: var(--ink-2);
  cursor: pointer;

  svg {
    width: 17px;
    height: 17px;
    color: var(--ink-3);
  }

  &.is-flag:active {
    color: var(--danger);
  }

  &:active {
    color: var(--accent);
  }
}

.op-sep {
  width: 1px;
  height: 14px;
  background: var(--line);
}

/* 测评档案：首屏给出一条可回看的观察结论，后续读数像杂志分栏一样展开。 */
.rp-head {
  height: 52px;
  padding-inline: 16px;
  border-bottom: 1px solid var(--line);
  box-shadow: none;

  .head-title {
    color: var(--ink-1);
  }
}

.rp-main {
  width: 100%;
  max-width: 430px;
  align-self: center;
  gap: 18px;
  padding: 18px 20px calc(36px + env(safe-area-inset-bottom));
}

.meta-line {
  gap: 8px 16px;
  padding: 0 2px 12px;
  border-bottom: 1px solid var(--line);
}

.meta-time {
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}

.type-card {
  min-height: 250px;
  align-items: flex-start;
  justify-content: flex-end;
  text-align: left;
  padding: 28px 22px 22px;
  border-radius: 8px 8px 8px 28px;
  background: var(--surface);
  box-shadow: none;

  .type-notch {
    right: 22px;
    left: 22px;
    height: 8px;
    background: repeating-linear-gradient(
      to right,
      var(--art-line) 0 1px,
      transparent 1px 8px
    );
  }
}

.type-ico {
  position: absolute;
  top: 30px;
  right: 22px;
  width: 72px;
  height: 72px;
  margin: 0;
  border: 0;
  border-radius: 0;
  background: transparent;

  svg {
    width: 60px;
    height: 60px;
    stroke-width: 1.25;
  }
}

.type-chip {
  width: fit-content;
  margin: 70px 0 8px;
  padding: 3px 8px;
  border-radius: 6px;
}

.type-name {
  max-width: 8em;
  margin: 0;
  font-size: 34px;
  line-height: 1.18;
  text-wrap: balance;
}

.type-slogan {
  max-width: 26ch;
  margin-top: 6px;
  text-align: left;
}

.type-divider {
  margin-top: 18px;
  padding-top: 12px;
  text-align: left;
  border-color: rgb(241 247 245 / 28%);

  .type-declare {
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--st-side-ink);
    line-height: 1.55;
    opacity: 0.84;
  }
}

.bands-card,
.insight-card,
.member-card {
  padding: 16px 0;
  border: 0;
  border-top: 1px solid var(--line-strong);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.bands-head,
.insight-head {
  padding-bottom: 10px;
}

.bands-note {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--ink-2);
}

.band-list {
  gap: 18px;
  padding: 4px 2px;
}

.insight-card {
  gap: 0;
}

.insight-block,
.insight-block.is-advice {
  padding: 14px 2px;
  border: 0;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
}

.ib-body {
  padding-left: 14px;
}

.wave-bar,
.fatalism-card {
  border-radius: 8px;
}

.fatalism-card {
  padding: 16px;

  p {
    color: var(--ink-2);
  }
}

.member-card :deep(.locked-note) {
  color: var(--ink-2);
}

.rp-main :deep(.disclaimer-text > span) {
  color: var(--ink-2);
}

.type-card {
  min-height: 258px;
  padding: 90px 22px 20px;
  border: 1px solid var(--st-side-line);
  border-radius: 12px;
  background: var(--st-side-bg);
  color: var(--st-side-ink);

  .type-notch {
    right: 22px;
    left: 22px;
    height: 8px;
    background: repeating-linear-gradient(
      to right,
      rgb(241 247 245 / 58%) 0 1px,
      transparent 1px 8px
    );
  }
}

.type-ico {
  top: 28px;
  right: 22px;
  width: 58px;
  height: 58px;
  color: var(--st-side-ink);
  opacity: 0.84;

  svg {
    width: 54px;
    height: 54px;
  }
}

.type-name {
  max-width: calc(100% - 64px);
  color: var(--st-side-ink);
  font-size: 34px;
}

.type-slogan {
  color: var(--st-side-ink);
}

.type-reading {
  max-width: 28ch;
  margin-top: 9px;
  color: var(--st-side-ink);
  font-size: var(--fs-sub);
  line-height: 1.55;
}

.member-card {
  padding-bottom: 0;
}

.member-open {
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
}

.action-area {
  padding-top: 6px;
}

@media (max-width: 360px) {
  .rp-main {
    padding-inline: 14px;
  }

  .type-card {
    min-height: 246px;
    padding-inline: 18px;
  }

  .type-ico {
    right: 18px;
  }

  .type-name {
    max-width: calc(100% - 56px);
    font-size: 30px;
  }
}
</style>

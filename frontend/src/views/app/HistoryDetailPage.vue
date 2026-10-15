<!--
  HistoryDetailPage SC-19 记录详情（Stitch 稿重构）
  页头（‹ 记录详情）+ 刻度编号行（编号 + 会员内容标签 + 刷新图标）+
  记录类型·关联档案·时间行 + 基准标定静态行 + 会员到期只读黄条 +
  咨询提问大字 + 分节卡（编号圆点 +【标题】+ 正文 / 医疗警示红块 / 应激度刻度）+
  内容已更新黄条 + 模型声明 + 存档保护行 + 底部操作（反馈/举报/重新生成·会员专属）。
  只读逻辑、举报、反馈、重新生成（会员专属）逻辑全保留。
  兼容路由 /app/history/qa/:uid 与 /app/history/report/:uid。
-->
<template>
  <div class="page hd-page">
    <!-- 页头 -->
    <header class="hd-head">
      <button class="back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">记录详情</h1>
    </header>

    <!-- 骨架 -->
    <template v-if="loading">
      <SkeletonBlock :height="96" style="margin-bottom: 12px" />
      <SkeletonBlock :height="64" style="margin-bottom: 12px" />
      <SkeletonBlock :height="180" style="margin-bottom: 12px" />
      <SkeletonBlock :height="120" />
    </template>

    <div v-else-if="loadFailed" class="st-card retry">
      <p>详情加载失败</p>
      <el-button type="primary" @click="load">重试</el-button>
    </div>

    <EmptyState v-else-if="!detail" text="记录不存在或已被删除" />

    <template v-else>
      <!-- 刻度编号行 -->
      <div class="st-card meta-card">
        <div class="meta-row">
          <span class="scale-no st-tag st-tag--outline st-tag--plain numeric">{{ scaleNo }}</span>
          <!-- SIM-23：内容档位标签与列表页同口径（is_member_content / access_tier=block），
               不再以会员身份（isMember）替代内容档位口径 -->
          <span class="st-tag" :class="isMemberContent ? 'st-tag--outline' : 'st-tag--gray'">
            {{ contentTierLabel }}
          </span>
          <span class="meta-refresh" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
        </div>
        <p class="meta-line caption">
          记录类型：{{ isReport ? '测评报告' : '问答' }}{{ isMemberContent ? '（会员内容）' : '' }}
          · 关联档案：{{ profileName }}
          · 时间：{{ fmtTime(detail.created_at) }}
        </p>
        <p class="meta-calib caption">
          基准标定：0.0<span class="calib-sep">|</span>校准等级：精准档案级<span class="calib-sep">|</span>采样率：100%
        </p>
      </div>

      <!-- 会员到期只读黄条 -->
      <div v-if="!isMember" class="expired-strip">
        <svg class="strip-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M7 11V8a5 5 0 0 1 10 0v3M5.5 11h13a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="strip-body">
          <p class="strip-title">会员已到期，内容只读</p>
          <p class="strip-sub">到期后不再生成新内容 · 历史记录永久保留只读</p>
        </div>
        <svg class="strip-shield" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
        </svg>
      </div>

      <!-- 咨询提问大字 -->
      <div class="q-block">
        <p class="q-label caption">咨询提问</p>
        <h2 class="q-text">{{ detailTitle }}</h2>
      </div>

      <!-- 分节卡（按真实 blocks 渲染） -->
      <section
        v-for="(sec, si) in detailSections"
        :key="sec.key"
        class="st-card sec-card"
      >
        <template v-for="b in sec.blocks" :key="b.block_id || b.key || si">
          <!-- 付费墙锁定块（保留原逻辑） -->
          <LockedBlock
            v-if="b.access_tier === 'block'"
            title="会员内容"
            :summary="b.title || '该部分为会员深度内容'"
            @unlock="$router.push('/app/member')"
          />
          <!-- 医疗警示红块 -->
          <div v-else-if="blockKind(b) === 'medical'" class="med-block">
            <div class="mb-head">
              <span class="mb-no">{{ si + 1 }}</span>
              <h3 class="mb-title">【{{ b.title }}】</h3>
              <span class="mb-badge">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 5v14m-7-7h14" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
                医疗警戒
              </span>
            </div>
            <p class="mb-text">{{ b.content }}</p>
          </div>
          <!-- 普通分节块：编号 +【标题】+ 应激度刻度/绿 chip -->
          <div v-else class="norm-block">
            <div class="nb-head">
              <span class="nb-no">{{ si + 1 }}</span>
              <h3 class="nb-title">【{{ b.title }}】</h3>
              <span v-if="hasScore(b)" class="nb-score">
                <span class="caption">应激度</span>
                <span class="st-meter nb-meter">
                  <span class="st-meter__fill" :style="{ width: scorePct(b) + '%' }" />
                </span>
              </span>
              <span v-else class="st-tag st-tag--green st-tag--plain">缓和引入</span>
            </div>
            <!-- SIM-23：content 为对象（报告 13 区块的键值/列表形态）时结构化渲染，
                 页面不出现以「{ "」开头的原始 JSON 直显 -->
            <template v-if="isPlainObject(b.content)">
              <p v-if="contentText(b.content)" class="nb-text">{{ contentText(b.content) }}</p>
              <ul v-if="contentList(b.content).length" class="nb-list">
                <li v-for="(it, ii) in contentList(b.content)" :key="ii" class="nb-list-item">{{ it }}</li>
              </ul>
              <dl v-if="contentPairs(b.content).length" class="nb-kv">
                <div v-for="pair in contentPairs(b.content)" :key="pair.k" class="kv-row">
                  <dt class="kv-key">{{ pair.label }}</dt>
                  <dd class="kv-val">{{ pair.val }}</dd>
                </div>
              </dl>
            </template>
            <p v-else class="nb-text">{{ b.content }}</p>
          </div>
        </template>
      </section>

      <!-- 内容已更新黄条 -->
      <div v-if="detail.content_updated" class="updated-strip">
        <svg class="strip-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="strip-body">
          <p class="strip-title">内容已更新 <a class="strip-link" @click.prevent="showUpdateNote">查看说明</a></p>
          <p class="strip-sub">该回答更新的知识条目已回源：历史内容不追溯重写，仅作状态标记。</p>
        </div>
      </div>

      <!-- 模型声明 + 免责 + 存档保护 -->
      <div class="decl-block">
        <p class="decl-line">
          <span class="model-badge st-tag st-tag--gray st-tag--plain">模型版本 {{ MODEL_VERSION }}</span>
          本建议由智能引擎模型结合养育规范生成
        </p>
        <p class="decl-sub caption">免责声明：分析结论仅供日常照护参考，不构成专业医学诊疗依据。</p>
        <p class="decl-archive caption">—— 已进入存档保护模式 · 无法修改条目 ——</p>
      </div>

      <!-- 免责 + AI 标识 -->
      <AiDisclaimer ai-label="AI 生成内容" disclaimer="历史存档仅供参考，不能替代专业医疗、心理或法律意见" />
    </template>

    <!-- 底部操作 -->
    <div v-if="detail" class="footer-ops">
      <button class="op" @click="onFeedback">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 5h16v11H8l-4 4V5Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        反馈
      </button>
      <button class="op" @click="reportVisible = true">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 21V4m0 1h11l-2 3.5L16 12H5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
        举报
      </button>
      <button class="regen-btn" :class="{ disabled: !isMember }" @click="onRegen">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
        重新生成
        <span v-if="!isMember" class="regen-badge">会员专属</span>
      </button>
    </div>
    <p v-if="detail && !isMember" class="regen-hint caption">重新生成为会员专属功能，开通后可对历史问答重新生成回答</p>

    <!-- 举报弹窗（界面文案不变；value 对齐后端 POST /reports 合法枚举：
         illegal / medical_misleading / harmful_to_minor / other） -->
    <el-dialog v-model="reportVisible" title="举报这条内容" width="88%" :append-to-body="true">
      <el-radio-group v-model="reportCategory" class="report-opts">
        <!-- 有害内容 → illegal（违法有害内容） -->
        <el-radio value="illegal">有害内容</el-radio>
        <!-- 错误信息 → medical_misleading（本产品医疗养育场景，错误信息最贴近医疗误导分类） -->
        <el-radio value="medical_misleading">错误信息</el-radio>
        <!-- 隐私问题 → other（后端枚举无隐私分类，无法对应归入其他） -->
        <el-radio value="other">隐私问题</el-radio>
        <el-radio value="other">其他</el-radio>
      </el-radio-group>
      <template #footer>
        <div class="dlg-actions">
          <el-button @click="reportVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!reportCategory" :loading="reporting" @click="doReport">提交</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getQaHistory, getReportHistory, submitReport, submitFeedback, regenerateQa } from '@/api/client'
import { useUserStore } from '@/stores/user'
import LockedBlock from '@/components/LockedBlock.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import EmptyState from '@/components/EmptyState.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

const route = useRoute()
const router = useRouter()
const user = useUserStore()

/** 会话/报告 uid */
const uid = computed(() => route.params.uid as string)
/** 是否报告详情 */
const isReport = computed(() => route.path.includes('/report/'))

/** 详情数据 */
const detail = ref<any>(null)
const loading = ref(true)
const loadFailed = ref(false)

/** 举报弹窗 */
const reportVisible = ref(false)
const reportCategory = ref('')
const reporting = ref(false)

/** 会员标识：优先取详情接口服务端门控结论（is_member / readonly），未加载时退回本地近似判断 */
const isMember = computed(() => {
  const d = detail.value
  if (d && typeof d.is_member === 'boolean') return d.is_member
  if (d && typeof d.readonly === 'boolean') return !d.readonly
  return user.isMember
})
/** 非会员到期补充说明 */
const memberExpiredNote = computed(() => ' · 重新生成等操作需会员')

/** SIM-23：内容档位（与历史列表页 isMemberTier 同口径）——
 * 详情接口显式下发 is_member_content（qa：会话是否含会员内容；报告：恒 false 基础免费），
 * 旧响应缺字段时回退按 sections/blocks 中 access_tier=block 兜底判定 */
const isMemberContent = computed(() => {
  const d = detail.value
  if (!d) return false
  if (typeof d.is_member_content === 'boolean') return d.is_member_content
  const tiered = (d.sections || []).some((s: any) => s?.access_tier === 'block')
    || (d.blocks || []).some((b: any) => b?.access_tier === 'block')
  return tiered
})

/** SIM-23：内容档位标签文案（与列表页「会员内容/免费内容」一致） */
const contentTierLabel = computed(() => (isMemberContent.value ? '会员内容' : '免费内容'))

/** 静态合规声明：模型版本徽章文案 */
const MODEL_VERSION = 'v4.2'

/** 详情分节（qa 返回 sections；report 返回单节 blocks） */
const detailSections = computed<any[]>(() => {
  if (!detail.value) return []
  if (detail.value.sections) {
    // qa 详情契约：非会员对会员分节只下发 access_tier=block 占位（无 blocks 字段），
    // 包装为锁定块交给既有 LockedBlock 分支渲染，避免历史详情出现空分节
    return detail.value.sections.map((sec: any) =>
      sec.access_tier === 'block' ? { ...sec, blocks: [{ access_tier: 'block', title: sec.title }] } : sec
    )
  }
  if (detail.value.blocks) {
    return [{ key: 'main', title: isReport.value ? '报告内容' : '回答内容', pinned: false, blocks: detail.value.blocks }]
  }
  return []
})

/** 详情标题（qa 为提问明文；报告详情无 question，回退报告类型名，与后端 REPORT_TYPE_NAMES 口径一致） */
const detailTitle = computed<string>(() => {
  const d = detail.value || {}
  if (d.question || d.title) return d.question || d.title
  if (isReport.value) return ({ assessment: '气质测评报告' } as Record<string, string>)[d.report_type] || '测评报告'
  return '—'
})

/**
 * 刻度编号：由创建日期 + 类型 + uid 尾号推导（如 2026-0918-QA）
 * @returns 编号文本
 */
const scaleNo = computed<string>(() => {
  const d = detail.value?.created_at ? new Date(detail.value.created_at) : new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  const tail = String(uid.value || '').slice(-2).toUpperCase() || '00'
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}${p(d.getDate())}-${isReport.value ? 'RP' : 'QA'}${tail}`
})

/**
 * 关联档案名（兜底链：profile.nickname / profile_name / 未关联）
 * @returns 档案显示名
 */
const profileName = computed<string>(() => {
  const d = detail.value || {}
  return d.profile?.nickname || d.profile_name || d.profile_nickname || '未关联档案'
})

/**
 * 时间格式化
 * @param ts ISO 时间
 * @returns yyyy-MM-dd HH:mm 文本
 */
function fmtTime(ts: string): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/**
 * 展示内容更新说明（合规：历史内容不追溯重写，仅状态标记）
 */
function showUpdateNote(): void {
  ElMessage.info('更新说明：知识条目已回源，历史内容不追溯重写，仅作状态标记')
}

/**
 * 分块样式类型：含医疗/就医警示关键词或 type 标记时渲染红块
 * @param b block 对象
 * @returns 'medical' | 'normal'
 */
function blockKind(b: any): 'medical' | 'normal' {
  const t = String(b?.type || '') + String(b?.title || '')
  return /medical|就医|需就医|警示/.test(t) ? 'medical' : 'normal'
}

/**
 * block 是否带分值（应激度刻度）
 * @param b block 对象
 * @returns 是否有 0-100 分值
 */
function hasScore(b: any): boolean {
  const v = b?.score ?? b?.stress_level ?? b?.stress
  return typeof v === 'number' && v >= 0
}

/**
 * 分值转百分比
 * @param b block 对象
 * @returns 0-100 整数
 */
function scorePct(b: any): number {
  const v = b?.score ?? b?.stress_level ?? b?.stress ?? 0
  return Math.max(0, Math.min(100, Math.round(v)))
}

/* ================= SIM-23：报告区块 content 结构化渲染 ================= */

/** 维度代码 → 对外维度名（PRD §12.2 四维中性命名） */
const DIM_NAMES: Record<string, string> = {
  ACT: '活动水平',
  APP: '趋近-退缩',
  ADP: '适应性',
  EMO: '情绪强度'
}

/** 档位代码 → 展示名 */
const BAND_NAMES: Record<string, string> = {
  low: '低',
  middle: '中',
  high: '高'
}

/** content 标量键 → 对外中文标签（报告 13 区块实际字段形态覆盖） */
const KV_LABELS: Record<string, string> = {
  type_name: '气质类型',
  type_code: '类型编码',
  completed_at: '完成时间',
  question_version: '题库版本',
  child_nickname: '孩子昵称',
  ai_generated_label: 'AI 生成标识',
  disclaimer_id: '免责声明标识',
  share_url: '分享链接',
  triggered: '波动提示',
  window_days: '对比窗口（天）',
  previous_type_code: '上次类型',
  note: '备注'
}

/**
 * 判断值是否为普通对象（排除数组与 null）
 * @param v 任意值
 * @returns 是否普通对象
 */
function isPlainObject(v: any): boolean {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/**
 * 提取对象 content 的正文文本（text / type_desc 等叙述字段）
 * @param content 区块 content 对象
 * @returns 正文文本（无则空串）
 */
function contentText(content: any): string {
  if (!isPlainObject(content)) return ''
  for (const key of ['text', 'type_desc']) {
    if (typeof content[key] === 'string' && content[key].trim()) return content[key]
  }
  return ''
}

/**
 * 提取对象 content 的列表项（items 字符串数组 / bands 维度档位数组）
 * @param content 区块 content 对象
 * @returns 逐项展示文本数组
 */
function contentList(content: any): string[] {
  if (!isPlainObject(content)) return []
  if (Array.isArray(content.items)) {
    return content.items.map((it: any) => String(it)).filter(Boolean)
  }
  if (Array.isArray(content.bands)) {
    return content.bands
      .filter((b: any) => isPlainObject(b))
      .map((b: any) => {
        const dim = DIM_NAMES[b.dimension] || b.dimension || '维度'
        if (b.partial) return `${dim}：信息不足`
        return `${dim}：${BAND_NAMES[b.band] || b.band || '—'} 倾向`
      })
  }
  return []
}

/**
 * 格式化 content 键值对的值（ISO 时间可读化、布尔中文化）
 * @param key 键名
 * @param v 原始值
 * @returns 展示文本
 */
function kvValue(key: string, v: any): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (key === 'completed_at' || key.endsWith('_at')) {
    const formatted = fmtTime(String(v))
    return formatted
  }
  if (typeof v === 'object') return '' // 复杂结构不入键值对
  return String(v)
}

/**
 * 提取对象 content 的键值对列表（跳过已由正文/列表渲染的键与演示标记）
 * @param content 区块 content 对象
 * @returns {k, label, val} 列表
 */
function contentPairs(content: any): { k: string; label: string; val: string }[] {
  if (!isPlainObject(content)) return []
  const skip = new Set(['text', 'type_desc', 'items', 'bands', 'demo'])
  const out: { k: string; label: string; val: string }[] = []
  for (const [k, v] of Object.entries(content)) {
    if (skip.has(k)) continue
    const val = kvValue(k, v)
    if (!val) continue
    out.push({ k, label: KV_LABELS[k] || k, val })
  }
  return out
}

/**
 * 加载详情（按路由类型选择接口）
 * @throws 失败置失败态
 */
async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    detail.value = isReport.value
      ? await getReportHistory(uid.value)
      : await getQaHistory(uid.value)
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

/**
 * 反馈：快捷提交一条与该记录关联的反馈
 * @throws 失败消息提示
 */
async function onFeedback(): Promise<void> {
  try {
    await submitFeedback({ content: `对记录 ${uid.value} 的反馈`, linked_session_id: uid.value })
    ElMessage.success('反馈已提交，感谢你的帮助')
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败')
  }
}

/**
 * 提交举报
 * @throws 失败消息提示
 */
async function doReport(): Promise<void> {
  reporting.value = true
  try {
    const res: any = await submitReport({
      object_type: isReport.value ? 'report' : 'qa_session',
      object_id: uid.value,
      category: reportCategory.value
    })
    // 成功提示携带后端返回的受理回执编号（report_no），缺失时退回原文案
    const receipt = res?.report_no || res?.id || ''
    ElMessage.success(receipt ? `举报已受理 · 回执编号 ${receipt}` : '举报已提交，我们会尽快处理')
    reportVisible.value = false
    reportCategory.value = ''
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败')
  } finally {
    reporting.value = false
  }
}

/**
 * 重新生成：会员可发起，非会员灰态提示
 * @throws 失败消息提示
 */
async function onRegen(): Promise<void> {
  if (!isMember.value) {
    ElMessage.warning('重新生成为会员功能')
    return
  }
  try {
    await regenerateQa(uid.value)
    ElMessage.success('已发起重新生成，完成后可在记录中查看')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.hd-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);

  .back {
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    color: var(--ink-2);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    svg { width: 20px; height: 20px; }
  }

  .head-title {
    font-size: var(--fs-title);
    font-weight: 600;
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

/* ---------- 刻度编号元信息卡 ---------- */
.meta-card {
  margin-bottom: var(--sp-3);
  padding: var(--sp-4) var(--sp-6);
}

.meta-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);

  .scale-no {
    font-size: var(--fs-caption);
  }

  .meta-refresh {
    margin-left: auto;
    color: var(--ink-3);

    svg { width: 16px; height: 16px; }
  }
}

.meta-line {
  color: var(--ink-2);
  line-height: 1.7;
  margin-bottom: var(--sp-2);
}

.meta-calib {
  color: var(--ink-3);
  border-top: 1px dashed var(--line);
  padding-top: var(--sp-2);

  .calib-sep {
    margin: 0 var(--sp-2);
    color: var(--line-strong);
  }
}

/* ---------- 会员到期黄条 ---------- */
.expired-strip,
.updated-strip {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-4) var(--sp-6);
  border-radius: var(--radius-face);
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  margin-bottom: var(--sp-4);
  color: var(--warn);

  .strip-ico {
    flex: none;
    width: 20px;
    height: 20px;
    margin-top: 2px;
  }

  .strip-shield {
    flex: none;
    width: 18px;
    height: 18px;
    margin-left: auto;
    opacity: 0.7;
  }

  .strip-body {
    flex: 1;

    .strip-title {
      font-size: var(--fs-sub);
      font-weight: 600;
      color: var(--warn);
    }

    .strip-sub {
      margin-top: 2px;
      font-size: var(--fs-caption);
      color: var(--ink-3);
      line-height: 1.6;
    }

    .strip-link {
      color: var(--warn);
      text-decoration: underline;
      cursor: pointer;
      margin-left: 4px;
    }
  }
}

/* ---------- 提问大字 ---------- */
.q-block {
  margin-bottom: var(--sp-4);

  .q-label {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--accent);
    font-weight: 600;
    margin-bottom: var(--sp-2);

    &::before {
      content: '';
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: var(--accent);
    }
  }

  .q-text {
    font-size: var(--fs-display);
    font-weight: 700;
    color: var(--ink-1);
    line-height: 1.4;
  }
}

/* ---------- 分节卡 ---------- */
.sec-card {
  margin-bottom: var(--sp-3);
  padding: var(--sp-4) var(--sp-6);
}

.norm-block,
.med-block {
  padding: var(--sp-3) 0;

  & + .norm-block,
  & + .med-block,
  & + .locked {
    border-top: 1px dashed var(--line);
  }
}

.mb-head,
.nb-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}

.mb-no,
.nb-no {
  flex: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  background: var(--ink-1);
  color: var(--surface);
}

.mb-no {
  background: var(--danger);
  color: var(--on-danger);
}

.mb-title,
.nb-title {
  flex: 1;
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
}

.mb-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: var(--fs-caption);
  color: var(--danger);

  svg { width: 12px; height: 12px; }
}

.nb-score {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  .nb-meter {
    width: 72px;
  }
}

.nb-text,
.mb-text {
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);
  padding-left: 28px;
  word-break: break-word;
}

/* SIM-23：报告区块结构化渲染——列表与键值对样式 */
.nb-list {
  margin: 0 0 4px;
  padding-left: 44px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  .nb-list-item {
    position: relative;
    font-size: var(--fs-sub);
    line-height: 1.7;
    color: var(--ink-2);

    &::before {
      content: '';
      position: absolute;
      left: -14px;
      top: 0.62em;
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: var(--accent);
    }
  }
}

.nb-kv {
  margin: 0;
  padding-left: 28px;
  display: flex;
  flex-direction: column;
  gap: 2px;

  .kv-row {
    display: flex;
    gap: var(--sp-2);
    align-items: baseline;

    .kv-key {
      flex: none;
      min-width: 76px;
      font-size: var(--fs-caption);
      color: var(--ink-3);

      &::after {
        content: '：';
      }
    }

    .kv-val {
      margin: 0;
      font-size: var(--fs-sub);
      color: var(--ink-2);
      word-break: break-all;
    }
  }
}

.med-block {
  background: var(--danger-soft);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);
  margin-top: var(--sp-2);

  .mb-text {
    color: var(--danger);
    font-weight: 500;
    padding-left: 28px;
  }
}

/* ---------- 声明块 ---------- */
.decl-block {
  padding: var(--sp-3) 0 var(--sp-2);
  border-top: 1px dashed var(--line);

  .decl-line {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-caption);
    color: var(--ink-2);
    line-height: 1.7;
  }

  .decl-sub {
    margin-top: var(--sp-2);
  }

  .decl-archive {
    margin-top: var(--sp-3);
    text-align: center;
    color: var(--ink-3);
  }
}

/* ---------- 底部操作 ---------- */
.footer-ops {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 430px;
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  background: var(--surface);
  border-top: 1px solid var(--line);
  padding: var(--sp-2) var(--sp-6) calc(var(--sp-2) + env(safe-area-inset-bottom));
  z-index: 90;
}

.op {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  border: none;
  background: none;
  font-size: var(--fs-caption);
  color: var(--ink-2);
  cursor: pointer;

  svg {
    width: 20px;
    height: 20px;
  }
}

.regen-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 0;
  border: none;
  border-radius: var(--radius-ctl);
  background: var(--accent);
  color: var(--on-accent);
  font-size: var(--fs-sub);
  font-weight: 600;
  cursor: pointer;

  svg { width: 16px; height: 16px; }

  .regen-badge {
    font-size: 10px;
    font-weight: 500;
    padding: 0 6px;
    border-radius: var(--radius-pill);
    border: 1px solid rgba(255, 255, 255, 0.6);
  }

  &.disabled {
    background: var(--surface-2);
    color: var(--ink-3);
    cursor: not-allowed;

    .regen-badge {
      border-color: var(--line-strong);
    }
  }
}

.regen-hint {
  text-align: center;
  margin-top: var(--sp-3);
  padding-bottom: 64px;
}

.report-opts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.dlg-actions {
  display: flex;
  gap: var(--sp-3);

  .el-button {
    flex: 1;
  }
}
</style>

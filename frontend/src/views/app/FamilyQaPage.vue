<!--
  FamilyQaPage SC-10 家庭综合问答（Stitch 稿重构）
  双对象 pills（孩子+宠物）+ 调度中卡（三段读数+3 Agent 状态行）+
  安全分节置顶卡（■ 家庭安全提示·置顶 徽章+编号行）+ 育儿侧/宠物侧建议卡 +
  冲突标注条（warn-soft）+ 多 Agent 协同说明折叠 + 单侧失败降级条与安全分节失败整卡隐藏。
  SSE 逻辑零回退：blocked 清空全部正文、section 渐进渲染、幂等重试。
-->
<template>
  <div class="qa-page">
    <!-- 顶部白卡：页头 + 对象对 -->
    <div class="top-sheet">
      <header class="qa-head">
        <button class="head-btn touch-target" aria-label="返回" @click="$safeBack()">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <h1 class="head-title">家庭综合问答</h1>
        <span class="head-spacer" aria-hidden="true" />
      </header>

      <!-- 同时关注对象对 -->
      <div class="dual-row">
        <span class="dual-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.75" />
            <circle cx="12" cy="12" r="2.6" fill="currentColor" />
          </svg>
        </span>
        <span class="dual-label">同时关注：</span>
        <span class="dual-pill dual-pill--child" :class="{ empty: !childName }">{{ childName || '孩子未建档' }}</span>
        <span class="dual-pill dual-pill--pet" :class="{ empty: !petName }">{{ petName || '宠物未建档' }}</span>
        <span v-if="user.quotaUnlimited" class="quota-chip obj-quota numeric">今日额度 不限次</span>
        <span v-else class="quota-chip obj-quota numeric">今日额度 {{ user.quotaUsed }}/{{ user.quotaLimit }}</span>
      </div>
      <p class="dual-note">安全先行，再展开育儿与宠物观察</p>
    </div>

    <!-- 会话流区域 -->
    <div class="stream-area">
      <!-- 用户气泡 -->
      <div v-if="lastQuestion" class="bubble-row">
        <div class="user-bubble">{{ lastQuestion }}</div>
        <p class="bubble-meta">
          <span v-if="askedAt" class="numeric">今天 {{ askedAt }}</span>
          <span class="meta-dot">·</span>
          <span class="first-flag">首次多 Agent 共答</span>
        </p>
      </div>

      <!-- 调度中卡：三段读数 + Agent 状态行 -->
      <section v-if="streaming || (streamStarted && !completed)" class="dispatch-card">
        <header class="dc-head">
          <span class="dc-badge">
            <span v-if="streaming" class="dc-spin" aria-hidden="true" />
            {{ completed ? '调度完成' : '调度中 · 并行 3 Agent' }}
          </span>
        </header>
        <!-- 三段读数行：拦截 / 调度 / 首包（本地计时） -->
        <div class="dc-metrics">
          <span class="m-item">安全拦截 <strong class="numeric">{{ fmtSec(metricBlockMs) }}</strong></span>
          <i class="m-sep" />
          <span class="m-item">并行调度 <strong class="numeric">{{ fmtSec(metricDispatchMs) }}</strong></span>
          <i class="m-sep" />
          <span class="m-item">首包阅读 <strong class="numeric">{{ fmtSec(metricFirstPktMs) }}</strong></span>
        </div>
        <!-- 三 Agent 状态行 -->
        <div class="dc-agents">
          <div v-for="a in agents" :key="a.key" class="agent-row">
            <svg class="ag-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path :d="a.icon" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="ag-name">{{ a.name }}</span>
            <span v-if="a.costMs" class="ag-cost numeric">{{ (a.costMs / 1000).toFixed(1) }}s</span>
            <span class="ag-state" :class="a.state">
              <i v-if="a.state === 'running'" class="ag-spin" aria-hidden="true" />
              {{ agentStateText(a.state) }}
            </span>
          </div>
        </div>
      </section>

      <!-- 家庭安全提示·置顶卡（失败则整卡隐藏） -->
      <section v-if="safetySection && !safetyFailed" class="agent-card pinned">
        <header class="ac-head">
          <span class="ac-badge dark">家庭安全提示 · 置顶</span>
        </header>
        <div v-if="safetySection.streaming" class="delta-text" v-html="safetySection.deltaHtml" />
        <template v-else>
          <p v-for="(b, bi) in safetySection.blocks" :key="b.block_id" class="num-block">
            <span class="nb-no numeric">{{ bi + 1 }}.</span>
            <span class="nb-body">{{ b.content }}</span>
          </p>
        </template>
      </section>

      <!-- 冲突标注条 -->
      <ConflictNote
        v-if="conflictDetected"
        text="观点存在差异 · 建议多方参考：各 Agent 视角结论不完全一致，请结合实际情况甄别。"
      />

      <!-- 育儿侧建议卡 -->
      <section v-for="sec in childSections" :key="sec.key" class="agent-card">
        <header class="ac-head">
          <span class="ac-badge">{{ sec.title || '育儿侧建议' }} · 育儿 Agent</span>
        </header>
        <div v-if="sec.streaming" class="delta-text" v-html="sec.deltaHtml" />
        <template v-else>
          <template v-for="(b, bi) in sec.blocks" :key="b.block_id">
            <LockedBlock
              v-if="b.access_tier === 'block'"
              title="会员内容"
              :summary="b.title || '该部分为会员深度内容'"
              @unlock="$router.push('/app/member')"
            />
            <p v-else-if="b.type === 'warn'" class="plain-warn">{{ b.content }}</p>
            <p v-else class="num-block">
              <span class="nb-no numeric">{{ bi + 1 }}.</span>
              <span class="nb-body"><strong v-if="b.title">{{ b.title }}：</strong>{{ b.content }}</span>
            </p>
          </template>
        </template>
      </section>

      <!-- 宠物饲养建议卡 -->
      <section v-for="sec in petSections" :key="sec.key" class="agent-card">
        <header class="ac-head">
          <span class="ac-badge">{{ sec.title || '宠物饲养建议' }} · 宠物 Agent</span>
        </header>
        <div v-if="sec.streaming" class="delta-text" v-html="sec.deltaHtml" />
        <template v-else>
          <template v-for="(b, bi) in sec.blocks" :key="b.block_id">
            <LockedBlock
              v-if="b.access_tier === 'block'"
              title="会员内容"
              :summary="b.title || '该部分为会员深度内容'"
              @unlock="$router.push('/app/member')"
            />
            <p v-else class="num-block">
              <span class="nb-no numeric">{{ bi + 1 }}.</span>
              <span class="nb-body"><strong v-if="b.title">{{ b.title }}：</strong>{{ b.content }}</span>
            </p>
          </template>
        </template>
      </section>

      <!-- 其余分节（何时咨询专业人士等） -->
      <SectionCard v-for="sec in otherSections" :key="sec.key" :title="sec.title" :pinned="sec.pinned" :immutable="sec.immutable">
        <div v-if="sec.streaming" class="delta-text" v-html="sec.deltaHtml" />
        <template v-else>
          <template v-for="b in sec.blocks" :key="b.block_id">
            <LockedBlock
              v-if="b.access_tier === 'block'"
              title="会员内容"
              :summary="b.title || '该部分为会员深度内容'"
              @unlock="$router.push('/app/member')"
            />
            <p v-else class="block-text">
              <strong v-if="b.title" class="bt-title">{{ b.title }}：</strong>{{ b.content }}
            </p>
          </template>
        </template>
      </SectionCard>

      <template v-if="streamStarted && sections.length === 0 && !safetySection">
        <SkeletonBlock :height="80" style="margin-bottom: 12px" />
        <SkeletonBlock :height="140" />
      </template>

      <!-- 单侧失败降级条（非安全分节） -->
      <StatusStrip v-if="degraded" type="degraded" :text="`「${failedSections.join('、')}」视角生成失败，其余内容已正常展示`" />
      <StatusStrip v-if="completed && !degraded" type="readonly" text="本次综合回答已生成完毕" />

      <!-- 多 Agent 协同说明折叠行 -->
      <details v-if="completed" class="coop-fold">
        <summary>
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M8 8h9m-9 4h6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
          多 Agent 协同说明
          <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </summary>
        <p>
          本页由 0-6 岁育儿、宠物饲养、家庭安全三个 Agent 并行生成，总执行时间
          <strong class="numeric">{{ totalSecText }}</strong>；引用来源：平台审核知识条目。
        </p>
      </details>

      <section v-if="!streamStarted && sections.length === 0 && !safetySection && !lastQuestion" class="family-guide">
        <div class="family-guide-head">
          <h2>一个场景，三面观察</h2>
          <span>共居视角</span>
        </div>
        <div class="lens-route" aria-label="回答顺序：安全优先，再看育儿与宠物视角">
          <div class="lens-step step-safety"><i />安全先行</div>
          <span class="route-link" aria-hidden="true" />
          <div class="lens-step step-child"><i />育儿观察</div>
          <span class="route-link" aria-hidden="true" />
          <div class="lens-step step-pet"><i />宠物观察</div>
        </div>
        <p>例如：孩子总想摸猫的尾巴，怎么引导彼此保持安全距离？</p>
        <div class="guide-fields" aria-label="问题观察要素">
          <span>发生了什么</span><span>当时在哪里</span><span>谁在场</span>
        </div>
        <p class="guide-note">视角出现差异时，会单独标出需要结合情境判断的部分。</p>
      </section>
    </div>

    <!-- 底部输入区；键盘避让走 CSS 变量：过渡期 motion.scss 需接管 bottom 做重锚定 -->
    <div class="input-dock" :style="{ '--keyboard-offset': keyboardOffset + 'px' }">
      <div class="input-row">
        <input v-model="question" class="q-input" :disabled="streaming" placeholder="输入家庭综合问题…" maxlength="500" @keydown.enter="ask" />
        <button v-if="streaming" class="send-btn stop" aria-label="停止" @click="stopGen"><span class="stop-square" /></button>
        <button v-else class="send-btn" :disabled="!question.trim()" aria-label="发送" @click="ask">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 19V6m0 0-5.5 5.5M12 6l5.5 5.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
      <AiDisclaimer ai-label="内容由 AI 生成" disclaimer="仅供参考，不能替代专业医疗、兽医或法律意见" />
    </div>

    <!-- 额度用尽抽屉（1202 触发） -->
    <QuotaDrawer v-model="quotaDrawer" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createQaSession, cancelQaSession, getChildren, getPets } from '@/api/client'
import { startQaStream } from '@/api/stream'
import { newRequestId } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { useKeyboardOffset } from '@/composables/useKeyboardOffset'
import QuotaDrawer from '@/components/QuotaDrawer.vue'
import SectionCard from '@/components/SectionCard.vue'
import LockedBlock from '@/components/LockedBlock.vue'
import ConflictNote from '@/components/ConflictNote.vue'
import StatusStrip from '@/components/StatusStrip.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

const router = useRouter()
const user = useUserStore()
/** 软键盘遮挡高度：输入区抬升用 */
const { keyboardOffset } = useKeyboardOffset()
/** 额度用尽抽屉（1202 触发） */
const quotaDrawer = ref(false)

/** Agent 定义与运行态（icon+稿面名称） */
interface AgentState {
  key: string
  name: string
  /** SVG path（24 网格 / 1.75 描边）：禁止 emoji 充当图标 */
  icon: string
  state: 'pending' | 'running' | 'done' | 'failed'
  costMs: number
}
const agents = ref<AgentState[]>([
  {
    key: 'parenting',
    name: '0-6 岁育儿 Agent',
    icon: 'M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm-3.4-6.4c.9 1.3 2 2 3.4 2s2.5-.7 3.4-2M9.4 10h.01M14.6 10h.01',
    state: 'pending',
    costMs: 0
  },
  {
    key: 'pet',
    name: '宠物饲养 Agent',
    icon: 'M7 8.5c0-1.6 1-2.9 2.2-2.9s2.2 1.3 2.2 2.9M12.6 7c0-1.7 1-3.1 2.3-3.1S17.2 5.3 17.2 7M12 11.4c2.7 0 4.9 2 4.9 4.4 0 1.7-1.3 2.8-2.9 2.8-.8 0-1.4-.3-2-.3s-1.2.3-2 .3c-1.6 0-2.9-1.1-2.9-2.8 0-2.4 2.2-4.4 4.9-4.4Z',
    state: 'pending',
    costMs: 0
  },
  {
    key: 'family_safety',
    name: '家庭安全 Agent',
    icon: 'M12 3 4 6.5v5.2c0 4.4 3.3 8 8 9.3 4.7-1.3 8-4.9 8-9.3V6.5L12 3Z',
    state: 'pending',
    costMs: 0
  }
])

interface SectionState {
  key: string
  title: string
  pinned: boolean
  immutable: boolean
  deltaHtml: string
  streaming: boolean
  blocks: any[]
  /** 是否缓存回放整节创建（done 帧兜底，无 delta 流式过程） */
  cached?: boolean
}
const sections = ref<SectionState[]>([])

const question = ref('')
const sessionUid = ref('')
const cancelToken = ref('')
const streamStarted = ref(false)
const completed = ref(false)
const degraded = ref(false)
const failedSections = ref<string[]>([])
const conflictDetected = ref(false)
const streaming = ref(false)
const requestIdKey = 'jiaban_qa_request_id_family'

/** 孩子与宠物显示名 */
const childName = ref('')
const petName = ref('')

/** 最近一次提问（用户气泡） */
const lastQuestion = ref('')
/** 提问时间戳（HH:mm） */
const askedAt = ref('')

/** 安全分节（置顶单独渲染，失败整卡隐藏） */
const safetySection = ref<SectionState | null>(null)
/** 安全分节是否失败（整卡隐藏开关） */
const safetyFailed = ref(false)

/** 本地计时起点（ask 时刻） */
let tAsk = 0
/** 会话创建完成时刻 */
let tCreated = 0
/** started 到达时刻 */
let tStarted = 0
/** 首个 delta 到达时刻 */
let tFirstDelta = 0

/** 安全拦截耗时（创建会话往返） */
const metricBlockMs = computed(() => (tCreated ? tCreated - tAsk : 0))
/** 并行调度耗时（创建完成 → started） */
const metricDispatchMs = computed(() => (tStarted ? tStarted - (tCreated || tAsk) : 0))
/** 首包耗时（started → 首个 delta） */
const metricFirstPktMs = computed(() => (tFirstDelta ? tFirstDelta - (tStarted || tAsk) : 0))

/** 总执行时间文本（折叠行） */
const totalSecText = computed(() => {
  const end = agents.value.reduce((mx, a) => Math.max(mx, a.costMs), 0)
  return end ? `${(end / 1000).toFixed(1)}s` : '—'
})

/** 育儿侧分节（key 含 child/parent） */
const childSections = computed(() => sections.value.filter((s) => matchAgent(s.key) === 'parenting'))
/** 宠物侧分节（key 含 pet） */
const petSections = computed(() => sections.value.filter((s) => matchAgent(s.key) === 'pet'))
/** 其余分节（何时咨询专业人士等，无法归类到三 Agent 的通用分节） */
const otherSections = computed(() => sections.value.filter((s) => !s.pinned && matchAgent(s.key) === 'other'))

/**
 * 分节 key → Agent key 归属
 * @param sectionKey 分节 key
 * @returns Agent key
 */
function matchAgent(sectionKey: string): string {
  if (sectionKey === 'family_safety' || sectionKey === 'safety') return 'family_safety'
  if (sectionKey.includes('pet')) return 'pet'
  if (sectionKey.includes('child') || sectionKey.includes('parent')) return 'parenting'
  return 'other'
}

/**
 * 毫秒 → 秒文本（0.6s 格式；未就绪显示 —）
 * @param ms 毫秒
 * @returns 秒文本
 */
function fmtSec(ms: number): string {
  return ms ? `${(ms / 1000).toFixed(1)}s` : '—'
}

/**
 * Agent 状态文案映射（✓ 完成 / 生成中 / 失败 / 排队中）
 * @param s Agent 状态
 * @returns 中文状态文本
 */
function agentStateText(s: string): string {
  return { done: '✓ 完成', failed: '✕ 失败', running: '生成中', pending: '排队中' }[s] || s
}

/**
 * HTML 转义（v-html 前必须调用）
 * @param s 原始文本
 * @returns 转义后文本
 */
function escapeHtml(s: string): string {
  // 空值防护：真实 LLM 分片偶发 null/undefined，直接崩溃会导致 SSE 流 ERR_ABORTED
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 重置渲染态
 */
function resetRender(): void {
  sections.value = []
  safetySection.value = null
  safetyFailed.value = false
  streamStarted.value = false
  completed.value = false
  degraded.value = false
  failedSections.value = []
  conflictDetected.value = false
  cancelToken.value = ''
  agents.value.forEach((a) => {
    a.state = 'pending'
    a.costMs = 0
  })
  tAsk = 0
  tCreated = 0
  tStarted = 0
  tFirstDelta = 0
}

/**
 * 发起综合提问
 * @throws 网络错误消息提示
 */
async function ask(): Promise<void> {
  const q = question.value.trim()
  if (!q || streaming.value) return

  let requestId = sessionStorage.getItem(requestIdKey)
  if (!requestId) {
    requestId = newRequestId()
    sessionStorage.setItem(requestIdKey, requestId)
  }

  streaming.value = true
  lastQuestion.value = q
  askedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  question.value = ''
  resetRender()
  tAsk = Date.now()
  // 全部进入 running
  agents.value.forEach((a) => (a.state = 'running'))

  try {
    const res = await createQaSession({
      entry: 'family',
      question: q,
      profile_uid: undefined,
      client_request_id: requestId
    })
    sessionUid.value = res.session_uid
    tCreated = Date.now()

    await startQaStream(res.session_uid, {
      onStarted: (d) => {
        streamStarted.value = true
        cancelToken.value = d.cancel_token
        tStarted = Date.now()
      },
      onSectionDelta: (d) => {
        if (!tFirstDelta) tFirstDelta = Date.now()
        // 家庭安全分节单独置顶渲染
        if (d.section_key === 'family_safety' || d.section_key === 'safety') {
          if (!safetySection.value) {
            safetySection.value = {
              key: d.section_key,
              title: d.title || '安全提示（优先阅读）',
              pinned: true,
              immutable: true,
              deltaHtml: '',
              streaming: true,
              blocks: []
            }
          }
          safetySection.value.deltaHtml += escapeHtml(d.delta)
          markAgent(d.section_key)
          return
        }
        let sec = sections.value.find((s) => s.key === d.section_key)
        if (!sec) {
          sec = { key: d.section_key, title: d.title || '生成中…', pinned: false, immutable: false, deltaHtml: '', streaming: true, blocks: [] }
          sections.value.push(sec)
        }
        sec.deltaHtml += escapeHtml(d.delta)
        markAgent(d.section_key)
      },
      onSectionDone: (d) => {
        if (d.section_key === 'family_safety' || d.section_key === 'safety') {
          if (!safetySection.value) {
            // 兜底：SSE 缓存回放流只发 started→section_done×N→completed（无 section_delta），
            // 安全分节未创建时直接用 done 帧的 title/blocks/pinned/immutable 整节创建，
            // 否则回放时置顶安全卡空白
            safetySection.value = {
              key: d.section_key,
              title: d.title || '安全提示（优先阅读）',
              pinned: d.pinned !== false,
              immutable: d.immutable !== false,
              deltaHtml: '',
              streaming: false,
              blocks: d.blocks || [],
              cached: true
            }
          } else {
            // 正常 delta 路径：分节已存在，收尾替换为完整 blocks（行为不变）
            safetySection.value.streaming = false
            safetySection.value.blocks = d.blocks || []
          }
          agents.value.find((a) => a.key === 'family_safety')!.state = 'done'
          agents.value.find((a) => a.key === 'family_safety')!.costMs = Date.now() - tAsk
          return
        }
        let sec = sections.value.find((s) => s.key === d.section_key)
        if (!sec) {
          // 兜底：缓存回放流无 section_delta，分节未创建时用 done 帧整节创建（标记 cached）
          sec = {
            key: d.section_key,
            title: d.title || (d.blocks || []).find((b) => b.title)?.title || '',
            pinned: !!d.pinned,
            immutable: !!d.immutable,
            deltaHtml: '',
            streaming: false,
            blocks: d.blocks || [],
            cached: true
          }
          sections.value.push(sec)
        } else {
          // 正常 delta 路径：分节已存在，收尾替换为完整 blocks（行为不变）
          sec.streaming = false
          sec.blocks = d.blocks || []
          const t = sec.blocks.find((b) => b.title)
          if (t?.title) sec.title = t.title
          sec.immutable = sec.blocks.some((b) => b.immutable)
        }
        // 冲突检测：done 数据携带 conflict 标记或分节间结论差异由服务端标注
        if (sec.blocks.some((b) => b.pinned) || (d as any).conflict) conflictDetected.value = true
        const agentKey = matchAgent(d.section_key)
        if (agentKey !== 'other') {
          const agent = agents.value.find((a) => a.key === agentKey)
          if (agent) {
            agent.state = 'done'
            agent.costMs = Date.now() - tAsk
          }
        }
      },
      onBlocked: (d) => {
        sections.value = []
        safetySection.value = null
        streaming.value = false
        sessionStorage.removeItem(requestIdKey)
        router.push({ path: '/app/risk-blocked', query: { session: sessionUid.value, data: encodeURIComponent(JSON.stringify(d || {})) } })
      },
      onDegraded: (d) => {
        degraded.value = true
        failedSections.value = d.failed_sections || []
        // 安全分节失败 → 整卡隐藏（与单侧降级条视觉区分）
        if (failedSections.value.some((k) => k.includes('safety') || k.includes('安全'))) {
          safetyFailed.value = true
        }
        failedSections.value.forEach((k) => {
          const agentKey = matchAgent(k)
          if (agentKey !== 'other') {
            const agent = agents.value.find((a) => a.key === agentKey)
            if (agent) agent.state = 'failed'
          }
        })
      },
      onCompleted: (d) => {
        completed.value = true
        streaming.value = false
        sessionStorage.removeItem(requestIdKey)
        // 冲突标注：completed 数据可带冲突标记
        if ((d as any)?.conflict_detected) conflictDetected.value = true
        agents.value.forEach((a) => {
          if (a.state === 'running') a.state = 'done'
          if (!a.costMs) a.costMs = Date.now() - tAsk
        })
        user.refreshQuota()
      },
      onError: (d) => {
        streaming.value = false
        ElMessage.error(d?.message || '生成中断，请重试')
      }
    })
    if (streaming.value) {
      completed.value = true
      streaming.value = false
    }
  } catch (e: any) {
    streaming.value = false
    if (e?.code === 1202) {
      // 回填问题：当日额度恢复或开通会员后可直接重发
      question.value = q
      quotaDrawer.value = true
    } else ElMessage.error(e?.message || '请求失败，请重试')
  }
}

/**
 * 按分节 key 标记对应 Agent 进行中
 * @param sectionKey 分节 key
 */
function markAgent(sectionKey: string): void {
  const agentKey = matchAgent(sectionKey)
  if (agentKey === 'other') return
  const agent = agents.value.find((a) => a.key === agentKey)
  if (agent && agent.state === 'pending') agent.state = 'running'
}

/**
 * 停止生成
 */
async function stopGen(): Promise<void> {
  if (!sessionUid.value || !cancelToken.value) return
  try {
    await cancelQaSession(sessionUid.value, cancelToken.value)
    ElMessage.success('已停止生成')
  } catch {
    ElMessage.warning('停止请求失败')
  } finally {
    streaming.value = false
  }
}

/** 加载双对象显示名 */
onMounted(async () => {
  // 挂载即拉真实额度：避免额度 chip 使用 store 默认值（0/5），与首页真实口径（0/4）不一致
  user.refreshQuota()
  try {
    const [c, p]: any = await Promise.all([getChildren(), getPets()])
    const cl = c?.children || c?.items || (Array.isArray(c) ? c : [])
    const pl = p?.pets || p?.items || (Array.isArray(p) ? p : [])
    childName.value = cl[0]?.nickname || ''
    petName.value = pl[0]?.nickname || ''
  } catch {
    // 双对象名静默为空
  }
})

onBeforeUnmount(() => {
  if (streaming.value && sessionUid.value && cancelToken.value) {
    cancelQaSession(sessionUid.value, cancelToken.value).catch(() => undefined)
  }
})
</script>

<style lang="scss" scoped>
/* ===== 页面骨架 ===== */
.qa-page {
  min-height: 100vh;
  background: var(--bg);
  padding-bottom: 132px;
}

/* 顶部白卡 */
.top-sheet {
  background: var(--surface);
  border-radius: 0 0 var(--radius-face) var(--radius-face);
  padding: var(--sp-4) var(--sp-6);
  box-shadow: var(--shadow-e1);
}

.qa-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);

  .head-title {
    flex: 1;
    text-align: center;
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }

  .head-btn {
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    color: var(--ink-1);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;

    svg { width: 20px; height: 20px; }
  }

  .head-spacer { width: 32px; flex: none; }
}

/* 同时关注对象对 */
.dual-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-4);
  flex-wrap: wrap;

  .dual-ico {
    display: flex;
    color: var(--accent);

    svg { width: 17px; height: 17px; }
  }

  .dual-label {
    font-size: var(--fs-sub);
    color: var(--ink-2);
  }

  .dual-pill {
    padding: 5px 14px;
    border-radius: var(--radius-pill);
    background: var(--accent-soft);
    border: 1px solid var(--accent-line);
    color: var(--accent);
    font-size: var(--fs-sub);
    font-weight: 600;

    &.empty {
      background: var(--surface-2);
      border-color: var(--line);
      color: var(--ink-3);
      font-weight: 400;
    }
  }
}

.dual-note {
  margin-top: var(--sp-2);
  font-size: var(--fs-caption);
  color: var(--accent);
}

.obj-quota {
  margin-left: auto;
}

/* ===== 会话流 ===== */
.stream-area {
  padding: var(--sp-4) var(--sp-6) 0;
}

/* 用户气泡 */
.bubble-row {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-bottom: var(--sp-4);
}

.user-bubble {
  max-width: 78%;
  padding: 12px 16px;
  border-radius: 18px 18px 4px 18px;
  background: var(--brand-primary-container);
  color: #fff;
  font-size: var(--fs-body);
  line-height: 1.6;
  word-break: break-word;
}

html.dark .user-bubble {
  color: var(--ink-1);
}

.bubble-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: var(--fs-caption);
  color: var(--ink-3);

  .meta-dot { color: var(--line-strong); }

  .first-flag {
    color: var(--accent);
    background: var(--accent-soft);
    border-radius: 4px;
    padding: 0 6px;
  }
}

/* ===== 调度中卡 ===== */
.dispatch-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-4) var(--sp-6);
  margin-bottom: var(--sp-4);
  box-shadow: var(--shadow-e1);
}

.dc-head {
  display: flex;
  align-items: center;
}

.dc-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 600;
}

.dc-spin {
  width: 10px;
  height: 10px;
  border: 2px solid var(--accent-line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: fq-spin 0.9s linear infinite;
}

@keyframes fq-spin {
  to { transform: rotate(360deg); }
}

/* 三段读数行 */
.dc-metrics {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  font-size: var(--fs-caption);
  color: var(--ink-3);

  strong { color: var(--ink-1); font-weight: 600; }

  .m-sep {
    width: 1px;
    height: 12px;
    background: var(--line-strong);
  }
}

/* 三 Agent 状态行 */
.dc-agents {
  margin-top: var(--sp-2);
}

.agent-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;

  & + .agent-row {
    border-top: 1px dashed var(--line);
  }

  .ag-ico { flex: none; width: 16px; height: 16px; color: var(--ink-2); }

  .ag-name {
    flex: 1;
    font-size: var(--fs-sub);
    color: var(--ink-1);
  }

  .ag-cost {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }

  .ag-state {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--fs-caption);
    min-width: 64px;
    justify-content: flex-end;

    &.done { color: var(--accent); font-weight: 600; }
    &.failed { color: var(--danger); }
    &.running, &.pending { color: var(--ink-3); }
  }
}

.ag-spin {
  width: 10px;
  height: 10px;
  border: 2px solid var(--line-strong);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: fq-spin 0.9s linear infinite;
}

/* ===== Agent 分节卡 ===== */
.agent-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  margin-bottom: var(--sp-4);
  box-shadow: var(--shadow-e1);

  &.pinned {
    background: var(--accent-soft);
    border-color: var(--accent-line);
  }
}

.ac-head {
  margin-bottom: var(--sp-3);
}

.ac-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--sc-low);
  border: 1px solid var(--line-strong);
  color: var(--ink-1);
  font-size: var(--fs-caption);
  font-weight: 600;

  /* 徽章前缀：6px 方块取自刻度标尺语汇，替代原先的 Unicode ■ */
  &::before {
    content: '';
    flex: none;
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--ink-2);
  }

  &.dark {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);

    &::before {
      background: currentColor;
    }
  }
}

html.dark .ac-badge.dark {
  color: var(--ink-1);
}

/* 编号块 */
.num-block {
  display: flex;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);
  margin-bottom: var(--sp-2);

  .agent-card.pinned & {
    background: var(--surface);
  }

  .nb-no {
    flex: none;
    font-weight: 700;
    color: var(--accent);
  }

  .nb-body {
    font-size: var(--fs-sub);
    line-height: 1.7;
    color: var(--ink-1);

    strong { font-weight: 600; }
  }
}

/* 警示文本块 */
.plain-warn {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  color: var(--ink-1);
  font-size: var(--fs-sub);
  line-height: 1.7;
  margin-bottom: var(--sp-2);
}

/* 常规文本块 */
.block-text {
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);
  margin-bottom: var(--sp-2);

  .bt-title { color: var(--ink-1); font-weight: 600; }
}

.delta-text {
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);
  word-break: break-word;
}

/* 多 Agent 协同说明折叠 */
.coop-fold {
  margin-top: var(--sp-2);

  summary {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-caption);
    color: var(--ink-3);
    cursor: pointer;
    list-style: none;

    &::-webkit-details-marker { display: none; }

    svg { width: 14px; height: 14px; }

    .chev { margin-left: auto; transition: transform 0.2s; }

    &.open .chev { transform: rotate(180deg); }
  }

  &[open] summary .chev {
    transform: rotate(180deg);
  }

  p {
    margin-top: var(--sp-2);
    font-size: var(--fs-caption);
    color: var(--ink-2);
    line-height: 1.7;

    strong { color: var(--ink-1); }
  }
}

/* ===== 底部输入区 ===== */
.input-dock {
  position: fixed;
  bottom: var(--keyboard-offset, 0px);
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 430px;
  padding: var(--sp-3) var(--sp-6) calc(var(--sp-2) + env(safe-area-inset-bottom));
  background: var(--surface);
  border-top: 1px solid var(--line);
  z-index: 90;
}

.input-row {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
}

.q-input {
  flex: 1;
  height: 44px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-1);
  font-family: inherit;
  /* 16px 起：iOS 聚焦不再自动放大页面 */
  font-size: var(--fs-body);

  &:focus {
    outline: none;
    border-color: var(--accent);
  }

  &::placeholder { color: var(--ink-3); }
}

.send-btn {
  width: 44px;
  height: 44px;
  border: none;
  border-radius: var(--radius-ctl);
  background: var(--accent);
  color: var(--on-accent);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &:disabled {
    background: var(--line-strong);
    cursor: not-allowed;
  }

  svg { width: 19px; height: 19px; }

  &.stop { background: var(--danger); }
}

.stop-square {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  background: #fff;
}
</style>

<style lang="scss" scoped>
.family-guide {
  padding: 28px 4px 26px;
}

.family-guide-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;

  h2 {
    color: var(--ink-1);
    font-size: 21px;
    font-weight: 700;
    line-height: 1.3;
  }

  span {
    flex: none;
    color: var(--ink-3);
    font-size: var(--fs-caption);
  }
}

.lens-route {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 16px 0 13px;
  margin-top: 8px;
  border-bottom: 1px solid var(--line);
}

.lens-step {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-2);
  font-size: 11px;
  white-space: nowrap;

  i {
    width: 7px;
    height: 7px;
    flex: none;
    border-radius: 1px;
    background: currentColor;
  }

  &.step-safety { color: var(--accent); font-weight: 600; }
  &.step-child { color: var(--perspective-child); }
  &.step-pet { color: var(--perspective-pet); }
}

.route-link {
  height: 1px;
  min-width: 8px;
  flex: 1;
  background: var(--line-strong);
}

.family-guide > p:first-of-type {
  margin-top: 14px;
  color: var(--ink-2);
  font-size: var(--fs-body);
  line-height: 1.6;
}

.guide-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  padding-top: 11px;
  margin-top: 12px;
  border-top: 1px solid var(--line);

  span {
    position: relative;
    padding-left: 10px;
    color: var(--ink-2);
    font-size: var(--fs-caption);

    &::before {
      position: absolute;
      top: .62em;
      left: 0;
      width: 5px;
      height: 5px;
      border-radius: 1px;
      background: var(--accent);
      content: '';
    }
  }
}

.family-guide .guide-note {
  margin-top: 12px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
  line-height: 1.55;
}

.dual-pill--child:not(.empty) { color: var(--perspective-child); background: var(--perspective-child-soft); border-color: transparent; }
.dual-pill--pet:not(.empty) { color: var(--perspective-pet); background: var(--perspective-pet-soft); border-color: transparent; }

.dispatch-card {
  border-radius: 4px 12px 12px 12px;
  border-color: var(--line);
  box-shadow: none;
}

.agent-row {
  border-radius: 4px;

  &:nth-child(1) .ag-ico { color: var(--perspective-child); }
  &:nth-child(2) .ag-ico { color: var(--perspective-pet); }
  &:nth-child(3) .ag-ico { color: var(--accent); }
}

.agent-card {
  border: 0;
  border-top: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
  box-shadow: none;

  &.pinned {
    border: 0;
    border-radius: 4px 12px 12px 12px;
    background: var(--accent-soft);
  }
}

.dual-pill { border-radius: 6px; }
.input-dock { border-top-color: var(--line-strong); }

@media (max-width: 360px) {
  .lens-route { gap: 5px; }
  .lens-step { gap: 4px; font-size: 10px; }
  .route-link { min-width: 4px; }
}
</style>

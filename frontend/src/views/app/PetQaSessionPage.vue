<!--
  PetQaSessionPage SC-09 宠物问答（Stitch 稿重构）
  与育儿问答同构（SSE 渐进渲染 / blocked 清空跳拦截页 / 幂等重试），
  附加：行为快捷词 chips（甩尾/低吼/哈气/护食/飞机耳）+ 有孩子档案时互动安全提醒条 +
  急症警示块 + 刻度带块（band）+ 知识源/有帮助反馈行。
  视觉：页头（返回+标题）/ 对象 pill（● 问答对象：名（品种）+已建档案标签）/
  绿底联动提醒 / 用户气泡（已送达·档案已读入）/ 安全检查行 /
  AI 生成内容卡（编号建议条+风险黄条+就医骨架）/ 底部 chips+语音+输入条。
-->
<template>
  <div class="qa-page qa-page--pet">
    <!-- 顶部白卡：页头 + 对象行 + 联动提醒 -->
    <div class="top-sheet">
      <header class="qa-head">
        <button class="head-btn touch-target" aria-label="返回" @click="$safeBack()">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <h1 class="head-title">宠物问答 · 猫狗</h1>
        <button class="head-btn dim touch-target" type="button" aria-label="更多" @click="onMore">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="12" r="1.6" fill="currentColor" />
            <circle cx="12" cy="12" r="1.6" fill="currentColor" />
            <circle cx="19" cy="12" r="1.6" fill="currentColor" />
          </svg>
        </button>
      </header>

      <!-- 问答对象行：● pill + 已建档案标签 -->
      <div class="obj-row">
        <span class="obj-dot" aria-hidden="true" />
        <el-popover placement="bottom-start" :width="280" trigger="click" popper-class="obj-popper">
          <template #reference>
            <button class="obj-pill touch-target" type="button">
              <span class="obj-label">
                问答对象：<strong>{{ petDisplayName || '未选择' }}</strong>
              </span>
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </template>
          <div class="obj-menu">
            <p class="obj-menu-title">宠物档案</p>
            <div
              v-for="p in pets"
              :key="p.uid"
              class="obj-opt"
              :class="{ current: p.uid === profileUid }"
              @click="pickProfile(p.uid)"
            >
              <span>{{ petOptionLabel(p) }}</span>
              <svg v-if="p.uid === profileUid" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
            <p v-if="!pets.length" class="obj-empty">暂无宠物档案</p>
          </div>
        </el-popover>
        <span v-if="profileUid" class="archived-tag">已建档案</span>
        <span v-if="user.quotaUnlimited" class="quota-chip obj-quota numeric">今日额度 不限次</span>
        <span v-else class="quota-chip obj-quota numeric">今日额度 {{ user.quotaUsed }}/{{ user.quotaLimit }}</span>
      </div>

      <!-- 联动提醒条：有孩子档案时（绿底） -->
      <div v-if="hasChildren" class="link-note">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Zm0 5v5m0 2.5v.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <p>已自动附加「孩子-宠物互动安全提醒」 · 依据：存在孩子档案{{ childName ? ` ${childName}` : '' }}</p>
      </div>
    </div>

    <!-- 会话流区域 -->
    <div class="stream-area">
      <!-- 用户气泡 -->
      <div v-if="lastQuestion" class="bubble-row">
        <div class="user-bubble">{{ lastQuestion }}</div>
        <p class="bubble-meta">
          <span v-if="askedAt" class="numeric">今日 {{ askedAt }}</span>
          <span class="meta-dot">·</span>
          <span>已送达 · 多模态档案已读入</span>
        </p>
      </div>

      <!-- 内容安全检查行 -->
      <div v-if="streaming" class="safe-check">
        <template v-if="!streamStarted">
          <span class="sc-spin" aria-hidden="true" />
          <span>正在检查内容安全…</span>
        </template>
        <template v-else>
          <svg viewBox="0 0 24 24" class="sc-shield" fill="none" aria-hidden="true">
            <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
          </svg>
          <span class="sc-pass">通过</span>
          <i class="sc-divider" />
          <span class="sc-agent">宠物 Agent 生成中（≤8s）</span>
        </template>
      </div>

      <!-- AI 生成内容卡 -->
      <section v-if="streamStarted || sections.length" class="ai-card">
        <header class="ai-head">
          <span class="ai-badge-ico" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <rect x="5" y="7" width="14" height="12" rx="3" stroke="currentColor" stroke-width="1.75" />
              <path d="M12 4v3M9.5 12.5v1m5-1v1" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            </svg>
          </span>
          <h2 class="ai-title">AI 生成内容 · 仅供参考</h2>
          <button class="copy-btn" type="button" :disabled="!canCopy" @click="copyAnswer">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.75" />
              <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" stroke="currentColor" stroke-width="1.75" />
            </svg>
            {{ copied ? '已复制' : '复制' }}
          </button>
        </header>

        <!-- 分节渐进渲染；pinned 分节（安全类）用护盾面标识 -->
        <div
          v-for="(sec, si) in sections"
          :key="sec.key"
          class="ai-sec"
          :class="{ 'not-last': si < sections.length - 1, 'ai-sec--pinned': sec.pinned }"
        >
          <h3 class="sec-bar-head">
            <svg v-if="sec.pinned" class="sec-pin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" />
              <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            {{ sec.title }}
          </h3>
          <div v-if="sec.streaming" class="delta-text" v-html="sec.deltaHtml" />
          <template v-else>
            <template v-for="b in sec.blocks" :key="b.block_id">
              <LockedBlock
                v-if="b.access_tier === 'block'"
                title="会员内容"
                :summary="b.title || '该部分为会员深度内容'"
                @unlock="$router.push('/app/member')"
              />
              <!-- 行为刻度带块：GraduatedBand 接入点 -->
              <div v-else-if="b.type === 'band'" class="band-wrap">
                <GraduatedBand
                  :label="b.title || '行为等级评估'"
                  :bands="b.bands || ['平静探索', '轻度警觉', '防御警告', '直接攻击']"
                  :value="typeof b.value === 'number' ? b.value : 0.6"
                />
              </div>
              <!-- 急症警示块（professional_referral） -->
              <div v-else-if="b.type === 'emergency'" class="emergency">
                <div class="em-head">
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  <strong>{{ b.title || '急症警示' }}</strong>
                </div>
                <p class="em-body">{{ b.content }}</p>
                <p class="em-note">以上情况请立即联系宠物医院，勿等待线上建议</p>
              </div>
              <!-- 风险提示：黄条 -->
              <div v-else-if="b.type === 'warn'" class="block-warn">
                <p class="bw-title">
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  {{ b.title || '风险提示' }}
                </p>
                <p class="bw-body">{{ b.content }}</p>
              </div>
              <!-- 建议应对：编号条 -->
              <p v-else-if="isActionSec(sec)" class="block-numbered">
                <span class="num numeric">{{ padNum(numberedIndex(sec, b)) }}</span>
                <span class="nb-text">{{ b.content }}</span>
              </p>
              <!-- 常规文本块 -->
              <p v-else class="block-text">
                <strong v-if="b.title" class="bt-title">{{ b.title }}：</strong>{{ b.content }}
              </p>
            </template>
          </template>
        </div>

        <!-- started 后未收到 delta 的骨架占位 -->
        <template v-if="streamStarted && sections.length === 0">
          <SkeletonBlock :height="16" round style="margin-bottom: 12px" />
          <SkeletonBlock :height="64" style="margin-bottom: 12px" />
          <SkeletonBlock :height="44" />
        </template>

        <StatusStrip v-if="degraded" type="degraded" :text="`部分分节生成失败（${failedSections.join('、')}），已展示可获取的内容`" />
        <StatusStrip v-if="completed && !degraded" type="readonly" text="本次回答已生成完毕" />

        <!-- 知识源 + 有帮助反馈 -->
        <footer v-if="completed" class="ai-foot">
          <span class="src-text">知识源：{{ sourceLabel }}</span>
          <button class="helpful-btn" :class="{ done: helpfulDone }" type="button" @click="markHelpful">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M7 11v9m0-9 3.5-7.2a2 2 0 0 1 3.7 1.4L13.5 10H18a2 2 0 0 1 2 2.4l-1.2 5.6a2 2 0 0 1-2 1.6H7m0-8.6H4.6A1.6 1.6 0 0 0 3 12.6v5.8A1.6 1.6 0 0 0 4.6 20H7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            {{ helpfulDone ? '已感谢反馈' : '有帮助' }}
          </button>
        </footer>
      </section>

      <ScenarioGuide
        v-if="!streamStarted && !sections.length && !lastQuestion"
        tone="pet"
        heading="从一个动作开始观察"
        example="比如：猫最近总甩尾、哈气，是在表达什么？"
        :factors="['发生情境', '身体信号', '持续多久']"
        note="有孩子档案时，回答会带上互动安全提醒。"
      />
    </div>

    <!-- 底部输入区；键盘避让走 CSS 变量：过渡期 motion.scss 需接管 bottom 做重锚定 -->
    <div class="input-dock" :style="{ '--keyboard-offset': keyboardOffset + 'px' }">
      <!-- 快捷词 chips（空态可用） -->
      <div v-if="!streamStarted && sections.length === 0" class="chips-row">
        <button v-for="c in QUICK" :key="c" class="chip" :disabled="streaming" @click="applyChip(c)">{{ c }}</button>
        <span class="chips-note">语音暂不支持</span>
      </div>
      <div class="input-row">
        <button class="voice-btn" disabled title="暂不支持">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 1 1-6 0V7a3 3 0 0 1 3-3Zm-7 8a7 7 0 0 0 14 0m-7 7v2" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            <path d="M4 4l16 16" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </button>
        <input v-model="question" class="q-input" :disabled="streaming" placeholder="输入你的宠物问题…" maxlength="500" @keydown.enter="ask" />
        <button v-if="streaming" class="send-btn stop" aria-label="停止" @click="stopGen"><span class="stop-square" /></button>
        <button v-else class="send-btn" :disabled="!question.trim()" aria-label="发送" @click="ask">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m5 12 13-7-3.5 7L21 12l-6.5 0L18 19 5 12Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
      <AiDisclaimer ai-label="内容由 AI 生成" disclaimer="仅供参考，不替代执业兽医诊疗" />
    </div>

    <!-- 额度用尽抽屉（1202 触发） -->
    <QuotaDrawer v-model="quotaDrawer" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createQaSession, cancelQaSession, getChildren, getPets } from '@/api/client'
import { startQaStream } from '@/api/stream'
import { newRequestId } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { useKeyboardOffset } from '@/composables/useKeyboardOffset'
import QuotaDrawer from '@/components/QuotaDrawer.vue'
import GraduatedBand from '@/components/GraduatedBand.vue'
import LockedBlock from '@/components/LockedBlock.vue'
import StatusStrip from '@/components/StatusStrip.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import ScenarioGuide from '@/components/ScenarioGuide.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

const router = useRouter()
const route = useRoute()
const user = useUserStore()
/** 软键盘遮挡高度：输入区抬升用 */
const { keyboardOffset } = useKeyboardOffset()
/** 额度用尽抽屉（1202 触发） */
const quotaDrawer = ref(false)

/** 行为快捷词 */
const QUICK = ['甩尾', '低吼', '哈气', '护食', '飞机耳']

/** 问答对象 */
const profileUid = ref<string | null>(user.currentProfileUid)
const question = ref('')
const sessionUid = ref('')
const cancelToken = ref('')

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
const streamStarted = ref(false)
const completed = ref(false)
const degraded = ref(false)
const failedSections = ref<string[]>([])
const streaming = ref(false)
const requestIdKey = 'jiaban_qa_request_id_pet'

/** 是否有孩子档案（互动安全提醒条开关） */
const hasChildren = ref(false)
/** 第一个孩子档案名（联动提醒展示） */
const childName = ref('')
/** 宠物档案列表（对象 pill 数据源） */
const pets = ref<any[]>([])
/** 最近一次提问（用户气泡） */
const lastQuestion = ref('')
/** 提问时间戳（HH:mm） */
const askedAt = ref('')
/** 复制成功态（2s 复位） */
const copied = ref(false)
/** 有帮助反馈完成态（本地轻交互） */
const helpfulDone = ref(false)

/** 当前宠物显示名（名+品种） */
const petDisplayName = computed(() => {
  const hit = pets.value.find((p) => p.uid === profileUid.value)
  if (!hit) return ''
  return hit.breed && hit.breed !== 'unknown' ? `${hit.nickname}（${hit.breed}）` : hit.nickname
})

/** 知识源展示文案 */
const sourceLabel = '平台审核知识条目（犬猫行为）'

/** 是否可复制（存在已完成内容） */
const canCopy = computed(() => sections.value.some((s) => !s.streaming && s.blocks.length))

/**
 * 下拉选项显示文案（名+品种）
 * @param p 宠物档案
 * @returns 显示文案
 */
function petOptionLabel(p: any): string {
  return p.breed && p.breed !== 'unknown' ? `${p.nickname}（${p.breed}）` : p.nickname
}

/**
 * 判断分节是否为「建议应对」类（编号条渲染）
 * @param sec 分节状态
 * @returns 是否应对建议类
 */
function isActionSec(sec: SectionState): boolean {
  return (sec.title || '').includes('应对') || (sec.title || '').includes('建议')
}

/**
 * 计算块在分节内的序号（从 1 起）
 * @param sec 分节状态
 * @param block 当前块
 * @returns 序号
 */
function numberedIndex(sec: SectionState, block: any): number {
  return sec.blocks.filter((b) => b.type !== 'band' && b.type !== 'warn' && b.access_tier !== 'block').indexOf(block) + 1
}

/**
 * 序号格式化（1 → 01）
 * @param n 序号
 * @returns 两位序号文本
 */
function padNum(n: number): string {
  return String(n).padStart(2, '0')
}

/**
 * 选中宠物档案
 * @param uid 档案 uid
 */
function pickProfile(uid: string): void {
  profileUid.value = uid
  user.setCurrentProfile(uid)
}

/**
 * 页头更多按钮（预留扩展）
 */
function onMore(): void {
  ElMessage.info('会话设置开发中')
}

/**
 * 标记有帮助（本地态，轻反馈）
 */
function markHelpful(): void {
  helpfulDone.value = true
  ElMessage.success('感谢你的反馈')
}

/**
 * 应用快捷词到输入框
 * @param word 快捷词
 */
function applyChip(word: string): void {
  question.value = question.value ? `${question.value}${word}` : word
}

/**
 * 复制已完成回答文本
 * @throws 剪贴板不可用时提示失败
 */
async function copyAnswer(): Promise<void> {
  const text = sections.value
    .filter((s) => !s.streaming)
    .map((s) => `【${s.title}】\n${s.blocks.map((b) => (b.title ? `${b.title}：${b.content}` : b.content)).join('\n')}`)
    .join('\n\n')
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    ElMessage.success('回答已复制')
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    ElMessage.error('复制失败，请长按文本手动复制')
  }
}

/**
 * HTML 转义
 * @param s 原始文本
 * @returns 转义后文本
 */
function escapeHtml(s: string): string {
  // 空值防护：流式分片偶发 null/undefined 时直接拼接会抛异常中断 SSE 消费链路（与育儿/家庭页口径一致）
  const t = String(s ?? '')
  return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

/**
 * 重置渲染状态
 */
function resetRender(): void {
  sections.value = []
  streamStarted.value = false
  completed.value = false
  degraded.value = false
  failedSections.value = []
  cancelToken.value = ''
}

/**
 * 发起提问（SSE 同育儿问答；blocked 清空正文跳拦截页）
 * @param text 显式提问文本（首页 ?q= 接棒）；缺省取输入框
 * @throws 网络错误消息提示；1202 弹额度抽屉并回填问题
 */
async function ask(text?: string): Promise<void> {
  const q = (text ?? question.value).trim()
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
  try {
    const res = await createQaSession({
      entry: 'pet',
      question: q,
      profile_uid: profileUid.value || undefined,
      client_request_id: requestId
    })
    sessionUid.value = res.session_uid

    await startQaStream(res.session_uid, {
      onStarted: (d) => {
        streamStarted.value = true
        cancelToken.value = d.cancel_token
      },
      onSectionDelta: (d) => {
        let sec = sections.value.find((s) => s.key === d.section_key)
        if (!sec) {
          sec = { key: d.section_key, title: d.title || '生成中…', pinned: false, immutable: false, deltaHtml: '', streaming: true, blocks: [] }
          sections.value.push(sec)
        }
        sec.deltaHtml += escapeHtml(d.delta)
      },
      onSectionDone: (d) => {
        let sec = sections.value.find((s) => s.key === d.section_key)
        if (!sec) {
          // 兜底：SSE 缓存回放流只发 started→section_done×N→completed（无 section_delta），
          // 分节未创建时直接用 done 帧的 title/blocks/pinned/immutable 整节创建，
          // 否则回放时回答区 0 分节空渲染
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
          sec.pinned = sec.blocks.some((b) => b.pinned)
          sec.immutable = sec.blocks.some((b) => b.immutable)
        }
      },
      onBlocked: (d) => {
        sections.value = []
        streaming.value = false
        sessionStorage.removeItem(requestIdKey)
        router.push({ path: '/app/risk-blocked', query: { session: sessionUid.value, data: encodeURIComponent(JSON.stringify(d || {})) } })
      },
      onDegraded: (d) => {
        degraded.value = true
        failedSections.value = d.failed_sections || []
      },
      onCompleted: () => {
        completed.value = true
        streaming.value = false
        sessionStorage.removeItem(requestIdKey)
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
    } else {
      ElMessage.error(e?.message || '请求失败，请重试')
    }
  }
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

onMounted(async () => {
  // 挂载即拉真实额度：避免额度 chip 使用 store 默认值（0/5），与首页真实口径（0/4）不一致
  user.refreshQuota()
  try {
    const [c, p]: any = await Promise.all([getChildren(), getPets()])
    const cl = c?.children || c?.items || (Array.isArray(c) ? c : [])
    const pl = p?.pets || p?.items || (Array.isArray(p) ? p : [])
    hasChildren.value = cl.length > 0
    childName.value = cl[0]?.nickname || ''
    pets.value = pl
  } catch {
    hasChildren.value = false
    pets.value = []
  }
  // 本地缓存的问答对象可能已被删除：失效即清除，回落未选口径
  if (profileUid.value && !pets.value.some((p: any) => p.uid === profileUid.value)) {
    profileUid.value = null
    user.setCurrentProfile(null)
  }
  // 首页「问一下」接棒：携带 ?q= 预填并自动提问一次；先 replace 去 query，防返回重发
  const q = String(route.query.q || '').trim()
  if (q) {
    void router.replace({ path: route.path })
    void ask(q)
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
  padding-bottom: 150px;
}

/* 顶部白卡 */
.top-sheet {
  background: var(--surface);
  border-radius: 0 0 var(--radius-face) var(--radius-face);
  padding: var(--sp-4) var(--sp-6) var(--sp-4);
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

    &.dim { color: var(--ink-3); }
  }
}

/* 对象行 */
.obj-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-4);
}

.obj-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 1px;
  background: var(--accent);
}

.obj-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-pill);
  background: var(--sc-low);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  cursor: pointer;

  strong {
    color: var(--ink-1);
    font-weight: 600;
    font-size: var(--fs-sub);
  }

  svg {
    width: 14px;
    height: 14px;
    color: var(--ink-3);
  }
}

/* 已建档案标签 */
.archived-tag {
  flex: none;
  font-size: var(--fs-caption);
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-pill);
  padding: 2px 10px;
}

.obj-quota {
  margin-left: auto;
}

/* 对象下拉菜单 */
.obj-menu-title {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  margin-bottom: var(--sp-2);
}

.obj-opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  font-size: var(--fs-sub);
  color: var(--ink-1);
  cursor: pointer;

  svg { width: 15px; height: 15px; color: var(--accent); }

  &.current { background: var(--accent-soft); }
}

.obj-empty {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* 联动提醒条：绿底 */
.link-note {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  font-size: var(--fs-caption);
  line-height: 1.6;

  svg { width: 15px; height: 15px; flex: none; margin-top: 2px; }

  p { color: var(--accent); }
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
  gap: 5px;
  margin-top: 4px;
  font-size: var(--fs-caption);
  color: var(--ink-3);

  .meta-dot { color: var(--line-strong); }
}

/* 安全检查行 */
.safe-check {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--ink-3);

  .sc-shield { width: 15px; height: 15px; color: var(--accent); }

  .sc-pass { color: var(--accent); font-weight: 600; }

  .sc-divider {
    width: 1px;
    height: 12px;
    background: var(--line-strong);
  }

  .sc-agent { color: var(--ink-2); }
}

.sc-spin {
  width: 14px;
  height: 14px;
  border: 2px solid var(--line-strong);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: pet-spin 0.9s linear infinite;
}

@keyframes pet-spin {
  to { transform: rotate(360deg); }
}

/* ===== AI 生成内容卡 ===== */
.ai-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  box-shadow: var(--shadow-e1);
}

.ai-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--line);

  .ai-badge-ico {
    width: 26px;
    height: 26px;
    border-radius: var(--radius-ctl);
    background: var(--accent-soft);
    color: var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
    flex: none;

    svg { width: 16px; height: 16px; }
  }

  .ai-title {
    flex: 1;
    font-size: var(--fs-sub);
    font-weight: 700;
    color: var(--ink-1);
  }

  .copy-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: none;
    background: none;
    color: var(--accent);
    font-size: var(--fs-caption);
    cursor: pointer;

    svg { width: 14px; height: 14px; }

    &:disabled { color: var(--ink-3); cursor: not-allowed; }
  }
}

/* 分节 */
.ai-sec {
  padding-top: var(--sp-4);

  &.not-last {
    padding-bottom: var(--sp-4);
    border-bottom: 1px solid var(--line);
  }

  /* pinned 分节（安全类内容）：护盾面 + 同色发丝线 */
  &.ai-sec--pinned {
    margin-top: var(--sp-2);
    padding: var(--sp-3) var(--sp-4);
    background: var(--accent-soft);
    border: 1px solid var(--accent-line);
    border-radius: var(--radius-ctl);

    &.not-last {
      border-bottom: 1px solid var(--accent-line);
    }
  }
}

/* 分节竖条标题（刻度方点：器械物件语汇，替代彩色竖条） */
.sec-bar-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--sp-2);
  font-size: var(--fs-sub);
  font-weight: 700;
  color: var(--ink-1);

  &::before {
    content: '';
    flex: none;
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }

  .sec-pin {
    width: 15px;
    height: 15px;
    color: var(--accent);
    flex: none;
  }
}

/* pinned 分节：护盾图标替代刻度方点（安全类内容的身份标识） */
.ai-sec--pinned .sec-bar-head::before {
  display: none;
}

.delta-text {
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);
  word-break: break-word;
}

/* 刻度带容器 */
.band-wrap {
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

/* 建议应对：编号条 */
.block-numbered {
  display: flex;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);
  margin-bottom: var(--sp-2);

  .num {
    flex: none;
    font-weight: 700;
    color: var(--accent);
    font-size: var(--fs-sub);
  }

  .nb-text {
    font-size: var(--fs-sub);
    line-height: 1.7;
    color: var(--ink-2);
  }
}

/* 风险提示：黄条 */
.block-warn {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  margin-bottom: var(--sp-2);

  .bw-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 700;
    color: var(--warn);
    font-size: var(--fs-sub);

    svg { width: 15px; height: 15px; }
  }

  .bw-body {
    margin-top: 4px;
    font-size: var(--fs-sub);
    color: var(--ink-1);
    line-height: 1.7;
  }
}

/* 急症警示块：红色高对比 */
.emergency {
  background: var(--danger-soft);
  border: 1px solid var(--danger);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
  margin-bottom: var(--sp-2);

  .em-head {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    color: var(--danger);
    font-weight: 700;

    svg { width: 18px; height: 18px; }
  }

  .em-body {
    margin-top: var(--sp-2);
    font-size: var(--fs-sub);
    color: var(--ink-1);
    line-height: 1.7;
  }

  .em-note {
    margin-top: var(--sp-2);
    font-size: var(--fs-caption);
    color: var(--danger);
  }
}

/* 知识源 + 反馈行 */
.ai-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);

  .src-text {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }

  .helpful-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--ink-2);
    font-size: var(--fs-caption);
    padding: 4px 12px;
    cursor: pointer;

    svg { width: 14px; height: 14px; }

    &.done {
      color: var(--accent);
      border-color: var(--accent-line);
      background: var(--accent-soft);
    }
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

/* 快捷词 chips 行 */
.chips-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding-bottom: var(--sp-2);

  .chip {
    padding: 11px 14px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--ink-2);
    font-size: var(--fs-caption);
    cursor: pointer;

    &:active {
      background: var(--accent-soft);
      color: var(--accent);
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  .chips-note {
    margin-left: auto;
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }
}

.input-row {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
}

.voice-btn {
  width: 44px;
  height: 44px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  color: var(--ink-3);
  cursor: not-allowed;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg { width: 19px; height: 19px; }
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
.qa-page {
  min-height: 100dvh;
  background: var(--bg);
  padding-bottom: 0;
}

.top-sheet {
  padding: 10px 20px 14px;
  border-radius: 0;
  border-bottom: 1px solid var(--line);
  box-shadow: none;
}

.qa-head .head-title { text-align: left; font-size: var(--fs-body); }
.obj-row { align-items: flex-start; margin-top: 10px; }
.obj-pill { border-radius: 6px; background: var(--surface-2); }
.archived-tag { border-radius: 4px; }
.link-note { border: 0; border-radius: 4px 10px 10px 10px; background: var(--accent-soft); }

.stream-area {
  min-height: 0;
  padding: 12px 20px 24px;
}

.bubble-row { align-items: flex-start; margin: 4px 0 18px; }

.user-bubble {
  max-width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 4px 12px 12px 12px;
  background: var(--surface);
  color: var(--ink-1);
}

.ai-card { padding: 18px 0; border-radius: 0; box-shadow: none; }
.ai-head { padding-bottom: 12px; border-bottom: 1px solid var(--line); }
.ai-head .ai-badge-ico { border-radius: 6px; color: var(--perspective-pet); background: var(--perspective-pet-soft); }
.ai-sec { padding: 18px 0; border-bottom: 1px solid var(--line); }
.ai-sec--pinned { margin-top: 12px; padding: 14px; border: 0; border-radius: 4px 12px 12px 12px; background: var(--accent-soft); }
.sec-bar-head { color: var(--perspective-pet); }
.ai-sec--pinned .sec-bar-head { color: var(--accent); }

.input-dock { padding-inline: 16px; border-top-color: var(--line-strong); }
.input-dock :deep(.disclaimer-text > span) { color: var(--ink-2); }
.voice-btn,
.send-btn { border-radius: 8px; }

@media (max-width: 360px) {
  .top-sheet { padding-inline: 14px; }
  .stream-area { padding-inline: 14px; }
}
</style>

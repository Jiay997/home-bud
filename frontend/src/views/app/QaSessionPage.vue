<!--
  QaSessionPage SC-08 育儿问答（Stitch 稿重构）
  流程：输入问题 → 创建会话（幂等 client_request_id，失败重试复用）→
  SSE 渐进渲染：started（骨架占位）→ section_delta（追加，escape 后渲染）→
  section_done（替换完整 blocks）→ completed；
  blocked → 清空全部已渲染正文并跳 RiskBlockPage；
  语音按钮灰态（暂不支持）；AiDisclaimer 常驻。
  视觉：页头与对象档案 / 未选档案提示 / 问题观察条目 / 内容安全检查行 /
  AI 回答分节与置顶安全面 / 底部固定输入。以记录式层级替代聊天气泡堆叠。
-->
<template>
  <div class="qa-page qa-page--parenting">
    <!-- 顶部白卡：页头 + 对象选择 + 档案提示 -->
    <div class="top-sheet">
      <header class="qa-head">
        <button class="head-btn touch-target" aria-label="返回" @click="$safeBack()">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <h1 class="head-title">育儿问答 · 0-6 岁</h1>
        <button class="head-btn dim touch-target" type="button" aria-label="更多" @click="onMore">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="12" r="1.6" fill="currentColor" />
            <circle cx="12" cy="12" r="1.6" fill="currentColor" />
            <circle cx="19" cy="12" r="1.6" fill="currentColor" />
          </svg>
        </button>
      </header>

      <!-- 问答对象选择器 pill + 多孩提示 -->
      <div class="obj-row">
        <el-popover placement="bottom-start" :width="260" trigger="click" popper-class="obj-popper">
          <template #reference>
            <button class="obj-pill touch-target" type="button">
              <span class="obj-label">问答对象：<strong>{{ profileName || '未选择' }}</strong></span>
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </template>
          <div class="obj-menu">
            <p class="obj-menu-title">孩子档案</p>
            <div
              v-for="c in children"
              :key="c.uid"
              class="obj-opt"
              :class="{ current: c.uid === profileUid }"
              @click="pickProfile(c.uid)"
            >
              <span>{{ c.nickname }}</span>
              <svg v-if="c.uid === profileUid" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
            <p v-if="!children.length" class="obj-empty">暂无孩子档案</p>
          </div>
        </el-popover>
        <span class="obj-meta">
          <span class="obj-hint">多孩可切换</span>
          <span v-if="user.quotaUnlimited" class="quota-chip numeric">今日额度 不限次</span>
          <span v-else class="quota-chip numeric">今日额度 {{ user.quotaUsed }}/{{ user.quotaLimit }}</span>
        </span>
      </div>

      <!-- 未选档案提示条：黄底 -->
      <div v-if="!profileUid" class="profile-tip">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.75" />
          <path d="M12 8v4.5m0 3v.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
        </svg>
        <p>未选档案：按「通用 1-3 岁」回答</p>
        <button class="tip-link touch-target" type="button" @click="$router.push('/app/profiles')">补充档案</button>
      </div>
    </div>

    <!-- 会话流区域 -->
    <div class="stream-area">
      <!-- 用户气泡：提问后显示 -->
      <div v-if="lastQuestion" class="bubble-row">
        <div class="user-bubble">{{ lastQuestion }}</div>
        <p v-if="askedAt" class="bubble-time numeric">{{ askedAt }}</p>
      </div>

      <!-- 内容安全检查行：生成中可见 -->
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
          <span class="sc-agent">育儿 Agent 生成中（≤8s）</span>
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

        <!-- 分节渐进渲染：delta → done；pinned 分节（安全类）用护盾面标识 -->
        <div
          v-for="(sec, si) in sections"
          :key="sec.key"
          class="ai-sec"
          :class="{ 'not-last': si < sections.length - 1, 'ai-sec--pinned': sec.pinned }"
        >
          <h3 class="sec-dot-head">
            <svg v-if="sec.pinned" class="sec-pin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" />
              <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <i v-else class="dot" aria-hidden="true" />
            {{ sec.title }}
          </h3>
          <!-- 流式增量 -->
          <div v-if="sec.streaming" class="delta-text" v-html="sec.deltaHtml" />
          <!-- 完整 blocks -->
          <template v-else>
            <template v-for="b in sec.blocks" :key="b.block_id">
              <LockedBlock
                v-if="b.access_tier === 'block'"
                title="会员内容"
                :summary="b.title || '该部分为会员深度内容'"
                @unlock="$router.push('/app/member')"
              />
              <!-- 不建议做法：警示红头块 -->
              <div v-else-if="b.type === 'warn'" class="block-warn">
                <p class="bw-title">
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  {{ b.title || '不建议做法' }}
                </p>
                <p class="bw-body">{{ b.content }}</p>
              </div>
              <!-- 适用前提：绿底条块 -->
              <div v-else-if="isPremiseSec(sec)" class="block-premise">{{ b.content }}</div>
              <!-- 常规要点：圆点条目 -->
              <p v-else class="block-point">
                <i class="pt-dot" aria-hidden="true" />
                <span><strong v-if="b.title">{{ b.title }}：</strong>{{ b.content }}</span>
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

        <!-- 降级 / 完成状态 -->
        <StatusStrip v-if="degraded" type="degraded" :text="`部分分节生成失败（${failedSections.join('、')}），已展示可获取的内容`" />
        <StatusStrip v-if="completed && !degraded" type="readonly" text="本次回答已生成完毕" />
      </section>

      <ScenarioGuide
        v-if="!streamStarted && !sections.length && !lastQuestion"
        heading="先记下发生的场景"
        example="比如：一岁半的孩子，最近不肯吃晚饭。"
        :factors="['大概月龄', '具体表现', '试过什么']"
        note="建议按档位呈现，不给孩子贴固定标签。"
      />
    </div>

    <!-- 底部输入区；键盘避让走 CSS 变量：过渡期 motion.scss 需接管 bottom 做重锚定 -->
    <div class="input-dock" :style="{ '--keyboard-offset': keyboardOffset + 'px' }">
      <div class="input-row">
        <!-- 语音按钮：灰态斜杠 -->
        <button class="voice-btn" disabled title="暂不支持">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 1 1-6 0V7a3 3 0 0 1 3-3Zm-7 8a7 7 0 0 0 14 0m-7 7v2" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            <path d="M4 4l16 16" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </button>
        <input
          v-model="question"
          class="q-input"
          :disabled="streaming"
          placeholder="输入你的问题…"
          maxlength="500"
          @keydown.enter="ask"
        />
        <!-- 生成中：停止；空闲：发送 -->
        <button v-if="streaming" class="send-btn stop" aria-label="停止" @click="stopGen">
          <span class="stop-square" />
        </button>
        <button v-else class="send-btn" :disabled="!question.trim()" aria-label="发送" @click="ask">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 19V6m0 0-5.5 5.5M12 6l5.5 5.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
      <AiDisclaimer ai-label="内容由 AI 生成" disclaimer="仅供参考，不能替代专业医疗、心理或法律意见" />
    </div>

    <!-- 额度用尽抽屉（1202 触发） -->
    <QuotaDrawer v-model="quotaDrawer" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createQaSession, cancelQaSession, getChildren } from '@/api/client'
import { startQaStream } from '@/api/stream'
import { newRequestId } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { useKeyboardOffset } from '@/composables/useKeyboardOffset'
import QuotaDrawer from '@/components/QuotaDrawer.vue'
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

/** 问答对象档案 uid */
const profileUid = ref<string | null>(user.currentProfileUid)
/** 问题输入 */
const question = ref('')
/** 当前会话 uid */
const sessionUid = ref('')
/** 取消令牌（started 下发） */
const cancelToken = ref('')

/** 已渲染分节状态 */
interface SectionState {
  key: string
  title: string
  pinned: boolean
  immutable: boolean
  /** 流式增量 HTML（已 escape） */
  deltaHtml: string
  /** 是否流式渲染中 */
  streaming: boolean
  /** 完成后的 blocks */
  blocks: any[]
  /** 是否缓存回放整节创建（done 帧兜底，无 delta 流式过程） */
  cached?: boolean
}
/** 分节集合（有序） */
const sections = ref<SectionState[]>([])

/** SSE 已 started（进入骨架态） */
const streamStarted = ref(false)
/** 是否整体完成 */
const completed = ref(false)
/** 降级失败分节名 */
const failedSections = ref<string[]>([])
const degraded = ref(false)

/** 是否生成中 */
const streaming = ref(false)
/** 幂等键：失败重试复用（per action 存 sessionStorage） */
const requestIdKey = 'jiaban_qa_request_id_parenting'

/** 最近一次提问内容（用户气泡展示） */
const lastQuestion = ref('')
/** 提问时间戳（HH:mm） */
const askedAt = ref('')
/** 复制成功态（2s 复位） */
const copied = ref(false)
/** 孩子档案列表（对象 pill 选择用） */
const children = ref<any[]>([])

/** 当前对象显示名 */
const profileName = computed(() => {
  const hit = children.value.find((c) => c.uid === profileUid.value)
  return hit ? hit.nickname : ''
})

/** 是否可复制（存在已完成内容） */
const canCopy = computed(() => sections.value.some((s) => !s.streaming && s.blocks.length))

/**
 * 判断分节是否为「适用前提」类（渲染绿底条块）
 * @param sec 分节状态
 * @returns 是否前提类分节
 */
function isPremiseSec(sec: SectionState): boolean {
  return (sec.title || '').includes('前提')
}

/**
 * 选中对象（记录到本地，下次提问携带）
 * @param uid 档案 uid
 */
function pickProfile(uid: string): void {
  profileUid.value = uid
  user.setCurrentProfile(uid)
}

/**
 * 页头更多按钮（预留扩展，轻提示）
 */
function onMore(): void {
  ElMessage.info('会话设置开发中')
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
 * 加载孩子档案列表（对象 pill 数据源）→ 校验当前对象 → 消费首页 ?q= 接棒
 */
onMounted(async () => {
  // 挂载即拉真实额度：避免额度 chip 使用 store 默认值（0/5），与首页真实口径（0/4）不一致
  user.refreshQuota()
  try {
    const c: any = await getChildren()
    // 后端契约：data.children；非数组（null/对象）防御为空数组，避免 find 报错
    children.value = c?.children || c?.items || (Array.isArray(c) ? c : [])
  } catch {
    children.value = []
  }
  // 本地缓存的问答对象可能已被删除：失效即清除，回落通用口径
  if (profileUid.value && !children.value.some((c: any) => c.uid === profileUid.value)) {
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
 * 重置会话渲染状态
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
 * 发起提问：创建会话 → 消费 SSE 流
 * 失败重试复用同一 client_request_id（幂等）
 * @param text 显式提问文本（首页 ?q= 接棒）；缺省取输入框
 * @throws 网络错误时消息提示，保留 id 供重试
 */
async function ask(text?: string): Promise<void> {
  const q = (text ?? question.value).trim()
  if (!q || streaming.value) return

  // 复用幂等 id：同一次动作（含重试）共用
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
      entry: 'child',
      question: q,
      profile_uid: profileUid.value || undefined,
      client_request_id: requestId
    })
    sessionUid.value = res.session_uid

    // 消费流；blocked 清空正文并跳拦截页
    await startQaStream(res.session_uid, {
      onStarted: (d) => {
        streamStarted.value = true
        cancelToken.value = d.cancel_token
      },
      onSectionDelta: (d) => {
        let sec = sections.value.find((s) => s.key === d.section_key)
        if (!sec) {
          sec = {
            key: d.section_key,
            title: d.title || '生成中…',
            pinned: false,
            immutable: false,
            deltaHtml: '',
            streaming: true,
            blocks: []
          }
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
        // 关键：拦截时清空全部已渲染正文
        sections.value = []
        streaming.value = false
        sessionStorage.removeItem(requestIdKey)
        router.push({
          path: '/app/risk-blocked',
          query: { session: sessionUid.value, data: encodeURIComponent(JSON.stringify(d || {})) }
        })
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
    // 流正常结束但未收到 completed 视为完成
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
    ElMessage.warning('停止请求失败，生成可能继续')
  } finally {
    streaming.value = false
  }
}

onBeforeUnmount(() => {
  // 离开页面时若在生成中，尝试取消
  if (streaming.value && sessionUid.value && cancelToken.value) {
    cancelQaSession(sessionUid.value, cancelToken.value).catch(() => undefined)
  }
})
</script>

<style lang="scss" scoped>
/* ===== 页面骨架：浅灰底 + 顶部白卡 ===== */
.qa-page {
  min-height: 100vh;
  background: var(--bg);
  padding-bottom: 132px;
}

/* 顶部白卡：页头 + 对象行 + 提示条 */
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

/* 对象 pill 行 */
.obj-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
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
  font-size: var(--fs-sub);
  cursor: pointer;

  strong {
    color: var(--ink-1);
    font-weight: 600;
  }

  svg {
    width: 14px;
    height: 14px;
    color: var(--ink-3);
  }
}

.obj-hint {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* 提示 + 额度刻度：同组靠右，避免 space-between 拉开中间元素 */
.obj-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-3);
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

/* 未选档案提示条：黄底 */
.profile-tip {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  color: var(--warn);
  font-size: var(--fs-caption);

  svg { width: 15px; height: 15px; flex: none; }

  p {
    flex: 1;
    color: var(--warn);
  }

  .tip-link {
    border: none;
    background: none;
    color: var(--warn);
    font-weight: 600;
    font-size: var(--fs-caption);
    text-decoration: underline;
    cursor: pointer;
  }
}

/* ===== 会话流 ===== */
.stream-area {
  padding: var(--sp-4) var(--sp-6) 0;
}

/* 用户气泡：右对齐深绿 */
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

.bubble-time {
  margin-top: 4px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* 内容安全检查行 */
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

/* 旋转检查圈 */
.sc-spin {
  width: 14px;
  height: 14px;
  border: 2px solid var(--line-strong);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: qa-spin 0.9s linear infinite;
}

@keyframes qa-spin {
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

/* 分节刻度方点标题 */
.sec-dot-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: var(--sp-2);
  font-size: var(--fs-sub);
  font-weight: 700;
  color: var(--ink-1);

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
    flex: none;
  }

  .sec-pin {
    width: 15px;
    height: 15px;
    color: var(--accent);
    flex: none;
  }
}

/* 流式增量文本 */
.delta-text {
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);
  word-break: break-word;
}

/* 常规要点：刻度方点条目（正文内次要要点，中性灰） */
.block-point {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);

  .pt-dot {
    flex: none;
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--ink-3);
    margin-top: 9px;
  }

  span {
    font-size: var(--fs-sub);
    line-height: 1.7;
    color: var(--ink-2);

    strong { color: var(--ink-1); font-weight: 600; }
  }
}

/* 适用前提：绿底块 */
.block-premise {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  font-size: var(--fs-sub);
  line-height: 1.7;
  margin-bottom: var(--sp-2);
}

/* 不建议做法：警示块 */
.block-warn {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--danger-soft);
  border: 1px solid var(--line-strong);
  margin-bottom: var(--sp-2);

  .bw-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 700;
    color: var(--danger);
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

/* 发送：深绿方按钮 */
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

/* 问答记录：问题作为观察条目，回答按档案分节阅读。 */
.top-sheet {
  padding: 10px 20px 14px;
  border-radius: 0 0 8px 8px;
  box-shadow: none;
  border-bottom: 1px solid var(--line);
}

.qa-head .head-title {
  text-align: left;
  font-size: var(--fs-body);
}

.obj-row {
  align-items: flex-start;
  margin-top: 10px;
}

.obj-pill {
  border-radius: 8px;
  background: var(--surface-2);
}

.obj-meta {
  justify-content: flex-end;
  flex-wrap: wrap;
  row-gap: 2px;
}

.quota-chip {
  color: var(--ink-2);
  font-size: var(--fs-caption);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.profile-tip {
  border-radius: 8px;
}

.stream-area {
  padding: 12px 20px 0;
}

.bubble-row {
  align-items: flex-start;
  margin: 4px 0 18px;
}

.user-bubble {
  max-width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 8px 8px 8px 2px;
  background: var(--surface-2);
  color: var(--ink-1);
}

.ai-card {
  padding: 18px 16px;
  border-radius: 8px;
  box-shadow: none;
}

.ai-head {
  padding-bottom: 12px;
}

.ai-head .ai-badge-ico {
  border-radius: 6px;
}

.ai-sec {
  padding-top: 18px;
}

.ai-sec--pinned {
  margin-top: 12px;
  padding: 14px;
  border-radius: 8px;
}

.input-dock {
  padding-inline: 16px;
  border-top-color: var(--line-strong);
}

.input-dock :deep(.disclaimer-text > span) {
  color: var(--ink-2);
}

.voice-btn,
.send-btn {
  border-radius: 8px;
}

.stream-area :deep(.empty) {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr);
  align-items: start;
  padding: 26px 4px 32px;
  text-align: left;
}

.stream-area :deep(.empty-art) {
  grid-column: 1;
  grid-row: 1 / span 4;
  width: 52px;
  height: 64px;
  margin: 0 10px 0 0;
}

.stream-area :deep(.empty-text),
.stream-area :deep(.empty-sub),
.stream-area :deep(.empty-hint),
.stream-area :deep(.empty-action) {
  grid-column: 2;
  max-width: none;
  text-align: left;
}

.stream-area :deep(.empty-text) {
  align-self: end;
  font-size: var(--fs-title);
}

.stream-area :deep(.empty-sub) {
  margin-top: 4px;
}

.stream-area :deep(.empty-hint) {
  padding: 10px 0 0;
  margin-top: 10px;
  border: 0;
  border-top: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
}

@media (max-width: 360px) {
  .top-sheet {
    padding-inline: 14px;
  }

  .stream-area {
    padding-inline: 14px;
  }

  .obj-hint {
    display: none;
  }
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

.qa-head .head-title {
  text-align: left;
  font-size: var(--fs-body);
}

.obj-row { align-items: flex-start; margin-top: 10px; }
.obj-pill { border-radius: 6px; background: var(--surface-2); }
.obj-meta { justify-content: flex-end; flex-wrap: wrap; row-gap: 2px; }
.quota-chip { color: var(--ink-2); font-size: var(--fs-caption); white-space: nowrap; font-variant-numeric: tabular-nums; }
.profile-tip { border-radius: 6px; }

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
.ai-head .ai-badge-ico { border-radius: 6px; color: var(--perspective-child); background: var(--perspective-child-soft); }
.ai-sec { padding: 18px 0; border-bottom: 1px solid var(--line); }
.ai-sec--pinned { margin-top: 12px; padding: 14px; border: 0; border-radius: 4px 12px 12px 12px; background: var(--accent-soft); }
.sec-dot-head { color: var(--perspective-child); }
.ai-sec--pinned .sec-dot-head { color: var(--accent); }

.input-dock { padding-inline: 16px; border-top-color: var(--line-strong); }
.input-dock :deep(.disclaimer-text > span) { color: var(--ink-2); }
.voice-btn,
.send-btn { border-radius: 8px; }

@media (max-width: 360px) {
  .top-sheet { padding-inline: 14px; }
  .stream-area { padding-inline: 14px; }
  .obj-hint { display: none; }
}
</style>

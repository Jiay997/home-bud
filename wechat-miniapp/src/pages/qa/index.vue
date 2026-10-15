<script setup lang="ts">
import { computed, getCurrentInstance, nextTick, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ApiError } from '../../platform/request'
import { api, BASE_URL, TOKEN_KEY } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import MiniActionSheet from '../../components/MiniActionSheet.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import ReportSheet from '../../components/ReportSheet.vue'
import FeedbackSheet from '../../components/FeedbackSheet.vue'
import { useActionSheet, useDialog } from '../../services/dialog'
import { ensureBaseConsent } from '../../services/session'
import { pollQaSession } from '../../services/qa-poll'
import { createQaTargetStore, type QaTarget } from '../../services/qa-target'
import {
  createQaStreamService,
  createQaStreamState,
  canRenderStreamContent,
  type ChunkedRequest,
  type QaBlockedInfo,
  type QaStreamFinish,
  type QaStreamSection,
  type QaStreamState
} from '../../services/qa-stream'
import { layoutLongImage, renderLongImage, type LongImageDoc, type LongImageLayout } from '../../services/image-export'
import { decodeRouteValue } from '../../services/route'
import {
  isSafetyDegrade,
  qaConflictLabel,
  qaDegradedLabel,
  qaEntryInputPlaceholder,
  qaEntryLabel,
  qaEntryTitle,
  qaSectionTitle
} from '../../services/qa-copy'
import { userFacingMessage } from '../../services/user-message'

type Entry = 'child' | 'pet' | 'family'

interface ChatItem {
  id: number
  role: 'user' | 'answer'
  text: string
  status: 'sending' | 'sent' | 'failed'
  clientRequestId: string
  sessionUid: string
  entry: Entry
  state: QaStreamState
  historyMode: boolean
  readonly: boolean
  contentUpdated: boolean
  regenerating: boolean
  streamError: string
  createdAt: string
}

interface ChannelCard {
  channel_code?: string
  channel_name?: string
  phone_number?: string
  script?: string
}

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const aiBadge = '内容由 AI 生成 · 仅供参考'
const emptyTitle = '把具体情况说给我听'
const emptyCopy = '描述越具体，给出的参考越贴合你的情况'
const safetyCheckingCopy = '正在检查内容安全…'
const safetyPassedCopy = '内容安全检查通过'
const safetyStreamingCopy = '内容安全检查通过 · 生成中'
const blockedTitle = '已停止生成回答'
const blockedLead = '为保护你与孩子，本页不展示你的原文，也不提供任何诊断或建议文本。'
const blockedReasonCopy = '拦截原因：命中高危类别，本次不生成内容、不计提问次数。'
const blockedLineCopy = '本次提问已停止生成回答'
const blockedReopen = '查看安全信息'
const channelFallbackNote = '号码待补充，请以官方渠道为准'
const channelFallback: ChannelCard = { channel_name: '紧急报警', phone_number: '110', script: '紧急情况请说明地点与情况' }
const safetyStaticTitle = '安全提示未能生成'
const safetyStaticCopy = '为谨慎起见，本页暂不展示本次生成的其他内容。情况紧急请立即联系线下专业机构。'
const gatedHint = '开通会员后可查看完整内容'
const gatedTitleFallback = '深度内容'
const readonlyCopy = '会员已到期 · 只读'
const updatedCopy = '内容已更新'
const disclaimerLine = '内容由人工智能生成，仅供参考，不替代医疗或专业诊断'
const noContentCopy = '本次没有生成可展示的内容'
const memberOnlyTip = '会员专属功能，开通后可重新生成'
const regeneratedCopy = '已重新生成'
const savedCopy = '已保存到相册'
const copiedCopy = '已复制'
const voiceTip = '语音输入暂未开放，请使用文字输入'
const sendFailedCopy = '发送失败，请检查网络后重试。'
const streamFailedCopy = '生成中断，请稍后重试'
const timeoutCopy = '生成超时，请稍后重试'
const regenerateFallback = '重新生成失败，请稍后重试。'
const imageFallback = '图片生成失败，请稍后重试。'

const instance = getCurrentInstance()
const targetStore = createQaTargetStore({
  storage: {
    getStorageSync: (key: string) => uni.getStorageSync(key),
    setStorageSync: (key: string, value: unknown) => uni.setStorageSync(key, value)
  }
})

const entry = ref<Entry>('child')
const historyMode = ref(false)
const historyUid = ref('')
const historyLoading = ref(false)
const historyError = ref('')
const chat = ref<ChatItem[]>([])
const draft = ref('')
const inputFocus = ref(false)
const scrollAnchor = ref('')
const quota = ref<{ remaining: number | null; limit: number | null; unlimited: boolean } | null>(null)
const me = ref<{ user_uid: string; member_status: string } | null>(null)
const children = ref<any[]>([])
const pets = ref<any[]>([])
const target = ref<QaTarget | null>(null)
const sending = ref(false)
const reportVisible = ref(false)
const reportObjectId = ref('')
const feedbackVisible = ref(false)
const blockedOverlay = ref<QaBlockedInfo | null>(null)
const savingImage = ref(false)
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()
const { actionSheet, openActionSheet, onActionSheetSelect, onActionSheetClose } = useActionSheet()
let idSeed = 0

function nextId() {
  idSeed += 1
  return idSeed
}

function makeClientRequestId() {
  return `mp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function normalizeEntry(value: unknown): Entry {
  const raw = String(value || '').trim()
  return raw === 'pet' || raw === 'family' ? raw : 'child'
}

const isMember = computed(() => me.value?.member_status === 'member')
const headerTitle = computed(() => qaEntryTitle(entry.value))
const inputPlaceholder = computed(() => qaEntryInputPlaceholder(entry.value))
const quotaText = computed(() => {
  const view = quota.value
  if (!view || view.unlimited || view.limit === null || view.remaining === null) return ''
  return `今日剩余 ${view.remaining}/${view.limit} 次`
})
const profileNotice = computed(() => {
  if (historyMode.value) return ''
  if (entry.value === 'child' && !children.value.length) return '未选择档案：将按通用 1-3 岁回答'
  if (entry.value === 'pet' && !pets.value.length) return '暂无宠物档案：将按通用饲喂区间回答'
  return ''
})
const busyStreaming = computed(() => chat.value.some((item) =>
  item.role === 'answer' && !item.historyMode && ['waiting', 'checking', 'streaming'].includes(item.state.phase)
))
const canSend = computed(() => !!draft.value.trim() && !sending.value && !busyStreaming.value)
const targetLabel = computed(() => {
  if (target.value?.name) return target.value.name
  const list = entry.value === 'pet' ? pets.value : children.value
  return list.length ? '选择对象' : '未绑定档案'
})
const familyLabel = computed(() => {
  const names: string[] = []
  if (children.value[0]) names.push(String(children.value[0].nickname || '宝宝'))
  if (pets.value[0]) names.push(petLabel(pets.value[0]))
  return names.length ? names.join(' + ') : '孩子与宠物'
})
const overlayChannels = computed<ChannelCard[]>(() => {
  const channels = (blockedOverlay.value?.channels || []) as ChannelCard[]
  return channels.length ? channels : [channelFallback]
})

function petLabel(pet: any) {
  if (pet?.breed) return String(pet.breed)
  return pet?.pet_type === 'cat' ? '猫咪' : '狗狗'
}

// ------------------------------------------------------------------
// 启动
// ------------------------------------------------------------------
onLoad((query) => {
  entry.value = normalizeEntry(query?.entry)
  historyMode.value = String(query?.history || '') === '1'
  historyUid.value = decodeRouteValue(query?.uid)
  const question = decodeRouteValue(query?.q).trim()
  if (historyMode.value && historyUid.value) {
    void bootHistory(historyUid.value)
    return
  }
  if (historyUid.value && question) {
    void bootExisting(historyUid.value, question)
    return
  }
  void bootNew(question)
})

async function ensureBaseConsentSafe() {
  try {
    if (await ensureBaseConsent()) return true
    uni.reLaunch({ url: '/pages/index/index' })
    return false
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '连接失败，请检查网络后重试。'), icon: 'none' })
    return false
  }
}

async function bootNew(question: string) {
  if (!(await ensureBaseConsentSafe())) return
  if (question) {
    await loadBootstrap()
    void submitQuestion(question)
  } else {
    inputFocus.value = true
    void loadBootstrap()
  }
}

async function bootExisting(sessionUid: string, question: string) {
  if (!(await ensureBaseConsentSafe())) return
  void loadBootstrap()
  const userItem = makeUserItem(question)
  userItem.status = 'sent'
  const answerItem = makeAnswerItem(sessionUid)
  chat.value = [...chat.value, userItem, answerItem]
  void pinToBottom()
  startStream(chat.value[chat.value.length - 1])
}

async function bootHistory(sessionUid: string) {
  if (!(await ensureBaseConsentSafe())) return
  historyLoading.value = true
  historyError.value = ''
  void loadBootstrap()
  try {
    const detail = await api.historyQa(sessionUid)
    entry.value = normalizeEntry(detail?.profile_type || detail?.entry)
    const userItem = makeUserItem(String(detail?.question || ''))
    userItem.status = 'sent'
    const answerItem = makeAnswerItem(sessionUid)
    answerItem.historyMode = true
    answerItem.readonly = detail?.readonly === true
    answerItem.contentUpdated = detail?.content_updated === true
    answerItem.createdAt = String(detail?.created_at || '')
    answerItem.state = mapHistoryPayload(detail)
    chat.value = [userItem, answerItem]
    void pinToBottom()
  } catch (error: any) {
    historyError.value = userFacingMessage(error, '记录读取失败，请稍后重试。')
  } finally {
    historyLoading.value = false
  }
}

function retryHistory() {
  if (historyUid.value) void bootHistory(historyUid.value)
}

async function loadBootstrap() {
  try {
    const [meView, quotaView] = await Promise.all([api.me(), api.quota()])
    me.value = { user_uid: meView.user_uid, member_status: meView.member_status }
    quota.value = {
      remaining: quotaView.remaining ?? null,
      limit: quotaView.limit ?? null,
      unlimited: quotaView.unlimited === true
    }
  } catch {
    // 基础信息失败不阻断提问（会员判定回退为非会员，门控仍由服务端裁剪）
  }
  if (entry.value === 'child' || entry.value === 'family') {
    try {
      children.value = (await api.children()).children || []
    } catch {
      children.value = []
    }
  }
  if (entry.value === 'pet' || entry.value === 'family') {
    try {
      pets.value = (await api.pets()).pets || []
    } catch {
      pets.value = []
    }
  }
  initTarget()
}

async function refreshQuota() {
  try {
    const view = await api.quota()
    quota.value = {
      remaining: view.remaining ?? null,
      limit: view.limit ?? null,
      unlimited: view.unlimited === true
    }
  } catch {
    // 额度刷新失败静默
  }
}

function initTarget() {
  if (entry.value === 'family') {
    target.value = null
    return
  }
  const list = entry.value === 'pet' ? pets.value : children.value
  if (!list.length) {
    target.value = null
    if (me.value?.user_uid) targetStore.clear(entry.value, me.value.user_uid)
    return
  }
  const saved = me.value?.user_uid ? targetStore.read(entry.value, me.value.user_uid) : null
  const matched = saved
    ? list.find((item: any) => (entry.value === 'pet' ? item.pet_uid : item.profile_uid) === saved.profile_uid)
    : null
  if (matched && saved) {
    target.value = saved
    return
  }
  const first = list[0]
  const next: QaTarget = {
    profile_uid: entry.value === 'pet' ? first.pet_uid : first.profile_uid,
    name: entry.value === 'pet' ? petLabel(first) : String(first.nickname || '宝宝')
  }
  target.value = next
  if (me.value?.user_uid) targetStore.write(entry.value, me.value.user_uid, next)
}

async function switchTarget() {
  const list = entry.value === 'pet' ? pets.value : children.value
  if (!list.length) {
    goProfiles()
    return
  }
  const names = list.slice(0, 6).map((item: any) =>
    entry.value === 'pet' ? petLabel(item) : String(item.nickname || '宝宝')
  )
  const picked = await openActionSheet(names)
  const chosen = picked === null ? null : list[picked]
  if (!chosen) return
  const next: QaTarget = {
    profile_uid: entry.value === 'pet' ? chosen.pet_uid : chosen.profile_uid,
    name: entry.value === 'pet' ? petLabel(chosen) : String(chosen.nickname || '宝宝')
  }
  target.value = next
  if (me.value?.user_uid) targetStore.write(entry.value, me.value.user_uid, next)
}

function goProfiles() {
  uni.redirectTo({ url: '/pages/profiles/index' })
}

function goMember() {
  uni.navigateTo({ url: '/pages/member/index' })
}

// ------------------------------------------------------------------
// 发送与会话流
// ------------------------------------------------------------------
function makeUserItem(text: string): ChatItem {
  return {
    id: nextId(),
    role: 'user',
    text,
    status: 'sending',
    clientRequestId: makeClientRequestId(),
    sessionUid: '',
    entry: entry.value,
    state: createQaStreamState(),
    historyMode: false,
    readonly: false,
    contentUpdated: false,
    regenerating: false,
    streamError: '',
    createdAt: ''
  }
}

function makeAnswerItem(sessionUid: string): ChatItem {
  return {
    id: nextId(),
    role: 'answer',
    text: '',
    status: 'sent',
    clientRequestId: '',
    sessionUid,
    entry: entry.value,
    state: createQaStreamState(),
    historyMode: false,
    readonly: false,
    contentUpdated: false,
    regenerating: false,
    streamError: '',
    createdAt: ''
  }
}

function send() {
  const text = draft.value.trim()
  if (!text || !canSend.value) return
  draft.value = ''
  inputFocus.value = false
  void submitQuestion(text)
}

async function submitQuestion(text: string, resendOf?: ChatItem) {
  let userItem: ChatItem
  if (resendOf) {
    const live = chat.value.find((item) => item.id === resendOf.id)
    if (!live) return
    userItem = live
    userItem.status = 'sending'
  } else {
    const raw = makeUserItem(text)
    chat.value = [...chat.value, raw]
    userItem = chat.value[chat.value.length - 1]
  }
  void pinToBottom()
  sending.value = true
  try {
    const body: { entry: Entry; question: string; client_request_id: string; profile_uid?: string } = {
      entry: entry.value,
      question: userItem.text,
      client_request_id: userItem.clientRequestId
    }
    if (entry.value !== 'family' && target.value?.profile_uid) body.profile_uid = target.value.profile_uid
    const created = await api.createQaSession(body)
    userItem.status = 'sent'
    const answerRaw = makeAnswerItem(created.session_uid)
    chat.value = [...chat.value, answerRaw]
    void pinToBottom()
    startStream(chat.value[chat.value.length - 1])
  } catch (error: any) {
    userItem.status = 'failed'
    uni.showToast({ title: userFacingMessage(error, sendFailedCopy), icon: 'none' })
  } finally {
    sending.value = false
  }
}

function retrySend(item: ChatItem) {
  if (item.status !== 'failed' || sending.value) return
  void submitQuestion(item.text, item)
}

function startStream(item: ChatItem) {
  item.streamError = ''
  if (!chunkedSupported()) {
    void fallbackPoll(item, true)
    return
  }
  const service = createQaStreamService({
    request: wxChunkedRequest,
    storage: { getStorageSync: (key: string) => uni.getStorageSync(key) },
    baseUrl: BASE_URL,
    tokenKey: TOKEN_KEY
  })
  service.start(item.sessionUid, {
    onUpdate(state: QaStreamState) {
      item.state = state
      if (state.quota && state.quota.limit !== null) {
        quota.value = {
          remaining: Math.max(0, state.quota.limit - state.quota.used),
          limit: state.quota.limit,
          unlimited: false
        }
      }
      if (state.phase === 'blocked') blockedOverlay.value = state.blocked
    },
    onFinish(result: QaStreamFinish) {
      void handleStreamFinish(item, result)
    }
  })
}

async function handleStreamFinish(item: ChatItem, result: QaStreamFinish) {
  const phase = item.state.phase
  if (phase === 'done' || phase === 'blocked' || phase === 'failed') {
    if (phase === 'done') void refreshQuota()
    return
  }
  if (!result.hadFrames) {
    if (result.message) {
      item.streamError = result.message
      return
    }
    await fallbackPoll(item, true)
    return
  }
  // 已有帧但连接中断：后端仍在生成，直接轮询兜底
  await fallbackPoll(item, false)
}

async function fallbackPoll(item: ChatItem, trigger: boolean) {
  try {
    const getTriggerError = trigger ? api.triggerQaGeneration(item.sessionUid) : () => null
    const payload = await pollQaSession<any>({
      getSession: () => api.getQaSession(item.sessionUid),
      getTriggerError
    })
    const mapped = mapSessionPayload(payload)
    item.state = mapped
    if (mapped.phase === 'blocked') {
      blockedOverlay.value = mapped.blocked
      return
    }
    if (mapped.phase === 'failed') {
      item.streamError = mapped.errorMessage || streamFailedCopy
      return
    }
    if (mapped.phase !== 'done') {
      item.streamError = timeoutCopy
      return
    }
    void refreshQuota()
  } catch (error: any) {
    item.streamError = userFacingMessage(error, sendFailedCopy)
  }
}

function mapSessionPayload(payload: any): QaStreamState {
  const rawSections = Array.isArray(payload?.sections) ? payload.sections : []
  const sections: QaStreamSection[] = rawSections.map((section: any) => ({
    section_key: String(section?.section_key || ''),
    title: String(section?.title || ''),
    blocks: Array.isArray(section?.blocks) ? section.blocks : [],
    done: true,
    pinned: section?.pinned === true,
    immutable: section?.immutable === true
  }))
  const status = String(payload?.status || '')
  const blocked = status === 'blocked'
  const failed = status === 'failed'
  return {
    ...createQaStreamState(),
    sessionUid: String(payload?.session_uid || ''),
    renderOrder: Array.isArray(payload?.render_order) ? payload.render_order : [],
    riskLevel: String(payload?.risk_level || ''),
    degradedReason: typeof payload?.degraded_reason === 'string' ? payload.degraded_reason : null,
    sections,
    phase: blocked ? 'blocked' : failed ? 'failed' : status === 'done' || status === 'degraded' ? 'done' : 'failed',
    blocked: blocked ? { reason: blockedLineCopy, channels: [], appealAllowed: false } : null,
    errorMessage: failed ? streamFailedCopy : !blocked && sections.length === 0 ? timeoutCopy : ''
  }
}

function mapHistoryPayload(detail: any): QaStreamState {
  const rawSections = Array.isArray(detail?.sections) ? detail.sections : []
  const sections: QaStreamSection[] = rawSections.map((section: any) => ({
    section_key: String(section?.section_key || ''),
    title: String(section?.title || ''),
    blocks: Array.isArray(section?.blocks) ? section.blocks : [],
    done: true,
    pinned: section?.pinned === true,
    immutable: section?.immutable === true,
    access_tier: section?.access_tier === 'block' ? 'block' : 'free'
  }))
  return {
    ...createQaStreamState(),
    sessionUid: String(detail?.session_uid || ''),
    riskLevel: String(detail?.risk_level || ''),
    degradedReason: typeof detail?.degraded_reason === 'string' ? detail.degraded_reason : null,
    sections,
    phase: 'done'
  }
}

function retryAnswer(item: ChatItem) {
  item.state = createQaStreamState()
  item.streamError = ''
  startStream(item)
}

function regenerate(item: ChatItem) {
  if (!isMember.value) {
    uni.showToast({ title: memberOnlyTip, icon: 'none' })
    return
  }
  if (item.regenerating) return
  item.regenerating = true
  void (async () => {
    try {
      await api.regenerateQaSession(item.sessionUid, { client_request_id: makeClientRequestId() })
      const detail = await api.historyQa(item.sessionUid)
      item.state = mapHistoryPayload(detail)
      item.readonly = detail?.readonly === true
      item.contentUpdated = detail?.content_updated === true
      uni.showToast({ title: regeneratedCopy, icon: 'none' })
    } catch (error: any) {
      if (error instanceof ApiError && error.code === 1401) {
        item.state = {
          ...item.state,
          phase: 'blocked',
          sections: [],
          blocked: { reason: blockedLineCopy, channels: [], appealAllowed: true }
        }
        blockedOverlay.value = item.state.blocked
      } else {
        uni.showToast({ title: userFacingMessage(error, regenerateFallback), icon: 'none' })
      }
    } finally {
      item.regenerating = false
    }
  })()
}

// ------------------------------------------------------------------
// 流式传输适配（微信端分块；不支持时降级轮询）
// ------------------------------------------------------------------
const wxChunkedRequest: ChunkedRequest = (options) => {
  const wxApi = (globalThis as { wx?: any }).wx
  if (!wxApi || typeof wxApi.request !== 'function') {
    options.handlers.onFail('当前环境不支持流式传输')
    return { abort: () => undefined }
  }
  const task = wxApi.request({
    url: options.url,
    method: options.method,
    header: options.header,
    timeout: options.timeout,
    enableChunked: true,
    responseType: 'arraybuffer',
    success: (response: any) => {
      options.handlers.onComplete({ statusCode: Number(response?.statusCode || 0), body: '' })
    },
    fail: (error: any) => {
      options.handlers.onFail(error?.errMsg || '网络连接失败')
    }
  })
  if (task && typeof task.onChunkReceived === 'function') {
    task.onChunkReceived((response: any) => {
      options.handlers.onChunk(response.data)
    })
  }
  return { abort: () => task?.abort?.() }
}

function chunkedSupported() {
  try {
    const wxApi = (globalThis as { wx?: any }).wx
    if (!wxApi || typeof wxApi.request !== 'function') return false
    const info = typeof wxApi.getAppBaseInfo === 'function' ? wxApi.getAppBaseInfo() : wxApi.getSystemInfoSync?.()
    const version = String(info?.SDKVersion || '')
    return compareVersion(version, '2.20.2') >= 0
  } catch {
    return false
  }
}

function compareVersion(left: string, right: string) {
  const leftParts = left.split('.').map((part) => parseInt(part, 10) || 0)
  const rightParts = right.split('.').map((part) => parseInt(part, 10) || 0)
  const length = Math.max(leftParts.length, rightParts.length)
  for (let index = 0; index < length; index += 1) {
    const a = leftParts[index] || 0
    const b = rightParts[index] || 0
    if (a !== b) return a > b ? 1 : -1
  }
  return 0
}

// ------------------------------------------------------------------
// 渲染与操作
// ------------------------------------------------------------------
async function pinToBottom() {
  scrollAnchor.value = ''
  await nextTick()
  scrollAnchor.value = 'qa-bottom'
}

function sectionRenderable(section: QaStreamSection) {
  return section.done || canRenderStreamContent(section.section_key, isMember.value)
}

function safetyLineText(item: ChatItem) {
  if (item.state.phase === 'checking' || item.state.phase === 'waiting') return safetyCheckingCopy
  if (item.state.phase === 'streaming') return safetyStreamingCopy
  return safetyPassedCopy
}

function isSafetyFailed(item: ChatItem) {
  return !item.historyMode && isSafetyDegrade(item.state.degradedReason)
}

function showDegradedBar(item: ChatItem) {
  return !!item.state.degradedReason && !isSafetyFailed(item)
}

function hasRenderableContent(item: ChatItem) {
  return item.state.sections.some((section) =>
    section.access_tier !== 'block' &&
    section.blocks.some((block) => block.access_tier !== 'block' && String(block.content || '').trim().length > 0)
  )
}

function cardActionsVisible(item: ChatItem) {
  return item.state.phase === 'done'
}

function answerText(item: ChatItem) {
  const lines: string[] = []
  for (const section of item.state.sections) {
    if (section.access_tier === 'block') continue
    const sectionLines: string[] = []
    for (const block of section.blocks) {
      if (block.access_tier === 'block') continue
      if (block.title) sectionLines.push(String(block.title))
      if (block.content) sectionLines.push(String(block.content))
    }
    if (!sectionLines.length) continue
    lines.push(qaSectionTitle(section))
    lines.push(...sectionLines)
    lines.push('')
  }
  if (!lines.length) return ''
  lines.push(disclaimerLine)
  return lines.join('\n').trim()
}

function copyPlain(text: string) {
  if (!text) return
  uni.setClipboardData({
    data: text,
    success: () => uni.showToast({ title: copiedCopy, icon: 'none' })
  })
}

function copyAnswer(item: ChatItem) {
  copyPlain(answerText(item))
}

function openReport(item: ChatItem) {
  if (!item.sessionUid) return
  reportObjectId.value = item.sessionUid
  reportVisible.value = true
}

function openBlocked(item: ChatItem) {
  if (!item.state.blocked) return
  blockedOverlay.value = item.state.blocked
}

function callChannel(channel: ChannelCard) {
  if (!channel.phone_number) {
    uni.showToast({ title: channelFallbackNote, icon: 'none' })
    return
  }
  uni.makePhoneCall({ phoneNumber: channel.phone_number, fail: () => undefined })
}

function voiceUnavailable() {
  uni.showToast({ title: voiceTip, icon: 'none' })
}

// ------------------------------------------------------------------
// 保存长图（canvas 2d 简化版）
// ------------------------------------------------------------------
function questionOf(item: ChatItem) {
  const index = chat.value.findIndex((entryItem) => entryItem.id === item.id)
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const prev = chat.value[cursor]
    if (prev.role === 'user') return prev.text
  }
  return ''
}

function formatDate(value?: string) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月 ${date.getDate()} 日`
}

function buildAnswerDoc(item: ChatItem): LongImageDoc {
  const sections = item.state.sections.flatMap((section) => {
    if (section.access_tier === 'block') return []
    const body = section.blocks
      .filter((block) => block.access_tier !== 'block')
      .map((block) => [block.title, block.content].filter(Boolean).join('\n'))
      .filter(Boolean)
      .join('\n\n')
    if (!body) return []
    return [{ heading: qaSectionTitle(section), body }]
  })
  return {
    brand: '小光景',
    title: questionOf(item) || qaEntryLabel(item.entry),
    meta: `${qaEntryLabel(item.entry)} · ${formatDate(item.createdAt)}`,
    dimensions: [],
    sections,
    disclaimers: [disclaimerLine],
    badge: '内容由 AI 生成'
  }
}

function getPixelRatio() {
  try {
    return uni.getSystemInfoSync().pixelRatio || 2
  } catch {
    return 2
  }
}

function queryExportCanvas(): Promise<any> {
  return new Promise((resolve, reject) => {
    const query = uni.createSelectorQuery()
    const scoped = instance ? query.in(instance.proxy as any) : query
    scoped.select('#qa-export-canvas').fields({ node: true, size: true } as any, (res: any) => {
      const node = Array.isArray(res) ? res[0]?.node : res?.node
      if (node) resolve(node)
      else reject(new Error('画布初始化失败'))
    }).exec()
  })
}

function canvasToFile(canvas: any, layout: LongImageLayout, dpr: number): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.canvasToTempFilePath({
      canvas,
      x: 0,
      y: 0,
      width: layout.width,
      height: layout.height,
      destWidth: Math.ceil(layout.width * dpr),
      destHeight: Math.ceil(layout.height * dpr),
      fileType: 'png',
      success: (res: any) => resolve(res.tempFilePath),
      fail: () => reject(new Error('图片导出失败'))
    } as any)
  })
}

function saveToAlbum(filePath: string): Promise<'saved' | 'denied'> {
  return new Promise((resolve, reject) => {
    uni.saveImageToPhotosAlbum({
      filePath,
      success: () => resolve('saved'),
      fail: (error: any) => {
        const message = String(error?.errMsg || '')
        if (/auth|deny|authorize/i.test(message)) resolve('denied')
        else reject(new Error('保存失败'))
      }
    } as any)
  })
}

async function promptAlbumSetting() {
  const result = await openDialog({
    title: '需要相册权限',
    message: '请在设置中允许保存图片到相册，然后重试。',
    confirmText: '去设置'
  })
  if (result.confirm) uni.openSetting({})
}

function saveAnswerImage(item: ChatItem) {
  if (savingImage.value) return
  savingImage.value = true
  uni.showLoading({ title: '正在生成图片…', mask: true })
  void (async () => {
    try {
      const doc = buildAnswerDoc(item)
      const canvas = await queryExportCanvas()
      const ctx: any = canvas.getContext('2d')
      const dpr = getPixelRatio()
      const measure = (text: string, font: string) => {
        ctx.font = font
        return ctx.measureText(text).width
      }
      const layout = layoutLongImage(doc, { width: 375, measure })
      canvas.width = Math.ceil(layout.width * dpr)
      canvas.height = Math.ceil(layout.height * dpr)
      if (typeof ctx.scale === 'function') ctx.scale(dpr, dpr)
      renderLongImage(ctx, layout)
      const filePath = await canvasToFile(canvas, layout, dpr)
      const outcome = await saveToAlbum(filePath)
      uni.hideLoading()
      if (outcome === 'saved') uni.showToast({ title: savedCopy, icon: 'none' })
      else promptAlbumSetting()
    } catch (error: any) {
      uni.hideLoading()
      uni.showToast({ title: userFacingMessage(error, imageFallback), icon: 'none' })
    } finally {
      savingImage.value = false
      uni.hideLoading()
    }
  })()
}
</script>

<template>
  <view class="qa-page tex">
    <MiniPageHeader :title="headerTitle" />
    <scroll-view class="qa-scroll" scroll-y :scroll-into-view="scrollAnchor" :scroll-with-animation="true">
      <view class="qa-inner">
        <view v-if="!historyMode" class="top-strip">
          <button v-if="entry !== 'family'" class="target-pill" hover-class="pill-pressed" @tap="switchTarget">
            <view class="target-dot" />
            <text class="target-name">{{ targetLabel }}</text>
            <view class="target-caret" />
          </button>
          <text v-else class="target-static">{{ familyLabel }}</text>
          <text v-if="quotaText" class="quota-line">{{ quotaText }}</text>
        </view>

        <view v-if="profileNotice" class="profile-notice">
          <text class="notice-copy">{{ profileNotice }}</text>
          <button class="notice-action" @tap="goProfiles">补充档案</button>
        </view>

        <view v-if="historyLoading && !chat.length" class="history-loading">
          <StateSkeleton mode="skeleton" />
        </view>

        <view v-if="historyError" class="answer-fail">
          <text class="fail-copy">{{ historyError }}</text>
          <button class="fail-retry" @tap="retryHistory">重试</button>
        </view>

        <StateSkeleton v-if="!chat.length && !historyLoading && !historyError" mode="empty" :title="emptyTitle" :copy="emptyCopy" />

        <view v-for="item in chat" :key="item.id" class="chat-row">
          <template v-if="item.role === 'user'">
            <view class="user-line">
              <view class="user-bubble" @longpress="copyPlain(item.text)">
                <text class="user-text">{{ item.text }}</text>
              </view>
              <view v-if="item.status === 'failed'" class="send-fail">
                <text class="fail-mark">未发送</text>
                <button class="fail-retry" @tap="retrySend(item)">重试</button>
              </view>
            </view>
          </template>

          <template v-else>
            <view v-if="!item.historyMode && item.state.phase !== 'blocked'" class="safety-line">
              <view v-if="item.state.phase === 'checking' || item.state.phase === 'waiting'" class="safety-icon spinning" />
              <view v-else class="safety-check" />
              <text class="safety-copy">{{ safetyLineText(item) }}</text>
            </view>

            <view v-if="item.state.phase === 'blocked'" class="blocked-line">
              <text class="blocked-copy">{{ blockedLineCopy }}</text>
              <button class="blocked-action" @tap="openBlocked(item)">{{ blockedReopen }}</button>
            </view>

            <view v-else-if="item.state.phase === 'failed' || item.streamError" class="answer-fail">
              <text class="fail-copy">{{ item.streamError || item.state.errorMessage || '生成中断，请稍后重试' }}</text>
              <button class="fail-retry" @tap="retryAnswer(item)">重试</button>
            </view>

            <view v-else-if="isSafetyFailed(item)" class="safety-static">
              <view class="safety-static-head">
                <view class="warn-mark" />
                <text class="safety-static-title">{{ safetyStaticTitle }}</text>
              </view>
              <text class="safety-static-copy">{{ safetyStaticCopy }}</text>
              <view class="channel-list">
                <view class="channel-card">
                  <view class="channel-info">
                    <text class="channel-name">{{ channelFallback.channel_name }}</text>
                    <text class="channel-phone">{{ channelFallback.phone_number }}</text>
                  </view>
                  <button class="channel-call" @tap="callChannel(channelFallback)">拨打</button>
                </view>
              </view>
              <button class="retry-button" @tap="retryAnswer(item)">重试</button>
            </view>

            <view v-else class="answer-card">
              <view class="card-head">
                <view class="ai-pill">
                  <view class="ai-dot" />
                  <text class="ai-text">{{ aiBadge }}</text>
                </view>
                <button v-if="hasRenderableContent(item)" class="head-copy" hover-class="pressed" @tap="copyAnswer(item)">复制</button>
              </view>

              <view class="section-list">
                <view v-if="showDegradedBar(item)" class="degraded-wrap">
                  <StateSkeleton mode="degraded" :title="qaDegradedLabel(item.state.degradedReason)" copy="其余内容仍可查看" />
                </view>

                <view v-for="section in item.state.sections" :key="section.section_key" class="answer-section">
                  <view class="section-title-row">
                    <view class="section-dash" />
                    <text class="section-title">{{ qaSectionTitle(section) }}</text>
                  </view>
                  <view v-if="section.access_tier === 'block'" class="gated-section">
                    <text class="gated-hint">{{ gatedHint }}</text>
                    <button class="gated-action" @tap="goMember">解锁会员</button>
                  </view>
                  <template v-else-if="sectionRenderable(section)">
                    <view v-for="(block, blockIndex) in section.blocks" :key="blockIndex" class="answer-block">
                      <view v-if="block.access_tier === 'block'" class="gated-block">
                        <text class="gated-title">{{ block.title || gatedTitleFallback }}</text>
                        <text v-if="block.summary" class="gated-summary">{{ block.summary }}</text>
                        <button class="gated-action" @tap="goMember">解锁会员</button>
                      </view>
                      <template v-else>
                        <text v-if="block.title" class="block-title">{{ block.title }}</text>
                        <text v-if="block.content" class="block-content">{{ block.content }}</text>
                        <StateSkeleton v-else-if="!section.done" mode="skeleton" />
                      </template>
                    </view>
                    <StateSkeleton v-if="!section.blocks.length && !section.done" mode="skeleton" />
                  </template>
                  <StateSkeleton v-else mode="skeleton" />
                </view>

                <view v-if="item.state.conflictNote" class="conflict-note">
                  <text class="conflict-copy">{{ qaConflictLabel(item.state.conflictNote) }}</text>
                </view>

                <view v-if="item.state.phase === 'done' && !hasRenderableContent(item)" class="answer-empty">
                  <text class="fail-copy">{{ noContentCopy }}</text>
                  <button class="fail-retry" @tap="retryAnswer(item)">重试</button>
                </view>

                <view v-if="item.contentUpdated" class="updated-row">
                  <text class="updated-copy">{{ updatedCopy }}</text>
                </view>

                <view v-if="cardActionsVisible(item)" class="card-actions">
                  <button class="action-item" hover-class="pressed" @tap="copyAnswer(item)">复制</button>
                  <button class="action-item" hover-class="pressed" @tap="saveAnswerImage(item)">存图</button>
                  <button class="action-item" hover-class="pressed" @tap="feedbackVisible = true">反馈</button>
                  <button class="action-item" hover-class="pressed" @tap="openReport(item)">举报</button>
                  <button
                    v-if="item.historyMode"
                    class="action-item"
                    :class="{ disabled: !isMember || item.regenerating }"
                    hover-class="pressed"
                    @tap="regenerate(item)"
                  >
                    {{ item.regenerating ? '重新生成中…' : '重新生成' }}
                  </button>
                </view>

                <view v-if="item.readonly" class="readonly-row">
                  <text class="readonly-copy">{{ readonlyCopy }}</text>
                </view>
              </view>
            </view>
          </template>
        </view>

        <view id="qa-bottom" class="bottom-anchor" />
      </view>
    </scroll-view>

    <view class="input-dock">
      <view class="input-bar">
        <button class="mic-button" hover-class="pressed" aria-label="语音输入" @tap="voiceUnavailable">
          <view class="mic-icon" />
        </button>
        <textarea
          v-model="draft"
          class="question-input"
          :placeholder="inputPlaceholder"
          :maxlength="500"
          :auto-height="true"
          :show-confirm-bar="false"
          confirm-type="send"
          :focus="inputFocus"
          @confirm="send"
        />
        <button class="send-button" :class="{ disabled: !canSend }" :disabled="!canSend" hover-class="pressed" @tap="send">发送</button>
      </view>
      <MiniComplianceBar />
    </view>

    <ReportSheet :visible="reportVisible" object-type="qa_answer" :object-id="reportObjectId" @close="reportVisible = false" />
    <FeedbackSheet :visible="feedbackVisible" @close="feedbackVisible = false" />
    <MiniDialog
      :visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :confirm-text="dialog.confirmText"
      :cancel-text="dialog.cancelText"
      :show-cancel="dialog.showCancel"
      :danger="dialog.danger"
      :input="dialog.input"
      @confirm="onDialogConfirm"
      @cancel="onDialogCancel"
    />
    <MiniActionSheet
      :visible="actionSheet.visible"
      :items="actionSheet.items"
      @select="onActionSheetSelect"
      @close="onActionSheetClose"
    />
    <canvas type="2d" id="qa-export-canvas" class="export-canvas" />

    <view v-if="blockedOverlay" class="blocked-overlay">
      <view class="blocked-card">
        <view class="blocked-head">
          <text class="blocked-title">{{ blockedTitle }}</text>
        </view>
        <text class="blocked-lead">{{ blockedLead }}</text>
        <text class="blocked-reason">{{ blockedReasonCopy }}</text>
        <view class="channel-list">
          <view v-for="(channel, channelIndex) in overlayChannels" :key="channelIndex" class="channel-card">
            <view class="channel-info">
              <text class="channel-name">{{ channel.channel_name }}</text>
              <text v-if="channel.phone_number" class="channel-phone">{{ channel.phone_number }}</text>
              <text v-else class="channel-phone">{{ channelFallbackNote }}</text>
              <text v-if="channel.script" class="channel-script">{{ channel.script }}</text>
            </view>
            <template v-if="channel.phone_number">
              <button class="channel-call" @tap="callChannel(channel)">拨打</button>
              <button class="channel-copy" @tap="copyPlain(String(channel.phone_number))">复制号码</button>
            </template>
          </view>
        </view>
        <button class="blocked-confirm" hover-class="pressed" @tap="blockedOverlay = null">我知道了</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.qa-page { display: flex; flex-direction: column; height: 100vh; background-color: var(--bg); }
.qa-scroll { flex: 1; min-height: 0; }
.qa-inner { padding: 20rpx 32rpx 40rpx; }
.bottom-anchor { height: 2rpx; }

.top-strip { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 4rpx 0 10rpx; }
.target-pill { display: flex; align-items: center; gap: 12rpx; margin: 0; padding: 10rpx 26rpx; background: var(--surface); border: var(--border-warm); border-radius: var(--r-control); }
.pill-pressed { background: var(--surface-warm); }
.target-dot { width: 12rpx; height: 12rpx; border-radius: 50%; background: var(--primary); }
.target-name { max-width: 320rpx; overflow: hidden; color: var(--ink-1); font-size: 26rpx; text-overflow: ellipsis; white-space: nowrap; }
.target-caret { width: 12rpx; height: 12rpx; margin-top: -6rpx; border-right: 2rpx solid var(--ink-3); border-bottom: 2rpx solid var(--ink-3); transform: rotate(45deg); }
.target-static { color: var(--ink-2); font-size: 26rpx; }
.quota-line { color: var(--ink-3); font-size: 24rpx; font-variant-numeric: tabular-nums; }

.profile-notice { display: flex; align-items: center; gap: 16rpx; margin: 8rpx 0 4rpx; padding: 18rpx 24rpx; background: var(--warn-soft); border-radius: var(--r-inner); }
.notice-copy { flex: 1; color: var(--ink-1); font-size: 26rpx; line-height: 1.6; }
.notice-action { flex: none; margin: 0; padding: 8rpx 26rpx; color: var(--warn); background: transparent; border: 1rpx solid var(--warn); border-radius: var(--r-control); font-size: 24rpx; line-height: 1.5; }

.history-loading { padding: 40rpx 0; }

.chat-row { margin-top: 30rpx; }
.user-line { display: flex; flex-direction: column; align-items: flex-end; }
.user-bubble { max-width: 78%; padding: 20rpx 28rpx; background: var(--info-soft); border: 1px solid var(--line-warm); border-radius: 24rpx 24rpx 8rpx 24rpx; box-sizing: border-box; }
.user-text { color: var(--ink-1); font-size: 30rpx; line-height: 1.6; white-space: pre-wrap; }
.send-fail { display: flex; align-items: center; gap: 12rpx; margin-top: 10rpx; }
.fail-mark { color: var(--danger); font-size: 24rpx; }
.fail-retry { flex: none; margin: 0; padding: 6rpx 26rpx; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 24rpx; line-height: 1.5; }

.safety-line { display: flex; align-items: center; gap: 14rpx; margin: 4rpx 0 12rpx; }
.safety-icon { width: 14rpx; height: 14rpx; border: 3rpx solid var(--info-soft); border-top-color: var(--info); border-radius: 50%; }
.safety-icon.spinning { animation: qa-spin 1s linear infinite; }
@keyframes qa-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .safety-icon.spinning { animation: none; } }
.safety-check { width: 18rpx; height: 10rpx; margin-top: -4rpx; border-bottom: 3rpx solid var(--primary); border-left: 3rpx solid var(--primary); transform: rotate(-45deg); }
.safety-copy { color: var(--ink-3); font-size: 24rpx; }

.blocked-line { display: flex; align-items: center; gap: 16rpx; padding: 20rpx 24rpx; background: var(--danger-soft); border: 1px solid var(--danger); border-radius: var(--r-inner); }
.blocked-copy { flex: 1; color: var(--danger); font-size: 26rpx; line-height: 1.6; }
.blocked-action { flex: none; margin: 0; padding: 8rpx 24rpx; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 24rpx; line-height: 1.5; }

.answer-fail { display: flex; align-items: center; gap: 16rpx; padding: 20rpx 24rpx; background: var(--danger-soft); border-radius: var(--r-inner); }
.fail-copy { flex: 1; color: var(--danger); font-size: 26rpx; line-height: 1.6; }

.safety-static { padding: 28rpx; background: var(--warn-soft); border-radius: var(--r-card); }
.safety-static-head { display: flex; align-items: center; gap: 14rpx; }
.warn-mark { width: 18rpx; height: 18rpx; border: 4rpx solid var(--warn); border-radius: 50%; }
.safety-static-title { color: var(--ink-1); font-size: 30rpx; font-weight: 700; }
.safety-static-copy { display: block; margin-top: 14rpx; color: var(--ink-2); font-size: 27rpx; line-height: 1.7; }
.retry-button { display: inline-flex; align-items: center; justify-content: center; margin: 20rpx 0 0; padding: 0 32rpx; min-height: 68rpx; color: var(--warn); background: transparent; border: 1rpx solid var(--warn); border-radius: var(--r-control); font-size: 26rpx; }

.answer-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); padding: 0 28rpx 28rpx; box-shadow: var(--shadow-card); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 22rpx 0 18rpx; border-bottom: 1px solid var(--line); }
.ai-pill { display: flex; align-items: center; gap: 10rpx; padding: 8rpx 18rpx; background: var(--info-soft); border-radius: var(--r-control); }
.ai-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: var(--info); }
.ai-text { color: var(--ink-2); font-size: 22rpx; line-height: 1.4; }
.head-copy { flex: none; margin: 0; padding: 8rpx 24rpx; color: var(--ink-2); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-control); font-size: 24rpx; line-height: 1.5; }

.section-list { padding-top: 4rpx; }
.degraded-wrap { margin: 20rpx 0 4rpx; }
.answer-section { padding: 24rpx 0 8rpx; border-bottom: 1px solid var(--line); }
.answer-section:last-child { border-bottom: none; }
.section-title-row { display: flex; align-items: center; gap: 12rpx; margin-bottom: 6rpx; }
.section-dash { width: 28rpx; height: 4rpx; border-radius: 2rpx; background: var(--primary); }
.section-title { color: var(--ink-1); font-size: 32rpx; font-weight: 700; }
.answer-block { margin-top: 16rpx; }
.block-title { display: block; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.block-content { display: block; margin-top: 8rpx; color: var(--ink-2); font-size: 30rpx; line-height: 1.75; white-space: pre-wrap; }

.gated-section { margin-top: 14rpx; padding: 24rpx; background: #EDECE8; border-radius: var(--r-inner); }
.gated-block { margin-top: 14rpx; padding: 24rpx; background: #EDECE8; border-radius: var(--r-inner); }
.gated-title { display: block; color: var(--ink-1); font-size: 30rpx; font-weight: 650; }
.gated-summary { display: block; margin-top: 8rpx; color: var(--ink-3); font-size: 26rpx; line-height: 1.6; }
.gated-hint { display: block; color: var(--ink-2); font-size: 26rpx; line-height: 1.6; }
.gated-action { display: inline-flex; align-items: center; justify-content: center; margin: 18rpx 0 0; padding: 0 36rpx; min-height: 72rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 26rpx; }

.conflict-note { margin-top: 20rpx; padding: 18rpx 24rpx; background: var(--warn-soft); border-radius: var(--r-inner); }
.conflict-copy { color: var(--ink-1); font-size: 26rpx; line-height: 1.6; }
.answer-empty { display: flex; align-items: center; gap: 16rpx; margin-top: 20rpx; padding: 20rpx 24rpx; background: var(--surface-warm); border-radius: var(--r-inner); }
.updated-row { margin-top: 16rpx; }
.updated-copy { color: var(--warn); font-size: 24rpx; }
.readonly-row { margin-top: 18rpx; padding-top: 16rpx; border-top: 1px solid var(--line); }
.readonly-copy { color: var(--ink-3); font-size: 24rpx; }

.card-actions { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 24rpx; }
.action-item { margin: 0; padding: 12rpx 30rpx; color: var(--ink-2); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-control); font-size: 26rpx; line-height: 1.5; }
.action-item.disabled { opacity: .5; }
.pressed { opacity: .82; }

.input-dock { flex: none; background: var(--surface); }
.input-bar { display: flex; align-items: flex-end; gap: 16rpx; padding: 16rpx 24rpx 12rpx; }
.mic-button { display: flex; align-items: center; justify-content: center; width: 76rpx; height: 76rpx; flex: none; margin: 0; padding: 0; background: var(--surface-warm); border: var(--border-warm); border-radius: 50%; }
.mic-icon { position: relative; width: 18rpx; height: 30rpx; border-radius: 9rpx; background: var(--ink-3); }
.mic-icon::after { content: ''; position: absolute; left: -9rpx; top: 14rpx; width: 30rpx; height: 18rpx; border: 3rpx solid var(--ink-3); border-top: none; border-radius: 0 0 18rpx 18rpx; }
.question-input { flex: 1; min-height: 76rpx; max-height: 240rpx; padding: 16rpx 24rpx; color: var(--ink-1); background: var(--surface-warm); border: var(--border-warm); border-radius: var(--r-inner); font-size: 28rpx; line-height: 1.6; box-sizing: border-box; }
.question-input::placeholder { color: var(--ink-3); }
.send-button { display: flex; align-items: center; justify-content: center; flex: none; min-width: 128rpx; min-height: 76rpx; margin: 0; padding: 0 32rpx; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 28rpx; font-weight: 650; }
.send-button.disabled { opacity: .45; }

.export-canvas { position: fixed; left: -2000rpx; top: 0; width: 375px; height: 1px; }

.blocked-overlay { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 120; display: flex; align-items: center; justify-content: center; padding: 48rpx 40rpx; background: rgba(46, 51, 46, .5); box-sizing: border-box; }
.blocked-card { width: 100%; max-height: 86vh; overflow-y: auto; padding: 36rpx 32rpx; background: var(--surface); border: 2rpx solid var(--danger); border-radius: var(--r-card); box-sizing: border-box; }
.blocked-head { display: flex; align-items: center; justify-content: center; padding: 20rpx; background: var(--danger-soft); border-radius: var(--r-inner); }
.blocked-title { color: var(--danger); font-size: 34rpx; font-weight: 700; }
.blocked-lead { display: block; margin-top: 26rpx; color: var(--ink-1); font-size: 28rpx; line-height: 1.7; }
.blocked-reason { display: block; margin-top: 14rpx; color: var(--ink-3); font-size: 24rpx; line-height: 1.6; }
.channel-list { margin-top: 24rpx; border: 1px solid var(--line); border-radius: var(--r-inner); overflow: hidden; }
.channel-card { display: flex; align-items: center; gap: 16rpx; padding: 24rpx; border-bottom: 1px solid var(--line); }
.channel-card:last-child { border-bottom: none; }
.channel-info { flex: 1; min-width: 0; }
.channel-name { display: block; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.channel-phone { display: block; margin-top: 4rpx; color: var(--ink-2); font-size: 30rpx; font-variant-numeric: tabular-nums; }
.channel-script { display: block; margin-top: 6rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.5; }
.channel-call { display: flex; align-items: center; justify-content: center; flex: none; margin: 0; padding: 0 30rpx; min-height: 68rpx; color: var(--on-primary); background: var(--danger); border: 0; border-radius: var(--r-control); font-size: 26rpx; }
.channel-copy { display: flex; align-items: center; justify-content: center; flex: none; margin: 0; padding: 0 20rpx; min-height: 68rpx; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 24rpx; }
.blocked-confirm { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 92rpx; margin: 32rpx 0 0; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }
</style>

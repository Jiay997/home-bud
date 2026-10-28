<script setup lang="ts">
import { computed, getCurrentInstance, nextTick, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ApiError } from '../../platform/request'
import { chunkedRequest, chunkedSupported } from '../../platform/chunked'
import { activeBaseUrl, api, TOKEN_KEY } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import MiniActionSheet from '../../components/MiniActionSheet.vue'
import MiniMarkdown from '../../components/MiniMarkdown.vue'
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
  type QaBlockedInfo,
  type QaStreamFinish,
  type QaStreamSection,
  type QaStreamState
} from '../../services/qa-stream'
import { stripMarkdown, type LongImageDoc } from '../../services/image-export'
import { renderAndSaveLongImage } from '../../platform/long-image'
import { saveShareCardImage, shareCardCopy, shareCardMessage } from '../../platform/share-card'
import { runtime } from '../../platform/runtime'
import { createQaPhotoService, qaPhotoLimitCopy, type QaPhotoFile, type QaPhotoSource } from '../../services/qa-photo'
import { decodeRouteValue } from '../../services/route'
import {
  isSafetyDegrade,
  qaAiLabelText,
  qaConflictLabel,
  qaDegradedLabel,
  qaEntryInputPlaceholder,
  qaEntryLabel,
  qaEntryTitle,
  qaSectionTitle,
  qaTriageTone,
  qaTrustElementLabel
} from '../../services/qa-copy'
import { userFacingMessage } from '../../services/user-message'
import type { AiLabelView, PhotoGuideView, QaSessionBody, TriageView } from '../../api'

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
  /** 图片提问已送检的图片标识（≤3，重试沿用以避免重复上传） */
  photoUids: string[]
}

interface ChannelCard {
  channel_code?: string
  channel_name?: string
  phone_number?: string
  script?: string
  notice?: string
  service_hours?: string
  expired?: boolean
  placeholder?: boolean
  /** D-01：渠道占位/超期时的可执行兜底指引（如「请拨打 110/120」） */
  fallback_text?: string
}

/** 选图后的本地预览项（H5 为 blob 地址，小程序为临时路径；原图不上传第二份） */
interface PhotoPick {
  file: QaPhotoFile
  preview: string
}

/** 追问升级强提醒（不可关闭，仅可收起） */
interface EscalateBanner {
  text: string
  currentLabel: string
}

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
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
const channelExpiredCopy = '该渠道信息已过复核期，请以官方渠道公布号码为准'
const channelHoursCopy = (hours: string) => `服务时间 ${hours}`
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
// 未完成首启同意时进入问答：明确提示并回到首页同意门禁（N1 不可绕过）
const initialConsentRequiredCopy = '请先同意用户协议与免责声明'

// ---- V3.1 信任条 / 档位卡 / 长图 / 图片提问 / 追问重判 文案 ----
// 含拉丁字母文案一律经 script 常量插值，模板禁止裸写
const trustBarTitle = '本页信息依据'
const trustAiLabel = '生成标识'
const trustAgeLabel = '适用月龄'
const trustSourceLabel = '来源等级'
const trustBadgeLabel = '档位'
const trustMissingCopy = '信息待补'
const trustMissingLead = '信息待补：以下要素本次未完整下发，请结合正文与线下判断'
const trustCheckCopy = (passed: number, total: number) => `信任检查单通过 ${passed}/${total} 项`
const trustSourceMissing = '信息待补'
const sourceLowNote = '低等级来源，仅作科普参考'
const filingNoCopy = (value: string) => `生成式人工智能服务备案号 ${value}`

const triageSectionTitle = '本次档位'
const triageBasisTitle = '判定依据'
const triageObservationTitle = '观察项（可勾选记录，仅本机保存）'
const triageEscalationTitle = '升级红旗：出现任一项请按立即就医处理'
const triageContraTitle = '禁忌：请勿这样做'
const triageInsufficientTitle = '信息不足，需补充'
const triageInsufficientLead = '以下关键信息未提供，补全后可获得更明确的档位参考'
const triageUnavailableCopy = '分级服务暂不可用，请按通用就医建议处理：出现精神差、叫不醒、抽搐、呼吸困难、持续高热、无法进水或尿量明显减少等情况，请尽快线下就医。'
const triageNightTitle = '夜间提示'
const triageRuleCopy = (ruleId: string, version: number) => `判定规则 ${ruleId} · 规则版本 ${version}`
const triageDisclaimerTitle = '档位说明'
const referralAction = '就近就医指引'
const referralTitle = '就近就医指引'
const referralEmpty = '暂无已核验的机构信息，请优先选择设有急诊的医疗机构。'
const referralFailed = '就医指引读取失败，请稍后重试。'

const shareCardAction = '生成长图'
const shareCardBusy = shareCardCopy.busy

const photoPanelTitle = '图片提问'
const photoPrivacyTitle = '图片如何使用'
const photoSceneTitle = '拍摄场景'
const photoCameraCopy = '拍照'
const photoAlbumCopy = '从相册选择'
const photoSubmitCopy = '用这些图片提问'
const photoBusyCopy = '正在上传并送检…'
const photoGuideFailed = '图片提问说明读取失败，请稍后重试。'
const photoPanelClose = '关闭'
const photoTtlCopy = (hours: number) => `图片仅用于本次解析，${hours} 小时内删除原图`
const photoCountCopy = (count: number, max: number) => `已选 ${count}/${max} 张`
const photoEmptyCopy = '还没有选择图片'
const photoHistoryBlocked = '历史记录不可再发起图片提问'
const photoBusyStreaming = '当前回答仍在生成，请稍后再试'
const photoPickFailed = '无法打开相机或相册，可改用文字提问。'
const photoQuestionDefault = '请参考这张图片，说明需要注意的观察点'
const photoQuestionTag = (count: number) => `图片提问 · ${count} 张`

const escalateTitle = '档位已升级'
const escalateFallbackText = '档位已升级为「建议立即就医」：请优先线下就医，不要继续等待观察。'
const escalateCollapse = '收起'
const escalateExpand = '展开'

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
// 触达归因（RQ-08）：每周一问 / 提醒任务跳转时透传，支撑归因链
const reminderTrace = ref('')
const pendingPhotoEntry = ref(false)
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
// V3.1：页面级 AI 标识兜底（未拿到回答契约时不留空标识）+ 追问升级强提醒
const pageAiLabel = ref<AiLabelView | null>(null)
const escalateBanner = ref<EscalateBanner | null>(null)
const escalateCollapsed = ref(false)
// 档位观察项勾选：仅本机状态，不落库、不回传
const observationState = ref<Record<string, boolean>>({})
const referralBusy = ref(false)
// 图片提问：场景说明 + 本地选图 + 上传送检
const photoPanelVisible = ref(false)
const photoGuide = ref<PhotoGuideView | null>(null)
const photoGuideLoading = ref(false)
const photoGuideError = ref('')
const photoScene = ref('rash')
const photoPicks = ref<PhotoPick[]>([])
const photoBusy = ref(false)
const photoService = createQaPhotoService({
  runtime,
  upload: { uploadQaPhoto: (filePath, scene) => api.uploadQaPhoto(filePath, scene) }
})
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
const canSend = computed(
  () => draft.value.trim().length >= 5 && !sending.value && !busyStreaming.value
)
// 1-4 字时给出实时提示，避免用户只看到按钮置灰却不知道原因
const draftTooShort = computed(() => {
  const length = draft.value.trim().length
  return length > 0 && length < 5
})
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
const overlayAiText = computed(() => qaAiLabelText(blockedOverlay.value?.aiLabel || pageAiLabel.value))

// ---- 图片提问面板 ----
const photoMaxCount = computed(() => {
  const max = Number(photoGuide.value?.max_count)
  return Number.isFinite(max) && max > 0 ? Math.min(3, max) : 3
})
const photoScenes = computed(() => photoGuide.value?.scenes || [])
const photoSelectedGuide = computed(() => photoGuide.value?.selected?.guide || '')
const photoTtlText = computed(() => photoTtlCopy(Number(photoGuide.value?.ttl_hours) || 24))
const photoCountText = computed(() => (photoPicks.value.length
  ? photoCountCopy(photoPicks.value.length, photoMaxCount.value)
  : photoEmptyCopy))
const photoSubmitDisabled = computed(() => !photoPicks.value.length || photoBusy.value)

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
  reminderTrace.value = decodeRouteValue(query?.reminder_trace_id)
  // 隐私承诺页「图片处理说明」直达图片提问面板
  pendingPhotoEntry.value = String(query?.section || '') === 'photo'
  // D-12：工具页「深入问问」通过本地存储带入问题，避免 URL 双重编码；
  // 兼容旧链接：仅当 query 仍含百分号转义时才解码一次，防止二次解码。
  let question = String(query?.q ?? '')
  if (question.includes('%')) question = decodeRouteValue(question)
  question = question.trim()
  try {
    const prefilled = String(uni.getStorageSync('qa:prefill') || '').trim()
    if (prefilled) {
      uni.removeStorageSync('qa:prefill')
      if (!question) question = prefilled
    }
  } catch {
    // 存储不可用时忽略，使用 URL 中已有问题
  }
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
    // 同意节点（N1）：未同意时不静默回流（用户会误判为「点击无响应」），
    // 先给出明确提示再回到首页的同意门禁页
    uni.showToast({ title: initialConsentRequiredCopy, icon: 'none' })
    setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 600)
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
    // 不自动聚焦：真机键盘弹起会把 webview 整体上推，页头顶进状态栏（甲方需求 2026-10-15）
    void loadBootstrap()
  }
  if (pendingPhotoEntry.value) {
    pendingPhotoEntry.value = false
    void openPhotoPanel()
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
  void loadPageAiLabel()
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

// 页面级 AI 标识兜底：回答契约未下发时仍不留无标识页面（AC-RQ01-4）
async function loadPageAiLabel() {
  try {
    pageAiLabel.value = await api.fetchAiLabel('answer')
  } catch {
    pageAiLabel.value = null
  }
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
function makeUserItem(text: string, photoUids: string[] = []): ChatItem {
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
    createdAt: '',
    photoUids
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
    createdAt: '',
    photoUids: []
  }
}

function send() {
  const text = draft.value.trim()
  if (!text || !canSend.value) return
  draft.value = ''
  inputFocus.value = false
  void submitQuestion(text)
}

async function submitQuestion(text: string, resendOf?: ChatItem, photoUids: string[] = []) {
  let userItem: ChatItem
  if (resendOf) {
    const live = chat.value.find((item) => item.id === resendOf.id)
    if (!live) return
    userItem = live
    userItem.status = 'sending'
  } else {
    const raw = makeUserItem(text, photoUids)
    chat.value = [...chat.value, raw]
    userItem = chat.value[chat.value.length - 1]
  }
  void pinToBottom()
  // 追问重判：已有档位时把本次追问并入同一会话重判（不阻断本次提问）
  void recheckFollowup(userItem.text, photoUids)
  sending.value = true
  try {
    const body: QaSessionBody = {
      entry: entry.value,
      question: userItem.text,
      client_request_id: userItem.clientRequestId
    }
    if (entry.value !== 'family' && target.value?.profile_uid) body.profile_uid = target.value.profile_uid
    if (photoUids.length) {
      body.input_mode = 'photo'
      body.photo_uids = photoUids
    }
    if (reminderTrace.value) body.reminder_trace_id = reminderTrace.value
    const created = await api.createQaSession(body)
    userItem.status = 'sent'
    const answerRaw = makeAnswerItem(created.session_uid)
    chat.value = [...chat.value, answerRaw]
    void pinToBottom()
    startStream(chat.value[chat.value.length - 1])
  } catch (error: any) {
    userItem.status = 'failed'
    // 1301：服务端同意门禁（N1）拦下创建会话 → 明确提示并回到首页同意页，
    // 而不是停在问答页显示一句看不懂的错误
    if (error instanceof ApiError && error.code === 1301) {
      uni.showToast({ title: initialConsentRequiredCopy, icon: 'none' })
      setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 600)
      return
    }
    uni.showToast({ title: userFacingMessage(error, sendFailedCopy), icon: 'none' })
  } finally {
    sending.value = false
  }
}

function retrySend(item: ChatItem) {
  if (item.status !== 'failed' || sending.value) return
  void submitQuestion(item.text, item, item.photoUids)
}

/**
 * 追问重判（RQ-06）：把追问并入最近一条已有档位的会话重判。
 * 档位只升不降由服务端保证；升级时在页首插入不可关闭、可收起的强提醒条。
 */
async function recheckFollowup(text: string, photoUids: string[] = []) {
  if (!text.trim()) return
  if (photoUids.length) return
  const targetItem = [...chat.value]
    .reverse()
    .find((item) => item.role === 'answer' && item.sessionUid && item.state.triage && !item.historyMode)
  if (!targetItem) return
  try {
    const result = await api.recheckTriage(targetItem.sessionUid, { followup: text.trim() })
    if (result.triage) {
      targetItem.state = { ...targetItem.state, triage: result.triage as TriageView }
    }
    if (result.escalate_banner) {
      const bannerText = String(result.banner_text || '').trim()
      escalateBanner.value = {
        text: bannerText && !/[A-Za-z]/.test(bannerText) ? bannerText : escalateFallbackText,
        currentLabel: String(result.triage?.level_label || '')
      }
      escalateCollapsed.value = false
      // 强提醒必须被看到：滚动到页首提醒条（用户已滚到底部提问时尤其重要）
      scrollAnchor.value = ''
      void nextTick().then(() => { scrollAnchor.value = 'qa-top' })
    }
  } catch {
    // 重判失败不阻断本次提问（档位仍保留首轮判定）
  }
}

function toggleEscalateBanner() {
  escalateCollapsed.value = !escalateCollapsed.value
}

function startStream(item: ChatItem) {
  item.streamError = ''
  if (!chunkedSupported()) {
    void fallbackPoll(item, true)
    return
  }
  const service = createQaStreamService({
    request: chunkedRequest,
    storage: { getStorageSync: (key: string) => uni.getStorageSync(key) },
    // 流式请求必须与常规 API 同源：用 resolver 当前生效地址，而不是编译期 BASE_URL
    // （BASE_URL 可能是真机预览用局域网地址，DevTools 内经代理访问会 502）
    baseUrl: activeBaseUrl(),
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
    blocked: blocked
      ? {
          reason: blockedLineCopy,
          channels: [],
          appealAllowed: false,
          aiLabel: (payload?.ai_label as AiLabelView) || null
        }
      : null,
    errorMessage: failed ? streamFailedCopy : !blocked && sections.length === 0 ? timeoutCopy : '',
    // 轮询兜底同样不得丢合规要素（RQ-01 / RQ-06 / RQ-07）
    aiLabel: (payload?.ai_label as AiLabelView) || null,
    trustBar: payload?.trust_bar && typeof payload.trust_bar === 'object' ? payload.trust_bar : null,
    triage: payload?.triage === null || payload?.triage === undefined ? null : (payload.triage as TriageView),
    inputMode: String(payload?.input_mode || ''),
    photoMeta: payload?.photo_meta && typeof payload.photo_meta === 'object' ? payload.photo_meta : null
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
    phase: 'done',
    // 历史详情接口当前未下发信任条/档位：缺失即不渲染，不做本地补造
    aiLabel: (detail?.ai_label as AiLabelView) || null,
    trustBar: detail?.trust_bar && typeof detail.trust_bar === 'object' ? detail.trust_bar : null,
    triage: detail?.triage && typeof detail.triage === 'object' ? (detail.triage as TriageView) : null,
    inputMode: String(detail?.input_mode || '')
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
          blocked: { reason: blockedLineCopy, channels: [], appealAllowed: true, aiLabel: pageAiLabel.value }
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
// 流式传输适配（小程序 enableChunked / H5 fetch 流式）已抽至 platform/chunked，
// 本页只保留「支持则流式、不支持则轮询降级」的编排逻辑。
// ------------------------------------------------------------------

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
// 信任条（RQ-07）：AI 标识 / 月龄适配 / 来源等级徽标 / 档位徽标 + 缺失要素
// ------------------------------------------------------------------
function trustBarOf(item: ChatItem) {
  return item.state.trustBar
}

function aiLabelOf(item: ChatItem) {
  return qaAiLabelText(item.state.aiLabel || item.state.trustBar?.ai_label || pageAiLabel.value)
}

function trustAgeText(item: ChatItem) {
  const bar = item.state.trustBar
  if (!bar?.age_adaptation) return ''
  const label = bar.age_adaptation.label || ''
  const hint = bar.age_adaptation.hint || ''
  if (!hint) return label
  return `${label} · ${hint}`
}

function trustSources(item: ChatItem) {
  return item.state.trustBar?.source_levels || []
}

function sourceText(source: { level_label?: string; missing?: boolean; low_level?: boolean }) {
  if (source.missing) return trustSourceMissing
  return source.level_label || trustSourceMissing
}

function trustBadge(item: ChatItem) {
  const bar = item.state.trustBar
  return bar?.triage_badge || null
}

function trustMissing(item: ChatItem) {
  const missing = item.state.trustBar?.missing || []
  return missing.map((key) => qaTrustElementLabel(key))
}

function trustCheckText(item: ChatItem) {
  const bar = item.state.trustBar
  if (!bar) return ''
  return trustCheckCopy(Number(bar.checklist_passed) || 0, Number(bar.checklist_total) || 10)
}

function filingNoOf(item: ChatItem) {
  const label = item.state.aiLabel || item.state.trustBar?.ai_label || pageAiLabel.value
  return String(label?.filing_no || '').trim()
}

// ------------------------------------------------------------------
// 档位卡（RQ-06）：红=立即就医 / 黄=尽快评估 / 绿=居家观察；红旗与禁忌权重高于正文
// ------------------------------------------------------------------
function triageOf(item: ChatItem): TriageView | null {
  return item.state.triage
}

function triageTone(item: ChatItem) {
  return qaTriageTone(item.state.triage?.level_color)
}

function triageTitle(item: ChatItem) {
  const triage = item.state.triage
  if (!triage) return ''
  return triage.level_label || triageSectionTitle
}

function triageHidden(item: ChatItem) {
  const triage = item.state.triage
  if (!triage) return true
  // 无分级场景（level=null 且非信息不足 / 非不可用）不展示档位卡
  return !triage.level && !triage.insufficient && !triage.unavailable
}

function triageInsufficient(item: ChatItem) {
  return item.state.triage?.insufficient === true
}

function triageUnavailable(item: ChatItem) {
  return item.state.triage?.unavailable === true
}

function triageMissingInfo(item: ChatItem) {
  return item.state.triage?.missing_info || []
}

function triageObservations(item: ChatItem) {
  return item.state.triage?.observations || []
}

function triageEscalation(item: ChatItem) {
  return item.state.triage?.escalation_flags || []
}

function triageContra(item: ChatItem) {
  return item.state.triage?.contraindications || []
}

function triageDisclaimers(item: ChatItem) {
  return item.state.triage?.disclaimers || []
}

function triageRulesText(item: ChatItem) {
  const hit = item.state.triage?.rule_hits?.[0]
  if (!hit) return ''
  return triageRuleCopy(String(hit.rule_id || ''), Number(hit.version) || 0)
}

// 观察项勾选：仅本地状态，不落库、不上报
function observationKey(item: ChatItem, index: number) {
  return `${item.id}:${index}`
}

function observationChecked(item: ChatItem, index: number) {
  return observationState.value[observationKey(item, index)] === true
}

function toggleObservation(item: ChatItem, index: number) {
  const key = observationKey(item, index)
  observationState.value = { ...observationState.value, [key]: !observationChecked(item, index) }
}

function canReferral(item: ChatItem) {
  const level = item.state.triage?.level
  return !item.historyMode && (level === 'red' || level === 'yellow')
}

async function openReferral(item: ChatItem) {
  if (referralBusy.value || !item.sessionUid) return
  referralBusy.value = true
  try {
    const result = await api.fetchReferral({
      scene: item.entry === 'pet' ? 'pet_redflag' : 'triage_red',
      session_uid: item.sessionUid
    })
    const lines: string[] = []
    if (result.notice) lines.push(result.notice)
    for (const entryItem of result.items || []) {
      const meta = [entryItem.address, entryItem.service_hours].filter(Boolean).join(' · ')
      lines.push(meta ? `${entryItem.name || referralTitle}：${meta}` : String(entryItem.name || ''))
    }
    if (result.fallback_guide) lines.push(result.fallback_guide)
    if (result.reason) lines.push(result.reason)
    void openDialog({
      title: referralTitle,
      message: lines.filter(Boolean).join('\n') || referralEmpty,
      showCancel: false,
      confirmText: '知道了'
    })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, referralFailed), icon: 'none' })
  } finally {
    referralBusy.value = false
  }
}

// ------------------------------------------------------------------
// 服务端分享长图（RQ-09 + RQ-01：图内双标识 + PNG 隐式标识）
// ------------------------------------------------------------------
async function saveShareCard(item: ChatItem) {
  if (savingImage.value || !item.sessionUid) return
  savingImage.value = true
  uni.showLoading({ title: shareCardBusy, mask: true })
  let outcome: Awaited<ReturnType<typeof saveShareCardImage>> = 'failed'
  try {
    const token = uni.getStorageSync(TOKEN_KEY)
    outcome = await saveShareCardImage({
      url: api.qaShareCardUrl(item.sessionUid),
      token: typeof token === 'string' ? token : '',
      fileName: `Babe宝伴-问答长图-${item.sessionUid}.png`
    })
  } catch {
    outcome = 'failed'
  } finally {
    uni.hideLoading()
    savingImage.value = false
  }
  uni.showToast({ title: shareCardMessage(outcome), icon: 'none' })
}

// ------------------------------------------------------------------
// 图片提问（RQ-05）：先说明拍摄与隐私口径，再选图 → 上传送检 → 以图片形态提问
// ------------------------------------------------------------------
function previewOf(file: QaPhotoFile): string {
  const path = file.tempFilePath
  if (typeof path === 'string') return path
  // 小程序选图返回临时路径（直接可预览）；H5 返回 File 对象，需转 blob 地址
  if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
    try {
      return URL.createObjectURL(path)
    } catch {
      return ''
    }
  }
  return ''
}

function releasePreview(preview: string) {
  if (!preview || !preview.startsWith('blob:')) return
  if (typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
    try {
      URL.revokeObjectURL(preview)
    } catch {
      // 释放失败不影响后续流程
    }
  }
}

function releasePreviews() {
  for (const pick of photoPicks.value) releasePreview(pick.preview)
  photoPicks.value = []
}

async function loadPhotoGuide(scene: string) {
  photoGuideLoading.value = true
  photoGuideError.value = ''
  try {
    photoGuide.value = await api.fetchPhotoGuide(scene)
  } catch (error: any) {
    photoGuideError.value = userFacingMessage(error, photoGuideFailed)
  } finally {
    photoGuideLoading.value = false
  }
}

function openPhotoPanel() {
  if (historyMode.value) {
    uni.showToast({ title: photoHistoryBlocked, icon: 'none' })
    return
  }
  if (busyStreaming.value) {
    uni.showToast({ title: photoBusyStreaming, icon: 'none' })
    return
  }
  photoPanelVisible.value = true
  photoPicks.value = []
  photoScene.value = 'rash'
  void loadPhotoGuide(photoScene.value)
}

function closePhotoPanel() {
  if (photoBusy.value) return
  photoPanelVisible.value = false
  releasePreviews()
}

function selectPhotoScene(scene: string) {
  if (photoBusy.value || scene === photoScene.value) return
  photoScene.value = scene
  void loadPhotoGuide(scene)
}

async function pickPhoto(source: QaPhotoSource) {
  if (photoBusy.value) return
  const remaining = photoMaxCount.value - photoPicks.value.length
  if (remaining <= 0) {
    uni.showToast({ title: qaPhotoLimitCopy, icon: 'none' })
    return
  }
  try {
    const files = await photoService.pick(source, photoMaxCount.value, remaining)
    if (!files) return
    const added: PhotoPick[] = files.map((file) => ({ file, preview: previewOf(file) }))
    photoPicks.value = [...photoPicks.value, ...added].slice(0, photoMaxCount.value)
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, photoPickFailed), icon: 'none' })
  }
}

function removePhoto(index: number) {
  const picked = photoPicks.value[index]
  if (picked) releasePreview(picked.preview)
  photoPicks.value = photoPicks.value.filter((_, position) => position !== index)
}

async function submitPhotoQuestion() {
  if (photoSubmitDisabled.value) return
  photoBusy.value = true
  try {
    const batch = await photoService.upload(
      photoPicks.value.map((pick) => pick.file),
      photoScene.value
    )
    // 1303（送检未通过 / 配额超限）：停在面板，本次不计提问次数，不回退为文字提问
    if (batch.rejected) return
    if (!batch.photoUids.length) return
    const text = draft.value.trim() || photoQuestionDefault
    draft.value = ''
    photoPanelVisible.value = false
    releasePreviews()
    await submitQuestion(text, undefined, batch.photoUids)
  } finally {
    photoBusy.value = false
  }
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
      .map((block) => [block.title, stripMarkdown(block.content || '')].filter(Boolean).join('\n'))
      .filter(Boolean)
      .join('\n\n')
    if (!body) return []
    return [{ heading: qaSectionTitle(section), body }]
  })
  return {
    brand: 'Babe宝伴',
    title: questionOf(item) || qaEntryLabel(item.entry),
    meta: `${qaEntryLabel(item.entry)} · ${formatDate(item.createdAt)}`,
    dimensions: [],
    sections,
    disclaimers: [disclaimerLine],
    badge: '内容由 AI 生成'
  }
}

// 长图的取画布、导出与落盘已抽至 platform/long-image（小程序存相册 / H5 触发下载），
// 本页只保留文档构建与交互编排。

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
      const outcome = await renderAndSaveLongImage({
        doc,
        selector: '#qa-export-canvas',
        instance
      })
      uni.hideLoading()
      if (outcome === 'saved') {
        uni.showToast({ title: savedCopy, icon: 'none' })
        // D-13：H5 通过浏览器下载保存，无相册预览；补充明确的结果反馈，
        // 避免用户点击后不知道图片去了哪里。
        // #ifdef H5
        uni.showModal({
          title: '长图已生成',
          content: '已触发浏览器下载，可在浏览器「下载」记录中查看；图片含 AI 生成标识。',
          showCancel: false,
          confirmText: '知道了'
        })
        // #endif
      } else promptAlbumSetting()
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
        <!-- 追问重判升级：不可关闭、可收起的强提醒（RQ-06 AC-RQ06-5） -->
        <view v-if="escalateBanner" id="qa-top" class="escalate-banner" :class="{ collapsed: escalateCollapsed }">
          <view class="escalate-head">
            <view class="escalate-mark" />
            <text class="escalate-title">{{ escalateTitle }}</text>
            <text v-if="escalateBanner.currentLabel" class="escalate-level">{{ escalateBanner.currentLabel }}</text>
            <button class="escalate-toggle" hover-class="pressed" @tap="toggleEscalateBanner">
              {{ escalateCollapsed ? escalateExpand : escalateCollapse }}
            </button>
          </view>
          <text v-if="!escalateCollapsed" class="escalate-copy">{{ escalateBanner.text }}</text>
        </view>

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
                <text v-if="item.photoUids.length" class="user-photo-tag">{{ photoQuestionTag(item.photoUids.length) }}</text>
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
                  <text class="ai-text">{{ aiLabelOf(item) }}</text>
                </view>
                <button v-if="hasRenderableContent(item)" class="head-copy" hover-class="pressed" @tap="copyAnswer(item)">复制</button>
              </view>

              <!-- 信任条（RQ-07）：标识 / 月龄 / 来源等级 / 档位徽标，缺失要素显示「信息待补」 -->
              <view v-if="trustBarOf(item)" class="trust-bar">
                <view class="trust-head">
                  <view class="trust-dash" />
                  <text class="trust-title">{{ trustBarTitle }}</text>
                  <text class="trust-check">{{ trustCheckText(item) }}</text>
                </view>
                <view class="trust-row">
                  <text class="trust-key">{{ trustAiLabel }}</text>
                  <text class="trust-val">{{ aiLabelOf(item) }}</text>
                </view>
                <text v-if="filingNoOf(item)" class="trust-filing">{{ filingNoCopy(filingNoOf(item)) }}</text>
                <view v-if="trustAgeText(item)" class="trust-row">
                  <text class="trust-key">{{ trustAgeLabel }}</text>
                  <text class="trust-val">{{ trustAgeText(item) }}</text>
                </view>
                <view v-if="trustSources(item).length" class="trust-source-row">
                  <text class="trust-key">{{ trustSourceLabel }}</text>
                  <view class="source-list">
                    <view
                      v-for="source in trustSources(item)"
                      :key="source.kb_id"
                      class="source-chip"
                      :class="{ missing: source.missing, low: source.low_level }"
                    >
                      <text class="source-badge">{{ source.badge }}</text>
                      <text class="source-text">{{ sourceText(source) }}</text>
                    </view>
                  </view>
                </view>
                <view v-if="trustBadge(item)" class="trust-row">
                  <text class="trust-key">{{ trustBadgeLabel }}</text>
                  <view class="trust-badge" :class="'tone-' + triageTone(item)">
                    <text class="trust-badge-text">{{ trustBadge(item)?.label }}</text>
                  </view>
                </view>
                <view v-if="trustMissing(item).length" class="trust-missing">
                  <text class="trust-missing-lead">{{ trustMissingCopy }}</text>
                  <text class="trust-missing-list">{{ trustMissing(item).join('、') }}</text>
                  <text class="trust-missing-note">{{ trustMissingLead }}</text>
                </view>
              </view>

              <!-- 档位卡（RQ-06）：红旗 / 禁忌视觉权重高于正文 -->
              <view
                v-if="!triageHidden(item)"
                class="triage-card"
                :class="'tone-' + triageTone(item)"
              >
                <view class="triage-head">
                  <view class="triage-beacon" />
                  <text class="triage-title">{{ triageTitle(item) }}</text>
                  <text v-if="triageOf(item)?.icon" class="triage-icon">{{ triageOf(item)?.icon }}</text>
                </view>
                <text v-if="triageOf(item)?.action_hint" class="triage-action">{{ triageOf(item)?.action_hint }}</text>

                <view v-if="triageInsufficient(item)" class="triage-flag">
                  <text class="triage-flag-title">{{ triageInsufficientTitle }}</text>
                  <text class="triage-flag-copy">{{ triageInsufficientLead }}</text>
                  <view v-for="(info, infoIndex) in triageMissingInfo(item)" :key="infoIndex" class="triage-li">
                    <view class="triage-li-dot" />
                    <text class="triage-li-text">{{ info }}</text>
                  </view>
                </view>

                <view v-if="triageUnavailable(item)" class="triage-flag">
                  <text class="triage-flag-copy">{{ triageUnavailableCopy }}</text>
                </view>

                <view v-if="triageOf(item)?.basis" class="triage-block">
                  <text class="triage-block-title">{{ triageBasisTitle }}</text>
                  <text class="triage-block-body">{{ triageOf(item)?.basis }}</text>
                </view>

                <view v-if="triageObservations(item).length" class="triage-block">
                  <text class="triage-block-title">{{ triageObservationTitle }}</text>
                  <view
                    v-for="(observation, observationIndex) in triageObservations(item)"
                    :key="observationIndex"
                    class="triage-check"
                    hover-class="pressed"
                    @tap="toggleObservation(item, observationIndex)"
                  >
                    <view class="triage-box" :class="{ checked: observationChecked(item, observationIndex) }">
                      <view v-if="observationChecked(item, observationIndex)" class="triage-tick" />
                    </view>
                    <text class="triage-check-text">{{ observation }}</text>
                  </view>
                </view>

                <view v-if="triageEscalation(item).length" class="triage-alert">
                  <text class="triage-alert-title">{{ triageEscalationTitle }}</text>
                  <view v-for="(flag, flagIndex) in triageEscalation(item)" :key="flagIndex" class="triage-alert-row">
                    <view class="triage-alert-dot" />
                    <text class="triage-alert-text">{{ flag }}</text>
                  </view>
                </view>

                <view v-if="triageContra(item).length" class="triage-contra">
                  <text class="triage-contra-title">{{ triageContraTitle }}</text>
                  <view v-for="(contra, contraIndex) in triageContra(item)" :key="contraIndex" class="triage-contra-row">
                    <view class="triage-contra-dot" />
                    <text class="triage-contra-text">{{ contra }}</text>
                  </view>
                </view>

                <view v-if="triageOf(item)?.night_mode && triageOf(item)?.night_notice" class="triage-night">
                  <text class="triage-night-title">{{ triageNightTitle }}</text>
                  <text class="triage-night-copy">{{ triageOf(item)?.night_notice }}</text>
                </view>

                <view v-if="triageDisclaimers(item).length" class="triage-disclaimer">
                  <text class="triage-disclaimer-title">{{ triageDisclaimerTitle }}</text>
                  <text v-for="(line, lineIndex) in triageDisclaimers(item)" :key="lineIndex" class="triage-disclaimer-line">{{ line }}</text>
                </view>

                <view class="triage-foot">
                  <text v-if="triageRulesText(item)" class="triage-rules">{{ triageRulesText(item) }}</text>
                  <button v-if="canReferral(item)" class="triage-referral" hover-class="pressed" @tap="openReferral(item)">{{ referralAction }}</button>
                </view>
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
                        <MiniMarkdown v-if="block.content" :content="block.content" />
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
                  <button
                    v-if="!item.historyMode"
                    class="action-item"
                    :class="{ disabled: savingImage }"
                    hover-class="pressed"
                    @tap="saveShareCard(item)"
                  >
                    {{ shareCardAction }}
                  </button>
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
        <button
          v-if="!historyMode"
          class="camera-button"
          hover-class="pressed"
          aria-label="图片提问"
          @tap="openPhotoPanel"
        >
          <view class="camera-icon" />
        </button>
        <textarea
          v-model="draft"
          class="question-input"
          :placeholder="inputPlaceholder"
          :maxlength="2000"
          :auto-height="true"
          :show-confirm-bar="false"
          confirm-type="send"
          :focus="inputFocus"
          :cursor-spacing="120"
          @confirm="send"
        />
        <button class="send-button" :class="{ disabled: !canSend }" :disabled="!canSend" hover-class="pressed" @tap="send">发送</button>
      </view>
      <text v-if="draftTooShort" class="input-hint">至少输入 5 个字，描述越具体越有帮助</text>
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

    <!-- 图片提问（RQ-05）：隐私说明与拍摄要点先于选图，拒绝授权可改用文字 -->
    <view v-if="photoPanelVisible" class="photo-mask" @tap="closePhotoPanel">
      <view class="photo-sheet" @tap.stop>
        <view class="photo-head">
          <text class="photo-title">{{ photoPanelTitle }}</text>
          <button class="photo-close" hover-class="pressed" @tap="closePhotoPanel">{{ photoPanelClose }}</button>
        </view>
        <scroll-view scroll-y class="photo-scroll">
          <view v-if="photoGuideLoading" class="photo-loading"><StateSkeleton mode="skeleton" /></view>
          <view v-else-if="photoGuideError" class="photo-error">
            <text class="photo-error-copy">{{ photoGuideError }}</text>
            <button class="photo-retry" hover-class="pressed" @tap="loadPhotoGuide(photoScene)">重试</button>
          </view>
          <template v-else-if="photoGuide">
            <text class="photo-section-title">{{ photoPrivacyTitle }}</text>
            <text class="photo-privacy">{{ photoGuide.privacy_notice }}</text>
            <text class="photo-degrade">{{ photoGuide.degradation }}</text>

            <text class="photo-section-title">{{ photoSceneTitle }}</text>
            <view class="scene-row">
              <view
                v-for="scene in photoScenes"
                :key="scene.scene"
                class="scene-chip"
                :class="{ active: scene.scene === photoScene }"
                hover-class="pressed"
                @tap="selectPhotoScene(scene.scene)"
              >
                <text class="scene-label">{{ scene.label }}</text>
              </view>
            </view>
            <text v-if="photoSelectedGuide" class="scene-guide">{{ photoSelectedGuide }}</text>

            <view class="photo-actions">
              <button class="photo-pick" hover-class="pressed" @tap="pickPhoto('camera')">{{ photoCameraCopy }}</button>
              <button class="photo-pick" hover-class="pressed" @tap="pickPhoto('album')">{{ photoAlbumCopy }}</button>
            </view>
            <text class="photo-count">{{ photoCountText }}</text>
            <view v-if="photoPicks.length" class="thumb-row">
              <view v-for="(pick, pickIndex) in photoPicks" :key="pickIndex" class="thumb">
                <image v-if="pick.preview" class="thumb-img" :src="pick.preview" mode="aspectFill" />
                <button class="thumb-del" hover-class="pressed" @tap="removePhoto(pickIndex)">移除</button>
              </view>
            </view>
            <text class="photo-ttl">{{ photoTtlText }}</text>
          </template>
        </scroll-view>
        <view class="photo-foot">
          <button
            class="photo-submit"
            :class="{ disabled: photoSubmitDisabled }"
            :disabled="photoSubmitDisabled"
            hover-class="pressed"
            @tap="submitPhotoQuestion"
          >
            {{ photoBusy ? photoBusyCopy : photoSubmitCopy }}
          </button>
        </view>
      </view>
    </view>

    <view v-if="blockedOverlay" class="blocked-overlay">
      <view class="blocked-card">
        <view class="blocked-head">
          <text class="blocked-title">{{ blockedTitle }}</text>
        </view>
        <view class="blocked-ai">
          <view class="blocked-ai-dot" />
          <text class="blocked-ai-text">{{ overlayAiText }}</text>
        </view>
        <text class="blocked-lead">{{ blockedLead }}</text>
        <text class="blocked-reason">{{ blockedReasonCopy }}</text>
        <view class="channel-list">
          <view v-for="(channel, channelIndex) in overlayChannels" :key="channelIndex" class="channel-card">
            <view class="channel-info">
              <text class="channel-name">{{ channel.channel_name }}</text>
              <text v-if="channel.phone_number" class="channel-phone">{{ channel.phone_number }}</text>
              <text v-else class="channel-phone">{{ channelFallbackNote }}</text>
              <text v-if="channel.service_hours" class="channel-script">{{ channelHoursCopy(channel.service_hours) }}</text>
              <text v-if="channel.expired" class="channel-expired">{{ channelExpiredCopy }}</text>
              <text v-if="channel.script" class="channel-script">{{ channel.script }}</text>
              <text v-if="channel.notice" class="channel-script">{{ channel.notice }}</text>
              <text v-if="channel.fallback_text" class="channel-fallback">{{ channel.fallback_text }}</text>
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
.input-hint { display: block; margin: 0 32rpx 8rpx; color: var(--warn); font-size: 22rpx; line-height: 1.5; }
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
.channel-expired { display: block; margin-top: 6rpx; color: var(--warn); font-size: 22rpx; line-height: 1.5; }
.channel-fallback { display: block; margin-top: 8rpx; color: var(--warn); font-size: 24rpx; font-weight: 600; line-height: 1.5; }
.channel-call { display: flex; align-items: center; justify-content: center; flex: none; margin: 0; padding: 0 30rpx; min-height: 68rpx; color: var(--on-primary); background: var(--danger); border: 0; border-radius: var(--r-control); font-size: 26rpx; }
.channel-copy { display: flex; align-items: center; justify-content: center; flex: none; margin: 0; padding: 0 20rpx; min-height: 68rpx; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 24rpx; }
.blocked-confirm { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 92rpx; margin: 32rpx 0 0; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 30rpx; font-weight: 650; }

/* ---- V3.1：追问升级强提醒 / 信任条 / 档位卡 / 图片提问 ---- */
.escalate-banner { margin-bottom: 18rpx; padding: 22rpx 24rpx; background: var(--danger-soft); border: 2rpx solid var(--danger); border-radius: var(--r-card); }
.escalate-banner.collapsed { padding-bottom: 18rpx; }
.escalate-head { display: flex; align-items: center; gap: 12rpx; }
.escalate-mark { width: 14rpx; height: 14rpx; flex: none; border-radius: 50%; background: var(--danger); }
.escalate-title { color: var(--danger); font-size: 28rpx; font-weight: 700; }
.escalate-level { flex: 1; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.escalate-toggle { flex: none; margin: 0; padding: 4rpx 20rpx; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 22rpx; line-height: 1.4; }
.escalate-copy { display: block; margin-top: 12rpx; color: var(--ink-1); font-size: 26rpx; line-height: 1.7; }

.user-photo-tag { display: block; margin-top: 8rpx; color: var(--ink-3); font-size: 22rpx; }

.camera-button { display: flex; align-items: center; justify-content: center; width: 68rpx; height: 76rpx; flex: none; margin: 0; padding: 0; background: var(--surface-warm); border: var(--border-warm); border-radius: 50%; }
.camera-icon { position: relative; width: 32rpx; height: 24rpx; border: 3rpx solid var(--ink-3); border-radius: 6rpx; }
.camera-icon::before { position: absolute; top: -9rpx; left: 7rpx; width: 14rpx; height: 6rpx; background: var(--ink-3); border-radius: 3rpx 3rpx 0 0; content: ''; }
.camera-icon::after { position: absolute; top: 4rpx; left: 7rpx; width: 12rpx; height: 12rpx; border: 3rpx solid var(--ink-3); border-radius: 50%; content: ''; }

.trust-bar { margin: 20rpx 0 4rpx; padding: 20rpx 22rpx; background: var(--surface-warm); border: 1px solid var(--line-warm); border-radius: var(--r-inner); }
.trust-head { display: flex; align-items: center; gap: 10rpx; margin-bottom: 12rpx; }
.trust-dash { width: 20rpx; height: 4rpx; border-radius: 2rpx; background: var(--primary); }
.trust-title { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.trust-check { margin-left: auto; color: var(--ink-3); font-size: 22rpx; font-variant-numeric: tabular-nums; }
.trust-row { display: flex; align-items: flex-start; gap: 14rpx; margin-top: 8rpx; }
.trust-source-row { display: flex; align-items: flex-start; gap: 14rpx; margin-top: 10rpx; }
.trust-key { flex: none; width: 128rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.trust-val { flex: 1; color: var(--ink-2); font-size: 23rpx; line-height: 1.6; }
.trust-filing { display: block; margin: 6rpx 0 0 142rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.5; }
.source-list { display: flex; flex: 1; flex-wrap: wrap; gap: 10rpx; }
.source-chip { display: flex; align-items: center; gap: 8rpx; padding: 6rpx 14rpx; background: var(--info-soft); border-radius: var(--r-control); }
.source-chip.missing { background: var(--warn-soft); }
.source-chip.low { background: var(--surface); border: 1px dashed var(--warn); }
.source-badge { color: var(--info); font-size: 20rpx; font-weight: 700; }
.source-chip.low .source-badge { color: var(--warn); }
.source-text { color: var(--ink-2); font-size: 21rpx; }
.trust-badge { flex: none; padding: 4rpx 16rpx; border-radius: var(--r-control); }
.trust-badge-text { font-size: 21rpx; font-weight: 650; }
.trust-badge.tone-danger { background: var(--danger-soft); }
.trust-badge.tone-danger .trust-badge-text { color: var(--danger); }
.trust-badge.tone-warn { background: var(--warn-soft); }
.trust-badge.tone-warn .trust-badge-text { color: var(--warn); }
.trust-badge.tone-ok { background: var(--primary-soft); }
.trust-badge.tone-ok .trust-badge-text { color: var(--primary-press); }
.trust-badge.tone-neutral { background: var(--surface); border: 1px solid var(--line); }
.trust-badge.tone-neutral .trust-badge-text { color: var(--ink-2); }
.trust-missing { margin-top: 14rpx; padding: 14rpx 16rpx; background: var(--warn-soft); border-radius: var(--r-inner); }
.trust-missing-lead { color: var(--warn); font-size: 22rpx; font-weight: 650; }
.trust-missing-list { display: block; margin-top: 6rpx; color: var(--ink-1); font-size: 23rpx; line-height: 1.6; }
.trust-missing-note { display: block; margin-top: 6rpx; color: var(--ink-3); font-size: 21rpx; line-height: 1.55; }

.triage-card { margin: 22rpx 0 6rpx; padding: 24rpx 22rpx; border-radius: var(--r-card); border-left: 10rpx solid var(--ink-3); background: var(--surface-warm); }
.triage-card.tone-danger { background: var(--danger-soft); border-left-color: var(--danger); }
.triage-card.tone-warn { background: var(--warn-soft); border-left-color: var(--warn); }
.triage-card.tone-ok { background: var(--primary-soft); border-left-color: var(--primary); }
.triage-card.tone-neutral { background: var(--surface-warm); border-left-color: var(--ink-3); }
.triage-head { display: flex; align-items: center; gap: 12rpx; }
.triage-beacon { width: 18rpx; height: 18rpx; flex: none; border-radius: 50%; background: var(--ink-3); }
.tone-danger .triage-beacon { background: var(--danger); }
.tone-warn .triage-beacon { background: var(--warn); }
.tone-ok .triage-beacon { background: var(--primary); }
.triage-title { flex: 1; color: var(--ink-1); font-size: 34rpx; font-weight: 700; letter-spacing: 1rpx; }
.tone-danger .triage-title { color: var(--danger); }
.tone-warn .triage-title { color: var(--warn); }
.tone-ok .triage-title { color: var(--primary-press); }
.triage-icon { flex: none; font-size: 30rpx; }
.triage-action { display: block; margin-top: 12rpx; color: var(--ink-1); font-size: 26rpx; line-height: 1.7; }
.triage-flag { margin-top: 16rpx; padding: 16rpx; background: rgba(255, 255, 255, .66); border-radius: var(--r-inner); }
.triage-flag-title { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.triage-flag-copy { display: block; margin-top: 6rpx; color: var(--ink-2); font-size: 24rpx; line-height: 1.7; }
.triage-li { display: flex; align-items: flex-start; gap: 10rpx; margin-top: 8rpx; }
.triage-li-dot { width: 8rpx; height: 8rpx; margin-top: 14rpx; flex: none; border-radius: 50%; background: var(--warn); }
.triage-li-text { flex: 1; color: var(--ink-2); font-size: 24rpx; line-height: 1.65; }
.triage-block { margin-top: 18rpx; }
.triage-block-title { display: block; color: var(--ink-1); font-size: 25rpx; font-weight: 650; }
.triage-block-body { display: block; margin-top: 6rpx; color: var(--ink-2); font-size: 24rpx; line-height: 1.7; }
.triage-check { display: flex; align-items: flex-start; gap: 12rpx; margin-top: 10rpx; }
.triage-box { display: flex; align-items: center; justify-content: center; width: 32rpx; height: 32rpx; margin-top: 4rpx; flex: none; background: var(--surface); border: 2rpx solid var(--line); border-radius: 8rpx; }
.triage-box.checked { background: var(--primary); border-color: var(--primary); }
.triage-tick { width: 14rpx; height: 8rpx; border-left: 3rpx solid var(--on-primary); border-bottom: 3rpx solid var(--on-primary); transform: rotate(-45deg) translateY(-2rpx); }
.triage-check-text { flex: 1; color: var(--ink-2); font-size: 24rpx; line-height: 1.65; }
.triage-alert { margin-top: 20rpx; padding: 18rpx; background: var(--danger-soft); border: 1rpx solid var(--danger); border-radius: var(--r-inner); }
.triage-alert-title { display: block; color: var(--danger); font-size: 25rpx; font-weight: 700; line-height: 1.6; }
.triage-alert-row { display: flex; align-items: flex-start; gap: 10rpx; margin-top: 10rpx; }
.triage-alert-dot { width: 10rpx; height: 10rpx; margin-top: 13rpx; flex: none; background: var(--danger); transform: rotate(45deg); }
.triage-alert-text { flex: 1; color: var(--ink-1); font-size: 25rpx; font-weight: 650; line-height: 1.65; }
.triage-contra { margin-top: 14rpx; padding: 18rpx; background: var(--surface); border: 1rpx solid var(--warn); border-radius: var(--r-inner); }
.triage-contra-title { display: block; color: var(--warn); font-size: 25rpx; font-weight: 700; line-height: 1.6; }
.triage-contra-row { display: flex; align-items: flex-start; gap: 10rpx; margin-top: 8rpx; }
.triage-contra-dot { width: 10rpx; height: 10rpx; margin-top: 13rpx; flex: none; border-radius: 50%; background: var(--warn); }
.triage-contra-text { flex: 1; color: var(--ink-2); font-size: 24rpx; line-height: 1.65; }
.triage-night { margin-top: 14rpx; padding: 16rpx; background: var(--info-soft); border-radius: var(--r-inner); }
.triage-night-title { display: block; color: var(--info); font-size: 23rpx; font-weight: 650; }
.triage-night-copy { display: block; margin-top: 6rpx; color: var(--ink-2); font-size: 23rpx; line-height: 1.65; }
.triage-disclaimer { margin-top: 16rpx; }
.triage-disclaimer-title { display: block; color: var(--ink-3); font-size: 22rpx; }
.triage-disclaimer-line { display: block; margin-top: 4rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.triage-foot { display: flex; align-items: center; justify-content: space-between; gap: 14rpx; margin-top: 18rpx; }
.triage-rules { flex: 1; color: var(--ink-3); font-size: 21rpx; line-height: 1.5; }
.triage-referral { flex: none; margin: 0; padding: 10rpx 24rpx; color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 23rpx; line-height: 1.4; }

.photo-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 110; display: flex; align-items: flex-end; background: rgba(46, 51, 46, .5); }
.photo-sheet { display: flex; flex-direction: column; width: 100%; max-height: 88vh; padding-bottom: env(safe-area-inset-bottom); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; box-sizing: border-box; }
.photo-head { display: flex; align-items: center; justify-content: space-between; padding: 26rpx 28rpx 12rpx; }
.photo-title { color: var(--ink-1); font-size: 31rpx; font-weight: 650; }
.photo-close { margin: 0; padding: 4rpx 0; color: var(--ink-3); background: transparent; border: 0; font-size: 25rpx; line-height: 1.4; }
.photo-scroll { height: 56vh; padding: 0 28rpx; box-sizing: border-box; }
.photo-loading { padding: 30rpx 0; }
.photo-error { display: flex; flex-direction: column; gap: 18rpx; padding: 30rpx 0; }
.photo-error-copy { color: var(--danger); font-size: 25rpx; line-height: 1.6; }
.photo-retry { align-self: flex-start; margin: 0; padding: 8rpx 26rpx; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 24rpx; line-height: 1.5; }
.photo-section-title { display: block; margin-top: 16rpx; color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.photo-privacy { display: block; margin-top: 8rpx; padding: 16rpx 18rpx; color: var(--ink-2); background: var(--info-soft); border-radius: var(--r-inner); font-size: 24rpx; line-height: 1.7; }
.photo-degrade { display: block; margin-top: 10rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.scene-row { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 12rpx; }
.scene-chip { padding: 10rpx 22rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-control); }
.scene-chip.active { background: var(--primary-soft); border-color: var(--primary); }
.scene-label { color: var(--ink-2); font-size: 24rpx; }
.scene-chip.active .scene-label { color: var(--primary-press); font-weight: 650; }
.scene-guide { display: block; margin-top: 12rpx; color: var(--ink-2); font-size: 24rpx; line-height: 1.7; }
.photo-actions { display: flex; gap: 16rpx; margin-top: 20rpx; }
.photo-pick { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 80rpx; margin: 0; color: var(--primary-press); background: var(--surface-warm); border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 26rpx; }
.photo-count { display: block; margin-top: 16rpx; color: var(--ink-3); font-size: 23rpx; }
.thumb-row { display: flex; flex-wrap: wrap; gap: 16rpx; margin-top: 14rpx; }
.thumb { position: relative; width: 180rpx; }
.thumb-img { width: 180rpx; height: 180rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); }
.thumb-del { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 56rpx; margin: 8rpx 0 0; padding: 0; color: var(--danger); background: transparent; border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 22rpx; }
.photo-ttl { display: block; margin: 18rpx 0 20rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.photo-foot { padding: 16rpx 28rpx 24rpx; border-top: 1px solid var(--line); }
.photo-submit { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 88rpx; margin: 0; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 28rpx; font-weight: 650; }
.photo-submit.disabled { opacity: .5; }

.blocked-ai { display: flex; align-items: center; justify-content: center; gap: 10rpx; margin-top: 18rpx; }
.blocked-ai-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: var(--info); }
.blocked-ai-text { color: var(--ink-2); font-size: 22rpx; }
</style>

import type { DailyKnowledgeView, KnowledgeEntryView } from '../api'

/**
 * 每日一则小知识的取用与降级服务。
 *
 * 服务端负责「按北京时间日期从知识库稳定选取」；客户端负责：
 * 1. 同一天内优先复用本地缓存，避免重复请求与内容漂移；
 * 2. 请求失败或知识库为空时，按日期从内置通用提示中稳定取一条；
 * 3. 降级内容与正常内容共用同一套卡片字段，页面无需分支渲染。
 */

const CACHE_KEY = 'jiaban_daily_knowledge'
const CN_OFFSET_HOURS = 8

/** 内容来源：daily=当日接口，cache=当日本地缓存，fallback=内置降级提示 */
export type DailyKnowledgeSource = 'daily' | 'cache' | 'fallback'

/** 解析结果（date 为北京时间日期 YYYY-MM-DD） */
export type ResolvedDailyKnowledge = {
  entry: KnowledgeEntryView
  source: DailyKnowledgeSource
  date: string
}

type Storage = {
  getStorageSync(key: string): unknown
  setStorageSync(key: string, value: unknown): void
}

type CacheRecord = {
  checked_date: string
  payload: DailyKnowledgeView
}

/**
 * 内置降级知识：知识库为空 / 接口不可用时按日期轮换展示。
 * 文案只保留通用养育提示，不写诊断、处方或剂量。
 */
export const FALLBACK_KNOWLEDGE: KnowledgeEntryView[] = [
  {
    kb_id: 'fallback_infant_01',
    title: '先看信号，再回应',
    summary: '观察宝宝的眼神、表情、动作和声音，判断需求后再及时回应。',
    content: '观察宝宝的眼神、表情、动作和声音，判断是在表达饥饿、困倦还是需要安抚，再及时、恰当地回应。回应性照护的关键是看见信号并回应。',
    category: 'infant',
    category_label: '母婴',
    topic: '回应性照护',
    stage_label: '0–36 月',
    preconditions: '0–36 月龄健康儿童日常照护；早产儿按矫正月龄观察。',
    source_level: null,
    source_name: '通用养育提示'
  },
  {
    kb_id: 'fallback_toddler_01',
    title: '情绪先被看见，规则才听得进',
    summary: '先命名情绪，再明确边界，最后给出有限选择。',
    content: '先帮孩子命名情绪（「你现在很生气」），再明确边界（「打人不可以」），最后给出有限选择（「先收积木还是先洗手」）。共情不等于让步，规则要稳定一致。',
    category: 'toddler',
    category_label: '幼儿',
    topic: '情绪与管教',
    stage_label: '1–6 岁',
    preconditions: '1–6 岁典型发展儿童；频繁自伤或伤人需咨询专业人士。',
    source_level: null,
    source_name: '通用养育提示'
  },
  {
    kb_id: 'fallback_pet_01',
    title: '给猫一个能躲的地方',
    summary: '哈气、低吼是防御信号，此时需要空间而不是强行抱起。',
    content: '哈气、低吼、飞机耳都是猫的防御信号，表示它感到威胁、需要空间。此时不要强行抱起或惩罚，应移除刺激源、提供躲藏处，等它放松后再互动。',
    category: 'pet',
    category_label: '宠物',
    topic: '行为解读',
    stage_label: null,
    preconditions: '家养猫日常互动；若伴随拒食超过 24 小时或呼吸异常请就医。',
    source_level: null,
    source_name: '通用养育提示'
  },
  {
    kb_id: 'fallback_family_01',
    title: '接触宠物后先洗手',
    summary: '用肥皂和清水洗手，饭前也要洗，宠物粪便及时清理。',
    content: '接触宠物、清理粪便或户外活动后，用肥皂和清水洗手，饭前也要洗。宠物粪便及时清理，沙坑不用时加盖，教育孩子不食土、不把玩具放嘴里。',
    category: 'family',
    category_label: '家庭共处',
    topic: '家庭卫生',
    stage_label: null,
    preconditions: '所有养宠家庭；儿童、孕妇和免疫低下人群重点执行。',
    source_level: null,
    source_name: '通用养育提示'
  }
]

/**
 * 生成北京时间日期戳（YYYY-MM-DD）。
 *
 * @param now 当前时间，默认取系统时间
 * @returns 北京时间口径的日期字符串
 */
export function localDateStamp(now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + CN_OFFSET_HOURS * 3600 * 1000)
  return shifted.toISOString().slice(0, 10)
}

/**
 * 把日期戳转换为自 epoch 起的天数，用于稳定轮换。
 *
 * @param dateStamp YYYY-MM-DD 日期字符串
 * @returns 整数天数（非法日期返回 0）
 */
export function dayNumber(dateStamp: string): number {
  const parts = dateStamp.split('-').map(Number)
  if (parts.length !== 3 || parts.some((value) => !Number.isFinite(value))) return 0
  return Math.floor(Date.UTC(parts[0], parts[1] - 1, parts[2]) / 86400000)
}

/**
 * 按日期从内置提示中稳定选取一条。
 *
 * @param dateStamp YYYY-MM-DD 日期字符串
 * @returns 当日降级知识条目
 */
export function pickFallback(dateStamp: string): KnowledgeEntryView {
  const index = ((dayNumber(dateStamp) % FALLBACK_KNOWLEDGE.length) + FALLBACK_KNOWLEDGE.length) % FALLBACK_KNOWLEDGE.length
  return FALLBACK_KNOWLEDGE[index]
}

/**
 * 把日期戳格式化为首页展示用的「X月X日」。
 *
 * @param dateStamp YYYY-MM-DD 日期字符串
 * @returns 中文月日文案；非法格式返回空串
 */
export function formatKnowledgeDate(dateStamp: string): string {
  const [, month, day] = dateStamp.split('-').map(Number)
  if (!month || !day) return ''
  return `${month}月${day}日`
}

/**
 * 读取本地缓存（仅接受结构完整的记录）。
 *
 * @param storage 本地存储适配器
 * @returns 缓存记录；无缓存或结构损坏时返回 null
 */
function readCache(storage: Storage): CacheRecord | null {
  try {
    const raw = storage.getStorageSync(CACHE_KEY)
    if (!raw || typeof raw !== 'object') return null
    const record = raw as CacheRecord
    if (typeof record.checked_date !== 'string') return null
    if (!record.payload || typeof record.payload !== 'object') return null
    if (!record.payload.entry || typeof record.payload.entry.kb_id !== 'string') return null
    return record
  } catch {
    // 本地存储不可用时按「无缓存」处理，继续走接口或内置提示
    return null
  }
}

/**
 * 写入当日缓存（失败不阻塞展示）。
 *
 * @param storage 本地存储适配器
 * @param record 缓存记录
 */
function writeCache(storage: Storage, record: CacheRecord): void {
  try {
    storage.setStorageSync(CACHE_KEY, record)
  } catch {
    // 本地缓存失败只影响下次启动的稳定性，不影响本次展示
  }
}

/**
 * 解析当日小知识：当日缓存 → 接口 → 内置提示。
 *
 * @param options.storage 本地存储适配器（uni.getStorageSync / setStorageSync）
 * @param options.load 拉取每日小知识的接口函数
 * @param options.todayStamp 可注入的「今天」日期戳（测试用）
 * @returns 可用于卡片渲染的知识条目与来源标记
 */
export async function resolveDailyKnowledge(options: {
  storage: Storage
  load: () => Promise<DailyKnowledgeView>
  todayStamp?: () => string
}): Promise<ResolvedDailyKnowledge> {
  const today = (options.todayStamp || localDateStamp)()
  const cached = readCache(options.storage)

  // 当日已成功取过：直接复用，保证同一天内内容一致，也减少一次请求
  if (cached && cached.checked_date === today && cached.payload.entry) {
    return { entry: cached.payload.entry, source: 'cache', date: cached.payload.date }
  }

  try {
    const payload = await options.load()
    if (payload.entry) {
      writeCache(options.storage, { checked_date: today, payload })
      return { entry: payload.entry, source: 'daily', date: payload.date }
    }
  } catch {
    // 网络异常或服务端异常统一进入降级分支
  }

  // 当日缓存仍可用时优先复用（例如首次请求失败但此前已成功）
  if (cached && cached.checked_date === today && cached.payload.entry) {
    return { entry: cached.payload.entry, source: 'cache', date: cached.payload.date }
  }

  // 知识库为空或加载失败：展示内置通用提示，并保证同一天内稳定
  return { entry: pickFallback(today), source: 'fallback', date: today }
}

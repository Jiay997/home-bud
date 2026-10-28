const riskLabels: Record<string, string> = {
  none: '未发现明显风险',
  low: '低风险提示',
  mid: '需要留意',
  medium: '需要留意',
  high: '较高风险提示'
}

const sectionLabels: Record<string, string> = {
  child: '育儿侧建议',
  pet: '宠物侧建议',
  family: '家庭建议',
  safety: '安全提示'
}

const degradedLabels: Record<string, string> = {
  agent_failed: '本次部分内容未能生成',
  safety_failed: '安全提示未能生成，本页暂不展示建议内容'
}

const entryTitles: Record<string, string> = {
  child: '育儿问答 · 0-6 岁',
  pet: '宠物问答 · 猫狗',
  family: '家庭综合问答'
}

const entryLabels: Record<string, string> = {
  child: '育儿问答',
  pet: '宠物问答',
  family: '家庭综合问答'
}

const entryPlaceholders: Record<string, string> = {
  child: '描述宝宝的具体情况，越具体越好',
  pet: '描述宠物的具体表现，越具体越好',
  family: '描述家中孩子与宠物相处的情况'
}

const conflictFallback = '育儿与宠物侧建议存在差异，请结合实际谨慎采纳'

export function qaRiskLabel(value: unknown) {
  const raw = String(value || '').trim()
  return riskLabels[raw.toLowerCase()] || (/[A-Za-z]/.test(raw) ? '安全提醒' : raw || '安全提醒')
}

export function qaSectionTitle(section: { section_key?: unknown; title?: unknown }) {
  const title = String(section.title || '').trim()
  if (title && !/[A-Za-z]/.test(title)) return title

  const key = String(section.section_key || '').trim().toLowerCase()
  return sectionLabels[key] || '观察建议'
}

// 降级原因以下发英文码（agent_failed/safety_failed）为准，模板禁止直出英文
export function qaDegradedLabel(value: unknown) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  return degradedLabels[raw] || (/[A-Za-z]/.test(raw) ? '本次回答有部分内容未能生成' : raw)
}

export function isSafetyDegrade(value: unknown) {
  return String(value || '').toLowerCase().includes('safety')
}

export function qaConflictLabel(value: unknown) {
  const raw = String(value || '').trim()
  return raw && !/[A-Za-z]/.test(raw) ? raw : conflictFallback
}

export function qaEntryTitle(entry: unknown) {
  return entryTitles[String(entry || '').trim()] || entryTitles.child
}

export function qaEntryLabel(entry: unknown) {
  return entryLabels[String(entry || '').trim()] || entryLabels.child
}

export function qaEntryInputPlaceholder(entry: unknown) {
  return entryPlaceholders[String(entry || '').trim()] || entryPlaceholders.child
}

// ---- V3.1 合规要素文案（RQ-01 标识 / RQ-07 信任条 / RQ-06 档位） ----

// text_id → 文案映射：服务端只下发 text_id，前端不得自造标识文案（AC-RQ01-1）
const aiLabelTexts: Record<string, string> = {
  AI_GEN_LABEL_V1: '内容由 AI 生成，仅供参考，不构成诊疗建议'
}

// text_id 未登记时的兜底（禁止空标识页面，AC-RQ01-4）
const aiLabelFallback = '内容由 AI 生成，仅供参考'

// 信任条要素中文名：缺失要素按名展示「信息待补」，不静默隐藏（AC-RQ07-6）
const trustElementLabels: Record<string, string> = {
  ai_label: '生成标识',
  disclaimer: '免责说明',
  age_adaptation: '月龄适配',
  source_level: '来源等级',
  triage_badge: '档位徽标',
  contraindications: '禁忌项',
  deterministic_scan: '结论表述自检',
  anthropomorphic_scan: '表述口径自检',
  crisis_channel: '危机渠道',
  share_export_label: '分享导出标识'
}

const triageTones: Record<string, string> = {
  danger: 'danger',
  warning: 'warn',
  success: 'ok',
  neutral: 'neutral'
}

export function qaAiLabelText(label: { text_id?: unknown; fallback_text?: unknown } | null | undefined) {
  const textId = String(label?.text_id || '').trim()
  const mapped = aiLabelTexts[textId]
  if (mapped) return mapped
  const fallback = String(label?.fallback_text || '').trim()
  return fallback && !/[A-Za-z]/.test(fallback) ? fallback : aiLabelFallback
}

export function qaTrustElementLabel(key: unknown) {
  return trustElementLabels[String(key || '').trim()] || '其他要素'
}

// 档位语义色：红=立即就医（danger）/ 黄=尽快评估（warn）/ 绿=居家观察（ok）
export function qaTriageTone(levelColor: unknown) {
  return triageTones[String(levelColor || '').trim()] || 'neutral'
}


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

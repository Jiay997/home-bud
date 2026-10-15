import test from 'node:test'
import assert from 'node:assert/strict'
import { userFacingMessage } from '../src/services/user-message.ts'
import {
  isSafetyDegrade,
  qaConflictLabel,
  qaDegradedLabel,
  qaEntryTitle,
  qaRiskLabel,
  qaSectionTitle
} from '../src/services/qa-copy.ts'

test('technical English errors fall back to concise Chinese recovery copy', () => {
  assert.equal(userFacingMessage(new Error('request:fail timeout'), '连接失败，请稍后重试。'), '连接失败，请稍后重试。')
})

test('Chinese service errors are preserved', () => {
  assert.equal(userFacingMessage(new Error('账号暂不可用'), '连接失败，请稍后重试。'), '账号暂不可用')
})

test('known risk codes are displayed in Chinese', () => {
  assert.equal(qaRiskLabel('low'), '低风险提示')
  assert.equal(qaRiskLabel('high'), '较高风险提示')
})

test('section keys never appear as raw English labels', () => {
  assert.equal(qaSectionTitle({ section_key: 'safety' }), '安全提示')
  assert.equal(qaSectionTitle({ section_key: 'unknown_section' }), '观察建议')
  assert.equal(qaSectionTitle({ section_key: 'child', title: 'Child advice' }), '育儿侧建议')
})

test('degraded reasons map to Chinese copy and safety failures are detected', () => {
  assert.equal(qaDegradedLabel('agent_failed'), '本次部分内容未能生成')
  assert.equal(qaDegradedLabel('unknown_reason'), '本次回答有部分内容未能生成')
  assert.equal(isSafetyDegrade('safety_failed'), true)
  assert.equal(isSafetyDegrade('agent_failed'), false)
  assert.equal(qaConflictLabel('育儿与宠物侧建议存在差异，请结合实际谨慎采纳'), '育儿与宠物侧建议存在差异，请结合实际谨慎采纳')
  assert.equal(qaConflictLabel('conflict detected'), '育儿与宠物侧建议存在差异，请结合实际谨慎采纳')
})

test('entry titles stay Chinese-only for navigation', () => {
  assert.equal(qaEntryTitle('child'), '育儿问答 · 0-6 岁')
  assert.equal(qaEntryTitle('pet'), '宠物问答 · 猫狗')
  assert.equal(qaEntryTitle('family'), '家庭综合问答')
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { layoutLongImage, renderLongImage, wrapText } from '../src/services/image-export.ts'

const measureBySize = (value, font) => value.length * (Number(font.match(/([\d.]+)px/)?.[1]) || 10) * 0.6

test('wrapText breaks long Chinese paragraphs by measured width', () => {
  const lines = wrapText('一二三四五六七八', 30, (value) => value.length * 10)
  assert.deepEqual(lines, ['一二三', '四五六', '七八'])
})

test('wrapText preserves explicit newlines and empty paragraphs', () => {
  const lines = wrapText('第一行\n\n第二行', 100, (value) => value.length * 10)
  assert.deepEqual(lines, ['第一行', '', '第二行'])
})

test('wrapText keeps an over-wide single character as its own line', () => {
  const lines = wrapText('甲乙丙', 5, (value) => value.length * 10)
  assert.deepEqual(lines, ['甲', '乙', '丙'])
})

test('layoutLongImage produces a sized background, title and disclaimer ops', () => {
  const layout = layoutLongImage({
    brand: 'Babe宝伴',
    title: '慢热型',
    meta: '宝宝A · 2026-10-13',
    dimensions: [{ label: '活动水平', band: '偏低' }],
    sections: [{ heading: '类型解读', body: '慢热的孩子需要更多过渡时间。' }],
    disclaimers: ['内容由人工智能生成，仅供参考。', '本结果不构成任何诊断。'],
    badge: '内容由 AI 生成'
  }, { width: 375, measure: measureBySize })

  assert.equal(layout.width, 375)
  assert.ok(layout.height > 200)
  assert.equal(layout.ops[0].kind, 'rect')
  assert.equal(layout.ops[0].height, layout.height)
  const texts = layout.ops.filter((op) => op.kind === 'text').map((op) => op.text)
  assert.ok(texts.includes('慢热型'))
  assert.ok(texts.some((value) => value.includes('人工智能')))
  assert.ok(layout.ops.some((op) => op.kind === 'rect' && op.radius > 0))
})

test('renderLongImage draws every op and fills the background first', () => {
  const layout = layoutLongImage({
    brand: 'Babe宝伴',
    title: '活跃型',
    meta: '宝宝A',
    dimensions: [],
    sections: [],
    disclaimers: ['仅供参考。'],
    badge: '内容由 AI 生成'
  }, { width: 375, measure: measureBySize })

  const calls = []
  const ctx = {
    fillStyle: '',
    font: '',
    textBaseline: '',
    fillRect: (x, y, width, height) => calls.push(['rect', width, height]),
    fillText: (text) => calls.push(['text', text])
  }
  renderLongImage(ctx, layout)

  assert.equal(calls[0][0], 'rect')
  assert.equal(calls[0][1], 375)
  assert.equal(calls[0][2], layout.height)
  assert.equal(calls.filter((call) => call[0] === 'text').length, layout.ops.filter((op) => op.kind === 'text').length)
})

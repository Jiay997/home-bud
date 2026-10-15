export interface LongImageDimension {
  label: string
  band: string
}

export interface LongImageSection {
  heading: string
  body: string
}

export interface LongImageDoc {
  brand: string
  title: string
  meta: string
  dimensions: LongImageDimension[]
  sections: LongImageSection[]
  disclaimers: string[]
  badge: string
}

export interface TextOp {
  kind: 'text'
  x: number
  y: number
  text: string
  font: string
  color: string
}

export interface RectOp {
  kind: 'rect'
  x: number
  y: number
  width: number
  height: number
  color: string
  radius: number
}

export type DrawOp = TextOp | RectOp

export interface LongImageLayout {
  width: number
  height: number
  ops: DrawOp[]
}

// 按字符贪心折行：中文逐字断行，显式换行保留，单字符超宽兜底独立成行
export function wrapText(text: string, maxWidth: number, measure: (value: string) => number): string[] {
  const lines: string[] = []
  for (const paragraph of String(text || '').split('\n')) {
    if (!paragraph) {
      lines.push('')
      continue
    }
    let line = ''
    for (const char of paragraph) {
      const next = line + char
      if (line && measure(next) > maxWidth) {
        lines.push(line)
        line = char
      } else {
        line = next
      }
    }
    lines.push(line)
  }
  return lines
}

// 长图 canvas 无 Markdown 渲染能力：导出前去掉渲染器支持的语法标记
// （标题/列表/加粗/斜体/分隔线/表格，与 MiniMarkdown 语法子集一致）
export function stripMarkdown(text: string): string {
  return String(text || '')
    .replace(/^\s{0,3}#{1,3}\s+/gm, '')
    .replace(/^\s*[-*]\s+/gm, '· ')
    .replace(/^\s*\|?[\s:|-]+\|?\s*$/gm, (match) => (match.includes('|') ? '' : match))
    .replace(/\*\*([^*\n]+)\*\*/g, '$1')
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1$2')
    .replace(/^\s*-{3,}\s*$/gm, '')
    .replace(/\s*\|\s*/g, '  ')
}

const COLORS = {
  background: '#FFFFFF',
  band: '#F5F2EC',
  ink: '#2E332E',
  inkSoft: '#5B625B',
  muted: '#8A9088',
  primary: '#7C9082',
  primarySoft: '#E4EBE3',
  line: '#E3E2DE'
}

const FONTS = {
  brand: '600 15px "PingFang SC", sans-serif',
  title: '700 26px "PingFang SC", sans-serif',
  meta: '12px "PingFang SC", sans-serif',
  heading: '600 15px "PingFang SC", sans-serif',
  body: '13.5px "PingFang SC", sans-serif',
  chip: '12px "PingFang SC", sans-serif',
  badge: '11px "PingFang SC", sans-serif',
  disclaimer: '11px "PingFang SC", sans-serif'
}

const PADDING = 22
const BODY_LINE_HEIGHT = 21
const BODY_FONT_SIZE = 13.5

export function layoutLongImage(doc: LongImageDoc, options: {
  width?: number
  measure: (value: string, font: string) => number
}): LongImageLayout {
  const width = options.width || 375
  const contentWidth = width - PADDING * 2
  const ops: DrawOp[] = [{ kind: 'rect', x: 0, y: 0, width, height: 1, color: COLORS.background, radius: 0 }]
  let y = PADDING + 18

  const badgeWidth = options.measure(doc.badge, FONTS.badge) + 20
  ops.push({ kind: 'text', x: PADDING, y, text: doc.brand, font: FONTS.brand, color: COLORS.ink })
  ops.push({ kind: 'rect', x: width - PADDING - badgeWidth, y: y - 14, width: badgeWidth, height: 20, color: COLORS.primarySoft, radius: 10 })
  ops.push({ kind: 'text', x: width - PADDING - badgeWidth + 10, y: y - 10, text: doc.badge, font: FONTS.badge, color: COLORS.inkSoft })
  y += 30

  for (const line of wrapText(doc.title, contentWidth, (value) => options.measure(value, FONTS.title))) {
    ops.push({ kind: 'text', x: PADDING, y, text: line, font: FONTS.title, color: COLORS.ink })
    y += 34
  }
  y += 2

  for (const line of wrapText(doc.meta, contentWidth, (value) => options.measure(value, FONTS.meta))) {
    ops.push({ kind: 'text', x: PADDING, y, text: line, font: FONTS.meta, color: COLORS.muted })
    y += 18
  }
  y += 14

  if (doc.dimensions.length) {
    const bandHeight = doc.dimensions.length * 30 + 12
    ops.push({ kind: 'rect', x: PADDING, y: y - 10, width: contentWidth, height: bandHeight, color: COLORS.band, radius: 12 })
    let bandY = y + 6
    for (const dimension of doc.dimensions) {
      ops.push({ kind: 'text', x: PADDING + 14, y: bandY, text: dimension.label, font: FONTS.chip, color: COLORS.inkSoft })
      const chipWidth = options.measure(dimension.band, FONTS.chip) + 18
      ops.push({ kind: 'rect', x: PADDING + contentWidth - 14 - chipWidth, y: bandY - 7, width: chipWidth, height: 22, color: COLORS.primarySoft, radius: 11 })
      ops.push({ kind: 'text', x: PADDING + contentWidth - 14 - chipWidth + 9, y: bandY - 2, text: dimension.band, font: FONTS.chip, color: COLORS.primary })
      bandY += 30
    }
    y += bandHeight + 16
  }

  for (const section of doc.sections) {
    y += 6
    for (const line of wrapText(section.heading, contentWidth, (value) => options.measure(value, FONTS.heading))) {
      ops.push({ kind: 'text', x: PADDING, y, text: line, font: FONTS.heading, color: COLORS.primary })
      y += 24
    }
    y += 4
    for (const line of wrapText(section.body, contentWidth, (value) => options.measure(value, FONTS.body))) {
      ops.push({ kind: 'text', x: PADDING, y, text: line, font: FONTS.body, color: COLORS.inkSoft })
      y += BODY_LINE_HEIGHT
    }
    y += 14
    ops.push({ kind: 'rect', x: PADDING, y: y - 8, width: contentWidth, height: 1, color: COLORS.line, radius: 0 })
    y += 10
  }

  y += 8
  for (const disclaimer of doc.disclaimers) {
    for (const line of wrapText(disclaimer, contentWidth, (value) => options.measure(value, FONTS.disclaimer))) {
      ops.push({ kind: 'text', x: PADDING, y, text: line, font: FONTS.disclaimer, color: COLORS.muted })
      y += 16
    }
    y += 6
  }

  const height = Math.ceil(y + PADDING - 10)
  ops[0] = { kind: 'rect', x: 0, y: 0, width, height, color: COLORS.background, radius: 0 }
  return { width, height, ops }
}

function roundRectPath(ctx: any, x: number, y: number, width: number, height: number, radius: number) {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2))
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + width, y, x + width, y + height, r)
  ctx.arcTo(x + width, y + height, x, y + height, r)
  ctx.arcTo(x, y + height, x, y, r)
  ctx.arcTo(x, y, x + width, y, r)
  ctx.closePath()
}

export interface LongImageCanvasContext {
  fillStyle: string
  font: string
  textBaseline: string
  fillRect(x: number, y: number, width: number, height: number): void
  fillText(text: string, x: number, y: number): void
  beginPath?: () => void
  arcTo?: (...values: number[]) => void
  moveTo?: (...values: number[]) => void
  closePath?: () => void
  fill?: () => void
}

export function renderLongImage(ctx: LongImageCanvasContext, layout: LongImageLayout) {
  ctx.textBaseline = 'top'
  for (const op of layout.ops) {
    if (op.kind === 'rect') {
      ctx.fillStyle = op.color
      const supportsPath = op.radius > 0 &&
        typeof ctx.beginPath === 'function' && typeof ctx.arcTo === 'function' && typeof ctx.fill === 'function'
      if (supportsPath) {
        roundRectPath(ctx, op.x, op.y, op.width, op.height, op.radius)
        ctx.fill?.()
      } else {
        ctx.fillRect(op.x, op.y, op.width, op.height)
      }
      continue
    }
    ctx.font = op.font
    ctx.fillStyle = op.color
    ctx.fillText(op.text, op.x, op.y)
  }
}

<template>
  <view class="md-root">
    <template v-for="(blk, bi) in blocks" :key="bi">
      <view v-if="blk.type === 'h'" class="md-h">
        <text class="md-h-text"><text v-for="(sg, si) in blk.segs" :key="si" :class="segClass(sg)">{{ sg.s }}</text></text>
      </view>
      <view v-else-if="blk.type === 'p'" class="md-p">
        <text class="md-p-text"><text v-for="(sg, si) in blk.segs" :key="si" :class="segClass(sg)">{{ sg.s }}</text></text>
      </view>
      <view v-else-if="blk.type === 'ul'" class="md-list">
        <view v-for="(li, liIdx) in blk.items" :key="liIdx" class="md-li">
          <view class="md-dot" />
          <text class="md-li-text"><text v-for="(sg, si) in li" :key="si" :class="segClass(sg)">{{ sg.s }}</text></text>
        </view>
      </view>
      <view v-else-if="blk.type === 'ol'" class="md-list">
        <view v-for="(li, liIdx) in blk.items" :key="liIdx" class="md-li">
          <text class="md-ol-num">{{ liIdx + 1 }}.</text>
          <text class="md-li-text"><text v-for="(sg, si) in li" :key="si" :class="segClass(sg)">{{ sg.s }}</text></text>
        </view>
      </view>
      <view v-else-if="blk.type === 'table'" class="md-table">
        <view class="md-tr md-tr-head">
          <text v-for="(cell, ci) in blk.header" :key="ci" class="md-th"><text v-for="(sg, si) in cell" :key="si" :class="segClass(sg)">{{ sg.s }}</text></text>
        </view>
        <view v-for="(row, ri) in blk.rows" :key="ri" class="md-tr">
          <text v-for="(cell, ci) in row" :key="ci" class="md-td"><text v-for="(sg, si) in cell" :key="si" :class="segClass(sg)">{{ sg.s }}</text></text>
        </view>
      </view>
      <view v-else class="md-hr" />
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// MiniMarkdown：AI 回答/笔记共用的轻量渲染器（甲方需求 2026-10-15 可读性）。
// 仅支持与后端排版约定一致的语法子集：## 标题、- / 1. 列表、**加粗**、
// *斜体*、--- 分隔线、| 表格（首行表头 + 第二行 |---| 分隔）。
// 纯函数渲染：props.content → 块级解析 → view 树；无内部状态，
// 流式 partial 每个 chunk 全量重算不残留（表格未完整时整段降级为段落）。

interface Seg {
  t: 'text' | 'b' | 'i'
  s: string
}

type Block =
  | { type: 'h'; segs: Seg[] }
  | { type: 'p'; segs: Seg[] }
  | { type: 'ul'; items: Seg[][] }
  | { type: 'ol'; items: Seg[][] }
  | { type: 'table'; header: Seg[][]; rows: Seg[][][] }
  | { type: 'hr' }

const props = defineProps<{ content: string }>()

function parseInline(src: string): Seg[] {
  const segs: Seg[] = []
  const re = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    if (m.index > last) segs.push({ t: 'text', s: src.slice(last, m.index) })
    const tok = m[0]
    if (tok.startsWith('**')) segs.push({ t: 'b', s: tok.slice(2, -2) })
    else segs.push({ t: 'i', s: tok.slice(1, -1) })
    last = m.index + tok.length
  }
  if (last < src.length) segs.push({ t: 'text', s: src.slice(last) })
  return segs
}

function isTableSeparator(line: string): boolean {
  return line.includes('-') && /^\|?[\s:|-]+\|?$/.test(line)
}

function splitRow(line: string): Seg[][] {
  return line
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => parseInline(cell.trim()))
}

function parseBlocks(src: string): Block[] {
  const lines = String(src || '').replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let para: string[] = []
  const flushPara = () => {
    if (para.length) {
      blocks.push({ type: 'p', segs: parseInline(para.join('\n')) })
      para = []
    }
  }
  let i = 0
  while (i < lines.length) {
    const line = lines[i].trim()
    if (!line) {
      flushPara()
      i += 1
      continue
    }
    const heading = /^#{1,3}\s+(.*)$/.exec(line)
    if (heading) {
      flushPara()
      blocks.push({ type: 'h', segs: parseInline(heading[1]) })
      i += 1
      continue
    }
    if (/^\|.+\|?\s*$/.test(line) || (line.startsWith('|') && line.endsWith('|'))) {
      const buf: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        buf.push(lines[i].trim())
        i += 1
      }
      if (buf.length >= 2 && isTableSeparator(buf[1])) {
        blocks.push({ type: 'table', header: splitRow(buf[0]), rows: buf.slice(2).map(splitRow) })
      } else {
        // 表格段不完整（流式截断）→ 降级为段落，分隔行到达后自动重渲为表格
        flushPara()
        blocks.push({ type: 'p', segs: parseInline(buf.join('\n')) })
      }
      continue
    }
    if (/^(-{3,}|\*{3,})$/.test(line)) {
      flushPara()
      blocks.push({ type: 'hr' })
      i += 1
      continue
    }
    const ul = /^[-*]\s+(.*)$/.exec(line)
    if (ul) {
      flushPara()
      const items: Seg[][] = [parseInline(ul[1])]
      i += 1
      while (i < lines.length) {
        const next = /^\s*[-*]\s+(.*)$/.exec(lines[i])
        if (!next) break
        items.push(parseInline(next[1]))
        i += 1
      }
      blocks.push({ type: 'ul', items })
      continue
    }
    const ol = /^\d{1,3}[.、)]\s*(.*)$/.exec(line)
    if (ol) {
      flushPara()
      const items: Seg[][] = [parseInline(ol[1])]
      i += 1
      while (i < lines.length) {
        const next = /^\s*\d{1,3}[.、)]\s*(.*)$/.exec(lines[i])
        if (!next) break
        items.push(parseInline(next[1]))
        i += 1
      }
      blocks.push({ type: 'ol', items })
      continue
    }
    para.push(line)
    i += 1
  }
  flushPara()
  return blocks
}

const blocks = computed(() => parseBlocks(props.content))

function segClass(sg: Seg): string {
  if (sg.t === 'b') return 'md-b'
  if (sg.t === 'i') return 'md-i'
  return ''
}
</script>

<style scoped>
.md-root { display: block; }
.md-h { margin-top: 14rpx; }
.md-h:first-child { margin-top: 0; }
.md-h-text { display: block; color: var(--ink-1, #2E332E); font-size: 30rpx; font-weight: 700; line-height: 1.6; }
.md-p { margin-top: 8rpx; }
.md-p-text { display: block; color: var(--ink-2, #5B625B); font-size: 30rpx; line-height: 1.75; white-space: pre-wrap; word-break: break-all; }
.md-list { margin-top: 8rpx; }
.md-li { display: flex; flex-direction: row; margin-top: 6rpx; }
.md-li:first-child { margin-top: 0; }
.md-dot { width: 10rpx; height: 10rpx; border-radius: 5rpx; background: var(--primary, #7C9082); margin-top: 19rpx; margin-right: 14rpx; flex-shrink: 0; }
.md-ol-num { color: var(--primary, #7C9082); font-size: 30rpx; font-weight: 650; margin-right: 10rpx; flex-shrink: 0; line-height: 1.75; }
.md-li-text { flex: 1; color: var(--ink-2, #5B625B); font-size: 30rpx; line-height: 1.75; white-space: pre-wrap; word-break: break-all; }
.md-table { margin-top: 12rpx; border: 2rpx solid #E3E2DE; border-radius: 12rpx; overflow: hidden; }
.md-tr { display: flex; flex-direction: row; border-top: 2rpx solid #E3E2DE; }
.md-tr-head { border-top: none; background: #F2F1EC; }
.md-th, .md-td { flex: 1; padding: 14rpx 16rpx; font-size: 26rpx; line-height: 1.6; color: var(--ink-2, #5B625B); word-break: break-all; }
.md-th { font-weight: 650; color: var(--ink-1, #2E332E); }
.md-hr { margin-top: 14rpx; height: 2rpx; background: #E3E2DE; }
.md-b { font-weight: 700; color: var(--ink-1, #2E332E); }
.md-i { font-style: italic; }
</style>

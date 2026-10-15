export interface SseFrame {
  event: string
  data: string
}

// SSE 帧解析：跨块半帧在缓冲区续接，`\r\n` 归一化为 `\n`，注释行忽略。
export function createSseParser({ onFrame }: { onFrame: (frame: SseFrame) => void }) {
  let buffer = ''
  return {
    push(chunk: string) {
      buffer += chunk.replace(/\r\n/g, '\n')
      let index = buffer.indexOf('\n\n')
      while (index !== -1) {
        const raw = buffer.slice(0, index)
        buffer = buffer.slice(index + 2)
        const frame = parseFrame(raw)
        if (frame) onFrame(frame)
        index = buffer.indexOf('\n\n')
      }
    },
    reset() {
      buffer = ''
    }
  }
}

function parseFrame(raw: string): SseFrame | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') dataLines.push(value)
  }
  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}

// 微信端分块为 ArrayBuffer，多字节 UTF-8 字符可能跨块：不完整尾字节进入 carry 续接。
export function decodeUtf8Chunk(
  carry: number[],
  chunk: ArrayBuffer | Uint8Array | number[]
): { text: string; carry: number[] } {
  const incoming = chunk instanceof Uint8Array
    ? chunk
    : chunk instanceof ArrayBuffer
      ? new Uint8Array(chunk)
      : Uint8Array.from(chunk)
  const merged = carry.length ? Uint8Array.from([...carry, ...incoming]) : incoming
  let text = ''
  let index = 0
  while (index < merged.length) {
    const byte = merged[index]
    let size = 0
    if (byte < 0x80) size = 1
    else if ((byte & 0xe0) === 0xc0) size = 2
    else if ((byte & 0xf0) === 0xe0) size = 3
    else if ((byte & 0xf8) === 0xf0) size = 4
    else {
      index += 1
      continue
    }
    if (index + size > merged.length) break
    let code: number
    if (size === 1) code = byte
    else if (size === 2) code = ((byte & 0x1f) << 6) | (merged[index + 1] & 0x3f)
    else if (size === 3) code = ((byte & 0x0f) << 12) | ((merged[index + 1] & 0x3f) << 6) | (merged[index + 2] & 0x3f)
    else code = ((byte & 0x07) << 18) | ((merged[index + 1] & 0x3f) << 12) | ((merged[index + 2] & 0x3f) << 6) | (merged[index + 3] & 0x3f)
    text += String.fromCodePoint(code)
    index += size
  }
  return { text, carry: Array.from(merged.slice(index)) }
}

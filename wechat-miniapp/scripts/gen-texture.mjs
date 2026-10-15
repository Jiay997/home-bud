// 生成 C-2「织理质感」纸纹：128×128 透明底稀疏噪点 PNG，输出 base64 到 src/styles/texture.css。
// 固定随机种子，保证输出稳定可复现（重新生成不产生 diff 噪音）。
import { deflateSync } from 'node:zlib'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const SIZE = 128
const SPECK_RATE = 0.07 // 约 7% 像素带噪点
const SEED = 20261013

function mulberry32(seed) {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let value = i
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
    }
    table[i] = value >>> 0
  }
  return table
})()

function crc32(bytes) {
  let value = 0xffffffff
  for (const byte of bytes) value = CRC_TABLE[(value ^ byte) & 0xff] ^ (value >>> 8)
  return (value ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const typeBytes = Buffer.from(type, 'ascii')
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length, 0)
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(Buffer.concat([typeBytes, data])), 0)
  return Buffer.concat([length, typeBytes, data, crc])
}

function buildPng() {
  const random = mulberry32(SEED)
  const raw = Buffer.alloc(SIZE * (SIZE * 4 + 1))
  for (let y = 0; y < SIZE; y += 1) {
    const rowStart = y * (SIZE * 4 + 1)
    raw[rowStart] = 0 // filter: none
    for (let x = 0; x < SIZE; x += 1) {
      if (random() >= SPECK_RATE) continue
      const offset = rowStart + 1 + x * 4
      const shade = 40 + Math.floor(random() * 40)
      raw[offset] = shade
      raw[offset + 1] = shade
      raw[offset + 2] = shade
      raw[offset + 3] = 3 + Math.floor(random() * 10)
    }
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(SIZE, 0)
  ihdr.writeUInt32BE(SIZE, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // color type: RGBA

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0))
  ])
}

const png = buildPng()
const base64 = png.toString('base64')
const outDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'styles')
mkdirSync(outDir, { recursive: true })
const css = `/* 由 scripts/gen-texture.mjs 生成（纸纹噪点层），请勿手改；重新生成：npm run gen:texture */
.tex {
  background-image: url("data:image/png;base64,${base64}");
  background-repeat: repeat;
  background-size: 256rpx 256rpx;
}
`
writeFileSync(join(outDir, 'texture.css'), css, 'utf8')
console.log(`texture.css 已生成：PNG ${png.length} 字节，base64 ${base64.length} 字符`)

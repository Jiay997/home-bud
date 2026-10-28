import test from 'node:test'
import assert from 'node:assert/strict'
import { createSseParser, decodeUtf8Chunk } from '../src/services/sse.ts'

const encoder = new TextEncoder()

test('UTF-8 decoding survives multi-byte characters split across chunks', () => {
  const bytes = encoder.encode('光照')
  const first = decodeUtf8Chunk([], bytes.slice(0, 2))
  assert.equal(first.text, '')
  assert.deepEqual(first.carry, [0xe5, 0x85])

  const second = decodeUtf8Chunk(first.carry, bytes.slice(2))
  assert.equal(second.text, '光照')
  assert.deepEqual(second.carry, [])
})

test('UTF-8 decoding passes through complete ASCII and Chinese chunks', () => {
  const decoded = decodeUtf8Chunk([], encoder.encode('event: 你好\n'))
  assert.equal(decoded.text, 'event: 你好\n')
  assert.deepEqual(decoded.carry, [])
})

test('SSE parser emits complete frames and buffers partial ones', () => {
  const frames = []
  const parser = createSseParser({ onFrame: (frame) => frames.push(frame) })
  parser.push('event: started\ndata: {"a":1}\n\nevent: section_delta\nda')
  assert.deepEqual(frames, [{ event: 'started', data: '{"a":1}' }])

  parser.push('ta: {"b":2}\n\n')
  assert.deepEqual(frames, [
    { event: 'started', data: '{"a":1}' },
    { event: 'section_delta', data: '{"b":2}' }
  ])
})

test('SSE parser handles CRLF frames and ignores comment lines', () => {
  const frames = []
  const parser = createSseParser({ onFrame: (frame) => frames.push(frame) })
  parser.push(': keep-alive\r\nevent: completed\r\ndata: {"status":"done"}\r\n\r\n')
  assert.deepEqual(frames, [{ event: 'completed', data: '{"status":"done"}' }])
})

test('SSE parser joins multi-line data fields and drops frames without data', () => {
  const frames = []
  const parser = createSseParser({ onFrame: (frame) => frames.push(frame) })
  parser.push('event: ping\n\n')
  parser.push('data: line-1\ndata: line-2\n\n')
  assert.deepEqual(frames, [
    { event: 'message', data: 'line-1\nline-2' }
  ])
})

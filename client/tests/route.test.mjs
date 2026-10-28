import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { decodeRouteValue } from '../src/services/route.ts'

function listVueFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? listVueFiles(path) : entry.name.endsWith('.vue') ? [path] : []
  })
}

test('route values decode UTF-8 query parameters', () => {
  assert.equal(decodeRouteValue('%E5%AE%B6%E5%BA%AD'), '家庭')
})

test('route values preserve malformed input instead of breaking page load', () => {
  assert.equal(decodeRouteValue('%E5%AE%B6%'), '%E5%AE%B6%')
})

test('page templates contain no visible English copy', () => {
  const files = listVueFiles(fileURLToPath(new URL('../src', import.meta.url)))
  const findings = files.flatMap((file) => {
    const source = readFileSync(file, 'utf8')
    const template = source.match(/<template>([\s\S]*?)<\/template>/)?.[1] || ''
    const visibleText = template.replace(/\{\{[\s\S]*?\}\}/g, ' ').replace(/<[^>]*>/g, ' ')
    const english = visibleText.match(/[A-Za-z]{2,}(?:[ /-]+[A-Za-z]{2,})*/g) || []
    // 品牌专名「Babe宝伴」中的英文 Babe 属品牌标识，不计入可见英文文案
    return english
      .map((copy) => copy.trim())
      .filter((copy) => copy !== 'Babe')
      .map((copy) => `${file}: ${copy}`)
  })

  assert.deepEqual(findings, [])
})

test('all declared mini-program routes point to existing page files', () => {
  const pagesFile = fileURLToPath(new URL('../src/pages.json', import.meta.url))
  const pages = JSON.parse(readFileSync(pagesFile, 'utf8')).pages.map(({ path }) => path)
  const sourceDirectory = fileURLToPath(new URL('../src', import.meta.url))
  const expected = [
    'pages/index/index',
    'pages/records/index',
    'pages/profiles/index',
    'pages/me/index',
    'pages/qa/index',
    'pages/assessment-intro/index',
    'pages/assessment/index',
    'pages/report/index',
    'pages/member/index',
    'pages/profile-detail/index',
    'pages/profile-album/index',
    'pages/health/index',
    'pages/health/edit',
    'pages/notes/index',
    'pages/notes/edit',
    'pages/privacy-pledge/index',
    'pages/reminders/index',
    'pages/tools/index',
    'pages/topics/index',
    'pages/knowledge/index'
  ]

  assert.deepEqual(pages, expected)
  for (const page of pages) {
    assert.equal(existsSync(join(sourceDirectory, `${page}.vue`)), true, page)
  }
})

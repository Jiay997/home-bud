// 测评作答批量驱动：连续答完 16 题并提交，最终停在报告页。
// 前置：小程序已停在 pages/assessment/index 作答页（由 assessment-intro 的 startOrResume 进入）。
// 用法：node scripts/assess-answer.mjs [--from N]   # N 为起始题号（1-based，默认 1，断点续答用）
import automator from 'miniprogram-automator'
import { execFileSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'walkthrough')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (m) => console.log(`[assess ${new Date().toISOString().slice(11, 19)}] ${m}`)
process.on('unhandledRejection', (e) => { log(`unhandledRejection: ${String(e).slice(0, 200)}`) })
const watchdog = setTimeout(() => { log('WATCHDOG'); process.exit(2) }, 300000)
watchdog.unref?.()

const SCORE_KEYS = { 1: 'e0_1', 2: 'e1_2', 3: 'e2_3', 4: 'e3_4', 5: 'e4_5' }
const NEXT_KEY = 'e6_b2'
// 覆盖不同分值的作答序列（模拟真实用户波动）
const PLAN = [3, 2, 4, 1, 3, 2, 5, 3, 2, 4, 3, 1, 2, 3, 4, 2]

const fromIdx = process.argv.indexOf('--from')
const FROM = fromIdx >= 0 ? Math.max(1, parseInt(process.argv[fromIdx + 1], 10) || 1) : 1

function focusWindow() {
  try {
    execFileSync('python', [resolve(dirname(fileURLToPath(import.meta.url)), 'win-focus.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 30000 })
  } catch { /* ignore */ }
}

const mp = await automator.connect({ wsEndpoint: process.env.MP_WS || 'ws://127.0.0.1:9420' })
log('connected')

async function invoke(key, type, detail) {
  return mp.evaluate((k, t, d) => {
    const pages = getCurrentPages()
    const p = pages[pages.length - 1]
    const fn = p[k]
    if (typeof fn !== 'function') return 'NO_INVOKER:' + k
    fn({ type: t, target: { dataset: {} }, currentTarget: { dataset: {} }, detail: d || {} })
    return 'OK'
  }, key, type, detail || {})
}

async function shot(name) {
  focusWindow()
  await sleep(300)
  await mp.screenshot({ path: resolve(OUT, `${name}.png`) })
  log(`saved ${name}.png`)
}

try {
  for (let i = FROM - 1; i < PLAN.length; i++) {
    const no = i + 1
    const score = PLAN[i]
    const r = await invoke(SCORE_KEYS[score], 'tap', {})
    if (r !== 'OK') { log(`Q${no} option invoke ${r}`); break }
    await sleep(1100)
    const r2 = await invoke(NEXT_KEY, 'tap', {})
    if (r2 !== 'OK') { log(`Q${no} next invoke ${r2}`); break }
    await sleep(900)
    log(`Q${no} answered(${score})`)
    if (no === 3) await shot('t_assess_q3')
    if (no === 16) {
      log('submitted; waiting for report redirect')
      await sleep(4000)
      await shot('t_report_after_submit')
      await sleep(8000)
      await shot('t_report_after_submit_12s')
    }
  }
  const route = await mp.evaluate(() => {
    const pages = getCurrentPages()
    return pages[pages.length - 1].route
  })
  log(`final route: ${route}`)
} catch (e) {
  log(`ERROR: ${e && e.message ? e.message : String(e)}`)
} finally {
  clearTimeout(watchdog)
  try { mp.disconnect() } catch { /* ignore */ }
  process.exit(0)
}

// =====================================================================
// 小程序端测评逐题作答驱动（t2-assess.mjs）
//
// 背景：uni-app 的 invoker 键在 v-for 选项上随题切换重新注册，
//       固定键（e0_1..e4_5）在题号变化后失效 → 需每题实时读取选项键。
// 用法：node scripts/t2-assess.mjs [--start-q N]
// =====================================================================
import automator from 'miniprogram-automator'
import { execFileSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'walkthrough')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (m) => console.log(`[t2-assess ${new Date().toISOString().slice(11, 19)}] ${m}`)
const watchdog = setTimeout(() => { log('WATCHDOG'); process.exit(2) }, 420000)
watchdog.unref?.()

/** 读取当前题页面的关键数据（题号、选项绑定键、上/下一题绑定键）。
 * @returns {Promise<object>} {route, qNo, opts:[{label,key}], prevKey, nextKey}
 */
async function readState(mp) {
  return mp.evaluate(() => {
    const p = getCurrentPages()[getCurrentPages().length - 1]
    const d = p.data || {}
    const opts = Array.isArray(d.v) ? d.v.map((o) => ({ label: o.a, key: o.f })) : []
    const meta = d.l && typeof d.l === 'object' ? d.l : {}
    return { route: p.route, qNo: meta.q_no, opts, prevKey: d.E, nextKey: d.I }
  })
}

/** 触发页面 invoker（真实事件流）。
 * @param {object} mp - automator 连接
 * @param {string} key - invoker 键
 * @returns {Promise<string>} 'OK' 或 NO_INVOKER
 */
async function invoke(mp, key) {
  return mp.evaluate((k) => {
    const p = getCurrentPages()[getCurrentPages().length - 1]
    const fn = p[k]
    if (typeof fn !== 'function') return 'NO_INVOKER:' + k
    fn({ type: 'tap', target: { dataset: {} }, currentTarget: { dataset: {} }, detail: {} })
    return 'OK'
  }, key)
}

/** 置前窗口并截图。
 * @param {object} mp - automator 连接
 * @param {string} name - 文件名（不含扩展名）
 * @returns {Promise<void>}
 */
async function shot(mp, name) {
  try {
    execFileSync(process.env.MP_PY || 'python', [resolve(dirname(fileURLToPath(import.meta.url)), 'win-focus.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 30000 })
  } catch { /* ignore */ }
  await sleep(300)
  await mp.screenshot({ path: resolve(OUT, `${name}.png`) })
  log(`saved ${name}.png`)
}

const mp = await automator.connect({ wsEndpoint: process.env.MP_WS || 'ws://127.0.0.1:9420' })
log('connected')

// 1) 回到第 1 题：连续点“上一题”
for (let i = 0; i < 20; i++) {
  const st = await readState(mp)
  if (st.route !== 'pages/assessment/index') { log(`route=${st.route}, abort`); break }
  if (st.qNo === 1) break
  if (!st.prevKey) { log('no prevKey'); break }
  await invoke(mp, st.prevKey)
  await sleep(700)
}
log('rewound to Q1')

// 2) 逐题作答
const PLAN = [3, 2, 4, 1, 3, 2, 5, 3, 2, 4, 3, 1, 2, 3, 4, 2]
for (let i = 0; i < 16; i++) {
  const st = await readState(mp)
  if (st.route !== 'pages/assessment/index') { log(`left assessment -> ${st.route}`); break }
  if (!st.opts.length) { log(`Q${st.qNo}: no opts, stop`); break }
  const score = PLAN[i] || 3
  const pick = st.opts[score - 1] || st.opts[Math.floor(st.opts.length / 2)]
  const r1 = await invoke(mp, pick.key)
  await sleep(900)
  const st2 = await readState(mp)
  const r2 = await invoke(mp, st2.nextKey)
  await sleep(1100)
  log(`Q${st.qNo} pick=${pick.label}(${r1}) next(${r2})`)
  if (st.qNo === 3) await shot(mp, 't2_assess_q3')
  if (st.qNo === 16) {
    log('submitted; waiting report redirect')
    await sleep(5000)
    await shot(mp, 't2_report_after_submit')
    await sleep(9000)
    await shot(mp, 't2_report_after_submit_12s')
  }
}

const fin = await readState(mp)
log(`final route: ${fin.route} qNo=${fin.qNo}`)

clearTimeout(watchdog)
try { mp.disconnect() } catch { /* ignore */ }
process.exit(0)

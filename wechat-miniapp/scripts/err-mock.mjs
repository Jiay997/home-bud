// 异常场景走查 v2：对象形态 mock wx.request 失败（errMsg → 触发 fail 回调）
// 覆盖：首页错误态 → 离线重试按钮 → 记录/我的页错误态 → 还原后点「重新连接」恢复
import automator from 'miniprogram-automator'
import { execFileSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(HERE, '..', 'walkthrough')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (m) => console.log(`[errmock] ${m}`)

process.on('unhandledRejection', (e) => { log(`unhandledRejection: ${String(e)}`) })

function focus() {
  try {
    execFileSync('python', [resolve(HERE, 'win-focus.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 30000 })
    return true
  } catch (e) {
    log(`focus failed: ${e.message}`)
    return false
  }
}

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(`timeout ${label} after ${ms}ms`)), ms))
  ])
}

async function shot(name) {
  focus()
  try {
    await withTimeout(mp.screenshot({ path: resolve(OUT, `${name}.png`) }), 30000, 'screenshot')
    log(`shot ${name}.png`)
  } catch (e) {
    log(`shot warn ${name}: ${e.message}`)
  }
}

async function winShot(name) {
  focus()
  try {
    const out = execFileSync('python', [resolve(HERE, 'dt-screen.py'), resolve(OUT, `${name}.png`), '0'], { encoding: 'utf8', timeout: 60000 })
    log(`winShot ${name}: ${out.trim().split('\n').slice(-2).join(' | ')}`)
    return true
  } catch (e) {
    log(`winShot warn ${name}: ${e.message}`)
    return false
  }
}

function findButton(winName) {
  try {
    const out = execFileSync('python', [resolve(HERE, 'dt-findbtn.py'), resolve(OUT, `${winName}.png`)], { encoding: 'utf8', timeout: 30000 }).trim()
    log(`findButton ${winName} -> ${out}`)
    const m = /^(\d+) (\d+)/.exec(out)
    return m ? { x: Number(m[1]), y: Number(m[2]) } : null
  } catch (e) {
    log(`findButton warn: ${e.message}`)
    return null
  }
}

function clickAt(x, y) {
  try {
    const out = execFileSync('python', [resolve(HERE, 'dt-mouse.py'), 'click', String(x), String(y)], { encoding: 'utf8', timeout: 30000 }).trim()
    log(`clickAt(${x},${y}): ${out}`)
    return true
  } catch (e) {
    log(`clickAt warn: ${e.message}`)
    return false
  }
}

async function goto(url, settle = 4200) {
  log(`goto -> ${url}`)
  try { await withTimeout(mp.reLaunch(url), 20000, 'reLaunch') } catch (e) { log(`reLaunch warn: ${e.message}`) }
  await sleep(settle)
}

async function dataPeek(tag) {
  try {
    const res = await withTimeout(mp.evaluate(() => {
      try {
        const pages = getCurrentPages()
        const p = pages[pages.length - 1]
        const d = p ? p.data : {}
        const out = {}
        for (const k of Object.keys(d)) {
          const v = d[k]
          out[k] = typeof v === 'string' ? v.slice(0, 60) : (typeof v === 'number' || typeof v === 'boolean' || v === null) ? v : `[${Array.isArray(v) ? 'arr' : typeof v}]`
        }
        return { route: p ? p.route : '', data: out }
      } catch (e) { return { err: e.message } }
    }), 10000, 'evaluate')
    log(`${tag} peek ${JSON.stringify(res)}`)
    return res
  } catch (e) {
    log(`${tag} peek warn ${e.message}`)
    return null
  }
}

focus()
const mp = await withTimeout(automator.connect({ wsEndpoint: process.env.MP_WS || 'ws://127.0.0.1:9420' }), 20000, 'connect')
log('connected')

try {
  log('mock wx.request (object form, errMsg=fail)')
  await withTimeout(mp.mockWxMethod('request', { errMsg: 'request:fail mock_offline' }), 15000, 'mockWxMethod')

  await goto('/pages/index/index')
  await dataPeek('home')
  await shot('compat_err_network_home')
  await winShot('_win_err_home')

  const btn1 = findButton('_win_err_home')
  if (btn1) {
    clickAt(btn1.x, btn1.y)
    await sleep(500)
    await shot('compat_err_network_retry_pending')
    await sleep(3200)
    await dataPeek('retry_offline')
    await shot('compat_err_network_retry_offline')
  }

  await goto('/pages/qa/index')
  await shot('compat_err_network_qa')

  await goto('/pages/records/index')
  await dataPeek('records')
  await shot('compat_err_network_records')

  await goto('/pages/me/index')
  await dataPeek('me')
  await shot('compat_err_network_me')

  await goto('/pages/index/index')
  await winShot('_win_err_home2')
  const btn2 = findButton('_win_err_home2') || btn1

  log('restore wx.request')
  await withTimeout(mp.restoreWxMethod('request'), 15000, 'restoreWxMethod')
  await sleep(600)

  if (btn2) {
    clickAt(btn2.x, btn2.y)
    await sleep(4500)
    await dataPeek('recovered')
    await shot('compat_err_network_recovered')
  } else {
    log('no button coords for recovery click; fallback reLaunch')
    await goto('/pages/index/index', 4500)
    await shot('compat_err_network_recovered')
  }
} catch (e) {
  log(`ERROR: ${e && e.message ? e.message : String(e)}`)
} finally {
  try { mp.disconnect() } catch { /* ignore */ }
  process.exit(0)
}

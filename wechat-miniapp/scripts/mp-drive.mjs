// 小程序端测试驱动（绕过 automator Page.* 挂起）。
// 原理：uni-app 定制 Vue 为模板事件绑定注册 invoker（页面实例上的 eN_xx 函数），
// invoker.value 即原始 handler，直接调用即可触发真实事件流。
//
// 前置：cli auto --auto-port 9420 已启动。
// 用法：
//   node scripts/mp-drive.mjs inbox                 # 列出当前页面的 invoker 及源码
//   node scripts/mp-drive.mjs state                 # 打印页面栈/登录态/时间
//   node scripts/mp-drive.mjs input  <key> <text>   # 触发输入事件
//   node scripts/mp-drive.mjs tap    <key>          # 触发点击事件
//   node scripts/mp-drive.mjs eval   <code>         # 在逻辑层执行表达式（经包装）
//   node scripts/mp-drive.mjs eval-file <path>      # 同上，代码从文件读取（长脚本）
//   node scripts/mp-drive.mjs mock   <api> <json>   # mock wx API（automator mockWxMethod）
//   node scripts/mp-drive.mjs unmock <api>          # 还原 wx API
//   node scripts/mp-drive.mjs shot   <name>         # 协议截图到 walkthrough/（无需窗口置前）
//   node scripts/mp-drive.mjs goto   <url>          # reLaunch
import automator from 'miniprogram-automator'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'walkthrough')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (m) => console.log(`[drive] ${m}`)

process.on('unhandledRejection', (e) => { log(`unhandledRejection: ${String(e).slice(0, 200)}`) })

const watchdog = setTimeout(() => { log('WATCHDOG'); process.exit(2) }, 100000)
watchdog.unref?.()

const EVENT_BASE = '{type:__T, target:{dataset:{}}, currentTarget:{dataset:{}}, detail:__D}'

const mp = await automator.connect({ wsEndpoint: process.env.MP_WS || 'ws://127.0.0.1:9420' })
log('connected')

const [cmd, ...args] = process.argv.slice(2)

async function listInvokers() {
  return mp.evaluate(() => {
    const pages = getCurrentPages()
    const p = pages[pages.length - 1]
    const keys = Object.keys(p).filter((k) => /^e\d+_/.test(k))
    const out = []
    for (let i = 0; i < keys.length; i++) {
      let src = ''
      try { src = String(p[keys[i]].value) } catch (e) { src = 'ERR:' + e.message }
      out.push(keys[i] + ' || ' + src.replace(/\s+/g, ' ').slice(0, 220))
    }
    return { route: p.route, invokers: out }
  })
}

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

try {
  if (cmd === 'scroll') {
    const top = parseInt(args[0] || '0', 10) || 0
    await mp.evaluate((t) => { wx.pageScrollTo({ scrollTop: t, duration: 0 }) }, top)
    log(`scroll -> ${top}`)
  } else if (cmd === 'inbox') {
    const r = await listInvokers()
    log(`route=${r.route}`)
    for (const line of r.invokers) log(line)
  } else if (cmd === 'state') {
    const r = await mp.evaluate(() => {
      const pages = getCurrentPages()
      const route = pages.length ? pages[pages.length - 1].route : ''
      let token = ''
      try { token = String(wx.getStorageSync('jiaban_access_token') || '').slice(0, 12) } catch (e) { token = 'ERR' }
      return { route, token, pageCount: pages.length }
    })
    log(JSON.stringify(r))
  } else if (cmd === 'input') {
    const r = await invoke(args[0], 'input', { value: args[1] || '' })
    log(`input ${args[0]} -> ${r}`)
  } else if (cmd === 'tap') {
    const r = await invoke(args[0], 'tap', {})
    log(`tap ${args[0]} -> ${r}`)
  } else if (cmd === 'eval') {
    const code = args.join(' ')
    // 本版 DevTools 的 App.callFunction 会把 functionDeclaration 求值后立即调用：
    // 传字符串会导致 "xxx is not a function"，必须传真正的函数。
    // 表达式优先（自动 return），失败则按语句体编译（需显式 return）。
    let fn
    try { fn = new Function(`return (${code})`) } catch { fn = new Function(code) }
    const r = await mp.evaluate(fn)
    log(`eval -> ${JSON.stringify(r).slice(0, 800)}`)
  } else if (cmd === 'eval-file') {
    // 从文件读取 eval 代码（argv 有长度上限，长脚本/内嵌 base64 走这里）
    const { readFileSync } = await import('node:fs')
    const code = readFileSync(resolve(args[0]), 'utf8')
    let fn
    try { fn = new Function(`return (${code})`) } catch { fn = new Function(code) }
    const r = await mp.evaluate(fn)
    log(`eval-file -> ${JSON.stringify(r).slice(0, 800)}`)
  } else if (cmd === 'mock') {
    // mock wx API（automator mockWxMethod）：mock <api> <resultJSON>
    const api = args[0]
    const payload = JSON.parse(args.slice(1).join(' '))
    await mp.mockWxMethod(api, payload)
    log(`mock ${api}`)
  } else if (cmd === 'unmock') {
    await mp.restoreWxMethod(args[0])
    log(`unmock ${args[0]}`)
  } else if (cmd === 'shot') {
    // App.captureScreenshot 直出模拟器渲染画面，与窗口前台焦点无关
    await mp.screenshot({ path: resolve(OUT, `${args[0] || 'shot'}.png`) })
    log(`saved ${args[0]}.png`)
  } else if (cmd === 'goto') {
    let url = args[0] || '/pages/index/index'
    const m = url.match(/\/pages\/[^\\]*$/)
    if (m) url = m[0]
    await mp.reLaunch(url)
    log(`reLaunch -> ${url}`)
  } else {
    log('unknown command; see header for usage')
  }
} catch (e) {
  log(`ERROR: ${e && e.message ? e.message : String(e)}`)
} finally {
  clearTimeout(watchdog)
  try { mp.disconnect() } catch { /* ignore */ }
  process.exit(0)
}

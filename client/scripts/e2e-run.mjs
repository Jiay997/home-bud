// 小程序端 E2E 执行器（单连接跑完整套件）。
//
// 为什么必须是「单连接」：本项目使用的 `cli auto --auto-port 9420` 把自动化会话与
// 单个客户端绑定 —— 客户端一断开，开发者工具的项目窗口随之关闭、端口消失。
// 因此所有用例必须在一次 connect/disconnect 内跑完；脚本把结果增量写入
// screenshots/_results.json，即使中途崩了也能看到已完成的部分。
//
// 用法：
//   node scripts/e2e-run.mjs                 # 全部套件
//   node scripts/e2e-run.mjs pages states    # 只跑指定套件
//
// 已知环境事实（本轮实测，勿踩）：
//   · 模拟器停在欢迎页（项目未编译）时 evaluate 会永久挂起 → 连上后先触发一次编译。
//   · 读取页面 invoker 的函数源码（p[eN_xx].value）会把会话打挂 → 一律不碰。
//   · 元素查询（Page.$ / createSelectorQuery 经 automator 回传）会挂起 → 只用
//     reLaunch + p.data + 截图 + 真鼠标点击四条通道。
import automator from 'miniprogram-automator'
import fs from 'node:fs'
import net from 'node:net'
import { execFileSync, spawn } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const SHOTS = resolve(ROOT, 'screenshots')
const RESULTS = resolve(SHOTS, '_results.json')
const RUNLOG = resolve(SHOTS, '_run.log')
const PROJECT = resolve(ROOT, 'dist', 'dev', 'mp-weixin')
const PORT = Number(process.env.MP_PORT || 9420)
const WS = `ws://127.0.0.1:${PORT}`
const CLI = process.env.MP_CLI || 'C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const lines = []
function log(m) {
  const line = `[e2e ${new Date().toISOString().slice(11, 19)}] ${m}`
  console.log(line)
  lines.push(line)
  try { fs.appendFileSync(RUNLOG, line + '\n') } catch { /* ignore */ }
}
function heading(m) { log(`\n===== ${m} =====`) }

for (const d of ['pages', 'flows', 'compat', 'states']) fs.mkdirSync(resolve(SHOTS, d), { recursive: true })

// ---------- 结果仓库（增量落盘） ----------
let results = { startedAt: new Date().toISOString(), env: {}, suites: {} }
try { if (fs.existsSync(RESULTS)) results = JSON.parse(fs.readFileSync(RESULTS, 'utf8')) } catch { /* ignore */ }
results.startedAt = results.startedAt || new Date().toISOString()
function save() { try { fs.writeFileSync(RESULTS, JSON.stringify(results, null, 2)) } catch { /* ignore */ } }
function record(suite, item) {
  results.suites[suite] = results.suites[suite] || { cases: [] }
  const arr = results.suites[suite].cases
  const i = arr.findIndex((c) => c.id === item.id)
  if (i >= 0) arr[i] = item; else arr.push(item)
  save()
}

// ---------- 环境准备 ----------
function portOpen() {
  return new Promise((res) => {
    const s = net.connect(PORT, '127.0.0.1')
    const done = (v) => { try { s.destroy() } catch { /* ignore */ } res(v) }
    s.on('connect', () => done(true)); s.on('error', () => done(false))
    setTimeout(() => done(false), 1500)
  })
}
async function ensurePort() {
  if (await portOpen()) { log(`port ${PORT} already listening`); return true }
  log(`spawning: cli auto --project ${PROJECT} --auto-port ${PORT}`)
  const child = spawn(CLI, ['auto', '--project', PROJECT, '--auto-port', String(PORT)], { stdio: 'ignore', detached: true })
  child.unref()
  for (let i = 0; i < 60; i++) { await sleep(2000); if (await portOpen()) { log('port is up'); return true } }
  return false
}
function focusWindow() {
  try { execFileSync('python', [resolve(HERE, 'win-focus.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 30000 }); return true }
  catch (e) { log(`focus warn: ${e.message}`); return false }
}
function triggerCompile() {
  try {
    const out = execFileSync('python', [resolve(HERE, 'dt-compile.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 40000 })
    return out.trim().split('\n').pop()
  } catch (e) { return 'compile-err: ' + e.message }
}
function wt(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(`TIMEOUT ${label} ${ms}ms`)), ms))
  ])
}

// ---------- 与小程序交互的通道 ----------
let mp = null

async function ev(fn, ms = 12000, label = 'evaluate', ...args) {
  return wt(mp.evaluate(fn, ...args), ms, label)
}
async function goto(url, settle = 3600) {
  try { await wt(mp.reLaunch(url), 20000, 'reLaunch') } catch (e) { log(`reLaunch warn ${url}: ${e.message}`) }
  await sleep(settle)
}
const TAG = process.env.MP_TAG ? `${process.env.MP_TAG}-` : ''
async function shot(name, dir = 'pages') {
  focusWindow()
  const path = resolve(SHOTS, dir, `${TAG}${name}.png`)
  try {
    await wt(mp.screenshot({ path }), 30000, 'screenshot')
    return `screenshots/${dir}/${TAG}${name}.png`
  } catch (e) {
    log(`shot warn ${name}: ${e.message}`)
    return null
  }
}
// 页面状态快照：数据层全量键值（值做长度截断），用于「页面确实渲染了业务数据」的断言
async function snapshot(ms = 12000) {
  return ev(() => {
    const pages = getCurrentPages()
    const p = pages[pages.length - 1]
    if (!p) return { route: '', data: {}, stack: [] }
    const d = p.data || {}
    const out = {}
    for (const k of Object.keys(d)) {
      const v = d[k]
      out[k] = (typeof v === 'string') ? v.slice(0, 120)
        : (v === null || typeof v === 'number' || typeof v === 'boolean') ? v
          : Array.isArray(v) ? { __arr: v.length, sample: v.length ? String(JSON.stringify(v[0])).slice(0, 200) : '' }
            : typeof v === 'object' ? String(JSON.stringify(v)).slice(0, 200)
              : typeof v
    }
    return { route: p.route, stack: pages.map((x) => x.route), data: out }
  }, ms, 'snapshot')
}
// 从数据层任意字符串里找 uuid（用于详情页/报告页入参）
function findUid(snap, kind) {
  const re = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i
  const hit = new Set()
  const walk = (v) => {
    if (typeof v === 'string') { const m = re.exec(v); if (m) hit.add(m[0]); return }
    if (v && typeof v === 'object') for (const k of Object.keys(v)) walk(v[k])
  }
  walk(snap.data)
  const all = [...hit]
  return { all, first: all[0] || '' }
}
function countStrings(snap, needles) {
  const found = {}
  for (const n of needles) found[n] = false
  const walk = (v) => {
    if (typeof v === 'string') { for (const n of needles) if (!found[n] && v.includes(n)) found[n] = true; return }
    if (v && typeof v === 'object') for (const k of Object.keys(v)) walk(v[k])
  }
  walk(snap.data)
  return found
}
// 把数据层里的字符串/布尔值抽平：字符串用于「异常态引入了新文案」的差异比对，
// 布尔值用于「哪个 wx:if 分支被打开」的差异比对（错误态分支会从 false 翻成 true）
function flattenPrimitives(snap) {
  const strings = new Set()
  const bools = {}
  const walk = (v, path) => {
    if (typeof v === 'string') { if (v) strings.add(v.slice(0, 80)); return }
    if (typeof v === 'boolean') { bools[path] = v; return }
    if (v && typeof v === 'object') for (const k of Object.keys(v)) walk(v[k], `${path}.${k}`)
  }
  for (const k of Object.keys(snap.data)) walk(snap.data[k], k)
  return { strings: [...strings], bools }
}
// 导航并校验落点（reLaunch 到当前页可能被忽略，故带重试）
async function gotoVerify(url, expect, settle = 3800, tries = 3) {
  let stack = ''
  for (let i = 0; i < tries; i++) {
    await goto(url, settle)
    stack = await ev(() => getCurrentPages().map((x) => x.route).join('>'), 12000, 'stack')
    if (stack.split('>').pop() === expect) return { ok: true, stack, tries: i + 1 }
    log(`   gotoVerify ${url} -> 落在 '${stack}'（第 ${i + 1} 次）`)
    await sleep(1200)
  }
  return { ok: false, stack, tries }
}

// ---------- 用例封装 ----------
async function runCase(suite, id, name, fn, opts = {}) {
  const t0 = Date.now()
  const item = { id, name, status: 'RUN', suite }
  log(`-- ${suite}/${id} ${name}`)
  try {
    const r = await fn()
    Object.assign(item, r || {})
    item.status = item.status === 'FAIL' ? 'FAIL' : 'PASS'
  } catch (e) {
    item.status = 'FAIL'
    item.error = String(e && e.message ? e.message : e).slice(0, 300)
    log(`   !! ${id} FAILED: ${item.error}`)
  }
  item.ms = Date.now() - t0
  record(suite, item)
  log(`   -> ${item.status} (${item.ms}ms)${item.note ? ' :: ' + item.note : ''}`)
  return item
}

// ============================================================
// 套件：probe —— 环境与数据通道体检
// ============================================================
async function suiteProbe() {
  heading('suite probe')
  await runCase('probe', 'sysinfo', '模拟器系统信息', async () => {
    const si = await wt(mp.systemInfo(), 15000, 'systemInfo')
    const info = {
      model: si.model, platform: si.platform, SDKVersion: si.SDKVersion,
      screenWidth: si.screenWidth, screenHeight: si.screenHeight, pixelRatio: si.pixelRatio,
      statusBarHeight: si.statusBarHeight, safeAreaBottom: si.safeArea ? si.safeArea.bottom : null,
      windowWidth: si.windowWidth, windowHeight: si.windowHeight, brand: si.brand, system: si.system
    }
    results.env.systemInfo = info
    save()
    return { note: `${info.model} ${info.screenWidth}x${info.screenHeight} dpr=${info.pixelRatio} lib=${info.SDKVersion}`, data: info }
  })

  await runCase('probe', 'home-snapshot', '首页数据层快照', async () => {
    await goto('/pages/index/index')
    const snap = await snapshot()
    return { note: `route=${snap.route} dataKeys=${Object.keys(snap.data).length}`, data: { route: snap.route, dataKeys: Object.keys(snap.data).length } }
  })
}

// ============================================================
// 套件：pages —— 11 页逐页走查（渲染断言 + 模拟器截图）
// ============================================================
async function suitePages() {
  heading('suite pages')
  const pages = [
    { id: 'p01-home', name: '首页', url: '/pages/index/index', dir: 'pages', needles: ['Babe宝伴'] },
    { id: 'p02-qa-child', name: '问答（孩子）', url: '/pages/qa/index?entry=child', dir: 'pages' },
    { id: 'p03-qa-pet', name: '问答（宠物）', url: '/pages/qa/index?entry=pet', dir: 'pages' },
    { id: 'p04-qa-family', name: '问答（家庭综合）', url: '/pages/qa/index?entry=family', dir: 'pages' },
    { id: 'p05-records', name: '记录', url: '/pages/records/index', dir: 'pages' },
    { id: 'p06-profiles', name: '家庭档案列表', url: '/pages/profiles/index', dir: 'pages' },
    { id: 'p07-me', name: '我的', url: '/pages/me/index', dir: 'pages', settle: 9000 },
    { id: 'p08-member', name: '会员', url: '/pages/member/index', dir: 'pages' },
    { id: 'p09-assessment-intro', name: '测评引导', url: '/pages/assessment-intro/index', dir: 'pages' },
    { id: 'p10-assessment', name: '测评作答', url: '/pages/assessment/index', dir: 'pages' },
    { id: 'p11-report-history', name: '报告（历史）', url: '/pages/report/index?history=1', dir: 'pages' }
  ]

  let detailTargets = null

  for (const pg of pages) {
    await runCase('pages', pg.id, pg.name, async () => {
      const expect = pg.url.split('?')[0].replace(/^\//, '')
      const nav = await gotoVerify(pg.url, expect, pg.settle || 4200)
      const snap = await snapshot()
      const shotPath = await shot(pg.id, pg.dir)
      const keys = Object.keys(snap.data)
      const { strings, bools } = flattenPrimitives(snap)
      const detail = {
        route: snap.route, dataKeys: keys.length, shot: shotPath,
        stack: snap.stack, strings: strings.slice(0, 60), bools,
        nestedArrays: Object.keys(snap.data).filter((k) => snap.data[k] && typeof snap.data[k] === 'object' && snap.data[k].__arr).length
      }
      if (snap.route !== expect) {
        return { status: 'FAIL', error: `route mismatch: ${snap.route}`, note: `期望 ${expect}，实际 ${snap.route}；栈=${snap.stack.join('>')}；导航重试=${nav.tries}`, data: detail }
      }
      const needles = pg.needles ? countStrings(snap, pg.needles) : {}
      const missing = Object.keys(needles).filter((n) => !needles[n])
      const note = `route=${snap.route} keys=${keys.length} 字符串=${strings.length}`
      return { status: missing.length ? 'FAIL' : 'PASS', note, data: detail, error: missing.length ? 'missing copy: ' + missing.join(',') : undefined }
    })

    // 档案列表页拿到 uid 后，顺带跑详情页与相册页
    if (pg.id === 'p06-profiles') {
      await runCase('pages', 'p06b-uid-discovery', '档案 uid 发现（详情/相册入参）', async () => {
        await gotoVerify('/pages/profiles/index', 'pages/profiles/index', 4200)
        const snap = await snapshot()
        const uids = findUid(snap)
        detailTargets = uids
        return { note: `发现 uid ${uids.all.length} 个`, data: { uids: uids.all.slice(0, 6) } }
      })
    }
  }

  // 详情页 / 相册页：依赖 uid，失败不算产品缺陷，标记为 SKIP 并注明原因
  const uid = detailTargets && detailTargets.first
  // 真实报告页：先用记录页里的条目 uid 打开（p11 用的是缺参降级入口）
  await runCase('pages', 'p11b-report-real', '报告（真实 uid）', async () => {
    await gotoVerify('/pages/records/index', 'pages/records/index', 4200)
    const recSnap = await snapshot()
    const u = findUid(recSnap).first
    if (!u) return { status: 'FAIL', error: '记录页未发现报告/问答 uid' }
    const nav = await gotoVerify(`/pages/report/index?uid=${u}&history=1`, 'pages/report/index', 5000)
    const snap = await snapshot()
    const shotPath = await shot('p11b-report-real', 'pages')
    const { strings, bools } = flattenPrimitives(snap)
    return { note: `uid=${u.slice(0, 8)}… route=${snap.route} 字符串=${strings.length}`, data: { uid: u, route: snap.route, shot: shotPath, strings: strings.slice(0, 60), bools, tries: nav.tries } }
  })

  if (uid) {
    await runCase('pages', 'p12-profile-detail-child', '档案详情（孩子）', async () => {
      const nav = await gotoVerify(`/pages/profile-detail/index?kind=child&uid=${uid}`, 'pages/profile-detail/index', 4200)
      const snap = await snapshot()
      const shotPath = await shot('p12-profile-detail-child', 'pages')
      const { strings, bools } = flattenPrimitives(snap)
      return { note: `route=${snap.route} 字符串=${strings.length}`, data: { route: snap.route, shot: shotPath, strings: strings.slice(0, 60), bools, tries: nav.tries } }
    })
    await runCase('pages', 'p13-profile-album-child', '成长相册（孩子）', async () => {
      await goto(`/pages/profile-album/index?kind=child&uid=${uid}`, 4200)
      const snap = await snapshot()
      const shotPath = await shot('p13-profile-album-child', 'pages')
      return { note: `route=${snap.route}`, data: { route: snap.route, shot: shotPath } }
    })
  } else {
    await runCase('pages', 'p12-profile-detail-child', '档案详情（孩子）', async () => ({ status: 'FAIL', error: 'no uid discovered' }))
  }
}

// ============================================================
// 套件：states —— 异常与降级（断网故障注入）
// ============================================================
async function suiteStates() {
  heading('suite states')
  await runCase('states', 'offline-inject', '注入离线故障（mock wx.request）', async () => {
    await wt(mp.mockWxMethod('request', { errMsg: 'request:fail mock_offline' }), 15000, 'mockWxMethod')
    return { note: 'mock wx.request -> request:fail' }
  })

  const targets = [
    { id: 's01-home-offline', name: '首页断网错误态', url: '/pages/index/index', normal: 'p01-home' },
    { id: 's02-records-offline', name: '记录页断网错误态', url: '/pages/records/index', normal: 'p05-records' },
    { id: 's03-me-offline', name: '我的页断网错误态', url: '/pages/me/index', normal: 'p07-me' },
    { id: 's04-qa-offline', name: '问答页断网降级', url: '/pages/qa/index?entry=child', normal: 'p02-qa-child' }
  ]
  for (const t of targets) {
    await runCase('states', t.id, t.name, async () => {
      const expect = t.url.split('?')[0].replace(/^\//, '')
      await gotoVerify(t.url, expect, 4200)
      const snap = await snapshot()
      const shotPath = await shot(t.id, 'states')
      const { strings, bools } = flattenPrimitives(snap)
      // 差异比对：与正常态相比新增的文案 / 由 false 翻成 true 的分支，即为错误态证据
      const normalCase = results.suites.pages?.cases?.find((c) => c.id === t.normal)
      const normalStrings = new Set(normalCase?.data?.strings || [])
      const normalBools = normalCase?.data?.bools || {}
      const added = strings.filter((s) => !normalStrings.has(s))
      const flipped = Object.keys(bools).filter((k) => bools[k] === true && normalBools[k] === false)
      const errWords = ['无法连接', '连接失败', '重新连接', '重新加载', '网络']
      const addedErr = added.filter((s) => errWords.some((w) => s.includes(w)))
      const evidence = addedErr.length > 0 || flipped.length > 0
      return {
        status: evidence ? 'PASS' : 'FAIL',
        note: `新增文案=${added.length}${addedErr.length ? '（错误类:' + addedErr.join(' / ').slice(0, 90) + '）' : ''} 分支翻转=${flipped.length}`,
        error: evidence ? undefined : '与正常态相比未观察到错误分支或新增文案',
        data: { route: snap.route, shot: shotPath, added: added.slice(0, 30), addedErr, flipped: flipped.slice(0, 12), bools, strings: strings.slice(0, 60) }
      }
    })
  }

  await runCase('states', 'offline-restore', '还原网络并验证恢复', async () => {
    await wt(mp.restoreWxMethod('request'), 15000, 'restoreWxMethod')
    await gotoVerify('/pages/index/index', 'pages/index/index', 5000)
    const snap = await snapshot()
    const shotPath = await shot('s05-home-recovered', 'states')
    const { strings, bools } = flattenPrimitives(snap)
    const normalCase = results.suites.pages?.cases?.find((c) => c.id === 'p01-home')
    const normalStrings = new Set(normalCase?.data?.strings || [])
    const normalBools = normalCase?.data?.bools || {}
    const errWords = ['无法连接', '连接失败', '重新连接']
    const stillErr = strings.filter((s) => errWords.some((w) => s.includes(w)) && !normalStrings.has(s))
    const errBranches = Object.keys(bools).filter((k) => bools[k] === true && normalBools[k] === false)
    const ok = stillErr.length === 0 && errBranches.length === 0
    return {
      status: ok ? 'PASS' : 'FAIL',
      note: ok ? '还原后首屏回到就绪态（无错误分支/错误文案）' : `仍残留: ${stillErr.join(' / ')} 分支=${errBranches.join(',')}`,
      error: ok ? undefined : '网络还原后首页未回到就绪态',
      data: { route: snap.route, shot: shotPath, strings: strings.slice(0, 40), bools }
    }
  })
}

// ============================================================
// 交互驱动：沿「编译产物 render key → 运行时 invoker 名」调用真实事件流
// ============================================================
function readJs(pageDir) {
  return fs.readFileSync(resolve(PROJECT, `${pageDir}.js`), 'utf8')
}
// 具名 handler 绑定的 render key（含 v-for 内 ($event) => handler(arg) 形式）
function diskKeyForHandler(pageDir, handler) {
  const js = readJs(pageDir)
  const out = new Set()
  const patterns = [
    `([A-Za-z_$][\\w$]*):\\s*common_vendor\\.o\\(\\s*(?:common_vendor\\.unref\\()?${handler}\\b`,
    `([A-Za-z_$][\\w$]*):\\s*common_vendor\\.o\\(\\s*\\([^)]*\\)\\s*=>\\s*${handler}\\(`
  ]
  for (const p of patterns) {
    const re = new RegExp(p, 'g')
    let m
    while ((m = re.exec(js))) out.add(m[1])
  }
  return [...out]
}
// 内联表达式 handler（如 v-model 赋值、activeTab = 'child'）的 render key
function diskKeyForCode(pageDir, snippets) {
  const js = readJs(pageDir)
  for (const sn of snippets) {
    const idx = js.indexOf(sn)
    if (idx < 0) continue
    const before = js.slice(Math.max(0, idx - 6000), idx)
    const ms = [...before.matchAll(/([A-Za-z_$][\w$]*):\s*common_vendor\.o\(/g)]
    if (ms.length) return ms[ms.length - 1][1]
  }
  return null
}
// 按 render key 找到 invoker 名并调用真实事件流（可指定第 index 个匹配，用于 v-for 项）
async function callRenderKey(rk, opts = {}) {
  const idx = typeof opts.index === 'number' ? opts.index : -1
  const detail = opts.detail || {}
  return ev((k, i, d) => {
    const pages = getCurrentPages()
    const p = pages[pages.length - 1]
    const hits = []
    const walk = (n, path, depth) => {
      if (depth > 5 || !n || typeof n !== 'object') return
      if (Array.isArray(n)) { n.forEach((it, j) => walk(it, `${path}[${j}]`, depth + 1)); return }
      for (const kk of Object.keys(n)) {
        const v = n[kk]
        if (kk === k && typeof v === 'string') hits.push({ path: `${path}.${kk}`, name: v })
        else if (v && typeof v === 'object') walk(v, `${path}.${kk}`, depth + 1)
      }
    }
    walk(p.data || {}, '', 0)
    if (!hits.length) return `NO_HIT:${k}`
    const pick = (i >= 0 && i < hits.length) ? hits[i] : hits[0]
    const fn = p[pick.name]
    if (typeof fn !== 'function') return `NOT_INVOKER:${pick.name}`
    try { fn({ type: 'tap', target: { dataset: {} }, currentTarget: { dataset: {} }, detail: d }) } catch (e) { return `THROW:${String(e && e.message)}` }
    return `OK ${pick.path}=${pick.name} n=${hits.length}`
  }, 15000, 'callRenderKey', rk, idx, detail)
}
// 事件流调用必须真成功，否则用例判失败（避免「调不动但记 PASS」的假绿）
const invoked = (r) => typeof r === 'string' && r.startsWith('OK')
// 弹层/对话框可见性
const probeVisible = () => ev(() => {
  const p = getCurrentPages()[getCurrentPages().length - 1]
  const out = []
  const walk = (n, path, depth) => {
    if (depth > 4 || !n || typeof n !== 'object') return
    if (Array.isArray(n)) { n.forEach((it, j) => walk(it, `${path}[${j}]`, depth + 1)); return }
    if (n.visible === true) out.push(path)
    for (const k of Object.keys(n)) walk(n[k], `${path}.${k}`, depth + 1)
  }
  walk(p.data || {}, '', 0)
  return out.slice(0, 8)
}, 10000, 'probeVisible')
// 数据层数组长度（用于「列表确实加载了」）
const probeArrays = () => ev(() => {
  const p = getCurrentPages()[getCurrentPages().length - 1]
  const out = {}
  const walk = (n, path, depth) => {
    if (depth > 3 || !n || typeof n !== 'object') return
    if (Array.isArray(n)) { if (path) out[path] = n.length; return }
    for (const k of Object.keys(n)) walk(n[k], `${path}.${k}`, depth + 1)
  }
  walk(p.data || {}, '', 0)
  return out
}, 10000, 'probeArrays')

// 记录列表条目数：按 :key 形如 `qa-<uuid>` / `report-<uuid>` 识别真正的业务列表
const probeRecordCount = () => ev(() => {
  const p = getCurrentPages()[getCurrentPages().length - 1]
  const re = /^(?:qa|report|report-|qa-)[0-9a-f-]{20,}$/i
  let best = 0
  const walk = (n, depth) => {
    if (depth > 5 || !n || typeof n !== 'object') return
    if (Array.isArray(n)) {
      let hit = 0
      for (const it of n) {
        if (!it || typeof it !== 'object') continue
        for (const k of Object.keys(it)) {
          if (typeof it[k] === 'string' && re.test(it[k])) { hit++; break }
        }
      }
      if (hit > best) best = hit
      n.forEach((it) => walk(it, depth + 1))
      return
    }
    for (const k of Object.keys(n)) walk(n[k], depth + 1)
  }
  walk(p.data || {}, 0)
  return best
}, 10000, 'probeRecordCount')

// 数据层文本体量：流式内容渲染会让总字符数显著增长
const probeTextVolume = () => ev(() => {
  const p = getCurrentPages()[getCurrentPages().length - 1]
  let total = 0
  let maxLen = 0
  const walk = (n, d) => {
    if (typeof n === 'string') { total += n.length; if (n.length > maxLen) maxLen = n.length; return }
    if (d > 5 || !n || typeof n !== 'object') return
    for (const k of Object.keys(n)) walk(n[k], d + 1)
  }
  walk(p.data || {}, 0)
  return { total, maxLen }
}, 10000, 'probeTextVolume')

// 像素差异：弹层多渲染在子组件里，页面数据层看不到 visible，用截图差异补证
function absShot(rel) {
  return resolve(ROOT, rel.replace(/^screenshots\//, 'screenshots/'))
}
function pixelDiff(relA, relB) {
  try {
    const out = execFileSync('python', [resolve(HERE, 'dt-diff.py'), absShot(relA), absShot(relB)], { encoding: 'utf8', timeout: 40000 })
    return Number(out.trim())
  } catch (e) {
    log(`pixelDiff warn: ${e.message}`)
    return -1
  }
}

// ============================================================
// 套件：flows —— 业务链路（真实事件流）
// ============================================================
async function suiteFlows() {
  heading('suite flows')

  await runCase('flows', 'f00-map-probe', '交互映射体检（磁盘 render key 解析）', async () => {
    const m = {
      qa_input_snippets: ['draft.value = $event.detail.value', 'draft.value='],
      qa_send: diskKeyForHandler('pages/qa/index', 'send'),
      qa_regen: diskKeyForHandler('pages/qa/index', 'regenerate'),
      assess_choose: diskKeyForHandler('pages/assessment/index', 'choose'),
      assess_next: diskKeyForHandler('pages/assessment/index', 'next'),
      assess_start: diskKeyForHandler('pages/assessment-intro/index', 'startOrResume'),
      records_preset: diskKeyForHandler('pages/records/index', 'setPreset'),
      profiles_add_child: diskKeyForHandler('pages/profiles/index', 'startAddChild'),
      profiles_tab_child: diskKeyForCode('pages/profiles/index', ["activeTab.value = 'child'", 'activeTab.value = "child"', "activeTab = 'child'", 'activeTab = "child"']),
      me_sheets: diskKeyForHandler('pages/me/index', 'openSheet'),
      member_orders: diskKeyForHandler('pages/member/index', 'openOrders'),
      report_save: diskKeyForHandler('pages/report/index', 'saveLongImage'),
      detail_birth: diskKeyForHandler('pages/profile-detail/index', 'toggleBirth'),
      album_add: diskKeyForHandler('pages/profile-album/index', 'addPhotos')
    }
    m.qa_input_key = diskKeyForCode('pages/qa/index', m.qa_input_snippets)
    const bad = Object.keys(m).filter((k) => Array.isArray(m[k]) ? !m[k].length : !m[k])
    return { note: bad.length ? `未解析: ${bad.join(',')}` : '全部 handler 已解析', data: m }
  })

  // ---- 导航探针：首页 reLaunch 落点核实（第一轮 p01 曾落到档案详情页） ----
  await runCase('flows', 'f00b-nav-probe', '导航探针：首页 reLaunch 落点与页面栈', async () => {
    const probe = async (from, target) => {
      await goto(from, 4000)
      const before = await ev(() => getCurrentPages().map((x) => x.route).join('>'), 12000, 'stack')
      await wt(mp.reLaunch(target), 20000, 'reLaunch')
      const marks = []
      for (const w of [1000, 2000, 4000]) {
        await sleep(w)
        marks.push(await ev(() => getCurrentPages().map((x) => x.route).join('>'), 12000, 'stack'))
      }
      return { from, before, marks }
    }
    const a = await probe('/pages/profiles/index', '/pages/index/index')
    const b = await probe('/pages/profile-detail/index?kind=child&uid=x', '/pages/index/index')
    const c = await probe('/pages/index/index', '/pages/index/index')
    return {
      note: `首页→首页 ${JSON.stringify(a.marks)} | 详情→首页 ${JSON.stringify(b.marks)} | 自跳 ${JSON.stringify(c.marks)}`,
      data: { a, b, c }
    }
  })

  // ---- 记录页筛选 chips ----
  await runCase('flows', 'f01-records-filters', '记录页筛选 chips 切换与列表联动', async () => {
    const key = diskKeyForHandler('pages/records/index', 'setPreset')
    if (!key.length) return { status: 'FAIL', error: 'setPreset invoker 未解析' }
    const shots = []
    const counts = []
    const results_ = []
    for (let i = 0; i < 5; i++) {
      await gotoVerify('/pages/records/index', 'pages/records/index', 4000)
      const r = await callRenderKey(key[0], { index: i })
      results_.push(r)
      await sleep(2400)
      counts.push(await probeRecordCount())
      shots.push(await shot(`f01-records-filter-${i}`, 'flows'))
    }
    const allOk = results_.every(invoked)
    const varied = new Set(counts).size > 1
    return {
      status: allOk && varied ? 'PASS' : 'FAIL',
      note: `触发=${results_.filter(invoked).length}/5 各档业务条目数=${JSON.stringify(counts)}`,
      error: !allOk ? '部分 chip 事件流未触发: ' + JSON.stringify(results_) : (!varied ? '切换筛选后条目数无变化' : undefined),
      data: { shots, counts, results: results_ }
    }
  })

  // ---- 首页协议弹窗 ----
  await runCase('flows', 'f02-home-policy-dialog', '首页《服务协议》弹窗', async () => {
    await gotoVerify('/pages/index/index', 'pages/index/index', 4200)
    const keys = diskKeyForHandler('pages/index/index', 'showPolicy')
    if (!keys.length) return { status: 'FAIL', error: 'showPolicy invoker 未解析' }
    const before = await shot('f02-home-policy-before', 'flows')
    const r = await callRenderKey(keys[0])
    await sleep(1600)
    const after = await shot('f02-home-policy-dialog', 'flows')
    const diff = before && after ? pixelDiff(before, after) : -1
    const ok = invoked(r) && diff > 0.02
    return {
      status: ok ? 'PASS' : 'FAIL',
      note: `触发=${invoked(r)} 截图差异=${diff}`,
      error: ok ? undefined : `弹窗未出现或事件流未触发（触发=${r}, 差异=${diff}）`,
      data: { shots: [before, after], diff, invoke: r }
    }
  })

  // ---- 问答：真实流式生成（判定「慢」还是「卡死」）----
  await runCase('flows', 'f03-qa-send-stream', '问答发送（真实流式生成）', async () => {
    const inputKey = diskKeyForCode('pages/qa/index', ['draft.value = $event.detail.value', 'draft.value='])
    const sendKeys = diskKeyForHandler('pages/qa/index', 'send')
    if (!inputKey || !sendKeys.length) return { status: 'FAIL', error: `inputKey=${inputKey} sendKeys=${sendKeys}` }
    await gotoVerify('/pages/records/index', 'pages/records/index', 4200)
    const before = await probeRecordCount()
    await gotoVerify('/pages/qa/index?entry=child', 'pages/qa/index', 4500)
    const vol0 = await probeTextVolume()
    const ri = await callRenderKey(inputKey, { detail: { value: '宝宝十个月，夜里频繁醒来要吃奶，白天精神还好，想调整夜醒。' } })
    await sleep(700)
    const rs = await callRenderKey(sendKeys[0])
    const shots = []
    const marks = []
    for (const [label, wait] of [['5s', 5000], ['25s', 20000], ['60s', 35000], ['95s', 35000]]) {
      await sleep(wait)
      shots.push(await shot(`f03-qa-${label}`, 'flows'))
      const vol = await probeTextVolume()
      marks.push({ label, total: vol.total, maxLen: vol.maxLen })
    }
    // 落库核对：换页后回记录页，看这一次提问是否已形成记录
    await gotoVerify('/pages/records/index', 'pages/records/index', 4500)
    const after = await probeRecordCount()
    const grew = marks[marks.length - 1].total - vol0.total
    const rendered = grew > 200
    const persisted = after > before
    const ok = invoked(ri) && invoked(rs) && (rendered || persisted)
    return {
      status: ok ? 'PASS' : 'FAIL',
      note: `触发=${invoked(ri) && invoked(rs)} | 文本体量 ${vol0.total}→${marks.map((m) => `${m.label}:${m.total}`).join(' ')} | 记录数 ${before}→${after}`,
      error: ok ? undefined : '95s 内未渲染答案，且记录数未增长（疑似流式链路卡死）',
      data: { shots, marks, vol0, rendered, persisted, before, after, invoke: [ri, rs] }
    }
  })

  // ---- 测评 16 题全链路 ----
  await runCase('flows', 'f04-assessment-full', '测评 16 题作答至报告', async () => {
    const startKeys = diskKeyForHandler('pages/assessment-intro/index', 'startOrResume')
    const chooseKey = diskKeyForHandler('pages/assessment/index', 'choose')
    const nextKeys = diskKeyForHandler('pages/assessment/index', 'next')
    if (!startKeys.length || !chooseKey.length || !nextKeys.length) {
      return { status: 'FAIL', error: `start=${startKeys} choose=${chooseKey} next=${nextKeys}` }
    }
    await gotoVerify('/pages/assessment-intro/index', 'pages/assessment-intro/index', 4200)
    const shots = [await shot('f04-assessment-intro', 'flows')]
    const r0 = await callRenderKey(startKeys[0])
    await sleep(4500)
    const log = []
    let okCount = 0
    for (let q = 0; q < 16; q++) {
      const rc = await callRenderKey(chooseKey[0], { index: 0 })
      await sleep(500)
      if (q === 0) shots.push(await shot('f04-assessment-q1', 'flows'))
      const rn = await callRenderKey(nextKeys[0])
      await sleep(900)
      if (invoked(rc) && invoked(rn)) okCount++
      if (q === 2) shots.push(await shot('f04-assessment-q3', 'flows'))
    }
    await sleep(8000)
    const route = await ev(() => getCurrentPages().map((x) => x.route).join('>'), 12000, 'route')
    shots.push(await shot('f04-assessment-submitted', 'flows'))
    const ok = invoked(r0) && okCount >= 15
    log.push(`开始=${invoked(r0)}`, `作答轮次成功=${okCount}/16`, `落点=${route}`)
    return {
      status: ok ? 'PASS' : 'FAIL',
      note: log.join(' | '),
      error: ok ? undefined : '测评作答事件流未完整触发',
      data: { shots, route, okCount, startInvoke: r0 }
    }
  })

  // ---- 报告页：保存长图 ----
  await runCase('flows', 'f05-report-save-longimage', '报告页保存长图', async () => {
    const keys = diskKeyForHandler('pages/report/index', 'saveLongImage')
    if (!keys.length) return { status: 'FAIL', error: 'saveLongImage invoker 未解析' }
    const route = await ev(() => getCurrentPages()[getCurrentPages().length - 1].route, 10000, 'route')
    if (route !== 'pages/report/index') return { status: 'FAIL', error: '当前不在报告页: ' + route }
    const shots = [await shot('f05-report-before-save', 'flows')]
    const r = await callRenderKey(keys[0])
    await sleep(2500)
    shots.push(await shot('f05-report-save-pending', 'flows'))
    await sleep(5000)
    const vis = await probeVisible()
    shots.push(await shot('f05-report-save-result', 'flows'))
    const ok = invoked(r)
    return {
      status: ok ? 'PASS' : 'FAIL',
      note: `触发=${invoked(r)} 可见弹层=${vis.length}`,
      error: ok ? undefined : 'saveLongImage 事件流未触发',
      data: { shots, visible: vis, invoke: r }
    }
  })

  // ---- 档案列表：tab 切换 + 新增弹层 ----
  await runCase('flows', 'f06-profiles-tabs-add', '档案列表 tab 切换与新增弹层', async () => {
    const tabChild = diskKeyForCode('pages/profiles/index', ["activeTab.value = 'child'", 'activeTab.value = "child"'])
    const tabPet = diskKeyForCode('pages/profiles/index', ["activeTab.value = 'pet'", 'activeTab.value = "pet"'])
    const addChild = diskKeyForHandler('pages/profiles/index', 'startAddChild')
    const addPet = diskKeyForHandler('pages/profiles/index', 'startAddPet')
    const notes = []
    let maxDiff = 0
    // 1) 孩子 tab
    await gotoVerify('/pages/profiles/index', 'pages/profiles/index', 4200)
    if (tabChild) { const r = await callRenderKey(tabChild); notes.push(`孩子 tab:${invoked(r) ? 'OK' : 'FAIL'}`) }
    await sleep(1600)
    await shot('f06-profiles-tab-child', 'flows')
    // 2) 宠物 tab（切换后宠物分支才会渲染，其 invoker 才存在）
    if (tabPet) {
      const r = await callRenderKey(tabPet)
      notes.push(`宠物 tab:${invoked(r) ? 'OK' : 'FAIL'}`)
      await sleep(1800)
      await shot('f06-profiles-tab-pet', 'flows')
    } else notes.push('宠物 tab:未解析')
    // 3) 宠物 tab 下新增宠物档案
    if (addPet.length) {
      const before = await shot('f06-profiles-before-add-pet', 'flows')
      const r = await callRenderKey(addPet[0])
      notes.push(`新增宠物:${invoked(r) ? 'OK' : 'FAIL'}`)
      await sleep(2200)
      const after = await shot('f06-profiles-add-pet-sheet', 'flows')
      const diff = before && after ? pixelDiff(before, after) : -1
      notes.push(`宠物弹层差异=${diff}`)
      maxDiff = Math.max(maxDiff, diff)
    }
    // 4) 回孩子 tab 新增孩子档案
    if (addChild.length) {
      await gotoVerify('/pages/profiles/index', 'pages/profiles/index', 4000)
      if (tabChild) await callRenderKey(tabChild)
      await sleep(1400)
      const before = await shot('f06-profiles-before-add-child', 'flows')
      const r = await callRenderKey(addChild[0])
      notes.push(`新增孩子:${invoked(r) ? 'OK' : 'FAIL'}`)
      await sleep(2200)
      const after = await shot('f06-profiles-add-child-sheet', 'flows')
      const diff = before && after ? pixelDiff(before, after) : -1
      notes.push(`孩子弹层差异=${diff}`)
      maxDiff = Math.max(maxDiff, diff)
    }
    return {
      status: maxDiff > 0.02 ? 'PASS' : 'FAIL',
      note: notes.join(' | '),
      error: maxDiff > 0.02 ? undefined : '新增档案表单弹层未出现',
      data: { notes, maxDiff }
    }
  })

  // ---- 档案详情：出生日期脱敏 / 编辑入口 ----
  await runCase('flows', 'f07-profile-detail-actions', '档案详情页交互（脱敏切换/编辑/设为当前）', async () => {
    const uids = results.suites.pages?.cases?.find((c) => c.id === 'p06b-uid-discovery')?.data?.uids || []
    const uid = uids[0]
    if (!uid) return { status: 'FAIL', error: '无 uid 可用（档案发现未成功）' }
    const shots = []
    const notes = []
    let okCount = 0
    for (const [handler, shotName] of [['toggleBirth', 'f07-detail-birth-revealed'], ['openEdit', 'f07-detail-edit-sheet'], ['setCurrent', 'f07-detail-set-current']]) {
      await gotoVerify(`/pages/profile-detail/index?kind=child&uid=${uid}`, 'pages/profile-detail/index', 4200)
      const keys = diskKeyForHandler('pages/profile-detail/index', handler)
      if (!keys.length) { notes.push(`${handler}:未解析`); continue }
      const r = await callRenderKey(keys[0])
      if (invoked(r)) okCount++
      await sleep(1800)
      const vis = await probeVisible()
      notes.push(`${handler}:${invoked(r) ? 'OK' : 'FAIL'} vis=${vis.length}`)
      shots.push(await shot(shotName, 'flows'))
    }
    return {
      status: okCount >= 3 ? 'PASS' : 'FAIL',
      note: notes.join(' | '),
      error: okCount >= 3 ? undefined : `仅 ${okCount}/3 个详情页事件流触发成功`,
      data: { shots, uid, okCount }
    }
  })

  // ---- 相册页 ----
  await runCase('flows', 'f08-album-add-photos', '成长相册：新增照片弹层', async () => {
    const uids = results.suites.pages?.cases?.find((c) => c.id === 'p06b-uid-discovery')?.data?.uids || []
    const uid = uids[0]
    if (!uid) return { status: 'FAIL', error: '无 uid 可用' }
    await gotoVerify(`/pages/profile-album/index?kind=child&uid=${uid}`, 'pages/profile-album/index', 4500)
    const shots = [await shot('f08-album-empty', 'flows')]
    const keys = diskKeyForHandler('pages/profile-album/index', 'addPhotos')
    if (!keys.length) return { status: 'FAIL', error: 'addPhotos invoker 未解析', data: { shots } }
    const r = await callRenderKey(keys[0])
    await sleep(4500)
    const vis = await probeVisible()
    shots.push(await shot('f08-album-add-photos', 'flows'))
    return {
      status: invoked(r) ? 'PASS' : 'FAIL',
      note: `触发=${invoked(r)} 可见弹层=${vis.length}（相册选择器由 wx.chooseMedia 提供，模拟器下由系统弹层接管）`,
      error: invoked(r) ? undefined : 'addPhotos 事件流未触发',
      data: { shots, visible: vis, invoke: r }
    }
  })

  // ---- 会员页 ----
  await runCase('flows', 'f09-member-sheets', '会员页：权益说明/订单弹层/购买入口', async () => {
    const shots = []
    const notes = []
    let okCount = 0
    for (const [handler, shotName] of [['openBenefitDoc', 'f09-member-benefit-doc'], ['openOrders', 'f09-member-orders'], ['startPurchase', 'f09-member-purchase']]) {
      const keys = diskKeyForHandler('pages/member/index', handler)
      if (!keys.length) { notes.push(`${handler}:未解析`); continue }
      await gotoVerify('/pages/member/index', 'pages/member/index', 4000)
      const before = await shot(`${shotName}-before`, 'flows')
      const r = await callRenderKey(keys[0])
      if (invoked(r)) okCount++
      await sleep(2400)
      const vis = await probeVisible()
      const after = await shot(shotName, 'flows')
      const diff = before && after ? pixelDiff(before, after) : -1
      notes.push(`${handler}:${invoked(r) ? 'OK' : 'FAIL'} vis=${vis.length} diff=${diff}`)
    }
    return {
      status: okCount >= 3 ? 'PASS' : 'FAIL',
      note: notes.join(' | '),
      error: okCount >= 3 ? undefined : `仅 ${okCount}/3 个会员页事件流触发成功`,
      data: { shots: [], okCount, notes }
    }
  })

  // ---- 我的页：三个弹层 ----
  await runCase('flows', 'f10-me-sheets', '我的页：账户/反馈/权利中心弹层', async () => {
    const keys = diskKeyForHandler('pages/me/index', 'openSheet')
    if (!keys.length) return { status: 'FAIL', error: 'openSheet invoker 未解析' }
    const notes = []
    const names = ['account', 'feedback', 'rights']
    let maxDiff = 0
    for (let i = 0; i < Math.min(3, keys.length); i++) {
      await gotoVerify('/pages/me/index', 'pages/me/index', 5000)
      const before = await shot(`f10-me-${names[i] || i}-before`, 'flows')
      const r = await callRenderKey(keys[i])
      await sleep(2400)
      const vis = await probeVisible()
      const after = await shot(`f10-me-sheet-${names[i] || i}`, 'flows')
      const diff = before && after ? pixelDiff(before, after) : -1
      maxDiff = Math.max(maxDiff, diff)
      notes.push(`${names[i] || i}:${invoked(r) ? 'OK' : 'FAIL'} vis=${vis.length} diff=${diff}`)
    }
    return {
      status: maxDiff > 0.02 ? 'PASS' : 'FAIL',
      note: notes.join(' | '),
      error: maxDiff > 0.02 ? undefined : '三个弹层均未出现',
      data: { keys, maxDiff, notes }
    }
  })
}

// ============================================================
// main
// ============================================================
const wanted = process.argv.slice(2).filter((a) => !a.startsWith('-'))
const suites = wanted.length ? wanted : ['probe', 'pages', 'states']

log(`suites: ${suites.join(', ')}`)
if (!(await ensurePort())) { log('FATAL: automation port unavailable'); process.exit(1) }

mp = await wt(automator.connect({ wsEndpoint: WS }), 30000, 'connect')
log('connected')

// 连上后先编译一次：fresh 窗口默认停在欢迎页，此时 evaluate 会挂起
log(`compile: ${triggerCompile()}`)
await sleep(18000)

let ready = false
for (let i = 0; i < 4 && !ready; i++) {
  try {
    const r = await ev(() => ({ n: getCurrentPages().length, route: getCurrentPages().length ? getCurrentPages()[getCurrentPages().length - 1].route : '' }), 30000, 'readiness')
    log(`ready: ${JSON.stringify(r)}`)
    ready = true
  } catch (e) {
    log(`readiness try ${i + 1} failed: ${e.message}; recompile`)
    log(`compile: ${triggerCompile()}`)
    await sleep(16000)
  }
}
if (!ready) { log('FATAL: simulator never became interactive'); save(); process.exit(1) }

const t0 = Date.now()
try {
  if (suites.includes('probe')) await suiteProbe()
  if (suites.includes('pages')) await suitePages()
  if (suites.includes('flows')) await suiteFlows()
  if (suites.includes('states')) await suiteStates()
} catch (e) {
  log(`SUITE ERROR: ${e && e.message ? e.message : String(e)}`)
} finally {
  results.finishedAt = new Date().toISOString()
  results.elapsedMs = Date.now() - t0
  save()
  const all = Object.values(results.suites).flatMap((s) => s.cases)
  log(`summary: PASS=${all.filter((c) => c.status === 'PASS').length} FAIL=${all.filter((c) => c.status === 'FAIL').length} total=${all.length}`)
  try { mp.disconnect() } catch { /* ignore */ }
  process.exit(0)
}

// 确保微信开发者工具自动化链路可用（可复用）：端口 → 自动化会话 → 项目已编译。
//
// 已知环境事实（本轮实测）：
//   1. `cli auto` 之后若模拟器停在开发者工具欢迎页，automator 的 evaluate 会永久挂起
//      （连得上 ws，但任何 RPC 都不返回）；此时需要触发一次编译。
//   2. 读取页面 invoker 的函数源码（`p[eN_xx].value`）会把自动化会话打挂 —— 本脚本与
//      e2e 脚本都不得触碰该字段。
// 因此这里用「独立子进程 ping + 真实按键编译 + 轮询」三件事把会话恢复到可用态。
//
// 用法：node scripts/mp-ensure.mjs        # 静默修复，成功打印 ENSURED ok
import net from 'node:net'
import { spawn, execFileSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const PROJECT = resolve(HERE, '..', 'dist', 'dev', 'mp-weixin')
const PORT = Number(process.env.MP_PORT || 9420)
const CLI = process.env.MP_CLI || 'C:\\Program Files (x86)\\Tencent\\微信web开发者工具\\cli.bat'
const log = (m) => console.log(`[ensure] ${m}`)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function portOpen() {
  return new Promise((res) => {
    const s = net.connect(PORT, '127.0.0.1')
    const done = (v) => { try { s.destroy() } catch { /* ignore */ } res(v) }
    s.on('connect', () => done(true))
    s.on('error', () => done(false))
    setTimeout(() => done(false), 1500)
  })
}

// 每次 ping 都在独立子进程里跑：即使 evaluate 挂起也不会污染当前进程
function ping(timeout = 30000) {
  try {
    const out = execFileSync(process.execPath, [resolve(HERE, 'mp-ping.mjs')], {
      encoding: 'utf8', timeout, env: { ...process.env, MP_WS: `ws://127.0.0.1:${PORT}` }
    })
    return { ok: out.includes('PING_OK'), out: out.trim() }
  } catch (e) {
    const out = `${e.stdout || ''}${e.stderr || ''}`.trim()
    return { ok: false, out: out.split('\n').pop() || e.message }
  }
}

function compile() {
  try {
    const out = execFileSync('python', [resolve(HERE, 'dt-compile.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 40000 })
    return out.trim().split('\n').pop()
  } catch (e) {
    return 'compile-err: ' + e.message
  }
}

async function startCli() {
  log(`launching cli auto on port ${PORT}`)
  const child = spawn(CLI, ['auto', '--project', PROJECT, '--auto-port', String(PORT)], {
    stdio: 'ignore', detached: true, shell: false
  })
  child.unref()
  for (let i = 0; i < 60; i++) {
    await sleep(2000)
    if (await portOpen()) { log('automation port is up'); return true }
  }
  log('automation port did not open in 120s')
  return false
}

async function main() {
  if (!(await portOpen())) {
    if (!(await startCli())) process.exit(1)
  } else {
    log(`port ${PORT} already listening`)
  }

  // 阶段一：给初次编译留时间，轮询 ping
  for (let i = 0; i < 8; i++) {
    const p = ping(30000)
    if (p.ok) { log(`ENSURED ok (${p.out})`); process.exit(0) }
    log(`ping not ready (${i + 1}/8): ${p.out}`)
    await sleep(4000)
  }

  // 阶段二：真实按键触发编译后再轮询
  for (let round = 1; round <= 2; round++) {
    log(`compile round ${round}: ${compile()}`)
    await sleep(15000)
    for (let i = 0; i < 5; i++) {
      const p = ping(30000)
      if (p.ok) { log(`ENSURED ok after compile (${p.out})`); process.exit(0) }
      log(`ping not ready after compile (${i + 1}/5): ${p.out}`)
      await sleep(5000)
    }
  }

  log('FAILED: automation session is not usable')
  process.exit(1)
}

await main()

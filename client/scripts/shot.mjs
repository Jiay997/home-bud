// 单页截图工具（miniprogram-automator）。
// 前置：`cli auto --project dist/dev/mp-weixin --auto-port 9420` 已执行。
// 用法：node scripts/shot.mjs [url] [outName]
// 经验：截图必须让开发者工具窗口处于前台；本脚本在截图前自行激活窗口，
// 并带 75s 全局看门狗，任何一步挂起都会以非零码退出而不是无限等待。
import automator from 'miniprogram-automator'
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'walkthrough')
mkdirSync(OUT, { recursive: true })

// Git Bash 会把 /pages/... 参数转换成 Windows 路径（如 C:/Program Files/Git/pages/...），
// 这里统一从最后一个 /pages/ 片段起截取，避免无效 URL 触发运行时崩溃
function normalizePageUrl(input) {
  const match = input.match(/\/pages\/[^\\]*$/)
  return match ? match[0] : input
}

const url = normalizePageUrl(process.argv[2] || '/pages/records/index')
const name = process.argv[3] || 'shot'

const log = (msg) => console.log(`[shot ${new Date().toISOString().slice(11, 19)}] ${msg}`)
const watchdog = setTimeout(() => { log('WATCHDOG timeout, aborting'); process.exit(2) }, 75000)
watchdog.unref?.()

function activateDevtoolsWindow() {
  const ps = [
    '$p = Get-Process wechatdevtools -ErrorAction SilentlyContinue |',
    'Where-Object { $_.MainWindowTitle } | Select-Object -First 1;',
    'if ($p) { (New-Object -ComObject WScript.Shell).AppActivate($p.Id) | Out-Null; Write-Output "ok" }',
    'else { Write-Output "no-window" }'
  ].join(' ')
  try {
    const out = execFileSync('powershell', ['-NoProfile', '-Command', ps], { encoding: 'utf8', timeout: 20000 })
    log(`activate window: ${out.trim()}`)
  } catch (error) {
    log(`activate window failed: ${error.message}`)
  }
}

log(`connect ws://127.0.0.1:9420 -> ${url}`)
const mp = await automator.connect({ wsEndpoint: process.env.MP_WS || 'ws://127.0.0.1:9420' })
log('connected')
try {
  await mp.reLaunch(url)
  log('reLaunch ok')
  await new Promise((r) => setTimeout(r, 2500))
  activateDevtoolsWindow()
  await new Promise((r) => setTimeout(r, 400))
  log('screenshot...')
  await mp.screenshot({ path: resolve(OUT, `${name}.png`) })
  log(`saved ${resolve(OUT, `${name}.png`)}`)
} finally {
  clearTimeout(watchdog)
  try { mp.disconnect() } catch { /* ignore */ }
}
process.exit(0)

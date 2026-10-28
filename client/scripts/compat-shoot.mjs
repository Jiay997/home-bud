// 兼容性走查：单设备一轮「系统信息 + 核心页面截图」。
// 截图走 automator App.captureScreenshot 协议；实测窗口被遮挡时会被 Chromium 节流而超时，
// 故每次截图前先 win-focus 置前（只抢焦点约 1s，不依赖屏幕截图）。
// 用法：node scripts/compat-shoot.mjs <tag>   # 如 iphone5 / huawei80
import automator from 'miniprogram-automator'
import fs from 'node:fs'
import { execFileSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'walkthrough')
const tag = process.argv[2] || 'dev'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (m) => console.log(`[compat] ${m}`)

const watchdog = setTimeout(() => { log('WATCHDOG'); process.exit(2) }, 300000)
watchdog.unref?.()

process.on('uncaughtException', (e) => { log(`uncaughtException: ${String(e)}`) })
process.on('unhandledRejection', (e) => { log(`unhandledRejection: ${String(e)}`) })

const mp = await automator.connect({ wsEndpoint: process.env.MP_WS || 'ws://127.0.0.1:9420' })
log('connected')

function focusWindow() {
  try {
    execFileSync('python', [resolve(dirname(fileURLToPath(import.meta.url)), 'win-focus.py'), 'mp-weixin'], { encoding: 'utf8', timeout: 30000 })
    return true
  } catch (e) {
    log(`focus failed: ${e.message}`)
    return false
  }
}

async function shot(name) {
  log(`shot ${name} ...`)
  focusWindow()
  try {
    await mp.screenshot({ path: resolve(OUT, `${name}.png`) })
  } catch (e) {
    log(`shot warn ${name}: ${JSON.stringify(e).slice(0, 120)}`)
  }
}
async function goto(url, settle = 2600) {
  log(`goto -> ${url}`)
  try {
    await mp.reLaunch(url)
  } catch (e) {
    log(`reLaunch warn: ${JSON.stringify(e).slice(0, 120)}`)
  }
  await sleep(settle)
}

try {
  const info = await mp.systemInfo()
  fs.writeFileSync(resolve(OUT, `compat_${tag}_sysinfo.json`), JSON.stringify(info, null, 2))
  log(`sysinfo ${info.model} ${info.screenWidth}x${info.screenHeight} dpr=${info.pixelRatio} platform=${info.platform} bar=${info.statusBarHeight} safeBottom=${info.safeArea ? info.safeArea.bottom : '?'} SDK=${info.SDKVersion}`)

  await goto('/pages/index/index')
  await shot(`compat_${tag}_home`)
  await mp.pageScrollTo(99999)
  await sleep(900)
  await shot(`compat_${tag}_home_end`)

  await goto('/pages/qa/index')
  await shot(`compat_${tag}_qa`)

  await goto('/pages/records/index')
  await shot(`compat_${tag}_records`)

  let uid = ''
  try {
    // 生产构建会把页面 data 字段名压缩（a/b/c…），这里不依赖字段名：
    // 卡片 :key 形如 `${item_type}-${uid}`（report-<纯uuid>），取其纯 uuid 部分；
    // 报告接口 /history/report/{uid} 只认纯 uuid，带前缀会 404「资源不存在」。
    uid = await mp.evaluate(() => {
      const pages = getCurrentPages()
      const p = pages[pages.length - 1]
      const d = p.data || {}
      const re = /^(?:report|qa)-([0-9a-f-]{20,})$/i
      for (const k of Object.keys(d)) {
        const v = d[k]
        if (!Array.isArray(v)) continue
        for (const it of v) {
          if (!it || typeof it !== 'object') continue
          for (const kk of Object.keys(it)) {
            const s = it[kk]
            if (typeof s !== 'string') continue
            const m = re.exec(s)
            if (m) return m[1]
          }
        }
      }
      return ''
    })
  } catch (e) {
    log(`uid probe failed: ${e.message}`)
  }
  log(`uid=${uid || '(none)'}`)
  if (uid) {
    await goto(`/pages/report/index?uid=${uid}&history=1`, 3600)
    await shot(`compat_${tag}_report`)
  }

  await goto('/pages/me/index')
  await shot(`compat_${tag}_me`)

  await goto('/pages/member/index')
  await shot(`compat_${tag}_member`)

  await goto('/pages/assessment-intro/index')
  await shot(`compat_${tag}_assess_intro`)
} catch (e) {
  log(`ERROR: ${e && e.message ? e.message : String(e)}`)
  process.exitCode = 1
} finally {
  clearTimeout(watchdog)
  try { mp.disconnect() } catch { /* ignore */ }
  process.exit(process.exitCode || 0)
}

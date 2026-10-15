// 自动化链路健康检查（独立子进程运行，避免挂起的 RPC 污染主进程）。
// 退出码：0 可用；3 连接后 evaluate 挂起（项目未编译或会话已死）；4 连接失败。
import automator from 'miniprogram-automator'

const WS = process.env.MP_WS || 'ws://127.0.0.1:9420'
const watchdog = setTimeout(() => { console.log('PING_TIMEOUT'); process.exit(3) }, 25000)
watchdog.unref?.()

let mp
try {
  mp = await automator.connect({ wsEndpoint: WS })
} catch (e) {
  console.log('PING_CONNECT_FAIL ' + e.message)
  process.exit(4)
}

try {
  const r = await mp.evaluate(() => {
    const pages = getCurrentPages()
    return { count: pages.length, route: pages.length ? pages[pages.length - 1].route : '' }
  })
  console.log('PING_OK ' + JSON.stringify(r))
  clearTimeout(watchdog)
  try { mp.disconnect() } catch { /* ignore */ }
  process.exit(0)
} catch (e) {
  console.log('PING_EVAL_FAIL ' + e.message)
  process.exit(3)
}

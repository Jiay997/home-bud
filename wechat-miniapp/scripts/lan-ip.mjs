// 把开发机当前的局域网 IP 写入 .env.development.local（真机预览/调试用，不提交版本库）。
// dev 构建前自动执行：换网络后地址自动刷新，避免真机连到过期 IP。
// 主地址用 LAN_IP 或默认路由 IP；其余可用网卡地址一并写入 VITE_API_BASE_URLS，
// 供小程序运行时按序探测（开发工具可经 127.0.0.1 回环自愈）。
// 可用 LAN_IP=192.168.x.x 覆盖自动探测结果。
import { createSocket } from 'node:dgram'
import { writeFileSync } from 'node:fs'
import { networkInterfaces } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const API_PORT = 8000
const LOOPBACK_URL = `http://127.0.0.1:${API_PORT}/api/v1`
const ENV_FILE = resolve(dirname(fileURLToPath(import.meta.url)), '..', '.env.development.local')

function usableIpv4(address) {
  if (!address) return false
  if (address.startsWith('169.254.')) return false
  if (address.startsWith('172.17.')) return false // 本机 WSL vEthernet
  if (address.startsWith('172.19.')) return false // 本机 WSL vEthernet
  return true
}

function collectInterfaceIps() {
  const ips = []
  for (const addrs of Object.values(networkInterfaces())) {
    for (const addr of addrs || []) {
      if (addr.family !== 'IPv4' || addr.internal) continue
      if (!usableIpv4(addr.address)) continue
      if (!ips.includes(addr.address)) ips.push(addr.address)
    }
  }
  return ips
}

function detectRouteIp() {
  return new Promise((done) => {
    const socket = createSocket('udp4')
    const fallback = () => {
      try { socket.close() } catch { /* ignore */ }
      done('')
    }
    socket.once('error', fallback)
    try {
      socket.connect(80, '223.5.5.5', () => {
        const ip = socket.address().address
        socket.close()
        done(ip)
      })
    } catch {
      fallback()
    }
  })
}

const interfaceIps = collectInterfaceIps()
const routeIp = process.env.LAN_IP || (await detectRouteIp())
const primary = routeIp && usableIpv4(routeIp) ? routeIp : interfaceIps[0] || ''

if (!primary) {
  console.log('[lan-ip] 未探测到局域网 IP，保留现有 .env.development.local')
  process.exit(0)
}

const urls = [primary, ...interfaceIps.filter((ip) => ip !== primary)].map((ip) => `http://${ip}:${API_PORT}/api/v1`)
if (!urls.includes(LOOPBACK_URL)) urls.push(LOOPBACK_URL)

writeFileSync(
  ENV_FILE,
  [
    '# 由 scripts/lan-ip.mjs 自动生成（npm run dev:mp-weixin 前刷新），不提交版本库。',
    '# 真机预览/真机调试要求手机与开发机在同一局域网；换网络后重新执行 dev 构建即可。',
    '# VITE_API_BASE_URLS 供小程序运行时按序探测，选中首个可达地址。',
    `VITE_API_BASE_URL=${urls[0]}`,
    `VITE_API_BASE_URLS=${urls.join(',')}`,
    ''
  ].join('\n')
)
console.log(`[lan-ip] VITE_API_BASE_URL=${urls[0]}`)
console.log(`[lan-ip] VITE_API_BASE_URLS=${urls.join(',')}`)

try {
  const res = await fetch(`${urls[0]}/health`, { signal: AbortSignal.timeout(2500) })
  console.log(`[lan-ip] 后端自检 ${urls[0]}/health -> ${res.status}`)
} catch (error) {
  console.log(`[lan-ip] 提示：后端在该地址不可达（${error.message}），真机将连不上；先启动后端再编译。`)
}

# =====================================================================
# Babe宝伴 - 一键停止脚本 (stop.ps1)
#
# 功能：安全终止后端(8000)、用户端 H5(5174) 与后台管理端(5175) 相关进程，
#       并验证无残留监听。
# 说明：V3.0 起前端拆分为 client/（H5，5174）与 admin-web/（5175），
#       旧版单站点前端 5173 一并兼容清理，避免历史进程残留。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
# =====================================================================

$ErrorActionPreference = "Continue"

# 端口清单：后端 / 用户端 H5 / 后台管理端 / 旧版前端（兼容清理）
$backendPort = 8000
$clientPort = 5174
# D-17：后台端口支持 ADMIN_PORT 覆盖，默认 5175
$adminPort = if ($env:ADMIN_PORT) { [int]$env:ADMIN_PORT } else { 5175 }
$legacyFrontendPort = 5173

function Stop-PortProcess {
    # 终止占用指定端口的进程（含子进程树）。
    param([int]$port, [string]$name)
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Host "  - $name (端口 $port)：无运行中进程" -ForegroundColor Gray
        return
    }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        if ($procId -and $procId -ne 0) {
            try {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($proc) {
                    # 优雅终止进程树（taskkill /T 连带子进程）
                    & taskkill /PID $procId /T /F 2>$null | Out-Null
                    Write-Host "  - $name (端口 $port)：已终止进程 $($proc.ProcessName) (PID $procId)" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "  - $name：终止 PID $procId 失败：$_" -ForegroundColor Red
            }
        }
    }
}

Write-Host "停止Babe宝伴服务 ..."

# 1. 终止两端前端 Vite（用户端 5174 / 管理端 5175）与旧版 5173
Stop-PortProcess -port $clientPort -name "用户端 H5 Vite"
Stop-PortProcess -port $adminPort -name "后台管理端 Vite"
Stop-PortProcess -port $legacyFrontendPort -name "旧版前端 Vite(兼容)"

# 2. 终止后端 uvicorn（8000）
Stop-PortProcess -port $backendPort -name "后端 FastAPI"

# 3. 兜底：清理残留进程（仅限本项目路径，避免误杀其他业务进程：
#    命令行需同时包含 HomeBud 项目特征与 app.main / vite 特征）
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='node.exe' OR Name='cmd.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "HomeBud" -and $_.CommandLine -match "app\.main:app|vite" } |
    ForEach-Object {
        try {
            & taskkill /PID $_.ProcessId /T /F 2>$null | Out-Null
            Write-Host "  - 兜底清理：PID $($_.ProcessId) ($($_.CommandLine.Substring(0, [Math]::Min(60, $_.CommandLine.Length))))" -ForegroundColor DarkYellow
        } catch { }
    }

# 4. 验证无残留监听
Start-Sleep -Seconds 2
$ports = @($backendPort, $clientPort, $adminPort, $legacyFrontendPort)
$left = $ports | Where-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue }
if ($left) {
    Write-Host "存在残留监听，已强制再次清理 ..." -ForegroundColor Red
    foreach ($port in $left) { Stop-PortProcess -port $port -name "残留监听" }
}

$leftAgain = $ports | Where-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue }
if (-not $leftAgain) {
    Write-Host "全部服务已停止，端口 $($ports -join ' / ') 无残留监听。" -ForegroundColor Green
    exit 0
} else {
    Write-Host "仍有残留监听，请手工检查：$($leftAgain -join ', ')" -ForegroundColor Red
    exit 1
}

# =====================================================================
# 小光景 - 一键停止脚本 (stop.ps1)
# 功能：安全终止后端(8000)与前端(5173)全部相关进程，并验证无残留监听。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
# =====================================================================

$ErrorActionPreference = "Continue"

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

Write-Host "停止小光景服务 ..." 

# 1. 终止前端 Vite（5173）
Stop-PortProcess -port 5173 -name "前端 Vite"

# 2. 终止后端 uvicorn（8000）
Stop-PortProcess -port 8000 -name "后端 FastAPI"

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
$beLeft = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$feLeft = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($beLeft -or $feLeft) {
    Write-Host "存在残留监听，已强制再次清理 ..." -ForegroundColor Red
    if ($beLeft) { Stop-PortProcess -port 8000 -name "后端(残留)" }
    if ($feLeft) { Stop-PortProcess -port 5173 -name "前端(残留)" }
}

$beLeft2 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$feLeft2 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if (-not $beLeft2 -and -not $feLeft2) {
    Write-Host "全部服务已停止，端口 8000 / 5173 无残留监听。" -ForegroundColor Green
    exit 0
} else {
    Write-Host "仍有残留监听，请手工检查：8000=$([bool]$beLeft2) 5173=$([bool]$feLeft2)" -ForegroundColor Red
    exit 1
}

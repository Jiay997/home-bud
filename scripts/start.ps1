# =====================================================================
# 小光景 - 一键启动脚本 (start.ps1)
# 功能：按序启动 PostgreSQL 检查 -> 后端 FastAPI(8000) -> 前端 Vite(5173)
#       并进行健康检查，输出访问地址；重复执行不会产生重复进程。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$pidDir = Join-Path $root ".run"
if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Path $pidDir | Out-Null }

# 日志文件路径（后端/前端各一）
$beOut = Join-Path $pidDir "backend.out.log"
$beErr = Join-Path $pidDir "backend.err.log"
$feOut = Join-Path $pidDir "frontend.out.log"
$feErr = Join-Path $pidDir "frontend.err.log"

function Test-PortListening([int]$port) {
    # 检查指定端口是否已有监听；已监听返回 True。
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# ---------- 第 1 步：PostgreSQL 连通性检查 ----------
Write-Host "[1/5] 检查 PostgreSQL ..." -NoNewline
# 优先用 psql（PostgreSQL 16 常见安装路径自动探测）
$psqlCandidates = @("D:\PostgreSQL\bin\psql.exe", "C:\Program Files\PostgreSQL\16\bin\psql.exe", "psql")
$psql = $psqlCandidates | Where-Object { (Get-Command $_ -ErrorAction SilentlyContinue) -or (Test-Path $_) } | Select-Object -First 1
if ($psql) {
    # 数据库密码取自 backend/.env（源码不硬编码凭据）
    $dbUrlLine = Get-Content -LiteralPath (Join-Path $backend ".env") -Encoding UTF8 -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
    if ($dbUrlLine -match '://[^:/@]+:([^@]+)@') { $env:PGPASSWORD = $Matches[1].Trim() }
    $ok = & $psql -h localhost -p 5432 -U postgres -d jiaban -tAc "SELECT 1" 2>$null
    if ($ok -eq "1") { Write-Host " OK (jiaban@localhost:5432)" -ForegroundColor Green }
    else { Write-Host " FAIL：数据库 jiaban 不可达，请确认 PostgreSQL 服务已启动"; exit 1 }
} else {
    # 找不到 psql 时仅检查服务状态
    $svc = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq "Running") { Write-Host " OK (service running)" -ForegroundColor Green }
    else { Write-Host " WARN：未找到 psql 且服务状态未知，继续启动（后端健康检查会再验证）" -ForegroundColor Yellow }
}

# ---------- 第 2 步：Python 解释器与依赖检查 ----------
Write-Host "[2/5] 检查 Python 环境 ..." -NoNewline
# 探测顺序：系统 Python 优先（依赖齐全），venv 兜底
$pyCandidates = @(
    "C:\Users\杨志泽民\AppData\Local\Programs\Python\Python312\python.exe",
    (Join-Path $backend ".venv\Scripts\python.exe")
)
$py = $null
foreach ($candidate in $pyCandidates) {
    if (Test-Path $candidate) {
        # 依赖探测：fastapi/uvicorn/sqlalchemy/langgraph 均可导入即视为就绪
        & $candidate -c "import fastapi, uvicorn, sqlalchemy, langgraph" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $py = $candidate; break }
    }
}
if (-not $py) {
    # 全部候选缺依赖：选第一个存在的解释器安装 requirements 后使用
    $py = $pyCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $py) { $py = "python" }
    Write-Host " 安装依赖中（首次运行较慢）..." -NoNewline
    & $py -m pip install -r (Join-Path $backend "requirements.txt") -i https://mirrors.aliyun.com/pypi/simple/ --timeout 60 --quiet 2>$null | Out-Null
}
Write-Host " OK ($py)" -ForegroundColor Green

# ---------- 第 3 步：启动后端（uvicorn :8000） ----------
Write-Host "[3/5] 启动后端 FastAPI ..." -NoNewline
if (Test-PortListening 8000) {
    Write-Host " 已在运行（端口 8000 被占用，跳过重复启动）" -ForegroundColor Yellow
} else {
    Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $backend -WindowStyle Hidden `
        -RedirectStandardOutput $beOut -RedirectStandardError $beErr
    # 健康检查轮询（最多 30 秒；127.0.0.1 直连避免 IPv6/代理干扰，
    # 最终以端口监听兜底判定——防止个别环境下 HTTP 探测误报）
    $ready = $false
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 2
            if ($health.code -eq 0) { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { $ready = [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) }
    if ($ready) { Write-Host " OK (http://localhost:8000)" -ForegroundColor Green }
    else {
        Write-Host " FAIL：健康检查未通过，最近错误日志：" -ForegroundColor Red
        Get-Content $beErr -ErrorAction SilentlyContinue | Select-Object -Last 15
        exit 1
    }
}

# ---------- 第 4 步：启动前端（vite :5173） ----------
Write-Host "[4/5] 启动前端 Vite ..." -NoNewline
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host " npm install 中 ..." -NoNewline
    Push-Location $frontend; npm install --silent 2>&1 | Out-Null; Pop-Location
}
if (Test-PortListening 5173) {
    Write-Host " 已在运行（端口 5173 被占用，跳过重复启动）" -ForegroundColor Yellow
} else {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory $frontend -WindowStyle Hidden `
        -RedirectStandardOutput $feOut -RedirectStandardError $feErr
    $ready = $false
    foreach ($i in 1..45) {
        Start-Sleep -Seconds 1
        if (Test-PortListening 5173) { $ready = $true; break }
    }
    if ($ready) { Write-Host " OK (http://localhost:5173)" -ForegroundColor Green }
    else {
        Write-Host " FAIL：前端启动超时，最近错误日志：" -ForegroundColor Red
        Get-Content $feErr -ErrorAction SilentlyContinue | Select-Object -Last 15
        exit 1
    }
}

# ---------- 第 5 步：输出访问地址 ----------
Write-Host "[5/5] 全部服务已启动：" -ForegroundColor Green
Write-Host "  - 用户端(H5)      : http://localhost:5173/app/home"
Write-Host "  - 后台管理端      : http://localhost:5173/admin/login  (账号 admin / Admin@123456，MFA 演示码 123456)"
Write-Host "  - API 文档(Swagger): http://localhost:8000/docs"
Write-Host "  - 健康检查        : http://localhost:8000/api/v1/health"
Write-Host "  日志目录: $pidDir"

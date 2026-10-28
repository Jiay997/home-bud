# =====================================================================
# Babe宝伴 - 一键启动脚本 (start.ps1)
#
# 架构（V3.0 起，两站点 + 一后端）：
#   backend/     FastAPI + uvicorn           http://localhost:8000
#   client/      uni-app 跨端工程（H5 形态）  http://localhost:5174/app/
#   admin-web/   后台管理端（Element Plus）   http://localhost:5175/admin/login（可用 ADMIN_PORT 覆盖）
#
# 说明：旧版单站点 frontend/ 已拆分为 client/ 与 admin-web/，
#       本脚本按新架构启动并按端口判定避免重复启动。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\start.ps1 [-SkipClient] [-SkipAdmin]
# 参数：-SkipClient 只启动后端与管理端；-SkipAdmin 只启动后端与用户端
# =====================================================================

param(
    [switch]$SkipClient,
    [switch]$SkipAdmin
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$client = Join-Path $root "client"
$adminWeb = Join-Path $root "admin-web"
$pidDir = Join-Path $root ".run"
if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Path $pidDir | Out-Null }

# 端口分配（与 client/vite.config.ts、admin-web/vite.config.ts 保持一致）
$backendPort = 8000
$clientPort = 5174
$adminPort = if ($env:ADMIN_PORT) { [int]$env:ADMIN_PORT } else { 5175 }

# 日志文件路径（后端 / H5 / 管理端各一）
$beOut = Join-Path $pidDir "backend.out.log"
$beErr = Join-Path $pidDir "backend.err.log"
$clientOut = Join-Path $pidDir "client-h5.out.log"
$clientErr = Join-Path $pidDir "client-h5.err.log"
$adminOut = Join-Path $pidDir "admin-web.out.log"
$adminErr = Join-Path $pidDir "admin-web.err.log"

function Test-PortListening([int]$port) {
    # 检查指定端口是否已有监听；已监听返回 True。
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Ensure-NodeModules([string]$dir, [string]$name) {
    # 依赖缺失时安装（首次运行较慢）
    if (-not (Test-Path (Join-Path $dir "node_modules"))) {
        Write-Host " $name npm install 中 ..." -NoNewline
        Push-Location $dir
        try { npm install --silent 2>&1 | Out-Null } finally { Pop-Location }
    }
}

function Start-Vite([string]$dir, [string]$script, [int]$port, [string]$name, [string]$outLog, [string]$errLog) {
    # 启动 Vite（已监听则跳过），最多等待 60 秒
    if (Test-PortListening $port) {
        # D-17：端口被占用时区分「本项目已在运行」与「被其他项目占用」。
        # 后者必须显式失败（并提示 ADMIN_PORT），不能当作启动成功。
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        $proc = if ($conn) { Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue } else { $null }
        $cmdLine = if ($proc) { [string]$proc.CommandLine } else { "" }
        if ($cmdLine -and $cmdLine.ToLower().Contains($dir.ToLower())) {
            Write-Host " 已在运行（端口 $port 被本项目占用，跳过重复启动）" -ForegroundColor Yellow
            return $true
        }
        Write-Host " FAIL：端口 $port 已被其他进程占用，无法启动$name。" -ForegroundColor Red
        Write-Host "        占用进程: $cmdLine" -ForegroundColor DarkGray
        Write-Host "        解决：设置环境变量 ADMIN_PORT 指定其他端口后重试，例如 `$env:ADMIN_PORT=5177; .\scripts\start.ps1" -ForegroundColor Yellow
        return $false
    }
    # 端口经环境变量传给 vite.config.ts（与 ADMIN_PORT 保持一致）
    $env:ADMIN_PORT = "$port"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run $script" `
        -WorkingDirectory $dir -WindowStyle Hidden `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    foreach ($i in 1..60) {
        Start-Sleep -Seconds 1
        if (Test-PortListening $port) { return $true }
    }
    Write-Host " FAIL：$name 启动超时，最近错误日志：" -ForegroundColor Red
    Get-Content $errLog -ErrorAction SilentlyContinue | Select-Object -Last 15
    return $false
}

# ---------- 第 1 步：PostgreSQL 连通性检查 ----------
Write-Host "[1/5] 检查 PostgreSQL ..." -NoNewline
# 优先用 psql（PostgreSQL 16 常见安装路径自动探测）
$psqlCandidates = @("D:\PostgreSQL\bin\psql.exe", "C:\Program Files\PostgreSQL\16\bin\psql.exe", "psql")
$psql = $psqlCandidates | Where-Object { (Get-Command $_ -ErrorAction SilentlyContinue) -or (Test-Path $_) } | Select-Object -First 1
# 数据库地址与凭据取自 backend/.env（源码不硬编码凭据）；缺失时回退本机默认实例
$dbHost = "localhost"; $dbPort = 5432; $dbUser = "postgres"; $dbName = "jiaban"
$envFile = Join-Path $backend ".env"
if (Test-Path $envFile) {
    $dbUrlLine = Get-Content -LiteralPath $envFile -Encoding UTF8 |
        Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
    if ($dbUrlLine -match '://([^:/@]+):([^@]+)@([^:/]+):(\d+)/([^?\s]+)') {
        $dbUser = $Matches[1]; $env:PGPASSWORD = $Matches[2]; $dbHost = $Matches[3]; $dbPort = $Matches[4]; $dbName = $Matches[5]
    }
}
if ($psql) {
    $ok = & $psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -tAc "SELECT 1" 2>$null
    if ($ok -eq "1") { Write-Host " OK ($dbName@${dbHost}:$dbPort)" -ForegroundColor Green }
    else { Write-Host " FAIL：数据库 $dbName 不可达（$dbHost`:$dbPort），请确认 PostgreSQL 服务已启动"; exit 1 }
} else {
    # 找不到 psql 时仅检查服务状态
    $svc = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq "Running") { Write-Host " OK (service running)" -ForegroundColor Green }
    else { Write-Host " WARN：未找到 psql 且服务状态未知，继续启动（后端健康检查会再验证）" -ForegroundColor Yellow }
}

# ---------- 第 2 步：Python 解释器与依赖检查 ----------
Write-Host "[2/5] 检查 Python 环境 ..." -NoNewline
# 探测顺序：venv 优先（依赖隔离），系统 Python 兜底
$pyCandidates = @(
    (Join-Path $backend ".venv\Scripts\python.exe"),
    "C:\Users\杨志泽民\AppData\Local\Programs\Python\Python312\python.exe"
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
if (Test-PortListening $backendPort) {
    Write-Host " 已在运行（端口 $backendPort 被占用，跳过重复启动）" -ForegroundColor Yellow
} else {
    Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$backendPort" `
        -WorkingDirectory $backend -WindowStyle Hidden `
        -RedirectStandardOutput $beOut -RedirectStandardError $beErr
    # 健康检查轮询（最多 30 秒；127.0.0.1 直连避免 IPv6/代理干扰，
    # 最终以端口监听兜底判定——防止个别环境下 HTTP 探测误报）
    $ready = $false
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$backendPort/api/v1/health" -TimeoutSec 2
            if ($health.code -eq 0) { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { $ready = [bool](Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue) }
    if ($ready) { Write-Host " OK (http://localhost:$backendPort)" -ForegroundColor Green }
    else {
        Write-Host " FAIL：健康检查未通过，最近错误日志：" -ForegroundColor Red
        Get-Content $beErr -ErrorAction SilentlyContinue | Select-Object -Last 15
        exit 1
    }
}

# ---------- 第 4 步：启动两端前端 ----------
if (-not $SkipClient) {
    Write-Host "[4/5] 启动用户端 H5（client，端口 $clientPort）..." -NoNewline
    Ensure-NodeModules $client "用户端"
    if (Start-Vite $client "dev:h5" $clientPort "用户端 H5" $clientOut $clientErr) {
        Write-Host " OK (http://localhost:$clientPort/app/)" -ForegroundColor Green
    } else { exit 1 }
} else {
    Write-Host "[4/5] 跳过用户端 H5（-SkipClient）" -ForegroundColor DarkGray
}

if (-not $SkipAdmin) {
    Write-Host "[4/5] 启动后台管理端（admin-web，端口 $adminPort）..." -NoNewline
    Ensure-NodeModules $adminWeb "管理端"
    if (Start-Vite $adminWeb "dev" $adminPort "后台管理端" $adminOut $adminErr) {
        Write-Host " OK (http://localhost:$adminPort/admin/login)" -ForegroundColor Green
    } else { exit 1 }
} else {
    Write-Host "[4/5] 跳过后台管理端（-SkipAdmin）" -ForegroundColor DarkGray
}

# ---------- 第 5 步：输出访问地址 ----------
Write-Host "[5/5] 全部服务已启动：" -ForegroundColor Green
if (-not $SkipClient) {
    Write-Host "  - 用户端(H5)       : http://localhost:$clientPort/app/"
}
if (-not $SkipAdmin) {
    Write-Host "  - 后台管理端       : http://localhost:$adminPort/admin/login  (账号 admin / Admin@123456，MFA 演示码 123456)"
}
Write-Host "  - API 文档(Swagger): http://localhost:$backendPort/docs"
Write-Host "  - 健康检查         : http://localhost:$backendPort/api/v1/health"
Write-Host "  日志目录: $pidDir"
Write-Host ""
Write-Host "提示：生产形态由 deploy/docker-compose.yml 提供（nginx 单容器托管 /app/ 与 /admin/，端口 80）。" -ForegroundColor DarkGray

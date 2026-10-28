# =====================================================================
# Babe宝伴 - 服务状态检查脚本 (status.ps1)
# 功能：显示后端/前端运行状态、端口占用、数据库连通与健康检查详情。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\status.ps1
# =====================================================================

function Format-Status($ok) {
    # 布尔值转状态标记（正常/已停止）。
    if ($ok) { return "运行中" } else { return "已停止" }
}

Write-Host "========== Babe宝伴服务状态 ==========" 

# --- 数据库 ---
$dbOk = $false
$psql = @("D:\PostgreSQL\bin\psql.exe", "C:\Program Files\PostgreSQL\16\bin\psql.exe", "psql") |
    Where-Object { (Get-Command $_ -ErrorAction SilentlyContinue) -or (Test-Path $_) } | Select-Object -First 1
if ($psql) {
    # 数据库密码取自 backend/.env（源码不硬编码凭据）
    $envFile = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) "backend") ".env"
    $dbUrlLine = Get-Content -LiteralPath $envFile -Encoding UTF8 -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
    if ($dbUrlLine -match '://[^:/@]+:([^@]+)@') { $env:PGPASSWORD = $Matches[1].Trim() }
    $r = & $psql -h localhost -p 5432 -U postgres -d jiaban -tAc "SELECT 1" 2>$null
    $dbOk = ($r -eq "1")
}
$dbSvc = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host ("PostgreSQL 服务 : {0}  数据库 jiaban 连接: {1}" -f $(if ($dbSvc) { $dbSvc.Status } else { "未知" }), (Format-Status $dbOk))

# --- 后端 8000 ---
$beListen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
# 注意：参数模式下 "[bool]$beListen" 会被解析为字面字符串而非类型转换（恒为真值导致误报），
# 必须加括号强制表达式求值后再传入 Format-Status。
Write-Host ("后端 FastAPI    : {0} (端口 8000)" -f (Format-Status ([bool]$beListen)))
if ($beListen) {
    try {
        $health = Invoke-RestMethod "http://localhost:8000/api/v1/health" -TimeoutSec 3
        Write-Host ("  健康: code={0}  DB={1}  模型白名单={2}  llm_mock={3}" -f `
            $health.code, $health.data.db_connected, ($health.data.model_whitelist -join ","), $health.data.llm_mock)
        Write-Host ("  Swagger: http://localhost:8000/docs")
    } catch {
        Write-Host "  健康检查失败: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# --- 前端：用户端 H5（5174）与后台管理端（5175）---
# V3.0 起前端拆分为 client/（5174，base=/app/）与 admin-web/（5175，base=/admin/）
$clientListen = Get-NetTCPConnection -LocalPort 5174 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host ("用户端 H5       : {0} (端口 5174)" -f (Format-Status ([bool]$clientListen)))
if ($clientListen) {
    Write-Host "  访问: http://localhost:5174/app/"
}

# D-17：后台端口支持 ADMIN_PORT 覆盖，默认 5175
$adminPort = if ($env:ADMIN_PORT) { [int]$env:ADMIN_PORT } else { 5175 }
$adminListen = Get-NetTCPConnection -LocalPort $adminPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host ("后台管理端      : {0} (端口 {1})" -f (Format-Status ([bool]$adminListen)), $adminPort)
if ($adminListen) {
    Write-Host "  访问: http://localhost:$adminPort/admin/login"
}

Write-Host "=================================="

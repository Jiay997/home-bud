﻿# =====================================================================
# 小光景 - 数据库恢复脚本 (restore_db.ps1)
# 功能：使用 pg_restore 将 pg_dump -Fc 生成的 .dump 备份恢复到指定库
#       （--clean --if-exists --no-owner 覆盖式恢复）。恢复成功后向备份
#       所在目录的 restore_log.txt 追加一行留痕。
# 密码：不硬编码——优先取环境变量 PGPASSWORD；否则解析 backend\.env
#       中 DATABASE_URL（形如 postgresql+psycopg2://user:pwd@host:port/db），
#       解析失败报错退出。环境变量优先于 .env。
# 参数：
#   -BackupFile  备份文件路径（必填，需已存在）
#   -DbName      目标库名（默认 jiaban）
#   -DbUser/-DbHost/-DbPort  连接参数（默认 postgres/localhost/5432）
#   -PgBin       pg_restore 所在 bin 目录（可选；缺省按 PATH →
#                C:\Program Files\PostgreSQL\*\bin（取版本最高）→
#                D:\PostgreSQL\bin（本机实际安装位置，与 start.ps1 一致）探测）
#   -Force       跳过交互确认（用于自动化场景）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\restore_db.ps1 -BackupFile d:\HomeBud\backups\jiaban_yyyyMMdd_HHmmss.dump
#       powershell -ExecutionPolicy Bypass -File scripts\restore_db.ps1 -BackupFile ... -Force
# 退出码：0=恢复成功；1=失败（缺参/备份文件不存在/找不到 pg_restore/用户取消/pg_restore 报错）
# 注意：--clean 会先删除目标库中已有对象再导入，属覆盖式恢复，请谨慎执行！
# =====================================================================

param(
    [string]$BackupFile = "",      # 备份文件路径（必填）
    [string]$DbName = "jiaban",    # 目标数据库名
    [string]$DbUser = "postgres",  # 数据库登录用户
    [string]$DbHost = "localhost", # 数据库主机
    [int]$DbPort = 5432,           # 数据库端口
    [string]$PgBin = "",           # pg_restore 所在目录（可选，优先于 PATH 探测）
    [switch]$Force                 # 跳过交互确认
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"


<#
.SYNOPSIS
    解析数据库连接密码：环境变量 PGPASSWORD 优先，其次解析 backend\.env 的 DATABASE_URL。
.RETURNS
    string：明文数据库密码。
.EXCEPTION
    .env 不存在或其中无合法 DATABASE_URL 行时，输出中文错误并以退出码 1 结束脚本。
#>
function Get-DbPassword {
    if ($env:PGPASSWORD) { return $env:PGPASSWORD }
    $envFile = Join-Path $backend ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        Write-Host "FAIL：未设置环境变量 PGPASSWORD，且找不到 $envFile，无法获取数据库密码" -ForegroundColor Red
        exit 1
    }
    $line = Get-Content -LiteralPath $envFile -Encoding UTF8 -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
    # 匹配形如 postgresql+psycopg2://user:pwd@host:port/db 中的密码段
    if ($line -match '://[^:/@]+:([^@]+)@') { return $Matches[1].Trim() }
    Write-Host "FAIL：$envFile 中未找到合法的 DATABASE_URL 行，无法解析数据库密码" -ForegroundColor Red
    exit 1
}


<#
.SYNOPSIS
    按优先级探测 PostgreSQL 命令行工具完整路径：-PgBin 指定目录 → PATH → C:\Program Files\PostgreSQL\*\bin（取版本最高）。
.PARAMETER ToolName
    工具名（不含 .exe），如 pg_dump / pg_restore。
.PARAMETER BinDir
    显式指定的 bin 目录（对应 -PgBin 参数，可为空）。
.RETURNS
    string：工具可执行文件完整路径。
.EXCEPTION
    各候选均未命中时输出中文安装/配置指引并以退出码 1 结束脚本。
#>
function Resolve-PgTool {
    param(
        [string]$ToolName,   # 工具名（如 pg_restore）
        [string]$BinDir = "" # 优先探测目录（-PgBin），可为空
    )
    if ($BinDir) {
        $p = Join-Path $BinDir "$ToolName.exe"
        if (Test-Path -LiteralPath $p) { return $p }
        Write-Host "FAIL：-PgBin 指定目录中未找到 $ToolName.exe：$BinDir" -ForegroundColor Red
        exit 1
    }
    # 1) PATH 探测
    $cmd = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    # 2) 默认安装目录探测，按数字版本号取最高（避免字符串排序把 9 排在 16 之后）
    $hit = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "$ToolName.exe") } |
        Sort-Object { $n = 0; if ([int]::TryParse($_.Name, [ref]$n)) { $n } else { 0 } } -Descending |
        Select-Object -First 1
    if ($hit) { return (Join-Path $hit.FullName "$ToolName.exe") }
    # 3) 本机实际安装位置兜底（与 start.ps1 候选一致）
    if (Test-Path -LiteralPath "D:\PostgreSQL\bin\$ToolName.exe") { return "D:\PostgreSQL\bin\$ToolName.exe" }
    Write-Host "FAIL：未找到 $ToolName.exe，请任选其一处理：`n  1) 加 -PgBin 指定 PostgreSQL bin 目录；`n  2) 将 bin 目录加入 PATH；`n  3) 安装 PostgreSQL（默认 C:\Program Files\PostgreSQL\<版本>\bin）" -ForegroundColor Red
    exit 1
}


# ---------- [1/4] 校验参数与备份文件 ----------
Write-Host "[1/4] 校验参数与备份文件 ..." -NoNewline
if (-not $BackupFile) {
    Write-Host " FAIL" -ForegroundColor Red
    Write-Host "FAIL：缺少必填参数 -BackupFile（pg_dump -Fc 生成的 .dump 文件路径）" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
    Write-Host " FAIL" -ForegroundColor Red
    Write-Host "FAIL：备份文件不存在：$BackupFile" -ForegroundColor Red
    exit 1
}
Write-Host " OK（$BackupFile）" -ForegroundColor Green

# ---------- [2/4] 探测 pg_restore ----------
Write-Host "[2/4] 探测 pg_restore ..." -NoNewline
$pgRestore = Resolve-PgTool -ToolName "pg_restore" -BinDir $PgBin
Write-Host " OK（$pgRestore）" -ForegroundColor Green

# ---------- [3/4] 恢复确认（-Force 跳过） ----------
if (-not $Force) {
    Write-Host "警告：将使用 --clean 覆盖恢复到 [$DbUser@$($DbHost):$($DbPort)/$DbName]，目标库现有对象会被删除后重建！" -ForegroundColor Yellow
    $ans = Read-Host "确认继续恢复？(y=继续 / n=取消)"
    if ($ans -notin @("y", "n")) {
        Write-Host "FAIL：输入无效（仅接受 y 或 n），已拒绝执行恢复" -ForegroundColor Red
        exit 1
    }
    if ($ans -ne "y") {
        Write-Host "已取消恢复（未对数据库做任何修改）" -ForegroundColor Yellow
        exit 1
    }
}

# ---------- [4/4] 执行 pg_restore ----------
Write-Host "[4/4] 恢复 $BackupFile -> $DbName@$($DbHost):$($DbPort) ..."
$env:PGPASSWORD = Get-DbPassword
$sw = [System.Diagnostics.Stopwatch]::StartNew()
# 原生命令写 stderr 不应中断脚本，临时放宽错误偏好
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $pgRestore -h $DbHost -p $DbPort -U $DbUser -d $DbName --clean --if-exists --no-owner $BackupFile
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEap
$sw.Stop()
if ($code -ne 0) {
    Write-Host "FAIL：pg_restore 退出码 $code，恢复未完成，请检查上方错误输出" -ForegroundColor Red
    exit 1
}

# ---------- 留痕 + 摘要 ----------
$logFile = Join-Path (Split-Path -Parent $BackupFile) "restore_log.txt"
Add-Content -LiteralPath $logFile -Value ("{0}  {1}  ->  {2}@{3}:{4}/{5}  ok" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), (Split-Path -Leaf $BackupFile), $DbUser, $DbHost, $DbPort, $DbName) -Encoding UTF8
Write-Host ""
Write-Host "===== 恢复完成 =====" -ForegroundColor Green
Write-Host "  - 备份  : $BackupFile"
Write-Host "  - 目标  : $DbName@$($DbHost):$($DbPort)"
Write-Host ("  - 耗时  : {0}s" -f [math]::Round($sw.Elapsed.TotalSeconds, 1))
Write-Host "  - 日志  : $logFile"
exit 0

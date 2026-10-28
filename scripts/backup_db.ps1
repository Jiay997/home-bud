﻿# =====================================================================
# Babe宝伴 - 数据库备份容灾脚本 (backup_db.ps1)
# 功能：调用 pg_dump 对本地 PostgreSQL 指定库做 -Fc 自定义格式备份，
#       生成 <库名>_yyyyMMdd_HHmmss.dump；成功后向 OutDir\backup_log.txt
#       追加一行留痕（时间戳 + 文件名 + 大小MB + ok），并按文件名轮转
#       仅保留最新 -Keep 份 .dump（多余删除并记日志）。
# 密码：不硬编码——优先取环境变量 PGPASSWORD；否则解析 backend\.env
#       中 DATABASE_URL（形如 postgresql+psycopg2://user:pwd@host:port/db），
#       解析失败报错退出。环境变量优先于 .env。
# 参数：
#   -DbName   目标库名（默认 jiaban）
#   -OutDir   备份输出目录（默认 d:\HomeBud\backups，不存在自动创建）
#   -Keep     保留份数（默认 7）
#   -PgBin    pg_dump 所在 bin 目录（可选；缺省按 PATH →
#             C:\Program Files\PostgreSQL\*\bin（取版本最高）→
#             D:\PostgreSQL\bin（本机实际安装位置，与 start.ps1 一致）探测）
#   -DbUser   数据库用户（默认 postgres）
#   -DbHost   数据库主机（默认 localhost）
#   -DbPort   数据库端口（默认 5432）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\backup_db.ps1
#       powershell -ExecutionPolicy Bypass -File scripts\backup_db.ps1 -Keep 14
# 退出码：0=备份成功；1=失败（密码缺失/找不到 pg_dump/pg_dump 执行出错）
# =====================================================================

param(
    [string]$DbName = "jiaban",    # 目标数据库名
    [string]$OutDir = "",          # 备份输出目录；为空时取 <项目根>\backups
    [int]$Keep = 7,                # 备份保留份数（超出即轮转删除最旧）
    [string]$PgBin = "",           # pg_dump 所在目录（可选，优先于 PATH 探测）
    [string]$DbUser = "postgres",  # 数据库登录用户
    [string]$DbHost = "localhost", # 数据库主机
    [int]$DbPort = 5432            # 数据库端口
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
if (-not $OutDir) { $OutDir = Join-Path $root "backups" }
$logFile = Join-Path $OutDir "backup_log.txt"


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
        [string]$ToolName,   # 工具名（如 pg_dump）
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


# ---------- [1/5] 解析数据库密码（环境变量优先于 .env） ----------
Write-Host "[1/5] 解析数据库密码 ..." -NoNewline
$fromEnv = [bool]$env:PGPASSWORD
$env:PGPASSWORD = Get-DbPassword
$src = if ($fromEnv) { "环境变量 PGPASSWORD" } else { "backend\.env DATABASE_URL" }
Write-Host " OK（来源：$src）" -ForegroundColor Green

# ---------- [2/5] 探测 pg_dump ----------
Write-Host "[2/5] 探测 pg_dump ..." -NoNewline
$pgDump = Resolve-PgTool -ToolName "pg_dump" -BinDir $PgBin
Write-Host " OK（$pgDump）" -ForegroundColor Green

# ---------- [3/5] 确保输出目录存在 ----------
Write-Host "[3/5] 准备输出目录 ..." -NoNewline
if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
Write-Host " OK（$OutDir）" -ForegroundColor Green

# ---------- [4/5] 执行 pg_dump ----------
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpName = "${DbName}_${stamp}.dump"
$dumpFile = Join-Path $OutDir $dumpName
Write-Host "[4/5] 备份 $DbName@$($DbHost):$($DbPort) -> $dumpName ..."
$sw = [System.Diagnostics.Stopwatch]::StartNew()
# 原生命令写 stderr 不应中断脚本，临时放宽错误偏好
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $pgDump -h $DbHost -p $DbPort -U $DbUser -d $DbName -Fc -f $dumpFile
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEap
$sw.Stop()
if ($code -ne 0) {
    # 备份失败：清理半成品 dump 文件
    if (Test-Path -LiteralPath $dumpFile) { Remove-Item -LiteralPath $dumpFile -Force -ErrorAction SilentlyContinue }
    Write-Host "FAIL：pg_dump 退出码 $code，已删除半成品文件，请检查上方错误输出" -ForegroundColor Red
    exit 1
}
$sizeBytes = (Get-Item -LiteralPath $dumpFile).Length
$sizeMb = [math]::Round($sizeBytes / 1MB, 2)
if ($sizeBytes -le 0) {
    Write-Host "FAIL：dump 文件大小为 0 字节，备份可能异常：$dumpFile" -ForegroundColor Red
    exit 1
}

# ---------- [5/5] 写日志 + 轮转 ----------
Add-Content -LiteralPath $logFile -Value ("{0}  {1}  {2}MB  ok" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $dumpName, $sizeMb) -Encoding UTF8
# 轮转：文件名含时间戳，按名称倒序即最新在前，仅保留前 Keep 份
$dumps = @(Get-ChildItem -LiteralPath $OutDir -Filter "*.dump" -File | Sort-Object Name -Descending)
$expired = @($dumps | Select-Object -Skip $Keep)
foreach ($f in $expired) {
    Remove-Item -LiteralPath $f.FullName -Force
    Add-Content -LiteralPath $logFile -Value ("{0}  轮转删除：{1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $f.Name) -Encoding UTF8
}
$remain = $dumps.Count - $expired.Count

# ---------- 摘要 ----------
Write-Host ""
Write-Host "===== 备份完成 =====" -ForegroundColor Green
Write-Host "  - 文件  : $dumpFile"
Write-Host "  - 大小  : $sizeMb MB"
Write-Host ("  - 耗时  : {0}s" -f [math]::Round($sw.Elapsed.TotalSeconds, 1))
Write-Host "  - 剩余  : $remain 份（Keep=$Keep）"
Write-Host "  - 日志  : $logFile"
exit 0

# =====================================================================
# 小光景 - 提交前质量门禁脚本 (ci_gate.ps1)
# 功能：按序执行 契约校验(contract_check) -> 后端测试(pytest) -> 可选举项：
#       -WithBuild 前端构建(npm run build)；-WithE2E 端到端 API 模拟测试
#       （需前后端服务已在运行：scripts\start.ps1；e2e 为真实 LLM 模式，耗时且
#       消耗模型额度）。任一环节失败即中止后续步骤，并在汇总后以退出码 1 结束；
#       全通过退出码 0——可直接挂入 CI 流水线或本地提交前检查。
# 依赖：PostgreSQL 可达（pytest 用独立测试库 jiaban_test）。
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\ci_gate.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\ci_gate.ps1 -WithBuild
#   powershell -ExecutionPolicy Bypass -File scripts\ci_gate.ps1 -WithBuild -WithE2E
#   powershell -ExecutionPolicy Bypass -File scripts\ci_gate.ps1 -PytestArgs "tests/test_admin_menus.py -q"
# =====================================================================

param(
    [string]$PytestArgs = "tests -q",
    [switch]$WithBuild,
    [switch]$WithE2E
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

# ---------- Python 解释器探测（与 start.ps1 同序：系统 Python 优先，venv 兜底） ----------
$pyCandidates = @(
    "C:\Users\杨志泽民\AppData\Local\Programs\Python\Python312\python.exe",
    (Join-Path $backend ".venv\Scripts\python.exe")
)
$py = $null
foreach ($candidate in $pyCandidates) {
    if (Test-Path $candidate) {
        & $candidate -c "import fastapi, uvicorn, sqlalchemy, langgraph" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $py = $candidate; break }
    }
}
if (-not $py) {
    $py = $pyCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $py) { $py = "python" }
}

$steps = @()
$failed = $false

function Report-Step {
    # 记录并打印单个门禁步骤结果（绿=通过 / 红=失败）。
    param([string]$Name, [int]$Code, [double]$Seconds)
    if ($Code -eq 0) {
        Write-Host ("    结果：PASS（{0}s）" -f $Seconds) -ForegroundColor Green
    } else {
        Write-Host ("    结果：FAIL（退出码 {0}，{1}s）" -f $Code, $Seconds) -ForegroundColor Red
        $script:failed = $true
    }
    $script:steps += ("{0}：{1}" -f $Name, $(if ($Code -eq 0) { "PASS" } else { "FAIL(exit $Code)" }))
}

Write-Host "小光景质量门禁：契约校验 + 后端测试$(if ($WithBuild) { ' + 前端构建' })$(if ($WithE2E) { ' + E2E 模拟' })"
Write-Host "Python: $py"

# ---------- 第 1 步：契约校验（前端调用 × OpenAPI，漂移即失败） ----------
Write-Host ""
Write-Host "[1] 契约校验（frontend/src/api/*.ts × app.openapi()）" -ForegroundColor Cyan
$sw = [System.Diagnostics.Stopwatch]::StartNew()
Push-Location $backend
& $py scripts/contract_check.py
$code = $LASTEXITCODE
Pop-Location
$sw.Stop()
Report-Step "契约校验" $code ([math]::Round($sw.Elapsed.TotalSeconds, 1))

# ---------- 第 2 步：后端测试（pytest，默认全量 tests/） ----------
Write-Host ""
Write-Host "[2] 后端测试（python -m pytest $PytestArgs）" -ForegroundColor Cyan
$sw = [System.Diagnostics.Stopwatch]::StartNew()
Push-Location $backend
& $py -m pytest ($PytestArgs -split "\s+")
$code = $LASTEXITCODE
Pop-Location
$sw.Stop()
Report-Step "后端测试" $code ([math]::Round($sw.Elapsed.TotalSeconds, 1))

# ---------- 第 3 步（可选）：前端构建 ----------
if ($WithBuild -and $failed) {
    $steps += "前端构建：SKIP（前置失败）"
} elseif ($WithBuild) {
    Write-Host ""
    Write-Host "[3] 前端构建（npm run build）" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Push-Location $frontend
    & cmd.exe /c "npm run build"
    $code = $LASTEXITCODE
    Pop-Location
    $sw.Stop()
    Report-Step "前端构建" $code ([math]::Round($sw.Elapsed.TotalSeconds, 1))
}

# ---------- 第 4 步（可选）：端到端 API 模拟（需服务在跑） ----------
if ($WithE2E -and $failed) {
    $steps += "E2E 模拟：SKIP（前置失败）"
} elseif ($WithE2E) {
    Write-Host ""
    Write-Host "[E2E] 端到端 API 模拟（需后端 8000 在运行，真实 LLM 模式）" -ForegroundColor Cyan
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $port8000) {
        Write-Host "    结果：FAIL（后端 8000 未监听；先执行 scripts\start.ps1）" -ForegroundColor Red
        $failed = $true
        $steps += "E2E 模拟：FAIL(service down)"
    } else {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        Push-Location $backend
        & $py scripts/e2e_api_test.py --base http://localhost:8000
        $code = $LASTEXITCODE
        Pop-Location
        $sw.Stop()
        Report-Step "E2E 模拟" $code ([math]::Round($sw.Elapsed.TotalSeconds, 1))
    }
}

# ---------- 汇总 ----------
Write-Host ""
Write-Host "===== 门禁汇总 =====" 
foreach ($s in $steps) { Write-Host "  - $s" }
if ($failed) {
    Write-Host "结论：FAIL（修复后重跑本脚本；契约漂移与失败用例见上方输出）" -ForegroundColor Red
    exit 1
}
Write-Host "结论：PASS 全部通过，可提交/发布" -ForegroundColor Green
exit 0

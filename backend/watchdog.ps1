# 后端看门狗：检测 8000 端口失联则自动重启 uvicorn（答辩演示保障）
# 注意：本文件需 UTF-8 BOM 保存
$logFile = 'D:\HomeBud\backend\watchdog.log'
function Write-Log([string]$msg) {
    "$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')) $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}
Write-Log 'watchdog started'
while ($true) {
    Start-Sleep -Seconds 3
    $listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $listening) {
        Write-Log 'port 8000 down -> restarting uvicorn'
        Start-Process -FilePath 'python' `
            -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' `
            -WorkingDirectory 'D:\HomeBud\backend' -WindowStyle Hidden `
            -RedirectStandardOutput 'D:\HomeBud\backend\uvicorn-demo.log' `
            -RedirectStandardError 'D:\HomeBud\backend\uvicorn-demo.err.log'
        Start-Sleep -Seconds 8
        $ok = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($ok) { Write-Log 'restart ok' } else { Write-Log 'restart FAILED' }
    }
}

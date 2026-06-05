# start-windows.ps1 Smoke test
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-windows-start.ps1
# Starts backend+frontend, verifies health, auto-stops, returns exit code.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Startup Script Smoke Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Test-PortInUse {
    param([int]$Port)
    try {
        $conn = New-Object System.Net.Sockets.TcpClient
        $conn.Connect("127.0.0.1", $Port)
        $conn.Close()
        return $true
    } catch {
        return $false
    }
}

if (Test-PortInUse 8000) {
    Write-Host "  FAIL: port 8000 already in use" -ForegroundColor Red
    exit 1
}
if (Test-PortInUse 5173) {
    Write-Host "  FAIL: port 5173 already in use" -ForegroundColor Red
    exit 1
}
Write-Host "  PASS: ports 8000/5173 available" -ForegroundColor Green

$startScript = Join-Path $ProjectRoot "scripts\start-windows.ps1"
Write-Host ""
Write-Host "  Running start-windows.ps1 -NoOpenBrowser -AutoStopAfterSeconds 5 ..." -ForegroundColor Yellow

$exitCode = 0
try {
    & powershell -ExecutionPolicy Bypass -File $startScript -NoOpenBrowser -AutoStopAfterSeconds 5
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host "  FAIL: start-windows.ps1 threw: $_" -ForegroundColor Red
    $exitCode = 1
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "  PASS: start-windows.ps1 started and stopped OK (exit code 0)" -ForegroundColor Green
} else {
    Write-Host "  FAIL: start-windows.ps1 exit code $exitCode" -ForegroundColor Red
}

Start-Sleep -Seconds 1
$portClear = $true
if (Test-PortInUse 8000) {
    Write-Host "  FAIL: port 8000 still in use (service not stopped)" -ForegroundColor Red
    $portClear = $false
}
if (Test-PortInUse 5173) {
    Write-Host "  FAIL: port 5173 still in use (service not stopped)" -ForegroundColor Red
    $portClear = $false
}
if ($portClear) {
    Write-Host "  PASS: ports 8000/5173 released" -ForegroundColor Green
}

$stateFile = Join-Path $ProjectRoot "scripts\.running_pids"
if (Test-Path $stateFile) {
    Write-Host "  FAIL: PID file not cleaned up: $stateFile" -ForegroundColor Red
    $exitCode = 1
} else {
    Write-Host "  PASS: PID file cleaned up" -ForegroundColor Green
}

$frontendLog = Join-Path $ProjectRoot "scripts\frontend.log"
if (Test-Path $frontendLog) {
    $badLog = Select-String -Path $frontendLog -Pattern "EPIPE|Unhandled|Error:" -CaseSensitive:$false
    if ($badLog) {
        Write-Host "  FAIL: frontend log contains stop-time error noise" -ForegroundColor Red
        $badLog | Select-Object -First 5 | ForEach-Object {
            Write-Host "    $($_.Line)" -ForegroundColor Gray
        }
        $exitCode = 1
    } else {
        Write-Host "  PASS: frontend log has no EPIPE/Unhandled/Error noise" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  Running stop-windows.ps1 to verify no residual ..." -ForegroundColor Yellow
$stopScript = Join-Path $ProjectRoot "scripts\stop-windows.ps1"
& powershell -ExecutionPolicy Bypass -File $stopScript
Write-Host "  PASS: stop-windows.ps1 completed" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor $(if ($exitCode -eq 0) { "Green" } else { "Red" })
if ($exitCode -eq 0) {
    Write-Host "  Smoke test PASSED" -ForegroundColor Green
} else {
    Write-Host "  Smoke test FAILED" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor $(if ($exitCode -eq 0) { "Green" } else { "Red" })
Write-Host ""

exit $exitCode

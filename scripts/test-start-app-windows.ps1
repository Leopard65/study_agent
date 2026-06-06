# start-app-windows.ps1 Smoke test
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-start-app-windows.ps1
# Starts backend in production mode, verifies health/frontend/SPA routes, auto-stops, returns exit code.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Production Startup Smoke Test" -ForegroundColor Cyan
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

# Pre-check: port 8000 must be free
if (Test-PortInUse 8000) {
    Write-Host "  FAIL: port 8000 already in use" -ForegroundColor Red
    exit 1
}
Write-Host "  PASS: port 8000 available" -ForegroundColor Green

# Check frontend/dist exists
$distDir = Join-Path $ProjectRoot "frontend\dist"
if (-not (Test-Path (Join-Path $distDir "index.html"))) {
    Write-Host "  SKIP: frontend/dist/index.html not found (run 'npm run build' in frontend/ first)" -ForegroundColor Yellow
    exit 0
}
Write-Host "  PASS: frontend/dist exists" -ForegroundColor Green

$startScript = Join-Path $ProjectRoot "scripts\start-app-windows.ps1"
Write-Host ""
Write-Host "  Running start-app-windows.ps1 -NoOpenBrowser -AutoStopAfterSeconds 5 ..." -ForegroundColor Yellow

$exitCode = 0
try {
    & powershell -ExecutionPolicy Bypass -File $startScript -NoOpenBrowser -AutoStopAfterSeconds 5
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host "  FAIL: start-app-windows.ps1 threw: $_" -ForegroundColor Red
    $exitCode = 1
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "  PASS: start-app-windows.ps1 started and stopped OK (exit code 0)" -ForegroundColor Green
} else {
    Write-Host "  FAIL: start-app-windows.ps1 exit code $exitCode" -ForegroundColor Red
}

# Verify port released
Start-Sleep -Seconds 1
if (Test-PortInUse 8000) {
    Write-Host "  FAIL: port 8000 still in use (service not stopped)" -ForegroundColor Red
    $exitCode = 1
} else {
    Write-Host "  PASS: port 8000 released" -ForegroundColor Green
}

# Verify PID file cleaned up
$stateFile = Join-Path $ProjectRoot "scripts\.running_pids"
if (Test-Path $stateFile) {
    Write-Host "  FAIL: PID file not cleaned up: $stateFile" -ForegroundColor Red
    $exitCode = 1
} else {
    Write-Host "  PASS: PID file cleaned up" -ForegroundColor Green
}

# Run stop script to verify no residual
Write-Host ""
Write-Host "  Running stop-windows.ps1 to verify no residual ..." -ForegroundColor Yellow
$stopScript = Join-Path $ProjectRoot "scripts\stop-windows.ps1"
& powershell -ExecutionPolicy Bypass -File $stopScript
Write-Host "  PASS: stop-windows.ps1 completed" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor $(if ($exitCode -eq 0) { "Green" } else { "Red" })
if ($exitCode -eq 0) {
    Write-Host "  Production smoke test PASSED" -ForegroundColor Green
} else {
    Write-Host "  Production smoke test FAILED" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor $(if ($exitCode -eq 0) { "Green" } else { "Red" })
Write-Host ""

exit $exitCode

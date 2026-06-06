# start-app-windows.ps1 Smoke test
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-start-app-windows.ps1
# Starts backend in production mode, verifies endpoints, auto-stops, returns exit code.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Production Startup Smoke Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$exitCode = 0

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

function Stop-ProcessTree {
    param([int]$ProcessId)
    try {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            Stop-ProcessTree -ProcessId $child.ProcessId
        }
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {}
}

function Assert-Url {
    param([string]$Name, [string]$Url, [int]$ExpectedStatus, [string]$ContentTypeMustNot = "")
    try {
        $wc = New-Object System.Net.WebClient
        $response = $wc.DownloadString($Url)
        # WebClient doesn't give us status code easily; if we get here it's 200
        if ($ExpectedStatus -ne 200) {
            Write-Host "  FAIL $Name : expected $ExpectedStatus, got 200" -ForegroundColor Red
            $script:exitCode = 1
            return
        }
        if ($ContentTypeMustNot) {
            $ct = $wc.ResponseHeaders["Content-Type"]
            if ($ct -and $ct -like "*$ContentTypeMustNot*") {
                Write-Host "  FAIL $Name : content-type should not be $ContentTypeMustNot, got $ct" -ForegroundColor Red
                $script:exitCode = 1
                return
            }
        }
        Write-Host "  PASS $Name : 200 OK" -ForegroundColor Green
    } catch [System.Net.WebException] {
        $resp = $_.Exception.Response
        if ($resp) {
            $status = [int]$resp.StatusCode
            if ($status -ne $ExpectedStatus) {
                Write-Host "  FAIL $Name : expected $ExpectedStatus, got $status" -ForegroundColor Red
                $script:exitCode = 1
                return
            }
            if ($ContentTypeMustNot) {
                $ct = $resp.ContentType
                if ($ct -and $ct -like "*$ContentTypeMustNot*") {
                    Write-Host "  FAIL $Name : content-type should not be $ContentTypeMustNot, got $ct" -ForegroundColor Red
                    $script:exitCode = 1
                    return
                }
            }
            Write-Host "  PASS $Name : $status" -ForegroundColor Green
        } else {
            Write-Host "  FAIL $Name : $($_.Exception.Message)" -ForegroundColor Red
            $script:exitCode = 1
        }
    } catch {
        Write-Host "  FAIL $Name : $($_.Exception.Message)" -ForegroundColor Red
        $script:exitCode = 1
    }
}

# Pre-check: port 8000 must be free
if (Test-PortInUse 8000) {
    Write-Host "  FAIL: port 8000 already in use" -ForegroundColor Red
    exit 1
}
Write-Host "  PASS: port 8000 available" -ForegroundColor Green

# Pre-check: frontend/dist must exist
$distDir = Join-Path $ProjectRoot "frontend\dist"
if (-not (Test-Path (Join-Path $distDir "index.html"))) {
    Write-Host "  frontend/dist/index.html not found, building..." -ForegroundColor Yellow
    $frontendDir = Join-Path $ProjectRoot "frontend"
    Push-Location $frontendDir
    & npm run build 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAIL: frontend build failed" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
}
Write-Host "  PASS: frontend/dist exists" -ForegroundColor Green

# Start backend in background
Write-Host ""
Write-Host "  Starting backend in production mode ..." -ForegroundColor Yellow

$backendDir = Join-Path $ProjectRoot "backend"
$pyExe = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendLog = Join-Path $ProjectRoot "scripts\backend.log"

$backendCmd = "/c `"`"$pyExe`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > `"$backendLog`" 2>&1 < NUL`""
$backendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList $backendCmd `
    -WorkingDirectory $backendDir `
    -PassThru `
    -WindowStyle Minimized

$backendPid = $backendProc.Id
Write-Host "  Backend PID: $backendPid" -ForegroundColor Gray

# Wait for backend to be ready
$retries = 0
$backendReady = $false
while ($retries -lt 30) {
    try {
        $wc = New-Object System.Net.WebClient
        $null = $wc.DownloadString("http://127.0.0.1:8000/api/health")
        $backendReady = $true
        break
    } catch {
        if ($backendProc.HasExited) {
            Write-Host "  FAIL: backend exited prematurely" -ForegroundColor Red
            if (Test-Path $backendLog) {
                Get-Content $backendLog -Tail 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            }
            exit 1
        }
        Start-Sleep -Milliseconds 500
        $retries++
    }
}

if (-not $backendReady) {
    Write-Host "  FAIL: backend startup timeout" -ForegroundColor Red
    Stop-ProcessTree -ProcessId $backendPid
    exit 1
}

Write-Host "  Backend ready" -ForegroundColor Green
Write-Host ""

# ── Endpoint assertions ──
Write-Host "  --- Endpoint assertions ---" -ForegroundColor Cyan

Assert-Url -Name "/api/health" -Url "http://127.0.0.1:8000/api/health" -ExpectedStatus 200
Assert-Url -Name "/" -Url "http://127.0.0.1:8000/" -ExpectedStatus 200
Assert-Url -Name "/materials (SPA)" -Url "http://127.0.0.1:8000/materials" -ExpectedStatus 200
Assert-Url -Name "/api/not-found" -Url "http://127.0.0.1:8000/api/not-found" -ExpectedStatus 404 -ContentTypeMustNot "text/html"

# ── Cleanup ──
Write-Host ""
Write-Host "  Stopping backend ..." -ForegroundColor Gray
Stop-ProcessTree -ProcessId $backendPid
Start-Sleep -Seconds 1

# Verify port released
if (Test-PortInUse 8000) {
    Write-Host "  FAIL: port 8000 still in use after stop" -ForegroundColor Red
    $exitCode = 1
} else {
    Write-Host "  PASS: port 8000 released" -ForegroundColor Green
}

# Verify PID file not left behind
$stateFile = Join-Path $ProjectRoot "scripts\.running_pids"
if (Test-Path $stateFile) {
    Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
}

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

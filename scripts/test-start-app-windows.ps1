# start-app-windows.ps1 Production Smoke Test
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-start-app-windows.ps1
#        powershell -ExecutionPolicy Bypass -File scripts\test-start-app-windows.ps1 -Clean
#        powershell -ExecutionPolicy Bypass -File scripts\test-start-app-windows.ps1 -Clean -FailAfterIsolation
#
# Verifies the production startup path: venv, deps, .env, frontend build, backend
# startup, endpoint health, SPA routing, asset delivery, and port cleanup.
#
# -Clean  Clean artifact isolation mode:
#         - Isolates .venv, frontend/dist, backend/.env (renamed with GUID suffix)
#         - Creates temporary DATABASE_URL and UPLOAD_DIR in $env:TEMP
#         - Real backend/data/ is NEVER touched -- the user's database is safe
#         - Reuses existing frontend/node_modules (does NOT reinstall npm deps)
#         - After the test, all isolated artifacts are restored and temp dirs deleted
#         Without -Clean the script reuses all existing artifacts (fast path).
#
# -FailAfterIsolation  (requires -Clean) Throws after isolation completes but before
#         backend startup. Used to verify that finally-block cleanup correctly
#         restores isolated artifacts, deletes temp dirs, and releases port 8000.
#
# Exit code: 0 = all checks passed, 1 = at least one failure.
# On ANY exit path the process tree is killed and port 8000 is released.
#
# SAFETY: Restore-first policy. Backups are NEVER force-deleted. If a restore
# fails, the backup is preserved on disk and the script reports failure with
# the exact path. The user must manually inspect and resolve.

param(
    [switch]$Clean,
    [switch]$FailAfterIsolation
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Dot-source shared library (backup resolution + FS retry helpers)
. (Join-Path $PSScriptRoot "lib\backup-resolution.ps1")

# -- State (all mutable state lives here, one place) --
# Functions read/write via $S.property. No bare $script: vars elsewhere.
$S = [PSCustomObject]@{
    exitCode         = 0
    backendPid       = $null
    backendProc      = $null
    tempDirs         = @()
    restoredItems    = @()   # list of @{Orig; Backup; Label}
    realDbMtimeBefore = $null
    realDbPath       = Join-Path $ProjectRoot "backend\data\app.db"
    # Set during setup
    pyExe            = $null
    pipExe           = $null
    backendDir       = $null
    # Set during isolation
    cleanDbUrl       = $null
    cleanUploadDir   = $null
}
# Alias so helper functions can reference state as $S
Set-Variable -Name S -Value $S -Scope Script

# ======================================================================
# Utility functions
# ======================================================================

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

function Write-Pass { param([string]$Msg) Write-Host "  PASS $Msg" -ForegroundColor Green }
function Write-Fail { param([string]$Msg) Write-Host "  FAIL $Msg" -ForegroundColor Red; $S.exitCode = 1 }
function Write-Step { param([string]$Msg) Write-Host "  $Msg" -ForegroundColor Yellow }
function Write-Info { param([string]$Msg) Write-Host "  $Msg" -ForegroundColor Gray }
function Write-Warn { param([string]$Msg) Write-Host "  WARN: $Msg" -ForegroundColor Yellow }

function Assert-Url {
    param([string]$Name, [string]$Url, [int]$ExpectedStatus, [string]$ContentTypeMustNot = "")
    try {
        $wc = New-Object System.Net.WebClient
        $null = $wc.DownloadString($Url)
        if ($ExpectedStatus -ne 200) {
            Write-Fail "$Name : expected $ExpectedStatus, got 200"
            return
        }
        if ($ContentTypeMustNot) {
            $ct = $wc.ResponseHeaders["Content-Type"]
            if ($ct -and $ct -like "*$ContentTypeMustNot*") {
                Write-Fail "$Name : content-type should not be $ContentTypeMustNot, got $ct"
                return
            }
        }
        Write-Pass "$Name : 200 OK"
    } catch [System.Net.WebException] {
        $resp = $_.Exception.Response
        if ($resp) {
            $status = [int]$resp.StatusCode
            if ($status -ne $ExpectedStatus) {
                Write-Fail "$Name : expected $ExpectedStatus, got $status"
                return
            }
            if ($ContentTypeMustNot) {
                $ct = $resp.ContentType
                if ($ct -and $ct -like "*$ContentTypeMustNot*") {
                    Write-Fail "$Name : content-type should not be $ContentTypeMustNot, got $ct"
                    return
                }
            }
            Write-Pass "$Name : $status"
        } else {
            Write-Fail "$Name : $($_.Exception.Message)"
        }
    } catch {
        Write-Fail "$Name : $($_.Exception.Message)"
    }
}

# ======================================================================
# Phase 1: Isolation (Clean mode)
# ======================================================================
#
# Backup safety rules:
#   1. Each item gets a unique GUID suffix. No two runs share a suffix.
#   2. Before isolation, scan for orphaned backups from prior crashed runs:
#      - frontend/dist._smoke_* : safe to delete (build artifact, reproducible)
#      - backend/.venv._smoke_* : safe to delete (recreatable via pip install)
#      - backend/.env._smoke_*  : NEVER auto-deleted. Contains user config/API key.
#        If orphaned .env backup exists and original is missing, restore it.
#        If both exist, fail with explicit path -- user must resolve manually.
#   3. Restore uses -ErrorAction Stop. If restore fails, backup is kept on disk.
#   4. After restore loop, verify backups are gone. If not, report path and fail.
#      NEVER force-delete a backup that survived a failed restore.

function Invoke-Isolation {
    if (Test-Path $S.realDbPath) {
        $S.realDbMtimeBefore = (Get-Item $S.realDbPath).LastWriteTimeUtc
        Write-Info "Real DB mtime (before): $($S.realDbMtimeBefore)"
    } else {
        Write-Info "no real backend/data/app.db found, will skip mtime check"
    }

    Write-Host ""
    Write-Host "  --- Isolating for clean artifact isolation ---" -ForegroundColor Yellow
    $backendDir = Join-Path $ProjectRoot "backend"

    # Resolve orphaned backups from previous crashed runs
    $backupResults = Resolve-OrphanedBackups -ProjectRoot $ProjectRoot -FsTimeoutMs 3000 -FsIntervalMs 200
    foreach ($r in $backupResults) {
        if ($r.Ok) {
            Write-Info "$($r.Action): $($r.Label) $($r.Detail)"
        } else {
            Write-Fail "$($r.Action): $($r.Label) -- $($r.Error)"
            if ($r.Path) { Write-Host "    Path: $($r.Path)" -ForegroundColor Red }
            throw "Backup resolution failed: $($r.Action)"
        }
    }

    # Create temp directories for DB and uploads
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "smoke_test_$([guid]::NewGuid().ToString('N').Substring(0,12))"
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $S.tempDirs += $tempRoot

    $tempDataDir = Join-Path $tempRoot "data"
    $tempUploadDir = Join-Path $tempRoot "uploads"
    New-Item -ItemType Directory -Force -Path $tempDataDir | Out-Null
    New-Item -ItemType Directory -Force -Path $tempUploadDir | Out-Null

    $tempDbPath = ($tempDataDir + "\app.db").Replace("\", "/")
    $S.cleanDbUrl = "sqlite+aiosqlite:///$tempDbPath"
    $S.cleanUploadDir = $tempUploadDir

    Write-Info "Temp DB: $($S.cleanDbUrl)"
    Write-Info "Temp uploads: $($S.cleanUploadDir)"

    # Rename originals to backups with unique GUID suffix
    $guidSuffix = [guid]::NewGuid().ToString("N").Substring(0, 12)
    foreach ($item in @(
        @{ Orig = Join-Path $backendDir ".venv";     Label = "backend/.venv" },
        @{ Orig = Join-Path $backendDir ".env";       Label = "backend/.env" },
        @{ Orig = Join-Path $ProjectRoot "frontend\dist"; Label = "frontend/dist" }
    )) {
        if (Test-Path $item.Orig) {
            $backup = "$($item.Orig)._smoke_$guidSuffix"
            if (Test-Path $backup) {
                Write-Fail "backup already exists: $backup"
                Write-Host "  Refusing to overwrite -- clean up manually and retry." -ForegroundColor Red
                throw "Backup collision: $backup"
            }
            Rename-Item $item.Orig $backup -Force
            $S.restoredItems += @{ Orig = $item.Orig; Backup = $backup; Label = $item.Label }
            Write-Info "Isolated: $($item.Label)"
        }
    }

    # Failure injection: throw after isolation
    if ($FailAfterIsolation) {
        Write-Host "  [INJECT] Throwing after isolation to test cleanup ..." -ForegroundColor Yellow
        throw "Injected failure after isolation"
    }
}

# Resolve-OrphanedBackups is in scripts/lib/backup-resolution.ps1

# ======================================================================
# Phase 2: Setup steps
# ======================================================================

function Invoke-SetupVenv {
    Write-Step "[1/5] Setting up Python venv ..."
    $backendDir = Join-Path $ProjectRoot "backend"
    $venvDir = Join-Path $backendDir ".venv"
    $pyExe = Join-Path $venvDir "Scripts\python.exe"
    $pipExe = Join-Path $venvDir "Scripts\pip.exe"

    if (-not (Test-Path $pyExe)) {
        Write-Info "Creating venv ..."
        & python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "venv creation failed"
            return
        }
    }
    Write-Pass "venv ready"

    $S.pyExe = $pyExe
    $S.pipExe = $pipExe
    $S.backendDir = $backendDir
}

function Invoke-InstallDeps {
    Write-Step "[2/5] Installing backend deps ..."
    $reqFile = Join-Path $S.backendDir "requirements.txt"
    & $S.pipExe install -r $reqFile --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "pip install failed"
        return
    }
    Write-Pass "backend deps installed"
}

function Invoke-EnsureEnv {
    Write-Step "[3/5] Checking .env ..."
    $envFile = Join-Path $S.backendDir ".env"
    $envExample = Join-Path $S.backendDir ".env.example"
    if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
        Copy-Item $envExample $envFile
        Write-Info "Created .env from .env.example"
    }
    Write-Pass ".env present"
}

function Invoke-BuildFrontend {
    Write-Step "[4/5] Checking frontend build ..."
    $distDir = Join-Path $ProjectRoot "frontend\dist"
    if (Test-Path (Join-Path $distDir "index.html")) {
        Write-Pass "frontend/dist ready"
        return
    }

    Write-Info "Building frontend ..."
    $frontendDir = Join-Path $ProjectRoot "frontend"
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        try {
            Push-Location $frontendDir
            & npm install --silent 2>&1 | Out-Null
        } finally {
            Pop-Location
        }
    }
    try {
        Push-Location $frontendDir
        & npm run build 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "frontend build failed"
            return
        }
    } finally {
        Pop-Location
    }
    Write-Pass "frontend/dist ready"
}

# ======================================================================
# Phase 3: Start backend and run assertions
# ======================================================================

function Invoke-BackendAndAssert {
    Write-Step "[5/5] Starting backend in production mode ..."
    $backendLog = Join-Path $ProjectRoot "scripts\backend.log"
    if (Test-Path $backendLog) { Clear-Content $backendLog -ErrorAction SilentlyContinue }

    # Inject clean DB/Upload URLs into .env
    if ($Clean -and $S.cleanDbUrl) {
        $envFile = Join-Path $S.backendDir ".env"
        Add-Content -Path $envFile -Value "`nDATABASE_URL=$($S.cleanDbUrl)`nUPLOAD_DIR=$($S.cleanUploadDir)" -Encoding utf8
    }

    $backendCmd = "/c `"`"$($S.pyExe)`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > `"$backendLog`" 2>&1 < NUL`""
    $S.backendProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList $backendCmd `
        -WorkingDirectory $S.backendDir `
        -PassThru `
        -WindowStyle Hidden

    $S.backendPid = $S.backendProc.Id
    Write-Info "Backend PID: $($S.backendPid)"

    # Wait for backend to be ready (15s timeout)
    $retries = 0
    $backendReady = $false
    while ($retries -lt 30) {
        try {
            $wc = New-Object System.Net.WebClient
            $null = $wc.DownloadString("http://127.0.0.1:8000/api/health")
            $backendReady = $true
            break
        } catch {
            if ($S.backendProc.HasExited) {
                Write-Fail "backend exited prematurely"
                if (Test-Path $backendLog) {
                    Write-Host "  --- Last 15 lines of backend.log ---" -ForegroundColor Gray
                    Get-Content $backendLog -Tail 15 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
                }
                return
            }
            Start-Sleep -Milliseconds 500
            $retries++
        }
    }

    if (-not $backendReady) {
        Write-Fail "backend startup timeout (15s)"
        return
    }

    Write-Pass "backend ready"
    Write-Host ""

    # Endpoint assertions
    Write-Host "  --- Endpoint assertions ---" -ForegroundColor Cyan
    Assert-Url -Name "/api/health" -Url "http://127.0.0.1:8000/api/health" -ExpectedStatus 200
    Assert-Url -Name "/" -Url "http://127.0.0.1:8000/" -ExpectedStatus 200
    Assert-Url -Name "/materials (SPA)" -Url "http://127.0.0.1:8000/materials" -ExpectedStatus 200
    Assert-Url -Name "/api/not-found" -Url "http://127.0.0.1:8000/api/not-found" -ExpectedStatus 404 -ContentTypeMustNot "text/html"

    # Asset delivery verification
    Write-Host ""
    Write-Host "  --- Asset delivery verification ---" -ForegroundColor Cyan
    try {
        $wc = New-Object System.Net.WebClient
        $indexHtml = $wc.DownloadString("http://127.0.0.1:8000/")
        if ($indexHtml -match '(/assets/[^"''>\s]+\.(?:js|css))') {
            $assetPath = $Matches[1]
            $assetUrl = "http://127.0.0.1:8000$assetPath"
            try {
                $assetWc = New-Object System.Net.WebClient
                $null = $assetWc.DownloadData($assetUrl)
                $assetCt = $assetWc.ResponseHeaders["Content-Type"]
                if ($assetCt -like "*text/html*") {
                    Write-Fail "$assetPath : content-type is HTML (assets not served)"
                } else {
                    Write-Pass "$assetPath : 200 ($assetCt)"
                }
            } catch {
                Write-Fail "$assetPath : $($_.Exception.Message)"
            }
        } else {
            Write-Fail "no /assets/ path found in index.html"
        }
    } catch {
        Write-Fail "could not fetch index.html for asset check"
    }
}

# ======================================================================
# Phase 4: Cleanup
# ======================================================================
#
# Restore-first policy:
#   - Backups are NEVER force-deleted after a failed restore.
#   - If a backup survives restore, it is reported as a failure with its path.
#   - The user must inspect and resolve manually.

function Invoke-Cleanup {
    Write-Host ""
    Write-Host "  --- Cleanup ---" -ForegroundColor Gray

    # Kill backend process tree
    try {
        if ($S.backendPid) {
            Stop-ProcessTree -ProcessId $S.backendPid
            Start-Sleep -Seconds 1
        }
    } catch {
        Write-Warn "failed to stop backend process: $($_.Exception.Message)"
    }

    # Force-kill anything left on port 8000
    try {
        if (Test-PortInUse 8000) {
            Write-Warn "port 8000 still in use, force-killing ..."
            $netstat = netstat -ano 2>&1 | Select-String ":8000\s.*LISTENING"
            foreach ($line in $netstat) {
                if ($line.ToString() -match '\s(\d+)\s*$') {
                    $leftoverPid = [int]$Matches[1]
                    Stop-ProcessTree -ProcessId $leftoverPid
                }
            }
            Start-Sleep -Seconds 1
            if (Test-PortInUse 8000) {
                Write-Fail "port 8000 still in use after force-kill"
            } else {
                Write-Pass "port 8000 released (after force-kill)"
            }
        } else {
            Write-Pass "port 8000 released"
        }
    } catch {
        Write-Warn "port cleanup error: $($_.Exception.Message)"
    }

    # Remove state file if left behind
    try {
        $stateFile = Join-Path $ProjectRoot "scripts\.running_pids"
        if (Test-Path $stateFile) {
            Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
        }
    } catch {}

    # Clean mode: mtime verification + restore isolated items
    if ($Clean) {
        Invoke-CleanupIsolation
    }

    # Remove temp dirs
    foreach ($td in $S.tempDirs) {
        try {
            if (Test-Path $td) {
                Remove-Item $td -Recurse -Force -ErrorAction SilentlyContinue
                Write-Info "Removed temp dir: $td"
            }
        } catch {
            Write-Warn "failed to remove temp dir $td : $($_.Exception.Message)"
        }
    }
}

function Invoke-CleanupIsolation {
    # Verify real DB was not touched
    try {
        if (-not (Test-Path $S.realDbPath)) {
            if ($null -ne $S.realDbMtimeBefore) {
                Write-Fail "real backend/data/app.db was deleted!"
            } else {
                Write-Info "no real backend/data/app.db exists, skipping mtime check"
            }
        } elseif ($null -ne $S.realDbMtimeBefore) {
            $realDbMtimeAfter = (Get-Item $S.realDbPath).LastWriteTimeUtc
            if ($realDbMtimeAfter -eq $S.realDbMtimeBefore) {
                Write-Pass "real backend/data/app.db mtime unchanged (was not written)"
            } else {
                Write-Fail "real backend/data/app.db mtime changed! ($($S.realDbMtimeBefore) -> $realDbMtimeAfter)"
            }
        } else {
            Write-Info "real backend/data/app.db appeared during test, skipping mtime check"
        }
    } catch {
        Write-Warn "mtime check error: $($_.Exception.Message)"
    }

    # Restore isolated items (rename backups back to originals)
    $restoreResults = Restore-IsolatedItems -Items $S.restoredItems -FsTimeoutMs 3000 -FsIntervalMs 200
    foreach ($r in $restoreResults) {
        if ($r.Ok) {
            Write-Info "Restored: $($r.Label)"
        } else {
            Write-Warn "$($r.Action): $($r.Label) -- $($r.Error)"
            if ($r.Path) { Write-Host "    Path: $($r.Path)" -ForegroundColor Yellow }
            $S.exitCode = 1
        }
    }
}

# ======================================================================
# Banner
# ======================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Production Startup Smoke Test" -ForegroundColor Cyan
if ($Clean) {
    Write-Host "  (clean artifact isolation)" -ForegroundColor Cyan
} else {
    Write-Host "  (reuses existing artifacts)" -ForegroundColor Cyan
}
if ($FailAfterIsolation) {
    Write-Host "  (failure injection mode)" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- Pre-check: port 8000 must be free --
if (Test-PortInUse 8000) {
    Write-Fail "port 8000 already in use"
    exit 1
}
Write-Pass "port 8000 available"

# ======================================================================
# Main logic
# ======================================================================

try {
    # Phase 1: Isolation (Clean mode only)
    if ($Clean) {
        Invoke-Isolation
    }

    # Phase 2: Setup
    Write-Host ""
    Invoke-SetupVenv
    if ($S.exitCode -eq 0) { Invoke-InstallDeps }
    if ($S.exitCode -eq 0) { Invoke-EnsureEnv }
    if ($S.exitCode -eq 0) { Invoke-BuildFrontend }

    # Phase 3: Start backend and assert
    if ($S.exitCode -eq 0) { Invoke-BackendAndAssert }

} catch {
    Write-Host ""
    Write-Host "  UNEXPECTED ERROR: $($_.Exception.Message)" -ForegroundColor Red
    $S.exitCode = 1
} finally {
    # Phase 4: Cleanup -- ALWAYS runs
    Invoke-Cleanup
}

# -- Summary --
Write-Host ""
Write-Host "========================================" -ForegroundColor $(if ($S.exitCode -eq 0) { "Green" } else { "Red" })
if ($S.exitCode -eq 0) {
    Write-Host "  Production smoke test PASSED" -ForegroundColor Green
} else {
    Write-Host "  Production smoke test FAILED" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor $(if ($S.exitCode -eq 0) { "Green" } else { "Red" })
Write-Host ""

exit $S.exitCode

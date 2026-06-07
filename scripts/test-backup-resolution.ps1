# test-backup-resolution.ps1
# Regression tests for backup resolution logic.
# Calls the REAL production functions from scripts/lib/backup-resolution.ps1.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-backup-resolution.ps1
#
# Tests run in isolated temp directories (GUID-based) and clean up via try/finally.
# Exit code: 0 = all passed, 1 = at least one failure.

$ErrorActionPreference = "Stop"
$script:passed = 0
$script:failed = 0

# Dot-source the production library -- tests call real functions, not copies
. (Join-Path $PSScriptRoot "lib\backup-resolution.ps1")

function Check {
    param([string]$Name, [bool]$Condition, [string]$Detail = "")
    if ($Condition) {
        $script:passed++
        Write-Host "  PASS  $Name" -ForegroundColor Green
    } else {
        $script:failed++
        $msg = "  FAIL  $Name"
        if ($Detail) { $msg += "  ($Detail)" }
        Write-Host $msg -ForegroundColor Red
    }
}

function New-GuidTempDir {
    $d = Join-Path ([System.IO.Path]::GetTempPath()) "backup_test_$([guid]::NewGuid().ToString('N').Substring(0,12))"
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    return $d
}

# ======================================================================
# Test 1: Filter matching
# ======================================================================
Write-Host ""
Write-Host "[1] Filter matching" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    New-Item -ItemType File -Path (Join-Path $d ".env") -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $d ".env._smoke_abc123") -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $d ".venv._smoke_def456") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $d ".venv._smoke_ghi789") -Force | Out-Null

    $envBackups = @(Get-ChildItem $d -Filter ".env._smoke_*" -Force -ErrorAction SilentlyContinue)
    Check ".env._smoke_* found by filter" ($envBackups.Count -eq 1) "count=$($envBackups.Count)"
    Check ".env._smoke_* correct name" ($envBackups[0].Name -eq ".env._smoke_abc123") "name=$($envBackups[0].Name)"

    $venvBackups = @(Get-ChildItem $d -Filter ".venv._smoke_*" -Force -ErrorAction SilentlyContinue)
    Check ".venv._smoke_* separate filter" ($venvBackups.Count -eq 2) "count=$($venvBackups.Count)"

    $oldFilter = @(Get-ChildItem $d -Filter "._smoke_*" -Force -ErrorAction SilentlyContinue)
    $oldFoundEnv = @($oldFilter | Where-Object { $_.Name -match "^\.env\._smoke_" })
    Check "old filter ._smoke_* misses .env._smoke_*" ($oldFoundEnv.Count -eq 0) "count=$($oldFoundEnv.Count)"
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 2: Scenario A -- missing original + single backup -> restore
# ======================================================================
Write-Host ""
Write-Host "[2] Scenario A: missing original + single backup -> restore" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $fakeBackend = Join-Path $d "backend"
    New-Item -ItemType Directory -Force -Path $fakeBackend | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $d "frontend") | Out-Null
    Set-Content (Join-Path $fakeBackend ".env._smoke_restore1") "OPENAI_API_KEY=sk-test-key" -NoNewline

    $results = @(Resolve-OrphanedBackups -ProjectRoot $d)

    $envResult = $results | Where-Object { $_.Action -match "env" }
    Check "A: result ok" ($envResult.Ok -eq $true) "action=$($envResult.Action)"
    Check "A: .env restored" (Test-Path (Join-Path $fakeBackend ".env"))
    Check "A: backup consumed" (-not (Test-Path (Join-Path $fakeBackend ".env._smoke_restore1")))
    if (Test-Path (Join-Path $fakeBackend ".env")) {
        Check "A: content preserved" ((Get-Content (Join-Path $fakeBackend ".env") -Raw) -eq "OPENAI_API_KEY=sk-test-key")
    }
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 3: Scenario B -- original exists + single backup -> fail, backup preserved
# ======================================================================
Write-Host ""
Write-Host "[3] Scenario B: original exists + single backup -> fail, backup preserved" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $fakeBackend = Join-Path $d "backend"
    New-Item -ItemType Directory -Force -Path $fakeBackend | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $d "frontend") | Out-Null
    Set-Content (Join-Path $fakeBackend ".env") "ORIGINAL=true" -NoNewline
    New-Item -ItemType File -Path (Join-Path $fakeBackend ".env._smoke_conflict1") -Force | Out-Null
    Set-Content (Join-Path $fakeBackend ".env._smoke_conflict1") "BACKUP=true" -NoNewline

    $results = @(Resolve-OrphanedBackups -ProjectRoot $d)

    $envResult = $results | Where-Object { $_.Action -match "env" }
    Check "B: result not ok" ($envResult.Ok -eq $false) "action=$($envResult.Action)"
    Check "B: action is ambiguous" ($envResult.Action -eq "ambiguous_env")
    Check "B: backup still exists" (Test-Path (Join-Path $fakeBackend ".env._smoke_conflict1"))
    Check "B: original untouched" ((Get-Content (Join-Path $fakeBackend ".env") -Raw) -eq "ORIGINAL=true")
    Check "B: backup content intact" ((Get-Content (Join-Path $fakeBackend ".env._smoke_conflict1") -Raw) -eq "BACKUP=true")
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 4: Scenario C -- multiple backups -> fail, all preserved
# ======================================================================
Write-Host ""
Write-Host "[4] Scenario C: multiple backups -> fail, all preserved" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $fakeBackend = Join-Path $d "backend"
    New-Item -ItemType Directory -Force -Path $fakeBackend | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $d "frontend") | Out-Null
    New-Item -ItemType File -Path (Join-Path $fakeBackend ".env._smoke_multi1") -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $fakeBackend ".env._smoke_multi2") -Force | Out-Null
    Set-Content (Join-Path $fakeBackend ".env._smoke_multi1") "KEY1" -NoNewline
    Set-Content (Join-Path $fakeBackend ".env._smoke_multi2") "KEY2" -NoNewline

    $results = @(Resolve-OrphanedBackups -ProjectRoot $d)

    $envResult = $results | Where-Object { $_.Action -match "env" }
    Check "C: result not ok" ($envResult.Ok -eq $false)
    Check "C: action is multiple" ($envResult.Action -eq "multiple_env_backups")
    $afterBackups = @(Get-ChildItem $fakeBackend -Filter ".env._smoke_*" -Force -ErrorAction SilentlyContinue)
    Check "C: all backups still exist" ($afterBackups.Count -eq 2) "count=$($afterBackups.Count)"
    Check "C: multi1 content intact" ((Get-Content (Join-Path $fakeBackend ".env._smoke_multi1") -Raw) -eq "KEY1")
    Check "C: multi2 content intact" ((Get-Content (Join-Path $fakeBackend ".env._smoke_multi2") -Raw) -eq "KEY2")
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 5: Scenario D -- no backups -> no-op
# ======================================================================
Write-Host ""
Write-Host "[5] Scenario D: no backups -> no-op" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $fakeBackend = Join-Path $d "backend"
    New-Item -ItemType Directory -Force -Path $fakeBackend | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $d "frontend") | Out-Null
    Set-Content (Join-Path $fakeBackend ".env") "EXISTING=true" -NoNewline

    $results = @(Resolve-OrphanedBackups -ProjectRoot $d)

    $envResults = @($results | Where-Object { $_.Action -match "env" })
    Check "D: no env results" ($envResults.Count -eq 0)
    Check "D: original untouched" ((Get-Content (Join-Path $fakeBackend ".env") -Raw) -eq "EXISTING=true")
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 6: Restore-IsolatedItems -- rename + wait
# ======================================================================
Write-Host ""
Write-Host "[6] Restore-IsolatedItems: rename + wait" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $origDir = Join-Path $d "target"
    $backupDir = Join-Path $d "target._smoke_test"
    New-Item -ItemType Directory -Force -Path $origDir | Out-Null
    Set-Content (Join-Path $origDir "file.txt") "original" -NoNewline
    Rename-Item $origDir $backupDir -Force

    $items = @(@{ Orig = $origDir; Backup = $backupDir; Label = "test/target" })
    $results = @(Restore-IsolatedItems -Items $items)

    $r = $results[0]
    Check "6: result ok" ($r.Ok -eq $true) "action=$($r.Action)"
    Check "6: action is restored" ($r.Action -eq "restored")
    Check "6: original exists" (Test-Path $origDir)
    Check "6: backup gone" (-not (Test-Path $backupDir))
    if (Test-Path $origDir) {
        Check "6: content intact" ((Get-Content (Join-Path $origDir "file.txt") -Raw) -eq "original")
    }
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 7: Restore-IsolatedItems -- missing backup -> not ok
# ======================================================================
Write-Host ""
Write-Host "[7] Restore-IsolatedItems: missing backup -> not ok" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $items = @(@{ Orig = (Join-Path $d "nonexistent"); Backup = (Join-Path $d "nonexistent._smoke_xxx"); Label = "test/missing" })
    $results = @(Restore-IsolatedItems -Items $items)

    $r = $results[0]
    Check "7: result not ok" ($r.Ok -eq $false)
    Check "7: action is backup_missing" ($r.Action -eq "backup_missing")
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 8: FS retry helpers
# ======================================================================
Write-Host ""
Write-Host "[8] FS retry helpers" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $testFile = Join-Path $d "marker.txt"
    New-Item -ItemType File -Path $testFile -Force | Out-Null

    Check "8a: Wait-PathExists on existing" (Wait-PathExists -Path $testFile -TimeoutMs 500)
    Check "8b: Wait-PathGone on existing returns false" (-not (Wait-PathGone -Path $testFile -TimeoutMs 500))

    Remove-Item $testFile -Force
    Check "8c: Wait-PathGone after delete" (Wait-PathGone -Path $testFile -TimeoutMs 500)
    Check "8d: Wait-PathExists on missing returns false" (-not (Wait-PathExists -Path (Join-Path $d "nope.txt") -TimeoutMs 500))
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 9: Custom timeout passthrough
# ======================================================================
Write-Host ""
Write-Host "[9] Custom timeout passthrough" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $origDir = Join-Path $d "slow_target"
    $backupDir = Join-Path $d "slow_target._smoke_test"
    New-Item -ItemType Directory -Force -Path $origDir | Out-Null
    Rename-Item $origDir $backupDir -Force

    # Use a very short timeout to verify it's actually passed through
    $items = @(@{ Orig = $origDir; Backup = $backupDir; Label = "test/slow" })
    $results = @(Restore-IsolatedItems -Items $items -FsTimeoutMs 5000 -FsIntervalMs 100)

    Check "9: custom timeout restore ok" ($results[0].Ok -eq $true)
    Check "9: original exists" (Test-Path $origDir)
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 10: Safe-delete success via Resolve-OrphanedBackups
# ======================================================================
Write-Host ""
Write-Host "[10] Safe-delete: success path" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    # Create orphaned dist and .venv backups (no .env backup)
    $frontendDir = Join-Path $d "frontend"
    $backendDir = Join-Path $d "backend"
    New-Item -ItemType Directory -Force -Path $frontendDir | Out-Null
    New-Item -ItemType Directory -Force -Path $backendDir | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $frontendDir "dist._smoke_deltest") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $backendDir ".venv._smoke_deltest") | Out-Null

    $results = @(Resolve-OrphanedBackups -ProjectRoot $d)

    $distResult = $results | Where-Object { $_.Label -eq "frontend/dist backup" }
    Check "10: dist delete ok" ($distResult.Ok -eq $true) "action=$($distResult.Action)"
    Check "10: dist action is deleted_safe" ($distResult.Action -eq "deleted_safe")
    Check "10: dist directory gone" (-not (Test-Path (Join-Path $frontendDir "dist._smoke_deltest")))

    $venvResult = $results | Where-Object { $_.Label -eq "backend/.venv backup" }
    Check "10: venv delete ok" ($venvResult.Ok -eq $true) "action=$($venvResult.Action)"
    Check "10: venv action is deleted_safe" ($venvResult.Action -eq "deleted_safe")
    Check "10: venv directory gone" (-not (Test-Path (Join-Path $backendDir ".venv._smoke_deltest")))
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Test 11: Safe-delete failure (locked file)
# ======================================================================
Write-Host ""
Write-Host "[11] Safe-delete: failure path (locked file)" -ForegroundColor Yellow

$d = New-GuidTempDir
try {
    $frontendDir = Join-Path $d "frontend"
    New-Item -ItemType Directory -Force -Path $frontendDir | Out-Null
    $lockedDir = Join-Path $frontendDir "dist._smoke_locked"
    New-Item -ItemType Directory -Force -Path $lockedDir | Out-Null
    $lockedFile = Join-Path $lockedDir "lock.txt"
    Set-Content $lockedFile "locked" -NoNewline

    # Open an exclusive handle to prevent deletion
    $handle = [System.IO.File]::Open($lockedFile, 'Open', 'Read', 'None')

    try {
        # Use a very short timeout so the test doesn't wait 3 seconds
        $results = @(Resolve-OrphanedBackups -ProjectRoot $d -FsTimeoutMs 500 -FsIntervalMs 100)

        $distResult = $results | Where-Object { $_.Label -eq "frontend/dist backup" }
        Check "11: dist delete failed" ($distResult.Ok -eq $false) "action=$($distResult.Action)"
        Check "11: dist action is delete_failed" ($distResult.Action -eq "delete_failed")
        Check "11: dist path present" ($distResult.Path -eq $lockedDir)
        Check "11: dist still exists" (Test-Path $lockedDir)
    } finally {
        $handle.Close()
    }
} finally {
    Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
}

# ======================================================================
# Summary
# ======================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor $(if ($script:failed -eq 0) { "Green" } else { "Red" })
Write-Host "  Results: $($script:passed) passed, $($script:failed) failed" -ForegroundColor $(if ($script:failed -eq 0) { "Green" } else { "Red" })
Write-Host "========================================" -ForegroundColor $(if ($script:failed -eq 0) { "Green" } else { "Red" })
Write-Host ""

exit $(if ($script:failed -eq 0) { 0 } else { 1 })

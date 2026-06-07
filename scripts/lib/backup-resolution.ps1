# backup-resolution.ps1 -- Shared backup resolution and FS retry helpers
# Dot-sourced by test-start-app-windows.ps1 and test-backup-resolution.ps1
#
# DESIGN:
#   - Library functions return structured [PSCustomObject] results, never Write-Host.
#   - The caller (production script) owns all user-facing output.
#   - FS retry timeouts are configurable at every call site.
#   - Restore-first policy: backups are NEVER force-deleted.

# -- Default FS timing (overridable by caller) --
$script:FS_DEFAULT_TIMEOUT_MS  = 3000
$script:FS_DEFAULT_INTERVAL_MS = 200

# ======================================================================
# FS retry helpers
# ======================================================================

function Wait-PathGone {
    <#
    .SYNOPSIS  Wait until a path no longer exists.
    .OUTPUTS   [bool] $true if gone within timeout.
    #>
    param(
        [Parameter(Mandatory)][string]$Path,
        [int]$TimeoutMs  = $script:FS_DEFAULT_TIMEOUT_MS,
        [int]$IntervalMs = $script:FS_DEFAULT_INTERVAL_MS
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutMs) {
        if (-not (Test-Path $Path)) { return $true }
        Start-Sleep -Milliseconds $IntervalMs
        $elapsed += $IntervalMs
    }
    return -not (Test-Path $Path)
}

function Wait-PathExists {
    <#
    .SYNOPSIS  Wait until a path exists.
    .OUTPUTS   [bool] $true if exists within timeout.
    #>
    param(
        [Parameter(Mandatory)][string]$Path,
        [int]$TimeoutMs  = $script:FS_DEFAULT_TIMEOUT_MS,
        [int]$IntervalMs = $script:FS_DEFAULT_INTERVAL_MS
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutMs) {
        if (Test-Path $Path) { return $true }
        Start-Sleep -Milliseconds $IntervalMs
        $elapsed += $IntervalMs
    }
    return (Test-Path $Path)
}

# ======================================================================
# Result constructors
# ======================================================================
# Library functions return arrays of these. The caller decides how to print.

function New-Result {
    param(
        [bool]$Ok,
        [string]$Action,
        [string]$Label = "",
        [string]$Detail = "",
        [string]$Error = "",
        [string]$Path = ""
    )
    [PSCustomObject]@{
        Ok     = $Ok
        Action = $Action
        Label  = $Label
        Detail = $Detail
        Error  = $Error
        Path   = $Path
    }
}

# ======================================================================
# Resolve-OrphanedBackups
# ======================================================================

function Resolve-OrphanedBackups {
    <#
    .SYNOPSIS  Clean up or restore orphaned smoke backups from prior runs.
    .PARAMETER ProjectRoot   Root directory of the project.
    .PARAMETER FsTimeoutMs   FS retry timeout in ms (default 3000).
    .PARAMETER FsIntervalMs  FS retry poll interval in ms (default 200).
    .OUTPUTS   Array of result objects. Never throws -- caller checks .Ok.
    #>
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [int]$FsTimeoutMs  = $script:FS_DEFAULT_TIMEOUT_MS,
        [int]$FsIntervalMs = $script:FS_DEFAULT_INTERVAL_MS
    )

    $results = @()

    # -- Safe to delete: build artifacts and recreatable venv --
    foreach ($pattern in @(
        @{ Dir = Join-Path $ProjectRoot "frontend"; Filter = "dist._smoke_*";  Label = "frontend/dist backup" },
        @{ Dir = Join-Path $ProjectRoot "backend";  Filter = ".venv._smoke_*"; Label = "backend/.venv backup" }
    )) {
        $orphans = Get-ChildItem $pattern.Dir -Filter $pattern.Filter -ErrorAction SilentlyContinue
        foreach ($orphan in $orphans) {
            Remove-Item $orphan.FullName -Recurse -Force -ErrorAction SilentlyContinue
            if (Wait-PathGone -Path $orphan.FullName -TimeoutMs $FsTimeoutMs -IntervalMs $FsIntervalMs) {
                $results += New-Result -Ok $true -Action "deleted_safe" -Label $pattern.Label -Detail $orphan.Name
            } else {
                $results += New-Result -Ok $false -Action "delete_failed" -Label $pattern.Label `
                    -Detail $orphan.Name -Path $orphan.FullName `
                    -Error "still exists after Remove-Item (FS wait timeout)"
            }
        }
    }

    # -- NEVER auto-delete: .env backups may contain API keys --
    # NOTE: -Filter ".env._smoke_*" is required. "._smoke_*" does NOT match
    # ".env._smoke_abc" because the wildcard matches from the start of the name.
    $backendDir = Join-Path $ProjectRoot "backend"
    $envOrphans = @(Get-ChildItem $backendDir -Filter ".env._smoke_*" -Force -ErrorAction SilentlyContinue)

    if ($envOrphans.Count -eq 0) {
        return $results
    }

    $envOriginal = Join-Path $backendDir ".env"

    if ($envOrphans.Count -eq 1 -and -not (Test-Path $envOriginal)) {
        # Original missing, single backup -- restore
        $orphan = $envOrphans[0]
        try {
            Rename-Item $orphan.FullName $envOriginal -Force -ErrorAction Stop
            $ok = Wait-PathExists -Path $envOriginal -TimeoutMs $FsTimeoutMs -IntervalMs $FsIntervalMs
            $results += New-Result -Ok $ok -Action "restored_env" -Label ".env backup" `
                -Detail $orphan.Name -Path $envOriginal `
                -Error $(if (-not $ok) { "rename returned but .env not found after wait" } else { "" })
        } catch {
            $results += New-Result -Ok $false -Action "restore_env_failed" -Label ".env backup" `
                -Detail $orphan.Name -Path $orphan.FullName -Error $_.Exception.Message
        }
    } elseif ($envOrphans.Count -eq 1 -and (Test-Path $envOriginal)) {
        # Both exist -- ambiguous
        $results += New-Result -Ok $false -Action "ambiguous_env" -Label ".env backup" `
            -Detail "original and backup both exist" `
            -Path "$envOriginal | $($envOrphans[0].FullName)" `
            -Error "Found .env backup alongside existing .env -- cannot auto-resolve"
    } else {
        # Multiple backups
        $paths = ($envOrphans | ForEach-Object { $_.FullName }) -join " | "
        $results += New-Result -Ok $false -Action "multiple_env_backups" -Label ".env backup" `
            -Detail "$($envOrphans.Count) backups found" `
            -Path $paths `
            -Error "Found multiple .env backups -- cannot auto-resolve"
    }

    return $results
}

# ======================================================================
# Restore-IsolatedItems
# ======================================================================

function Restore-IsolatedItems {
    <#
    .SYNOPSIS  Restore backup directories to their original locations.
    .PARAMETER Items         Array of @{Orig; Backup; Label} from isolation phase.
    .PARAMETER FsTimeoutMs   FS retry timeout in ms (default 3000).
    .PARAMETER FsIntervalMs  FS retry poll interval in ms (default 200).
    .OUTPUTS   Array of result objects. Never force-deletes a backup.
    #>
    param(
        [Parameter(Mandatory)][array]$Items,
        [int]$FsTimeoutMs  = $script:FS_DEFAULT_TIMEOUT_MS,
        [int]$FsIntervalMs = $script:FS_DEFAULT_INTERVAL_MS
    )

    $results = @()

    foreach ($entry in $Items) {
        # Step 1: Remove whatever was created in its place during the test
        try {
            if (Test-Path $entry.Orig) {
                Remove-Item $entry.Orig -Recurse -Force -ErrorAction Stop
                if (-not (Wait-PathGone -Path $entry.Orig -TimeoutMs $FsTimeoutMs -IntervalMs $FsIntervalMs)) {
                    $results += New-Result -Ok $false -Action "remove_failed" -Label $entry.Label `
                        -Path $entry.Orig -Error "still exists after removal (FS wait timeout)"
                    continue
                }
            }
        } catch {
            $results += New-Result -Ok $false -Action "remove_failed" -Label $entry.Label `
                -Path $entry.Orig -Error $_.Exception.Message
            continue
        }

        # Step 2: Rename backup back to original
        try {
            if (Test-Path $entry.Backup) {
                Rename-Item $entry.Backup $entry.Orig -Force -ErrorAction Stop
                $exists = Wait-PathExists -Path $entry.Orig -TimeoutMs $FsTimeoutMs -IntervalMs $FsIntervalMs
                if ($exists) {
                    $results += New-Result -Ok $true -Action "restored" -Label $entry.Label -Path $entry.Orig
                } else {
                    $results += New-Result -Ok $false -Action "restore_race" -Label $entry.Label `
                        -Path $entry.Backup -Error "rename returned but orig not found after wait"
                }
            } else {
                $results += New-Result -Ok $false -Action "backup_missing" -Label $entry.Label `
                    -Path $entry.Backup -Error "backup not found"
            }
        } catch {
            $results += New-Result -Ok $false -Action "rename_failed" -Label $entry.Label `
                -Path $entry.Backup -Error $_.Exception.Message
        }
    }

    # Final verification: no backup directories should remain
    foreach ($entry in $Items) {
        if (Test-Path $entry.Backup) {
            if (-not (Wait-PathGone -Path $entry.Backup -TimeoutMs $FsTimeoutMs -IntervalMs $FsIntervalMs)) {
                $results += New-Result -Ok $false -Action "backup_remains" -Label $entry.Label `
                    -Path $entry.Backup -Error "backup still exists after restore (manual cleanup needed)"
            }
        }
    }

    return $results
}

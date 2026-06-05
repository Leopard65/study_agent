# 考研学习助手 — Windows 停止脚本
# 用法：在项目根目录 PowerShell 中运行：
#   powershell -ExecutionPolicy Bypass -File scripts\stop-windows.ps1
#
# 参数：
#   -Force    端口兜底时无需确认进程身份，直接停止占用 8000/5173 的进程

param(
    [switch]$Force
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StateFile = Join-Path $ProjectRoot "scripts\.running_pids"

# ── 进程树停止工具 ──
function Stop-ProcessTree {
    <#
    .SYNOPSIS
    递归停止指定 PID 及其所有子进程（通过 Win32_Process ParentProcessId 查询）。
    #>
    param([int]$ProcessId)
    try {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            Stop-ProcessTree -ProcessId $child.ProcessId
        }
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {}
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  考研学习助手 — 停止脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$stopped = 0
$seenPids = @{}

# 1. 从 PID 文件读取并停止进程树
if (Test-Path $StateFile) {
    $lines = Get-Content $StateFile
    foreach ($line in $lines) {
        if ($line -match '^(backend|frontend)=(\d+)$') {
            $name = $Matches[1]
            $procId = [int]$Matches[2]
            if ($seenPids.ContainsKey($procId)) { continue }
            $seenPids[$procId] = $true
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Stop-ProcessTree -ProcessId $procId
                Write-Host "  已停止 $name 及其子进程 (PID $procId)" -ForegroundColor Green
                $stopped++
            } else {
                Write-Host "  $name 进程 (PID $procId) 已不在运行" -ForegroundColor Gray
            }
        }
    }
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    Write-Host ""
} else {
    Write-Host "  未找到 PID 记录文件，尝试按端口停止..." -ForegroundColor Yellow
}

# 2. 兜底：按端口查找并停止残留进程（默认需确认进程属于本项目）
foreach ($port in @(8000, 5173)) {
    try {
        $netstat = netstat -ano 2>&1 | Select-String ":$port\s.*LISTENING"
        foreach ($line in $netstat) {
            if ($line.ToString() -match '\s(\d+)\s*$') {
                $procId = [int]$Matches[1]
                if ($seenPids.ContainsKey($procId)) { continue }
                $seenPids[$procId] = $true
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($proc) {
                    if (-not $Force) {
                        # 检查进程命令行是否属于本项目（uvicorn/vite/math_agent）
                        $cmdLine = ""
                        try {
                            $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
                            if ($cim -and $cim.CommandLine) { $cmdLine = $cim.CommandLine }
                        } catch {}
                        $isOurs = $cmdLine -match "uvicorn|vite|math_agent|node.*dev"
                        if (-not $isOurs) {
                            Write-Host "  跳过端口 $port 的进程: $($proc.ProcessName) (PID $procId) — 不属于本项目" -ForegroundColor Yellow
                            $displayCmd = if ($cmdLine) { $cmdLine.Substring(0, [Math]::Min(120, $cmdLine.Length)) } else { "(无法读取命令行)" }
                            Write-Host "    命令行: $displayCmd" -ForegroundColor Gray
                            Write-Host "    使用 -Force 参数可强制停止" -ForegroundColor Gray
                            continue
                        }
                    }
                    Stop-ProcessTree -ProcessId $procId
                    Write-Host "  已停止占用端口 $port 的进程: $($proc.ProcessName) (PID $procId)" -ForegroundColor Green
                    $stopped++
                }
            }
        }
    } catch {}
}

if ($stopped -eq 0) {
    Write-Host "  没有发现正在运行的服务" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "  共停止 $stopped 个进程（含子进程树）" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

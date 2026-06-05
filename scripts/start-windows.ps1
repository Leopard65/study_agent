# 考研学习助手 — Windows 一键启动脚本
# 用法：在项目根目录 PowerShell 中运行：
#   powershell -ExecutionPolicy Bypass -File scripts\start-windows.ps1
#
# 参数：
#   -NoOpenBrowser        不自动打开浏览器
#   -AutoStopAfterSeconds N  启动后 N 秒自动停止（用于测试），默认不自动停止
#
# 停止服务：关闭此窗口、按任意键、或运行 scripts\stop-windows.ps1

param(
    [switch]$NoOpenBrowser,
    [int]$AutoStopAfterSeconds = 0
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StateFile = Join-Path $ProjectRoot "scripts\.running_pids"
$BackendLog = Join-Path $ProjectRoot "scripts\backend.log"
$FrontendLog = Join-Path $ProjectRoot "scripts\frontend.log"

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

function Stop-Services {
    <#
    .SYNOPSIS
    停止所有本应用服务：先按 PID 文件停止进程树，再按端口兜底。
    #>
    param([switch]$Quiet)
    $stopped = 0
    $seenPids = @{}

    # 1. 按 PID 文件停止进程树
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
                    if (-not $Quiet) {
                        Write-Host "  已停止 $name 及其子进程 (PID $procId)" -ForegroundColor Green
                    }
                    $stopped++
                }
            }
        }
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    }

    # 2. 按端口兜底清理（仅停止属于本项目的进程：uvicorn/vite/math_agent）
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
                        # 检查进程命令行是否属于本项目
                        $cmdLine = ""
                        try {
                            $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
                            if ($cim) { $cmdLine = $cim.CommandLine }
                        } catch {}
                        $isOurs = $cmdLine -match "uvicorn|vite|math_agent|node.*dev"
                        if (-not $isOurs) {
                            if (-not $Quiet) {
                                Write-Host "  跳过端口 $port 的进程: $($proc.ProcessName) (PID $procId) — 不属于本项目" -ForegroundColor Yellow
                            }
                            continue
                        }
                        Stop-ProcessTree -ProcessId $procId
                        if (-not $Quiet) {
                            Write-Host "  已停止占用端口 $port 的进程: $($proc.ProcessName) (PID $procId)" -ForegroundColor Green
                        }
                        $stopped++
                    }
                }
            }
        } catch {}
    }

    return $stopped
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  考研学习助手 — 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 检查 Python ──
Write-Host "[1/6] 检查 Python..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    if ($pyVer -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Host "  错误：需要 Python 3.10+，当前为 $pyVer" -ForegroundColor Red
            Write-Host "  请前往 https://www.python.org/downloads/ 下载安装" -ForegroundColor Red
            exit 1
        }
        Write-Host "  $pyVer OK" -ForegroundColor Green
    }
} catch {
    Write-Host "  错误：未找到 Python，请前往 https://www.python.org/downloads/ 下载安装" -ForegroundColor Red
    Write-Host "  安装时请勾选「Add to PATH」" -ForegroundColor Red
    exit 1
}

# ── 检查 Node.js ──
Write-Host "[2/6] 检查 Node.js..." -ForegroundColor Yellow
try {
    $nodeVer = node --version 2>&1
    if ($nodeVer -match "v(\d+)") {
        $nodeMajor = [int]$Matches[1]
        if ($nodeMajor -lt 18) {
            Write-Host "  错误：需要 Node.js 18+，当前为 $nodeVer" -ForegroundColor Red
            Write-Host "  请前往 https://nodejs.org/ 下载 LTS 版本安装" -ForegroundColor Red
            exit 1
        }
        Write-Host "  $nodeVer OK" -ForegroundColor Green
    }
} catch {
    Write-Host "  错误：未找到 Node.js，请前往 https://nodejs.org/ 下载 LTS 版本安装" -ForegroundColor Red
    exit 1
}

# ── 创建 .venv 并安装后端依赖 ──
Write-Host "[3/6] 安装后端依赖..." -ForegroundColor Yellow
$backendDir = Join-Path $ProjectRoot "backend"
$venvDir = Join-Path $backendDir ".venv"

if (-not (Test-Path (Join-Path $venvDir "Scripts\python.exe"))) {
    Write-Host "  创建虚拟环境..." -ForegroundColor Gray
    & python -m venv $venvDir
}

$pipExe = Join-Path $venvDir "Scripts\pip.exe"
$pyExe = Join-Path $venvDir "Scripts\python.exe"

# 检查是否需要安装（venv 刚创建或 requirements 更改）
$reqFile = Join-Path $backendDir "requirements.txt"
$markerFile = Join-Path $venvDir ".deps_installed"
$needInstall = $true
if (Test-Path $markerFile) {
    $installedTime = (Get-Item $markerFile).LastWriteTime
    $reqTime = (Get-Item $reqFile).LastWriteTime
    if ($reqTime -le $installedTime) {
        $needInstall = $false
    }
}

if ($needInstall) {
    Write-Host "  pip install（首次可能较慢）..." -ForegroundColor Gray
    & $pipExe install -r $reqFile --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  错误：pip install 失败" -ForegroundColor Red
        exit 1
    }
    New-Item -ItemType File -Path $markerFile -Force | Out-Null
}
Write-Host "  后端依赖 OK" -ForegroundColor Green

# ── 创建 .env 并检查 API Key ──
Write-Host "[4/6] 检查配置文件..." -ForegroundColor Yellow
$envFile = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"
$apiKeyConfigured = $false

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "  已从 .env.example 创建 .env" -ForegroundColor Green
    } else {
        # 创建最小 .env
        @"
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=
OPENAI_MODEL=deepseek-v4-flash
"@ | Out-File -FilePath $envFile -Encoding utf8
        Write-Host "  已创建最小 .env" -ForegroundColor Green
    }
} else {
    Write-Host "  .env 已存在，跳过" -ForegroundColor Green
}

# 检查 .env 中的 API Key 是否已配置（跳过注释行）
$placeholders = @("", "your_api_key_here", "your_deepseek_api_key", "replace_me", "sk-xxx", "sk-your-key-here", "your_openai_api_key", "xxx")
$envLines = Get-Content $envFile -ErrorAction SilentlyContinue
foreach ($envLine in $envLines) {
    $trimmed = $envLine.Trim()
    # 跳过注释行和空行
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    if ($trimmed -match '^OPENAI_API_KEY\s*=\s*(.*)$') {
        $val = $Matches[1].Trim().Trim('"').Trim("'")
        if ($val -and $val.ToLower() -notin $placeholders) {
            $apiKeyConfigured = $true
        }
        break  # 只看第一个非注释的 OPENAI_API_KEY
    }
}

if (-not $apiKeyConfigured) {
    Write-Host ""
    Write-Host "  ┌─────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "  │  OPENAI_API_KEY 未配置或为占位符             │" -ForegroundColor Yellow
    Write-Host "  │                                             │" -ForegroundColor Yellow
    Write-Host "  │  核心功能（错题本/复习/资料/计划/练习）可直接使用 │" -ForegroundColor Yellow
    Write-Host "  │  AI 功能（问答/解析/生成）需要真实的 API Key   │" -ForegroundColor Yellow
    Write-Host "  │                                             │" -ForegroundColor Yellow
    Write-Host "  │  如需 AI 功能：                              │" -ForegroundColor Yellow
    Write-Host "  │  1. 编辑 backend\.env                        │" -ForegroundColor Yellow
    Write-Host "  │  2. 填入 OPENAI_API_KEY=你的Key              │" -ForegroundColor Yellow
    Write-Host "  │  3. 重新运行本脚本                           │" -ForegroundColor Yellow
    Write-Host "  └─────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  API Key 已配置" -ForegroundColor Green
}

# ── 安装前端依赖 ──
Write-Host "[5/6] 安装前端依赖..." -ForegroundColor Yellow
$frontendDir = Join-Path $ProjectRoot "frontend"
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "  npm install（首次可能较慢）..." -ForegroundColor Gray
    Push-Location $frontendDir
    & npm install --silent 2>&1 | Out-Null
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  错误：npm install 失败" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  前端依赖 OK" -ForegroundColor Green

# ── 端口检查 ──
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

function Get-PortProcess {
    param([int]$Port)
    try {
        $netstat = netstat -ano 2>&1 | Select-String ":$Port\s"
        if ($netstat) {
            $line = ($netstat | Select-Object -First 1).ToString()
            if ($line -match '\s(\d+)\s*$') {
                $procId = $Matches[1]
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($proc) {
                    return "$($proc.ProcessName) (PID $procId)"
                }
            }
        }
    } catch {}
    return $null
}

# ── 启动后端和前端 ──
Write-Host "[6/6] 启动服务..." -ForegroundColor Yellow
Write-Host ""

# Check ports
foreach ($portName in @(@{Port=8000; Name="后端"}, @{Port=5173; Name="前端"})) {
    if (Test-PortInUse $portName.Port) {
        $who = Get-PortProcess $portName.Port
        if ($who) {
            Write-Host "  错误：端口 $($portName.Port)（$($portName.Name)）已被占用 — $who" -ForegroundColor Red
            Write-Host "  请先关闭占用进程，或运行 scripts\stop-windows.ps1 停止旧服务" -ForegroundColor Red
        } else {
            Write-Host "  错误：端口 $($portName.Port)（$($portName.Name)）已被占用" -ForegroundColor Red
        }
        exit 1
    }
}

# 启动后端（后台，直接用 cmd /c 内联命令，避免 .bat 文件的编码问题）
# < NUL 重定向 stdin 防止进程读取 stdin 时崩溃
# 注意：/c 和后续命令必须作为单个参数传递给 cmd.exe，否则 cmd.exe 不会正确解析
$backendCmd = "/c `"`"$pyExe`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > `"$BackendLog`" 2>&1 < NUL`""
$backendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList $backendCmd `
    -WorkingDirectory $backendDir `
    -PassThru `
    -WindowStyle Minimized

$backendPid = $backendProc.Id
Write-Host "  后端进程 PID: $backendPid" -ForegroundColor Gray

# 等待后端启动（使用 .NET WebClient 避免 PowerShell NonInteractive 模式问题）
$retries = 0
$backendReady = $false
while ($retries -lt 30) {
    try {
        $wc = New-Object System.Net.WebClient
        $null = $wc.DownloadString("http://127.0.0.1:8000/api/health")
        $backendReady = $true
        break
    } catch {
        # 检查进程是否已退出
        if ($backendProc.HasExited) {
            Write-Host ""
            Write-Host "  错误：后端启动失败（进程已退出）" -ForegroundColor Red
            Write-Host "  查看日志：$BackendLog" -ForegroundColor Yellow
            if (Test-Path $BackendLog) {
                Write-Host "  ── 最后 10 行日志 ──" -ForegroundColor Gray
                Get-Content $BackendLog -Tail 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            }
            exit 1
        }
        Start-Sleep -Milliseconds 500
        $retries++
    }
}

if (-not $backendReady) {
    Write-Host ""
    Write-Host "  错误：后端启动超时（15 秒）" -ForegroundColor Red
    Write-Host "  查看日志：$BackendLog" -ForegroundColor Yellow
    # 清理已启动的后端
    Stop-ProcessTree -ProcessId $backendPid
    exit 1
}

Write-Host "  后端已启动: http://127.0.0.1:8000" -ForegroundColor Green

# 启动前端（后台，直接用 cmd /c 内联命令）
# CI=1 禁用 Vite/npm 交互模式；< NUL 重定向 stdin 防止 EPIPE
# 注意：/c 和后续命令必须作为单个参数传递给 cmd.exe
$frontendCmd = "/c `"set `"CI=1`" && npm run dev > `"$FrontendLog`" 2>&1 < NUL`""
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList $frontendCmd `
    -WorkingDirectory $frontendDir `
    -PassThru `
    -WindowStyle Minimized

$frontendPid = $frontendProc.Id
Write-Host "  前端进程 PID: $frontendPid" -ForegroundColor Gray

# 等待前端启动（使用 .NET WebClient）
$frontendReady = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $wc = New-Object System.Net.WebClient
        $null = $wc.DownloadString("http://127.0.0.1:5173")
        $frontendReady = $true
        break
    } catch {
        if ($frontendProc.HasExited) {
            break
        }
    }
}

if (-not $frontendReady) {
    Write-Host ""
    Write-Host "  错误：前端启动失败" -ForegroundColor Red
    Write-Host "  查看日志：$FrontendLog" -ForegroundColor Yellow
    if (Test-Path $FrontendLog) {
        Write-Host "  ── 最后 10 行日志 ──" -ForegroundColor Gray
        Get-Content $FrontendLog -Tail 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    }
    Write-Host "  后端日志：$BackendLog" -ForegroundColor Yellow
    # 清理所有已启动进程
    Stop-ProcessTree -ProcessId $backendPid
    exit 1
}

Write-Host "  前端已启动: http://127.0.0.1:5173" -ForegroundColor Green

# 保存 PID 到文件（供 stop-windows.ps1 使用）
@"
backend=$backendPid
frontend=$frontendPid
"@ | Out-File -FilePath $StateFile -Encoding utf8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  浏览器打开：http://localhost:5173" -ForegroundColor White
Write-Host ""
if (-not $apiKeyConfigured) {
    Write-Host "  状态：核心功能可用，AI 功能未配置" -ForegroundColor Yellow
} else {
    Write-Host "  状态：全部功能可用" -ForegroundColor Green
}
Write-Host ""
Write-Host "  日志文件（出错时可查看）：" -ForegroundColor Gray
Write-Host "    后端: $BackendLog" -ForegroundColor Gray
Write-Host "    前端: $FrontendLog" -ForegroundColor Gray
Write-Host ""
Write-Host "  按任意键停止所有服务并退出" -ForegroundColor Gray
Write-Host "  或运行 scripts\stop-windows.ps1 停止" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# ── 测试模式：自动停止 ──
if ($AutoStopAfterSeconds -gt 0) {
    Write-Host "  [测试模式] ${AutoStopAfterSeconds} 秒后自动停止..." -ForegroundColor Cyan
    Start-Sleep -Seconds $AutoStopAfterSeconds
    Write-Host ""
    Write-Host "  正在停止所有服务..." -ForegroundColor Gray
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    Stop-Services | Out-Null
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    $ErrorActionPreference = $savedEAP
    Write-Host "  服务已停止" -ForegroundColor Green
    exit 0
}

# ── 普通模式：打开浏览器并等待按键 ──
if (-not $NoOpenBrowser) {
    Start-Process "http://localhost:5173"
}

# 等待用户按键，然后停止所有服务
try {
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
} finally {
    Write-Host ""
    Write-Host "  正在停止所有服务..." -ForegroundColor Gray
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    Stop-Services | Out-Null
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    $ErrorActionPreference = $savedEAP
    Write-Host "  服务已停止" -ForegroundColor Green
}

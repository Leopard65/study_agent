# 考研学习助手 — 生产/类 App 单服务启动脚本
# 用法：在项目根目录 PowerShell 中运行：
#   powershell -ExecutionPolicy Bypass -File scripts\start-app-windows.ps1
#
# 参数：
#   -NoOpenBrowser        不自动打开浏览器
#   -AutoStopAfterSeconds N  启动后 N 秒自动停止（用于测试），默认不自动停止
#
# 与 start-windows.ps1 的区别：
#   - 本脚本只启动 FastAPI 一个服务（不启动 Vite）
#   - FastAPI 直接托管 frontend/dist 静态资源
#   - 访问地址为 http://127.0.0.1:8000
#   - 适合生产部署或"类 App"使用模式

param(
    [switch]$NoOpenBrowser,
    [int]$AutoStopAfterSeconds = 0
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StateFile = Join-Path $ProjectRoot "scripts\.running_pids"
$BackendLog = Join-Path $ProjectRoot "scripts\backend.log"

# ── 进程树停止工具 ──
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

function Stop-Services {
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

    # 2. 按端口兜底清理
    foreach ($port in @(8000)) {
        try {
            $netstat = netstat -ano 2>&1 | Select-String ":$port\s.*LISTENING"
            foreach ($line in $netstat) {
                if ($line.ToString() -match '\s(\d+)\s*$') {
                    $procId = [int]$Matches[1]
                    if ($seenPids.ContainsKey($procId)) { continue }
                    $seenPids[$procId] = $true
                    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                    if ($proc) {
                        $cmdLine = ""
                        try {
                            $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
                            if ($cim) { $cmdLine = $cim.CommandLine }
                        } catch {}
                        $isOurs = $cmdLine -match "uvicorn|math_agent"
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
Write-Host "  考研学习助手 — 生产模式启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 检查 Python ──
Write-Host "[1/5] 检查 Python..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    if ($pyVer -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Host "  错误：需要 Python 3.10+，当前为 $pyVer" -ForegroundColor Red
            exit 1
        }
        Write-Host "  $pyVer OK" -ForegroundColor Green
    }
} catch {
    Write-Host "  错误：未找到 Python" -ForegroundColor Red
    exit 1
}

# ── 创建 .venv 并安装后端依赖 ──
Write-Host "[2/5] 安装后端依赖..." -ForegroundColor Yellow
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

# ── 检查 frontend/dist ──
Write-Host "[3/5] 检查前端构建..." -ForegroundColor Yellow
$distDir = Join-Path $ProjectRoot "frontend\dist"
if (-not (Test-Path (Join-Path $distDir "index.html"))) {
    Write-Host "  frontend/dist/index.html 不存在，尝试构建..." -ForegroundColor Gray
    $frontendDir = Join-Path $ProjectRoot "frontend"
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Host "  安装前端依赖..." -ForegroundColor Gray
        Push-Location $frontendDir
        & npm install --silent 2>&1 | Out-Null
        Pop-Location
    }
    Push-Location $frontendDir
    & npm run build 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  错误：前端构建失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "  前端构建完成" -ForegroundColor Green
} else {
    Write-Host "  frontend/dist OK" -ForegroundColor Green
}

# ── 创建 .env 并检查 API Key ──
Write-Host "[4/5] 检查配置文件..." -ForegroundColor Yellow
$envFile = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"
$apiKeyConfigured = $false

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "  已从 .env.example 创建 .env" -ForegroundColor Green
    }
}

$placeholders = @("", "your_api_key_here", "your_deepseek_api_key", "replace_me", "sk-xxx", "sk-your-key-here", "your_openai_api_key", "xxx")
$envLines = Get-Content $envFile -ErrorAction SilentlyContinue
foreach ($envLine in $envLines) {
    $trimmed = $envLine.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    if ($trimmed -match '^OPENAI_API_KEY\s*=\s*(.*)$') {
        $val = $Matches[1].Trim().Trim('"').Trim("'")
        if ($val -and $val.ToLower() -notin $placeholders) {
            $apiKeyConfigured = $true
        }
        break
    }
}

if (-not $apiKeyConfigured) {
    Write-Host ""
    Write-Host "  ┌─────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "  │  OPENAI_API_KEY 未配置或为占位符             │" -ForegroundColor Yellow
    Write-Host "  │  核心功能可用，AI 功能未配置                 │" -ForegroundColor Yellow
    Write-Host "  └─────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  API Key 已配置" -ForegroundColor Green
}

# ── 端口检查 ──
Write-Host "[5/5] 启动服务..." -ForegroundColor Yellow

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
    Write-Host "  错误：端口 8000 已被占用" -ForegroundColor Red
    Write-Host "  请先关闭占用进程，或运行 scripts\stop-windows.ps1" -ForegroundColor Red
    exit 1
}

# 启动后端（后台）
$backendCmd = "/c `"`"$pyExe`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > `"$BackendLog`" 2>&1 < NUL`""
$backendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList $backendCmd `
    -WorkingDirectory $backendDir `
    -PassThru `
    -WindowStyle Minimized

$backendPid = $backendProc.Id
Write-Host "  后端进程 PID: $backendPid" -ForegroundColor Gray

# 等待后端启动
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
            Write-Host ""
            Write-Host "  错误：后端启动失败（进程已退出）" -ForegroundColor Red
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
    Stop-ProcessTree -ProcessId $backendPid
    exit 1
}

Write-Host "  后端已启动: http://127.0.0.1:8000" -ForegroundColor Green

# 验证前端页面可访问
$frontendReady = $false
try {
    $wc = New-Object System.Net.WebClient
    $null = $wc.DownloadString("http://127.0.0.1:8000/")
    $frontendReady = $true
    Write-Host "  前端页面已托管: http://127.0.0.1:8000/" -ForegroundColor Green
} catch {
    Write-Host "  警告：前端页面可能未正确托管，但 API 仍可访问" -ForegroundColor Yellow
}

# 保存 PID
@"
backend=$backendPid
"@ | Out-File -FilePath $StateFile -Encoding utf8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  浏览器打开：http://127.0.0.1:8000" -ForegroundColor White
Write-Host ""
if (-not $apiKeyConfigured) {
    Write-Host "  状态：核心功能可用，AI 功能未配置" -ForegroundColor Yellow
} else {
    Write-Host "  状态：全部功能可用" -ForegroundColor Green
}
Write-Host ""
Write-Host "  模式：生产模式（单服务，FastAPI 托管前端）" -ForegroundColor Cyan
Write-Host ""
Write-Host "  日志文件：$BackendLog" -ForegroundColor Gray
Write-Host ""
Write-Host "  按任意键停止服务并退出" -ForegroundColor Gray
Write-Host "  或运行 scripts\stop-windows.ps1 停止" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# ── 测试模式 ──
if ($AutoStopAfterSeconds -gt 0) {
    Write-Host "  [测试模式] ${AutoStopAfterSeconds} 秒后自动停止..." -ForegroundColor Cyan
    Start-Sleep -Seconds $AutoStopAfterSeconds
    Write-Host ""
    Write-Host "  正在停止服务..." -ForegroundColor Gray
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    Stop-Services | Out-Null
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    $ErrorActionPreference = $savedEAP
    Write-Host "  服务已停止" -ForegroundColor Green
    exit 0
}

# ── 普通模式 ──
if (-not $NoOpenBrowser) {
    Start-Process "http://127.0.0.1:8000"
}

try {
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
} finally {
    Write-Host ""
    Write-Host "  正在停止服务..." -ForegroundColor Gray
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    Stop-Services | Out-Null
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    $ErrorActionPreference = $savedEAP
    Write-Host "  服务已停止" -ForegroundColor Green
}

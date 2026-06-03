# 考研学习助手 — Windows 一键启动脚本
# 用法：在项目根目录右键「在终端中打开」或 PowerShell 中运行：
#   powershell -ExecutionPolicy Bypass -File scripts\start-windows.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

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

# ── 创建 .env（如果不存在） ──
Write-Host "[4/6] 检查配置文件..." -ForegroundColor Yellow
$envFile = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "  已从 .env.example 创建 .env" -ForegroundColor Green
        Write-Host "  如需 AI 功能，请编辑 backend\.env 填入 OPENAI_API_KEY" -ForegroundColor Yellow
    } else {
        # 创建最小 .env
        @"
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=
OPENAI_MODEL=deepseek-v4-flash
"@ | Out-File -FilePath $envFile -Encoding utf8
        Write-Host "  已创建最小 .env（AI 功能需手动填入 API Key）" -ForegroundColor Green
    }
} else {
    Write-Host "  .env 已存在，跳过" -ForegroundColor Green
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

# ── 启动后端和前端 ──
Write-Host "[6/6] 启动服务..." -ForegroundColor Yellow
Write-Host ""

# 启动后端（后台）
$backendJob = Start-Process -FilePath $pyExe `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backendDir `
    -PassThru `
    -WindowStyle Minimized

Write-Host "  后端进程 PID: $($backendJob.Id)" -ForegroundColor Gray

# 等待后端启动
$retries = 0
while ($retries -lt 30) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -ErrorAction Stop
        break
    } catch {
        Start-Sleep -Milliseconds 500
        $retries++
    }
}

if ($retries -ge 30) {
    Write-Host "  警告：后端启动超时，请检查端口 8000 是否被占用" -ForegroundColor Yellow
} else {
    Write-Host "  后端已启动: http://127.0.0.1:8000" -ForegroundColor Green
}

# 启动前端（后台）
$frontendJob = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory $frontendDir `
    -PassThru `
    -WindowStyle Minimized

Write-Host "  前端进程 PID: $($frontendJob.Id)" -ForegroundColor Gray
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  浏览器打开：http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "  按 Ctrl+C 关闭此窗口不会停止服务" -ForegroundColor Gray
Write-Host "  如需停止，请在任务管理器中结束进程" -ForegroundColor Gray
Write-Host "    后端 PID: $($backendJob.Id)" -ForegroundColor Gray
Write-Host "    前端 PID: $($frontendJob.Id)" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 自动打开浏览器
Start-Process "http://localhost:5173"

# 保持窗口打开
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

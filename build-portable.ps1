# Build portable zip: novel-downloader-web-portable-{version}-windows-x64.zip
# Usage: .\build-portable.ps1 [-Version <version>]
param(
    [string]$Version
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

try {
    $distDir = Join-Path $PSScriptRoot "dist"
    $portableDir = Join-Path $distDir "portable"
    $pythonEmbedDir = Join-Path $portableDir "python"

    # Clean and prepare
    if (Test-Path $portableDir) { Remove-Item -Recurse -Force $portableDir }
    New-Item -ItemType Directory -Path $portableDir -Force | Out-Null
    New-Item -ItemType Directory -Path $pythonEmbedDir -Force | Out-Null

    # ── 构建前端 ──
    Write-Host "--- Building frontend ($(Get-Date -Format HH:mm:ss)) ---" -ForegroundColor Cyan
    Push-Location services\frontend
    if (-not (Test-Path node_modules)) {
        Write-Host "npm install (npmmirror)..." -ForegroundColor Yellow
        npm install --registry=https://registry.npmmirror.com
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: npm install 失败" -ForegroundColor Red
            Pop-Location
            exit 1
        }
    }
    Write-Host "npm run build ($(Get-Date -Format HH:mm:ss))..."
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: 前端构建失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "--- Frontend done ($(Get-Date -Format HH:mm:ss)) ---" -ForegroundColor Cyan

    # ── 下载 Embedded Python ──
    Write-Host "--- Downloading Embedded Python ---" -ForegroundColor Cyan
    $pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    Write-Host "Python version: $pyVersion"

    $embedUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip"
    $embedZip = Join-Path $distDir "python-embed.zip"
    Write-Host "Downloading $embedUrl ..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip

    Write-Host "Extracting embed Python..."
    Expand-Archive -Path $embedZip -DestinationPath $pythonEmbedDir -Force
    Remove-Item $embedZip

    # 修改 python3xx._pth：启用 site + 添加 Lib\site-packages
    $pthFile = Get-ChildItem -Path $pythonEmbedDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pthFile) {
        Write-Host "ERROR: 找不到 ._pth 文件" -ForegroundColor Red
        exit 1
    }
    $pthContent = Get-Content $pthFile.FullName
    $pthContent = $pthContent -replace "^#import site", "import site"
    $newContent = @()
    foreach ($line in $pthContent) {
        if ($line -eq "import site") {
            $newContent += "Lib\site-packages"
        }
        $newContent += $line
    }
    $newContent | Set-Content $pthFile.FullName -Encoding ASCII
    Write-Host "Modified $($pthFile.Name): site enabled, Lib\site-packages added"

    # ── 安装 pip ──
    Write-Host "--- Installing pip ---" -ForegroundColor Cyan
    $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
    $getPipPath = Join-Path $distDir "get-pip.py"
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath

    $pythonExe = Join-Path $pythonEmbedDir "python.exe"
    & $pythonExe $getPipPath --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: get-pip.py 失败" -ForegroundColor Red
        exit 1
    }
    Remove-Item $getPipPath

    # ── 安装项目依赖 ──
    Write-Host "--- Installing dependencies ---" -ForegroundColor Cyan
    $pipExe = Join-Path $pythonEmbedDir "Scripts\pip.exe"
    & $pipExe install -r requirements.txt --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install 失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "Dependencies installed"

    # ── 复制项目文件 ──
    Write-Host "--- Copying project files ---" -ForegroundColor Cyan
    Copy-Item -Recurse "novelbase" (Join-Path $portableDir "novelbase")
    $backendDst = Join-Path $portableDir "services\backend"
    New-Item -ItemType Directory -Path (Join-Path $portableDir "services") -Force | Out-Null
    Copy-Item -Recurse "services\backend" $backendDst
    Get-ChildItem -Recurse -Directory -Filter "__pycache__" -Path $portableDir | Remove-Item -Recurse -Force
    $frontendDistDst = Join-Path $portableDir "services\frontend\dist"
    New-Item -ItemType Directory -Path (Join-Path $portableDir "services\frontend") -Force | Out-Null
    Copy-Item -Recurse "services\frontend\dist" $frontendDistDst
    Copy-Item -Recurse "app_data\config" (Join-Path $portableDir "app_data\config")

    # ── 下载 Chrome 在线安装包 ──
    Write-Host "--- Downloading ChromeSetup.exe ---" -ForegroundColor Cyan
    $chromeUrl = "https://dl.google.com/tag/s/installdataindex/update2/installers/ChromeSetup.exe"
    $chromePath = Join-Path $portableDir "ChromeSetup.exe"
    try {
        Invoke-WebRequest -Uri $chromeUrl -OutFile $chromePath
        Write-Host "ChromeSetup.exe downloaded ($((Get-Item $chromePath).Length) bytes)"
    } catch {
        Write-Host "WARNING: ChromeSetup.exe 下载失败，browser 模式需用户自行安装 Chrome" -ForegroundColor Yellow
    }

    # ── 生成启动脚本 ──
    Write-Host "--- Generating launch script ---" -ForegroundColor Cyan
    $batContent = @'
@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHONHOME=%~dp0python"
set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"

:: 检查 Chrome 浏览器
set "CHROME_FOUND="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"

if not defined CHROME_FOUND (
    echo [提示] 未检测到 Chrome 浏览器。
    echo 如需使用 browser 模式，请双击 ChromeSetup.exe 安装 Chrome。
    echo 仅 requests / api 模式不受影响，可继续使用。
    echo.
)

echo 正在启动 novel-downloader-web...
start "" /B python\python.exe -m uvicorn services.backend.main:app --host 127.0.0.1 --port 8000

echo 等待服务就绪...
:wait
python\python.exe -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000')" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)

start "" http://localhost:8000
echo 服务已启动，浏览器已打开 http://localhost:8000
echo 关闭此窗口可停止服务。

pause
'@
    $batContent | Set-Content -Path (Join-Path $portableDir "启动.bat") -Encoding UTF8

    $readmeContent = @'
=== novel-downloader-web 便携版 ===

使用方法：
  1. 如需使用 browser 模式（DrissionPage），先双击 ChromeSetup.exe 安装 Chrome
  2. 双击 启动.bat
  3. 浏览器会自动打开 http://localhost:8000

首次使用 Chrome 模式：
  DrissionPage 首次调用时可能自动下载匹配的 chromedriver，需等待几秒。

数据存储位置：
  下载的小说数据保存在 app_data/storage/ 目录下。
  配置文件在 app_data/config/config.yaml。

停止服务：
  关闭命令行窗口即可。

问题排查：
  如果启动失败，检查是否缺少 VC++ 运行库（Visual C++ Redistributable）。
  Chrome 模式需要 Chrome 浏览器已安装。
'@
    $readmeContent | Set-Content -Path (Join-Path $portableDir "启动说明.txt") -Encoding UTF8

    # ── 打包 zip ──
    if (-not $Version) {
        $versionLine = Get-Content "novelbase\__init__.py" | Select-String '__version__\s*=\s*"(.+)"'
        $Version = $versionLine.Matches.Groups[1].Value
    }
    Write-Host "--- Packaging zip (v$Version) ---" -ForegroundColor Cyan
    # 产物命名与 Linux portable 统一：novel-downloader-web-portable-{version}-windows-x64.zip（无 v 前缀）
    $zipName = "novel-downloader-web-portable-$Version-windows-x64.zip"
    $zipPath = Join-Path $distDir $zipName
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path (Join-Path $portableDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
    $zipSizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host "Created: $zipName ($zipSizeMB MB)" -ForegroundColor Green
}
finally {
    Pop-Location
}

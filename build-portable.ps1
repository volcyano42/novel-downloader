# Build portable zip: novel-downloader-web-portable-v{version}.zip
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

    Write-Host "Done: $zipName" -ForegroundColor Green
}
finally {
    Pop-Location
}

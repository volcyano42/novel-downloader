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

    Write-Host "Done: $zipName" -ForegroundColor Green
}
finally {
    Pop-Location
}

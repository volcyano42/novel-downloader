# Build Nuitka onefile exe: novel-downloader-web-{version}-windows-x64.exe
# Usage: .\build-nuitka.ps1 [-Version <version>] [-MaxRetries <n>]
# Requires: Python 3.13, npm, MSVC (VS 2022 Build Tools)
param(
    [string]$Version,
    [int]$MaxRetries = 20
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

try {
    $distDir = Join-Path $PSScriptRoot "dist"

    # ── 版本号 ──
    if (-not $Version) {
        $content = Get-Content pyproject.toml -Raw
        $m = [regex]::Match($content, 'version = "([^"]+)"')
        if (-not $m.Success) { throw "无法从 pyproject.toml 获取版本号" }
        $Version = $m.Groups[1].Value
    }
    Write-Host "=== Nuitka build v$Version ($(Get-Date -Format 'HH:mm:ss')) ===" -ForegroundColor Cyan

    # ── 构建前端 ──
    Write-Host "--- Building frontend ($(Get-Date -Format HH:mm:ss)) ---" -ForegroundColor Cyan
    Push-Location services\frontend
    if (-not (Test-Path node_modules)) {
        Write-Host "npm install..." -ForegroundColor Yellow
        npm install --registry=https://registry.npmmirror.com
        if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
    }
    Write-Host "npm run build..."
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
    Pop-Location
    Write-Host "--- Frontend done ($(Get-Date -Format HH:mm:ss)) ---" -ForegroundColor Cyan

    # ── 生成书源 manifest（Nuitka onefile 无法扫描文件系统）──
    Write-Host "--- Generating source manifest ($(Get-Date -Format HH:mm:ss)) ---" -ForegroundColor Cyan
    python -m novelbase.utils.build_manifest
    if ($LASTEXITCODE -ne 0) { throw "manifest 生成失败" }

    # ── 安装 Nuitka 4.1.3 ──
    Write-Host "--- Installing Nuitka 4.1.3 ---" -ForegroundColor Cyan
    pip install nuitka==4.1.3
    if ($LASTEXITCODE -ne 0) { throw "Nuitka 安装失败" }

    # ── Nuitka 编译（自动重试） ──
    $exeName = "novel-downloader-web-$Version.exe"
    $exePath = Join-Path $distDir $exeName
    $nuitkaArgs = @(
        "-m", "nuitka",
        "--mode=onefile",
        "--output-dir=$distDir",
        "--output-filename=$exeName",
        "--include-package=novelbase",
        "--include-package=novelbase.sources",
        "--include-package=services.backend",
        "--include-module=init_config",
        "--include-data-dir=template=template",
        "--include-data-dir=services/frontend/dist=services/frontend/dist",
        "--assume-yes-for-downloads",
        "--msvc=latest",
        "services/backend/main.py"
    )

    $nuitkaCmd = "python " + ($nuitkaArgs -join " ")
    Write-Host $nuitkaCmd

    $startTime = Get-Date
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $attemptStart = Get-Date
        Write-Host "--- Nuitka attempt $attempt / $MaxRetries ($(Get-Date -Format 'HH:mm:ss')) ---" -ForegroundColor Cyan

        # 清理上次失败残留
        if (Test-Path $exePath) { Remove-Item $exePath -Force }

        & python $nuitkaArgs
        $exitCode = $LASTEXITCODE
        $elapsed = [math]::Round(((Get-Date) - $attemptStart).TotalMinutes, 1)

        if ($exitCode -eq 0 -and (Test-Path $exePath)) {
            $totalElapsed = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
            $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
            Write-Host "=== Build done: $exeName ($sizeMB MB) in $totalElapsed min ($(Get-Date -Format 'HH:mm:ss')) ===" -ForegroundColor Green
            break
        }

        # 失败处理
        Write-Host "--- Attempt $attempt failed (exit $exitCode, ${elapsed}min) ---" -ForegroundColor Red

        if ($attempt -lt $MaxRetries) {
            $waitSeconds = 30 * [math]::Pow(2, [math]::Min($attempt - 1, 4))  # 30s, 60s, 120s, 240s, 480s, cap at 480s
            $waitMinutes = [math]::Round($waitSeconds / 60, 1)
            Write-Host "等待 ${waitMinutes}min 后重试... (Ctrl+C 终止)" -ForegroundColor Yellow
            Start-Sleep -Seconds $waitSeconds
        } else {
            $totalElapsed = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
            throw "Nuitka 编译失败：已达最大重试次数 $MaxRetries（总耗时 ${totalElapsed}min）"
        }
    }
}
finally {
    Pop-Location
}

# Build & upload novelbase to PyPI
# Usage: .\build-pypi.ps1 [-Token <pypi-token>] [-SkipBuild] [-Repository <pypi|testpypi>]
#
#   -Token        PyPI API token（默认读取 $env:PYPI_TOKEN；推荐用环境变量，勿硬编码）
#   -SkipBuild    跳过构建，仅上传 dist/ 下已有产物
#   -Repository    上传目标（默认 pypi，测试用 testpypi）
#
# 前置依赖：
#   pip install build twine

param(
    [string]$Token = $env:PYPI_TOKEN,
    [switch]$SkipBuild,
    [string]$Repository = "pypi"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

# ── 并行构建锁（与 Nuitka 脚本共用，防 dist/ 冲突）──
$lockDir = Join-Path $PSScriptRoot ".build.lock"
if ($null -eq (New-Item -ItemType Directory -Path $lockDir -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 另一个构建正在进行（$lockDir 存在），请等待其完成" -ForegroundColor Red
    Pop-Location
    exit 1
}

try {
    # ── Token 检查 ────────────────────────────────────────────
    if (-not $Token) {
        Write-Host "ERROR: 未提供 PyPI token" -ForegroundColor Red
        Write-Host "  方式1: 设置环境变量 PYPI_TOKEN" -ForegroundColor Yellow
        Write-Host "  方式2: 运行参数 -Token <token>" -ForegroundColor Yellow
        exit 1
    }

    # ── 依赖检查 ──────────────────────────────────────────────
    foreach ($mod in @("build", "twine")) {
        $null = python -m pip show $mod 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "安装 $mod ..." -ForegroundColor Yellow
            python -m pip install $mod
        }
    }

    # ── 构建 ──────────────────────────────────────────────────
    if (-not $SkipBuild) {
        Write-Host "--- python -m build --no-isolation ---" -ForegroundColor Cyan
        python -m build --no-isolation
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: 构建失败" -ForegroundColor Red
            exit 1
        }
    }

    # ── 产物检查 ──────────────────────────────────────────────
    $artifacts = Get-ChildItem dist -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".whl", ".gz") }
    if (-not $artifacts) {
        Write-Host "ERROR: dist/ 下没有 .whl / .tar.gz 产物" -ForegroundColor Red
        exit 1
    }
    Write-Host "待上传产物:" -ForegroundColor Cyan
    $artifacts | ForEach-Object { Write-Host "  $($_.Name) ($([math]::Round($_.Length / 1KB, 1)) KB)" }

    # ── 上传 ──────────────────────────────────────────────────
    Write-Host "--- twine upload (repository: $Repository) ---" -ForegroundColor Cyan
    python -m twine upload --repository $Repository `
        --username __token__ `
        --password $Token `
        @($artifacts.FullName)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: 上传失败" -ForegroundColor Red
        exit 1
    }

    Write-Host "Done: 已上传 $($artifacts.Count) 个产物到 $Repository" -ForegroundColor Green
} finally {
    Remove-Item -Path $lockDir -Recurse -Force -ErrorAction SilentlyContinue
}
Pop-Location

# Build Web UI: novel-downloader-web.exe (backend + frontend)
# Usage: .\build-web.ps1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

# ── 并行构建锁（防止多个 Nuitka 脚本同时运行互删 dist/）──
$lockDir = Join-Path $PSScriptRoot ".build.lock"
if ($null -eq (New-Item -ItemType Directory -Path $lockDir -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 另一个构建正在进行（$lockDir 存在），请等待其完成" -ForegroundColor Red
    Pop-Location
    exit 1
}

try {

Write-Host "--- Building frontend ---" -ForegroundColor Cyan
Push-Location services\frontend
if (-not (Test-Path node_modules)) {
    Write-Host "npm install..." -ForegroundColor Yellow
    npm install
}
Write-Host "npm run build..."
npm run build
Pop-Location

$SOURCE_PKGS = @(
    "--include-package=novelbase",
    "--include-package=novelbase.sources.fanqie",
    "--include-package=novelbase.sources.fanqie.browser",
    "--include-package=novelbase.sources.fanqie.requests",
    "--include-package=novelbase.sources.fanqie.api.oiapi",
    "--include-package=novelbase.sources.fanqie.api.rain",
    "--include-package=novelbase.sources.qidian",
    "--include-package=novelbase.sources.qidian.browser",
    "--include-package=novelbase.sources.qidian.requests",
    "--include-package=novelbase.sources.qimao",
    "--include-package=novelbase.sources.qimao.browser",
    "--include-package=novelbase.sources.qimao.requests",
    "--include-package=novelbase.sources.qimao.api.rain",
    "--include-package=novelbase.sources.92xs",
    "--include-package=novelbase.sources.92xs.requests"
)

Write-Host "--- Nuitka: web backend (5-10 min) ---" -ForegroundColor Cyan
Get-ChildItem dist\*.build, dist\*.dist -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
python -m nuitka --standalone --onefile --static-libpython=yes --jobs=$env:NUMBER_OF_PROCESSORS `
    @SOURCE_PKGS `
    --include-package=app `
    --include-package=services `
    --include-data-dir=app_data/config=app_data/config `
    --include-data-dir=template/config=template/config `
    --include-data-dir=services/frontend/dist=services/frontend/dist `
    --output-dir=dist `
    --output-filename=novel-downloader-web `
    services/backend/main.py

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Write-Host "Done: dist/novel-downloader-web.exe" -ForegroundColor Green

} finally {
    Remove-Item -Path $lockDir -Recurse -Force -ErrorAction SilentlyContinue
}
Pop-Location

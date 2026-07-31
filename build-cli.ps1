# Build non-interactive CLI: novel-downloader-cli
# Usage: .\build-cmd.ps1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

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

Write-Host "--- Nuitka: non-interactive CLI (3-5 min) ---" -ForegroundColor Cyan
Get-ChildItem dist\*.build, dist\*.dist -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
python -m nuitka --standalone --onefile --jobs=$env:NUMBER_OF_PROCESSORS `
    @SOURCE_PKGS `
    --include-package=app `
    --include-data-dir=app_data/config=app_data/config `
    --output-dir=dist `
    --output-filename=novel-downloader-cmd `
    cli.py

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Write-Host "Done: dist/novel-downloader-cmd.exe" -ForegroundColor Green
Pop-Location

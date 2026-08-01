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

    Write-Host "Done: $zipName" -ForegroundColor Green
}
finally {
    Pop-Location
}

# Build novel-downloader-android APK
# Usage: .\build-android.ps1 [-ProjectPath <path>] [-Sign] [-KeyStore <path>] [-KeyAlias <name>]
#
#   -ProjectPath    Android 项目根目录（默认：.\android）
#   -Sign           签名 release APK（需配置 KeyStore/KeyAlias）
#   -KeyStore       签名密钥库路径（默认：$ProjectPath\release.keystore）
#   -KeyAlias       密钥别名
#
# 环境要求：Java 17+, Android SDK (ANDROID_HOME 或 ANDROID_SDK_ROOT)

param(
    [string]$ProjectPath = "",
    [switch]$Sign,
    [string]$KeyStore = "",
    [string]$KeyAlias = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

# ── 项目路径 ────────────────────────────────────────────
if (-not $ProjectPath) {
    # 尝试同级目录
    $candidate = Join-Path $PSScriptRoot "android"
    if (Test-Path $candidate) {
        $ProjectPath = (Resolve-Path $candidate).Path
    } else {
        Write-Host "ERROR: 未找到 Android 项目。请用 -ProjectPath 指定路径" -ForegroundColor Red
        Write-Host "  期望: .\android" -ForegroundColor Yellow
        Pop-Location
        exit 1
    }
}

if (-not (Test-Path (Join-Path $ProjectPath "gradlew"))) {
    Write-Host "ERROR: $ProjectPath 不是 Android 项目根目录（缺少 gradlew）" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "Project: $ProjectPath" -ForegroundColor Cyan

# ── 环境检查 ────────────────────────────────────────────
function Test-Command($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

Write-Host "--- 环境检查 ---" -ForegroundColor Cyan

# Java
if (-not (Test-Command "java")) {
    Write-Host "ERROR: 未找到 java。请安装 JDK 17+" -ForegroundColor Red
    Pop-Location
    exit 1
}
$javaVer = (java -version 2>&1 | Select-Object -First 1)
Write-Host "  Java : $javaVer" -ForegroundColor Green

# Android SDK
$sdkRoot = $env:ANDROID_HOME
if (-not $sdkRoot) { $sdkRoot = $env:ANDROID_SDK_ROOT }
if (-not $sdkRoot) {
    # 尝试常见路径
    $candidates = @(
        "$env:LOCALAPPDATA\Android\Sdk",
        "$env:APPDATA\Android\Sdk",
        "C:\Android\Sdk"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $sdkRoot = $c; break }
    }
}
if (-not $sdkRoot) {
    Write-Host "ERROR: 未找到 Android SDK。请设置 ANDROID_HOME 环境变量" -ForegroundColor Red
    Pop-Location
    exit 1
}
$env:ANDROID_HOME = $sdkRoot
Write-Host "  SDK  : $sdkRoot" -ForegroundColor Green

# 检查 local.properties
$localProps = Join-Path $ProjectPath "local.properties"
$needProps = $true
if (Test-Path $localProps) {
    $content = Get-Content $localProps -Raw
    if ($content -match "sdk\.dir=") { $needProps = $false }
}
if ($needProps) {
    Write-Host "  写入 local.properties（sdk.dir）..." -ForegroundColor Yellow
    $sdkDir = $sdkRoot -replace '\\', '\\'
    "sdk.dir=$sdkDir" | Out-File -FilePath $localProps -Encoding utf8
}

# ── 签名配置 ────────────────────────────────────────────
$signingArgs = ""
if ($Sign) {
    if (-not $KeyStore) {
        $KeyStore = Join-Path $ProjectPath "release.keystore"
    }
    if (-not (Test-Path $KeyStore)) {
        Write-Host "--- 生成签名密钥库 ---" -ForegroundColor Cyan
        if (-not $KeyAlias) { $KeyAlias = "novel-downloader" }
        $ksPassword = Read-Host "密钥库密码（至少 6 位）" -AsSecureString
        $ksPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ksPassword)
        )
        & keytool -genkey -v `
            -keystore $KeyStore `
            -alias $KeyAlias `
            -keyalg RSA -keysize 2048 -validity 10000 `
            -storepass $ksPlain `
            -keypass $ksPlain `
            -dname "CN=novel-downloader, OU=Dev, O=novel-downloader, L=Unknown, S=Unknown, C=CN"
        Write-Host "  密钥库已生成: $KeyStore" -ForegroundColor Green
    }
    if (-not $KeyAlias) {
        Write-Host "ERROR: -Sign 需要 -KeyAlias" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    $ksPassword = Read-Host "密钥库密码" -AsSecureString
    $ksPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ksPassword)
    )
    $signingArgs = "-Pandroid.injected.signing.store.file=`"$KeyStore`" -Pandroid.injected.signing.store.password=`"$ksPlain`" -Pandroid.injected.signing.key.alias=`"$KeyAlias`" -Pandroid.injected.signing.key.password=`"$ksPlain`""
}

# ── 构建 ────────────────────────────────────────────────
Write-Host "--- Gradle assembleRelease (3-5 min) ---" -ForegroundColor Cyan
Push-Location $ProjectPath

# Windows: gradlew.bat
$gradleCmd = if ($IsWindows -or (-not (Test-Path variable:IsWindows))) { ".\gradlew.bat" } else { "./gradlew" }

$args = @("assembleRelease")
if ($signingArgs) {
    $fullCmd = "$gradleCmd assembleRelease $signingArgs"
    Invoke-Expression $fullCmd
} else {
    & $gradleCmd assembleRelease
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: 构建失败" -ForegroundColor Red
    Pop-Location
    Pop-Location
    exit 1
}

# ── 输出 ────────────────────────────────────────────────
$apkPath = Get-ChildItem -Path "app\build\outputs\apk\release" -Filter "*.apk" -Recurse |
    Where-Object { -not $_.Name.Contains("unsigned") } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($apkPath) {
    # 复制到 dist/
    $distDir = Join-Path $ProjectPath "dist"
    New-Item -ItemType Directory -Force -Path $distDir | Out-Null

    $versionName = "1.0.0"
    $buildGradle = Join-Path $ProjectPath "app" "build.gradle.kts"
    if (Test-Path $buildGradle) {
        $match = Select-String -Path $buildGradle -Pattern 'versionName\s*=\s*"([^"]+)"'
        if ($match) { $versionName = $match.Matches.Groups[1].Value }
    }

    $outName = "novel-downloader-v${versionName}.apk"
    Copy-Item $apkPath.FullName (Join-Path $distDir $outName) -Force

    $sizeMB = [math]::Round($apkPath.Length / 1MB, 1)
    Write-Host "Done: dist/$outName ($sizeMB MB)" -ForegroundColor Green
} else {
    Write-Host "WARN: 未找到 release APK，检查 debug 输出..." -ForegroundColor Yellow
    $apkPath = Get-ChildItem -Path "app\build\outputs\apk\debug" -Filter "*.apk" | Select-Object -First 1
    if ($apkPath) {
        Write-Host "  Debug APK: $($apkPath.FullName)" -ForegroundColor Green
    }
}

Pop-Location
Pop-Location

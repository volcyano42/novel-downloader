# 便携版 zip 包构建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `build-portable.ps1`，构建包含 Embedded Python 的便携 zip 包，用户解压双击即可运行 Web 版。

**Architecture:** 构建脚本下载 Python embed 包 → 安装项目依赖到 embed 环境 → 复制源码 + 前端构建产物 + Chrome 安装包 → 生成启动脚本 → 打包 zip。不动任何现有代码或构建脚本。

**Tech Stack:** PowerShell 5.1+, Python 3.10+ (embed), Node/npm (仅构建前端)

## Global Constraints

- 只构建 Web 版（`services/backend/main.py`），前端 `services/frontend/dist/`
- 三种引擎模式全保留（browser/requests/api）
- 新建文件，不动现有 Nuitka 脚本（`build-web.ps1` 等）
- 依赖预装到 embed 环境，用户端零 pip install
- Python embed 包从 python.org 官方下载
- Chrome 在线安装包从 `https://dl.google.com/tag/s/installdataindex/update2/installers/ChromeSetup.exe` 下载
- 版本号从 `novelbase/__init__.py` 的 `__version__` 读取
- zip 产物命名 `novel-downloader-web-portable-v{version}.zip`

---

### Task 1: 创建 `build-portable.ps1` 骨架

**Files:**
- Create: `build-portable.ps1`

**Interfaces:**
- Produces: 完整的构建脚本，用户执行 `.\build-portable.ps1` 即可输出 zip

- [ ] **步骤 1：写入脚本骨架（参数解析 + UTF-8 编码 + 错误处理）**

```powershell
# Build portable zip: novel-downloader-web-portable-v{version}.zip
# Usage: .\build-portable.ps1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Push-Location $PSScriptRoot

$distDir = Join-Path $PSScriptRoot "dist"
$portableDir = Join-Path $distDir "portable"
$pythonEmbedDir = Join-Path $portableDir "python"

# Clean and prepare
if (Test-Path $portableDir) { Remove-Item -Recurse -Force $portableDir }
New-Item -ItemType Directory -Path $portableDir -Force | Out-Null
New-Item -ItemType Directory -Path $pythonEmbedDir -Force | Out-Null
```

- [ ] **步骤 2：添加 finally 块清理逻辑**

```powershell
# (在脚本末尾)
Write-Host "Done: $zipName" -ForegroundColor Green
Pop-Location
```

- [ ] **步骤 3：测试脚本能无错执行到结束**

Run: `powershell -File build-portable.ps1`
Expected: 创建 `dist/portable/` 和 `dist/portable/python/` 目录，无报错退出

- [ ] **步骤 4：提交**

```bash
git add build-portable.ps1
git commit -m "新增 build-portable.ps1 骨架"
```

---

### Task 2: 前端构建步骤

**Files:**
- Modify: `build-portable.ps1`（添加前端构建逻辑）

**Interfaces:**
- Consumes: Task 1 的骨架
- Produces: `services/frontend/dist/` 已构建

- [ ] **步骤 1：添加前端构建代码（在 Clean 之后、Python 下载之前）**

```powershell
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
```

- [ ] **步骤 2：测试前端构建步骤**

Run: `powershell -File build-portable.ps1`（会构建前端但不继续）
Expected: 前端构建成功，`services/frontend/dist/` 目录存在

- [ ] **步骤 3：提交**

```bash
git add build-portable.ps1
git commit -m "build-portable.ps1 添加前端构建步骤"
```

---

### Task 3: 下载并配置 Embedded Python

**Files:**
- Modify: `build-portable.ps1`（添加 embed Python 下载和解压）

**Interfaces:**
- Consumes: Task 2 的前端构建
- Produces: `dist/portable/python/` 下包含可运行的 Python embed 环境

- [ ] **步骤 1：添加读取 Python 版本 + 下载 embed 包的逻辑**

```powershell
# ── 下载 Embedded Python ──
Write-Host "--- Downloading Embedded Python ---" -ForegroundColor Cyan

# 读取当前运行的 Python 版本号
$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
$pyMajorMinor = python -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')"
Write-Host "Python version: $pyVersion"

$embedUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip"
$embedZip = Join-Path $distDir "python-embed.zip"

Write-Host "Downloading $embedUrl ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip

Write-Host "Extracting embed Python..."
Expand-Archive -Path $embedZip -DestinationPath $pythonEmbedDir -Force
Remove-Item $embedZip
```

- [ ] **步骤 2：添加修改 `._pth` 文件的逻辑**

```powershell
# 修改 python3xx._pth：启用 site + 添加 Lib\site-packages
$pthFile = Get-ChildItem -Path $pythonEmbedDir -Filter "python*._pth" | Select-Object -First 1
if (-not $pthFile) {
    Write-Host "ERROR: 找不到 ._pth 文件" -ForegroundColor Red
    exit 1
}
$pthContent = Get-Content $pthFile.FullName
$pthContent = $pthContent -replace "^#import site", "import site"
# 确保 Lib\site-packages 在搜索路径中
if ($pthContent -notcontains "Lib\site-packages") {
    # 在 import site 之前插入
    $newContent = @()
    foreach ($line in $pthContent) {
        if ($line -eq "import site") {
            $newContent += "Lib\site-packages"
        }
        $newContent += $line
    }
    $newContent | Set-Content $pthFile.FullName -Encoding ASCII
}
Write-Host "Modified $($pthFile.Name): site enabled, Lib\site-packages added"
```

- [ ] **步骤 3：测试 embed Python 可运行**

Run: 
```powershell
.\build-portable.ps1  # 先跑到这里
.\dist\portable\python\python.exe -c "print('OK')"
```
Expected: 输出 `OK`

- [ ] **步骤 4：提交**

```bash
git add build-portable.ps1
git commit -m "build-portable.ps1 添加 Embedded Python 下载和配置"
```

---

### Task 4: 安装 pip 和项目依赖到 embed 环境

**Files:**
- Modify: `build-portable.ps1`（添加 get-pip + pip install 逻辑）

**Interfaces:**
- Consumes: Task 3 的 embed Python 环境
- Produces: `dist/portable/python/Lib/site-packages/` 下包含所有项目依赖

- [ ] **步骤 1：添加 get-pip.py 下载和安装逻辑**

```powershell
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
```

- [ ] **步骤 2：添加 pip install 项目依赖的逻辑**

```powershell
# ── 安装项目依赖 ──
Write-Host "--- Installing dependencies ---" -ForegroundColor Cyan
$pipExe = Join-Path $pythonEmbedDir "Scripts\pip.exe"
& $pipExe install -r requirements.txt --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install 失败" -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed"
```

- [ ] **步骤 3：验证依赖安装完整性**

```powershell
# 可选：验证关键模块可导入
& $pythonExe -c "import fastapi, uvicorn, novelbase; print('All OK')"
```

- [ ] **步骤 4：测试**

Run: `.\build-portable.ps1`（跑到依赖安装步骤）
Then: `.\dist\portable\python\python.exe -c "import fastapi, uvicorn, drissionpage, bs4, PIL, yaml, rich; print('All OK')"`
Expected: 输出 `All OK`，无 ImportError

- [ ] **步骤 5：提交**

```bash
git add build-portable.ps1
git commit -m "build-portable.ps1 添加 pip 和项目依赖安装"
```

---

### Task 5: 复制项目文件到 portable 目录

**Files:**
- Modify: `build-portable.ps1`（添加文件复制逻辑）

**Interfaces:**
- Consumes: Task 4 的依赖环境 + Task 2 的前端构建
- Produces: `dist/portable/` 下包含完整可运行的项目

- [ ] **步骤 1：添加复制源码和资源的逻辑**

```powershell
# ── 复制项目文件 ──
Write-Host "--- Copying project files ---" -ForegroundColor Cyan

# 核心库
Copy-Item -Recurse "novelbase" (Join-Path $portableDir "novelbase")

# CLI 应用层（backend 的 import 依赖）
Copy-Item -Recurse "app" (Join-Path $portableDir "app")

# 后端服务（排除 __pycache__）
$backendSrc = "services\backend"
$backendDst = Join-Path $portableDir "services\backend"
New-Item -ItemType Directory -Path (Join-Path $portableDir "services") -Force | Out-Null
Copy-Item -Recurse $backendSrc $backendDst
Get-ChildItem -Recurse -Directory -Filter "__pycache__" -Path $portableDir | Remove-Item -Recurse -Force

# 前端构建产物
$frontendDistDst = Join-Path $portableDir "services\frontend\dist"
New-Item -ItemType Directory -Path (Join-Path $portableDir "services\frontend") -Force | Out-Null
Copy-Item -Recurse "services\frontend\dist" $frontendDistDst

# 默认配置文件
Copy-Item -Recurse "app_data\config" (Join-Path $portableDir "app_data\config")
# 确保 config.yaml 存在（不存在则按模板生成逻辑在运行时处理）
```

- [ ] **步骤 2：验证复制完整性**

Run: 
```powershell
.\build-portable.ps1
@(Get-ChildItem -Recurse -File dist\portable\).Count
```
Expected: 文件数量合理（源码 + 前端 dist + 依赖 + embed Python）

- [ ] **步骤 3：提交**

```bash
git add build-portable.ps1
git commit -m "build-portable.ps1 添加项目文件复制逻辑"
```

---

### Task 6: 下载 Chrome 在线安装包 + 生成启动脚本

**Files:**
- Modify: `build-portable.ps1`（添加 Chrome 下载 + 启动文件生成）

**Interfaces:**
- Consumes: Task 5 的完整 portable 目录
- Produces: `ChromeSetup.exe`、`启动.bat`、`启动说明.txt` 写入 portable 目录

- [ ] **步骤 1：添加 Chrome 在线安装包下载**

```powershell
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
```

- [ ] **步骤 2：生成 `启动.bat`**

```powershell
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
```

- [ ] **步骤 3：生成 `启动说明.txt`**

```powershell
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
```

- [ ] **步骤 4：验证生成文件**

Run: `.\build-portable.ps1`
Expected: `dist/portable/ChromeSetup.exe`、`启动.bat`、`启动说明.txt` 存在

- [ ] **步骤 5：提交**

```bash
git add build-portable.ps1
git commit -m "build-portable.ps1 添加 Chrome 安装包下载和启动脚本生成"
```

---

### Task 7: 打包 zip

**Files:**
- Modify: `build-portable.ps1`（添加 zip 打包 + 版本号读取）

**Interfaces:**
- Consumes: Task 6 的完整 portable 目录
- Produces: `dist/novel-downloader-web-portable-v{version}.zip`

- [ ] **步骤 1：添加版本号读取 + zip 打包逻辑**

```powershell
# ── 读取版本号 ──
$versionLine = Get-Content "novelbase\__init__.py" | Select-String '__version__\s*=\s*"(.+)"'
$version = $versionLine.Matches.Groups[1].Value
Write-Host "Version: $version"

# ── 打包 zip ──
Write-Host "--- Packaging zip ---" -ForegroundColor Cyan
$zipName = "novel-downloader-web-portable-v$version.zip"
$zipPath = Join-Path $distDir $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Compress-Archive -Path (Join-Path $portableDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
$zipSizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "Created: $zipName ($zipSizeMB MB)" -ForegroundColor Green
```

- [ ] **步骤 2：完整构建测试**

Run: `.\build-portable.ps1`
Expected: 生成 `dist/novel-downloader-web-portable-v4.2.3-dev.zip`，大小 ~80MB

- [ ] **步骤 3：功能测试（解压 + 启动 + 首页访问）**

```powershell
# 解压到临时目录
Expand-Archive -Path "dist/novel-downloader-web-portable-v4.2.3-dev.zip" -DestinationPath "$env:TEMP\portable-test" -Force

# 手动测试：双击 启动.bat，浏览器打开 http://localhost:8000
# 检查：首页能加载、sources API 正常返回
```

- [ ] **步骤 4：提交**

```bash
git add build-portable.ps1
git commit -m "build-portable.ps1 添加版本号读取和 zip 打包"
```

---

### Task 8: 添加 `.gitignore` 条目

**Files:**
- Modify: `.gitignore`（添加 portable 产物忽略）

- [ ] **步骤 1：添加忽略规则**

```gitignore
# 便携版构建产物
dist/portable/
dist/*-portable-*.zip
```

- [ ] **步骤 2：提交**

```bash
git add .gitignore
git commit -m "gitignore 添加 portable 构建产物"
```

---

## Self-Review

1. **Spec coverage**: 所有设计文档中的需求均有对应任务——前端构建(T2)、Embed Python(T3)、依赖安装(T4)、源码复制(T5)、Chrome安装包(T6)、启动脚本(T6)、zip打包(T7)
2. **Placeholder scan**: 无 TBD/TODO，所有代码块均包含实际内容
3. **Type consistency**: `$portableDir`、`$pythonEmbedDir`、`$pythonExe` 在各任务中定义和引用一致

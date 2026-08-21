# 便携版 zip 包构建方案设计

## 概述

放弃 Nuitka 编译为 exe 的方案，改为发布便携 zip 包：用户解压后双击启动脚本即可运行 Web 版小说下载器，无需安装 Python。

## 动机

1. **CI 构建严重不稳定**：Nuitka 在 GitHub Actions windows-latest runner 上连续多次超时（100+ 分钟不完成），而本机构建正常（~7 分钟）
2. **降低使用门槛**：zip 便携包用户体验接近 exe，解压即用
3. **构建快速可靠**：跳过 C 编译，构建时间从 30-100+ 分钟降到 ~5 分钟

## 设计决策

| 决策 | 结论 | 理由 |
|------|------|------|
| 产品线 | 仅 Web 版 | 最实用的使用方式（浏览器操作） |
| Python 运行时 | Embedded Python (python-embed) | 官方便携方案，~25MB，无需安装 |
| Chromium | 不打包浏览器本体，内置 Chrome 在线安装包 | 避免 zip 膨胀到 230MB+ |
| 引擎模式 | 三种全保留 (browser/requests/api) | browser 模式首次使用需先运行 Chrome 安装包 |
| 构建脚本 | **新建** `build-portable.ps1`，不动现有 Nuitka 脚本 | 独立方案，互不干扰 |

## 用户使用流程

```
1. 解压 novel-downloader-web-portable-{version}.zip
2. 如需 browser 模式：双击 ChromeSetup.exe 安装 Chrome（仅首次）
3. 双击 启动.bat
4. 浏览器自动打开 Web 界面
```

## 架构设计

### zip 包目录结构

```
novel-downloader-web-portable-v4.2.x/
├── python/                    ← Embedded Python 运行时
│   ├── python.exe
│   ├── python312.dll          ← 或对应版本的 dll
│   ├── python312.zip          ← 标准库
│   ├── Lib/site-packages/     ← pip 安装的第三方依赖
│   └── ...
├── app/                       ← CLI 应用层（import 依赖需要）
├── novelbase/                 ← 核心库源码
├── services/
│   ├── backend/               ← FastAPI 后端源码
│   └── frontend/dist/         ← 前端构建产物（Vite build）
├── app_data/
│   └── config/                ← 默认配置文件
├── ChromeSetup.exe            ← Chrome 在线安装包（1MB）
├── 启动.bat                   ← 启动脚本
└── 启动说明.txt               ← 简要说明
```

### 启动脚本 `启动.bat`

```batch
@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 设置嵌入式 Python 路径
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

:: 启动后端服务（后台运行）
echo 正在启动 novel-downloader-web...
start "" /B python\python.exe -m uvicorn services.backend.main:app --host 127.0.0.1 --port 8000

:: 等待服务就绪后打开浏览器
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
```

### 构建脚本 `build-portable.ps1` 流程

```
1. 检查前置条件 (Python 3.10+, Node, npm)
2. 构建前端
   - npm ci / npm run build
3. 准备输出目录 dist/portable/
4. 下载并解压 Embedded Python
   - 从 https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip 获取
   - 修改 python312._pth（取消 import site 注释，添加 Lib/site-packages）
5. 安装 pip + 依赖到 embed 环境
   - 下载 get-pip.py → python get-pip.py
   - python -m pip install -r requirements-freeze.txt --target python/Lib/site-packages
6. 下载 ChromeSetup.exe
   - URL: https://dl.google.com/tag/s/installdataindex/update2/installers/ChromeSetup.exe
   - 保存到 dist/portable/ChromeSetup.exe
7. 复制项目文件
   - novelbase/, app/, services/backend/
   - services/frontend/dist/
   - app_data/config/（默认配置模板）
8. 生成辅助文件
   - 启动.bat
   - 启动说明.txt
9. 打包 zip
   - Compress-Archive → dist/novel-downloader-web-portable-v{version}.zip
```

### 依赖版本处理

构建时用开发环境的 pip 将所有依赖安装到 embed 的 `Lib/site-packages/`。依赖在 zip 中预装好，用户端无需再执行 pip install。

构建脚本中可用 `pip install -r requirements.txt`（或精确版本），注意排除只在开发环境需要的包（如 `pytest`、`black` 等）。

### Embedded Python 的 `._pth` 修改

默认 embed 包的 `python312._pth` 禁用了 `site` 模块（pip 需要）。构建时必须：

1. 取消 `#import site` 的注释
2. 添加一行 `Lib\site-packages`（相对路径）

```ini
python312.zip
.
Lib\site-packages
import site
```

### 版本号获取

从 `novelbase/__init__.py` 读取 `__version__`，与 Nuitka 构建脚本一致。

### CI 集成（后续）

可在 GitHub Actions 上新增 `build-portable.yml` workflow：
- 矩阵：Windows x64（初始仅 Windows）
- 构建步骤参照 `build-portable.ps1`
- 产物：便携 zip 包上传为 artifact
- 不替代现有 Nuitka CI，作为独立 workflow

## 不在范围内

- 不删除现有 Nuitka 构建脚本（`build-web.ps1`、`build-main.ps1` 等）
- 不修改 `build-windows.yml` CI workflow
- 不处理 Linux/macOS 便携包（后续扩展）
- 不改变任何业务代码

## 预估

| 项目 | 数值 |
|------|------|
| Embedded Python | ~25 MB |
| 第三方依赖 (site-packages) | ~45 MB |
| 项目源码 + 前端 dist | ~8 MB |
| ChromeSetup.exe | ~1 MB |
| **zip 包总计** | **~80 MB** |
| 构建时间（本机） | ~5 分钟 |
| CI 构建时间 | ~5 分钟 |

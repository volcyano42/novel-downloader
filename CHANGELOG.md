# 更新日志

## v4.3.0

### 新增

1. **BrowserOptions 新增 `extra_args`** — 支持传入额外 Chromium 命令行参数（如 `--remote-debugging-port`、`--no-sandbox` 等），通过 CLI `--extra-args`、前端设置、配置文件均可配置
2. **Linux 环境自动适配 Chromium 启动参数** — `BrowserEngine._init_browser()` 在 Linux 下自动追加 `--no-sandbox`、`--disable-gpu`、`--disable-setuid-sandbox`、`--disable-dev-shm-usage`，解决 Termux / SSH / Docker 等无桌面环境的 sandbox 报错

### 说明

- FastAPI `version="2.0.0"`（`services/backend/main.py:35`）为独立 API 版本，与项目版本 4.3.0 分属不同命名空间，非矛盾

## v4.2.3

### 新增

1. **跨平台 portable 便携版** — 新增 `build-portable.sh`，替代 Nuitka onefile 编译（耗时/易错），改为「Python 解释器 + 源码 + 预装依赖」打包：
   - **Linux x64/arm64**：python-build-standalone 独立解释器（pip 用 manylinux wheel 免编译），解压即用
   - **Termux**：依赖在 termux-docker 容器按 bionic 环境预编译打包（`python-deps/`），仅需 `pkg install python` 一条命令，无 pip/编译
   - 支持 `--deps-dir`（预装 site-packages）与 `--pyroot-dir`（内置 Python，PYTHONHOME 重定位，已实测通过）参数
2. **便携版 CI 内启动验证** — termux workflow 在容器内实测 `uvicorn` 启动 + HTTP 200（前端与 API 均验证）
3. **Novel.origin_id 派生属性** — 只读属性，值为去掉 `{website}_` 前缀的源站原始 ID（如 `fanqie_7123...` → `7123...`）
4. **所有源新增 `ORIGIN_ID_PATTERN`** — 匹配去前缀的源站原始 ID（`Novel.origin_id`），与 `ID_PATTERN`（匹配带前缀的 Novel.id）并存；registry 扫描/硬编码兜底与 `cli.py source list --json` 同步暴露
### 变更

1. **Android 与 musl 产物移除** — 删除 `android/` 目录、`build-apk.yml`、`build-linux-arm64-musl.yml`（musl 动态产物 Termux 无法运行）；产物矩阵为 Windows x64 / Linux x64 / Linux arm64
2. **Linux 构建改用 portable 方案** — `build-linux-x64.yml` / `build-linux-arm64.yml` / `build-linux-arm64-termux.yml` 由 Nuitka 编译改为 `build-portable.sh`（构建 10-20 分钟，免 C 编译）
3. **打包版判断修正** — 用 Nuitka `__compiled__` 特性替代 `sys.frozen`（Nuitka 不设置 sys.frozen，导致 exe 误走 reload 分支报 WinError 10013）
4. **Windows 产物统一 portable 命名** — build-windows 产物改为 `novel-downloader-web-portable-{version}-windows-x64`（与 Linux 系列命名一致）
5. **workflow 显示名称统一** — `Build Windows x64` → `Build Windows x64 portable`（与 Linux portable 系列命名一致）
6. **Windows 构建改用 portable 方案** — build-windows.yml 由 Nuitka 编译（build-web.ps1）改为 `build-portable.ps1`（Embedded Python + 源码 + 依赖 zip），产物统一为 `novel-downloader-web-portable-{version}-windows-x64.zip`
7. **Termux 加回 build-dist（内置 Python）** — Termux portable 采用 pyroot 全内置方案（Python 本体 + 依赖库随包，PYTHONHOME 重定位，开箱即用无需 `pkg install python`）；build-dist 覆盖 Windows x64 / Linux x64 / Linux arm64 / Termux 四平台
8. **移除交互式 CLI** — 删除 `main.py` 及 app 交互层（`app/menus.py` / `app/ui.py` / `app/notify.py`），`cli.py` 重构为纯非交互唯一 CLI 入口：新增 `delete`（删除小说）、`novel list`（书架）、`source list`（书源，`source`/`sources` 均可）；`export` 改为直接导出不再走交互菜单；scripts 调试脚本改从 `app.config` 加载配置
9. **app/ 目录更名 cli_lib** — CLI 辅助层（配置加载/下载编排）改名，避免与嵌套核心目录命名冲突；cli.py 与调试脚本引用同步更新
10. **scripts/ 移至衍生产物目录** — 调试脚本（debug_source / debug_exporter / debug_parser / cloud_sync / recover_db / archive 等）不进核心仓库；构建辅助 check-termux-psutil.sh（原 probe-termux.sh，孤儿脚本）定位于衍生产物目录
11. **删除废弃 Nuitka 构建脚本** — build-main、build-cli（CLI 版 Nuitka 构建遗留，已只发布 portable 便携版）
12. **portable 构建仅打包 webui** — 移除 cli_lib 打包（webui 运行不依赖 CLI 层）
13. **删除杂项文件** — package.json / package-lock.json（本地 reasonix npm 临时文件误入仓库）
### 修复

1. **build-windows 重命名** — 改为 PowerShell `Copy-Item`（git-bash `mv` 在 CI 上失败）
2. **前端 npm 镜像** — CI 上 `npm install` 改用 npmmirror 镜像 + 时间戳输出（定位 Build 卡点）
3. **Termux 容器兼容** — 容器无 `/tmp`（改用挂载卷）；`ANDROID_API_LEVEL=24`（maturin 构建 pydantic-core 需要）；依赖 `.so` 随 `pyroot` 一并复制（PYTHONHOME 重定位必需）
4. **storage.delete_novel 在 Windows 删除失败** — sqlite 连接对象依赖 GC 销毁、文件句柄延迟释放导致 `os.remove` 撞 `PermissionError`；删除前强制 `gc.collect()` 并加重试
5. **构建脚本同步 cli_lib 改名** — build-portable.ps1/sh 与 build-web.ps1 仍引用已删除的 `app` 目录（打包会失败/漏包），改为 `cli_lib`
---

## v4.2.1

### 新增

1. **单平台构建 workflow** — 新增 `build-windows.yml` / `build-linux-x64.yml` / `build-linux-arm64.yml` / `build-linux-arm64-musl.yml` / `build-apk.yml`，每个可单独手动触发测试（保留 `build-dist.yml` 一键全平台）；新增 **Linux arm64 musl 静态构建**（Termux 可运行）
2. **PyPI 构建上传脚本** — `build-pypi.ps1` / `build-pypi.sh`，token 走环境变量
3. **前端设置页模式动态化** — 平台 / 引擎设置按 mode 过滤；**APK 与 WebUI 不自动跟随系统暗色**（默认亮色，手动可切换）

### 变更

1. **APK 改为通用 ABI** — 去掉 arm64-v8a 限定，任意设备可安装
2. **产物命名追加版本号** — Windows exe / Linux 可执行文件 / APK 均带 `4.2.1` 版本后缀
3. **Linux 构建改用 ubuntu-22.04** — 提升 glibc 兼容性（旧系统可运行）
4. **放弃 Windows/Linux x86 构建** — pillow-heif 无 win32 支持，32 位系统不再出产物
5. Nuitka 静态链接 libpython（Windows 移除不支持的 `--static-libpython`，Linux 保留）

### 修复

1. **Windows Nuitka 依赖分析** — 改用 `--experimental=force-dependencies-pefile`（原 `--windows-dependency-tool` 选项已移除），彻底规避 Dependency Walker 下载失败
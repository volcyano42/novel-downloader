# 更新日志

## v4.2.3

### 新增

1. **Termux 构建支持** — 新增 `build-termux.sh`（termux-docker bionic 环境构建，产物真机 Termux 可直接运行）+ `build-linux-arm64-termux.yml` workflow；Termux 环境排除 browser 模式（drissionpage→psutil 不支持 Android），requests/api 模式完整可用
2. **跨平台 portable 便携版** — 新增 `build-portable.sh`，替代 Nuitka onefile 编译（耗时/易错），改为「Python 解释器 + 源码 + 预装依赖」打包：
   - **Linux x64/arm64**：python-build-standalone 独立解释器（pip 用 manylinux wheel 免编译），解压即用
   - **Termux**：依赖在 termux-docker 容器按 bionic 环境预编译打包（`python-deps/`），仅需 `pkg install python` 一条命令，无 pip/编译
   - 支持 `--deps-dir`（预装 site-packages）与 `--pyroot-dir`（内置 Python，PYTHONHOME 重定位，已实测通过）参数
3. **便携版 CI 内启动验证** — termux workflow 在容器内实测 `uvicorn` 启动 + HTTP 200（前端与 API 均验证）
4. **Novel.origin_id 派生属性** — 只读属性，值为去掉 `{website}_` 前缀的源站原始 ID（如 `fanqie_7123...` → `7123...`）
5. **所有源新增 `ORIGIN_ID_PATTERN`** — 匹配去前缀的源站原始 ID（`Novel.origin_id`），与 `ID_PATTERN`（匹配带前缀的 Novel.id）并存；registry 扫描/硬编码兜底与 `cli.py source list --json` 同步暴露

### 变更

1. **版本号同步** — `pyproject.toml` 与 `novelbase/__init__.py` 统一为 `4.2.3-dev`
2. **Android 与 musl 产物移除** — 删除 `android/` 目录、`build-apk.yml`、`build-linux-arm64-musl.yml`（musl 动态产物 Termux 无法运行）；产物矩阵为 Windows x64 / Linux x64 / Linux arm64
3. **Linux 构建改用 portable 方案** — `build-linux-x64.yml` / `build-linux-arm64.yml` / `build-linux-arm64-termux.yml` 由 Nuitka 编译改为 `build-portable.sh`（构建 10-20 分钟，免 C 编译）
4. **打包版判断修正** — 用 Nuitka `__compiled__` 特性替代 `sys.frozen`（Nuitka 不设置 sys.frozen，导致 exe 误走 reload 分支报 WinError 10013）
5. **Windows 产物统一 portable 命名** — build-windows 产物改为 `novel-downloader-web-portable-{version}-windows-x64`（与 Linux 系列命名一致）
6. **Termux 移出 CI 产物矩阵** — build-dist 不再构建 Termux 产物（Termux 由用户本机构建），`build-linux-arm64-termux.yml` 保留可单独触发
7. **废弃构建文件清理** — 删除 Nuitka 版 `build-web.sh`（含 --musl 参数）、`build-termux.sh` 及 `build-linux-arm64-termux.yml` workflow（portable 方案已替代，Termux 产物由用户本机构建）
8. **workflow 显示名称统一** — `Build Windows x64` → `Build Windows x64 portable`（与 Linux portable 系列命名一致）
9. **Windows 构建改用 portable 方案** — build-windows.yml 由 Nuitka 编译（build-web.ps1）改为 `build-portable.ps1`（Embedded Python + 源码 + 依赖 zip），产物统一为 `novel-downloader-web-portable-{version}-windows-x64.zip`
10. **Termux 加回 build-dist（内置 Python）** — Termux portable 采用 pyroot 全内置方案（Python 本体 + 依赖库随包，PYTHONHOME 重定位，开箱即用无需 `pkg install python`）；build-dist 覆盖 Windows x64 / Linux x64 / Linux arm64 / Termux 四平台
11. **移除交互式 CLI** — 删除 `main.py` 及 app 交互层（`app/menus.py` / `app/ui.py` / `app/notify.py`），`cli.py` 重构为纯非交互唯一 CLI 入口：新增 `delete`（删除小说）、`novel list`（书架）、`source list`（书源，`source`/`sources` 均可）；`export` 改为直接导出不再走交互菜单；scripts 调试脚本改从 `app.config` 加载配置

### 修复

1. **build-windows 重命名** — 改为 PowerShell `Copy-Item`（git-bash `mv` 在 CI 上失败）
2. **前端 npm 镜像** — CI 上 `npm install` 改用 npmmirror 镜像 + 时间戳输出（定位 Build 卡点）
3. **Nuitka 参数排查** — 移除无效 `--cache-dir`（Nuitka 4.x 无此参数，会导致直接报错）；CI 缓存指向 Nuitka 内置目录 `%LOCALAPPDATA%\Nuitka`
4. **portable 打包结构** — 修复 `services/backend` 目录嵌套（`cp -r` 目标预建导致 `backend/backend`）；补打包根目录 `init_config.py`（main.py lifespan 必需，缺失则启动失败）
5. **Termux 容器兼容** — 容器无 `/tmp`（改用挂载卷）；`ANDROID_API_LEVEL=24`（maturin 构建 pydantic-core 需要）；依赖 `.so` 随 `pyroot` 一并复制（PYTHONHOME 重定位必需）
6. **storage.delete_novel 在 Windows 删除失败** — sqlite 连接对象依赖 GC 销毁、文件句柄延迟释放导致 `os.remove` 撞 `PermissionError`；删除前强制 `gc.collect()` 并加重试

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

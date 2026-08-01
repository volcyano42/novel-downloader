# 更新日志

## v4.2.3-dev

### 新增

1. **Termux 构建支持** — 新增 `build-termux.sh`（termux-docker bionic 环境构建，产物真机 Termux 可直接运行）+ `build-linux-arm64-termux.yml` workflow；Termux 环境排除 browser 模式（drissionpage→psutil 不支持 Android），requests/api 模式完整可用
2. **跨平台 portable 便携版** — 新增 `build-portable.sh`，替代 Nuitka onefile 编译（耗时/易错），改为「Python 解释器 + 源码 + 预装依赖」打包：
   - **Linux x64/arm64**：python-build-standalone 独立解释器（pip 用 manylinux wheel 免编译），解压即用
   - **Termux**：依赖在 termux-docker 容器按 bionic 环境预编译打包（`python-deps/`），仅需 `pkg install python` 一条命令，无 pip/编译
   - 支持 `--deps-dir`（预装 site-packages）与 `--pyroot-dir`（内置 Python，PYTHONHOME 重定位，已实测通过）参数
3. **便携版 CI 内启动验证** — termux workflow 在容器内实测 `uvicorn` 启动 + HTTP 200（前端与 API 均验证）

### 变更

1. **版本号同步** — `pyproject.toml` 与 `novelbase/__init__.py` 统一为 `4.2.3-dev`
2. **Android 与 musl 产物移除** — 删除 `android/` 目录、`build-apk.yml`、`build-linux-arm64-musl.yml`（musl 动态产物 Termux 无法运行）；产物矩阵为 Windows x64 / Linux x64 / Linux arm64
3. **Linux 构建改用 portable 方案** — `build-linux-x64.yml` / `build-linux-arm64.yml` / `build-linux-arm64-termux.yml` 由 Nuitka 编译改为 `build-portable.sh`（构建 10-20 分钟，免 C 编译）
4. **打包版判断修正** — 用 Nuitka `__compiled__` 特性替代 `sys.frozen`（Nuitka 不设置 sys.frozen，导致 exe 误走 reload 分支报 WinError 10013）

### 修复

1. **build-windows 重命名** — 改为 PowerShell `Copy-Item`（git-bash `mv` 在 CI 上失败）
2. **前端 npm 镜像** — CI 上 `npm install` 改用 npmmirror 镜像 + 时间戳输出（定位 Build 卡点）
3. **Nuitka 参数排查** — 移除无效 `--cache-dir`（Nuitka 4.x 无此参数，会导致直接报错）；CI 缓存指向 Nuitka 内置目录 `%LOCALAPPDATA%\Nuitka`
4. **portable 打包结构** — 修复 `services/backend` 目录嵌套（`cp -r` 目标预建导致 `backend/backend`）；补打包根目录 `init_config.py`（main.py lifespan 必需，缺失则启动失败）
5. **Termux 容器兼容** — 容器无 `/tmp`（改用挂载卷）；`ANDROID_API_LEVEL=24`（maturin 构建 pydantic-core 需要）；依赖 `.so` 随 `pyroot` 一并复制（PYTHONHOME 重定位必需）

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

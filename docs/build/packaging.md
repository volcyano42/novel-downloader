# 打包方案

## pip 安装（开发）

```powershell
pip install -e .          # 可编辑安装
novel-downloader           # CLI（非交互，等价 python cli.py）
novel-downloader-web       # Web 后端 (FastAPI + 内嵌前端)
```

## portable 便携版（主方案之一）

产物形态统一为「Python 解释器 + 源码 + 预装依赖」压缩包，解压即用（开箱即用，无 pip/编译）。**仅打包 webui**（novelbase + backend + frontend/dist + app_data/config + init_config.py，不含 cli/cli.py/main.py）：

| 平台 | 脚本 | 产物 |
|------|------|------|
| Windows x64 | `build-portable.ps1` | `novel-downloader-web-portable-{version}-windows-x64.zip`（Embedded Python） |
| Linux x64 / arm64 | `build-portable.sh --platform linux-x64/linux-arm64` | `-{version}-linux-x64.tar.gz`（python-build-standalone 独立解释器，manylinux wheel 免编译） |
| Termux (arm64) | `build-portable.sh --platform termux --deps-dir deps --pyroot-dir pyroot` | `-{version}-termux.tar.gz`（**pyroot 内置 Python**，PYTHONHOME 重定位，无需 `pkg install python`） |

- `--deps-dir`：预装 site-packages（termux-docker 容器按 bionic 环境预编译导出）
- `--pyroot-dir`：内置 Python 本体（bin + 标准库 + 依赖 .so，PYTHONHOME 重定位，已实测启动 HTTP 200）
- 启动脚本：`start.sh`（Linux/Termux）/ `启动.bat`（Windows）；首次运行自动从包内复制 `app_data/config/`
- 已删除：`build-pypi.ps1/sh`（PyPI 上传脚本，2026-09-19 清理，原 token 走环境变量）
- **Nuitka 已恢复（与 portable 共存）**：build-web.ps1 已删（2026-08-02）；新增 build-nuitka.ps1（2026-08-10，仅 Windows onefile，手动触发）。**2026-09-19 workflow 分层：Nuitka 从 `build-windows.yml` 拆出为独立 `build-windows-nuitka.yml`（两种产物不再共用一个 workflow）**。见下方 Nuitka 章节。
- **所有 ps1 需 UTF-8 BOM**（Windows PowerShell 5.1 按 ANSI 解析无 BOM 文件会中文乱码 → ParserError）
- **构建脚本在核心仓库内**（对齐官方 workflow+scripts 模式）：workflow 负责编排，脚本保留仓库根供复用/验证

## Nuitka onefile（Windows exe，与 portable 共存）

仅 Windows x64，**独立 workflow `build-windows-nuitka.yml`**，手动触发（不并入 build-dist.yml，避免全平台构建超时；Nuitka 编译需 30-60 分钟）：

| 脚本 | 产物 |
|------|------|
| `build-nuitka.ps1` | `novel-downloader-web-{version}.exe`（Nuitka 4.1.3 onefile 编译） |

- **版本锁死**：`nuitka==4.1.3`，不追新。升级前需重新验证参数（Nuitka 4.x 频繁废弃旧参数）。
- **编译器**：MSVC（`--msvc=latest`，VS 2022，windows-latest runner 自带）。
- **入口**：`backend/main.py`（FastAPI + 内嵌前端），启动逻辑复用 `__compiled__` 判断。
- **数据文件**：`template/`（配置模板）、`frontend/dist/`（前端静态文件）通过 `--include-data-dir` 打包。
- **杀毒扫描**：**已移除**（2026-09-19）。原 CI Defender 扫描（`MpCmdRun.exe -Scan`）在 pwsh 步骤里退出码非零会被 GitHub 判为步骤失败（脚本里只 `Write-Warning` 也不够：GitHub 取最后一条原生命令的 `$LASTEXITCODE`），导致 `Upload exe` 被 skip、产物丢失。
- exe 体积远小于 portable zip（~30-50MB vs ~300MB），但首次编译需 30-60 分钟（含依赖分析 + C 编译）。

## CI 构建（GitHub Actions，全部手动触发）

产物矩阵：

| workflow 文件 | 平台 | 产物 |
|--------------|------|------|
| build-windows.yml | Windows x64 | `...-windows-x64.zip`（build-portable.ps1） |
| build-windows-nuitka.yml | Windows x64 | `novel-downloader-web-{version}.exe`（build-nuitka.ps1，独立 workflow，仅 workflow_dispatch） |
| build-linux-x64.yml | Linux x64 | `...-linux-x64.tar.gz` |
| build-linux-arm64.yml | Linux arm64 | `...-linux-arm64.tar.gz` |
| build-linux-arm64-termux.yml | Linux arm64 Termux | `...-termux.tar.gz`（pyroot 内置 Python，含 PYTHONHOME 启动验证） |
| build-dist.yml | 一键触发以上 4 个 portable | 全平台 portable |
| release.yml | 发布：校验 CHANGELOG → 建 tag → 触发 build-dist → 下载产物 → 上传资产 → 创建 Release | Release + 附件 |

流程注意：

- build-dist / release 触发**必须用 main 分支**（GitHub 只注册默认分支的 workflow；单平台 workflow 需合并 main 才在 Actions 显示）
- **GitHub workflow 解析失败会静默注册失败**：release.yml 曾被覆盖成残缺片段（无 `name`/`on:`）导致 API dispatch 报 422 "does not have 'workflow_dispatch' trigger"——workflow 列表里 name 显示为文件路径即解析失败
- release.yml 第一步校验 CHANGELOG.md 存在 `## v{输入版本}` 段落（支持 `-dev` 后缀），缺失直接失败——发版前必须更新 CHANGELOG
- release 轮询 build-dist 上限 **120 分钟**（Termux job 需约 90 分钟）
- **download-artifact@v4 跨 run 下载**：input 名是 `run-id`（连字符，非 `run_id`），且必须加 `github-token: ${{ secrets.GITHUB_TOKEN }}`——两者缺失都会静默下载 0 个文件导致发布失败
- 上传资产用 github-script（`uploadReleaseAsset` 带重试），softprops/action-gh-release@v2 上传大文件（560MB）会失败

## deb 方案（评估记录，暂未实施）

**2026-08-10 评估结论：暂不做。** 如需推进则用胖 deb 方案。

动机：Linux 安装/卸载体验（`apt install` / `dpkg -r` 干净管理，`.desktop` 菜单集成）。

| 方案 | 体积 | 可行性 |
|------|------|--------|
| 瘦 deb（声明 apt 依赖） | 几 MB | ❌ `playwright`、`pillow-heif`、`yarl` 等不在 Debian/Ubuntu apt 源 |
| **胖 deb**（内置 python-build-standalone + 依赖 + 源码） | ~100MB | ✅ 复用 portable 产物重组 |

**推荐胖 deb 实施路径**（未来如需）：
- `build-portable.sh --platform linux-x64` 产出 → 新增 `build-deb.sh` 重组 deb 结构
- `debian/control` + `usr/lib/novel-downloader-web/` + `usr/bin/` 启动器 + `.desktop`
- `dpkg-deb --build`（无需额外工具）
- 仅 Debian/Ubuntu 系，先 linux-x64

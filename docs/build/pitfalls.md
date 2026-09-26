# CI 构建经验（踩坑记录，改参数前先看）

- **build-portable.sh 的 GitHub API 请求必须带 User-Agent**（无 UA 可能 403，导致 linux-x64 快速失败）
- **Windows portable 漏 init_config.py 事故（v4.2.3 已发布的坏产物根因）**：`backend/main.py` lifespan 硬依赖 `from init_config import check_config, init_all_config`，打包清单漏复制该根模块 → uvicorn 启动 `ModuleNotFoundError`，`启动.bat` 就绪轮询死循环刷屏。修复链：`008e201`（ps1 补 `Copy-Item init_config.py`）+ `6cbe243`（ps1/sh 防漏包加固：build-portable.sh 去掉 `cp ... || true` 静默容错，缺失即 `set -e` 失败；build-web.ps1 补 Nuitka include，后者已随 Nuitka 删除）。**改打包清单后必须核对 init_config.py 是否复制**
- **`启动.bat` 的 `timeout` 必须写 `%SystemRoot%\System32\timeout.exe`**：用户 PATH 中 `D:\Git\usr\bin` 排在 `C:\Windows\system32` 前时，cmd 的 `timeout` 被 Git Bash 的 GNU coreutils timeout 抢占，报 `invalid time interval '/t'`（a66e3dc 修复）
- **Nuitka 已恢复（与 portable 共存，仅 Windows）**：build-nuitka.ps1（`nuitka==4.1.3` 锁版本），**独立 workflow `build-windows-nuitka.yml`**，仅 `workflow_dispatch` 手动触发（2026-09-19 从 `build-windows.yml` 拆出，避免与 portable 产物共用一个 workflow）。旧 build-main / build-cli / build-web 均已移除。**升级 Nuitka 前必须重新验证参数**——4.x 频繁废弃旧参数（`--musl`、`--cache-dir`、`--windows-dependency-tool` 均已移除）。
- **构建脚本 bash 结构**：workflow 内嵌 bash 用 `bash -n` 本地验证（提取 run 块、替换 `${{ }}` 模板变量）
- **产物下载后 Linux 执行权限**：Windows 解压 zip 会丢失执行位 → Linux 上 `chmod +x`

- **前端源码改了必须重新 `npm run build`，否则后端 / 打包产物仍是旧 UI**（2026-09-25 实测踩到）：`frontend/dist` **不入库**（`.gitignore` 的 `dist/`），但它是被消费的那份 —— 后端 `StaticFiles` 托管它（`backend/main.py`）、portable/nuitka 用 `--include-data-dir` 打包它。所以只改 `frontend/src` 而不重建，`git status` **不会有任何提示**，而手机浏览器访问后端服务时看到的还是旧界面。典型症状：dev server 上已经删掉的入口在手机上仍然存在（本轮删掉的独立「书源」页就这样在手机端残留）。修复：`cd frontend && npm run build`（产出新 hash 资源、旧文件自动清理），浏览器强刷一次；后端无需重启（每次请求读磁盘）

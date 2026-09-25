# CI 构建经验（踩坑记录，改参数前先看）

- **build-portable.sh 的 GitHub API 请求必须带 User-Agent**（无 UA 可能 403，导致 linux-x64 快速失败）
- **Windows portable 漏 init_config.py 事故（v4.2.3 已发布的坏产物根因）**：`backend/main.py` lifespan 硬依赖 `from init_config import check_config, init_all_config`，打包清单漏复制该根模块 → uvicorn 启动 `ModuleNotFoundError`，`启动.bat` 就绪轮询死循环刷屏。修复链：`008e201`（ps1 补 `Copy-Item init_config.py`）+ `6cbe243`（ps1/sh 防漏包加固：build-portable.sh 去掉 `cp ... || true` 静默容错，缺失即 `set -e` 失败；build-web.ps1 补 Nuitka include，后者已随 Nuitka 删除）。**改打包清单后必须核对 init_config.py 是否复制**
- **`启动.bat` 的 `timeout` 必须写 `%SystemRoot%\System32\timeout.exe`**：用户 PATH 中 `D:\Git\usr\bin` 排在 `C:\Windows\system32` 前时，cmd 的 `timeout` 被 Git Bash 的 GNU coreutils timeout 抢占，报 `invalid time interval '/t'`（a66e3dc 修复）
- **Nuitka 已恢复（与 portable 共存，仅 Windows）**：build-nuitka.ps1（`nuitka==4.1.3` 锁版本），**独立 workflow `build-windows-nuitka.yml`**，仅 `workflow_dispatch` 手动触发（2026-09-19 从 `build-windows.yml` 拆出，避免与 portable 产物共用一个 workflow）。旧 build-main / build-cli / build-web 均已移除。**升级 Nuitka 前必须重新验证参数**——4.x 频繁废弃旧参数（`--musl`、`--cache-dir`、`--windows-dependency-tool` 均已移除）。
- **构建脚本 bash 结构**：workflow 内嵌 bash 用 `bash -n` 本地验证（提取 run 块、替换 `${{ }}` 模板变量）
- **产物下载后 Linux 执行权限**：Windows 解压 zip 会丢失执行位 → Linux 上 `chmod +x`

- **Android / ChaquoPy 构建（2026-09-19~24 首次打通，8 层阻塞）**：`build-apk.yml` 自 2026-08-02 落地后从未成功过，改它之前先看这几条 ——
  ① Gradle KTS 里 `#` **不是**注释（必须 `//`），写错会报一串 `Script compilation errors`；
  ② Chaquopy 的 `pip { }` 块**只有 `install`/`options`，没有 `exclude`**（写 `exclude("x")` 必然 KTS 编译失败）→ 依赖排除只能用预过滤清单：`build-apk.sh` 第 1b 步生成 `android/.req-android.txt`；
  ③ KTS 里 `java.util.Properties()` 不可用（`java` 被解析为 `Project.java` 扩展）→ `import java.util.Properties` + `Properties()`；
  ④ **pip 只接受 tag ≤ app `minSdk` 的 wheel**（Chaquopy 维护者原话），而 `lxml`/`PyYAML` 只有 `android_24` 的 cp311 wheel → **`minSdk` 必须 ≥ 24**；`android_21` 的包（yarl/multidict/numpy 等）在 24 下仍可安装；
  ⑤ `pydantic-core` 是 Rust 扩展、无 Android wheel → 必须 `pydantic<2`；相应地 `fastapi` 要 pin 到 `≤0.120`（`0.121+` 起要求 `pydantic>=2.9`）；
  ⑥ `Python.start()` 只接受 `Python.Platform`（旧写法 `Python.start(cls, "module")` 编译不过），且模块不会以 `__main__` 执行 → `Python.start(AndroidPlatform(this))` 后显式 `getModule("server").callAttr("_start")`；
  ⑦ `MainActivity` 里不存在的标签 `this@healthPoll` → 改为直接引用 `healthPoll` 字段；
  ⑧ Kotlin 属性在**初始化表达式内不能自引用**：`healthPoll` 的 `run()` 里要写 `this`（不能写 `healthPoll`），并显式标注类型（`: Runnable`）避免类型推断自循环。
  首次成功：run `35975357459`（artifact `novel-crawler-apk-dev` ≈28.6 MB，**未签名**，真机未验证）
- **前端源码改了必须重新 `npm run build`，否则后端 / 手机端 / 打包产物仍是旧 UI**（2026-09-25 实测踩到）：`frontend/dist` **不入库**（`.gitignore` 的 `dist/`），但它是被消费的那份 —— 后端 `StaticFiles` 托管它（`backend/main.py`）、`android/scripts/build-apk.sh` 从它 `cp` 进 APK、portable/nuitka 用 `--include-data-dir` 打包它。所以只改 `frontend/src` 而不重建，`git status` **不会有任何提示**，而手机浏览器访问后端服务时看到的还是旧界面。典型症状：dev server 上已经删掉的入口在手机上仍然存在（本轮删掉的独立「书源」页就这样在手机端残留）。修复：`cd frontend && npm run build`（产出新 hash 资源、旧文件自动清理），浏览器强刷一次；后端无需重启（每次请求读磁盘）

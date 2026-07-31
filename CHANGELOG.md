# 更新日志

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
2. **Nuitka 参数兼容** — 增加 `--msvc=latest` / `--assume-yes-for-downloads`（官方文档推荐，CI 非交互环境不卡下载）
3. **alpine musl 容器缺 bash** — docker 入口改 `sh -c` 并在 apk 安装 bash
4. **ps1 脚本加 UTF-8 BOM** — 修复 Windows PowerShell 5.1 按 ANSI 解析导致中文乱码报错
5. **APK 后端 API 兼容** — 修复 PUT 请求体读取、sources 响应包装

---

## v4.2.0

### 新增

1. **Android 版（WebView 套壳）** — 新增 `android/` 子项目：WebView 加载完整 WebUI（React 前端 100% 复用）+ NanoHTTPd 内嵌 HTTP 服务 + Kotlin 后端（4 平台书源 / 搜索 / 下载 / 书架 / TXT+EPUB 导出），APK 限定 arm64-v8a
2. **发行版 CI** — `build-dist.yml` 手动触发构建 Windows x64 exe / Linux x64+arm64 / APK 四产物；`release.yml` 发布版本：自动创建 tag、以 CHANGELOG 段落为 Release 内容、附构建产物
3. **构建脚本** — build-web / build-main / build-cli / build-android（PowerShell + Shell 双版本），Nuitka 打包参数统一，`.build.lock` 并行锁防 dist/ 互删
4. **init_config 重构** — `app/config/` → `template/config/`（跨 CLI/WebUI 共用默认配置），根目录 `init_config.py` 检查+初始化分离，frozen 感知路径解析，CLI/WebUI 启动自动初始化缺失配置
5. **Web 后端 frozen 配置修复** — `config_service` 支持 `NLD_APP_DATA` → exe 目录 → `__file__` 路径解析，首次运行自动复制默认配置，`database_url` 统一走 `get_database_url()`
6. **cloud_sync delete --all** — 一键全删云端备份

### 变更

1. **删除登录功能** — `login.py`、`AuthCredential`、`do_login` 菜单项移除
2. **前端动态平台** — 平台 / 模式 / provider 从 `sources` API 动态获取，不再硬编码
3. 移除 `soupsieve<2.8` 版本锁定
4. `pyproject.toml` 新增 CLI/Web entry points，支持 `pip install -e .`

### 修复

1. `build-android.ps1` — local.properties 写入 BOM 导致 Gradle 解析失败（改无 BOM UTF-8），签名调用消除 `Invoke-Expression` 注入风险
2. `fetch_text` 支持 `encoding` 参数，92xs GBK 编码自动检测
3. `build-dist.yml` arm64 runner 预装 `libheif-dev`（pillow-heif 无 arm64 wheel）

---

## v4.1.0

### 新增

1. **92xs 书源** — 新增 92xs.net 平台支持
2. **novel_id 加平台前缀** — 消除多平台 ID 冲突，统一格式 `{platform}_{id}`
3. **app/config 默认配置模板** — 新增 `init_config.py` 初始化脚本，自动生成 `app_data/config/` 下缺失的 YAML
4. **pyproject.toml** — 支持 `pip install -e .` 可编辑安装

### 变更

1. **统一 api 配置结构** — 去除 site YAML 中 `api` 下的冗余标量字段，后端统一将 `api` 视为 provider 容器

### 修复

1. download 只保存 db 不导出，避免导出失败阻塞下载
2. 修复 `serial` 空字符串及 hooks 顺序错误
3. 修复前端封面无法显示（92xs 相对路径图片）
4. CI 修复系列：移除未导出的 `get_logger`、修复 oiapi `chapter_content` UTF-8 编码、添加缺失的 `python-box` 依赖、清理废弃 `qiniu` 依赖

### 其他

1. 停止追踪 `groups.yaml`，转为本地配置
2. 完善 `.gitignore` 规则，`docs/` 不再纳入版本控制

---

# v4.0.0 更新日志

## 破坏性变更

1. `novelbase/fetchers` → `novelbase/sources` 重命名
   - 所有导入路径、Logger 名称、CLI 脚手架同步更新
   - `FUNC_FILE_MAP` 映射 `fetch_novel` → `novel_info` 等
2. 导出器 class → 纯函数
   - `TXTExporter`/`EPUBExporter`/`IMGExporter` 删除
   - 统一为 `export(chapters, novel, options)` 纯函数，无实例状态
   - 删除 `BASEExporter` ABC 基类
3. 删除 `fetch_*` 向后兼容别名
   - `fetch_novel` → `novel_info`、`fetch_chapter_list` → `chapter_list`、`fetch_chapter` → `chapter_content`
4. 删除 JSON 书源体系（`json_loader.py` + `app_data/sources/`）
5. `FetcherNotFoundError` → `SourceNotFoundError`

## 新增

1. 后端 download 路由支持纯数字 ID 直达（自动识别平台并构建 URL）
2. 搜索界面 URL 直达输入纯数字 ID 时显示 provider 选择器（按位数推断平台）
3. 导出失败时显示错误 toast，后端返回 error 字段
4. 番茄小说邮箱下载器（Rain API + 邮件发送 ZIP）

## 修复

1. 移动端导出下载改用 `window.open` 替代 `a.click()`，避免浏览器拦截
2. `AuthCredential` 是 dataclass，用 `dataclasses.asdict()` 替代 `model_dump()`
3. 移动端搜索栏布局优化：搜索框 + 按钮一行，筛选控件下一行
4. 修复起点下载功能

## 重构

1. registry 重构 — `register_source()` + `capabilities()` 扩展功能字段
2. downloader 重构 — 改用 `registry.resolve()` 动态分发
3. 删除 Fetcher 中间类，改为模块级常量
4. 删除向后兼容 wrapper 和死代码 `_scan_plugins`

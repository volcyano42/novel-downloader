# 更新日志

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

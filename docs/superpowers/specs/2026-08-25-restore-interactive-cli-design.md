# 还原交互式 CLI（main.py）设计文档

**日期**: 2026-08-25
**状态**: 已确认

---

## 一、动机

2026-08-02 提交 `2c717f7` 移除了交互式 CLI：删除了 `main.py` 入口与 `app/` 交互层（`core.py`/`menus.py`/`ui.py`/`notify.py`/`config.py`），将 `cli.py` 重构为纯非交互 argparse 命令。用户希望**还原交互式 CLI**（菜单式操作体验），要求：

1. **适应 novelbase 的变化**：还原代码必须适配 2026-08-02 之后 novelbase 的全部 API 变更
2. **去掉方框**：全部 box-drawing 装饰字符（主菜单 `┌─┐│├┤└┘` 方框、`───` 标题分隔线、注释分隔符）改为普通文字样式

## 二、还原形态

**并入 `cli/` 包**，不重建 `app/` 包；根目录新建 `main.py` 入口。现有非交互 argparse 命令（`cli/main.py`）**原样保留**，与交互式入口并存。

## 三、文件布局

| 文件 | 来源 | 内容 |
|------|------|------|
| `main.py`（根目录，新建） | 旧 `main.py` | 入口：`from cli.interactive import main; main()` |
| `cli/interactive.py`（新建） | 旧 `app/core.py` | 交互主循环 + 搜索/下载/更新/导出/删除/访问网站 菜单动作 |
| `cli/menus.py`（新建） | 旧 `app/menus.py` | 设置（下载/站点/格式）、导出、删除子菜单 |
| `cli/ui.py`（新建） | 旧 `app/ui.py` | 编号选择、文本输入、平台展示、CJK 宽度辅助（去 box-drawing） |
| `cli/notify.py`（新建） | 旧 `app/notify.py` | 响铃 + Windows 系统通知 |
| 复用 `cli/config.py`、`cli/core.py` | 现有 | 配置加载 / async 下载·更新核心逻辑（已适配 novelbase，零改动） |

## 四、novelbase 适配点

### 4.1 async API

`resolve_meta`/`resolve_chapter_list`/`resolve_chapter`/`search` 全部为 **async**。交互主循环是同步函数，所有异步调用经 `asyncio.run()` 包装：

```python
novel = asyncio.run(resolve_meta(url, engine=engine, skip_delay=True))
chapters = asyncio.run(resolve_chapter_list(novel.url, engine=engine, skip_delay=True))
results = asyncio.run(search(platform, query, engine=engine, skip_delay=True))
```

下载/更新复用 `cli/core.py` 的 `_do_download_inner`/`do_update`（内部已用 `await` + `asyncio.gather` + 信号量并发）。

### 4.2 删除 ID 反查（id_pattern 已退役）

旧 `app/ui.py` 的 `_build_url_from_id()`（按位数/正则匹配平台拼 URL）依赖已删除的 `ID_PATTERN`，**整体删除**。交互搜索流程与 cli 一致：

- URL 输入 → `novelbase.source.platform_from_url(url)` 推断平台
- 关键词搜索 → 用户选平台 → `search()`

不再支持"输入 hash id 反查"（hash 不可逆，2026-08-22 已确认退役）。

### 4.3 导入路径更新

| 旧路径（已失效） | 新路径 |
|---|---|
| `from novelbase.utils.registry import register_source` | `from novelbase.source import register_source` |
| `from novelbase.utils.registry import register_export_options` | `from novelbase.exporter import register_export_options` |
| `register_source()` 返回含 `id_pattern` 的结构 | 返回 `{name: {name, show_name, hosts}}` |
| `search(platform, query, engine=...)`（同步） | `await search(platform, query, engine, page=...)`（async） |

### 4.4 平台推断

新增 `_platform_from_url(url)`，优先 `platform_from_url` 数据驱动；无法识别时抛 `ValueError`（与 `cli/main.py` 一致）。旧 `_platform_from_url` 的硬编码域名判断删除。

### 4.5 配置构建

`build_options` 直接复用 `cli/config.py` 的实现（已含 `extra_args`/`auto_reconnect` 等新 BrowserOptions 字段的透传）。旧 `app/config.py` 不还原。

### 4.6 引擎获取

`_get_engine(platform)` 复用 `cli/core.py` 同构实现：`load_main_config()` + `load_site_config(platform)` + `build_options()` + `create_engine()`。

## 五、去方框（全部 box-drawing 装饰）

- **主菜单**：去掉 `┌─┐│├┤└┘` 48 宽边框，改为纯文字编号列表（`1. 🔍 搜索下载` … `0. 🚪 退出`），信息行（分组/并发）作为普通行打印
- **菜单标题**：`─── 设置 ───`、`─── 删除小说 ───`、`─── 格式设置 ───` 等改为普通标题文字（如 `[设置]` 或直接 `设置`）
- **更新进度**：`── [{i}/{total}] 正在更新: {title} ──` 改为 `[{i}/{total}] 正在更新: {title}`
- **注释分隔符**：`cli/ui.py` 等文件内 `# ── Section ──` 注释改为普通 `# Section` 注释
- **保留**：rich 进度条（`BarColumn` 的 `█` 块字符非 box-drawing）；下载信息里的 emoji

## 六、功能范围（主菜单）

完整还原 7 个功能项：

1. 🔍 搜索下载（URL 直接下载 / 关键词搜索选平台 → 下载）
2. 🔄 更新已有小说（分组展示，单选/全部更新，复用 `cli/core.py` 的 `do_update`）
3. 📤 导出小说（选书 → 选格式 → `export()`）
4. 🔁 重新导出（与导出同一入口，按需）
5. 🗑️ 删除小说（列表 + yes 确认，同步移出分组）
6. ⚙️ 设置（下载设置 / 站点设置 三模式 / 格式开关）
7. 🌐 访问网站（选平台 → browser 模式打开站点首页）
0. 🚪 退出

新增小说下载时仍询问分组归属（`add_novel_to_group`）。

## 七、边界

- `cli/` 非交互命令零改动；`cli/core.py`、`cli/config.py` 只读复用
- `cli/ui.py` 与旧 `app/ui.py` 的差异：删除 `_build_url_from_id`、`_platform_from_url` 改数据驱动、去 box-drawing
- 交互式入口 `main.py` 与旧版一致：先 `check_config`/`init_all_config` 初始化配置，再进主循环；`KeyboardInterrupt`/EOF 优雅退出
- 同步主循环中 `asyncio.run` 每次调用新建事件循环，开销可接受（交互式低频操作）

## 八、测试

- 不新增单元测试文件；交互层为薄壳，核心逻辑已由 `cli/core.py` 覆盖
- 手动验证：`python main.py` 各菜单项走通（搜索下载、更新、导出、删除、设置保存、访问网站退出）
- 回归：现有全量 pytest 不受影响（不触碰 `cli/main.py`、`cli/core.py`、`cli/config.py`）

## 九、影响文件清单

```
main.py                （新建）交互入口
cli/interactive.py     （新建）交互主循环 + 菜单动作（适配 async/新 API）
cli/menus.py           （新建）设置/导出/删除子菜单
cli/ui.py              （新建）输入/进度/平台辅助（去方框、去 ID 反查）
cli/notify.py          （新建）响铃 + Windows 通知
cli/__init__.py        （不改）
cli/main.py            （不改）非交互 argparse 入口
cli/core.py            （不改）async 下载/更新核心
cli/config.py          （不改）配置加载
```

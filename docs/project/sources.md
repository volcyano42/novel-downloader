# 书源（Source）机制

> **2026-09-25 扁平化重构后**：书源为**一层目录** + `source.json` + 4 个能力文件。
> 旧的 `platform` / `SHOW_NAME` / `HOSTS` / `NAME`、四层目录（`{platform}/{mode}/{variant}/`）、
> `variant` 概念、`register_source()` / `platform_from_url()` / `canonical_book_url()`
> **全部移除**——mode **默认**由书源在 `source.json` 里声明（用户可在用户层顶层整体覆盖，见「用户层覆盖」），`source_name` 是唯一的对外键。

## 书源结构

一个书源 = `{源根}/{dir}/` 一层目录。官方源随包发行在 `novelbase/sources/builtin/{dir}/`，
用户源放在任意源根（默认 `<APP_DATA>/sources/{dir}/`）——两者**结构完全相同、加载路径完全相同**。

```
{源根}/{dir}/
├── __init__.py          ← 空包标记
├── source.json          ← 身份 + 出厂配置（见「source.json 规范」）
├── search.py            ← 能力文件（按需；文件名 = 函数名 = 能力名）
├── novel_info.py
├── chapter_list.py
└── chapter_content.py
```

- **目录名 `{dir}`**：合法标识符（下划线），如 `fanqie_requests_default`，仅用于在源根下定位文件。
- **`source_name`**：`source.json` 里的唯一 id（连字符），如 `fanqie-requests-default`——
  是全部公共 API、后端/前端/CLI、`sources/{source_name}.yaml` 的键。两者解耦。
- **`source_name` 全局唯一**（2026-09-27，2026-10-26 扩展到全部源根）：**所有源根**
  （env 多根 / `NLD_PRIVATE_SOURCES` / `<APP_DATA>/sources` / 官方 `builtin`）是
  **同一命名空间**，任何两个目录声明同一个 `source_name` 都会在加载期抛
  `DuplicateSourceNameError`（`ManifestError` 子类），检测点唯一：
  `novelbase/sources/manifest.py::scan_source_names()`。用户源必须自带独立
  `source_name`，**不能**作为官方源的替代实现（「同名能力内置优先、内置缺失再用
  私有补齐」的旧机制已取消）。
- **不设 `_common.py`**：各书源自包含，共享逻辑内联进需要它的能力文件（接受书源间重复的代价）。

## 公共 API（`novelbase/source.py`）

对外只有 4 个函数 + 1 个 URL 入口：

| 函数 | 返回 |
|------|------|
| `list_sources()` | 全部书源 `source_name`（所有源根合并，排序；重名抛 `DuplicateSourceNameError`） |
| `get_manifest(source_name)` | 该书的 `source.json` 内容，归一化后带 `default_config = {能力: 同一套完整字段}`（能力按目录里的 `.py` 发现）；非编译模式同时校验能力文件存在性 |
| `capabilities(source_name)` | `{capability: mode}`，如 `{"search": "requests", "novel_info": "requests", ...}`；未知书源或声明非法返回 `{}`（**撞名例外**：直接抛 `DuplicateSourceNameError`，不吞成空能力） |
| `resolve(source_name, capability)` | `(函数, 该能力的 mode)`；动态 import 并校验必需参数名 |
| `resolve_book_url(raw)` | 把输入规范成完整 URL（仅接受 http(s)，否则 `ValueError`） |

- 所有公开 API 均以 **`source_name` 为键**；目录名只在 `import_module` 时使用。
- `resolve()` 动态 import `novelbase.sources.{dir}.{capability}` 并取同名函数，返回前用
  `inspect.signature` 校验必需参数名（契约见 `novelbase/sources/contracts.py` 的 `CAPABILITY_META`）。
- 未知书源：`get_manifest()` 抛 `KeyError`；`capabilities()` 吞掉异常返回 `{}`（**撞名例外**：`source_name` 重复时直接抛 `DuplicateSourceNameError`，不吞成空能力）。

## `source.json` 规范

> **预览版声明**：`novelbase` 面向开发者且对外公开，但仍是**预览版**——配置格式与公共 API
> 允许破坏性变更，**不承诺向后兼容**。改动会带日期写在本节，升级前请先对照。

```json
{
  "source_name": "fanqie-requests-default",
  "source_alias": "番茄·直连",
  "source_group": "番茄",
  "mode": "requests",
  "timeout": 30,
  "retry_times": 3,
  "delay": [0, 0],
  "backoff_factor": 2,
  "headers": {"User-Agent": "..."},
  "cookies": {},
  "proxies": {}
}
```

| 字段 | 含义 |
|------|------|
| `source_name` | 唯一 id；也是 `sources/{source_name}.yaml` 的文件名 |
| `source_alias` | （**可选**）显示别名；`sources/{source_name}.yaml` 顶层可覆盖。缺省 = 未设，界面回落 `source_name` |
| `source_group` | （**可选**）分组名（一个源一个组，`""` = 未分组）；`sources/{source_name}.yaml` 顶层可覆盖 |
| `concurrency` | （**可选**）书源级并发额度，缺省 **1**；`sources/{source_name}.yaml` 顶层可覆盖（见下） |
| `mode` | **必填**，`requests` / `browser` / `api` 之一 |
| 其余字段 | 由 `mode` 决定，见下 |

**一个书源只有一套参数（2026-10-25 起）**：不再有 `common` / `default_config` 能力段——
四类能力共享同一个 `mode` 和同一套字段。旧写法（`common` + 各能力段）**已废弃且不做兼容**，
遇到会直接抛 `ManifestError`。

**能力由文件系统发现**：目录里有 `search.py` / `novel_info.py` / `chapter_list.py` /
`chapter_content.py` 中的哪几个，就对外暴露哪几个能力（不再在 `source.json` 里声明）。
一个能力文件都没有 → `get_manifest()` 抛 `ManifestError`。

- 字段按 mode 划分（`MODE_FIELDS`，与 `novelbase/core/options.py` 的三个 dataclass 对应）：
  - `requests`：`mode, timeout, retry_times, delay, backoff_factor, headers, cookies, proxies`
  - `browser`：`mode, timeout, retry_times, delay, backoff_factor, browser_type, headless, user_data_dir, viewport, extra_args, auto_reconnect`
  - `api`：`mode, timeout, retry_times, delay, backoff_factor, key, params`
- 字段命名全链统一用 `retry_times`。
- `browser` 的 `user_data_dir`：**出厂默认** = `app_data/browser/Chromium/User Data`（持久化
  profile，登录态落盘）。相对路径由 `shared/config.py::build_options()` 按**仓库根**解析成绝对
  路径后交给 `launch_persistent_context()`；用户层写成空串 = 匿名 context（窗口里登录不落盘，
  进程退出即失效，`deep_merge` 的空串会覆盖出厂默认）。
- **元信息读取入口**（`shared.config`）：`source_group(name)` / `source_alias(name)`（用户层顶层覆盖出厂 `source.json` 顶层，空串 = 未设）/ `display_name(name)`（别名优先、未设回落 `source_name`）。`enabled` 已彻底废弃（2026-09-27）。

### 用户层覆盖（`sources/{source_name}.yaml`）

用户层就是**顶层一套字段**，形状与 `source.json` 一致（不再有 `common` 段或能力段）：

```yaml
mode: requests
timeout: 60
delay: [3, 5]
```

- 有效 mode = 用户层顶层 `mode`（合法值 `browser`/`requests`/`api`）优先于 `source.json` 声明；
  非法值忽略并回退声明。**一个 mode 对所有能力生效**（不再逐能力覆盖）。
- 唯一入口：`shared.config.effective_capabilities(source_name)`；`merged_source_config()`
  按有效 mode 取 `ENGINE_DEFAULTS[mode]` 作基底并保留 `mode` 键（表单回显）。
- core 分发层 `novelbase/core/downloader.py` 的 4 个函数接受**单个 `Engine` 实例**（调用方按
  `effective_capabilities()` 选有效 mode 后自行 `create_engine`）；core **不解析 mode**。
- API：`GET /api/v2/config/sources/{name}` 返回 `capabilities`（有效）与 `declared_capabilities`（声明）；
  `PUT` 直接传顶层字段（如 `{"timeout": 60}`），`mode: null` 即删除覆盖。
- 已知限制：不同 mode 的接口/参数互不通用，覆盖后不保证可用。

### 书源级并发 `concurrency`（2026-09-25）

书源**同时最多几个请求在飞**，**跨任务共享**（同一书源的两个下载任务共用这一额度）。

- **存储**：`source.json` **顶层**（与 `source_name` 同级，**可选**，缺省 1）；
  用户层 `app_data/config/sources/{source_name}.yaml` **顶层**可覆盖（与 `source_alias` / `source_group` 同级）。
  ⚠️ `concurrency` 是**元信息**、不是引擎字段，因此不在 `MODE_FIELDS` 里（引擎字段会按 mode 校验合法性）。
- **读取**：唯一入口 `shared.config.source_concurrency(source_name)`——用户层顶层 `concurrency` 覆盖出厂顶层，
  缺省 1；非法值（非正整数）忽略回退 1；未知书源返回 1。
- **覆盖范围**：任务内发出的请求都受该额度约束（`resolve_meta` 与每章 `resolve_chapter`）。
  CLI 章节并发上限 = `min(max_workers, source_concurrency(source_name))`，
  默认 `concurrency=1` 下即**单章串行**（提速靠 `delay=0`）。
- **API**：`GET /api/v2/config/sources/{name}` 返回有效 `concurrency`；
  `PUT` 支持顶层 `concurrency`（正整数写入用户层顶层，非法值忽略，不写坏 yaml）。
- **已知边界**：① 已是 `downloading` 的任务被暂停仍占任务槽；
  ② 后端「检查更新」走的独立路由（`GET /storage/novel/{id}/chapters` 等）**不经**该额度——
  同理搜索、远端章节列表等独立路由也不经书源额度；③ `max_workers` 下调最多 1 秒生效（TTL 缓存）。

## 内置书源

| source_name | mode | source_alias | source_group |
|-------------|:----:|--------------|--------------|
| `92xs-requests-default` | requests | `92xs` | `92xs` |
| `fanqie-requests-default` | requests | `番茄·直连` | `番茄` |
| `fanqie-browser-default` | browser | `番茄·浏览器` | `番茄` |
| `fanqie-api-rain` | api | `番茄·Rain API` | `番茄` |
| `fanqie-api-oiapi` | api | `番茄·oiapi` | `番茄` |
| `qidian-requests-default` | requests | `起点·直连` | `起点` |
| `qidian-browser-default` | browser | `起点·浏览器` | `起点` |
| `qimao-requests-default` | requests | `七猫·直连` | `七猫` |
| `qimao-browser-default` | browser | `七猫·浏览器` | `七猫` |
| `qimao-api-rain` | api | `七猫·Rain API` | `七猫` |

- 书源显示名 = 别名 `source_alias`（未设回落 `source_name`），由 `shared.config.display_name()`
  统一提供（界面、日志、CLI）；`source_name`（如 `fanqie-requests-default`）仍是唯一对外键。
- 新增书源只需在 `sources/` 下建一层目录 + 文件，**零注册表修改**；
  `python cli.py dev new-source --name <source_name>` 生成脚手架（见 [cli.md](cli.md)）。

## Novel.id 生成（`novelbase/utils/urls.py`）

```
Novel.id = sha256(url)[:32]      # 32 位 hex，无前缀
```

- 对外标识（模型字段 / 磁盘文件名 / API / 前端 / CLI）= `sha256(url)[:32]`。
- 库内 `meta.id` 列存**书源返回的 url 原样**（不做规范化，可按 url 查书）。
- **不做 url 规范化**：同一本书的不同 url 形态会得到不同 id（如 92xs 的 `/book/{id}.html`
  与 `/html/{id}/`），入库与后续使用须保持同一形态；重构**不得改变书源返回的 url**。
- 旧的 `canonical_book_url` / `platform_from_url` / `ID_PATTERN` / `ORIGIN_ID_PATTERN` /
  `BOOK_URL_TEMPLATE` / `get_source_for_id` 全部删除——**core 不再承载站点知识**。
- `resolve_book_url(raw)` 仅接受 http(s) 输入，无法从 id 反推 url。

## 源根（多根发现，2026-10-26）

书源**不再要求待在 `novelbase/sources/` 包内**。发现层按有序列表扫源根，所有根下的源
走**同一条加载路径**（`importlib.util.spec_from_file_location`），包内包外无差别：

| 顺序 | 源根 | 用途 |
|---|---|---|
| 1 | `NLD_SOURCE_ROOTS`（`os.pathsep` 分隔，可多根） | 显式指定（CI、多套源切换） |
| 2 | `NLD_PRIVATE_SOURCES` | 旧变量，保留为追加根（兼容既有用法） |
| 3 | `add_source_root()` 注入 | `<APP_DATA>/sources` 由 `shared.config` 在 import 时注册 |
| 4 | `novelbase/sources/builtin/` | 官方源，随 wheel 发行 |

- **顺序不改变语义**：撞名一律抛 `DuplicateSourceNameError`，不退化成一占先得；顺序只影响报错消息里的先占者/后来者。
- **`novelbase` 不认识 `app_data`**：它是可 `pip install` 的纯库，不能反向依赖 `shared`。用户根由 `shared.config.user_sources_dir()` 注册——直接用 novelbase 的第三方用户拿到的是「官方 `builtin` + env 根」。
- **用户源安装**：把源目录解压进 `<APP_DATA>/sources/`（该目录由 `init_config` 首次运行创建），**无需环境变量、无需重装**。
- **编译模式（Nuitka）是已知特例**：产物里 `builtin/` 下的 `.py` 已编译、文件系统无源文件，只能读 `utils/_manifest.py` 静态表（`python -m novelbase.utils.build_manifest` 生成，只覆盖 `builtin`）；用户源仍在文件系统里照常加载。两张表合并后才查撞名。
- **改源文件内容需重启进程才生效**（模块按「根哈希 + 目录名 + 能力」缓存在 `sys.modules`）；但增删源目录是即时生效的（目录扫描不缓存）。

```
<APP_DATA>/sources/
└── my_source/               ← 结构镜像官方源
    ├── __init__.py
    ├── source.json
    ├── search.py
    ├── novel_info.py
    ├── chapter_list.py
    └── chapter_content.py
```

- 根不存在 / 不是目录 / `_` 开头的子目录 → 静默跳过。
- 用途：官方仓库只保留能公开的源；敏感实现（逆向/破解）放用户源根，不进任何仓库。

# 书源（Source）机制

> **2026-09-25 扁平化重构后**：书源为**一层目录** + `source.json` + 4 个能力文件。
> 旧的 `platform` / `SHOW_NAME` / `HOSTS` / `NAME`、四层目录（`{platform}/{mode}/{variant}/`）、
> `variant` 概念、`register_source()` / `platform_from_url()` / `canonical_book_url()`
> **全部移除**——mode **默认**由书源在 `source.json` 里声明（用户可逐能力覆盖，见「mode 的用户覆盖」），`source_name` 是唯一的对外键。

## 书源结构

一个书源 = `novelbase/sources/{dir}/` 一层目录：

```
novelbase/sources/{dir}/
├── __init__.py          ← 空包标记
├── source.json          ← 身份 + 出厂配置（见「source.json 规范」）
├── search.py            ← 能力文件（按需；文件名 = 函数名 = 能力名）
├── novel_info.py
├── chapter_list.py
└── chapter_content.py
```

- **目录名 `{dir}`**：合法标识符（下划线），如 `fanqie_requests_default`，仅在 `import_module` 时使用。
- **`source_name`**：`source.json` 里的唯一 id（连字符），如 `fanqie-requests-default`——
  是全部公共 API、后端/前端/CLI、`sites/{source_name}.yaml` 的键。两者解耦。
- **不设 `_common.py`**：各书源自包含，共享逻辑内联进需要它的能力文件（接受书源间重复的代价）。

## 公共 API（`novelbase/source.py`）

对外只有 4 个函数 + 1 个 URL 入口：

| 函数 | 返回 |
|------|------|
| `list_sources()` | 全部书源 `source_name`（内置 + 私有，去重排序） |
| `get_manifest(source_name)` | 该书的 `source.json` 内容（`default_config` 已合并 `common`；非编译模式校验能力段 ⇔ `.py` 文件） |
| `capabilities(source_name)` | `{capability: mode}`，如 `{"search": "requests", "novel_info": "requests", ...}`；未知书源返回 `{}` |
| `resolve(source_name, capability)` | `(函数, 该能力的 mode)`；动态 import 并校验必需参数名 |
| `resolve_book_url(raw)` | 把输入规范成完整 URL（仅接受 http(s)，否则 `ValueError`） |

- 所有公开 API 均以 **`source_name` 为键**；目录名只在 `import_module` 时使用。
- `resolve()` 动态 import `novelbase.sources.{dir}.{capability}` 并取同名函数，返回前用
  `inspect.signature` 校验必需参数名（契约见 `novelbase/sources/contracts.py` 的 `CAPABILITY_META`）。
- 未知书源：`get_manifest()` 抛 `KeyError`；`capabilities()` 吞掉异常返回 `{}`。

## `source.json` 规范

```json
{
  "source_name": "fanqie-requests-default",
  "enabled": true,
  "concurrency": 1,
  "common": {
    "mode": "requests", "timeout": 30, "retry_times": 3,
    "delay": [0, 0], "backoff_factor": 2,
    "headers": {"User-Agent": "..."}, "cookies": {}, "proxies": {}
  },
  "default_config": {
    "search": {}, "novel_info": {}, "chapter_list": {}, "chapter_content": {}
  }
}
```

| 字段 | 含义 |
|------|------|
| `source_name` | 唯一 id；也是 `sites/{source_name}.yaml` 的文件名 |
| `enabled` | 出厂启用状态（**api 类默认 `false`，requests/browser 默认 `true`**）；`sites/{source_name}.yaml` 顶层 `enabled` 可覆盖 |
| `concurrency` | （**可选**，顶层）书源级并发额度，缺省 **1**；`sites/{source_name}.yaml` 顶层可覆盖（见下） |
| `common` | 并入每个能力段（能力段覆盖 `common`）；其字段必须对**所有出现的 mode** 都合法 |
| `default_config` | 逐能力段；每段 `mode` 缺省继承 `common.mode` |

- **能力段存在 ⇔ 同名 `.py` 文件存在**（双向），不一致直接抛 `ManifestError`
  （加载与校验见 `novelbase/sources/manifest.py`）。
- 字段按 mode 划分（`MODE_FIELDS`，与 `novelbase/core/options.py` 的三个 dataclass 对应）：
  - `requests`：`mode, timeout, retry_times, delay, backoff_factor, headers, cookies, proxies`
  - `browser`：`mode, timeout, retry_times, delay, backoff_factor, browser_type, headless, user_data_dir, viewport, extra_args, auto_reconnect`
  - `api`：`mode, timeout, retry_times, delay, backoff_factor, key, params`
- 字段命名全链统一用 `retry_times`。

### mode 的用户覆盖（2026-09-25）

- 有效 mode = 用户层 `app_data/config/sites/{source_name}.yaml` 的 `{cap}.mode`（合法值 `browser`/`requests`/`api`）
  优先于 `source.json` 声明；非法值忽略并回退声明
- 唯一入口：`shared.config.effective_capabilities(source_name)`；`merged_source_config()` 按有效 mode 取
  `ENGINE_DEFAULTS[mode]` 作基底并保留 `mode` 键（表单回显）
- core 分发层 `novelbase/core/downloader.py` 的 4 个函数接受可选 `mode_overrides`（能力名 → mode），
  由调用方（backend `task_manager` / 各路由、CLI）透传；`novelbase.source.capabilities()` 语义不变
- API：`GET /api/v2/config/sources/{name}` 返回 `capabilities`（有效）与 `declared_capabilities`（声明）；
  `PUT` 传 `config[cap].mode = null` 即删除覆盖
- 已知限制：不同 mode 的接口/参数互不通用，覆盖后不保证可用

### 书源级并发 `concurrency`（2026-09-25）

书源**同时最多几个请求在飞**，**跨任务共享**（同一书源的两个下载任务共用这一额度）。

- **存储**：`source.json` **顶层**（与 `source_name` / `enabled` 同级，**可选**，缺省 1）；
  用户层 `app_data/config/sites/{source_name}.yaml` **顶层**可覆盖（与 `enabled` 同级）。
  ⚠️ 不能放 `common`：`common` 的字段会被并入各能力段并受 `MODE_FIELDS` 校验，`concurrency` 不在其中。
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

## 环境能力表 —— Android 不支持 browser（2026-09-26）

APK 是**套壳**（WebView + 内嵌 FastAPI），构建时排除了 `playwright`，因此 `browser` 引擎在本环境不存在。
这条事实由**环境能力表**贯穿 core → 后端 → 前端，唯一入口全在 `shared/config.py`：

| 函数 | 语义 |
|------|------|
| `platform()` | 读 `NLD_PLATFORM`：`android` → `"android"`；其余/未设 → `"desktop"`（桌面行为与历史完全一致） |
| `supported_modes()` | `android` → `("requests", "api")`；桌面 → `VALID_MODES` 全量。**唯一真源** |
| `effective_capabilities(source_name)` | 覆盖判定用 `supported_modes()`：本环境不支持的覆盖被**忽略并回退书源声明**（用户 yaml 不动，回桌面版自动生效） |
| `available_capabilities(source_name)` | 有效能力中 mode 受支持的子集（未知书源 → `{}`） |
| `is_source_available(source_name)` | **源级、全能力**判定：所有有效能力都受支持才为 `True`。混 mode 私有源在 Android 上整源判不可用（避免「半可用」踩到执行路径），未知书源 → `False` |
| `enabled_source_names()` | = 「出厂/用户 `enabled`」 ∩ 「本环境可用」 |

- `NLD_PLATFORM` 由 `android/app/src/main/python/server.py` 在模块级 `setdefault` 注入；桌面 / portable / Nuitka 不设该 env。
- core 只兜底：`novelbase/core/engine.py` 的 `_async_playwright()` 在依赖缺失时抛 `ModeUnavailableError`（而非裸 `ImportError`）；core **不读环境变量**（保持纯库，无站点/环境知识）。
- CLI 与后端共用 `enabled_source_names()`，因此 Android 上的自动路径不会再碰 browser 书源。

### HTTP 出口

| 端点 | 行为 |
|------|------|
| `GET /api/v2/download/sources` | 每源附 `available`（**全量返回**，前端据此置灰；不参与搜索/下载） |
| `GET /api/v2/config/sources/{name}` | 附 `available`（**GET 一律放行**，否则前端无法置灰展示） |
| `GET /api/v2/config/environment` | `{platform, supported_modes}`，前端 mode 下拉的选项来源 |
| `PUT /api/v2/config/sources/{name}` | `enabled: true` 但源不可用 → 400；`config[cap].mode` 不在 `supported_modes()` → 400（校验先于落盘，任一非法整体拒绝）；`enabled: false` / `mode: null` 永远允许 |
| 执行入口（`/download/search`、`/download/novel*`、下载任务） | `source_guard.require_available_source()` → 400（与 `require_known_source()` 的 404 同处一个「HTTP 边界唯一校验点」） |

前端：设置页仍**列出** browser 书源，但置灰 + 标注「本环境不支持 browser」+ 禁用启用开关；`toSourceOptions()` 会滤掉 `available === false` 的源（搜索 / 换源 / 书架共用），所以选源列表里不出现。

设计文档：[superpowers/specs/2026-09-26-android-shell-no-browser-design.md](../superpowers/specs/2026-09-26-android-shell-no-browser-design.md)。

## 内置书源

| source_name | mode | enabled（出厂） | Android 可用 |
|-------------|:----:|:--:|:--:|
| `92xs-requests-default` | requests | ✅ | ✅ |
| `fanqie-requests-default` | requests | ✅ | ✅ |
| `fanqie-browser-default` | browser | ✅ | ❌ |
| `fanqie-api-rain` | api | ❌ | ✅ |
| `fanqie-api-oiapi` | api | ❌ | ✅ |
| `qidian-requests-default` | requests | ✅ | ✅ |
| `qidian-browser-default` | browser | ✅ | ❌ |
| `qimao-requests-default` | requests | ✅ | ✅ |
| `qimao-browser-default` | browser | ✅ | ❌ |
| `qimao-api-rain` | api | ❌ | ✅ |

- 书源**没有中文显示名**，界面、日志、CLI 统一显示 `source_name`。
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

## 私有源隔离（`NLD_PRIVATE_SOURCES`）

环境变量 `NLD_PRIVATE_SOURCES` 指向外部目录，镜像 `sources/{dir}/` 结构。
`list_sources()` / `capabilities()` 合并内置与私有书源；`resolve()` 中**同名能力内置优先**，
内置缺失再用私有补齐（私有目录在包外，走 `importlib.util.spec_from_file_location` 加载）。

```
$NLD_PRIVATE_SOURCES/
└── fanqie_api_custom/       ← 镜像 sources/{dir}/ 结构
    ├── source.json
    ├── search.py
    ├── novel_info.py
    ├── chapter_list.py
    └── chapter_content.py
```

- 未设置环境变量时行为完全不变；目录不存在时静默跳过。
- 用途：公开仓库不含危险的逆向/破解实现，本地开发设好环境变量即可使用全部功能。

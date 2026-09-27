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
- **`source_name` 全局唯一**（2026-09-27）：内置根与私有根（`NLD_PRIVATE_SOURCES`）
  是**同一命名空间**，任何两个目录声明同一个 `source_name` 都会在加载期抛
  `DuplicateSourceNameError`（`ManifestError` 子类），检测点唯一：
  `novelbase/sources/manifest.py::scan_source_names()`。私有源必须自带独立
  `source_name`，**不能**作为内置源的替代实现（「同名能力内置优先、内置缺失再用
  私有补齐」的旧机制已取消）。
- **不设 `_common.py`**：各书源自包含，共享逻辑内联进需要它的能力文件（接受书源间重复的代价）。

## 公共 API（`novelbase/source.py`）

对外只有 4 个函数 + 1 个 URL 入口：

| 函数 | 返回 |
|------|------|
| `list_sources()` | 全部书源 `source_name`（内置 + 私有，排序；重名抛 `DuplicateSourceNameError`） |
| `get_manifest(source_name)` | 该书的 `source.json` 内容（`default_config` 已合并 `common`；非编译模式校验能力段 ⇔ `.py` 文件） |
| `capabilities(source_name)` | `{capability: mode}`，如 `{"search": "requests", "novel_info": "requests", ...}`；未知书源或声明非法返回 `{}`（**撞名例外**：直接抛 `DuplicateSourceNameError`，不吞成空能力） |
| `resolve(source_name, capability)` | `(函数, 该能力的 mode)`；动态 import 并校验必需参数名 |
| `resolve_book_url(raw)` | 把输入规范成完整 URL（仅接受 http(s)，否则 `ValueError`） |

- 所有公开 API 均以 **`source_name` 为键**；目录名只在 `import_module` 时使用。
- `resolve()` 动态 import `novelbase.sources.{dir}.{capability}` 并取同名函数，返回前用
  `inspect.signature` 校验必需参数名（契约见 `novelbase/sources/contracts.py` 的 `CAPABILITY_META`）。
- 未知书源：`get_manifest()` 抛 `KeyError`；`capabilities()` 吞掉异常返回 `{}`（**撞名例外**：`source_name` 重复时直接抛 `DuplicateSourceNameError`，不吞成空能力）。

## `source.json` 规范

```json
{
  "source_name": "fanqie-requests-default",
  "source_alias": "番茄·直连",
  "source_group": "番茄",
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
| `source_alias` | （**可选**，顶层）显示别名；`sites/{source_name}.yaml` 顶层可覆盖。缺省 = 未设，界面回落 `source_name` |
| `source_group` | （**可选**，顶层）分组名（一个源一个组，`""` = 未分组）；`sites/{source_name}.yaml` 顶层可覆盖 |
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
- **元信息读取入口**（`shared.config`）：`source_group(name)` / `source_alias(name)`（用户层顶层覆盖出厂 `source.json` 顶层，空串 = 未设）/ `display_name(name)`（别名优先、未设回落 `source_name`）。`enabled` 已彻底废弃（2026-09-27，见下）。

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

- **存储**：`source.json` **顶层**（与 `source_name` 同级，**可选**，缺省 1）；
  用户层 `app_data/config/sites/{source_name}.yaml` **顶层**可覆盖（与 `source_alias` / `source_group` 同级）。
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

## 私有源隔离（`NLD_PRIVATE_SOURCES`）

环境变量 `NLD_PRIVATE_SOURCES` 指向外部目录，镜像 `sources/{dir}/` 结构。
`list_sources()` / `capabilities()` 合并内置与私有书源（私有目录在包外，走
`importlib.util.spec_from_file_location` 加载）。
**私有源须自带独立 `source_name`**：内置根与私有根是同一命名空间，任何重名（含私有源
复用内置 id）都会在加载期抛 `DuplicateSourceNameError`——原「同名能力内置优先、
内置缺失再用私有补齐」的机制已于 **2026-09-27 取消**。已有复用内置 id 的私有目录，
升级后需改其 `source.json` 的 `source_name`（目录名可不变）并同步
`app_data/config/sites/{新名}.yaml`。

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

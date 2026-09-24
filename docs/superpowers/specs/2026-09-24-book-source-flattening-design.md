# 书源扁平化重构 — 设计

- 日期：2026-09-24
- 状态：待 review（设计已逐节确认）
- 范围：`novelbase/sources/`、`novelbase/source.py`、`novelbase/core/downloader.py`、`novelbase/models/novel.py`、`novelbase/utils/urls.py`、`shared/config.py`、`shared/user_data.py`、`backend/`、`cli/`、`frontend/`、`tests/`
- 替代物：`novelbase/sources/{platform}/{mode}/{variant}/` 四层结构（**不保留兼容层**）

## 背景

现状盘点（2026-09-24 实测）：

- `novelbase/sources/` 下 **69 个 `.py`**：4 个平台目录，结构为 `{platform}/{mode}/{variant}/{capability}.py` 四层。
- 其中 **23 个是空 `__init__.py`**（纯包标记，`import_module` 需要），**40 个是「一个能力一个文件」**（`search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`）。
- 真正装了共享逻辑的只有 5 个文件：`contracts.py`、`fanqie/_common.py`、`qidian/_common.py`、`qimao/_common.py`、`fanqie/api/rain/_helpers.py`。
- 能力矩阵由**目录扫描**产生：`novelbase/source.py:170 _scan_capabilities()` → `{mode: {variant: [functions]}}`；分发由 `novelbase/source.py:230 resolve(name, mode, function, variant)` 完成。
- `mode`/`variant` 是**端到端用户可选维度**：CLI `--mode`（`cli/main.py:135`、`cli/interactive.py:38`）、后端每路由 Query 参数（`backend/routers/download.py:34-35,64-65,82,98,112-113`）、引擎缓存 key（`backend/services/engine_manager.py:25-30` 的 `_fingerprint(platform, mode, variant)`）、前端两级选择器（`frontend/src/features/bookshelf/SearchBar.tsx:77-88`、`frontend/src/features/download/DownloadDialog.tsx:12-110`）。
- 每新增一个 `{mode}/{variant}` 组合要摊 **5 个新文件**（1 个空 `__init__.py` + 4 个能力文件）；最小书源 `92xs`（只有 requests）也要 7 个文件。

问题：组织方式过重——四层目录 + 固定文件名约定 + 空包标记，把「书源」这个业务概念埋进了文件系统路径里。加一个书源、或改一个能力的实现方式，都要动目录结构。

另有一处文档与实现脱节：`AGENTS.md:34` 仍写「Registry 动态分发 `registry.resolve(name, mode, function, provider?)` + `FUNC_FILE_MAP`」，但 `registry.py` 已不存在（全库无匹配），`FUNC_FILE_MAP` 已被 `novelbase/sources/contracts.py` 的 `CAPABILITY_META` 取代。

## 目标

1. 书源组织**从四层压到一层**：`sources/{dir}/`。
2. 书源成为一等公民：`source.json` 声明身份（`source_name`/`show_name`/`enabled`）与配置（`default_config`）。
3. **`mode` 由书源自己声明**，用户不再选 mode——用户只选书源。
4. **彻底移除 platform 概念**（不是改名，是删除这个实体）。
5. 补上 `hosts` 消失造成的入口缺口：搜索用「已启用书源并发」，URL 解析由用户指定书源。

## 非目标

- 不改导出器子系统（`novelbase/exporters/`、`novelbase/exporter.py`）。
- 不改 `app_data/config/formats/*.yaml`。
- **不做旧结构兼容层**：旧代码与旧目录直接抛弃。
- **不迁移旧 `sites/*.yaml`**（含 api key / headers / cookies），用户重新配置。
- **不迁移 `search_history`**，drop 重建。

## 目录结构

新结构，10 个书源目录，每个 6 个文件（1 个空 `__init__.py` + 1 个 `source.json` + 4 个能力文件）：

```
novelbase/sources/
  __init__.py                # 保留（包标记）
  contracts.py               # CAPABILITY_META：能力清单 + 必需参数
  fanqie_api_rain/
    __init__.py              # 空
    source.json
    search.py
    novel_info.py
    chapter_list.py
    chapter_content.py
    _common.py               # 可选：本书源内部共享，不跨书源
  92xs_requests_default/
    __init__.py
    source.json
    search.py / novel_info.py / chapter_list.py / chapter_content.py
    canonical_url.py         # 可选：仅 URL 有特例的书源（92xs / qidian）需要
  ...
```

十个书源目录（由现有 `{platform}/{mode}/{variant}` 组合展开）：

| 目录 | source_name | 原路径 |
|---|---|---|
| `fanqie_api_oiapi` | `fanqie-api-oiapi` | `fanqie/api/oiapi/` |
| `fanqie_api_rain` | `fanqie-api-rain` | `fanqie/api/rain/` |
| `fanqie_browser_default` | `fanqie-browser-default` | `fanqie/browser/default/` |
| `fanqie_requests_default` | `fanqie-requests-default` | `fanqie/requests/default/` |
| `qidian_browser_default` | `qidian-browser-default` | `qidian/browser/default/` |
| `qidian_requests_default` | `qidian-requests-default` | `qidian/requests/default/` |
| `qimao_api_rain` | `qimao-api-rain` | `qimao/api/rain/` |
| `qimao_browser_default` | `qimao-browser-default` | `qimao/browser/default/` |
| `qimao_requests_default` | `qimao-requests-default` | `qimao/requests/default/` |
| `92xs_requests_default` | `92xs-requests-default` | `92xs/requests/default/` |

约定：

- **目录名必须是合法 Python 标识符**（下划线形式），因为 `search.py` 要用 `from ._common import ...` 这类相对 import，必须有包（保留一个空 `__init__.py`）。
- **`source_name` 与目录名解耦**：目录名只是磁盘位置，`source_name` 是系统内唯一 id（`sites/{source_name}.yaml` 用它命名）。系统**不解析** `source_name` 的结构（`variant` 由字段显式给出，不从名字反解）。
- 表里的 `{平台}-{mode}-{variant}` 命名只是便于人读的建议约定，不是强制规则。

**不设跨书源共享目录**：每个书源独立，需要复用就各自带一份 `_common.py`（重复可接受）。这排除了原先设想的 `sources/_shared/`。

规模变化（诚实记录）：

| | 现在 | 重构后 |
|---|---|---|
| 目录层次 | 4 层 | **2 层** |
| 能力实现 `.py` | 40 | 43（+3 个 `canonical_url.py`） |
| 空 `__init__.py` | 23 | 10 |
| `source.json` | 0 | 10 |
| 平台级 `_common.py` | 4 | 0 |
| 书源级 `_common.py` | — | 最多 9 份副本（按需，各书源自带） |
| 文件合计 | 69 | 65（+ 最多 9 份 `_common.py` 副本 = 74） |

即：**文件总数几乎不变**，收益在于层次从 4 层降到 2 层、书源成为一等公民、换 mode 不再动目录结构。若要文件数量级的收益，需要改成「一个书源一个 `impl.py`」（40 → 10 个能力文件、总数 ~25），本设计**不做**这个选择。

**「每书源独立」的代价要如实记录**：原先 4 个平台级 `_common.py` 承担的共享逻辑，扁平化后按书源各带一份（最多 9 份副本），代码会重复。这是「抛弃 platform 概念」的直接成本，本设计接受。

## source.json 规范

```jsonc
{
  "source_name": "fanqie-api-rain",     // 必填，唯一 id，也是 sites/{source_name}.yaml 的文件名
  "show_name": "番茄（API · rain）",     // 必填，展示名
  "enabled": true,                       // 出厂默认启用状态；用户层可覆盖

  "default_config": {                    // 逐能力配置段；段内 mode + 该 mode 的字段
    "search": {
      "mode": "api",
      "variant": "rain",                 // mode=api 时必需
      "timeout": 30,
      "retry_times": 3,
      "delay": [2, 3],
      "backoff_factor": 2,
      "key": "",
      "params": {}
    },
    "novel_info":   { "mode": "api", "variant": "rain", "timeout": 30, "retry_times": 3, "delay": [2, 3], "backoff_factor": 2, "key": "", "params": {} },
    "chapter_list": { "mode": "api", "variant": "rain", "timeout": 30, "retry_times": 3, "delay": [2, 3], "backoff_factor": 2, "key": "", "params": {} },
    "chapter_content": {
      "mode": "browser",                 // 允许逐能力偏离
      "timeout": 60,
      "retry_times": 2,
      "delay": [2, 5],
      "backoff_factor": 2,
      "browser_type": "chromium",
      "headless": false,
      "user_data_dir": "app_data/browser/Chromium/User Data",
      "viewport": { "width": 1280, "height": 720 },
      "extra_args": [],
      "auto_reconnect": false
    }
  }
}
```

字段集按 mode 划分（对应现有 `novelbase/core/options.py` 的三个 dataclass，不引入新概念）：

| 归属 | 字段 |
|---|---|
| 三种 mode 共有 | `mode`、`timeout`、`retry_times`、`delay`、`backoff_factor` |
| 仅 `api` | `variant`、`key`、`params` |
| 仅 `requests` | `headers`、`cookies`、`proxies` |
| 仅 `browser` | `browser_type`、`headless`、`user_data_dir`、`viewport`、`extra_args`、`auto_reconnect` |

规则：

1. **能力段存在 ⇔ 对应 `.py` 文件存在**（`canonical_url` 例外，见第 6 条）。`default_config` 里有 `search` 段，目录下就必须有 `search.py`；反之亦然。不一致在加载时**直接报错**。这条要落进 `capabilities()` 的实现与测试。
2. `default_config` 的值是**出厂默认**（配置合并的第 2 层），用户层 `sites/{source_name}.yaml` 覆盖它。
3. 字段命名全链保持 `retry_times`（不引入 `max_retry`），与 `options.py`、`ENGINE_DEFAULTS`、前端设置页一致。
4. 逐能力写全会产生重复（上面三段 `search`/`novel_info`/`chapter_list` 完全一样）。**本设计接受这个重复**，不引入公共默认段；若日后嫌重，可加一个公共默认段让能力段只写差异。
5. 不加 `version`/`author`/`group` 等字段（YAGNI）；私有书源要标注可加 `comment`。
6. **`canonical_url` 是唯一没有配置段的能力**：它是纯函数能力（URL 字符串变换，不联网、不需要引擎），存在性只由文件判定，`default_config` 里**不写** `canonical_url` 段。

## 加载与分发

`novelbase/source.py` 对外 API（`mode` 从**入参**变成**出参**）：

```python
list_sources() -> list[str]                     # source_name 列表
get_manifest(source_name) -> dict               # source.json 内容（show_name/enabled/default_config）
capabilities(source_name) -> dict[str, str]     # {"search": "api", "chapter_content": "browser"}
resolve(source_name, capability) -> tuple[Callable, str]   # (函数, 该能力的 mode)
```

- 加载方式：内置书源走 `import_module("novelbase.sources.{dir}.{capability}")`（目录名是合法标识符，保留空 `__init__.py`）。私有源（`NLD_PRIVATE_SOURCES`）维持 `spec_from_file_location`（`novelbase/source.py:298` 现有实现），因为它在包外。
- `CAPABILITY_META`（`novelbase/sources/contracts.py`）保留能力清单与必需参数，**去掉 `file_stem`**（能力名 = 文件名 = 函数名）。能力清单从 4 条增至 **5 条**：新增 `canonical_url`（`required_params: ("url",)`，见「URL 规范化」）。
- 运行时签名校验保留（`inspect.signature` 比对 `required_params`）。
- 删除 `platform_from_url()`（`novelbase/source.py:121`）与 `_scan_sources()` 里的 `NAME`/`SHOW_NAME`/`HOSTS` 约定——身份信息改由 `source.json` 提供。

`downloader` 侧：`novelbase/core/downloader.py` 四处 `_normalize_mode(engine)` / `_variant_for(engine)`（14-25 行，及 76-77、121-122、149-150、173-174 行的调用）**删除**。新签名：

```python
async def search(sources: Sequence[str], query: str, engines, **kwargs) -> list[SearchResult]
async def resolve_meta(url: str, source_name: str, engines, **kwargs) -> Novel
async def resolve_chapter_list(url: str, source_name: str, engines, **kwargs) -> Chapters
async def resolve_chapter(chapter, source_name: str, engines, **kwargs) -> Chapter | None
```

`engines` 是「按 mode 取引擎」的解析器（mapping 或 callable），由调用方按 `capabilities(source_name)` 里出现的 mode 集合**懒建并复用**。这样「一个书源的两个能力用不同 mode」是天然支持的，且不偏离就是单引擎，没有额外开销。

## 配置合并

三层，后者覆盖前者，沿用 `shared/config.py` 现成的 `deep_merge`：

1. **系统级默认**：`shared/config.py` 的 `ENGINE_DEFAULTS` / `GLOBAL_DEFAULTS`（最底层基底）
2. **书源出厂默认**：`source.json` 的 `default_config`
3. **用户层**：`app_data/config/sites/{source_name}.yaml`

> 措辞确认：讨论中「系统级优先」一语，本设计理解为「系统级在最底层当基底、被后两层覆盖」，**不是**「系统级压过用户配置」。

`shared/config.py` 中按 platform 的函数要改为按 `source_name`：

- `load_site_config(platform)` → `load_site_config(source_name)`（`config.py:132`）
- `save_site_config`（`:139`）、`load_platform_configs`（`:144`）、`load_platform_raw`（`:164`）、`load_mode_config(platform, mode, variant)`（`:188`）、`mode_variants`（`:194`）、`find_variant_options`（`:201`）

现有 `sites/fanqie.yaml` 的形态（`{api: {oiapi: {...}, rain: {...}}, browser: {default: {...}}, requests: {default: {...}}}`）与新「逐能力段」结构语义相近，可作为用户层字段的参考形状，但**旧文件不迁移**。

## 数据与兼容

| 数据 | 处理 |
|---|---|
| `app_data/config/sites/*.yaml` | **直接丢**（含 api key / headers / cookies），用户重配 |
| `search_history` 表 | **drop 重建**，新唯一键 `(source_name, keyword)`；删除 `shared/user_data.py:84-119` 的旧迁移与其 `platform='fanqie'` 硬编码 |
| 收藏 / 分组 / 书签 / 已下载书籍 | **不受影响**：全部按 `novel_id` 索引，`novel_id` 只依赖 `canonical_url` |
| `app_data/config/formats/*.yaml` | 不动 |

**硬约束（影响 `novel_id` 稳定性）**：`Novel.id = sha256(canonical_url)[:32]`（`novelbase/utils/urls.py:35`），而 `canonical_book_url(url, platform)` 含书源特例——`92xs` 的 `/book/{id}.html` ↔ `/html/{id}/` 归一、`qidian` 的 `/info/{id}/` → `/book/{id}/`（`urls.py:24-31`）。这些特例的实现**必须等价迁移**，否则所有已有书籍 id 变化，书架、收藏、分组、阅读进度、下载目录、已导出文件全部对不上。处置见「URL 规范化」一节。

模型改动：

- `Novel` 增加来源标记字段（`source_name: str = ""`，允许空）。空值表示「旧数据或来源未知」，前端提示用户选择书源。`Novel.loads(**kwargs)`（`novelbase/models/novel.py:298-308`）已有 `setattr` 兜底，旧 JSON 缺字段可正常加载。
- `SearchResult.platform: str`（`novelbase/models/novel.py:323`）改为 `source_name`。

## 后端改造

- 路由参数：`platform: str = Query(...)` → `source`（书源）；删除 `"fanqie" if platform == "all" else platform` 之类的 `all` 特例（`backend/routers/download.py:36`）。
- 搜索：并发跑**所有 `enabled` 书源**，结果合并并标注来源书源；不再是单 platform。
- `backend/services/engine_manager.py`：`_fingerprint(platform, mode, variant)` → 按 `source_name`（+ 能力所需的 mode）缓存；`create_engine_for_request` 改为按书源声明的 mode 建引擎。
- `backend/services/task_manager.py`：`_run_download(task, mode, variant, platform)`（`:26`）、任务字段 `_mode`/`_variant`/`_platform`（`:210`）改为 `_source`。
- `backend/routers/history.py`：`mode`/`variant` 字段与 `(platform, keyword, mode, variant)` 语义改为 `source_name`。
- `backend/routers/config.py`：站点配置端点从「按 mode/variant 树」改为「按书源」。

## CLI 改造

- `--platform` → `--source`；`search` 默认用全部启用书源并发。
- `cli/main.py:135`、`cli/interactive.py:38` 的 `_resolve(site_cfg, mode, variant)` 改为按书源建引擎。
- **`dev new-variant` 脚手架命令要重写**：它当前生成 `sources/{source}/{mode}/{variant}/` 结构并写 `sites/{source}.yaml`（见 `docs/superpowers/specs/2026-08-26-cli-dev-new-variant-design.md`），新结构下要改为生成「一层书源目录 + `source.json` + 4 个能力文件」。相关测试 `tests/test_cli_dev_new_variant.py`、`tests/test_cli_variant.py` 一并重写。

## 前端改造

前端的「mode/variant 两级选择器」是**删除**，不是改造：

- `features/bookshelf/SearchBar.tsx:77-88`（mode 切换 + variant 徽标 + 「多 variant 未选则抖动拦截」）→ 删除；搜索改用「已启用书源」并发。
- `features/download/DownloadDialog.tsx:12-110`（`availableModes` + `variantsByMode` 两排选择器）→ 删除，下载对话框不再询问 mode。
- `features/detail/DetailPage.tsx:237-322,489`（`runDownload(mode, variant)`）→ 改为只带 `source_name`。
- `features/settings/SettingsPage.tsx:242-261`（`ApiVariantsSection`，按 variant 编辑配置）→ 改为按书源编辑配置。
- `api/endpoints.ts`（四处请求的 `mode`/`variant` query 参数）、`utils/sessionCache.ts:4-30`（`nd:variant`）、`hooks/index.ts:135-302`（queryKey 含 mode/variant）→ 全部改为 `source_name`。
- `SearchHistoryPanel.tsx`：历史条目显示书源而非 mode/variant 徽标。

**新增**：书源管理界面（列表 + 启用/禁用 + 编辑该书的配置），因为 `enabled` 与用户层配置需要一个入口。

**URL 解析入口**（`hosts` 消失后的缺口）：直接粘贴 URL 时**由用户选择一个书源**。这是本设计采用的默认方案，因为「自动匹配书源」需要书源自己声明 URL 模式（见未决事项 1）。若日后补齐 URL 模式声明，可升级为自动匹配。

## 测试

- `tests/test_source_contracts.py`：重写。新结构下的能力发现、`resolve` 返回 `(fn, mode)`、签名校验、`CAPABILITY_META` 一致性。
- 新增 `source.json` 校验测试：能力段 ⇔ `.py` 文件一致性（双向）、字段按 mode 的合法性、`source_name` 唯一性。
- **新增 URL 规范化等价性测试**：对 `92xs` / `qidian` 的典型 URL 覆盖（`/book/{id}.html`、`/html/{id}/`、`/info/{id}/`、带 query/fragment/尾斜杠等变体），断言迁移后 `Novel.id` 与迁移前逐一致——这是防 `novel_id` 漂移的兜底。
- 私有源（`NLD_PRIVATE_SOURCES`）测试按新结构改写。
- `tests/check_imports.py`：更新 `list_sources()` 输出断言。
- 受波及需同步改写的测试：`test_cli_dev_new_variant.py`、`test_cli_variant.py`、`test_downloader.py`、`test_site_config.py`、`test_shared_user_data.py`、`test_browser_sources.py`。
- 回归基线：当前 `python -m pytest tests/ -q` = **317 passed, 2 skipped**（`AGENTS.md` 里写的「152 passed」已过期）。

## URL 规范化（已定：能力化）

`canonical_book_url(url, platform)`（`novelbase/utils/urls.py:8-32`）里的书源特例**搬到书源侧的 `canonical_url.py`**（新增第 5 种能力）：

- `CAPABILITY_META` 新增一条：`"canonical_url": {"required_params": ("url",)}`
- 需要特例的书源各带一份：`92xs-requests-default`、`qidian-browser-default`、`qidian-requests-default`（同一平台的多个书源各自带一份——「每书源独立」）
- 无特例的书源（`fanqie` / `qimao` 的 7 个）**不写该文件**，走 core 的通用规则（`canonical_book_url` 去掉 `platform` 参数、去掉特例分支后的部分）
- 它是纯函数能力：不联网、不需要 engine，`default_config` 里**不写** `canonical_url` 段（见「source.json 规范」规则 6）
- 调用点：`resolve_meta` 生成 `Novel.id` 之前，按 `resolve(source_name, "canonical_url")` 取函数；取不到则用 core 通用规则

**硬约束**：`92xs` 的 `/book/{id}.html` ↔ `/html/{id}/` 归一、`qidian` 的 `/info/{id}/` → `/book/{id}/` 必须**逐字符等价**迁移，否则 `novel_id` 漂移（见「数据与兼容」）。等价性要有测试兜底。

## 未决事项

1. **URL 解析的自动匹配**：若要让「粘贴 URL」自动判断该用哪个书源，需要书源声明「这个 URL 是否属于我」的模式。`canonical_url.py` 里的正则只管「归一」、不等于「归属判定」，且只覆盖有特例的 3 个书源，所以不能直接复用。补齐前，URL 解析由用户手选书源（见「前端改造」）。

## 风险

- **`novel_id` 漂移**：URL 规范化迁移不等价 → 已有书籍全部对不上。缓解：迁移前后对 `92xs` / `qidian` 的典型 URL 做等价性测试。
- **一次性切换无兼容层**：`sources/` 结构、配置、数据库、前端同时变，任何一个没跟上都是运行时崩溃。缓解：按「core → 书源 → 后端 → CLI → 前端」顺序推进，每步跑测试。
- **`enabled` 默认值**：10 个书源若出厂全 `enabled: true`，用户首次搜索会并发 10 个书源（含需要 api key 的）。需要定出厂默认（建议 api 类默认 false，requests/browser 默认 true）。
- **public 仓库同步**：`PUBLIC_MANIFEST.md` 的白名单迁移（`novel-crawler`）要跟着重写，书源路径全部变化；`api` 书源（oiapi/rain）仍不得进 public。

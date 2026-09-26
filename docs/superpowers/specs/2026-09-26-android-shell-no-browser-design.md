# Android 套壳定位 —— 前端交付修复 + 环境能力表（不支持 browser）设计

> ⚠️ **已作废（2026-09-26 起）**：Android 套壳与本设计描述的「环境能力表」已一并移除，移动端改走 Termux。本文仅作历史记录。

> 2026-09-26。APK 是**套壳**（WebView 加载内嵌 FastAPI 提供的 SPA + Chaquopy 跑 Python 后端，无任何原生下载/解析实现），因此**本环境不支持 `browser` 引擎**。
> 本设计做两件事：① 修掉真机白页（前端从未被 APK 正确交付）；② 把「Android 不支持 browser」落成一条**环境能力表**，贯穿 core → 后端 → 前端。

## 1. 背景

用户在真机安装 APK 后，WebView 显示的是后端的「前端尚未构建」提示页：

```
📖 novel-downloader
API 服务已启动（localhost:8000）
前端尚未构建。运行以下命令后刷新页面：
cd frontend && npm run build
```

（`localhost:8000` 只是 `backend/main.py:131` 的硬编码文案；实际服务监听 `127.0.0.1:18080`。）

同一 APK 上还有第二个悬而未决的问题：`playwright` 在 `build-apk.sh` 里被从依赖清单剔除（`grep -v -E "^(playwright|psutil|pillow-heif)"`），但**没有任何一层知道「本环境不支持 browser」**——3 个 browser 书源出厂 `enabled=true`，会被 `enabled_source_names()` 当启用书源收进搜索并发（`backend/routers/download.py:86`），用户也能在设置页把任一能力 `mode` 覆盖成 `browser`，选了必然失败。

## 2. 现状调查（2026-09-26 实测）

### 2.1 白页的直接原因：前端产物目录层级不一致

`backend/main.py:91-107` 的 `_find_frontend_dist()` 只认一个约定：

| 发行形态 | 前端落点 | `_project_root/frontend/dist` 是否命中 |
|---|---|---|
| portable | `dist/portable/frontend/dist/{assets,index.html,…}`（`scripts/build-portable.sh:127-128`） | ✅ |
| Nuitka | `--include-data-dir=frontend/dist=frontend/dist`（`scripts/build-nuitka.sh:100`） | ✅ |
| **APK** | `android/scripts/build-apk.sh:36-37`：`cp -r ../frontend/dist/* app/src/main/python/frontend/` | ❌ **少了 `dist` 这一层** |

本机用等价布局复现（把 `backend/ shared/ init_config.py template/ server.py` 复制进临时目录、`frontend/` 只放 `index.html`）：

```
_frontend 解析为 : None
/                -> 200  <!DOCTYPE html> …<title>novel-downloader</title>   ← 与真机截图一致
```

同一布局把产物放到 `frontend/dist/` 后：

```
_frontend = …\frontend\dist
/                     -> 200 text/html
/novels（SPA 路由）    -> 200 text/html
/assets/index-*.js    -> 200 application/javascript
/api/v2/health        -> 200 application/json
```

### 2.2 更深的原因：Chaquopy 里 `src/main/python/` 不是真实文件系统

Chaquopy 把源码目录打成 APK 资产（`.imy`/zip），`.py` 走自定义 import hook，数据文件**按需提取、不支持目录列举**（`os.listdir`/`os.scandir` 失败，见 [chaquopy#745](https://github.com/chaquo/chaquopy/issues/745)、[Asset Management](https://deepwiki.com/chaquo/chaquopy/3.2-asset-management)）。官方推荐姿势只有一条：**用 `__file__` 相对路径读单个文件**（[FAQ - Read files in Python](https://chaquo.com/chaquopy/doc/16.0/faq.html#faq-read)）。

而现有实现依赖两处「真实目录」假设：

- `backend/main.py:100-103`：`if (p / "index.html").exists()` 决定 `_frontend` 是否有效
- `backend/main.py:111`：`app.mount("/assets", StaticFiles(directory=str(_frontend / "assets")))`（`StaticFiles` 需要 `os.scandir`）

`android/app/src/main/python/server.py:61-65` 的兜底挂载（`app.mount("/", StaticFiles(...))`）**是死代码**：它注册 `backend/main.py` 的 catch-all（`:114` `@app.get("/{full_path:path}")`）**之后**，Starlette 按注册顺序匹配 → 永不命中；它指向的 `frontend/` 也不是约定路径。实测佐证：给该目录放一个内容为 `SHELL-OK` 的 index.html，`/` 返回的仍是 `_frontend` 的 index.html（当时 `_frontend` 因实验 `sys.path` 顺序命中了仓库真实 dist）。

因此结论是：**APK 的前端资源交付机制从未被正确设计/验证**，而 `tests/test_android_server.py:57-77` 只断言「存在根 mount」（`r.path in ("/","")`，且用的是旧路径 `src/main/assets/frontend`），从不验证「根路径真的返回前端」→ CI 全绿、真机白页。

### 2.3 前端产物体积

`frontend/dist` = **5 个文件 / 600 KB**（`index.html`、`assets/index-*.js`、`assets/index-*.css`、`favicon.svg`、`icons.svg`）——小到可以直接打成一个 zip 交付。

### 2.4 涉及的既有出口（能力表落点）

| 位置 | 现状 |
|---|---|
| `shared/config.py:202` | `VALID_MODES = ("browser", "requests", "api")` |
| `shared/config.py:205-221` | `effective_capabilities()`：`override if override in VALID_MODES else mode` |
| `shared/config.py:288-291` | `enabled_source_names()`：`is_source_enabled` 过滤（**不含可用性**） |
| `backend/routers/download.py:86` | 搜索并发 `enabled_source_names()` |
| `backend/routers/download.py:178-183` | `GET /download/sources` → `{name: {capabilities, enabled}}` |
| `backend/routers/config.py:87-105` | `GET /config/sources/{name}` → `capabilities` / `declared_capabilities` / `config` |
| `backend/routers/config.py:107-141` | `PUT /config/sources/{name}`（写用户层 yaml） |
| `backend/services/source_guard.py` | **唯一** HTTP 边界校验点（`require_known_source` → 404） |
| `frontend/src/api/endpoints.ts:226` | `useSources()` 类型 `{capabilities, enabled}` |
| `frontend/src/api/endpoints.ts:235-241` | 响应 → 选源列表（未启用的源仍列出，仅 UI 标注） |
| `frontend/src/features/sources/sourceConfigForm.tsx:187` | mode 下拉 = `Object.entries(MODE_META)`（恒有三个 mode） |
| `frontend/src/features/sources/SourceAccordion.tsx:9` | 折叠条 props `{capabilities, enabled}` |

## 3. 已拍板决策（用户，2026-09-26）

| # | 决策点 | 选择 |
|---|---|---|
| D1 | 触发点 | **实机白页**（前端未显示）+ 定位要求「APK = 套壳、不支持 browser」 |
| D2 | 「不支持 browser」落点 | **环境能力表**，贯穿 core → 后端 → 前端（含 API/前端出口） |
| D3 | browser 书源可见性 | **设置页仍列出并置灰 + 标注「本环境不支持 browser」**；搜索/选源/下载入口不出现（选不了） |
| D4 | 用户 yaml 里已存在的 browser 覆盖 | **忽略覆盖、回退书源声明的 mode**（yaml 保留不动，回桌面版自动生效） |
| D5 | APK 前端交付方式 | **构建期把 `frontend/dist` 打成单个 zip；Python 启动时解压到可写目录**，复用现有 `StaticFiles` + SPA fallback |

## 4. 目标

1. 真机 APK 的 WebView 加载到真实前端（根路径返回 `index.html` 而非占位页），且 SPA 路由与 `/assets/*` 正常。
2. Android 环境下 `browser` 不再是可用选项：不进启用集、不被搜索/下载/CLI 触碰、不能通过配置启用或覆盖、前端不提供选择。
3. 桌面 / portable / Nuitka / CLI 行为**逐字不变**（`NLD_PLATFORM` 未设即今天的行为）。
4. 白页这类「CI 绿、真机坏」的问题有**本机可跑的端到端测试**兜底。

## 5. 非目标（YAGNI）

- 不做「物理探测 + 自动降级」（如探测 `playwright` 是否安装来推导可用 mode）。能力表由**环境声明**驱动（D2）；core 只负责把「漏网」变成明确异常（见 6.2.4）。
- 不引入 Android 原生下载/解析实现（套壳定位）。
- 不改 `Novel.id` / URL 契约 / 存储结构 / 并发模型。
- 不为 `browser` 书源做「自动换源到 requests 变体」之类的跨源替换——用户换源列表里仍可手选可用的源（只是 browser 源不再出现）。
- 不新增前端单测基建（项目现无 vitest；前端验证 = `npx tsc -b` + `npm run lint`）。

## 6. 设计

### 6.1 A：APK 前端资源交付

#### 6.1.1 构建期（`android/scripts/build-apk.sh`）

- 删掉 `:36-37` 的两行（`mkdir -p app/src/main/python/frontend` + `cp -r ../frontend/dist/* app/src/main/python/frontend/`），以及 `:28` 清理列表里的 `app/src/main/python/frontend`（改为 `frontend.zip`）。
- 新增：前端构建完成后，用 `python3` + 标准库 `zipfile` 生成 `android/app/src/main/python/frontend.zip`，zip 内路径相对 `frontend/dist` 根（`index.html` 在根，不打 `dist/` 前缀），`ZIP_DEFLATED`。
- `.gitignore`：把现有 `android/app/src/main/python/frontend/` 一行替换为 `android/app/src/main/python/frontend.zip`（不再有目录副本）。

#### 6.1.2 运行时（`android/app/src/main/python/server.py`）

新增 `_extract_frontend()`，**在 `from backend.main import app` 之前**调用（后端定位前端发生在其模块级）：

1. zip 路径 = `Path(__file__).resolve().parent / "frontend.zip"`；不存在 → `print` 一条明确 error 日志并返回（前端回落到占位页，但日志可定位）。
2. 目标目录 = `Path(os.environ["HOME"]) / "frontend" / "dist"`（App 私有目录，Chaquopy FAQ 指定的可写位置）；`HOME` 缺失时回退 `Path(os.environ["NLD_APP_DATA"]) / ".frontend" / "dist"`（本机测试/异常兜底）。
3. **幂等**：目标目录内写 `.zip-sha256` 标记；与当前 zip 的 sha256 一致 → 跳过解压（省掉每次启动的 600 KB 解压）。
4. **安全**：逐个成员校验——拒绝绝对路径、`..` 组件、以及解析后落在目标目录之外的成员（zip slip 防护）。
5. 成功后设置 `os.environ["NLD_FRONTEND_DIR"] = str(target)`。**若该 env 已由外部设定且其下存在 `index.html`，直接采用、不覆盖、不解压**（保留「外部显式指定前端目录」这一能力，也方便本机联调）。

同时删除 `:61-65` 的死代码挂载（`app.mount("/", StaticFiles(...))` 与 `assets/frontend` 旧兼容路径），并把模块 docstring 里「挂载前端」的描述改为「解压前端资源并交给 `backend.main` 的 SPA fallback 统一服务」。

#### 6.1.3 定位契约（`backend/main.py`）

`_find_frontend_dist()` 增加**第一候选**：`os.environ.get("NLD_FRONTEND_DIR")`（仍要求其下存在 `index.html`）。其余候选与顺序**一律不动** → 桌面 / portable / Nuitka 零变化。

同时把候选列表抽成纯函数 `_frontend_candidates() -> list[Path]`（`_find_frontend_dist()` = 取第一个 `index.html` 存在的候选）——只为让测试能直接断言候选（见 8.1 的负例，本地仓库根存在真实 `frontend/dist`，不抽函数就无法构造「候选全落空」）。

### 6.2 B：环境能力表

#### 6.2.1 环境声明（唯一真源，`shared/config.py`）

- 新增 `platform() -> str`：读 `NLD_PLATFORM`，`"android"` → 返回 `"android"`，其余/未设 → `"desktop"`。
- 新增 `ANDROID_MODES = ("requests", "api")` 与 `supported_modes() -> tuple[str, ...]`：`platform() == "android"` → `ANDROID_MODES`，否则 `VALID_MODES`（全量 → 桌面行为不变）。
- `android/app/src/main/python/server.py` 注入 `os.environ.setdefault("NLD_PLATFORM", "android")`（模块级，与 `NLD_APP_DATA` 注入同处）。

#### 6.2.2 有效能力与可用性（`shared/config.py`）

- `effective_capabilities()`（`:205-221`）覆盖判定收紧为：`override if override in supported_modes() else mode` → Android 上 `browser` 覆盖被忽略、回退书源声明（D4；yaml 内容不动）。
- 新增 `available_capabilities(source_name) -> dict[str, str]`：`effective_capabilities()` 中 mode ∈ `supported_modes()` 的条目（未知书源 → `{}`）。
- 新增 `is_source_available(source_name) -> bool`：**源级、全能力**判定 —— `available_capabilities()` 的键集合 == `effective_capabilities()` 的键集合（即没有任何能力被本环境排除）。未知书源 → `False`。
  - 为什么是「全能力」而非「至少一个」：混合 mode 的源（只可能出现在私有源）在 Android 上会变成「半可用」，而执行路径（`engine_manager._capability_for_mode()` 按 mode 反查能力段、core 按能力分发）会踩到那个不可用的能力 → 整源判不可用比「静默半工作」安全。内置 10 个书源全是单一 mode，不受此选择影响。
- `enabled_source_names()`（`:288-291`）追加过滤：`is_source_enabled(n) and is_source_available(n)` → Android 上 `fanqie-browser-default` / `qidian-browser-default` / `qimao-browser-default`（4 个能力全 browser）不进启用集，搜索/下载/CLI 的自动路径因此自动跳过它们。

#### 6.2.3 后端出口

- `GET /download/sources`（`download.py:178-183`）：每源增加 `"available": bool`。**源仍全量返回**（D3 要求设置页能列出并置灰）。
- `GET /config/sources/{name}`（`config.py:87-105`）：增加 `"available": bool`。
- 新增 `GET /api/v2/config/environment` → `{"platform": "desktop"|"android", "supported_modes": [...]}`（前端 mode 下拉的数据源）。
- `PUT /config/sources/{name}`（`config.py:107-141`）新增校验：
  - `enabled: true` 且 `is_source_available(name)` 为假 → 400，message 说明本环境不支持其所需引擎。
  - `config[cap].mode` 取值 ∉ `supported_modes()` → 400（同理）。
  - 其余写入路径不变（`enabled: false` 永远允许；`mode: null` 永远允许）。
- `source_guard.py`（**唯一**校验点，保持这一约定）新增 `require_available_source(source_name)`：源不可用 → 400 + 明确 message（风格与既有 `require_known_source` 一致）。应用于**执行/写**入口：
  - `download.py:55` `_require_source`（URL 直达分支）与 `download.py:68` 的单源关键字搜索分支
  - 创建下载任务的路由（按 `source_name` 取参处）
  - `PUT /config/sources/{name}` 的 `enabled: true` 与 `mode` 覆盖分支
  **GET 配置读取照旧放行**（否则无法置灰展示，D3）。
- 搜索并发（`download.py:86`）无需改动：`enabled_source_names()` 已在 6.2.2 过滤。

#### 6.2.4 core 层（`novelbase/`）

- `novelbase/core/exceptions.py` 新增 `ModeUnavailableError(NovelDownloaderError)`，构造 `(mode: str, reason: str | None = None)`；与既有 `FeatureNotSupportedError` 语义区分（前者=引擎依赖/本环境不可用，后者=功能在该 mode 下不支持）。
- `novelbase/core/engine.py`：`_async_playwright()`（`:20-22`）与 `:472` 同步路径的 `import playwright` 失败（`ImportError`/`ModuleNotFoundError`）包成 `ModeUnavailableError("browser", …)`；`BrowserEngine` 启动处（`:309` 一带）同样兜底 → 漏网时得到明确异常而非裸 `ImportError`。
- **不新增 `downloader.py` 的 mode 参数校验**：`novelbase/core/downloader.py` 的 4 个函数只接受调用方给的 `engines(mode)` 解析器，core 若要知道「可用 mode 表」就得读环境或加参数，破坏「core 不承载环境/站点知识」的既有边界。校验由上层的 `supported_modes()` + `source_guard` 负责（声明层），core 只保证**声明的漏网**有明确语义（异常层）。

#### 6.2.5 前端（`frontend/src/`）

| 位置 | 改动 |
|---|---|
| `api/endpoints.ts:226` | `useSources()` 返回类型加 `available: boolean` |
| `api/endpoints.ts:235-241` | 响应 → 选源列表时**过滤** `available === false`（搜索页 / 详情换源 `SourcePickerDialog` / 书架共用此函数） |
| `api/endpoints.ts`（新增） | `getEnvironment()` → `{platform, supported_modes}` |
| `hooks/index.ts` | 新增 `useEnvironment()`（react-query，`staleTime` 长：环境在一次运行内不变） |
| `features/sources/sourceConfigForm.tsx:187` | mode 下拉选项 = `supported_modes`（来自 `useEnvironment()`）而非 `Object.entries(MODE_META)`；`ENGINE_FIELDS` 仍按 mode 取字段 |
| `features/sources/SourceAccordion.tsx:9` | props 加 `available`：`false` → 折叠条置灰 + 标注「本环境不支持 browser」+ 禁用 `enabled` 开关（已启用则为只读展示） |
| `features/settings/SettingsPage.tsx` | 透传 `available`（列表来源 `useSources()` 不变 → browser 源仍列出） |

#### 6.2.6 CLI

桌面行为不变。`cli/main.py`、`cli/interactive.py` 的显式 `--source <name>` 分支：若该源不可用 → 打印明确错误并退出（而非跑到引擎层 `ImportError`）。`enabled_source_names()` 的自动路径已由 6.2.2 覆盖。

> **实施说明（2026-09-26）**：该预校验**未实现**——`NLD_PLATFORM` 只由 APK 的 `server.py` 注入，而 APK 内没有 CLI；桌面 `supported_modes()` 是全量，因此 CLI 里的可用性预校验**恒不触发**（写了即死代码）。CLI 显式指定不可用源时的明确错误由 core 兜底（`ModeUnavailableError`，中文说明），已满足本节的实质目标。详见 §12。

### 6.3 数据流

```
构建期： frontend/dist ──zipfile──> src/main/python/frontend.zip (APK 资产)
启动：   server.py: NLD_PLATFORM=android
                     frontend.zip ──解压──> $HOME/frontend/dist ──> NLD_FRONTEND_DIR
                     └─> import backend.main
后端：   _find_frontend_dist(): [NLD_FRONTEND_DIR] → …（其余不变） → StaticFiles + SPA fallback
环境：   NLD_PLATFORM ──> supported_modes()
                          ├─> effective_capabilities()（忽略不可用覆盖）
                          ├─> available_capabilities()/is_source_available()
                          │     └─> enabled_source_names() → 搜索/下载/CLI
                          ├─> GET /config/environment ─> 前端 mode 下拉
                          └─> source_guard.require_available_source() → 400
```

### 6.4 错误处理

| 场景 | 行为 |
|---|---|
| `frontend.zip` 缺失 / 解压失败 / 校验不过 | `server.py` 打 error 日志，不设 `NLD_FRONTEND_DIR` → 前端回落现有占位页（保持可诊断，不静默） |
| zip 成员路径穿越 | 跳过该成员（打 warning），解压继续 |
| 显式指定不可用源（API/CLI） | 400 + message / CLI 明确报错退出 |
| 用户 yaml 里有 browser 覆盖（Android） | 静默回退声明 mode（yaml 不动），不报错 |
| 源所有能力都不可用 | 不进启用集（搜索/下载/CLI 自动跳过），但仍在 `GET /download/sources` 与设置页出现且 `available=false` |
| 漏网走到 browser 引擎 | core 抛 `ModeUnavailableError`（带 mode 与原因），不再裸 `ImportError` |

## 7. 涉及文件

**Android / 构建**
- `android/scripts/build-apk.sh`（zip 生成、删旧复制、清理列表）
- `android/app/src/main/python/server.py`（`NLD_PLATFORM` 注入、`_extract_frontend()`、删死挂载、docstring）
- `.gitignore`（`frontend.zip`）

**后端 / core / 配置**
- `backend/main.py`（`NLD_FRONTEND_DIR` 第一候选）
- `backend/routers/config.py`（`available`、`/environment`、PUT 校验）
- `backend/routers/download.py`（`available`）
- `backend/services/source_guard.py`（`require_available_source`）
- `shared/config.py`（`platform()`、`ANDROID_MODES`、`supported_modes()`、`available_capabilities()`、`is_source_available()`、`effective_capabilities()` 收紧、`enabled_source_names()` 过滤）
- `novelbase/core/exceptions.py`、`novelbase/core/engine.py`

**前端**
- `frontend/src/api/endpoints.ts`、`frontend/src/hooks/index.ts`
- `frontend/src/features/sources/{sourceConfigForm.tsx,SourceAccordion.tsx}`
- `frontend/src/features/settings/SettingsPage.tsx`

**测试 / 文档**
- `tests/test_android_server.py`（重写挂载断言 → 端到端）
- 新增 `tests/test_source_availability.py`（能力表 / 可用性 / API 校验）
- `docs/build/android-apk.md`、`docs/project/sources.md`、`docs/session-prompt.md`（追平约定）

## 8. 测试

### 8.1 Android 前端交付（`tests/test_android_server.py` 重写）

- **端到端**（用 `httpx.ASGITransport`，绕开既有 `TestClient` lifespan 挂起问题）：
  - 设置 `NLD_FRONTEND_DIR` 指向含真实 `index.html` + `assets/x.js` 的临时目录 → `GET /` 返回该 index.html（**断言不再是占位页**）、`GET /assets/x.js` 200、SPA 路由 `/novels` 回 index.html、`/api/v2/health` 200。
  - 未设 `NLD_FRONTEND_DIR` 且无前端 → `GET /` 返回占位页（负例，保证测试能区分两者）。
    ⚠️ 负例不能靠「删目录」制造：本地仓库根**确实存在** `frontend/dist`，会让 `_project_root` / `Path.cwd()` 候选命中。做法：① 直接对 `_frontend_candidates()`（6.1.3 抽出的纯函数）断言「候选全部不存在 → `_find_frontend_dist()` 返回 `None`」；② 再配一个用例：清 `sys.modules` 缓存、`chdir` 到空临时目录、并 monkeypatch `backend.main._project_root` 与 `NLD_FRONTEND_DIR` 指向该临时目录后再 import → `GET /` 返回占位页（沿用现有测试的 `sys.modules.pop` 手法）。
- zip 解压：构造 zip → `_extract_frontend()` → 目标目录内容正确、`NLD_FRONTEND_DIR` 已设；二次调用命中 sha256 标记不重复解压；含 `../evil` 成员的 zip 不写出目标目录之外。
- 删除 `test_server_module_has_app_with_static_mount`（断言死代码）与旧 `assets/frontend` 路径依赖；保留 env 注入与兜底用例。

### 8.2 环境能力表（新增 `tests/test_source_availability.py`）

- `supported_modes()`：未设 `NLD_PLATFORM` → 3 个 mode；`=android` → `("requests","api")`；非法值 → 全量（桌面）。
- `effective_capabilities()`：`=android` 下把 `fanqie-requests-default` 的 `search.mode` 覆盖成 `browser` → 仍返回 `requests`；未设 env 时同配置 → 返回 `browser`（桌面回归）。
- `is_source_available()` / `enabled_source_names()`：`=android` 下 3 个 browser 源被排除、requests 源保留；未设 env 时三者都在（桌面回归）。
- API：`GET /download/sources` 含 `available` 且 browser 源为 `false`；`GET /config/sources/{browser源}` 200 且 `available=false`；`PUT enabled=true` → 400；`PUT mode=browser` → 400；`GET /config/environment` 形状正确。
- core：`BrowserEngine` 在 `playwright` 不可用时抛 `ModeUnavailableError`（用 monkeypatch 让 import 失败）。

### 8.3 回归与验证命令

- `python -m pytest tests -q`（基线 **471 passed / 1 skipped**，必须全绿）
- `cd frontend && npx tsc -b`（0 错；`tsconfig.json` 是 solution 风格，`--noEmit` 会空转）、`npm run lint`（0 告警）
- 本机模拟 APK：构造 `frontend.zip` + `HOME`/`NLD_APP_DATA` + `NLD_PLATFORM=android`，起服务断言 `/` 为前端、`/config/environment` 与 `available` 正确（即 8.1/8.2 的组合场景）

## 9. 风险与硬约束

- **不得改变桌面行为**：`NLD_PLATFORM` 未设时，`supported_modes()` = 全量、`effective_capabilities()` 语义与今天一致、`_find_frontend_dist()` 候选顺序不变。这是本次改动的第一硬约束。
- **`NLD_PLATFORM` 的语义边界**：它声明的是「运行环境」，不由用户配置面板暴露；桌面误设会改变可选 mode（文档中注明仅 Android/测试使用）。
- **Chaquopy 行为无法本机验证**：`HOME` 可写、zip 解压、真机启动链路只能真机确认（见 10）。本机可验证的是「给定解压后的真实目录，后端一定能服务前端」这一段。
- **zip 解压是启动关键路径**：600 KB 解压在真机上应 <<1s；用 sha256 标记避免每次启动重复解压。解压失败不阻塞后端启动（回落到占位页 + 日志）。
- **能力表是「声明」，不保证书源真能用**：Android 上 `requests`/`api` 的具体可用性仍取决于站点与网络；本设计只解决「必然失败的 browser」。

## 10. 验收（手工）与遗留

**本机可验收**：8.3 的三条命令 + 8.1/8.2 的测试通过。

**真机验收（需用户执行，无法本机验证）**：
1. 授权后 dispatch `build-apk.yml`（`ref=dev`）→ 安装 APK；
2. WebView 显示真实前端 UI（不再是占位页），能搜索、能进设置；
3. 设置页能看到 `fanqie-browser-default` / `qidian-browser-default` / `qimao-browser-default` 置灰 + 标注「本环境不支持 browser」，开关不可点；
4. 搜索只命中可用书源；模式下拉不含 Browser。

**遗留（本次不做，如实记录）**：APK 仍未签名（未配置 `KEYSTORE_*` secrets，仅可侧载）；`versionName` 仍是 gradle 硬编码（public `1.0.1` / private `1.0.0`）；`buildPython 3.12.3` 与 app Python 3.11 不匹配导致 `.pyc` 预编译被跳过。

## 11. 参考

- `docs/build/android-apk.md`（现状：架构、`build-apk.sh` 职责、遗留清单）
- `docs/project/sources.md`（书源结构、`source.json` 规范、`concurrency` 与 mode 覆盖）
- [chaquopy#745](https://github.com/chaquo/chaquopy/issues/745)、[Asset Management](https://deepwiki.com/chaquo/chaquopy/3.2-asset-management)、[FAQ - Read files in Python](https://chaquo.com/chaquopy/doc/16.0/faq.html#faq-read)（Chaquopy 数据文件访问语义）
- `docs/superpowers/specs/2026-09-25-flattening-closeout-design.md`（`source_guard` 唯一校验点、前端书源配置合并的既有决策）

## 12. 实施记录（2026-09-26）

已按本文实施并推送 `dev`：`372d95f`（前端 zip 交付）→ `6419ed9`（环境能力表）→ `810c8b5`（前端）→ `b414856`（文档）→ `b1ffb66`（APK 构建修复）→ `982900b`（版本号 4.5.0）。

验证：`python -m pytest tests -q` = **507 passed / 0 failed**（基线 471）；前端 `npx tsc -b` 0 错、`npm run lint`（oxlint）0 告警；APK 构建 run `36240821327` **success**（artifact `novel-downloader-apk-4.5.0` ≈28.6 MB，未签名）。另做两轮本机等价演练（其中一轮只把「APK 内运行时目录」加入 `sys.path`，等价 Chaquopy srcDir）：`/` 返回真实前端、SPA 与 assets 正常、`platform=android`、browser 源 `available=False`。

### 12.1 与本文设计的两处偏差（如实记录）

1. **6.2.6 的 CLI 预校验未实现**：`NLD_PLATFORM` 只由 APK 的 `server.py` 注入，而 APK 内没有 CLI；桌面 `supported_modes()` 是全量 → CLI 里的可用性预校验**恒不触发**（写进去就是死代码）。CLI 显式指定不可用源时的明确错误由 core 兜底（`cli/core.py::_get_engine` → `create_engine` → 引擎启动时 `ModeUnavailableError`，中文说明而非裸 `ImportError`），已满足该节的实质目标；`enabled_source_names()` 的自动路径照常受可用性过滤。
2. **新增范围：APK 构建修复**（本文未预见）：dispatch 构建时发现本仓库 `build-apk.yml` **从未成功过** —— `pip { install("file:../..") }` 会让 pip 解析 `novelbase` 的 `dependencies`（含被清单刻意排除的 `playwright`）→ `generateReleasePythonRequirements` 必失败。改为与 `backend/`、`shared/` 同法复制 `../novelbase` 源码（依赖仍由 `.req-android.txt` 提供，与 `pyproject.toml.dependencies` 同源）。详见 `docs/build/android-apk.md` 与 `docs/build/pitfalls.md` ⑨。

### 12.2 本次未覆盖、留给真机验证的点

- 真机链路：`HOME` 可写 → 解压 → WebView 显示前端 → browser 源置灰。
- **`list_sources()` 在真机上的书源目录遍历**：它需要枚举 `sources/{dir}/source.json`，而 Chaquopy 资产不支持目录列举 —— 与前端白页同一类根因，本次未验证，若真机表现为「书源列表为空」则需按同样思路处理（例如构建期生成书源清单随资产分发）。

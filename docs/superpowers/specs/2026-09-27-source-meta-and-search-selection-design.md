# 书源元信息（分组/别名）与按选择搜索 —— 设计

> 2026-09-27。两件互相咬合的事一起做：① 书源设置页去掉「启用」概念，改为维护**分组**与**别名**，界面用别名代替 `source_name` 展示；② 搜索页把「并发全部源」改成**用户可选源**（单选「全选/分组」+ 逐源复选），URL 直达的单选按分组分节。
> 之所以合并成一份 spec：两者共用同一套新字段（`source_group` / `source_alias`），分别做会二次改动同一批文件与 API。

## 1. 背景

- 现在「某个书源参不参与」只由 `enabled` 表达：`source.json` 的出厂 `enabled` + 用户层 `sites/*.yaml` 顶层覆盖，界面把它做成折叠条顶部的开关。用户要求**彻底去掉 `enabled`**，改由「搜索时勾选哪些源」直接表达意图。
- 界面与日志统一显示 `source_name`（如 `fanqie-requests-default`），用户希望显示可读的**别名**，并希望按**分组**归类（10 个内置源里同平台有 2~3 个变体，平铺很乱）。
- 搜索页现在没有源选择：标题搜索固定「并发全部已启用书源」，URL 直达只有一个平铺 `Select`。

## 2. 现状调查（2026-09-26 实测）

| 事实 | 证据 |
|---|---|
| `enabled` 是 `source.json` 的**必填**字段 | `novelbase/sources/manifest.py:14` `IDENTITY_FIELDS = ("source_name", "enabled")`，`:53` 校验必须为 bool |
| 10 个内置源都写了 `enabled`（api 类为 `false`） | `novelbase/sources/*/source.json` 第 3 行 |
| 用户层顶层 `enabled` 覆盖出厂值 | `shared/config.py:253-259` `is_source_enabled()` |
| 「启用集」= 出厂/用户 `enabled` 的源，**无其它过滤** | `shared/config.py:288-294` `enabled_source_names()`（曾于 2026-09-26 叠加过环境能力表过滤，随 v4.5.1 移除 Android 套壳一并删掉） |
| 模板与脚手架也写 `enabled` | `template/config/sites/*.yaml` 第 1 行；`cli/main.py:382/390/394`（`dev new-source`） |
| 后端两处出口带 `enabled` | `backend/routers/config.py:98`（GET）、`:116-117`（PUT）；`backend/routers/download.py:183`（`/download/sources`） |
| 搜索只支持「全部启用源」或「单源」 | `backend/routers/download.py:87`（`enabled_source_names()`）、`:67-68`（单源 `source` Query） |
| CLI 三处依赖 | `cli/main.py:124-126`、`cli/interactive.py:13/56/84`、`cli/menus.py:11/86/110-111`（**交互式菜单里也有启用开关**） |
| 前端四处依赖 | `frontend/src/api/endpoints.ts:228/238/245`（`SourceInfo.enabled` / `SourceOption.enabled` / `toSourceOptions`）、`features/bookshelf/SearchBar.tsx:136`（「未启用」标注）、`features/detail/SourcePickerDialog.tsx:41/52`、`features/sources/SourceAccordion.tsx:9/12/19/26/65`（开关） |
| 搜索请求形状 | `frontend/src/api/endpoints.ts:175-179` `searchDownload({query, source?})` → `GET /download/search?query=&source=` |
| 展开区与折叠条现状 | `SourceAccordion.tsx`（顶部：名称 + 能力 badge + 并发数 + 开关）、`sourceConfigForm.tsx`（展开区：逐能力 mode + 字段） |
| `source.json` 对未知顶层字段宽容 | `manifest.py` 只校验身份字段与 `default_config`/`common` 结构（未知顶层键不报错） |

## 3. 已拍板决策（用户，2026-09-26）

| # | 决策点 | 选择 |
|---|---|---|
| D1 | 去掉启用开关后「参与」由什么决定 | **彻底废弃 `enabled`**，全部源都可选；由搜索时的勾选表达 |
| D2 | `enabled` 删除范围 | `source.json` 的出厂 `enabled` **与**用户层 `enabled` **一起删** |
| D3 | 别名字段与 `source_name -> name` | **不重命名 `source_name`**；新字段带 `source_` 前缀：分组 `source_group`、别名 `source_alias`；**仅 UI 显示**用别名替代 |
| D4 | 分组模型 | 一个源属**一个**组（`source_group` 字符串；空 = 未分组）；组集合由各源的值去重派生 |
| D5 | 内置源是否预置 | **预置**：给 10 个内置源写默认 `source_alias` / `source_group`（用户层可覆盖） |
| D6 | 搜索页默认与记忆 | 默认**全选**，**不持久化**（每次回到全选） |
| D7 | URL 直达 tab | 保持**单选**，但按分组分节显示 + 显示别名 |

## 4. 目标

1. `enabled` 从契约、配置、模板、脚手架、API、前端、CLI、测试中**彻底消失**，且旧配置里的残留键不导致任何错误。
2. 书源在界面上以**别名**（未设则 `source_name`）显示，并可见其**分组**；设置页可编辑两者。
3. 标题搜索支持**按选中的源子集并发**（默认全选），用户可用「全选/分组」批量操作并用复选微调。
4. 桌面 / portable / Nuitka / Termux 行为不倒退：**不引入任何环境相关的书源过滤**（「本环境不支持的引擎」这一维度已随 v4.5.1 移除）。

## 5. 非目标（YAGNI）

- 不做组实体的独立管理（不能预定义空组、不能批量改名组、不能排序组）—— 组名由各源的 `source_group` 派生。
- 不做一个源属多组。
- 不重命名 `source_name`（D3），不动 `Novel.id` / 存储 / `SearchResult.source_name`。
- 不做「按分组限制下载」等下游功能；下载入口的源选择沿用现有「详情页换源」。
- 搜索选择**不持久化**（D6），也不进搜索历史。

## 6. 设计

### 6.1 数据模型

**删除 `enabled`**

- `novelbase/sources/manifest.py`：`IDENTITY_FIELDS` 改为只含 `source_name`；删除 `:53` 的 bool 校验；新增**可选顶层字段**的类型校验（若出现 `source_alias` / `source_group`，必须是非空字符串，否则 `ManifestError`）。
- 10 个内置 `novelbase/sources/*/source.json`：删除 `enabled`，新增 `source_alias` / `source_group`（见 6.1.1）。
- `template/config/sites/*.yaml`：删除第 1 行 `enabled`（模板只留必要字段）。
- `cli/main.py` 的 `dev new-source`：不再写 `enabled`（`source.json` 与用户层都不写）。
- 用户层历史残留：**不读**（`is_source_enabled()` 删除即自然不读）；`PUT /config/sources/{name}` 保存时 `existing.pop("enabled", None)` 顺手清理。

**新增元信息字段（用户层顶层，与 `concurrency` 同级）**

```yaml
# app_data/config/sites/fanqie-requests-default.yaml
source_group: 番茄        # 分组名；空/未设 = 未分组
source_alias: 番茄·直连    # 显示名；空/未设 = 显示 source_name
concurrency: 1
search: { ... }          # 逐能力段（不变）
```

**读取入口（`shared/config.py`，与 `source_concurrency()` 同风格）**

| 函数 | 语义 |
|---|---|
| `source_group(source_name) -> str` | 用户层顶层 → 出厂 `source.json` 顶层 → `""`（未分组） |
| `source_alias(source_name) -> str` | 用户层顶层 → 出厂顶层 → `""`（未设） |
| `display_name(source_name) -> str` | `source_alias(name) or name`（**唯一**的显示名入口，供 CLI/日志用；前端有自己的数据不依赖它） |

- 未知书源：三者都返回 `source_name` / `""`（宽容，与 `capabilities()` 一致）。
- 出厂层的来源是 `get_manifest(source_name)`（`manifest.py` 的未知顶层字段宽容 → 加字段不影响旧的自定义源）。

#### 6.1.1 出厂预置（10 个内置源）

| `source_name` | `source_group` | `source_alias` |
|---|---|---|
| `fanqie-requests-default` | 番茄 | 番茄·直连 |
| `fanqie-browser-default` | 番茄 | 番茄·浏览器 |
| `fanqie-api-rain` | 番茄 | 番茄·Rain API |
| `fanqie-api-oiapi` | 番茄 | 番茄·oiapi |
| `qidian-requests-default` | 起点 | 起点·直连 |
| `qidian-browser-default` | 起点 | 起点·浏览器 |
| `qimao-requests-default` | 七猫 | 七猫·直连 |
| `qimao-browser-default` | 七猫 | 七猫·浏览器 |
| `qimao-api-rain` | 七猫 | 七猫·Rain API |
| `92xs-requests-default` | 92xs | 92xs |

（文案可在实施时微调；用户层覆盖后以用户层为准。）

### 6.2 「参与集」语义重构

- 删除 `is_source_enabled()`；`enabled_source_names()` **改名**为 `default_source_names()`，语义 = 「全部书源」：

  ```python
  def default_source_names() -> list[str]:
      """默认参与集 = 全部书源（无任何环境相关过滤）。"""
  ```

- **不引入环境相关过滤**：v4.5.1（`082592d`）已整套移除 Android 套壳与环境能力表（`platform()` / `supported_modes()` / `available_capabilities()` / `is_source_available()` / `NLD_PLATFORM` / 各处 `available` 字段），移动端改走 Termux —— 本设计不得把它们重新引入。
- 涉及改名/删除的调用点：`backend/routers/download.py:19/87`、`cli/main.py:124-126`、`cli/interactive.py:13/56/84`、`backend/services/source_guard.py:5`（docstring 里提到 `is_source_enabled()`）。

### 6.3 后端 API

| 端点 | 变化 |
|---|---|
| `GET /api/v2/download/sources` | 每源 `{capabilities, source_group, source_alias}`；**删除 `enabled`**（仍**全量**返回；某源是否参与搜索完全由搜索页的勾选表达） |
| `GET /api/v2/config/sources/{name}` | 加 `source_group` / `source_alias`；删除 `enabled` |
| `PUT /api/v2/config/sources/{name}` | 接受顶层 `source_group` / `source_alias`（字符串；**空串 = 删除该键**，回落出厂/`source_name`）；不再接受 `enabled`（即使传入也忽略，且保存时清理旧键） |
| `GET /api/v2/download/search` | **新增 `sources` 查询参数**（逗号分隔的 `source_name` 列表）；`sources` 缺省或为空 → `default_source_names()`；提供时只跑其中**存在**的源（未知源**静默跳过**，与既有「单源失败静默跳过」一致）；筛完为空 → **400**（`没有可用的书源` / `未指定任何有效书源`）。`source`（单源，URL 直达）行为不变；两者同时出现时 **`source`（单源）优先**（`if source:` 分支在前，保持既有控制流） |
| `GET /api/v2/config/environment` | **已随 v4.5.1 移除**（环境能力表的出口），本设计不再提供 |

- 与 `source_guard` 的关系：`source_guard` 只保留 `require_known_source()`（v4.5.1 已删除 `require_available_source()`）；`sources` 的过滤在路由内一次完成（只做**存在性**检查）。
- V2 响应包装（`{ok,message,data}`）不变。

### 6.4 前端设置页（#1）

**折叠条 `SourceAccordion`**

- 顶部（信息行）：**别名（主名，未设则 `source_name`）** + **分组 badge**（未分组不显示）+ `source_name`（次要灰色小字，仅当别名存在时显示，避免技术名彻底消失）+ 能力 badge；**删除启用开关**；**并发数输入移进展开区**。
- 折叠条不再有任何开关语义（`available` 概念已不存在）。

**展开区 `SourceConfigEditor`**

- 新增第一行「书源信息」：**分组**（`<input>` + `datalist` 建议已有组名）与**别名**（`<input>`）；沿用现有「失焦 / 回车提交、非法不写」的交互模式（与 `TextField` 一致），保存走 `PUT`（`{source_group: "…"}` / `{source_alias: "…"}`；清空即传空串删除键）。
- 新增「并发数」行（从折叠条顶部移来，逻辑不变）。
- 逐能力配置区（mode 下拉 + 字段）不变。

### 6.5 前端搜索页（#2）

**标题 tab（双框）**

- **框 1（分段单选）**：选项 = 「全选/全不选」+ 各分组名 + 「未分组」（仅当存在未分组源）。
  - 点「全选」→ 勾选全部（按钮文案变「全不选」）→ 再点 → 全部取消。
  - 点某分组 → 仅勾选该组（取消其它）。
  - 高亮是**派生**的：当前勾选 == 全部 → 高亮「全选」；当前勾选 == 某组 → 高亮该组；否则不高亮（自定义态）。
- **框 2（复选列表）**：按分组分节（组名作小节标题，未分组归「未分组」），每项显示**别名**（未设则 `source_name`）；**默认全选**、不持久化。
- 勾选为空 → 禁用「搜索」按钮并给提示（不发请求）；否则 `sources=<勾选的 source_name 逗号列表>`。
- 搜索历史回填：标题搜索的 `source` 本来就是空，不受影响。

**URL tab**

- 单选 `Select` 改为**按分组分节**（`SelectGroup` + `SelectLabel`，shadcn 的 `Select` 已支持），项显示别名（未设则 `source_name`）；仍只选一个源，选中值仍是 `source_name`。不出现不可用源。

**类型与工具（`api/endpoints.ts`）**

- `SourceInfo`：`{capabilities, source_group, source_alias}`（去掉 `enabled`）。
- `SourceOption`：`{name, alias, group}`（原名 `name` 保持 = `source_name`，避免大面积改名；`alias`/`group` 为前端显示用）。
- `toSourceOptions()`：把 `source_alias` / `source_group` 透出（不再有任何过滤）。
- `searchDownload({query, sources})`：`sources?: string[]` → `sources=a,b,c`（保留 `source` 单源供 URL 直达）。

### 6.6 CLI 与模板/初始化

- `cli/main.py`：`cmd_search` 的默认源集改用 `default_source_names()`；`cmd_source`（`sources list`）去掉 enabled 列，改为显示 **别名 · 分组 · `source_name`**（`--json` 输出保留 `source_name` 键，新增 `source_alias`/`source_group`，去掉 `enabled`）；`dev new-source` 不再写 `enabled`。
- `cli/interactive.py`：默认源集改 `default_source_names()`；搜索结果的来源显示用 `display_name()`。
- `cli/menus.py`：删除「启用/停用书源」菜单项与其实现（`:86/110-111`）。
- `init_config.py` / `template/config/sites/*.yaml`：模板去掉 `enabled`（`init_site_config` 逻辑本身不变）。

### 6.7 数据流

```
设置页编辑分组/别名 ──PUT /config/sources/{name}──> sites/{name}.yaml（顶层 source_group/source_alias）
                                                  └─ 保存时清理旧 enabled 键
列表展示           <──GET /download/sources──────── {capabilities, source_group, source_alias}
搜索页勾选          ──GET /download/search?query=&sources=a,b,c──> 过滤（仅存在性）
                                                                  └─ 逐源并发 search([源], …)
默认参与集 = default_source_names() = 全部书源
```

### 6.8 错误处理

| 场景 | 行为 |
|---|---|
| 旧配置含 `enabled`（用户层） | 忽略不读；下次 PUT 时清理掉该键 |
| 旧自定义 `source.json` 含 `enabled` | 忽略（manifest 对未知顶层字段宽容），不报错 |
| `source_alias` / `source_group` 非字符串 | `ManifestError`（出厂层）/ 忽略视为未设（用户层，与 `enabled` 的既有宽容策略一致） |
| 搜索 `sources=` 含未知或不可用源 | 静默跳过（与「单源失败静默跳过」一致） |
| 搜索 `sources=` 筛完为空 | 400 + 明确 message |
| 前端勾选为空 | 不发请求，禁用按钮 + 提示 |
| 分组名含空白/超长 | 保存前 `strip()`；空串即删除该键（= 未分组/无别名）；长度不做硬限制（YAGNI） |

## 7. 涉及文件

**core / 配置**
- `novelbase/sources/manifest.py`、`novelbase/sources/*/source.json`（10 个）
- `shared/config.py`（删 `is_source_enabled`、`enabled_source_names` → `default_source_names`，加 `source_group`/`source_alias`/`display_name`）
- `template/config/sites/*.yaml`（10 个）

**后端**
- `backend/routers/download.py`（`/sources` 形状、搜索 `sources` 参数、`default_source_names`）
- `backend/routers/config.py`（GET/PUT 元信息、清理 `enabled`）
- `backend/services/source_guard.py`（仅 docstring 措辞）

**CLI**
- `cli/main.py`、`cli/interactive.py`、`cli/menus.py`

**前端**
- `frontend/src/api/endpoints.ts`、`frontend/src/hooks/index.ts`（如需）
- `frontend/src/features/sources/SourceAccordion.tsx`、`sourceConfigForm.tsx`（+ 可能的 `sourceConfigFields.ts`）
- `frontend/src/features/bookshelf/SearchBar.tsx`、`BookshelfPage.tsx`
- `frontend/src/features/detail/SourcePickerDialog.tsx`

**测试 / 文档**
- `tests/test_source_metadata.py`（新，替代 `test_source_enabled.py`；后者已删，`test_source_availability.py` 亦已随 v4.5.1 删除）、`tests/test_backend_download_routes.py`、`tests/test_backend_config_routes.py`、`tests/test_interactive_cli.py`、`tests/test_cli_effective_mode.py` 等
- `docs/session-prompt.md`、`docs/project/{sources,config,cli,updates}.md`、`CHANGELOG.md`

## 8. 测试

- **元信息三层合并**（新 `tests/test_source_metadata.py`）：`source_group`/`source_alias` 的「用户层 → 出厂 → 默认」优先级；未设别名时 `display_name()` 回落 `source_name`；空串删除键后的回落；未知书源宽容。
- **参与集**：`default_source_names()` = 全部书源（无任何过滤）。
- **API**：`/download/sources` 形状（含 `source_group`/`source_alias`，不含 `enabled`）；`/config/sources/{name}` GET/PUT 元信息（含空串删除键）；`PUT` 传入 `enabled` 被忽略且旧键被清理；搜索 `sources=a,b` 只跑 a、b；`sources=` 含未知源 → 跳过；`sources=` 全无效 → 400。
- **搜索**：`sources` 缺省 → 走 `default_source_names()`；`source`（单源）路径不变的回归。
- **`source.json` 契约**：manifest 不再要求 `enabled`；`source_alias`/`source_group` 非字符串时报 `ManifestError`。
- **回归**：`python -m pytest tests -q` 全绿；前端 `npx tsc -b` 0 错 + `npm run lint` 0 告警。

## 9. 风险与硬约束

- **这是一次贯穿全链的删除**：`enabled` 涉及 core 契约、10 个源、模板、脚手架、shared、后端、CLI、前端、测试、文档。任何一处漏改都会留下死引用（`grep -rn "enabled" --include=*.py` 必须只剩前端无关项：`useQuery({enabled})`、导出格式 `enabled`）。
- **不得顺手重命名 `source_name`**（D3）：`SearchResult.source_name`、`Novel` 存储键、API 键、`sites/{source_name}.yaml` 文件名全部保持。
- **不得引入环境相关过滤**：`available` / `supported_modes()` / `NLD_PLATFORM` 已随 v4.5.1 移除；搜索的过滤维度只允许「用户勾选」与「源是否存在」两个。
- **搜索历史兼容**：历史记录里存的单源 `source` 语义不变（URL 直达仍是单源）。
- **组名派生**：组集合 = 各源 `source_group` 去重 + 可能的「未分组」桶；不引入组实体（改组名 = 逐个源改，接受这个代价）。

## 10. 验收（手工）

1. 设置页：折叠条顶部显示「别名 + 分组」，无启用开关；展开可改分组/别名/并发数；改完刷新仍在（写进 `sites/{name}.yaml`）。
2. 搜索页（标题）：默认全选；点「番茄」→ 只勾番茄三个源；点「全选」→ 文案变「全不选」，再点全部取消；取消全部后搜索按钮禁用。
3. 搜索页（URL）：单选下拉按分组分节、显示别名。
4. 三条 grep 验收：`grep -rn "is_source_enabled\|enabled_source_names" --include=*.py .` 无残留；`grep -rn '"enabled"' novelbase/sources/*/source.json` 与 `grep -rn "^enabled:" template/config/sites/` 均无输出。
5. 旧配置（含 `enabled: false` 的 `sites/*.yaml`）：启动无错、搜索页正常；PUT 一次后该键消失。
6. `grep -rn "is_source_enabled\|enabled_source_names" .` 无残留（除文档历史记录）。

## 11. 参考

- `docs/project/sources.md`（书源机制、`source.json` 规范与公共 API）
- `CHANGELOG.md` 的 `## v4.5.1` 与 `082592d`（移除 Android 套壳与环境能力表的原因与范围 —— 本设计的基础前提）
- `frontend/src/features/sources/{SourceAccordion,sourceConfigForm}.tsx`（现有折叠条与展开区实现）
- `docs/project/config.md`（`sites/{source_name}.yaml` 的字段与三层合并说明）

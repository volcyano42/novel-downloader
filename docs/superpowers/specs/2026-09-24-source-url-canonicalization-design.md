# 书源 URL 归一归属 + canonical_url 索引 — 设计

- 日期：2026-09-24
- 状态：待 review（设计已逐节确认）
- 范围：`novelbase/utils/urls.py`、`novelbase/core/downloader.py`、`novelbase/core/storage.py`、`novelbase/sources/{92xs,qidian}/`、`tests/`、`AGENTS.md`、`novel-downloader-tools/scripts/`
- 取代：`2026-09-24-book-source-flattening-design.md` 的「URL 规范化（已定：能力化）」一节

## 背景

`Novel.id` 现状：`id = sha256(canonical_book_url(url, platform))[:32]`（`novelbase/utils/urls.py`），由 `novelbase/core/downloader.py:127` 中心赋值。

`novelbase` 的定位是核心库（不承载站点/应用概念），但当前有三处平台知识渗入 core：

| 位置 | 内容 |
|---|---|
| `novelbase/utils/urls.py:8` | 函数签名 `canonical_book_url(url: str, platform: str)` |
| `novelbase/utils/urls.py:24-31` | 硬编码平台名分支 `92xs` / `qidian` |
| `novelbase/utils/urls.py:27,31` | 硬编码站点域名 `http://www.92xs.info/html/{id}/`、`https://www.qidian.com/book/{id}`（92xs 分支还会把任意域名的 url 重写为 `www.92xs.info`，即镜像站归一） |
| `novelbase/core/downloader.py:127` | core 把 **source 名** 传进 core 的 urls 工具 |
| `tests/test_urls.py:29-46` | 4 个用例直接断言平台特例 |

书源侧现状盘点（2026-09-24 实测）：**「书源自己产出规范 url」已是主流做法**——

- fanqie 的 4 个 variant 全部自己拼 `https://fanqienovel.com/page/{book_id}`（`_common.py:153,179,225`），短链由 `resolve_changdunovel()` 解析
- qimao 使用页面 `link[rel="canonical"]`，或回退到入参（`_common.py:69-73`）

漏网的只有两个（core 的两个特例正在替它们干活）：

| 书源 | 现状 | 依赖 |
|---|---|---|
| qidian ×2 | `parse_novel_info(html, url=url)` 原样透传（`_common.py:100`；该文件已有 `standardize_id()` 可从 `/book/` 或 `/info/` 提取 id） | core 的 `qidian` 特例 |
| 92xs ×1 | `Novel(url=url)` 原样透传（`92xs/requests/default/novel_info.py:52`） | core 的 `92xs` 特例 |

即：core 的特例不是「core 必须懂平台」，而是替两个没做归一的书源补漏。

## 目标

1. **core 零平台知识**：`canonical_book_url` 去掉 `platform` 参数、特例分支、硬编码域名，只留通用规范化；`downloader` 不再把 source 名传进 urls 工具。
2. **归一责任归书源**：书源 `novel_info` 必须返回站点规范形态的 `Novel.url`；**不新增 `canonical_url` 能力**（`CAPABILITY_META` 保持 4 条，core 侧零新增概念）。
3. **id 保持 32 位 hash 槽位**：不动全栈键结构（后端 14 个以 `novel_id` 为路径段的路由、前端页面路由与 `endpoints.ts`、磁盘文件名、用户数据外键），新增 `meta.canonical_url` 列作为 url 索引 / 规则快照。
4. **存量迁移**：35 本（33 fanqie + 2 92xs）按新规则校验与回填，id 漂移者重命名并同步外键。

## 非目标

- **不动 `platform_from_url()` / `HOSTS`**（`novelbase/source.py:47-125`）：这是 core 里的第二处平台知识（host→platform 映射表），被 backend/CLI 共 11 处调用（`backend/routers/download.py` 3 处、`cli/core.py` 2 处、`cli/interactive.py` 4 处、`cli/main.py` 2 处，各文件都包了一层 `_platform_from_url`），`cli/main.py:45` 还硬编码兜底 `"fanqie"`。属遗留，另案处理（书源扁平化设计的未决事项 1 已覆盖）。
- 不改 `sources/` 目录结构（`{platform}/{mode}/{variant}/` 四层 → 扁平，另见书源扁平化设计）。
- 不改章节 id（`Chapter.id` 维持现状；92xs 章节 id 已是 URL 末尾数字段）。
- 不做「粘贴 URL 自动匹配书源」。
- 不建全局 novel 索引表（见「未决事项 2」）。

## 设计

### 1. core：纯通用规范化

```python
# novelbase/utils/urls.py
def canonical_url(url: str) -> str:
    """通用 URL 规范化：小写 scheme/host、去 query/fragment、去尾斜杠。无任何站点特例。"""

def make_novel_id(canonical_url: str) -> str:
    """32 位 hex（sha256 前 32 字符）。物理槽位 id，不是业务标识（不可反查来源）。"""
```

- `canonical_book_url` 改名 `canonical_url`（它不再含「book 站点」概念；同时避免与 `make_novel_id` 的参数名混淆）
- 删除：`platform` 参数、`92xs`/`qidian` 两个分支、两处硬编码域名
- 保留：通用规则 = 小写 scheme/host、去 query、去 fragment、去尾斜杠；**path 大小写保持原样**（URL path 大小写敏感，不能 lower）

### 2. 书源：站点归一 + 独立纯函数模块

写入 `AGENTS.md` 的契约：

> 书源的 `novel_info` 必须返回站点规范形态的 `Novel.url`：同一本书的多种输入形态（短链、别名路径、带 query/尾斜杠）必须归一为**同一个字符串**，且该字符串再过一遍 `canonical_url()` 必须等于自身（幂等）。core 不再做站点级兜底。

实现：归一函数放在**书源目录下的独立纯函数模块**（不注册为能力），由 `novel_info` 与迁移脚本共用同一份实现：

| 书源 | 改动 |
|---|---|
| 92xs | 新建 `novelbase/sources/92xs/_common.py`：`canonical_url(url) -> str`，从 `/book/{id}.html` 或 `/html/{id}/` 提取 id，返回 `http://www.92xs.info/html/{id}`；`92xs/requests/default/novel_info.py` 用其返回值替换 `url=url` |
| qidian | `novelbase/sources/qidian/_common.py` 新增 `canonical_url(url) -> str`（复用已有 `standardize_id()`），返回 `https://www.qidian.com/book/{id}`；`parse_novel_info` 内的 `url=url`（`:100`）改为归一后的值（browser/requests 两个书源共用该方法，一处改） |
| fanqie ×4 | 已产出规范 url，无需改动 |
| qimao ×3 | 已用 `link[rel=canonical]`；入参 url 可能带 query，由 core 通用规则兜底 |

为什么仍要「独立纯函数模块」而不是内联在 `novel_info.py`：迁移脚本必须 import **同一份实现**重算 id。规则若内联，脚本只能复制一份，规则漂移会导致运行时与脚本算出不同 id（同一本书分裂成两本）。

### 3. id 与 canonical_url 的关系

```python
# novelbase/core/downloader.py:117-129（改后）
name = get_source(url)
if name is None:
    raise SourceNotFoundError(f"source not found for: {url}")
novel = await fn(url=url, engine=engine, **kwargs)
novel.url = canonical_url(novel.url)     # core 唯一参与的 URL 处理（通用规则，无平台参数）
novel.id = make_novel_id(novel.url)      # 物理槽位
novel.extra["platform"] = name           # 保留（来源冗余，hash 不可反查）
return novel
```

**一处必须说清的细节**：`meta.url` 存的就是 `novel.url`（`storage.py:376-383` 的 `INSERT OR REPLACE`）。当 `novel.url` 被保证为规范形后，`meta.url` **本身就是** canonical url——因此新增的 `canonical_url` 列在数据上与原 `url` 列等价。它的价值是**显式的「id 来源快照」**：规范化规则将来再变时，可用它精确重算 id、检测漂移，而不依赖可能被后续写入影响的 `url` 列。本设计规定 **`canonical_url` 为权威**，`url` 保留为用户可见的原始语义。

### 4. 数据模型变更

`novelbase/core/storage.py`：

```sql
-- 新库：_init_novel_db(:328) 的 meta 表加一列
canonical_url TEXT NOT NULL DEFAULT ''
```

- **已有库**：`_connect_novel()`（`:309`）在 `_init_novel_db()` 之后调用新增的 `_ensure_schema(conn)`——`PRAGMA table_info(meta)` 检查列是否存在，缺失则 `ALTER TABLE meta ADD COLUMN canonical_url TEXT NOT NULL DEFAULT ''`，并用 `PRAGMA user_version` 守卫避免每次连接重复检查
- `save_meta()`（`:371`）的 `INSERT OR REPLACE` 列清单加入 `canonical_url`，值取 `novel.url`
- `load_meta()` / `_row_to_novel()`：列可读可不读；本次**不改变 `Novel` 模型**（不新增字段），列只服务索引与校验
- `iter_metas()`（`:397`）不变（注释已写明「目录就是索引：扫描 `*.db` 读每本的 meta 表」）

> 先例：`shared/user_data.py:68-118` 已是 `_ensure_schema` + `PRAGMA user_version` 守卫的成熟模式（`search_history` 的 `mode`/`variant` 列即如此补上）。novel 库此前只有 `CREATE TABLE IF NOT EXISTS`，没有列迁移能力，本次照搬该模式。

### 5. 测试

- `tests/test_urls.py`：删除 4 个平台特例用例；保留并补齐通用规则用例（小写 scheme/host、去 query/fragment、去尾斜杠、path 大小写保持）；`make_novel_id` 的幂等/格式（32 位 hex）/不同 url 结果不同
- **书源归一测试**（新增）：92xs 的 `/book/{id}.html`、`/html/{id}/`、带 query/尾斜杠变体归一到同一结果；qidian 的 `/info/{id}/`、`/book/{id}`、`/book/{id}/` 归一到 `https://www.qidian.com/book/{id}`；非本域 url 的行为（原样返回，不误伤）
- **归一幂等契约测试**（新增，挂 `tests/test_source_contracts.py`）：对每个自带归一模块的书源，断言 `canonical_url(canonical_url(x)) == canonical_url(x)`，且 `core.canonical_url(书源归一(x)) == 书源归一(x)`。这是 core 不再兜底后的主要保障，且不需要网络/engine
- **id 等价性测试**：把「旧规则 id → 新规则 id」的映射固化为用例（含 92xs 两条真实 URL：`/book/536.html`、`/book/96850.html`），供迁移脚本复核
- `tests/test_storage.py`：断言新列存在、`save_meta` 写入、`_ensure_schema` 对旧库补列幂等

### 6. 存量迁移脚本

`novel-downloader-tools/scripts/migrate_canonical_url.py`（仓库外，遵循「衍生产物不进仓库」约定），复用 `migrate_novel_id.py` 的 Windows 踩坑处理（`_rename_with_retry`、显式 `commit`、dry-run 默认、幂等）：

1. 遍历 `app_data/storage/novels/*.db`，读 `meta(id, url)`
2. `canonical = 书源归一(url)`（通过 `get_source(url)` 定位书源模块；该书源无归一模块则用 core 通用规则）→ `new_id = make_novel_id(canonical)`
3. **校验旧规则**：断言 `old_id == make_novel_id(旧规则 canonical)`（脚本内置旧规则对照实现，**只用于校验**，不用于生成新 id）。不等则打印警告并跳过，说明该库的入库规则不明
4. `UPDATE meta SET url = canonical, canonical_url = canonical`（补列由 `_ensure_schema` 或脚本自行执行）
5. `new_id != old_id` 时：`_rename_with_retry('{old}.db' → '{new}.db')` → `UPDATE meta SET id` + `UPDATE illustrations SET owner_id`（`owner_type='novel'`）+ `user_data.db` 的 `favorites`/`groups`/`bookmarks`
6. 冲突检测：多本旧书映射到同一 `new_id` → 打印「疑似同书重复入库」，跳过不自动合并

实测预期（当前 35 本）：

| 分组 | 数量 | 迁移动作 |
|---|---|---|
| fanqie（`meta.url` 已是规范形） | 33 | 只写两列；id / 文件名 / 外键全部不变 |
| 92xs（`meta.url` 是未归一的 `/book/{id}.html`） | 2（`c18b41dc…`=536、`e2633bfd…`=96850） | 归一后 id 变化（旧特例输出保留尾斜杠 `http://www.92xs.info/html/{id}/`，新规则去尾斜杠）→ **重命名 + 改外键** |

### 7. 影响面清单

```
novelbase/utils/urls.py                            去 platform 参数/特例/域名；改名 canonical_url
novelbase/core/downloader.py:117-129               novel.url 规范化；id 生成不再传 source 名
novelbase/core/storage.py                          meta 加 canonical_url 列；_ensure_schema；save_meta
novelbase/sources/92xs/_common.py（新）             归一函数
novelbase/sources/92xs/requests/default/novel_info.py   返回规范 url
novelbase/sources/qidian/_common.py                归一函数 + parse_novel_info 归一
tests/test_urls.py                                 重写为通用规则
tests/test_source_contracts.py                     新增归一幂等契约测试
tests/test_storage.py                              新列断言
AGENTS.md                                          新增「书源必须返回规范 url」契约条目
novel-downloader-tools/scripts/migrate_canonical_url.py（新，仓库外）
```

## 风险

- **id 漂移**：92xs 的 2 本必然改 id（尾斜杠归一规则差异）；脚本用「旧规则校验」识别，dry-run 先行。fanqie 33 本零漂移。
- **漏归一的书源**：core 不再兜底，书源若忘记归一，同一本书会入库两次（书架重复、断点续传失效、进度分裂）。缓解：归一幂等契约测试 + `AGENTS.md` 契约条目——**新增书源时该测试是唯一拦截点**。
- **规则双份**：书源归一与迁移脚本若各自实现会漂移。缓解：归一函数放书源侧独立模块，脚本 import 同一份。
- **`_ensure_schema` 的连接开销**：用 `PRAGMA user_version` 守卫（照搬 `user_data.py` 先例）。
- **两列冗余**：`meta.url` 与 `meta.canonical_url` 默认同值；若将来有逻辑只更新其一，需以本设计规定（`canonical_url` 权威）为准，避免歧义。
- **`resolve_meta` 是唯一生成 id 的路径**：`downloader.py` 另有 2 处 `get_source()` 调用（`:145` 章节列表、`:169` 章节内容）不生成 id；确认章节路径不受本设计影响（章节 id 不由 url 派生）。

## 与既有文档的关系

- **取代** `2026-09-24-book-source-flattening-design.md` 的「URL 规范化（已定：能力化）」一节。该节定的是「`CAPABILITY_META` 新增 `canonical_url` 第 5 能力，3 个书源各带 `canonical_url.py`」；本设计改为「不新增能力，归一写在书源自己的模块里 + 契约要求 `novel_info` 返回规范 url」。实施书源扁平化时以本设计为准（新结构下可沿用同一份归一模块）。
- 与 `2026-08-22-novel-id-hash-design.md` 一致：id 生成仍中心化在 `resolve_meta`，仍为 32 位 hex（该文档 2.2 节「必须 hash canonical url」的前提不变）。

## 未决事项

1. **`platform_from_url()` / `HOSTS`**：core 里的第二处平台知识（host→platform 映射表 + 9 处调用 + `cli/main.py:45` 硬编码 `"fanqie"`）。本设计不动；书源扁平化设计的「未决事项 1（URL 自动匹配书源）」将重新设计这一块。
2. **全局 novel 索引表**：`canonical_url` 列位于每本书自己的库里，跨库「用 url 找书」目前靠 `iter_metas()` 遍历 `*.db`。35 本规模下够用；若将来需要全局唯一约束或跨书源去重，需在 `user_data.db` 建一张 `novels(id, canonical_url, source_name, title)` 索引表并维护一致性。
3. **`Novel` 模型是否暴露 `canonical_url`**：本设计不新增模型字段（列只服务存储与校验）。若前端需要展示/复制规范 url，再议。

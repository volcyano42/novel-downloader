# Novel.id 改为 hash(url) 设计文档

**日期**: 2026-08-22
**状态**: 已确认，待实施

---

## 一、动机

`Novel.id` 目前由各 source 自己从 URL 提取源站 ID 并拼接平台前缀（`fanqie_7123...`、`92xs_{数字}`、`qidian_{10位}`、`qimao_{数字}`），并配套维护 `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE` 三件套用于 id 反查。

问题：
- 每个 source 手动拼前缀、维护反查三件套，繁琐且易错（92xs 的 `re.search` 提取失败时 id 为空字符串）
- 不同平台去前缀后纯数字可能撞车（qimao 与 fanqie 都是数字），所以"必须带特定前缀才能让 id 唯一"
- id 生成逻辑分散在各 source 内部，无法统一

目标：**用 `hash(url)` 生成 id，彻底去掉平台前缀，id 生成中心化**。url 本身全局唯一（不同平台不同域名、同平台不同书不同路径），hash 只是把 url 变成文件名/URL 安全的确定性字符串。

## 二、id 生成核心

### 2.1 id 格式

```
sha256(canonical_url)[:32]   # 32 位 hex（128bit），无前缀
```

示例：`https://fanqienovel.com/page/7123456789012345678` → `a3f9...e2c1`（32 hex）。

- 128bit 碰撞概率对个人书库规模（<1 万本）约 1e-31 量级，可忽略
- hex 字符（0-9a-f）文件名安全、URL 路径安全

### 2.2 hash 输入 = canonical url（正确性关键）

**必须 hash「resolve_meta 返回的标准化 url」**，否则同一本书因输入 url 不同（changdunovel 短链 / 带 query / http vs https / 尾斜杠 / 92xs 两种路径形态）会得到不同 id，造成重复入库。

**公共函数 `canonical_book_url(url, platform)`**，放核心库（`novelbase/utils/`），两个场景共用（运行时生成 + 迁移脚本重算，保证结果一致）：
- 通用规范化（yarl）：小写 scheme/host、去 query、去 fragment、去尾斜杠
- 平台特殊规则：
  - 92xs 的 `/book/{id}.html` → `/html/{id}/`（与 `chapter_list` 现行规则一致）
  - qidian 的 `/info/{id}/` → `/book/{id}/`（qidian 两种 url 形态，`BOOK_URL_TEMPLATE` 以 `/book/` 为标准）
- fanqie 的 changdunovel 短链已由 source 层 `resolve_changdunovel` 预处理为标准 url，中心层不重复处理

### 2.3 id 生成位置（中心化）

`downloader.resolve_meta()` 返回前统一赋值：

```python
novel.id = make_novel_id(canonical_book_url(novel.url, name))
novel.extra["platform"] = name   # 冗余存平台，hash 后无法从 id 反推
```

同时**删除 4 个 source 里手动拼 id 的代码**（`f"fanqie_{...}"`、`f"92xs_{...}"`、`f"qidian_{...}"`、`f"qimao_{...}"`，含全部 mode/variant 下的 `novel_info.py`）。为配合删除，**`Novel.id` 字段加默认值 `""`**：source 构造 Novel 时不再传 id，由 `resolve_meta` 中心赋值后才有值。存储层 `save_meta` 之前 id 必已赋值（保存必经 `resolve_meta`）；`loads`/测试构造时显式传 id 不受影响。

一次改动覆盖全部 source，以后新增 source 无需关心 id。

## 三、依赖点改造

hash 后从 id 无法反推平台/URL，以下依赖点逐一处理：

| 依赖点 | 现状 | 改造 |
|---|---|---|
| `get_source_for_id()` | 用 `ID_PATTERN` 匹配前缀反查平台，仅 `resolve_chapter` 一处调用 | **删除函数**；`resolve_chapter` 直接走 `get_source(chapter.url)`。该回退路径现在就已生效：92xs 的 `chapter.novel_id` 是空字符串、fanqie 是纯数字（不匹配 `ID_PATTERN`），本就匹配不上 |
| `resolve_book_url()` | url 输入 + `ID_PATTERN`→`BOOK_URL_TEMPLATE` 反查 | **只保留 url 输入分支**（http/https 直接返回）；id 输入分支删除，无法识别时仍抛 `ValueError` |
| backend `/download/search` 的 `query.isdigit()` 分支 | 纯数字 id 输入走 resolve | **移除该分支**（hash 不是数字，无法解析），只保留 http(s) 输入 |
| 前端 `SearchBar.tsx` 的 `urlIdPlatform` | 按位数猜平台（19→fanqie、10→qidian、其余→qimao） | **移除**，只保留 URL 检测 |
| `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE` | 各 source `__init__.py` + `source.py._scan_sources` 收集 + `build_manifest`/`_manifest` + backend `/sources` + cli `sources` 展示 | **全部退役删除**（`BOOK_URL_TEMPLATE` 是 id→url 反查专用，hash 不可逆后无用） |
| `Novel.origin_id` 属性 | 去前缀逻辑 + setter 忽略赋值 | **删除属性**（无前缀可去）；`tests/test_models.py` 三个相关用例同步删除 |
| `source.py` 的 `register_source()` 元数据 | 含 `id_pattern` / `origin_id_pattern` / `book_url_template` 字段 | 字段移除；`backend /sources` 与 `cli sources` 响应同步去掉 |

`standardize_id`（fanqie 内部）保留：仍在 novel_info 里用于拼标准化 url，与 id 生成解耦。

## 四、存量迁移

**迁移脚本**：`novel-downloader-tools/scripts/migrate_novel_id.py`（符合"衍生产物放 novel-downloader-tools/"约定，不进仓库；运行时 `sys.path` 指向仓库以复用 `canonical_book_url` + `make_novel_id`）。

1. 遍历 `app_data/storage/novels/*.db`（SQLite 单书模式，用 `SQLiteStorage.iter_metas()` 直接读库内 meta 表，得到每本书的旧 id 与 url）
2. `new_id = make_novel_id(canonical_book_url(url, platform))` —— **与运行时同一函数**，迁移结果与重新拉取一致
3. **同步更新库内数据**（只改文件名会因 `load_meta` 用 `WHERE id = ?` 查询而失效）：
   - `UPDATE meta SET id = ? WHERE id = ?`（旧 id 主键 → 新 id）
   - `UPDATE illustrations SET owner_id = ? WHERE owner_type = 'novel' AND owner_id = ?`
4. 重命名 `{old_id}.db` → `{new_id}.db`
5. 更新 `app_data/storage/users/default/user_data.db` 的 `favorites.novel_id`：旧 id → 新 id 映射
6. 幂等：先扫描全部 `{old_id} → {new_id}` 映射再批量执行；已改名的跳过，中途失败可重跑

`chapters` 表无 novel_id 列（章节 `novel_id` 由 load 时回填），且章节 id 格式与 Novel.id 无关，**迁移不动 chapters**。

平台名来源：旧 meta.json 不含 platform 字段，脚本用 `platform_from_url(url)`（hosts 匹配，不受本次改动影响）推断。

## 五、测试

- `make_novel_id` 幂等性：同 url 两次调用结果相同；不同 url 结果不同
- `canonical_book_url` 用例：带 query / fragment / 尾斜杠 / http↔https 大小写 / 92xs `/book/{id}.html` 两种形态
- `resolve_chapter` 移除 `get_source_for_id` 后 url 回退路径（`tests/test_downloader.py` 现有 patch 改写）
- 迁移脚本 dry-run：样本 db 上验证 `{old_id} → {new_id}` 映射与 favorites 更新
- `tests/test_models.py`：删除 `origin_id` 三个用例，新增 hash id 格式校验

## 六、不做的事（明确排除）

- 前端 `sessionStorage` 旧 key（`nd:...`）——临时态，不迁移
- 进行中的下载任务（task_manager 内存态）——不迁移
- `sync.ffs_db` 同步文件——外部工具产物，不迁移
- `Chapter.id` / `Chapter.novel_id` 的格式统一（fanqie 章节 id 仍为源站 itemId，92xs 仍为 url）——本次只改 Novel.id，章节 id 维持现状（`resolve_chapter` 的平台识别走 url 回退即可）

## 七、影响文件清单（预估）

```
novelbase/utils/urls.py（新）            canonical_book_url + make_novel_id
novelbase/core/downloader.py             resolve_meta 中心化赋值；删除 get_source_for_id
novelbase/source.py                      _scan_sources 字段移除；resolve_book_url 简化
novelbase/models/novel.py                删除 origin_id 属性；id 字段加默认值 ""
novelbase/sources/{fanqie,92xs,qidian,qimao}/__init__.py   删 ID_PATTERN/ORIGIN_ID_PATTERN/BOOK_URL_TEMPLATE
novelbase/sources/{...}/.../novel_info.py   删手动拼 id
novelbase/utils/build_manifest.py + _manifest.py   字段移除
backend/routers/download.py              isdigit 分支移除、_resolve_url 简化、/sources 响应精简
frontend/src/features/bookshelf/SearchBar.tsx   移除 urlIdPlatform
cli/main.py                              sources 展示字段移除
tests/test_models.py / test_downloader.py       用例增删改
novel-downloader-tools/scripts/migrate_novel_id.py（新，仓库外）
```

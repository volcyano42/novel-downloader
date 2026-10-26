# 用户数据从 SQLite 拆到文本文件（books.yaml + search_history.jsonl）

2026-10-26

## 1. 意图与原因

单人项目，没有账户概念。`app_data/storage/users/default/user_data.db` 这一层
`users/default` 是伪多用户结构的遗留：整个仓库只有一个人用，`users` 下面永远只有
`default` 一个目录。

而这个库装的数据（分组 / 收藏 / 书源来源 / 搜索历史）既不是小说本体，也不该埋在
二进制 SQLite 里——想手改一条分组，得开 `sqlite3` 敲 SQL。

目标形态：`app_data/storage/` 只剩 `novels/`；这些账本变成能手改、能看懂的文本文件，
落在 `app_data/config/library/` 下。

## 2. 目标

- **G1** `app_data/storage/` 下只剩 `novels/`（`users/` 整层消失）
- **G2** `user_data.db` 的 5 张表 → 2 个文件：4 张表进 `books.yaml`，
  `search_history` 进 `search_history.jsonl`，`bookmarks` 删除
- **G3** 两个文件能手改：**每条能看出是哪本书**（书名）、字段直白、默认值省略、
  单行坏了不影响整体读取
- **G4** `shared/user_data.py` 的**业务函数**签名与返回形状不变 → backend 路由、
  CLI 业务代码、前端零改动（例外：`config init --user-db` 参数随 `init_user_db()`
  一起删除，见 6.6）
- **G5** 一次性迁移脚本 `scripts/migrate_user_data.py`（human partner 要求保留）

## 3. 非目标

- **N1** `novel_id` 语义不变：仍是 `sha256(url)[:32]`（`novelbase/utils/urls.py:17`），
  32 位 hex。原 URL 存在每本书 `storage/novels/<id>.db` 的 `meta.id` 里，不复制进账本。
- **N2** 不救活 `bookmarks`：0 行、无任何调用者、列还是旧的 `platform`
- **N3** 不动 `storage/novels/<id>.db` 的内部结构（`meta` / `chapters` / `illustrations`）
- **N4** 不做跨进程并发控制（见 C1）
- **N5** 不引入新依赖（PyYAML 已在用；不用 ruamel，因此**行内注释无法保留**）

## 4. 反目标（技术上跑通也算失败）

- **A1** 迁移后数据缺失或错位。本机 2026-10-26 实测基线：
  `groups` 103 行 / 102 本（`680fced7a0cef16dc19f37b1c191d75b` 同时在 `TEST` 和
  `default`）、`novel_sources` 102 行、`favorites` 1 行、`search_history` 10 行。
  **103 条组关系必须一条不少**（多组模型才能做到）。
- **A2** `books.yaml` 被写坏成半截 yaml（断电、并发写），且无事务可回滚
- **A3** 手改过的文件程序读不出来——缺字段抛异常、多未知字段被静默吃掉
- **A4** `app_data/config/` 根目录继续混装运行时数据（配置与账本混在一起）

## 5. 约束

- **C1** backend 单进程：`backend/main.py:158` 是 `uvicorn.run(app, host=...)`，不带
  `workers`。因此**进程内 `threading.Lock()` 就够**（项目惯例：
  `backend/services/task_manager.py:34` 的 `_tasks_lock`、
  `backend/services/engine_manager.py:20` 的 `_engine_lock`）
- **C2** 现有调用方（业务函数全部保持不动）：

  | 调用方 | 用到 |
  |---|---|
  | `backend/routers/config.py:51-80` | `load_groups` / `save_groups` / `load_favorites` / `add_favorite` / `remove_favorite` |
  | `backend/routers/history.py` | `get_search_history` / `add_search_history` / `delete_search_history` |
  | `backend/routers/storage.py:12` | `delete_novel_source` / `get_novel_source` / `get_novel_sources` / `set_novel_source` |
  | `backend/services/task_manager.py:26` | `set_novel_source`（下载热路径） |
  | `cli/config.py:106-193` | groups 系列薄封装 |
  | `cli/core.py:16,140,142` / `cli/interactive.py:20` | `get_novel_source` / `add_novel_to_group` / `set_novel_source` |
  | `cli/main.py:286` / `cli/menus.py:317` | `delete_novel_source` |
  | `novelbase/core/sync.py:236,307` | `get_novel_source` / `set_novel_source` |

- **C3** 前端按**整数 id** 删除搜索历史：`frontend/src/api/endpoints.ts:308`
  （`deleteSearchHistory(historyId: number)`）→ `DELETE /api/v2/history/search/{history_id}`
  （`backend/routers/history.py:64`，路径参数声明为 `int`）
- **C4** 旧数据在本机现有 db 里，必须保全后再删库。**`user_data.db-wal` 里有未
  checkpoint 的写入**（实测 4152 字节，10-26 查询仍可见）。成因：另一个进程启动过
  `app.py`（human partner 2026-10-26 说明，现已关闭），但进程退出后 WAL 仍未被合并。
  迁移前必须先 `PRAGMA wal_checkpoint(TRUNCATE)`，否则可能正好漏掉那 10 条搜索历史。
- **C5** `novel_id` 字段是书的主键，全部对外接口（API 路径段、前端路由、文件名）
  都用它——`books.yaml` 的 key 也只能是它，不能换成 URL

## 6. 方案

### 6.1 位置

```
app_data/
├── browser/Chromium/User Data/
├── config/
│   ├── config.yaml
│   ├── formats/*.yaml
│   ├── sources/*.yaml
│   └── library/                  ← 新增
│       ├── books.yaml
│       └── search_history.jsonl
└── storage/
    └── novels/<id>.db            ← 只剩这个（另有一个 sync.ffs_db，人工清理，见 6.6）
```

考虑过并否掉的两个位置：

- **`config/` 根平铺**：`config/` 根从此既有纯配置又有运行时账本，触犯 A4；
  后续加书签、阅读进度时无处安放。
- **`config/library.yaml` + `app_data/data/search_history.jsonl`**：按"你改 vs 程序攒"
  彻底分家，但 `app_data/` 多一个只装一个文件的顶层目录。

选 `config/library/`：与已有的 `sources/`、`formats/` 同级同构；`config/` 根保持纯配置；
后续所有书维度账本直接进这个目录。

### 6.2 `books.yaml` 形状

```yaml
# app_data/config/library/books.yaml
# 书维度账本。key = novel_id（sha256(url)[:32]）。
# title 由程序在首次见到这本书时填入，手改后不会被覆盖。
# 组关系写在 groups 下，每本书可属于多个组。
# 其余字段省略即默认：favorite=false / source 未知 / 无收藏时间。

"037507eea3ae924dc1b506189e6535d9":
  title: 时间循环：我成了杀害青梅的凶手
  groups:
    default: {}
  favorite: true
  favorited_at: "2026-09-20 10:00:00"
  source: fanqie-api-rain

"680fced7a0cef16dc19f37b1c191d75b":
  groups:
    default: {}
    TEST:
      pending_export: true
```

| 字段 | 类型 | 缺省含义 | 来源 |
|---|---|---|---|
| `title` | str | 未知书名 | `storage/novels/<id>.db` 的 `meta.title` |
| `groups` | dict | 不属于任何组 | `groups` 表按 `group_name` 归并 |
| `groups.<组名>` | dict | `{}` 合法 | 该组的附加属性，当前只有一个键 |
| `groups.<组名>.pending_export` | bool | `false` | `groups.pending_export` |
| `favorite` | bool | `false` | `favorites` 有行 |
| `favorited_at` | str | 未知收藏时间 | `favorites.favorited_at` |
| `source` | str | 未知来源 | `novel_sources.source_name` |

规则：

- **默认值省略**：`false` / 空串 / 缺失字段一律不写。`favorite: false` 不写；
  删掉该键等于取消收藏。
- **`groups` 用 dict 而非列表**：`pending_export` 是 `(组, 书)` 对的属性
  （`PRIMARY KEY (group_name, novel_id)`），列表装不下。dict 形式让
  `load_groups()` 的内层结构（`{novel_id: {pending_export}}`）几乎原样映射，
  无损且能手改。
- **`title` 是派生字段，保持最新**：`set_novel_source()`（下载/同步路径必经）与迁移
  脚本**每次**从 `storage/novels/<id>.db` 的 `meta.title` 同步写入。**手改 `title` 无效**，
  下次同步会盖回（human partner 2026-10-26 决定「title 保持最新」）。要让账本书名跟
  源站一致，改源站书名后跑一次同步即可。该书没有 `novels/<id>.db` 时跳过（不阻断）。
- **丢掉 `novel_sources.updated_at`**：无任何读方（`get_novel_source` 只读
  `source_name`），留着是噪音。有意接受的信息损失。
- **丢掉 `favorites.note`**：三年无人写入过（`add_favorite(novel_id)` 只收 id）。
- **未知字段原样保留**：read-modify-write 不吃掉你手写的备注字段。
- **注释会被抹掉**：写入用 `yaml.safe_dump`，PyYAML 不保留注释。
  为补偿，序列化层每次重写都**重新注入固定的文件头注释**，并按
  `title` → `groups` → `favorite` → `favorited_at` → `source` → 未知字段的
  固定顺序输出。**行内注释保不住**（N5）。

### 6.3 `search_history.jsonl` 形状

```jsonl
{"id": 1, "source_name": "fanqie-requests-default", "keyword": "斗罗", "searched_at": "2026-10-25 19:31:02"}
{"id": 2, "source_name": "qidian-browser-default", "keyword": "诡秘", "searched_at": "2026-10-25 19:33:10"}
```

**为什么是 jsonl 而不是 yaml**：这是唯一高频写的账本（每次搜索写一次）。jsonl 追加
是 O(1)、不需要 read-modify-write，也不会和 `PUT /config/groups` 的全量覆盖互相踩。

三条语义：

1. **写入 = 只追加**。同 `(source_name, keyword)` 再次搜索时**追加新行**（新时间戳），
   不原地更新。
2. **读取时去重**：按 `(source_name, keyword)` 只保留 `searched_at` 最新的一行，
   再按 `searched_at` 倒序（字符串序 = 时间序，格式 `%Y-%m-%d %H:%M:%S`），截 `limit`。
   这等价于原来 `UNIQUE(source_name, keyword) + ON CONFLICT DO UPDATE` 的可观测结果。
3. **压缩**：追加后行数 > **250** 时，重写成去重后的最近 **200** 行。行数用进程内
   计数器维护（首次访问数一遍），不必每次读全文件。

**`id` 保留在文件里**（C3 决定：拆 id 要动 API 契约 + 前端两个文件，而多一个整数字段
对手改几乎无影响）。分配规则：`max(现有 id) + 1`，进程内缓存。容忍度：

- 坏行（JSON 解析失败）跳过，不 abort 整个读取
- 缺 `id` 或 `id` 不是整数的行**跳过**（本文件由程序维护；手改请自带 id）

`delete_search_history(history_id)`：读到目标 id → 取其 `(source_name, keyword)`
→ **删除所有同键的物理行**（否则去重后它还会出现）→ 原子重写。
200 行的重写可忽略。

`clear_search_history()`：把文件重写为空。

### 6.4 函数映射（签名与返回形状全部不变）

| 函数 | 新实现语义 |
|---|---|
| `load_groups()` | 扫 `books.yaml` → `{group: {novel_id: {**组属性}}}` |
| `save_groups(groups)` | **只重建每本书的 `groups` 字段**；`title` / `favorite` / `favorited_at` / `source` 原样保留。**整个条目 dict 变空时才删 key**（只剩用户手写的未知字段则保留——A3） |
| `get_novel_group(id)` | `books[id].groups` 的第一个组名，无则 `None`。**多组时返回哪个未定义**（原 SQL `fetchone` 同样未定义），只用于 `ensure_novel_in_group` 判断"是否已有归属" |
| `add_novel_to_group(id, g)` | **保持原语义**：先从该书移出所有其它组，再加入 `g`。返回已在 `g` → `False`，否则 `True`。（唯一调用点 `cli/core.py:140` 是"下载后入组"，不是"多组追加"） |
| `ensure_novel_in_group(id)` | 无任何组时加入 `"default"` |
| `load_favorites()` | 所有 `favorite: true` 的 novel_id，按 `favorited_at` 倒序（无该字段排最后） |
| `add_favorite(id)` | 已收藏 → `False`；否则 `favorite: true` + `favorited_at` → `True` |
| `remove_favorite(id)` | 删 `favorite` + `favorited_at`；返回原本是否存在 |
| `is_favorite(id)` | `books[id].favorite is True` |
| `set_novel_source(id, s)` | 空 `s` 直接返回（不建孤儿条目）；否则写 `source`，并**始终**从 `meta.title` 同步 `title` |
| `get_novel_source(id)` | `books[id].source`，缺则 `None` |
| `get_novel_sources(ids)` | 一次读入，返回命中的 `{id: source}`；空输入返回 `{}` |
| `delete_novel_source(id)` | 删 `source` 字段，返回原本是否存在 |
| `get_search_history(limit)` | 见 6.3 第 2 条 |
| `add_search_history(s, k)` | 见 6.3 第 1 条 |
| `delete_search_history(id)` | 见 6.3 |
| `clear_search_history()` | 见 6.3 |
| `add_bookmark` / `remove_bookmark` / `get_bookmarks` | **删除**（不留半死接口） |

**`save_groups` 的语义修正是这次最容易踩的坑**：现在是 `DELETE FROM groups` + 按 body
全量插入（body = 全集）。换成 `books.yaml` 后如果照搬"全量覆盖整个文件"，前端拖一次
分组就会把 `favorite` 和 `source` 一起抹掉（A1）。它只能重建 `groups` 这一个字段。

### 6.5 读写安全

```python
_lock = threading.Lock()                     # 模块级，包住所有读-改-写

class LibraryCorruptError(RuntimeError):     # 文件存在但不是合法 dict
    ...

def _atomic_write(path: Path, text: str) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))   # 上一版可回滚
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())                 # A2：断电不能留 0 字节文件
    os.replace(tmp, path)                    # 同目录 rename，POSIX 原子
```

- `books.yaml` 的每次全量重写走 `_atomic_write`，并留下 `books.yaml.bak`
- `search_history.jsonl` 的**追加**直接 `open("a")`（单行 < PIPE_BUF，不会撕裂）；
  只有**压缩**和**删除**走 `_atomic_write`
- 读操作也拿锁（103 本书 / 200 行，代价可忽略），换取实现简单
- `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)`：中文不转义、保持顺序

**整份解析失败的处置（A2/A3）**：`books.yaml` 存在但 `safe_load` 抛异常、或顶层不是
dict → 抛 `LibraryCorruptError`（消息含文件路径）。**读和写都抛**，效果是"文件坏了
谁也别想覆盖它"：书架页会报错，你去修文件或从 `.bak` 恢复。绝不能降级成空 dict ——
那会让下一次 `set_novel_source`（下载热路径）把 103 本书的账本重写成一条。

### 6.6 删除清单

| 对象 | 动作 |
|---|---|
| `shared/user_data.py` 的 `_SCHEMA_SQL` / `_ensure_schema` / `_migrate_groups_yaml` | 删 |
| `shared/user_data.py` 的 `DB_PATH` / `GROUPS_YAML` | 换成 `LIBRARY_DIR` / `BOOKS_PATH` / `HISTORY_PATH` / `NOVELS_DIR`（仍派生自 `shared.config.APP_DATA`） |
| `init_config.init_user_db()` + `_user_db_target_dir()` | 删；`init_all_config()` 去掉这一步 |
| `cli/main.py` 的 `config init --user-db` 参数（`:101`）、`:396`、`:408`、帮助文案 `:365` | 删（`init_user_db()` 没了；**与 G4 的"CLI 零改动"是唯一例外**） |
| `template/storage/` 整个目录（`users/default/user_data.db`） | 删 |
| `template/config/groups.yaml`（内容只有 `default: {}`） | 删；`check_config()` / `init_all_config()` / `PUBLIC_MANIFEST.md` 的 template 清单同步 |
| `app_data/storage/users/` | 迁移脚本在 `--apply` 时删（备份已挪走，见 6.7） |
| `app_data/storage/sync.ffs_db`（FreeFileSync 环境文件） | **代码不动**，由 human partner 手工删 |
| `scripts/migrate_novel_sources.py` | 保留不动（调用 `set_novel_source`，继续有效） |

### 6.7 迁移脚本 `scripts/migrate_user_data.py`

1. 打开旧库前先 `PRAGMA wal_checkpoint(TRUNCATE)`（C4：WAL 里有未落盘的 10 条历史）
2. 读 4 张表 + 从 `storage/novels/<id>.db` 的 `meta.title` 补 `title`
3. 写 `config/library/books.yaml` + `search_history.jsonl`
4. 目标文件已存在时**拒绝执行**（`--force` 才覆盖），避免二次跑冲掉新数据
5. 默认 **dry-run**：只打印条数与内容摘要，不落盘；`--apply` 才写
6. `--apply` 成功后的收尾：把旧库**复制**到
   `app_data/config/library/user_data.db.migrated`（与账本同目录，不破坏 G1），
   然后删除整个 `app_data/storage/users/`（含 `-wal` / `-shm`）
7. 收尾后自检并打印 G1 是否达成（`storage/` 下只剩 `novels/` 与 `sync.ffs_db`）

## 7. 测试影响

| 文件 | 处理 |
|---|---|
| `tests/test_shared_user_data.py` | **重写**：monkeypatch `BOOKS_PATH` / `HISTORY_PATH` 到 `tmp_path`，覆盖 6.4 全部函数 + 去重 + 压缩 + 原子写 + 解析失败抛错 + 手写未知字段不丢 |
| `tests/test_user_db_template.py` | **删除**（测的是 `_SCHEMA_SQL` 与模板库，两者都没了） |
| `tests/test_paths.py::test_user_data_path_derives_from_app_data` | 改：断言新四个路径派生自 `APP_DATA`（现在是 `DB_PATH` / `GROUPS_YAML`） |
| `tests/test_migrate_user_data.py` | **新增**：造小 sqlite 库（含双组书、孤儿书、WAL 未 checkpoint）→ 迁移 → 断言两个文件内容与 6 条基线 |
| `tests/test_novel_source_writes.py` | **必须改**：现在 `monkeypatch.setattr(user_data, "DB_PATH", ...)`，常量一删就 `AttributeError` |
| `tests/test_storage_source_reads.py` | **必须改**：同上 |
| `tests/test_storage_source_write_route.py` | **必须改**：同上 |
| `tests/test_migrate_novel_sources.py` | **必须改**：同上 |
| `tests/test_cli_effective_mode.py` / `test_cli_dev_new_source.py` | 检查是否引用了 `--user-db` / `init_user_db`（`test_cli_effective_mode.py:145` 有 `init_user_db` mock） |

## 8. 留给 builder 决定的

- 是否对 `books.yaml` 做进程内 mtime 缓存（默认**不做**，每次全读；103 本书几十 KB）
- 压缩阈值的常量命名与落点（建议 `_HISTORY_MAX_LINES = 250` / `_HISTORY_KEEP = 200`）
- `search_history.jsonl` 尾行缺换行符的容错（建议读取用 `splitlines()`；追加前若文件
  非空且末尾无 `\n` 先补一个）
- `title` 同步除了 `set_novel_source`，是否还要在下载完成路径上补一次（默认**不需要**：
  下载路径必经 `set_novel_source`）

## 9. 已由 human partner 拍板

| 决策 | 选择 |
|---|---|
| 结构 | `books.yaml`（书维度聚合）+ `search_history.jsonl`（append-only），而非按数据集拆多个文件 |
| 位置 | `app_data/config/library/`，而非 `config/` 根平铺 |
| `novel_id` 当 yaml key | 保持 `sha256(url)[:32]` |
| 可读性 | **加 `title` 字段，并保持最新**（每次 `set_novel_source` 从 `meta.title` 同步；手改无效） |
| 分组模型 | **多组**（忠实还原现有 `(组, 书)` 复合主键）；`groups` 用 **dict**（`{组名: {属性}}`），**不用列表**；`pending_export` 写在组下 |
| 搜索历史上限 | 保留最近 200 条，写入时裁 |
| 老数据 | 留一个 `scripts/migrate_user_data.py` 在仓库里 |
| 能手改 | 是——这决定一切成败（见 A3） |

## 10. 我替 human partner 做的判断（请检查）

1. **`search_history.jsonl` 保留整数 `id`**，不改成 `(source_name, keyword)` 做删除键。
   理由 C3：去 id 要动 API 契约和前端两个文件，而多一个整数字段对手改几乎无影响。
2. **丢掉 `novel_sources.updated_at` 与 `favorites.note`**：都无读方，留着是噪音。
3. **`bookmarks` 三个函数直接删**，不留"暂时保留"的半死接口。
4. **旧库备份落到 `config/library/user_data.db.migrated` 并删 `storage/users/`**：
   这样 G1 能验收，备份也还在同一个 `app_data/` 里。
5. **整份 yaml 解析失败 = 读写都抛 `LibraryCorruptError`**，绝不降级成空 dict。
   宁可书架页报错，也不能让下载热路径把账本重写成一条。
6. **`title` 在每次 `set_novel_source` 时从 `meta.title` 全量同步**（human partner
   2026-10-26 决定「保持最新」）：它是派生字段，手改无效。
7. **`add_novel_to_group` 保持原语义**（先移出其它组再加）：它的唯一调用点是
   "下载后入组"，不是"多组追加"。多组数据只由前端 `save_groups` 全量覆盖产生。
8. **`save_groups` 删 key 的判据是"整个条目 dict 为空"**，不是"没有已知字段"——
   后者会静默吃掉你手写的备注（A3）。

## 附录 A：同批完成的文档订正（2026-10-26）

`sites → sources` 改名那轮遗留的过时描述，与本设计的实现无关但同批处理：

| 文件 | 改了什么 |
|---|---|
| `docs/project/cli.md:21` | 「用户可逐能力覆盖（`{cap}.mode`）」→「用户层顶层整体覆盖，一个 mode 对四类能力全部生效」 |
| `docs/project/config.md:25` | 同上 |
| `docs/project/config.md:69` | 「api 源的能力段 `key`」→「api 源的顶层 `key`」（模板里本来就是顶层 `key: ''`） |
| `docs/project/sources.md:6` | 同上，并把失效的章节引用「mode 的用户覆盖」改为「用户层覆盖」（该章节实际叫「用户层覆盖」） |
| `docs/session-prompt.md:39` | 同上，并去掉「`common.mode` 并入各能力段」 |
| `docs/session-prompt.md:46` | 「顶层 `common` 段并入每个能力段（能力段覆盖 `common`…）」→「顶层字段即唯一一套参数（2026-10-25 起 `common` / 能力段已删除）」 |
| `template/config/sources/*.yaml`（7 个非 api 源） | 头部注释「该**书**的用户层配置（… 与逐能力段）」→「该**书源**的用户层配置（… / mode 与引擎字段）」 |

**澄清两处不该动的**（避免误修）：

- `shared/config.py:254` 的 `manifest["default_config"][cap]` **不是 bug**。`source.json`
  磁盘上没有 `default_config`，但 `build_manifest()` 在内存里把顶层字段展开成
  `default_config[cap]`（实测 `get_manifest()` 返回它，四类能力各一份）。AGENTS.md 的
  「无 `common` / `default_config`」说的是**磁盘 source.json 与用户层**没有这个段。
- `docs/project/updates.md`、`CHANGELOG.md`、`docs/superpowers/**` 里的同类描述是历史
  记录，保留原文（与改名那轮的约定一致）。

**`template/` 的处理**：删 `template/storage/`（含 `users/default/user_data.db`）、
删 `template/config/groups.yaml`、改 `template/config/sources/*.yaml` 的注释；
**不在 `template/config/library/` 放样板**——两个文件首次写入时自动创建，
`config init` 不接管它们。

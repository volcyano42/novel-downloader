# 用户数据拆成 books.yaml + search_history.jsonl 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `user_data.db` 的 5 张表迁移成 `app_data/config/library/` 下两个能手改的文本文件，让 `app_data/storage/` 只剩 `novels/`。

**Architecture:** `shared/user_data.py` 从 SQLite 后端换成"YAML 全量读写 + JSONL 追加"。公开函数签名与返回形状一个不改，所以 backend 路由、CLI 业务代码、前端零改动。`books.yaml` 承载书维度账本（分组/收藏/来源/书名），全量重写走"临时文件 + fsync + os.replace"；`search_history.jsonl` 只追加，读取时去重，超过 250 行压缩到 200 行。

**Tech Stack:** Python 3.14 / PyYAML（已有）/ `threading.Lock` / pytest

**Spec:** `docs/superpowers/specs/2026-10-26-user-data-to-files-design.md`

## Global Constraints

- 不引入新依赖（PyYAML 已在使用；不用 ruamel，因此**行内注释保不住**）
- backend 单进程（`backend/main.py:158` 的 `uvicorn.run(app)` 无 `workers`），并发保护只用**进程内** `threading.Lock`
- `novel_id` = `sha256(url)[:32]`（`novelbase/utils/urls.py:17`），全链不变
- 所有路径派生自 `shared.config.APP_DATA` / `CONFIG_DIR`，不写死、不用 `__file__` 推导（Nuitka onefile 下 `__file__` 在临时目录）
- 不留兼容代码：旧常量（`DB_PATH` / `GROUPS_YAML`）、旧 schema、`bookmarks` 三个函数全部删除
- 提交：中文消息，一个方面一条 commit，**禁止 `git add -A`**
- 测试基线：`python -m pytest tests/ -q` 应为 `553 passed, 1 failed`，那 1 个失败是
  `tests/test_encoding.py::test_detect_encoding_gbk`（chardet 把短 GBK 判成 `ibm855`），**与本次改动无关，不要试图修它**

## Review Focus

1. **`books.yaml` 里某个条目值是 `null`**（手写成 `n1:` 后面空着，或删字段时删过头）→ `_load_books()` 必须归一成 `{}`，否则后续 `.get("groups")` 抛 `AttributeError`
2. **手改时 key 写成裸 URL（含 `:`）** → YAML 解析失败 → 必须抛 `LibraryCorruptError` 且**绝不覆盖原文件**，用户才知道去修
3. **`search_history.jsonl` 末尾没有换行符** → 直接 append 会把新行拼到旧行尾部，产生一条坏行；追加前必须补 `\n`
4. **跨进程并发**（backend 与 `cli.py` 同时跑）→ 进程内 `_lock` 管不到，后写的覆盖先写的。单人项目接受此代价，但要在 `docs/project/config.md` 写明
5. **磁盘满 / 文件只读** → `_atomic_write` 抛 `OSError`，`.tmp` 残留；下一次写入要能容忍 `.tmp` 已存在

---

## File Structure

| 文件 | 责任 |
|---|---|
| `shared/user_data.py` | 全部存储逻辑（books 读写 + history 读写 + 原子写 + 锁 + 异常）。保持单文件：调用方依赖它的函数名，拆文件要加一层 re-export，不值得 |
| `scripts/migrate_user_data.py` | 一次性迁移：旧 SQLite → 两个文本文件 |
| `init_config.py` | 删掉 `init_user_db()` / `_user_db_target_dir()`（模板库没了） |
| `cli/main.py` | 删掉 `config init --user-db` |
| `template/storage/` | 整个删除 |
| `template/config/groups.yaml` | 删除 |

---

## Task 1: 文本存储基础设施 + 书维度（books.yaml）

**Files:**
- Modify: `shared/user_data.py`（新增常量/异常/原子写/锁/`_load_books`/`_dump_books`/`_read_title`；替换全部书维度函数；**保留** `DB_PATH`、`_connection`、`_SCHEMA_SQL` 与 history/bookmarks 旧实现，Task 2 才删）
- Test: `tests/test_library_books.py`（Create）
- Modify: `tests/test_shared_user_data.py`（只保留 history 部分，书维度测试移走）
- Modify: `tests/test_novel_source_writes.py`、`tests/test_storage_source_reads.py`、`tests/test_storage_source_write_route.py`、`tests/test_migrate_novel_sources.py`（隔离路径从 `DB_PATH` 改为 `BOOKS_PATH`）

**Interfaces:**

Produces（Task 2、4 依赖）：
```python
LIBRARY_DIR: Path          # CONFIG_DIR / "library"
BOOKS_PATH: Path           # LIBRARY_DIR / "books.yaml"
HISTORY_PATH: Path         # LIBRARY_DIR / "search_history.jsonl"   (Task 2 用)
NOVELS_DIR: Path           # APP_DATA / "storage" / "novels"
class LibraryCorruptError(RuntimeError)
_lock: threading.Lock
def _atomic_write(path: Path, text: str) -> None
def _load_books() -> dict[str, dict]
def _dump_books(books: dict) -> str
def _read_title(novel_id: str) -> str | None
```

书维度函数签名（**全部不变**，调用方依赖）：
```python
def load_groups() -> dict
def save_groups(groups: dict) -> None
def get_novel_group(novel_id: str) -> Optional[str]
def add_novel_to_group(novel_id: str, group: str) -> bool
def ensure_novel_in_group(novel_id: str) -> None
def load_favorites() -> list[str]
def add_favorite(novel_id: str) -> bool
def remove_favorite(novel_id: str) -> bool
def is_favorite(novel_id: str) -> bool
def set_novel_source(novel_id: str, source_name: str) -> None
def get_novel_source(novel_id: str) -> Optional[str]
def get_novel_sources(novel_ids: Sequence[str]) -> dict[str, str]
def delete_novel_source(novel_id: str) -> bool
```

- [ ] **Step 1: 写失败测试 `tests/test_library_books.py`**

隔离用 fixture（后续所有测试都用它）：
```python
import pytest
from shared import user_data

@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(user_data, "BOOKS_PATH", tmp_path / "library" / "books.yaml")
    monkeypatch.setattr(user_data, "HISTORY_PATH", tmp_path / "library" / "search_history.jsonl")
    monkeypatch.setattr(user_data, "NOVELS_DIR", tmp_path / "novels")
    return user_data
```

测试名与断言（每个都是一个 `def test_...`）：

| 测试名 | 断言 |
|---|---|
| `test_missing_file_reads_empty` | `load_groups() == {}`、`load_favorites() == []`、`get_novel_source("nope") is None` |
| `test_corrupt_file_raises_and_is_not_overwritten` | 写 `"::: not yaml :::"` → `load_groups()` 抛 `lib.LibraryCorruptError`；`add_favorite("n1")` 也抛；事后文件内容仍是原样 |
| `test_top_level_not_dict_raises` | 写 `"- a\n- b\n"` → `load_groups()` 抛 `LibraryCorruptError` |
| `test_null_entry_normalized_to_empty_dict` | 写 `"n1:\n"` → `load_favorites() == []`；`add_favorite("n1")` 不抛 `AttributeError` |
| `test_groups_roundtrip` | `add_novel_to_group("n1","default") is True`；`get_novel_group("n1") == "default"`；`load_groups() == {"default": {"n1": {}}}` |
| `test_add_novel_to_group_moves_out_of_other_groups` | A 组加入后：`add_novel_to_group("n1","A") is False`；`add_novel_to_group("n1","B") is True`；`load_groups() == {"B": {"n1": {}}}` |
| `test_multi_group_via_save_groups` | `save_groups({"A":{"n1":{"pending_export":True}}, "B":{"n1":{}}})` → `load_groups()` 原样还原两组 |
| `test_save_groups_keeps_favorite_and_source` | 先 `set_novel_source` + `add_favorite`，再 `save_groups({"G":{"n1":{}}})` → source 与 favorite 仍在 |
| `test_save_groups_drops_key_only_when_entry_empties` | `add_favorite("n1")` → `save_groups({})` → `is_favorite("n1") is True`（条目还在）；`remove_favorite("n1")` → `_load_books() == {}` |
| `test_unknown_fields_survive_rewrite` | 写入 `"n1:\n  note: 好看\n"` → `add_favorite("n1")` → `_load_books()["n1"]["note"] == "好看"` |
| `test_favorites_ordered_by_favorited_at_desc` | 收藏 a 再 b（`favorited_at` 用 monkeypatch 打桩成不同值）→ `load_favorites() == ["b","a"]` |
| `test_set_novel_source_skips_empty` | `set_novel_source("n1", "")` → `_load_books() == {}` |
| `test_set_novel_source_always_syncs_title` | 造 `novels/n1.db`（`meta(id,title)`，插「新书名」）→ `set_novel_source` → title 为「新书名」；改库为「改名后」再调 → title 变「改名后」 |
| `test_title_sync_tolerates_missing_novels_db` | 无 `novels/n1.db` → `set_novel_source` 不抛，`title` 不写 |
| `test_atomic_write_leaves_backup` | 两次写入后 `books.yaml.bak` 存在，且内容是**上一次**的 |
| `test_write_failure_leaves_original_intact` | 把 `LIBRARY_DIR` 设成不可写（`chmod 0o500`）→ `add_favorite` 抛 `OSError`，原 `books.yaml` 内容不变，且事后恢复权限能正常读（Review Focus 5）；用 `pytest.skip` 护栏跳过 root 运行 |
| `test_dump_has_header_and_field_order` | 生成的文件以 `#` 开头；同一本书同时有 groups/favorite/source 时，三者出现顺序为 `groups` → `favorite` → `source` |

- [ ] **Step 2: 跑测试，确认失败**

Run: `python -m pytest tests/test_library_books.py -q`
Expected: FAIL — `AttributeError: module 'shared.user_data' has no attribute 'LIBRARY_DIR'`（或 import 阶段就报）

- [ ] **Step 3: 实现基础设施**

`shared/user_data.py` 顶部（`from shared.config import APP_DATA` 之后）：

```python
from shared.config import APP_DATA, CONFIG_DIR

LIBRARY_DIR = CONFIG_DIR / "library"
BOOKS_PATH = LIBRARY_DIR / "books.yaml"
HISTORY_PATH = LIBRARY_DIR / "search_history.jsonl"
NOVELS_DIR = APP_DATA / "storage" / "novels"

_lock = threading.Lock()


class LibraryCorruptError(RuntimeError):
    """books.yaml 存在但不是合法 YAML dict。读写都抛，绝不降级成空 dict。"""
```

`_dump_books` 的字段顺序固定为 `title` → `groups` → `favorite` → `favorited_at` → `source` → 其它（未知字段按原插入序跟在后面），并注入固定头注释（内容见 spec §6.2 的示例注释块）。

`_atomic_write`（spec §6.5，含 `shutil.copy2` 留 `.bak`、`f.flush()` + `os.fsync()`、`os.replace()`；`.tmp` 用前先 `unlink(missing_ok=True)`）。

`_load_books`：文件不存在 → `{}`；`yaml.safe_load` 抛 `yaml.YAMLError` 或顶层不是 dict → `raise LibraryCorruptError(f"{BOOKS_PATH}: ...")`；**每个 value 为 `None` 的条目归一成 `{}`**（Review Focus 1）。

`_read_title(novel_id)`：`sqlite3.connect(f"file:{NOVELS_DIR / f'{novel_id}.db'}?mode=ro", uri=True)` 读 `meta.title`；库不存在 / 表不存在 / 任何 `sqlite3.Error` → `None`。

- [ ] **Step 4: 实现书维度函数**

按 spec §6.4 的映射表逐条实现。四个必须守住的点：

1. 所有读-改-写都在 `with _lock:` 内
2. `save_groups` 只重建 `groups` 字段，`title`/`favorite`/`favorited_at`/`source` 原样保留
3. 写完调 `_prune_empty(books)`：只删 `book == {}` 的 key（不是"没有已知字段"）
4. `set_novel_source` 在 `source_name` 非空时**总是**调 `_read_title()` 覆盖 `title`

- [ ] **Step 5: 跑测试，确认通过**

Run: `python -m pytest tests/test_library_books.py -q`
Expected: PASS（17 个）

- [ ] **Step 6: 把旧测试的隔离路径改到新常量**

- `tests/test_shared_user_data.py`：删掉 groups / favorites / source 相关用例（已由 `test_library_books.py` 覆盖），只留 search_history 的 3 个（Task 2 会再动）
- `tests/test_novel_source_writes.py`、`tests/test_storage_source_reads.py`、`tests/test_storage_source_write_route.py`、`tests/test_migrate_novel_sources.py`：把
  `monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")` 换成
  `monkeypatch.setattr(user_data, "BOOKS_PATH", tmp_path / "books.yaml")` +
  `monkeypatch.setattr(user_data, "NOVELS_DIR", tmp_path / "novels")`；
  顺带删掉同处的 `GROUPS_YAML` monkeypatch

- [ ] **Step 7: 跑全量测试**

Run: `python -m pytest tests/ -q`
Expected: `553 passed, 1 failed`（失败仍是 `test_encoding.py::test_detect_encoding_gbk`）

- [ ] **Step 8: Commit**

```bash
git add shared/user_data.py tests/test_library_books.py tests/test_shared_user_data.py \
  tests/test_novel_source_writes.py tests/test_storage_source_reads.py \
  tests/test_storage_source_write_route.py tests/test_migrate_novel_sources.py
git commit -m "refactor: 书维度数据改存 app_data/config/library/books.yaml"
```

---

## Task 2: 搜索历史（search_history.jsonl）+ 删除 SQLite 遗留

**Files:**
- Modify: `shared/user_data.py`（替换 4 个 history 函数；删除 `DB_PATH`、`_connection`、`_SCHEMA_SQL`、`_ensure_schema`、`_migrate_groups_yaml`、`GROUPS_YAML`、`bookmarks` 三个函数）
- Test: `tests/test_library_history.py`（Create）
- Modify: `tests/test_shared_user_data.py`（history 用例移走后可能变空 → 删除整个文件）
- Modify: `tests/test_paths.py`

**Interfaces:**
- Consumes: Task 1 的 `HISTORY_PATH`、`_lock`、`_atomic_write`
- Produces:
```python
_HISTORY_MAX_LINES = 250
_HISTORY_KEEP = 200
def get_search_history(limit: int = 50) -> list[dict]   # [{id, source_name, keyword, searched_at}]
def add_search_history(source_name: str, keyword: str) -> None
def delete_search_history(history_id: int) -> bool
def clear_search_history() -> None
```

- [ ] **Step 1: 写失败测试 `tests/test_library_history.py`**

用 Task 1 的 `lib` fixture（复制一份到本文件）。测试名与断言：

| 测试名 | 断言 |
|---|---|
| `test_empty_file_returns_empty_list` | `get_search_history() == []` |
| `test_append_and_read_back` | 加 2 条 → 返回 2 条，字段 `{id, source_name, keyword, searched_at}` 齐全 |
| `test_same_pair_appends_but_reads_once` | 同一 `(source, keyword)` 加两次 → 文件里 2 行；`get_search_history()` 只返回 1 条，且是**较晚**的 `searched_at` |
| `test_order_desc_and_limit` | 3 条不同时间 → 倒序；`get_search_history(limit=2)` 只回前 2 条 |
| `test_bad_json_line_skipped` | 文件里混入 `"not json"` 行 → 其他行正常返回，不抛 |
| `test_line_without_id_skipped` | `{"source_name":"a","keyword":"b","searched_at":"..."}` 无 `id` → 不返回该条 |
| `test_missing_trailing_newline_is_handled` | 手工写入不带末尾 `\n` 的一行 → 再 `add_search_history` → 两行都能读出来（Review Focus 3） |
| `test_delete_removes_all_rows_with_same_pair` | 同键 2 行 → `delete_search_history(id)` 后两者都消失 |
| `test_delete_unknown_id_returns_false` | `delete_search_history(999999) is False` |
| `test_clear_empties_file` | `clear_search_history()` → `get_search_history() == []`，文件存在且为 0 字节 |
| `test_compaction_keeps_latest_200` | monkeypatch `_HISTORY_MAX_LINES = 5`、`_HISTORY_KEEP = 3`；加 6 条不同关键词 → 文件行数 ≤ 5，读取仍返回 3 条最新的 |
| `test_ids_are_stable_across_compaction` | 压缩前后同一条历史的 `id` 不变 |

- [ ] **Step 2: 跑测试，确认失败**

Run: `python -m pytest tests/test_library_history.py -q`
Expected: FAIL（首次用 `_HISTORY_MAX_LINES` 时 `AttributeError`，或行为与断言不符）

- [ ] **Step 3: 实现**

- 读取：`splitlines()` → 逐行 `json.loads`，坏行/缺 `id`/`id` 非 int 一律 `continue`；按 `(source_name, keyword)` 去重保留 `searched_at` 最大者；按 `searched_at` 倒序；截 `limit`
- 追加：`LIBRARY_DIR.mkdir(parents=True, exist_ok=True)`；若文件存在且末尾无 `\n` 先补一个；`id = max(现有 id) + 1`（进程内缓存 `_next_id`，启动首次读文件算一次）；单行写入后计数 +1；超过 `_HISTORY_MAX_LINES` 触发压缩
- 压缩：去重后的最近 `_HISTORY_KEEP` 条 → `_atomic_write`
- 删除：读到目标 id → 取其 `(source_name, keyword)` → 过滤掉**所有**同键行 → `_atomic_write`；找不到返回 `False`
- 全部在 `with _lock:` 内

- [ ] **Step 4: 跑测试，确认通过**

Run: `python -m pytest tests/test_library_history.py -q`
Expected: PASS（12 个）

- [ ] **Step 5: 删除 SQLite 遗留**

删 `shared/user_data.py` 里的 `DB_PATH`、`GROUPS_YAML`、`_connection()`、`_SCHEMA_SQL`、`_ensure_schema()`、`_migrate_groups_yaml()`、`add_bookmark()`、`remove_bookmark()`、`get_bookmarks()`，以及不再使用的 `import sqlite3`（`_read_title` 仍需它，保留）和模块 docstring 里的 SQLite 描述。

- [ ] **Step 6: 更新 `tests/test_paths.py`**

`test_user_data_path_derives_from_app_data` 改为断言四个新常量：
```python
assert user_data.LIBRARY_DIR == tmp_path / "exe_app_data" / "config" / "library"
assert user_data.BOOKS_PATH == user_data.LIBRARY_DIR / "books.yaml"
assert user_data.HISTORY_PATH == user_data.LIBRARY_DIR / "search_history.jsonl"
assert user_data.NOVELS_DIR == tmp_path / "exe_app_data" / "storage" / "novels"
```

- [ ] **Step 7: 删除 `tests/test_shared_user_data.py`**

history 用例已迁到 `tests/test_library_history.py`，书维度在 `tests/test_library_books.py`，该文件剩下的内容全部重复。

- [ ] **Step 8: 跑全量测试**

Run: `python -m pytest tests/ -q`
Expected: `553 passed, 1 failed`（数量可能因删并测试浮动，关键是只有那 1 个 encoding 失败）

- [ ] **Step 9: Commit**

```bash
git add shared/user_data.py tests/test_library_history.py tests/test_paths.py tests/test_shared_user_data.py
git commit -m "refactor: 搜索历史改存 search_history.jsonl，删除 SQLite 后端"
```

---

## Task 3: 清理 init_config / CLI / template

**Files:**
- Modify: `init_config.py`（删 `init_user_db()`、`_user_db_target_dir()`，`init_all_config()` 去掉那一步）
- Modify: `cli/main.py`（删 `--user-db` 参数与相关分支）
- Delete: `template/storage/`（整个目录）、`template/config/groups.yaml`
- Delete: `tests/test_user_db_template.py`
- Modify: `tests/test_cli_effective_mode.py`

**Interfaces:**
- Consumes: 无
- Produces: `init_config` 只保留 `check_config` / `init_main_config` / `init_source_config` / `init_export_config` / `init_all_config`

- [ ] **Step 1: 改 `tests/test_cli_effective_mode.py` 并确认失败**

`test_config_init_*` 里 `Args` 类的 `user_db = False` 字段删掉；`init_user_db` 的 monkeypatch 删掉；期望的 `calls` 列表从 `["main", "sources:demo-r-default", "user-db"]` 改成 `["main", "sources:demo-r-default"]`。

Run: `python -m pytest tests/test_cli_effective_mode.py -q`
Expected: FAIL（`Args` 仍传 `user_db` 给 `cmd_config`，或 `calls` 多一项）

- [ ] **Step 2: 改 `cli/main.py`**

删 `cf_init.add_argument("--user-db", ...)`；`cmd_config` 里删 `args.user_db` 相关的互斥判断、`--user-db` 文案、`if args.user_db: continue`、末尾 `if args.user_db or (...)` 中的 `args.user_db` 分支（保留"无参 / --all 时补齐"的语义，但不再有 user_db 这一步）；`_scaffold_source` 与模块 docstring 里的用法行同步。

Run: `python -m pytest tests/test_cli_effective_mode.py -q`
Expected: PASS

- [ ] **Step 3: 改 `init_config.py`**

删 `init_user_db()` 与 `_user_db_target_dir()`；`init_all_config()` 去掉 `result.extend(init_user_db())`；docstring 里"四张空表"相关描述删掉。

- [ ] **Step 4: 删模板**

```bash
git rm -r template/storage
git rm template/config/groups.yaml
git rm tests/test_user_db_template.py
```

- [ ] **Step 5: 验证 CLI 与初始化**

Run:
```bash
python -c "import init_config; print(sorted(n for n in dir(init_config) if n.startswith('init_')))"
NLD_APP_DATA=$(mktemp -d) python cli.py config init --help
NLD_APP_DATA=$(mktemp -d) python cli.py config init
```
Expected: 第一行不含 `init_user_db`；`--help` 里没有 `--user-db`；`config init` 正常输出已初始化项，生成的目录里**没有** `storage/users/`

- [ ] **Step 6: 跑全量测试**

Run: `python -m pytest tests/ -q`
Expected: 只有 `test_encoding.py::test_detect_encoding_gbk` 失败

- [ ] **Step 7: Commit**

```bash
git add init_config.py cli/main.py tests/test_cli_effective_mode.py
git commit -m "refactor: 删除 user_data.db 模板与 config init --user-db"
```

（Step 4 的 `git rm` 已把删除暂存到 index，无需再 add）

---

## Task 4: 一次性迁移脚本

**Files:**
- Create: `scripts/migrate_user_data.py`
- Test: `tests/test_migrate_user_data.py`

**Interfaces:**
- Consumes: Task 1/2 的 `_dump_books` 语义、`LIBRARY_DIR`、`BOOKS_PATH`、`HISTORY_PATH`、`NOVELS_DIR`
- Produces: `def migrate(app_data: Path, apply: bool = False, force: bool = False) -> dict`
  返回 `{"books": int, "history": int, "skipped": str | None, "written": list[str]}`
  —— 测试直接调它，CLI 部分只做参数解析

- [ ] **Step 1: 写失败测试 `tests/test_migrate_user_data.py`**

夹具：在 `tmp_path` 下造一个最小旧库（复刻 Task 2 之前删掉的 schema，**在测试里内联建表 SQL**，不要 import 已删除的 `_SCHEMA_SQL`）：
- 3 本书：`n1` 只在 `default`；`n2` 同时在 `TEST` 和 `default`（`pending_export=1` 在 `TEST`）；`n3` 是孤儿（有 groups 行，无 `novel_sources`，无 `novels/n3.db`）
- `novel_sources`：`n1 → src-a`
- `favorites`：`n1`
- `search_history`：2 行
- `novels/n1.db`：`meta(id,title)` 含「书名一」

| 测试名 | 断言 |
|---|---|
| `test_dry_run_writes_nothing` | `apply=False` 后 `BOOKS_PATH` / `HISTORY_PATH` 都不存在；返回值里 counts 正确 |
| `test_apply_writes_both_files` | `books.yaml` 里 3 个 key；`n2.groups` 有两个组且 `TEST.pending_export is True`；`n1.title == "书名一"`；`n1.favorite is True`；`n1.source == "src-a"`；`n3` 无 `source`/`title` 但有 groups |
| `test_apply_migrates_all_history` | `search_history.jsonl` 两行、`id` 从 1 递增 |
| `test_apply_checkpoints_wal_first` | 造库后**不关 WAL 连接**就写入一条历史 → 迁移后该条出现在 jsonl（证明 `PRAGMA wal_checkpoint(TRUNCATE)` 生效） |
| `test_refuses_when_target_exists` | 先建空 `books.yaml` → `migrate(apply=True)` 返回 `skipped` 且不改动文件；`force=True` 才覆盖 |
| `test_apply_backs_up_and_removes_users_dir` | `apply=True` 后 `config/library/user_data.db.migrated` 存在；`APP_DATA/storage/users/` 不存在；`storage/novels/` 仍在 |
| `test_apply_is_idempotent_when_no_source_db` | 旧库不存在 → 不改任何文件，返回 `skipped` |

- [ ] **Step 2: 跑测试，确认失败**

Run: `python -m pytest tests/test_migrate_user_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.migrate_user_data'`

- [ ] **Step 3: 实现 `scripts/migrate_user_data.py`**

`migrate()` 的步骤（spec §6.7）：
1. 旧库路径 `app_data / "storage" / "users" / "default" / "user_data.db"`；不存在 → 返回 `skipped`
2. `sqlite3.connect(...)` → **`conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")`**（Review Focus / C4）
3. 读 4 张表；`groups` 按 `novel_id` 归并成 `{组名: {属性}}`
4. 每本书 `title` 用 `shared.user_data._read_title()` 取（`NOVELS_DIR` 由 `app_data` 参数临时覆盖）
5. `apply=False` 时只 count 并返回；`apply=True` 时：目标存在且非 `force` → `skipped`
6. 写两个文件（复用 `shared.user_data._dump_books` + 原子写）
7. 备份旧库到 `config/library/user_data.db.migrated` → 删 `app_data/storage/users/`
8. 自检并返回 `written`

CLI 部分：`argparse` 三个参数 `--app-data`（默认 `shared.config.APP_DATA`）、`--apply`、`--force`；`main()` 里打印摘要。

- [ ] **Step 4: 跑测试，确认通过**

Run: `python -m pytest tests/test_migrate_user_data.py -q`
Expected: PASS（7 个）

- [ ] **Step 5: 跑全量测试**

Run: `python -m pytest tests/ -q`
Expected: 只有 encoding 那 1 个失败

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_user_data.py tests/test_migrate_user_data.py
git commit -m "feat: 新增 user_data.db → 文本文件的一次性迁移脚本"
```

---

## Task 5: 本机实跑迁移并验收

**Files:**
- 无代码改动（这一步改的是 `app_data/` 里的真实数据，`app_data/` 被 gitignore）

**Interfaces:**
- Consumes: Task 4 的 `scripts/migrate_user_data.py`

- [ ] **Step 1: 记下迁移前基线**

Run:
```bash
python -c "
import sqlite3
c = sqlite3.connect('app_data/storage/users/default/user_data.db')
for t in ('groups','favorites','search_history','novel_sources'):
    print(t, c.execute(f'select count(*) from {t}').fetchone()[0])
"
```
Expected: `groups 103` / `favorites 1` / `search_history 10` / `novel_sources 102`（若数字不同，以此处实际值为新基线）

- [ ] **Step 2: dry-run**

Run: `python scripts/migrate_user_data.py`
Expected: 打印条数与 `apply` 提示，`app_data/config/library/` 未被创建

- [ ] **Step 3: 正式迁移**

Run: `python scripts/migrate_user_data.py --apply`
Expected: 写出 `app_data/config/library/books.yaml` 与 `search_history.jsonl`；旧库备份为 `user_data.db.migrated`；`app_data/storage/users/` 消失

- [ ] **Step 4: 验收数据完整性**

Run:
```bash
python -c "
import yaml
d = yaml.safe_load(open('app_data/config/library/books.yaml', encoding='utf-8'))
print('books:', len(d))
print('组关系:', sum(len(b.get('groups') or {}) for b in d.values()))
print('有 source:', sum(1 for b in d.values() if b.get('source')))
print('有 title:', sum(1 for b in d.values() if b.get('title')))
print('favorite:', sum(1 for b in d.values() if b.get('favorite')))
"
wc -l app_data/config/library/search_history.jsonl
```
Expected: `books: 102`、`组关系: 103`、`有 source: 102`、`有 title` ≈ 102（孤儿书无库，可少于 102）、`favorite: 1`、历史文件 10 行

- [ ] **Step 5: 验收 G1（storage 只剩 novels）**

Run: `ls app_data/storage/`
Expected: 只有 `novels`（`sync.ffs_db` 若仍在，人工删除，代码不碰）

- [ ] **Step 6: 端到端冒烟**

Run:
```bash
python cli.py sources list | head -3
python -c "
from shared.user_data import load_groups, load_favorites, get_search_history
g = load_groups(); print('groups:', len(g), 'default:', len(g.get('default', {})))
print('favorites:', load_favorites()[:3])
print('history:', len(get_search_history()))
"
```
Expected: 无异常；分组与收藏数量与 Step 4 一致

- [ ] **Step 7: 无 commit**

这一步不改仓库文件。把 Step 4/5 的实际数字写进交付汇报。

---

## Task 6: 文档

**Files:**
- Modify: `docs/project/config.md`（配置文件清单、新增「书维度账本」一节）
- Modify: `docs/project/overview.md`（目录树）
- Modify: `docs/project/sources.md`（如提及用户数据位置）
- Modify: `docs/README.md`（索引行）
- Modify: `AGENTS.md`（`app_data/config/` 的约定：YAML + jsonl；`storage/` 只剩 `novels/`）

**Interfaces:** 无

- [ ] **Step 1: 更新 `docs/project/config.md`**

新增一节「`library/books.yaml` 与 `library/search_history.jsonl`」，写清：
- 文件形状与字段表（照 spec §6.2 / §6.3）
- `title` 是派生字段，每次 `set_novel_source` 从 `meta.title` 同步，手改无效
- `groups` 是 dict，一本书可属多组；`pending_export` 是组级属性
- 搜索历史 append-only、读取时去重、>250 行压缩到 200 行
- **已知边界**：进程内 `threading.Lock` 不跨进程 —— backend 与 CLI 同时写会后者覆盖前者
- 手改坏文件（YAML 不合法）会让书架接口报错，程序**不会**用空数据覆盖它

- [ ] **Step 2: 更新目录树与约定**

`docs/project/overview.md` 的 `app_data/` 树加 `config/library/`，删 `storage/users/`；
`AGENTS.md` 的「配置」约定把「全部 YAML」改为「YAML 配置 + `library/` 下的账本（yaml/jsonl）」。

- [ ] **Step 3: 校验文档与实现一致**

Run:
```bash
grep -rn "user_data.db\|storage/users" AGENTS.md docs/project docs/README.md | grep -v updates.md
```
Expected: 无输出（历史文档 `docs/project/updates.md` 与 `docs/superpowers/**` 除外）

- [ ] **Step 4: 跑全量测试**

Run: `python -m pytest tests/ -q`
Expected: 只有 `test_encoding.py::test_detect_encoding_gbk` 失败

- [ ] **Step 5: Commit**

```bash
git add docs/project/config.md docs/project/overview.md docs/project/sources.md docs/README.md AGENTS.md
git commit -m "docs: 记录 books/search_history 账本格式与 storage 收缩"
```

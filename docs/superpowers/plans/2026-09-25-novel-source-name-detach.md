# Novel.source_name 剥离 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把来源元数据从 `novelbase` 的 `Novel` 模型移出，改由 `user_data.db` 的 `novel_sources` 表承载，并一次性迁移存量数据。

**Architecture:** 三层改动，彼此独立可测：① `shared/user_data.py` 加表与 CRUD（数据层）；② `novelbase` 删 `Novel.source_name` 字段与 `extra["platform"]` 写入（模型层，纯删除）；③ 调用方在「下载完成 / 删书」时写入或清理（接入层）；另加一个幂等迁移脚本搬运存量。

**Tech Stack:** Python 3.10+ / SQLite（`sqlite3` 标准库）/ pytest 9.1.1 / FastAPI / argparse CLI。

**设计依据：** `docs/superpowers/specs/2026-09-25-novel-source-name-detach-design.md`

## Global Constraints

- **不建 `Book` 领域对象**（该方向已废弃）。
- **不新增 API / 前端读点**：`NovelMeta` 本就不含 `source_name`，本轮契约零变化。
- **不改** `SearchResult.source_name`、搜索历史、`bookmarks.platform`。
- **不动公开库** `novel-crawler`（本计划只涉及 `novel-downloader`）。
- **不兼容旧格式**：小说库 JSON 里遗留的 `source_name` 不再被读取（`Novel.loads(**kwargs)` 会把它 `setattr` 成游离实例属性，无害，不做特殊处理）。
- **测试基线**：`python -m pytest tests -q` 在改动前应为 **401 passed, 1 skipped**；每个 Task 结束必须 **0 failed**。
- **Git**：中文提交消息；一个方面一条 commit；**禁止 `git add -A`**（显式列文件）；`dev` 分支提交已授权，**不 push**。中文消息用文件传入：`git commit -F -`（heredoc）或 `-F <file>`，**不要** `git commit -m "中文…"`。
- **每个 Task 的验证命令在仓库根** `D:\Linux\novel-downloader\novel-downloader` 执行。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `shared/user_data.py` | 修改 | 新增 `novel_sources` 表 + 4 个 CRUD 函数（来源的唯一归属地） |
| `tests/test_shared_user_data.py` | 修改 | 追加 `novel_sources` 的 CRUD 与边界用例 |
| `novelbase/models/novel.py` | 修改 | 删除 `Novel.source_name` 字段 |
| `novelbase/core/downloader.py` | 修改 | 删除 `novel.extra["platform"] = source_name` |
| `tests/test_models.py` | 修改 | 断言 `Novel` 不再有该字段 |
| `backend/services/task_manager.py` | 修改 | 下载完成后写来源 |
| `cli/core.py` | 修改 | CLI 下载完成后写来源 |
| `backend/routers/storage.py` | 修改 | 删书时清理来源 |
| `tests/test_novel_source_writes.py` | 创建 | 断言删书端点清理了 `novel_sources`、CLI 下载写入了来源 |
| `scripts/migrate_novel_sources.py` | 创建 | 幂等迁移存量来源 |
| `tests/test_migrate_novel_sources.py` | 创建 | 迁移正确性 + 幂等 |

任务依赖：T1 独立；T2 独立；T3 依赖 T1；T4 依赖 T1 + T2。

---

### Task 1: `user_data` 新增 `novel_sources` 表与 CRUD

**Files:**
- Modify: `shared/user_data.py`（`_SCHEMA_SQL` 加表；文件末尾追加一组函数）
- Test: `tests/test_shared_user_data.py`

**Interfaces:**
- Consumes: 现有 `_connection()`（`shared/user_data.py:19`，每次新建连接 + 幂等建表）
- Produces:
  - `set_novel_source(novel_id: str, source_name: str) -> None`
  - `get_novel_source(novel_id: str) -> Optional[str]`
  - `get_novel_sources(novel_ids: Sequence[str]) -> dict[str, str]`
  - `delete_novel_source(novel_id: str) -> bool`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_shared_user_data.py` 末尾：

```python
def test_novel_source_set_get_upsert(tmp_path, monkeypatch):
    """set 写入、get 读回、同 id 再 set 为 UPSERT 覆盖。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    assert user_data.get_novel_source("n1") is None
    user_data.set_novel_source("n1", "fanqie-api-rain")
    assert user_data.get_novel_source("n1") == "fanqie-api-rain"

    user_data.set_novel_source("n1", "qimao-api-rain")   # UPSERT 覆盖
    assert user_data.get_novel_source("n1") == "qimao-api-rain"


def test_novel_source_skips_empty(tmp_path, monkeypatch):
    """空 source_name 不写行，避免无来源的孤儿记录。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.set_novel_source("n1", "")
    assert user_data.get_novel_source("n1") is None


def test_novel_sources_batch_only_hits(tmp_path, monkeypatch):
    """批量查询只返回命中的 id。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.set_novel_source("n1", "fanqie-api-rain")
    user_data.set_novel_source("n2", "qimao-api-rain")
    assert user_data.get_novel_sources(["n1", "n2", "n3"]) == {
        "n1": "fanqie-api-rain",
        "n2": "qimao-api-rain",
    }
    assert user_data.get_novel_sources([]) == {}


def test_novel_source_delete(tmp_path, monkeypatch):
    """删书清理：删掉返回 True，重复删返回 False。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.set_novel_source("n1", "fanqie-api-rain")
    assert user_data.delete_novel_source("n1") is True
    assert user_data.delete_novel_source("n1") is False
    assert user_data.get_novel_source("n1") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_shared_user_data.py -q -k novel_source`
Expected: FAIL —— `AttributeError: module 'shared.user_data' has no attribute 'set_novel_source'`

- [ ] **Step 3: 实现**

在 `shared/user_data.py` 顶部 import 区补 `Sequence`（若已有 `from typing import Optional`，另起一行）：

```python
from collections.abc import Sequence
```

在 `_SCHEMA_SQL` 的 `bookmarks` 表之后、结尾 `"""` 之前追加：

```sql

    CREATE TABLE IF NOT EXISTS novel_sources (
        novel_id     TEXT PRIMARY KEY,
        source_name  TEXT NOT NULL,
        updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
```

在文件末尾追加：

```python

# ═══════════════════════════════ Novel Sources ═══════════════════════════════

def set_novel_source(novel_id: str, source_name: str) -> None:
    """记录某本书的来源（UPSERT）。空 source_name 跳过，不建孤儿行。"""
    if not source_name:
        return
    conn = _connection()
    conn.execute(
        """INSERT INTO novel_sources(novel_id, source_name, updated_at)
           VALUES (?, ?, datetime('now','localtime'))
           ON CONFLICT(novel_id)
           DO UPDATE SET source_name = excluded.source_name,
                         updated_at  = datetime('now','localtime')""",
        (novel_id, source_name),
    )
    conn.commit()


def get_novel_source(novel_id: str) -> Optional[str]:
    """返回该书来源；无记录返回 None。"""
    conn = _connection()
    row = conn.execute(
        "SELECT source_name FROM novel_sources WHERE novel_id = ?", (novel_id,)
    ).fetchone()
    return row["source_name"] if row else None


def get_novel_sources(novel_ids: Sequence[str]) -> dict[str, str]:
    """批量查询（供列表 join 用）。只返回命中的 id；空输入返回 {}。"""
    ids = list(novel_ids)
    if not ids:
        return {}
    conn = _connection()
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT novel_id, source_name FROM novel_sources WHERE novel_id IN ({marks})",
        ids,
    ).fetchall()
    return {r["novel_id"]: r["source_name"] for r in rows}


def delete_novel_source(novel_id: str) -> bool:
    """删书时清理。返回 True 表示确实删除了。"""
    conn = _connection()
    cur = conn.execute("DELETE FROM novel_sources WHERE novel_id = ?", (novel_id,))
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_shared_user_data.py -q`
Expected: PASS（原有 5 个 + 新增 4 个）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: `405 passed, 1 skipped`（基线 401 + 新增 4），0 failed

- [ ] **Step 6: 提交**

```bash
git add shared/user_data.py tests/test_shared_user_data.py
git commit -F - <<'EOF'
feat(user_data): 新增 novel_sources 表承载书源来源

Novel 的来源改由 user_data.db 承载（设计见
docs/superpowers/specs/2026-09-25-novel-source-name-detach-design.md）。
set / get / get_many / delete 四个函数；空 source_name 跳过不写行。
EOF
```

---

### Task 2: 从 `Novel` 剥离 `source_name` 与 `extra["platform"]`

**Files:**
- Modify: `novelbase/models/novel.py:287-288`
- Modify: `novelbase/core/downloader.py:64`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: 无
- Produces: `Novel` 不再有 `source_name` 字段；`resolve_meta` 签名不变（来源仍由参数注入）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_models.py`：

```python
def test_novel_has_no_source_name_field():
    """Novel 只存纯小说数据：不再有 source_name 字段。"""
    import dataclasses
    assert "source_name" not in {f.name for f in dataclasses.fields(Novel)}


def test_novel_loads_tolerates_legacy_source_name():
    """旧库 JSON 残留的 source_name 不会让 loads 抛错。

    它只经 `Novel.loads(**kwargs)` 的 setattr 落到**游离实例属性**上，
    不属于 dataclass 字段，故不进入数据契约。
    """
    import dataclasses
    n = Novel.loads(title="t", url="https://x/y", id="abc", serial=1,
                    author="a", description="d", source_name="fanqie-api-rain")
    assert n.title == "t"
    assert n.source_name == "fanqie-api-rain"      # 游离属性存在（旧数据被兜住）
    assert "source_name" not in {f.name for f in dataclasses.fields(Novel)}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_models.py -q -k source_name`
Expected: `test_novel_has_no_source_name_field` FAIL（字段还在）；`tolerates` 那条此时应已 PASS

- [ ] **Step 3: 实现**

`novelbase/models/novel.py`：删除

```python
    # 书源系统级 id（如 92xs-requests-default）；空 = 旧数据或来源未知
    source_name: str = ""
```

`novelbase/core/downloader.py`：删除 `resolve_meta` 内的

```python
    novel.extra["platform"] = source_name
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_models.py -q`
Expected: PASS

- [ ] **Step 5: 全量回归 + 硬约束检查**

Run: `python -m pytest tests -q`
Run: `grep -rn "source_name" novelbase/models/novel.py novelbase/core/downloader.py`
Expected: 测试全绿；grep 在 `download.py` 只剩 `resolve_meta`/`resolve_chapter_list`/`resolve_chapter` 的**参数**，`novel.py` 无命中

- [ ] **Step 6: 提交**

```bash
git add novelbase/models/novel.py novelbase/core/downloader.py tests/test_models.py
git commit -F - <<'EOF'
refactor(novelbase): 剥离 Novel.source_name 与 extra["platform"]

Novel 回到「纯小说数据」；来源元数据不再进入核心模型。来源本由
resolve_meta(url, source_name, engines) 参数注入，novelbase 内部从不读该字段，
故为纯删除（API 契约零变化）。旧 JSON 残留字段由 loads(**kwargs) 兜住，不报错。
EOF
```

---

### Task 3: 接入写入点（下载完成 / 删书）

**Files:**
- Modify: `backend/services/task_manager.py:63-69`
- Modify: `cli/core.py:132-135`
- Modify: `backend/routers/storage.py:132-137`
- Test: `tests/test_novel_source_writes.py`

**Interfaces:**
- Consumes: `shared.user_data.set_novel_source(novel_id, source_name)` / `delete_novel_source(novel_id)`（Task 1）
- Produces: 来源在下载完成时落库；删书时清理

- [ ] **Step 1: 写失败测试（删书清理 + CLI 写入）**

新建 `tests/test_novel_source_writes.py`：

```python
"""写入点覆盖：删书端点清理来源、CLI 下载流程写入来源。"""
import asyncio

import pytest
from fastapi import HTTPException

from cli import core as cli_core
from novelbase.models.novel import Chapter, Chapters, Novel
from shared import user_data
from backend.routers import storage as storage_router


@pytest.fixture
def isolated_user_db(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    return user_data


def test_delete_novel_cleans_novel_sources(monkeypatch, isolated_user_db):
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")

    class FakeStore:
        def load_meta(self, novel_id):
            return object() if novel_id == "n1" else None

        def delete_novel(self, novel_id):
            return None

    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore())
    asyncio.run(storage_router.delete_novel("n1"))
    assert isolated_user_db.get_novel_source("n1") is None


def test_delete_unknown_novel_404(monkeypatch, isolated_user_db):
    class FakeStore:
        def load_meta(self, novel_id):
            return None

    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore())
    with pytest.raises(HTTPException) as ei:
        asyncio.run(storage_router.delete_novel("nope"))
    assert ei.value.status_code == 404


def test_cli_download_writes_novel_source(monkeypatch, isolated_user_db):
    """CLI 下载流程走到写入点即应落库。

    让 storage.load_chapters 返回「章节已存在」，从而在写入点之后的
    `if not to_download: return` 处提前返回 —— 无需进入真实下载循环。
    """
    novel = Novel(title="t", url="https://x/n1", id="n1", serial=1,
                  author="a", description="d")
    ch = Chapter(id="c1", url="https://x/n1/c1", novel_id="n1",
                 title="第一章", order=1)

    async def fake_resolve_meta(url, source_name, engines, **kw):
        return novel

    async def fake_resolve_chapter_list(url, source_name, engines, **kw):
        return Chapters([ch])

    class FakeStorage:
        def save_meta(self, n):
            return None

        def load_chapters(self, novel_id):
            return [ch]                      # 章节已在 → to_download 为空 → 提前返回

    monkeypatch.setattr(cli_core, "resolve_meta", fake_resolve_meta)
    monkeypatch.setattr(cli_core, "resolve_chapter_list", fake_resolve_chapter_list)
    monkeypatch.setattr(cli_core, "_get_storage", lambda: FakeStorage())
    monkeypatch.setattr(cli_core, "add_novel_to_group", lambda nid, grp: None)

    asyncio.run(cli_core._do_download_inner(
        "fanqie-api-rain", "https://x/n1", "default", {}))

    assert isolated_user_db.get_novel_source("n1") == "fanqie-api-rain"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_novel_source_writes.py -q`
Expected: `test_delete_novel_cleans_novel_sources` 与 `test_cli_download_writes_novel_source` FAIL（来源既未写入也未清理）；`test_delete_unknown_novel_404` 应已 PASS

- [ ] **Step 3: 实现（三处接入）**

`backend/routers/storage.py`：文件顶部 import 区加

```python
from shared.user_data import delete_novel_source
```

`delete_novel` 改为：

```python
@router.delete("/novel/{novel_id}")
async def delete_novel(novel_id: str):
    store = _get_storage()
    if not store.load_meta(novel_id): raise HTTPException(404, "小说不存在")
    store.delete_novel(novel_id)
    delete_novel_source(novel_id)
    return {"status": "deleted", "novel_id": novel_id}
```

`backend/services/task_manager.py`：文件顶部 import 区加

```python
from shared.user_data import set_novel_source
```

`_run_download` 中，`store.save_meta(meta)` 之后（该行在 `novel_url` 分支内）追加：

```python
                set_novel_source(task["novel_id"], source_name)
```

即改为：

```python
        novel_url = task.get("novel_url", "")
        if novel_url:
            try:
                meta = await resolve_meta(novel_url, source_name, engines)
                store.save_meta(meta)
                set_novel_source(task["novel_id"], source_name)
            except Exception:
                _log.warning("fetch_meta failed for %s", novel_url, exc_info=True)
```

`cli/core.py`：`_do_download_inner` 中 `add_novel_to_group(novel_id, group)`（`:135`）之后追加：

```python
    from shared.user_data import set_novel_source
    set_novel_source(novel_id, source_name)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_novel_source_writes.py -q`
Expected: PASS（3 passed）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: `410 passed, 1 skipped`，0 failed

- [ ] **Step 6: 提交**

```bash
git add backend/routers/storage.py backend/services/task_manager.py cli/core.py tests/test_novel_source_writes.py
git commit -F - <<'EOF'
feat: 下载完成时写入来源、删书时清理

- backend/services/task_manager.py：_run_download 在 save_meta 后
  set_novel_source(task["novel_id"], source_name)
- cli/core.py：_do_download_inner 在 add_novel_to_group 后同样写入
- backend/routers/storage.py：DELETE /novel/{id} 调 delete_novel_source 清理孤儿行
EOF
```

---

### Task 4: 存量迁移脚本

**Files:**
- Create: `scripts/migrate_novel_sources.py`
- Test: `tests/test_migrate_novel_sources.py`

**Interfaces:**
- Consumes: `user_data.set_novel_source`（Task 1）；`Novel` 无 `source_name` 字段但旧数据会 `setattr` 成游离属性（Task 2）
- Produces: `migrate(novels) -> tuple[int, int]`（迁移数, 跳过数），供测试直接调用

- [ ] **Step 1: 写失败测试**

新建 `tests/test_migrate_novel_sources.py`：

```python
"""存量来源迁移：正确搬运 + 幂等。"""
from novelbase.models.novel import Novel
from shared import user_data


def _fake_novel(novel_id: str, source_name: str) -> Novel:
    n = Novel(title="t", url=f"https://x/{novel_id}", id=novel_id,
              serial=1, author="a", description="d")
    n.source_name = source_name          # 模拟旧 JSON 残留的游离属性
    return n


def test_migrate_moves_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    from scripts import migrate_novel_sources as m
    novels = [
        _fake_novel("n1", "fanqie-api-rain"),
        _fake_novel("n2", "qimao-api-rain"),
        _fake_novel("n3", ""),           # 无来源 → 跳过
    ]

    moved, skipped = m.migrate(novels)
    assert (moved, skipped) == (2, 1)
    assert user_data.get_novel_source("n1") == "fanqie-api-rain"
    assert user_data.get_novel_source("n3") is None

    # 幂等：再跑一遍，值不变、仍报同样统计
    moved2, skipped2 = m.migrate(novels)
    assert (moved2, skipped2) == (2, 1)
    assert user_data.get_novel_source("n1") == "fanqie-api-rain"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_migrate_novel_sources.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'scripts.migrate_novel_sources'`

- [ ] **Step 3: 实现**

新建 `scripts/migrate_novel_sources.py`：

```python
"""把小说库里遗留的 Novel.source_name 迁移到 user_data.db 的 novel_sources。

幂等：可重复执行，已存在的行按最新值 UPSERT。

不复用 scripts/migrate_storage.py —— 那是文件布局迁移（storage/*.db →
storage/novels/），与此处的内容迁移职责无关。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:          # 允许 `python scripts/migrate_novel_sources.py`
    sys.path.insert(0, str(ROOT))

from novelbase.core.options import StorageOptions      # noqa: E402
from novelbase.core.storage import create_storage      # noqa: E402
from shared.config import get_database_url             # noqa: E402
from shared.user_data import set_novel_source          # noqa: E402


def migrate(novels) -> tuple[int, int]:
    """搬运一批 Novel 的来源。返回 (迁移数, 跳过数)。"""
    moved = skipped = 0
    for novel in novels:
        source_name = getattr(novel, "source_name", "") or ""
        if not source_name:
            skipped += 1
            continue
        set_novel_source(novel.id, source_name)
        moved += 1
    return moved, skipped


def main() -> None:
    storage = create_storage(StorageOptions(backend="sqlite",
                                            database_url=get_database_url()))
    moved, skipped = migrate(list(storage.iter_metas()))
    print(f"完成：迁移 {moved} 条，跳过 {skipped} 条（无来源）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_migrate_novel_sources.py -q`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: `411 passed, 1 skipped`，0 failed

- [ ] **Step 6: 提交**

```bash
git add scripts/migrate_novel_sources.py tests/test_migrate_novel_sources.py
git commit -F - <<'EOF'
feat(scripts): 新增存量来源迁移脚本 migrate_novel_sources

把小说库里遗留的 Novel.source_name 搬进 user_data.db 的 novel_sources，
幂等可重跑；无来源的书跳过。不兼容旧格式（迁移后不再读小说库里的该字段）。
EOF
```

---

## 完成后验证

- [ ] `python -m pytest tests -q` → **411 passed, 1 skipped**，0 failed
- [ ] `grep -rn "source_name" novelbase/models/novel.py` → 无命中（模型已纯净）
- [ ] `grep -rn "extra\[\"platform\"\]" novelbase/ backend/ cli/` → 无命中（冗余已清）
- [ ] `git status --porcelain` → clean
- [ ] 抽查：`python scripts/migrate_novel_sources.py` 后，随便挑 3 本书
      `python -c "from shared.user_data import get_novel_source as g; print(g('<id>'))"`
      能查到非空来源

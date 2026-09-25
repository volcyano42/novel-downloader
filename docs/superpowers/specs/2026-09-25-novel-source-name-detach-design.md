# Novel.source_name 剥离 —— 设计

> 2026-09-25。把「来源」（`source_name`）从 `novelbase` 的 `Novel` 模型移出，
> 改由 `shared/user_data.py` 的 `user_data.db` 承载。

## 背景

`Novel` 的定位是「纯小说数据」（书名 / 作者 / 简介 / 章节 / 插图等），但书源扁平化重构
（2026-09-24）在它上面加了 `source_name` 字段（`novelbase/models/novel.py:288`），
破坏了这一定位。同时为数据兼容保留了 `novel.extra["platform"]`
（`novelbase/core/downloader.py:64`），与 `source_name` 值重复。

## 现状调查（2026-09-25 实测）

| 事实 | 证据 |
|---|---|
| `Novel.source_name` **有 2 处真实读点** | `cli/core.py:264` 与 `cli/interactive.py:169` 的 `getattr(novel, "source_name", "")` —— 二者是「更新已有小说」取书源建引擎的**唯一来源**。初稿 grep `.source_name` 漏掉了这种字符串形式，故误判为「零读点」；本设计**必须**改造这两处，否则更新功能整体跳过 |
| `Novel.extra["platform"]` **只写不读** | 仅 `novelbase/core/downloader.py:64` 一处写入 |
| API 不返回该字段 | `backend/routers/storage.py:58` 经 `_novel_to_meta()` → `NovelMeta`，其中不含 `source_name` |
| 前端所有 `source_name` 用法属搜索 | `SearchResult.source_name`（按源分 tab）、`/history/search` |
| `novelbase` 内部不依赖该字段 | `resolve_meta(url, source_name, engines, …)` 由**参数**注入来源，从不读 `Novel.source_name` |

结论：剥离**没有消费方**，是纯粹的 schema 清理；API / 前端契约零变化。

## 目标

1. `Novel` 回到「纯小说数据」：不含来源元数据
2. 来源数据有明确归属：`user_data.db`（用户态库，与收藏 / 分组 / 书签同库）
3. 存量数据一次性迁移；迁移后**不保留**旧格式的兼容路径

## 非目标（YAGNI，明确不做）

- 不新建 `Book` 领域对象（该方向已废弃）
- 不新增 API / 前端读点；但 **CLI 既有的 2 处读点必须改造**（`cli/core.py`、`cli/interactive.py` 的更新路径）—— 那不是「接新消费方」，是保住既有功能
- 不改 `SearchResult.source_name`（有真实消费方，语义是「搜索结果的即时标签」）
- 不动搜索历史、`bookmarks.platform`
- 不动公开库 `novel-crawler`

## 设计

### 1. 数据层 —— `shared/user_data.py`

新增表（加入 `_SCHEMA_SQL`，由 `_ensure_schema` 幂等建表）：

```sql
CREATE TABLE IF NOT EXISTS novel_sources (
    novel_id     TEXT PRIMARY KEY,      -- = sha256(url)[:32]
    source_name  TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

新增函数：

| 函数 | 职责 |
|---|---|
| `set_novel_source(novel_id, source_name) -> None` | UPSERT（`ON CONFLICT(novel_id) DO UPDATE`），刷新 `updated_at` |
| `get_novel_source(novel_id) -> str \| None` | 单条查询；无记录返回 `None` |
| `get_novel_sources(novel_ids) -> dict[str, str]` | 批量查询（给将来的列表 join 留口） |
| `delete_novel_source(novel_id) -> bool` | 删书时清理，避免孤儿行 |

### 2. 模型层 —— `novelbase`

- `novelbase/models/novel.py`：删除 `Novel.source_name` 字段（`:287-288`）
- `novelbase/core/downloader.py`：删除 `:64` 的 `novel.extra["platform"] = source_name`
- `resolve_meta` / `resolve_chapter_list` / `resolve_chapter` 签名**不变**
- `novelbase` 不再感知「书库来源」概念；来源由调用方持有（本就在调用方手上）

### 3. 写入点与读点

| 位置 | 时机 | 动作 |
|---|---|---|
| `backend/services/task_manager.py::_run_download` | 下载完成 | `set_novel_source(novel_id, source_name)` |
| `cli/main.py::cmd_download` | 下载完成 | 同上 |
| `backend/routers/storage.py` 的 `DELETE /novel/{id}` | 删书 | `delete_novel_source(novel_id)` |

读点（改造既有 `getattr` 读法）：

| 位置 | 时机 | 动作 |
|---|---|---|
| `cli/core.py:264`（`do_update`） | 更新已有小说 | `getattr(novel, "source_name", "")` → `get_novel_source(novel.id)` |
| `cli/interactive.py:169`（`_update_one_async`） | 同上 | 同上 |

### 4. 存量迁移 —— 新增 `scripts/migrate_novel_sources.py`

> 不复用现有的 `scripts/migrate_storage.py`：那是**文件布局**迁移
> （`storage/*.db` → `storage/novels/`、`user_data.db` → `storage/users/default/`），
> 与本步的数据内容迁移职责无关。

迁移步骤：

1. 遍历小说库 `app_data/storage/novels/<id>.db` 的 meta 记录，取旧 `source_name` 值（仅当非空）
2. 写入 `app_data/storage/users/default/user_data.db` 的 `novel_sources`
3. **幂等**：可重复执行，已存在的行按最新值 UPSERT
4. 输出统计（迁移 N 条 / 跳过 M 条）

### 5. 数据流

```
下载：用户选书源 → resolve_meta(url, source_name, engines) → Novel（不含来源）
      → 存小说库；同时 set_novel_source(novel_id, source_name) → user_data.db

读取：storage 读 Novel（纯小说数据）
      + user_data.get_novel_source(novel_id)   ← CLI 更新路径本轮已接
      （API / 前端仍不返回来源，留给后续）
```

### 6. 错误处理

- `set_novel_source` 传空 `source_name`：**跳过写入**（不建无来源的行）
- `get_novel_source` 未命中：返回 `None`（不抛异常）
- 迁移遇旧格式（`source_name` 缺失 / 为空）：跳过该本，不写行
- 旧 JSON 里残留的 `source_name` 会被 `Novel.loads(**kwargs)` `setattr` 成游离实例属性 —— 无害，不做特殊处理

### 7. 测试

- `tests/test_user_data_novel_sources.py`（新增）：`set` / `get` / `get_many` / `delete` 的 CRUD、UPSERT 覆盖、空值跳过、未命中返回 `None`
- `tests/test_models.py`：新增断言 `Novel` 不再有 `source_name` 字段（用 `dataclasses.fields`）
- 迁移幂等：连跑两遍结果一致
- `python -m pytest tests -q` 全绿（基线 401 passed / 1 skipped）

## 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 静默丢来源 | 剥离后若写入点漏了，来源再无别处可查 | 迁移与写入点都要有单测；验证阶段抽查若干本书 |
| 旧库不兼容 | 旧数据里 `source_name` 只存在于小说库 JSON | 迁移脚本一次性搬运；不兼容语义已与用户确认 |
| 并发写 | 下载并发时多本同时写 `user_data.db` | `_connection()` 每次新连接 + SQLite 串行；已有先例（`favorites` 同库同模式） |

## 后续（不在本轮）

- 接上读点：`/storage/novels` 与 `/novel/{id}/meta` 返回 `source_name`，前端书架 / 详情显示来源
- 若届时需要更多用户态字段，再评估是否引入 `Book` 领域对象

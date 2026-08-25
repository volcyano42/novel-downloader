# 搜索历史去重 + mode/variant 字段 — 设计

日期：2026-08-25
状态：已获用户批准（唯一键 = (platform, keyword, mode, variant)；回填恢复 mode+variant）

## 背景

webui 的搜索历史目前每次搜索都会插入一条新记录，同一关键词反复搜索会无限堆积。
需求：搜索历史去重，并新增 `mode`（browser/requests/api）与 `variant`（API 提供商/
模式变体，如 `oiapi`、`rain`）字段，区分同一关键词在不同模式/变体下的搜索，
点击历史条目时完整还原搜索条件。

## 现状

- 表结构（`shared/user_data.py`）：

  ```sql
  CREATE TABLE IF NOT EXISTS search_history (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      platform     TEXT NOT NULL,
      keyword      TEXT NOT NULL,
      searched_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
  );
  ```

- `add_search_history(platform, keyword)` 直接 `INSERT`，无去重。
- 后端 `backend/routers/history.py`：POST 仅接收 `platform + keyword`；GET 返回
  `id / platform / keyword / searched_at`。
- 前端 `BookshelfPage.handleOnlineSearch` 持有 `filters.mode / filters.variant`，
  但未传给 `addHistoryMut`；面板 `SearchHistoryPanel` 展示 keyword + platform，
  点击回填仅恢复 query + platform。

## 设计

### 1. 去重语义

以 `(platform, keyword, mode, variant)` 为唯一键：

- 相同键再次搜索 → 更新该行 `searched_at`（挪到最新），不新增行。
- `mode` / `variant` 为空字符串（如 browser/requests 等无变体场景）同样参与去重。
- 不同 `mode` / `variant` 的相同关键词各自保留一条（variant 是 per-mode 的，
  如 `oiapi`/`rain` 仅存在于 api 模式）。

### 2. 数据层（`shared/user_data.py`）

- 建表 SQL 增加两列：

  ```sql
  mode         TEXT NOT NULL DEFAULT '',
  variant      TEXT NOT NULL DEFAULT '',
  ```

- `_ensure_schema` 增加列迁移：旧库检测 `mode` / `variant` 列缺失时分别执行
  `ALTER TABLE search_history ADD COLUMN ... TEXT NOT NULL DEFAULT ''`。
- 迁移填充：旧数据无 `mode` 信息，按平台整体处理——`platform == 'fanqie'`
  的旧记录统一填 `mode = 'api'`、`variant = 'rain'`（fanqie api 模式主 variant），
  其余平台保持 `''`。
- 迁移清理历史重复：按 `(platform, keyword, mode, variant)` 分组，每组仅保留
  `searched_at` 最新（并列时 id 最大）的一条，其余删除。
- 迁移后建唯一索引 `UNIQUE(platform, keyword, mode, variant)`（清理前置，
  避免建索引失败）。
- `add_search_history(platform, keyword, mode="", variant="")` 改为 UPSERT：

  ```sql
  INSERT INTO search_history(platform, keyword, mode, variant, searched_at)
  VALUES (?, ?, ?, ?, datetime('now','localtime'))
  ON CONFLICT(platform, keyword, mode, variant)
  DO UPDATE SET searched_at = datetime('now','localtime');
  ```

- `get_search_history` 返回行中带 `mode` / `variant`；`delete_search_history` 不变。

### 3. 后端（`backend/routers/history.py`）

- `SearchHistoryAddRequest` 增加 `mode: str = ""`、`variant: str = ""`。
- POST 路由把 `body.mode` / `body.variant` 传给 `add_search_history`。
- GET 每条 item 增加 `"mode"` / `"variant"`（缺失时 `""`）。

### 4. 前端

- `frontend/src/api/endpoints.ts`：
  - `SearchHistoryItem` 增加 `mode: string`、`variant: string`。
  - `addSearchHistory(platform, keyword, mode, variant)` → body 带 `mode` / `variant`。
- `frontend/src/hooks/index.ts`：`useAddSearchHistory` 的 mutation 参数增加
  `mode` / `variant`。
- `frontend/src/features/bookshelf/BookshelfPage.tsx`：
  - `handleOnlineSearch` 中 `addHistoryMut.mutate({ platform, mode, variant, keyword })`
    （mode 默认 `"browser"`，variant 为 `undefined` 时后端默认 `""`）。
  - `handleHistoryPick` 把 `item.mode` / `item.variant` 一并写入 `prefill`。
- `frontend/src/features/bookshelf/SearchBar.tsx`：
  - `prefill` 类型扩展为 `{ nonce; query; platform?; mode?; variant? }`。
  - nonce 变化时同步 keyword + platform + mode + variant（替代原"mode/variant
    保持当前选择"逻辑）。
  - 回填默认模式：历史记录 `mode` 为空（旧数据或未记录）时默认 `'requests'`，
    有值时沿用历史值。
  - 无效值兜底：若历史 mode/variant 不在当前平台可用选项中，沿用既有机制
    （平台/mode 切换时重置 variant、不可用 mode 自动回退）处理。
- `frontend/src/features/bookshelf/SearchHistoryPanel.tsx`：
  - 条目旁展示 mode + variant 徽标（仅当非空时）。
  - `onPick` 类型与回传增加 `mode` / `variant`。

### 5. 测试（`tests/test_shared_user_data.py`）

- 适配 `add_search_history` 新签名（mode/variant 默认 `""`，旧调用不破坏）。
- 去重用例：同键重复添加不新增行、`searched_at` 更新、行数不变；
  不同 mode/variant 视为不同记录。
- 迁移用例：旧表（无 mode/variant 列）加列后，`fanqie` 记录
  `mode = 'api'` / `variant = 'rain'`、其余平台为 `''`；重复记录被清理、
  唯一索引生效。

## 不做的事

- 不动收藏/分组等其它表。
- 不改变 URL 搜索的历史记录行为（URL 模式同样记历史，mode 默认 browser）。
- 不改变手动搜索（非回填）的默认模式——SearchBar 初始 mode 仍为
  `engineModes[0]`（通常 browser）；`'requests'` 默认仅作用于历史回填。

## 影响面

- 仅搜索历史相关：`shared/user_data.py`、`backend/routers/history.py`、
  前端 4 个文件（endpoints / hooks / BookshelfPage / SearchBar / SearchHistoryPanel）、
  1 个测试文件。
- 旧库自动迁移（加两列 → fanqie 填 mode=api/variant=rain → 清理重复 → 唯一索引），
  无需用户手动操作。

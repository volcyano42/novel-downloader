# 搜索历史去重 + variant 字段 — 设计

日期：2026-08-25
状态：已获用户批准（去重键 = (platform, keyword, variant)）

## 背景

webui 的搜索历史目前每次搜索都会插入一条新记录，同一关键词反复搜索会无限堆积。
需求：搜索历史去重，并新增 `variant` 字段（API 提供商/模式变体，如 `oiapi`、`rain`），
以区分同一关键词在不同变体下的搜索。

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
- 前端 `BookshelfPage.handleOnlineSearch` 持有 `filters.variant`，但未传给
  `addHistoryMut`；面板 `SearchHistoryPanel` 展示 keyword + platform，点击回填
  仅恢复 query + platform（mode/variant 保持当前选择）。

## 设计

### 1. 去重语义

以 `(platform, keyword, variant)` 为唯一键：

- 相同键再次搜索 → 更新该行 `searched_at`（挪到最新），不新增行。
- variant 为空字符串（browser/requests 等无变体场景）同样参与去重。
- 不同 variant（如 `oiapi` vs `rain`）的相同关键词各自保留一条。

### 2. 数据层（`shared/user_data.py`）

- 建表 SQL 增加列：`variant TEXT NOT NULL DEFAULT ''`。
- `_ensure_schema` 增加列迁移：旧库检测 `variant` 列缺失时执行
  `ALTER TABLE search_history ADD COLUMN variant TEXT NOT NULL DEFAULT ''`。
- 迁移清理历史重复：按 `(platform, keyword, variant)` 分组，每组仅保留
  `searched_at` 最新（并列时 id 最大）的一条，其余删除。
- 迁移后建唯一索引 `UNIQUE(platform, keyword, variant)`（清理前置，避免建索引失败）。
- `add_search_history(platform, keyword, variant="")` 改为 UPSERT：

  ```sql
  INSERT INTO search_history(platform, keyword, variant, searched_at)
  VALUES (?, ?, ?, datetime('now','localtime'))
  ON CONFLICT(platform, keyword, variant)
  DO UPDATE SET searched_at = datetime('now','localtime');
  ```

- `get_search_history` 返回行中带 `variant`；`delete_search_history` 不变。

### 3. 后端（`backend/routers/history.py`）

- `SearchHistoryAddRequest` 增加 `variant: str = ""`。
- POST 路由把 `body.variant` 传给 `add_search_history`。
- GET 每条 item 增加 `"variant": row.get("variant") or ""`。

### 4. 前端

- `frontend/src/api/endpoints.ts`：
  - `SearchHistoryItem` 增加 `variant: string`。
  - `addSearchHistory(platform, keyword, variant)` → body 带 `variant`。
- `frontend/src/hooks/index.ts`：`useAddSearchHistory` 的 mutation 参数增加 `variant`。
- `frontend/src/features/bookshelf/BookshelfPage.tsx`：
  `handleOnlineSearch` 中 `addHistoryMut.mutate({ platform, keyword, variant })`
  （variant 为 `undefined` 时后端默认 `""`）。
- `frontend/src/features/bookshelf/SearchHistoryPanel.tsx`：条目旁展示 variant
  徽标（仅当非空时），与 platform 徽标并列。
- 回填行为保持现状：点击历史只恢复 query + platform，不恢复 variant/mode
  （避免引入 mode 字段与跨模式 variant 歧义；本次 YAGNI，不做）。

### 5. 测试（`tests/test_shared_user_data.py`）

- 适配 `add_search_history` 新签名（第三参默认 `""`，旧调用不破坏）。
- 新增去重用例：同键重复添加不新增行、`searched_at` 更新、行数不变；
  不同 variant 视为不同记录。

## 不做的事

- 不记录 mode（variant 与 mode 的归属关系留待需要回填 variant 时再设计）。
- 不回填 variant（保持现状）。
- 不动收藏/分组等其它表。

## 影响面

- 仅搜索历史相关：`shared/user_data.py`、`backend/routers/history.py`、
  前端 3 个文件、1 个测试文件。
- 旧库自动迁移（加列 + 清理重复 + 唯一索引），无需用户手动操作。

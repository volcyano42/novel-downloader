# 搜索历史去重 + mode/variant 字段 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搜索历史以 `(platform, keyword, mode, variant)` 为唯一键去重（重复搜索更新 `searched_at`），新增 `mode`/`variant` 列并做旧库迁移，前端记录并在回填时恢复完整搜索条件。

**Architecture:** SQLite 表加列 + `_ensure_schema` 内联迁移（加列 → fanqie 旧记录填 mode=api/variant=rain → 清理重复 → 建唯一索引），写入改 UPSERT；FastAPI 路由透传 `mode`/`variant`；React 前端从搜索发起处一路传递到历史面板，回填时恢复 mode/variant（mode 为空默认 `requests`）。

**Tech Stack:** Python 3 + sqlite3 + FastAPI + Pydantic；React 18 + TypeScript + TanStack Query + Vite。

## Global Constraints

- 唯一键：`(platform, keyword, mode, variant)`；同键重复 → 只更新 `searched_at`，不新增行。
- `mode`/`variant` 为 `TEXT NOT NULL DEFAULT ''`，空字符串参与去重。
- 迁移顺序固定：① `ALTER TABLE ADD COLUMN`（缺失列）→ ② `UPDATE ... SET mode='api', variant='rain' WHERE platform='fanqie' AND mode=''` → ③ 清理重复（每组保留 `searched_at` 最新、并列取 `id` 最大）→ ④ `CREATE UNIQUE INDEX idx_search_history_dedup`。
- 清理重复用窗口函数 `ROW_NUMBER()`（SQLite ≥ 3.25，Python ≥ 3.6 自带，安全）。
- 回填：历史 `mode` 为空（含 undefined）→ 默认 `'requests'`；有值 → 沿用历史值。
- 不改变手动搜索（非回填）的默认模式；不改 URL 搜索历史行为；不动其它表。
- 提交遵循仓库约定：dev 分支可自动提交并推送。

---

### Task 1: 数据层 — 表结构、迁移、UPSERT

**Files:**
- Modify: `shared/user_data.py:30-51`（`_SCHEMA_SQL`）、`shared/user_data.py:66-77`（`_ensure_schema`）、`shared/user_data.py:203-209`（`add_search_history`）
- Test: `tests/test_shared_user_data.py`

**Interfaces:**
- Consumes: 现有 `_connection()`（内部调用 `_ensure_schema(conn)`）
- Produces:
  - `add_search_history(platform: str, keyword: str, mode: str = "", variant: str = "") -> None`
  - `get_search_history(limit: int = 50) -> list[dict]`（每行含 `id/platform/mode/variant/keyword/searched_at`）
  - 新私有函数 `_migrate_search_history(conn: sqlite3.Connection) -> None`

- [ ] **Step 1: 写失败测试**

在 `tests/test_shared_user_data.py` 末尾追加：

```python
def test_search_history_dedup_same_key_upsert(tmp_path, monkeypatch):
    """同键 (platform, keyword, mode, variant) 重复添加不新增行，只更新 searched_at。"""
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    rows = user_data.get_search_history()
    assert len(rows) == 1
    assert rows[0]["mode"] == "api"
    assert rows[0]["variant"] == "rain"
    assert rows[0]["keyword"] == "斗破苍穹"


def test_search_history_dedup_mode_variant_distinct(tmp_path, monkeypatch):
    """不同 mode/variant 的相同关键词各自保留一条。"""
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    user_data.add_search_history("fanqie", "斗破苍穹", "api", "oiapi")
    user_data.add_search_history("fanqie", "斗破苍穹", "browser", "")
    rows = user_data.get_search_history()
    assert len(rows) == 3
    assert {(r["mode"], r["variant"]) for r in rows} == {
        ("api", "rain"), ("api", "oiapi"), ("browser", ""),
    }


def test_search_history_migration_old_db(tmp_path, monkeypatch):
    """旧库（无 mode/variant 列）迁移：加列、fanqie 填 api/rain、其余留空、清理重复、唯一索引生效。"""
    import sqlite3

    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    # 预置旧版表结构 + 数据（fanqie 两条重复）
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE search_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            platform     TEXT NOT NULL,
            keyword      TEXT NOT NULL,
            searched_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO search_history(platform, keyword) VALUES ('fanqie', '斗破苍穹');
        INSERT INTO search_history(platform, keyword) VALUES ('fanqie', '斗破苍穹');
        INSERT INTO search_history(platform, keyword) VALUES ('qidian', '凡人修仙传');
    """)
    conn.commit()
    conn.close()

    rows = user_data.get_search_history()  # 触发 _connection → _ensure_schema 迁移
    fanqie_rows = [r for r in rows if r["platform"] == "fanqie"]
    qidian_rows = [r for r in rows if r["platform"] == "qidian"]
    assert len(fanqie_rows) == 1, "fanqie 重复记录应被清理为一条"
    assert fanqie_rows[0]["mode"] == "api"
    assert fanqie_rows[0]["variant"] == "rain"
    assert len(qidian_rows) == 1
    assert qidian_rows[0]["mode"] == ""
    assert qidian_rows[0]["variant"] == ""

    # 唯一索引生效：同键写入走 UPSERT，不新增行
    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    assert len(user_data.get_search_history()) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_shared_user_data.py -q`
Expected: 新测试 FAIL（旧表无 mode/variant 列 / UPSERT 未实现）

- [ ] **Step 3: 实现表结构 + 迁移 + UPSERT**

`shared/user_data.py` 三处修改：

① `_SCHEMA_SQL` 中 `search_history` 表加两列（保持 `idx_search_history_time` 不动；唯一索引不放这里，旧库执行会因缺列失败）：

```python
    CREATE TABLE IF NOT EXISTS search_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        platform     TEXT NOT NULL,
        mode         TEXT NOT NULL DEFAULT '',
        variant      TEXT NOT NULL DEFAULT '',
        keyword      TEXT NOT NULL,
        searched_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
```

② `_ensure_schema` 在 `conn.executescript(_SCHEMA_SQL)` 之后、groups.yaml 迁移之前插入 `_migrate_search_history(conn)` 调用，并新增函数：

```python
def _migrate_search_history(conn: sqlite3.Connection) -> None:
    """search_history 迁移：加列 → fanqie 填充 → 清理重复 → 唯一索引。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(search_history)")}
    if "mode" not in cols:
        conn.execute("ALTER TABLE search_history ADD COLUMN mode TEXT NOT NULL DEFAULT ''")
    if "variant" not in cols:
        conn.execute("ALTER TABLE search_history ADD COLUMN variant TEXT NOT NULL DEFAULT ''")
    # 旧数据无 mode 信息：fanqie 按 api 模式处理（主 variant rain），其余平台留空
    conn.execute(
        "UPDATE search_history SET mode = 'api', variant = 'rain' "
        "WHERE platform = 'fanqie' AND mode = ''"
    )
    # 清理重复：每组保留 searched_at 最新（并列取 id 最大）一条
    conn.execute("""
        DELETE FROM search_history WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY platform, keyword, mode, variant
                    ORDER BY searched_at DESC, id DESC
                ) AS rn FROM search_history
            ) WHERE rn = 1
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_search_history_dedup "
        "ON search_history(platform, keyword, mode, variant)"
    )
```

③ `add_search_history` 改签名 + UPSERT：

```python
def add_search_history(platform: str, keyword: str, mode: str = "", variant: str = "") -> None:
    conn = _connection()
    conn.execute(
        """INSERT INTO search_history(platform, keyword, mode, variant, searched_at)
           VALUES (?, ?, ?, ?, datetime('now','localtime'))
           ON CONFLICT(platform, keyword, mode, variant)
           DO UPDATE SET searched_at = datetime('now','localtime')""",
        (platform, keyword, mode, variant),
    )
    conn.commit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_shared_user_data.py -q`
Expected: 全部 PASS（含既有 `test_search_history_add_get_delete`，默认参数兼容旧调用）

- [ ] **Step 5: Commit**

```bash
git add shared/user_data.py tests/test_shared_user_data.py
git commit -m "feat: 搜索历史 (platform,keyword,mode,variant) 去重 + 旧库迁移（fanqie 填 api/rain）"
git push origin dev
```

---

### Task 2: 后端路由 — 透传 mode/variant

**Files:**
- Modify: `backend/routers/history.py:11-13`、`backend/routers/history.py:44-50`、`backend/routers/history.py:53-61`

**Interfaces:**
- Consumes: `shared.user_data.add_search_history(platform, keyword, mode="", variant="")`（Task 1 产出）
- Produces:
  - POST `/api/v2/history/search` 请求体 `{platform, keyword, mode, variant}`（mode/variant 默认 `""`）
  - GET `/api/v2/history/search` 每条 item 含 `mode`/`variant` 字段

- [ ] **Step 1: 修改请求模型与路由**

```python
class SearchHistoryAddRequest(BaseModel):
    platform: str = ""
    keyword: str
    mode: str = ""
    variant: str = ""
```

GET 分组 item 追加两个字段：

```python
        current["items"].append({
            "id": row["id"],
            "platform": row.get("platform") or "",
            "mode": row.get("mode") or "",
            "variant": row.get("variant") or "",
            "keyword": row.get("keyword") or "",
            "searched_at": searched_at,
        })
```

POST 透传：

```python
    _add(body.platform, body.keyword, body.mode, body.variant)
```

- [ ] **Step 2: 验证 import 与回归**

Run: `python -c "from backend.main import app; print('ok')" && python -m pytest tests/test_shared_user_data.py tests/test_user_db_template.py -q`
Expected: 打印 `ok`；测试全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/routers/history.py
git commit -m "feat: 搜索历史路由透传 mode/variant 字段"
git push origin dev
```

---

### Task 3: 前端链路 — 类型与传递

**Files:**
- Modify: `frontend/src/api/endpoints.ts:264-278`、`frontend/src/hooks/index.ts:211-218`、`frontend/src/features/bookshelf/BookshelfPage.tsx:92,137-158,160-162`、`frontend/src/features/bookshelf/SearchHistoryPanel.tsx:6-9,41-49`

**Interfaces:**
- Consumes: 后端 POST/GET 新字段（Task 2 产出）
- Produces:
  - `SearchHistoryItem` 含 `mode: string; variant: string`
  - `addSearchHistory(platform, keyword, mode, variant)`（body 带 mode/variant）
  - `useAddSearchHistory` mutation 参数 `{ platform, keyword, mode?, variant? }`
  - `prefill` 状态类型 `{ nonce: number; query: string; platform?: string; mode?: string; variant?: string }`
  - `SearchHistoryPanel.onPick(item: { platform: string; keyword: string; mode?: string; variant?: string })`

- [ ] **Step 1: 改 endpoints.ts**

```ts
export interface SearchHistoryItem {
  id: number; platform: string; mode: string; variant: string; keyword: string; searched_at: string;
}

export function addSearchHistory(platform: string, keyword: string, mode: string, variant: string) {
  return apiPost<{ status: string }>("/history/search", { platform, keyword, mode, variant });
}
```

- [ ] **Step 2: 改 hooks/index.ts**

```ts
mutationFn: ({ platform, keyword, mode, variant }: { platform: string; keyword: string; mode?: string; variant?: string }) =>
  addSearchHistory(platform, keyword, mode ?? "", variant ?? ""),
```

- [ ] **Step 3: 改 BookshelfPage.tsx**

`prefill` state 类型（92 行）加 `mode?`/`variant?`：

```ts
const [prefill, setPrefill] = useState<{ nonce: number; query: string; platform?: string; mode?: string; variant?: string } | null>(null);
```

`handleOnlineSearch`（147 行）传 mode + variant：

```ts
addHistoryMut.mutate({ platform, mode, variant, keyword: query.trim() });
```

`handleHistoryPick`（160-162 行）回传 mode/variant：

```ts
const handleHistoryPick = useCallback((item: { platform: string; keyword: string; mode?: string; variant?: string }) => {
  setPrefill({ nonce: Date.now(), query: item.keyword, platform: item.platform || undefined, mode: item.mode || undefined, variant: item.variant || undefined });
}, []);
```

`SearchHistoryPanel.tsx` 同步扩展 `onPick` 类型（6-9 行）与点击回传（44 行），
保证本 Task 结束时 tsc 无类型错误：

```ts
interface SearchHistoryPanelProps {
  /** 点击历史条目（非删除模式）：回填搜索框，不自动搜索 */
  onPick: (item: { platform: string; keyword: string; mode?: string; variant?: string }) => void;
}
```

```tsx
onClick={() => (deleteMode ? deleteMut.mutate(item.id) : onPick({ platform: item.platform, keyword: item.keyword, mode: item.mode, variant: item.variant }))}
```

- [ ] **Step 4: 验证 TypeScript 编译**

Run: `cd frontend && npm run build`
Expected: `tsc -b` 无类型错误（endpoints/hooks/BookshelfPage/SearchHistoryPanel 签名已同步）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/endpoints.ts frontend/src/hooks/index.ts frontend/src/features/bookshelf/BookshelfPage.tsx frontend/src/features/bookshelf/SearchHistoryPanel.tsx
git commit -m "feat: 前端搜索历史链路传递 mode/variant（记录 + 回填 + 面板回传）"
git push origin dev
```

---

### Task 4: SearchBar — 回填恢复 mode/variant，默认 requests

**Files:**
- Modify: `frontend/src/features/bookshelf/SearchBar.tsx:14,104-109`

**Interfaces:**
- Consumes: Task 3 的 `prefill` 类型（含 `mode?`/`variant?`）
- Produces: 回填行为——nonce 变化时同步 query/platform/mode/variant；mode 为空默认 `'requests'`

- [ ] **Step 1: 扩展 prefill 类型**

```ts
  /** 外部回填（点击搜索历史）：nonce 变化时同步到内部 state，不触发搜索 */
  prefill?: { nonce: number; query: string; platform?: string; mode?: string; variant?: string } | null;
```

- [ ] **Step 2: 改回填 useEffect**

```ts
  // 点击搜索历史回填：nonce 变化时同步 keyword + platform + mode + variant（mode 为空默认 requests）
  useEffect(() => {
    if (!prefill) return;
    setQuery(prefill.query);
    if (prefill.platform) setPlatform(prefill.platform);
    setMode(prefill.mode || "requests");
    if (prefill.variant) setVariant(prefill.variant);
  }, [prefill?.nonce]);
```

> 无效值兜底沿用既有机制：mode 不在 `availableModes` 时现有 `useEffect([platform, tab])` 自动回退并重置 variant；variant 不在当前平台选项时仅徽标不亮，不影响触发。

- [ ] **Step 3: 验证 TypeScript 编译**

Run: `cd frontend && npm run build`
Expected: `tsc -b` 无类型错误（Task 3 + 4 已覆盖全部 prefill 使用点）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/bookshelf/SearchBar.tsx
git commit -m "feat: 搜索历史回填恢复 mode/variant，mode 为空默认 requests"
git push origin dev
```

---

### Task 5: SearchHistoryPanel — 展示 mode/variant 徽标

**Files:**
- Modify: `frontend/src/features/bookshelf/SearchHistoryPanel.tsx:47-49`

**Interfaces:**
- Consumes: `SearchHistoryItem` 新字段、`onPick` 新签名（Task 3 产出）
- Produces: 历史条目旁展示 mode/variant 徽标（仅非空时）

- [ ] **Step 1: 展示 mode/variant 徽标**

在 platform 徽标旁追加（48 行附近）：

```tsx
                  {item.mode && <span className="shrink-0 text-[10px] text-slate-300">{item.mode}</span>}
                  {item.variant && <span className="shrink-0 text-[10px] text-slate-300">{item.variant}</span>}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd frontend && npm run build`
Expected: `tsc -b` 无类型错误、`vite build` 成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/bookshelf/SearchHistoryPanel.tsx
git commit -m "feat: 搜索历史面板展示 mode/variant 徽标"
git push origin dev
```

---

### Task 6: 全量验证

**Files:** 无新增

- [ ] **Step 1: 后端全量测试**

Run: `python -m pytest tests/ -q`
Expected: 全部 PASS，无回归

- [ ] **Step 2: 前端构建**

Run: `cd frontend && npm run build`
Expected: `tsc -b && vite build` 成功

- [ ] **Step 3: 手工冒烟（可选，agent 环境具备时执行）**

启动后端 `python app.py`，POST `/api/v2/history/search` 两次相同
`{platform:"fanqie", keyword:"测试", mode:"api", variant:"rain"}`，GET 应只返回一条。

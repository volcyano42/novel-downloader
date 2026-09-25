# 来源读点 + 用户可选 mode + 设置/书源整合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「来源」（`novel_sources`）真正被消费（API / 书架卡片 / 详情页 / 详情页默认书源），放开书源 `mode` 的用户逐能力覆盖，把书源管理并入设置页，并修掉 `headers` 字段的 `[object Object]` 显示与字符串写回缺陷。

**Architecture:** 四段彼此独立可测：① 读点（`backend/routers/storage.py` 两个端点 + 前端展示与默认值）；② mode 覆盖（`shared/config.effective_capabilities()` 唯一入口 + core `downloader` 的可选 `mode_overrides` + 各调用方透传，**core 的 `capabilities()` / `resolve()` 语义不变**）；③ 前端整合（共享折叠条组件 + 路由/侧边栏收窄 + 表单 `json`/`mode` 控件）；④ 文档约定修订。

**Tech Stack:** Python 3.10+ / FastAPI / pytest 9.1.1 / SQLite；React 19 + TypeScript 6 + Tailwind + `@tanstack/react-query`（前端无测试框架，验证 = `npx tsc --noEmit` + 手工自测）。

**设计依据：** `docs/superpowers/specs/2026-09-25-source-reads-mode-override-design.md`

## Global Constraints

- **测试基线**：改动前 `python -m pytest tests -q` = **416 passed, 1 skipped**；每个 Task 结束必须 **0 failed**。
- **不把 mode 覆盖下沉到 core**：`novelbase/source.py` 的 `capabilities()` / `resolve()` 签名与语义**不变**；覆盖只发生在调用方（`shared` / `backend` / `cli`）。
- **`mode_overrides` 是显式参数，不进传给书源函数的 `kwargs`**（`kwargs` 会原样透传给 `search()` / `chapter_content()` 等书源函数）。
- **不保证跨 mode 真能跑**：测试只锁定「覆盖值被正确解析 / 传递 / 落库 / 回显」，不做「三 mode 全通」的断言。
- **前端口径**：`npx tsc --noEmit` 必须 0 错（在 `frontend/` 下执行）。
- **Git**：中文提交消息；一个方面一条 commit；**禁止 `git add -A`**（显式列文件）；`dev` 分支提交已授权、**不 push**；中文消息用 `git commit -F - <<'EOF'` heredoc。
- **验证命令一律在仓库根执行**：`D:\Linux\novel-downloader\novel-downloader`。
- **不改** `SearchResult.source_name`、搜索历史、`bookmarks.platform`；**不动**公开库 `novel-crawler`。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend/schemas/storage.py` | 修改 | `NovelMeta` 加 `source_name` |
| `backend/routers/storage.py` | 修改 | 列表/详情返回来源（列表走批量查询） |
| `frontend/src/api/endpoints.ts` | 修改 | `NovelMeta` 类型加 `source_name` |
| `frontend/src/features/bookshelf/BookCard.tsx` | 修改 | 卡片该行改显示来源 |
| `frontend/src/features/bookshelf/BookshelfPage.tsx` | 修改 | 把来源传给卡片 |
| `frontend/src/features/detail/DetailPage.tsx` | 修改 | 显示来源 + 对话框默认来源 |
| `cli/main.py` / `cli/menus.py` | 修改 | 删书后清理来源 |
| `shared/config.py` | 修改 | `effective_capabilities()` + `merged_source_config()` + `build_options()` |
| `novelbase/core/downloader.py` | 修改 | 4 个分发函数加 `mode_overrides` |
| `backend/routers/config.py` | 修改 | `GET sources/{name}` 双 mode + `PUT` 的 `mode: null` 删键 |
| `backend/routers/download.py` | 修改 | `/sources` 返回有效 mode + 分发透传 `mode_overrides` |
| `backend/services/engine_manager.py` | 修改 | 反查能力段用有效 mode |
| `backend/services/task_manager.py` | 修改 | 预热与分发用有效 mode |
| `cli/core.py` / `cli/interactive.py` / `cli/main.py` / `cli/menus.py` | 修改 | 引擎与分发用有效 mode |
| `frontend/src/features/sources/sourceConfigFields.ts` | 修改 | `headers` 改 `type: "json"` |
| `frontend/src/features/sources/sourceConfigForm.tsx` | 修改 | 新增 `JsonField`、`mode` 下拉、`SourceEditor` 调整 |
| `frontend/src/features/sources/SourceAccordion.tsx` | 创建 | 共享折叠条（设置页与旧书源页的收口） |
| `frontend/src/features/settings/SettingsPage.tsx` | 修改 | 书源区改为折叠条列表 |
| `frontend/src/features/sources/SourcesPage.tsx` | 删除 | 并入设置页 |
| `frontend/src/App.tsx` | 修改 | `/sources` 重定向 + 侧边栏去「书源」 |
| `tests/test_storage_source_reads.py` | 创建 | 两个读点的契约 |
| `tests/test_novel_source_writes.py` | 修改 | CLI 两条删书路径清理 |
| `tests/test_config_effective_mode.py` | 创建 | 有效 mode 解析 |
| `tests/test_downloader_mode_overrides.py` | 创建 | 分发层覆盖传参 |
| `tests/test_backend_config_routes.py` | 创建 | 双 mode 契约 + `mode: null` 删键 |
| `docs/session-prompt.md` / `docs/project/sources.md` / `docs/project/config.md` / `docs/project/updates.md` | 修改 | 约定修订与记录 |

任务依赖：T1 独立；T2/T3 依赖 T1（需要接口字段）；T4 独立；T5 → T6 → T7 顺序依赖；T8 独立；T9 依赖 T7（需要 `declared_capabilities`）；T10 依赖 T8/T9；T11 最后。

---

## Part A：来源读点与 CLI 收尾

### Task 1: 后端来源读点（列表 + 详情）

**Files:**
- Modify: `backend/schemas/storage.py`（`NovelMeta`）
- Modify: `backend/routers/storage.py`（`_novel_to_meta`、`list_novels`）
- Test: `tests/test_storage_source_reads.py`

**Interfaces:**
- Consumes: `shared/user_data.get_novel_source(novel_id) -> Optional[str]`、`get_novel_sources(novel_ids) -> dict[str, str]`（均已存在）
- Produces: `NovelMeta.source_name: str | None = None`；`GET /api/v2/storage/novel` 每项含 `"source_name": str | None`；`GET /api/v2/storage/novel/{id}/meta` 含 `source_name`

- [ ] **Step 1: 写失败测试**

Create `tests/test_storage_source_reads.py`:

```python
"""来源读点：storage 列表与详情端点返回 novel_sources 里的 source_name。"""
import asyncio

import pytest

from novelbase.models.novel import Novel
from shared import user_data
from backend.routers import storage as storage_router


@pytest.fixture
def isolated_user_db(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    return user_data


def _novel(novel_id: str) -> Novel:
    return Novel(title="t", url=f"https://x/{novel_id}", id=novel_id,
                 serial=1, author="a", description="d")


class FakeStore:
    def __init__(self, novels):
        self._novels = list(novels)

    def iter_metas(self, include_images=False):
        return iter(self._novels)

    def load_meta(self, novel_id):
        return next((n for n in self._novels if n.id == novel_id), None)


def test_get_meta_returns_source_name(monkeypatch, isolated_user_db):
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore([_novel("n1")]))
    meta = asyncio.run(storage_router.get_meta("n1"))
    assert meta.source_name == "fanqie-api-rain"


def test_get_meta_without_source_is_none(monkeypatch, isolated_user_db):
    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore([_novel("n9")]))
    assert asyncio.run(storage_router.get_meta("n9")).source_name is None


def test_list_novels_returns_source_names(monkeypatch, isolated_user_db):
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    isolated_user_db.set_novel_source("n2", "92xs-requests-default")
    store = FakeStore([_novel("n1"), _novel("n2"), _novel("n3")])
    monkeypatch.setattr(storage_router, "_get_storage", lambda: store)

    rows = asyncio.run(storage_router.list_novels())

    assert {r["id"]: r["source_name"] for r in rows} == {
        "n1": "fanqie-api-rain",
        "n2": "92xs-requests-default",
        "n3": None,
    }
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_storage_source_reads.py -q`
Expected: 3 failed（`NovelMeta` 无 `source_name` 字段 / 列表 dict 无 `source_name` 键）

- [ ] **Step 3: 实现**

`backend/schemas/storage.py` — `NovelMeta` 末尾加字段：

```python
class NovelMeta(BaseModel):
    title: str
    url: str
    id: str
    serial: int
    author: str
    description: str
    tags: list[str] | None = None
    count: int | None = None
    cover: CoverData | None = None
    extra: dict | None = None
    source_name: str | None = None      # 来源（user_data.novel_sources；无记录为 None）
```

`backend/routers/storage.py` — 改 import 与两处：

```python
from shared.user_data import delete_novel_source, get_novel_source, get_novel_sources
```

```python
def _novel_to_meta(novel) -> NovelMeta:
    cover_data = _cover_to_response(novel.cover)
    serial = novel.serial
    if not isinstance(serial, int):
        serial = int(serial) if serial else 0
    return NovelMeta(
        title=novel.title, url=novel.url, id=novel.id, serial=serial,
        author=novel.author, description=novel.description,
        tags=list(novel.tags) if novel.tags else None, count=novel.count, cover=cover_data,
        extra=dict(novel.extra) if novel.extra else None,
        source_name=get_novel_source(novel.id),
    )
```

```python
@router.get("/novel")
async def list_novels():
    store = _get_storage()
    novels = list(store.iter_metas(include_images=True))
    # 一次批量查来源（避免逐本 N+1）
    sources = get_novel_sources([n.id for n in novels])
    result: list[dict] = []
    for novel in novels:
        result.append({
            "title": novel.title, "url": novel.url, "id": novel.id,
            "serial": novel.serial, "author": novel.author,
            "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None,
            "count": novel.count,
            "cover": _cover_to_response(novel.cover, thumbnail=True),
            "source_name": sources.get(novel.id),
        })
    return result
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_storage_source_reads.py -q`
Expected: 3 passed

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: 419 passed, 1 skipped, 0 failed

- [ ] **Step 6: 提交**

```bash
git add backend/schemas/storage.py backend/routers/storage.py tests/test_storage_source_reads.py
git commit -F - <<'EOF'
feat(backend): storage 列表与详情返回来源 source_name

NovelMeta 加可选字段 source_name；_novel_to_meta 逐本查 get_novel_source；
GET /storage/novel 列表用 get_novel_sources 一次批量查（避免 N+1）。
来源无记录时为 None，端点契约其余不变。
EOF
```

---

### Task 2: 前端展示来源（卡片 + 详情页）

**Files:**
- Modify: `frontend/src/api/endpoints.ts`（`NovelMeta` 接口）
- Modify: `frontend/src/features/bookshelf/BookCard.tsx`（该行改显示来源）
- Modify: `frontend/src/features/bookshelf/BookshelfPage.tsx`（传 prop）
- Modify: `frontend/src/features/detail/DetailPage.tsx`（显示来源）

**Interfaces:**
- Consumes: Task 1 的 `source_name`（列表项与 `/meta` 都含）
- Produces: `BookCard` 新增可选 prop `sourceName?: string | null`

- [ ] **Step 1: 加类型字段**

`frontend/src/api/endpoints.ts` — `NovelMeta` 接口（第 7 行）内加：

```ts
export interface NovelMeta {
  title: string;
  url: string;
  id: string;
  serial: number;
  author: string;
  description: string;
  tags?: string[] | null;
  count?: number | null;
  cover?: CoverData | null;
  extra?: Record<string, unknown> | null;
  source_name?: string | null;      // 来源书源（无记录为 null/undefined）
}
```

- [ ] **Step 2: 卡片改为显示来源**

`frontend/src/features/bookshelf/BookCard.tsx`：

props 接口加字段（`BookCardProps`）：

```ts
interface BookCardProps {
  title: string; author: string; novelId?: string; cover?: string | null;
  onRead?: () => void; className?: string;
  groups?: string[];
  currentGroup?: string;
  onDelete?: (novelId: string) => void;
  sourceName?: string | null;      // 来源书源名（无则不渲染该行）
}
```

解构加 `sourceName`：

```tsx
export function BookCard({ title, novelId, cover, onRead, className, groups = [], currentGroup, onDelete, sourceName }: BookCardProps) {
```

把这一行（原 `novelId` mono 小字）：

```tsx
{novelId && <p className="truncate text-[11px] text-slate-400 font-mono">{novelId}</p>}
```

替换为：

```tsx
{sourceName && <p className="truncate text-[11px] text-slate-400">{sourceName}</p>}
```

- [ ] **Step 3: 书架传值**

`frontend/src/features/bookshelf/BookshelfPage.tsx`（`<BookCard>` 位于分组列表内，约第 208 行）：在现有 props 后补一行：

```tsx
<BookCard key={novel.id} novelId={novel.id} title={novel.title} author={novel.author}
  sourceName={novel.source_name}
  onRead={() => navigate(`/novel/${novel.id}`)}
  groups={groupNames}
  currentGroup={tag === "未分类" ? undefined : tag}
  onDelete={handleDeleteNovel}
  cover={coverToUrl(novel.cover)}
/>
```

- [ ] **Step 4: 详情页显示来源**

`frontend/src/features/detail/DetailPage.tsx`：

在 `const novel = st?.meta ?? localMeta ?? null;`（约第 47 行）之后加：

```tsx
// 来源：本地书取 user_data 记录，远端书取进入详情页时手选的书源
const bookSource = localMeta?.source_name ?? st?.source;
```

在元信息区（`novel.extra?.rating != null` 那一行，约第 317 行）之前插入：

```tsx
{bookSource && <p className="text-xs text-slate-400 pt-0.5">来源：{bookSource}</p>}
```

- [ ] **Step 5: 类型检查**

Run（在 `frontend/` 下）: `npx tsc --noEmit`
Expected: 0 错

- [ ] **Step 6: 手工自测**

1. 启动后端 + 前端，打开书架：卡片上原 `novelId` 小字位置显示来源（如 `fanqie-api-rain`）；无来源的老书该行不显示。
2. 打开任一本地书详情页：元信息区显示「来源：xxx」。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/api/endpoints.ts frontend/src/features/bookshelf/BookCard.tsx frontend/src/features/bookshelf/BookshelfPage.tsx frontend/src/features/detail/DetailPage.tsx
git commit -F - <<'EOF'
feat(frontend): 书架卡片与详情页显示来源

卡片原先显示 novelId（sha256 前 32 位，对用户价值低），改显示 source_name，
无来源时不渲染该行；详情页元信息区新增「来源」一行（本地取 novel_sources，
远端取进入详情页时手选的书源）。
EOF
```

---

### Task 3: 详情页「检查更新 / 下载选中」默认使用该书来源

**Files:**
- Modify: `frontend/src/features/detail/DetailPage.tsx`（`DownloadDialog` 的 `initialSource`）

**Interfaces:**
- Consumes: Task 2 的 `bookSource`；`DownloadDialog` 既有 prop `initialSource?: string`（`frontend/src/features/download/DownloadDialog.tsx:12,17,25`，已实现「不在列表则回退第一项」）
- Produces: 无新接口（行为变更）

- [ ] **Step 1: 改默认来源**

`frontend/src/features/detail/DetailPage.tsx` 末尾的 `DownloadDialog`（约第 447 行）：

```tsx
      <DownloadDialog open={dialogVariant !== null} onClose={() => setDialogVariant(null)}
        dialogMode={dialogVariant ?? "download"} novelTitle={novel?.title ?? ""} chapterCount={selectedIds.size}
        sources={sourceNames} initialSource={bookSource}
        onStart={handleDialogConfirm} />
```

（`bookSource` 已在 Task 2 定义为 `localMeta?.source_name ?? st?.source`；`DownloadDialog` 内部若该值不在 `sources` 列表则回退第一项，因此书源被删/改名时不会传错。）

- [ ] **Step 2: 类型检查**

Run（在 `frontend/` 下）: `npx tsc --noEmit`
Expected: 0 错

- [ ] **Step 3: 手工自测**

1. 进入一本**本地已下载**的书详情页 → 点「检查更新」：书源选择默认已选中该书来源（不再是空/第一项），仍可手动改成其它书源。
2. 「下载选中」同理。
3. 来源书源已被删除/改名（如手改 `user_data.db`）→ 对话框回退到列表第一项，不报错。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/features/detail/DetailPage.tsx
git commit -F - <<'EOF'
feat(frontend): 详情页检查更新/下载选中默认使用该书来源

书源选择对话框的 initialSource 改为该书来源（本地取 novel_sources，远端取
进入详情页时手选的书源），用户仍可手动改；来源不在书源列表时回退第一项。
EOF
```

---

### Task 4: CLI 两条删书路径清理来源

**Files:**
- Modify: `cli/main.py`（`cmd_delete`）
- Modify: `cli/menus.py`（`do_delete`）
- Test: `tests/test_novel_source_writes.py`（追加）

**Interfaces:**
- Consumes: `shared/user_data.delete_novel_source(novel_id) -> bool`
- Produces: 无新接口（行为修复：删书不再留下孤儿来源行）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_novel_source_writes.py`（该文件已有 `isolated_user_db` fixture）：

```python
class _FakeStorage:
    """最小 storage 替身：iter_metas 给一本书，delete_novel 记账。"""

    def __init__(self):
        self.deleted: list[str] = []

    def iter_metas(self, include_images=False):
        return iter([Novel(title="t", url="https://x/1", id="n1", serial=1,
                           author="a", description="d")])

    def load_meta(self, novel_id):
        return next((n for n in self.iter_metas() if n.id == novel_id), None)

    def delete_novel(self, novel_id):
        self.deleted.append(novel_id)


def test_cli_cmd_delete_cleans_novel_sources(monkeypatch, isolated_user_db):
    """`novel-downloader delete <id>` 删书后要清掉 novel_sources 行。"""
    from cli import main as cli_main
    from cli import core as cli_core
    from cli import config as cli_config

    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    store = _FakeStorage()
    monkeypatch.setattr(cli_core, "_get_storage", lambda: store)
    monkeypatch.setattr(cli_config, "load_groups", lambda: {})
    monkeypatch.setattr(cli_config, "save_groups", lambda groups: None)

    cli_main.cmd_delete(argparse.Namespace(id="n1"))

    assert store.deleted == ["n1"]
    assert isolated_user_db.get_novel_source("n1") is None


def test_cli_menu_delete_cleans_novel_sources(monkeypatch, isolated_user_db):
    """交互式菜单删书（do_delete）同样要清掉 novel_sources 行。"""
    from cli import menus

    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    store = _FakeStorage()
    answers = iter(["1", "yes"])          # 先选第 1 本，再 yes 确认
    monkeypatch.setattr("cli.core._get_storage", lambda: store)
    monkeypatch.setattr(menus, "load_groups", lambda: {})
    monkeypatch.setattr("cli.config.save_groups", lambda groups: None)
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))

    menus.do_delete()

    assert store.deleted == ["n1"]
    assert isolated_user_db.get_novel_source("n1") is None
```

同时在该文件顶部补 import：

```python
import argparse
```

> **patch 目标的依据（已核对源码）**：`cli/main.py::cmd_delete` 用函数内 `from cli.core import _get_storage` 与 `from cli.config import load_groups, save_groups`，故 patch `cli.core._get_storage` / `cli.config.*`；`cli/menus.py::do_delete` 用函数内 `from cli.core import _get_storage`、函数内 `from cli.config import save_groups`，而 `load_groups` 是 `cli/menus.py` 的**模块级** import，故分别 patch `cli.core._get_storage` / `cli.config.save_groups` / `cli.menus.load_groups`。`do_delete` 的交互是两次 `input()`（编号 → `yes`），用 `iter(["1", "yes"])` 喂入。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_novel_source_writes.py -q -k cli`
Expected: 2 failed（`novel_sources` 行仍在）

- [ ] **Step 3: 实现**

`cli/main.py::cmd_delete`（`storage.delete_novel(novel_id)` 之后）：

```python
    storage.delete_novel(novel_id)

    from shared.user_data import delete_novel_source
    delete_novel_source(novel_id)
```

`cli/menus.py::do_delete`（`storage.delete_novel(novel.id)` 之后）：

```python
        storage.delete_novel(novel.id)
        from shared.user_data import delete_novel_source
        delete_novel_source(novel.id)
```

（懒 import 与 `cli/core.py` 的既有风格一致。）

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_novel_source_writes.py -q`
Expected: 全 PASS

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: 421 passed, 1 skipped, 0 failed

- [ ] **Step 6: 提交**

```bash
git add cli/main.py cli/menus.py tests/test_novel_source_writes.py
git commit -F - <<'EOF'
fix(cli): 删书时清理 novel_sources

CLI 两条删书路径（cmd_delete 与交互式 do_delete）此前只调 storage.delete_novel，
未清理 user_data 的 novel_sources，会不断留下孤儿来源行（与 HTTP 端点行为不一致）。
补 delete_novel_source 并加两条 spy 断言用例。
EOF
```

---

## Part B：用户逐能力覆盖 mode

### Task 5: 有效 mode 解析（`shared/config.py`）

**Files:**
- Modify: `shared/config.py`（新增 `effective_capabilities()`；改 `merged_source_config()`、`build_options()`）
- Test: `tests/test_config_effective_mode.py`

**Interfaces:**
- Consumes: `novelbase.source.capabilities(source_name) -> {cap: mode}`；用户层 yaml `sites/{source_name}.yaml`
- Produces: `effective_capabilities(source_name: str) -> dict[str, str]`（本计划所有调用方的**唯一** mode 入口）

- [ ] **Step 1: 写失败测试**

Create `tests/test_config_effective_mode.py`:

```python
"""有效 mode：用户层 sites/{name}.yaml 的 {cap}.mode 覆盖 source.json 声明。"""
import pytest

import shared.config as config_service

KNOWN = "92xs-requests-default"          # 出厂声明：四个能力均为 requests


@pytest.fixture
def isolated_sites(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    return sites


def _write(sites, cap: str, mode: str):
    (sites / f"{KNOWN}.yaml").write_text(f"{cap}:\n  mode: {mode}\n", encoding="utf-8")


def test_effective_capabilities_defaults_to_declared(isolated_sites):
    caps = config_service.effective_capabilities(KNOWN)
    assert caps["search"] == "requests"
    assert caps["chapter_content"] == "requests"


def test_effective_capabilities_user_override(isolated_sites):
    _write(isolated_sites, "search", "browser")

    caps = config_service.effective_capabilities(KNOWN)

    assert caps["search"] == "browser"
    assert caps["chapter_content"] == "requests"      # 未覆盖的能力仍取声明


def test_effective_capabilities_ignores_invalid_mode(isolated_sites):
    _write(isolated_sites, "search", "nonsense")

    assert config_service.effective_capabilities(KNOWN)["search"] == "requests"


def test_effective_capabilities_unknown_source(isolated_sites):
    assert config_service.effective_capabilities("no-such-source") == {}


def test_merged_source_config_uses_effective_mode_and_keeps_mode_key(isolated_sites):
    _write(isolated_sites, "search", "browser")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "browser"          # 表单要回显有效 mode
    assert "browser_type" in merged["search"]             # 取 browser 引擎默认字段
    assert merged["chapter_content"]["mode"] == "requests"
    assert "headers" in merged["chapter_content"]         # 未覆盖段取 requests 默认字段


def test_build_options_follows_effective_mode(isolated_sites):
    _write(isolated_sites, "search", "browser")

    opts = config_service.build_options(KNOWN, "browser")

    assert opts.mode == "browser"


def test_merged_source_config_invalid_mode_falls_back_in_output(isolated_sites):
    _write(isolated_sites, "search", "nonsense")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "requests"      # 输出恒等于有效 mode
    assert "headers" in merged["search"]               # 字段集同样按有效 mode 构建
    assert "browser_type" not in merged["search"]


def test_merged_source_config_null_mode_falls_back_in_output(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode:\n", encoding="utf-8")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "requests"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_config_effective_mode.py -q`
Expected: `effective_capabilities` 不存在（AttributeError）→ 全 failed

- [ ] **Step 3: 实现**

`shared/config.py` — 新增函数（放在 `merged_source_config` 之前）：

```python
VALID_MODES = ("browser", "requests", "api")


def effective_capabilities(source_name: str) -> dict[str, str]:
    """有效 mode 映射：用户层 `sites/{source_name}.yaml` 的 `{cap}.mode` 覆盖 `source.json` 声明。

    - 未覆盖 / 覆盖值非法（不在 VALID_MODES）→ 取书源声明
    - 未知书源 → `{}`（与 `capabilities()` 的宽容语义一致）
    """
    from novelbase.source import capabilities
    declared = capabilities(source_name)
    if not declared:
        return {}
    user = _user_site_cfg(source_name)
    out: dict[str, str] = {}
    for cap, mode in declared.items():
        section = user.get(cap) if isinstance(user.get(cap), dict) else {}
        override = section.get("mode")
        out[cap] = override if override in VALID_MODES else mode
    return out
```

`merged_source_config()` 改为使用有效 mode 且**保留** `mode` 键：

```python
def merged_source_config(source_name: str) -> dict[str, dict]:
    """三层合并某书源的逐能力配置。

    返回 `{capability: 该能力段三层合并后的完整字段}`；未知书源返回 `{}`。
    三层：ENGINE_DEFAULTS[mode]（系统默认）→ `source.json.default_config[cap]`（书源出厂，
    已含 `common` 合并）→ `sites/{source_name}.yaml[cap]`（用户层）。
    **mode 取有效值**（`effective_capabilities()`：用户层 `{cap}.mode` 覆盖声明），
    且用户层的 `mode` 键**保留**在输出中（前端表单需回显）。
    """
    from novelbase.source import get_manifest
    caps = effective_capabilities(source_name)
    if not caps:
        return {}
    manifest = get_manifest(source_name)
    user = _user_site_cfg(source_name)
    out: dict[str, dict] = {}
    for cap, mode in caps.items():
        base = deep_merge(ENGINE_DEFAULTS.get(mode, {}), manifest["default_config"][cap])
        base["mode"] = mode          # 不变量：输出的 mode 恒等于有效 mode
        user_cap = user.get(cap) if isinstance(user.get(cap), dict) else {}
        # 用户层 mode 键不参与覆盖（非法值 / YAML null 会污染有效 mode 与字段集一致性）
        user_cap = {k: v for k, v in user_cap.items() if k != "mode"}
        out[cap] = deep_merge(base, user_cap)
    return out
```

`build_options()` 反查改用有效 caps：

```python
def build_options(source_name: str, mode: str) -> Options:
    """按书源名 + mode 组 Options，字段取自 `merged_source_config(source_name)` 的对应能力段。

    能力段由 mode 反查（`effective_capabilities(source_name)` 里 mode 匹配的能力段；一个
    书源的各能力段通常同 mode）。未知书源 / 无匹配段时退回 `ENGINE_DEFAULTS[mode]`。
    """
    from novelbase.core.options import Options

    merged = merged_source_config(source_name)
    caps = effective_capabilities(source_name)
    cfg: dict = {}
    for cap, cap_mode in caps.items():
        if cap_mode == mode:
            cfg = merged.get(cap, {})
            break
    if not cfg:
        cfg = dict(ENGINE_DEFAULTS.get(mode, {}))
```

（其余函数体不变。）

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_config_effective_mode.py -q`
Expected: 8 passed（含 fix 轮补的非法值 / null 两条断言）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: 429 passed, 1 skipped, 0 failed

> 若此处出现与 `mode` 键相关的既有断言失败（例如某测试断言用户层 `mode` 被剔除），说明它在锁定旧约定——把该断言改为断言有效 mode（这是本 Task 的预期行为变更），在提交信息里写明。

- [ ] **Step 6: 提交**

```bash
git add shared/config.py tests/test_config_effective_mode.py
git commit -F - <<'EOF'
feat(shared): 新增 effective_capabilities，用户层可逐能力覆盖 mode

mode 从「恒取书源声明」改为「声明为默认、用户层 {cap}.mode 可覆盖」：
effective_capabilities() 忽略非法值回退声明；merged_source_config() 按有效 mode
取引擎默认字段并保留 mode 键（表单回显）；build_options() 用有效 mode 反查能力段。
core 的 capabilities()/resolve() 语义不变。
EOF
```

---

### Task 6: core 分发层支持 `mode_overrides`

**Files:**
- Modify: `novelbase/core/downloader.py`（4 个分发函数）
- Test: `tests/test_downloader_mode_overrides.py`

**Interfaces:**
- Consumes: `novelbase.source.resolve(source_name, capability) -> (fn, mode)`（不变）
- Produces: `search(..., mode_overrides=None)`、`resolve_meta(..., mode_overrides=None)`、`resolve_chapter_list(..., mode_overrides=None)`、`resolve_chapter(..., mode_overrides=None)`，其中 `mode_overrides: dict[str, str] | None`（**能力名 → mode**）；未传时行为与现状完全一致

- [ ] **Step 1: 写失败测试**

Create `tests/test_downloader_mode_overrides.py`:

```python
"""分发层 mode_overrides：覆盖能力 mode 后，engines 收到覆盖后的 mode。"""
import asyncio

from novelbase.core import downloader
from novelbase.models.novel import Chapter


def _patch_resolve(monkeypatch, declared_mode: str, calls: list[str]):
    """替换 novelbase.source.resolve，返回声明 mode 的假实现。"""

    def fake_resolve(source_name, capability):
        calls.append(capability)

        async def fn(**kwargs):
            return None

        return fn, declared_mode

    monkeypatch.setattr("novelbase.source.resolve", fake_resolve)


def test_resolve_chapter_uses_override_mode(monkeypatch):
    calls: list[str] = []
    _patch_resolve(monkeypatch, "requests", calls)
    seen: list[str] = []

    def engines(mode):
        seen.append(mode)
        return object()

    chapter = Chapter(id="c1", url="https://x/1", novel_id="n1", title="t", order=1)
    asyncio.run(downloader.resolve_chapter(
        chapter, "src", engines, mode_overrides={"chapter_content": "browser"}))

    assert calls == ["chapter_content"]
    assert seen == ["browser"]


def test_resolve_chapter_without_override_uses_declared_mode(monkeypatch):
    calls: list[str] = []
    _patch_resolve(monkeypatch, "requests", calls)
    seen: list[str] = []

    def engines(mode):
        seen.append(mode)
        return object()

    chapter = Chapter(id="c1", url="https://x/1", novel_id="n1", title="t", order=1)
    asyncio.run(downloader.resolve_chapter(chapter, "src", engines))

    assert seen == ["requests"]


def test_search_uses_override_mode(monkeypatch):
    seen: list[str] = []
    _patch_resolve(monkeypatch, "requests", [])

    async def fake_search(**kwargs):
        return ()

    def fake_resolve(source_name, capability):
        return fake_search, "requests"

    monkeypatch.setattr("novelbase.source.resolve", fake_resolve)

    def engines(mode):
        seen.append(mode)
        return object()

    asyncio.run(downloader.search(["src"], "q", engines,
                                  mode_overrides={"search": "api"}))

    assert seen == ["api"]
```

（`Chapter` 的构造字段以 `novelbase/models/novel.py` 为准；若 `Chapter` 需要更多必填字段，按实际签名补齐。）

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_downloader_mode_overrides.py -q`
Expected: `TypeError: resolve_chapter() got an unexpected keyword argument 'mode_overrides'`

- [ ] **Step 3: 实现**

`novelbase/core/downloader.py` — 4 个函数各加参数与一行覆盖逻辑（`mode_overrides` **不进 `kwargs`**）：

```python
async def search(sources: Sequence[str], query: str, engines,
                 skip_delay: bool = False, mode_overrides: dict[str, str] | None = None,
                 **kwargs) -> tuple[SearchResult, ...]:
    """并发搜索给定书源；单个书源失败静默跳过。

    `mode_overrides`（能力名 → mode）覆盖书源声明的 mode，用于用户层配置。
    """
    from ..source import resolve as _resolve

    async def _one(name: str) -> list[SearchResult]:
        fn, mode = _resolve(name, "search")
        mode = (mode_overrides or {}).get("search") or mode
        kwargs["skip_delay"] = skip_delay
        results = await fn(query=query, engine=engines(mode), **kwargs)
        for r in results:
            r.source_name = name
        return list(results)
    ...
```

```python
async def resolve_meta(url: str, source_name: str, engines, skip_delay: bool = False,
                       mode_overrides: dict[str, str] | None = None, **kwargs) -> Novel:
    from ..source import resolve as _resolve

    try:
        fn, mode = _resolve(source_name, "novel_info")
    except (ValueError, ImportError) as e:
        raise SourceNotFoundError(f"source not found: {source_name}") from e
    mode = (mode_overrides or {}).get("novel_info") or mode
    kwargs["skip_delay"] = skip_delay
    novel = await fn(url=url, engine=engines(mode), **kwargs)
    novel.id = make_novel_id(novel.url)
    return novel
```

```python
async def resolve_chapter_list(url: str, source_name: str, engines, skip_delay: bool = False,
                               mode_overrides: dict[str, str] | None = None, **kwargs) -> Chapters:
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "chapter_list")
    mode = (mode_overrides or {}).get("chapter_list") or mode
    kwargs["skip_delay"] = skip_delay
    return await fn(url=url, engine=engines(mode), **kwargs)
```

```python
async def resolve_chapter(chapter: Chapter, source_name: str, engines, skip_delay: bool = False,
                          mode_overrides: dict[str, str] | None = None, **kwargs) -> Chapter | None:
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "chapter_content")
    mode = (mode_overrides or {}).get("chapter_content") or mode
    kwargs["skip_delay"] = skip_delay
    return await fn(chapter=chapter, engine=engines(mode), **kwargs)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_downloader_mode_overrides.py -q`
Expected: 3 passed

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: 430 passed, 1 skipped, 0 failed

- [ ] **Step 6: 提交**

```bash
git add novelbase/core/downloader.py tests/test_downloader_mode_overrides.py
git commit -F - <<'EOF'
feat(novelbase): 分发层支持 mode_overrides 覆盖能力 mode

search/resolve_meta/resolve_chapter_list/resolve_chapter 新增可选参数
mode_overrides（能力名 → mode），覆盖 resolve() 返回的声明 mode 后再取引擎；
缺省时不改变任何行为。core 仍不感知用户态：覆盖值由调用方给出。
EOF
```

---

### Task 7: backend 侧接入有效 mode（契约 + 消费点）

**Files:**
- Modify: `backend/routers/config.py`（`GET sources/{name}` 双 mode；`PUT` 的 `mode: null` 删键）
- Modify: `backend/routers/download.py`（`/sources` 返回有效 mode；分发透传 `mode_overrides`）
- Modify: `backend/services/engine_manager.py`（`_capability_for_mode` 用有效 mode）
- Modify: `backend/services/task_manager.py`（预热与分发用有效 mode）
- Test: `tests/test_backend_config_routes.py`

**Interfaces:**
- Consumes: Task 5 的 `effective_capabilities(source_name)`、Task 6 的 `mode_overrides`
- Produces:
  - `GET /api/v2/config/sources/{name}` 返回 `{source_name, enabled, capabilities: {cap: 有效mode}, declared_capabilities: {cap: 声明mode}, config: {...}}`
  - `GET /api/v2/download/sources` 的 `capabilities` = 有效 mode
  - `PUT /api/v2/config/sources/{name}`：`config[cap].mode` 为字符串 → 覆盖；为 `null` → 删除该键

- [ ] **Step 1: 写失败测试**

Create `tests/test_backend_config_routes.py`:

```python
"""书源配置端点的 mode 契约：有效 mode + 声明 mode 双出，PUT 支持删除覆盖。"""
import asyncio

import pytest

import shared.config as config_service
from backend.routers import config as cfg
from backend.routers import download as dl
from backend.services import source_guard

KNOWN = "92xs-requests-default"          # 声明 mode = requests


@pytest.fixture
def isolated_sites(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(source_guard, "list_sources", lambda: [KNOWN])
    return sites


def test_get_source_config_returns_effective_and_declared(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    data = asyncio.run(cfg.get_source_config(KNOWN))

    assert data["capabilities"]["search"] == "browser"
    assert data["declared_capabilities"]["search"] == "requests"
    assert data["config"]["search"]["mode"] == "browser"


def test_put_source_config_writes_mode_override(isolated_sites):
    asyncio.run(cfg.save_source_config(KNOWN, {"config": {"search": {"mode": "browser"}}}))

    saved = config_service.load_yaml(isolated_sites / f"{KNOWN}.yaml")

    assert saved["search"]["mode"] == "browser"
    assert config_service.effective_capabilities(KNOWN)["search"] == "browser"


def test_put_source_config_mode_null_removes_override(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    asyncio.run(cfg.save_source_config(KNOWN, {"config": {"search": {"mode": None}}}))

    saved = config_service.load_yaml(isolated_sites / f"{KNOWN}.yaml")
    assert "mode" not in (saved.get("search") or {})
    assert config_service.effective_capabilities(KNOWN)["search"] == "requests"


def test_download_sources_returns_effective_mode(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    data = asyncio.run(dl.list_all_sources())

    assert data[KNOWN]["capabilities"]["search"] == "browser"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_backend_config_routes.py -q`
Expected: failed（无 `declared_capabilities` 键；`capabilities` 仍是声明值；`mode: None` 不能删键）

- [ ] **Step 3: 实现**

`backend/routers/config.py` — import 与两处改造：

```python
import shared.config as config_service
from novelbase.source import capabilities
from shared.config import effective_capabilities
from backend.services.source_guard import require_known_source
```

```python
@router.get("/sources/{source_name}")
async def get_source_config(source_name: str):
    """三层合并后的书源配置 + 启用状态 + 能力映射。

    形状：`{source_name, enabled, capabilities: {cap: 有效mode}, declared_capabilities: {cap: 声明mode},
    config: {cap: {…完整合并字段（含 mode）…}}}`。
    `capabilities` 为**有效 mode**（用户层 `{cap}.mode` 覆盖书源声明），
    `declared_capabilities` 为书源声明值（前端「恢复默认」用）。
    """
    require_known_source(source_name)
    return {
        "source_name": source_name,
        "enabled": config_service.is_source_enabled(source_name),
        "capabilities": effective_capabilities(source_name),
        "declared_capabilities": capabilities(source_name),
        "config": config_service.merged_source_config(source_name),
    }
```

```python
@router.put("/sources/{source_name}")
async def save_source_config(source_name: str, body: dict):
    """只写用户层 `sites/{source_name}.yaml`：顶层 `enabled` + 逐能力段 `deep_merge`。

    不把三层合并后的全量写回（否则用户层被灌满出厂/系统默认值）。
    能力段的 `mode` 键特判：传入字符串 → 覆盖；传入 `null` → 删除该键（恢复书源声明）。
    """
    require_known_source(source_name)
    path = config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml"
    existing = config_service.load_yaml(path)
    if isinstance(body.get("enabled"), bool):
        existing["enabled"] = body["enabled"]
    cfg_body = body.get("config")
    if isinstance(cfg_body, dict):
        for cap, partial in cfg_body.items():
            if not isinstance(partial, dict):
                continue
            section = existing.get(cap)
            section = dict(section) if isinstance(section, dict) else {}
            mode = partial.get("mode")
            if mode is None and "mode" in partial:
                section.pop("mode", None)        # 恢复默认：删掉覆盖
            section = config_service.deep_merge(
                section, {k: v for k, v in partial.items() if k != "mode"})
            if mode is not None:
                section["mode"] = mode
            if section:
                existing[cap] = section
            else:
                existing.pop(cap, None)
    config_service.save_yaml(path, existing)
    return {"status": "ok"}
```

`backend/routers/download.py`：

```python
from shared.config import enabled_source_names, effective_capabilities, is_source_enabled
```

```python
def _mode_overrides(source_name: str) -> dict[str, str]:
    """用户层覆盖后的「能力 → mode」映射，透传给 core 分发层。"""
    return effective_capabilities(source_name)
```

分发调用点各加 `mode_overrides=`：

```python
        novel = await resolve_meta(url, source_name, _engines_for(source_name),
                                   mode_overrides=_mode_overrides(source_name))
```

```python
        results = await search([source_name], query, _engines_for(source_name), page=page,
                               mode_overrides=_mode_overrides(source_name))
```

（另有 `/search` 的 URL 分支与关键字分支、`/novel/{id}`、`/novel/{id}/chapters` 三处 `resolve_*` 调用，逐处同样加 `mode_overrides=_mode_overrides(source_name)`；并发分支里用 `_mode_overrides(name)`。）

`/download/sources`（`list_all_sources`）改为有效 mode：

```python
@router.get("/sources")
async def list_all_sources():
    """返回全部书源（含未启用）的扁平能力矩阵与启用状态（mode 为**有效值**）。"""
    return {
        name: {"capabilities": effective_capabilities(name), "enabled": is_source_enabled(name)}
        for name in list_sources()
    }
```

`backend/services/engine_manager.py` — `_capability_for_mode` 与 `create_engine_for_request` 的 docstring：

```python
def _capability_for_mode(source_name: str, mode: str) -> str | None:
    """按 mode 反查书源的能力段名（用有效 mode；同名多段取声明序第一个）。"""
    from shared.config import effective_capabilities
    for cap, cap_mode in effective_capabilities(source_name).items():
        if cap_mode == mode:
            return cap
    return None
```

`backend/services/task_manager.py` — 预热与分发：

```python
    from shared.config import effective_capabilities
    ...
    _caps = effective_capabilities(source_name)
    primary_mode = _caps.get("novel_info") or next(iter(_caps.values()), None)
```

并把 `_run_download` 内两处分发调用加上覆盖：

```python
                meta = await resolve_meta(novel_url, source_name, engines,
                                          mode_overrides=_caps)
```

```python
                    downloaded = await resolve_chapter(ch, source_name, engines,
                                                       mode_overrides=_caps)
```

（`_caps` 即本函数内已有的 `effective_capabilities(source_name)` 结果；若作用域不便复用，直接再调用一次。）

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_backend_config_routes.py tests/test_backend_source_guard.py tests/test_backend_download_routes.py -q`
Expected: 全 PASS

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: 434 passed, 1 skipped, 0 failed

- [ ] **Step 6: 提交**

```bash
git add backend/routers/config.py backend/routers/download.py backend/services/engine_manager.py backend/services/task_manager.py tests/test_backend_config_routes.py
git commit -F - <<'EOF'
feat(backend): 书源 mode 走有效值，配置端点支持覆盖与恢复

GET /config/sources/{name} 同时返回 capabilities（有效 mode）与 declared_capabilities
（声明值）；PUT 的 config[cap].mode 为字符串即覆盖、为 null 则删键恢复声明。
/download/sources、engine_manager 反查、task_manager 预热与分发统一改用
effective_capabilities，并把 mode_overrides 透传给 core 分发层。
EOF
```

---

### Task 8: CLI 侧接入有效 mode

**Files:**
- Modify: `cli/core.py`（`_get_engine`、`_do_download_inner`）
- Modify: `cli/interactive.py`（`_get_engine`、更新路径）
- Modify: `cli/main.py`（`cmd_source`）、`cli/menus.py`（`_settings_source_detail`）
- Test: `tests/test_cli_effective_mode.py`

**Interfaces:**
- Consumes: Task 5 的 `effective_capabilities()`、Task 6 的 `mode_overrides`
- Produces: CLI 与 backend 行为一致（同一份 `sites/{name}.yaml` 覆盖，两侧都生效）

- [ ] **Step 1: 写失败测试**

Create `tests/test_cli_effective_mode.py`:

```python
"""CLI 书源列表显示有效 mode（用户层 {cap}.mode 覆盖声明）。"""
import argparse

import shared.config as config_service

KNOWN = "92xs-requests-default"


def test_cmd_source_list_shows_effective_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    (sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    from cli import main as cli_main
    cli_main.cmd_source(argparse.Namespace(source_command="list", json=False))

    out = capsys.readouterr().out
    assert "search:browser" in out          # 有效 mode
    assert "search:requests" not in out     # 声明值不再直出
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cli_effective_mode.py -q`
Expected: FAIL（输出仍是 `search:requests`）

- [ ] **Step 3: 实现**

`cli/main.py::cmd_source`：

```python
def cmd_source(args):
    """书源管理（mode 显示有效值：用户层覆盖优先）。"""
    from novelbase.source import list_sources
    from shared.config import effective_capabilities

    if args.source_command != "list":
        return

    names = list_sources()
    if args.json:
        import json
        payload = {
            name: {
                "name": name,
                "show_name": name,
                "capabilities": effective_capabilities(name),
            }
            for name in names
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"可用书源 ({len(names)}):")
    for name in names:
        caps = effective_capabilities(name)
        cap_str = ", ".join(f"{c}:{m}" for c, m in caps.items()) or "无"
        print(f"  - {name}   capabilities: {cap_str}")
```

`cli/menus.py::_settings_source_detail`：

```python
def _settings_source_detail(cfg: dict, source_name: str) -> None:
    """单书源详情：启用开关 + 各能力段入口（mode 显示有效值）。"""
    from shared.config import effective_capabilities

    while True:
        caps = effective_capabilities(source_name)
        ...
```

`cli/core.py::_get_engine`：

```python
def _get_engine(source_name: str = "fanqie", mode: str | None = None):
    """按书源名创建引擎；mode 缺省取书源首个能力声明的**有效** mode。"""
    from shared.config import effective_capabilities

    if mode is None:
        caps = effective_capabilities(source_name)
        mode = next(iter(caps.values()), "browser")
    options = build_options(source_name, mode)
    if options_hook is not None:
        options_hook(options)
    return create_engine(options)
```

`cli/core.py` 顶部 import：原 `from novelbase.source import capabilities` 只被 `_get_engine` 用到，直接换源：

```python
from shared.config import effective_capabilities
```

`cli/core.py` 的 5 处分发调用（行号为本计划编写时实测，改动前用 `grep -n "resolve_" cli/core.py` 复核）：

```python
# :111（_do_download_inner 的 meta 解析）
    _overrides = effective_capabilities(source_name)
    novel = await resolve_meta(url, source_name, engines, skip_delay=skip_delay,
                               mode_overrides=_overrides)

# :120
    chapters = await resolve_chapter_list(novel.url, source_name, engines, skip_delay=skip_delay,
                                         mode_overrides=_overrides)

# :163
                resolved = await resolve_chapter(ch, source_name, engines, mode_overrides=_overrides)

# :274（do_update 路径；其函数内自行算一份 _overrides）
            remote_chapters = await resolve_chapter_list(novel.url, source_name, engines,
                                                        mode_overrides=_overrides)

# :294
                        resolved = await resolve_chapter(ch, source_name, engines,
                                                         mode_overrides=_overrides)
```

`cli/interactive.py`：顶部补 `effective_capabilities`，并删掉 `_get_engine` 里的函数内 `from novelbase.source import capabilities`：

```python
from shared.config import effective_capabilities, enabled_source_names
```

```python
# :71（do_search 的 URL 直达分支）
            novel = asyncio.run(resolve_meta(query, source_name, engines, skip_delay=True,
                                             mode_overrides=effective_capabilities(source_name)))

# :95（并发搜索分支：每个源用自己的覆盖）
                return await search([name], query, engines, skip_delay=True,
                                    mode_overrides=effective_capabilities(name))

# :176 / :196（更新路径，函数内算一份 _overrides 复用）
        _overrides = effective_capabilities(source_name)
        remote_chapters = await resolve_chapter_list(novel.url, source_name, engines,
                                                     mode_overrides=_overrides)
        # ...
                    resolved = await resolve_chapter(ch, source_name, engines,
                                                     mode_overrides=_overrides)
```

`cli/main.py`：顶部补 `from shared.config import effective_capabilities`，两处调用：

```python
# :132（cmd_search 的并发分支）
                return await search([name], args.query, engines, page=args.page,
                                    mode_overrides=effective_capabilities(name))

# :232（cmd_download 的 meta 解析）
        novel = asyncio.run(resolve_meta(args.url, source_name, engines,
                                         mode_overrides=effective_capabilities(source_name)))
```

`cli/menus.py`：顶部 `from novelbase.source import list_sources, capabilities` 改为 `from novelbase.source import list_sources`，另加 `from shared.config import effective_capabilities`；`_settings_source_detail` 的 `caps = capabilities(source_name)` 改为 `caps = effective_capabilities(source_name)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cli_effective_mode.py tests/test_cli_storage.py -q`
Expected: 全 PASS

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests -q`
Expected: 435 passed, 1 skipped, 0 failed

- [ ] **Step 6: 提交**

```bash
git add cli/core.py cli/interactive.py cli/main.py cli/menus.py tests/test_cli_effective_mode.py
git commit -F - <<'EOF'
feat(cli): 书源 mode 走有效值，引擎与分发透传覆盖

cmd_source / 交互式书源详情显示有效 mode；_get_engine 缺省 mode 取有效值；
下载与更新路径调用分发函数时透传 mode_overrides，与 backend 行为一致。
EOF
```

---

## Part C：前端整合与表单修复

### Task 9: `headers` 字段显示与写回修复

**Files:**
- Modify: `frontend/src/features/sources/sourceConfigFields.ts`（字段类型 + `EngineField.type`）
- Modify: `frontend/src/features/sources/sourceConfigForm.tsx`（新增 `JsonField` + `renderField` 分支）

**Interfaces:**
- Produces: `EngineField.type` 新增取值 `"json"`；新增导出组件 `JsonField({ value, onCommit })`

- [ ] **Step 1: 改字段声明**

`frontend/src/features/sources/sourceConfigFields.ts`：

```ts
export type EngineField = {
  label: string; desc?: string;
  type: "toggle" | "num" | "select" | "range-delay" | "text" | "json";
  key: string;
  opts?: { value: string; label: string }[];
  min?: number; max?: number; unit?: string;
};
```

`requests` 段的 `headers` 一行改为：

```ts
    { key: "headers", label: "请求头", desc: "JSON 对象，如 {\"Cookie\": \"…\"}", type: "json" },
```

- [ ] **Step 2: 新增 `JsonField`**

`frontend/src/features/sources/sourceConfigForm.tsx`：确保顶部有 `import { useEffect, useState } from "react";`（已 import 则跳过），并在 `TextField` 之后加：

```tsx
/** JSON 对象字段（如 headers）：文本域编辑，失焦时解析；非法则提示且不写回。 */
export function JsonField({ value, onCommit }: { value: unknown; onCommit: (v: Record<string, unknown>) => void }) {
  const toText = (v: unknown) => JSON.stringify(v ?? {}, null, 2);
  const [text, setText] = useState(() => toText(value));
  const [error, setError] = useState(false);

  // 服务端值变化（保存后 refetch）时同步文本
  useEffect(() => { setText(toText(value)); setError(false); }, [value]);

  const commit = () => {
    const raw = text.trim();
    if (!raw) { setError(false); onCommit({}); return; }
    try {
      const parsed: unknown = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        setError(false);
        onCommit(parsed as Record<string, unknown>);
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    }
  };

  return (
    <div className="w-full">
      <textarea value={text} onChange={e => setText(e.target.value)} onBlur={commit} rows={4} spellCheck={false}
        className={cn("w-full rounded-lg border bg-white/50 px-2 py-1.5 font-mono text-xs text-slate-700 outline-none backdrop-blur-sm dark:bg-slate-800/50 dark:text-slate-300",
          error ? "border-red-300 dark:border-red-500/40" : "border-white/20 dark:border-slate-600/30")} />
      {error && <p className="mt-1 text-[11px] text-red-400">JSON 格式错误，未保存</p>}
    </div>
  );
}
```

`renderField` 内加分支（放在 `case "text"` 之前）：

```tsx
      case "json":
        return <JsonField value={val} onCommit={v => set(v)} />;
```

- [ ] **Step 3: 类型检查**

Run（在 `frontend/` 下）: `npx tsc --noEmit`
Expected: 0 错

- [ ] **Step 4: 手工自测（含数据校验）**

1. 打开设置 → 任一 `requests` 模式书源 → 展开：`请求头` 显示为格式化 JSON，**不再是 `[object Object]`**。
2. 改成非法 JSON（如 `{"a":`）失焦 → 出现「JSON 格式错误，未保存」，`app_data/config/sites/{name}.yaml` 不变。
3. 改成合法 JSON 失焦 → 用 `python -c "import yaml;print(type(yaml.safe_load(open('app_data/config/sites/<name>.yaml',encoding='utf-8').read())['search']['headers']))"` 确认是 `dict`（不是 `str`）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/features/sources/sourceConfigFields.ts frontend/src/features/sources/sourceConfigForm.tsx
git commit -F - <<'EOF'
fix(frontend): 请求头字段不再显示 [object Object]

headers 原声明为 text 类型，String(dict) 渲染成 "[object Object]"，且编辑后以
字符串写回用户层 yaml，破坏请求头。新增 json 字段类型与 JsonField（JSON 文本域，
失焦解析，非法不写回），headers 改用它。
EOF
```

---

### Task 10: mode 下拉与「恢复默认」

**Files:**
- Modify: `frontend/src/api/endpoints.ts`（`SourceConfig*` 类型加 `declared_capabilities`）
- Modify: `frontend/src/hooks/index.ts`（`useSaveSourceConfig` 的 mutation 类型放宽，允许 `mode: null`）
- Modify: `frontend/src/features/sources/sourceConfigForm.tsx`（`SourceConfigEditor` 加 mode 下拉）

**Interfaces:**
- Consumes: Task 7 的 `GET /config/sources/{name}` 之 `capabilities`（有效）/ `declared_capabilities`（声明）；`PUT` 的 `mode: null` 删键语义
- Produces: 每个能力段一个 mode 下拉 + 未覆盖时的「默认：xxx」提示与「恢复默认」按钮

- [ ] **Step 1: 类型与 hook 放宽**

`frontend/src/api/endpoints.ts` — 书源配置类型（`source_name` 所在的 interface）加字段，并让 config 值可为 `null`：

```ts
export interface SourceConfig {
  source_name: string;
  enabled: boolean;
  capabilities: Record<string, string>;            // 有效 mode
  declared_capabilities: Record<string, string>;   // 书源声明 mode（恢复默认用）
  config: Record<string, Record<string, unknown>>;
}
```

`frontend/src/hooks/index.ts` — `useSaveSourceConfig`：

```ts
    mutationFn: (data: { enabled?: boolean; config?: Record<string, Record<string, unknown>> }) =>
      saveSourceConfig(source, data),
```

（`saveSourceConfig` 在 `endpoints.ts` 的签名同步放宽为 `Record<string, unknown>`。）

- [ ] **Step 2: 加 mode 下拉**

`frontend/src/features/sources/sourceConfigForm.tsx` — `SourceConfigEditor` 内取声明值并渲染控件：

```tsx
  const caps = cfg?.capabilities ?? {};
  const declared = cfg?.declared_capabilities ?? {};
  const merged = cfg?.config ?? {};
```

每个能力段标题行（原只渲染 `MODE_META[mode]` 标签）替换为：

```tsx
            <div className="flex flex-wrap items-center gap-2 py-1">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{CAP_LABELS[cap] ?? cap}</span>
              <Select value={mode}
                onChange={v => saveSource.mutate({ config: { [cap]: { mode: v } } })}
                options={Object.entries(MODE_META).map(([m, meta]) => ({ value: m, label: meta.label }))} />
              {declared[cap] && declared[cap] !== mode && (
                <button onClick={() => saveSource.mutate({ config: { [cap]: { mode: null } } })}
                  className="text-[10px] font-medium text-indigo-500 hover:underline">
                  恢复默认（{declared[cap]}）
                </button>
              )}
            </div>
```

（字段列表仍按**有效** mode 取：`const fields = ENGINE_FIELDS[mode] ?? [];` —— `mode` 来自 `caps`，即有效值，无需再改。风险提示文案加在编辑器顶部一次即可：

```tsx
      <p className="pb-1 text-[11px] text-slate-400">
        切换引擎模式可能不可用（不同模式的接口/参数互不通用）；不可用时点「恢复默认」回退。
      </p>
```

）

- [ ] **Step 3: 类型检查**

Run（在 `frontend/` 下）: `npx tsc --noEmit`
Expected: 0 错

- [ ] **Step 4: 手工自测**

1. 展开任一书源：每个能力段有 mode 下拉，初值为有效 mode（默认即声明值）。
2. 切成 `browser` → 出现「恢复默认（requests）」，字段列表随之变成 browser 字段集；`app_data/config/sites/{name}.yaml` 里该能力段出现 `mode: browser`。
3. 点「恢复默认」→ 该键从 yaml 消失，下拉回到 `requests`。
4. 改 mode 后回到书架执行一次搜索/下载，观察后端日志确认按新 mode 建引擎（失败属预期风险，不算回归）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/endpoints.ts frontend/src/hooks/index.ts frontend/src/features/sources/sourceConfigForm.tsx
git commit -F - <<'EOF'
feat(frontend): 书源编辑支持逐能力切换引擎 mode

每个能力段加 mode 下拉（有效值初值）与「恢复默认」按钮（提交 mode: null 删键），
字段集随有效 mode 变化；类型侧补 declared_capabilities 并允许 config 值传 null。
EOF
```

---

### Task 11: 书源折叠条共享组件 + 设置页整合

**Files:**
- Create: `frontend/src/features/sources/SourceAccordion.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`（书源区改为折叠条列表）
- Delete: `frontend/src/features/sources/SourcesPage.tsx`
- Modify: `frontend/src/App.tsx`（`/sources` 重定向 + 侧边栏去「书源」）

**Interfaces:**
- Consumes: `useSources()`（`{source_name: {capabilities, enabled}}`）、`SourceConfigEditor`、`Toggle`
- Produces: `SourceAccordion({ name, info })` 组件（折叠条：名称 + 能力 badge + enabled 开关 + 展开编辑）

- [ ] **Step 1: 新建共享折叠条**

Create `frontend/src/features/sources/SourceAccordion.tsx`（从 `SourcesPage.tsx` 的 `SourceRow` 平移而来）：

```tsx
import {useEffect, useState} from "react";
import {ChevronDown} from "lucide-react";
import {cn} from "@/lib/utils";
import {useSaveSourceConfig} from "@/hooks/index";
import {SourceConfigEditor, Toggle} from "./sourceConfigForm";
import {CAP_LABELS} from "./sourceConfigFields";

/** 单个书源的折叠条：名称 + 能力 badge + enabled 开关；展开即编辑配置（含 mode 下拉）。 */
export function SourceAccordion({ name, info }: { name: string; info: { capabilities: Record<string, string>; enabled: boolean } }) {
  const saveSource = useSaveSourceConfig(name);
  const [enabled, setEnabled] = useState(info.enabled);
  const [open, setOpen] = useState(false);

  // 列表数据（useSources）刷新后同步开关显示
  useEffect(() => { setEnabled(info.enabled); }, [info.enabled]);

  const caps = info.capabilities ?? {};
  const toggleEnabled = (v: boolean) => {
    setEnabled(v); // 乐观更新，避免受控开关因 refetch 滞后回弹
    saveSource.mutate({ enabled: v });
  };

  return (
    <div className="border-b border-slate-100 last:border-b-0 dark:border-slate-800/50">
      <div className="flex items-center justify-between gap-4 py-2.5">
        <button onClick={() => setOpen(o => !o)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-200", open && "rotate-180")} strokeWidth={1.5} />
          <span className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{name}</span>
          <span className="flex flex-wrap gap-1">
            {Object.keys(caps).length === 0 && <span className="text-[11px] text-slate-400">无能力</span>}
            {Object.entries(caps).map(([cap, mode]) => (
              <span key={cap} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {CAP_LABELS[cap] ?? cap}·{mode}
              </span>
            ))}
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-3">
          <Toggle checked={enabled} onChange={toggleEnabled} />
        </div>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}
```

- [ ] **Step 2: 设置页书源区改用折叠条**

`frontend/src/features/settings/SettingsPage.tsx`：把 `SourceSection` 整体替换为（删除原先的横排按钮 + 单选 state + `useSourceConfig`/`useState` 相关代码）：

```tsx
/** 书源：每源一个折叠条，展开即编辑（含逐能力 mode 下拉）。 */
function SourceSection() {
  const { data: sources } = useSources();
  const names = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);

  return (
    <Section icon={Layers} title="书源">
      {names.map(name => <SourceAccordion key={name} name={name} info={sources![name]} />)}
      {names.length === 0 && <div className="py-3 text-xs text-slate-400">暂无书源</div>}
    </Section>
  );
}
```

import 调整：加 `import {SourceAccordion} from "@/features/sources/SourceAccordion";`；移除新代码不再引用的 `SourceConfigEditor`、`useSourceConfig`、`useSaveSourceConfig` 三个 import（`cn` / `Num` / `Range` / `Select` / `Toggle` / `useFormatConfig` 等仍被本页其它区段使用，保留）；其余以 `npm run lint` 的未使用告警为准。

- [ ] **Step 3: 删除书源页与路由收窄**

- 删除文件：`git rm frontend/src/features/sources/SourcesPage.tsx`
- `frontend/src/App.tsx`：
  - 移除 `import SourcesPage from "@/features/sources/SourcesPage";`
  - `type NavItem` 去掉 `"sources"`；`DESKTOP_ITEMS` 去掉 `{ id: "sources", … }` 一项；`TO_PATH` 去掉 `sources: "/sources"`
  - `activeNav` 去掉 `if (pathname === "/sources") return "sources";`
  - 路由 `<Route path="/sources" element={<SourcesPage />} />` 改为 `<Route path="/sources" element={<Navigate to="/settings" replace />} />`（保留旧深链）
  - 若 `Layers` 图标不再被使用，一并从 `lucide-react` 的 import 列表移除

- [ ] **Step 4: 类型检查与 lint**

Run（在 `frontend/` 下）: `npx tsc --noEmit && npm run lint`
Expected: tsc 0 错；lint 无新增告警

- [ ] **Step 5: 手工自测**

1. 设置页「书源」区：每个书源一行折叠条（名称 + 能力 badge + 开关），点击展开可编辑（含 mode 下拉与 JSON 请求头）。
2. 侧边栏不再有「书源」入口；访问旧的 `/sources` 自动跳到 `/settings`。
3. 开关某书源 → 书架搜索并发集随之变化（沿用既有 `enabled_source_names()` 行为）。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/features/sources/SourceAccordion.tsx frontend/src/features/settings/SettingsPage.tsx frontend/src/App.tsx
git rm frontend/src/features/sources/SourcesPage.tsx
git commit -F - <<'EOF'
refactor(frontend): 书源管理并入设置页，每源一个折叠条

抽取共享 SourceAccordion（名称 + 能力 badge + enabled 开关 + 展开编辑），设置页书源区
改为折叠条列表；删除 SourcesPage，/sources 重定向到 /settings（保留旧深链），侧边栏
移除「书源」入口。
EOF
```

---

## Part D：文档与约定

### Task 12: 修订 mode 约定与更新记录

**Files:**
- Modify: `docs/session-prompt.md`
- Modify: `docs/project/sources.md`
- Modify: `docs/project/config.md`
- Modify: `docs/project/updates.md`

**Interfaces:**
- Consumes: 前 11 个 Task 的最终行为
- Produces: 文档与代码一致（尤其「用户不再选 mode」这条约定必须反转）

- [ ] **Step 1: 改约定条目**

`docs/session-prompt.md` 的「引擎」条（约第 37 行）：

```markdown
- **引擎** 三种模式：`browser`（**Playwright**，2026-08-16 从 DrissionPage 迁移）、`requests`（httpx）、`api`（Rain.ink 代理）。**mode 默认由书源在 `source.json` 里声明**（`common.mode` 并入各能力段）；**用户可逐能力覆盖**（`sites/{source_name}.yaml` 的 `{cap}.mode`，唯一入口 `shared.config.effective_capabilities()`，2026-09-25 二次修订；覆盖为「值 + 引擎默认字段」替换，`null` 表示恢复声明）。core 的 `capabilities()` / `resolve()` 恒取声明值，覆盖只在调用方生效
```

- [ ] **Step 2: 改机制文档**

`docs/project/sources.md`：在能力声明（`source.json` 的 `capabilities`/`mode`）一节后补：

```markdown
### mode 的用户覆盖（2026-09-25）

- 有效 mode = 用户层 `app_data/config/sites/{source_name}.yaml` 的 `{cap}.mode`（合法值 `browser`/`requests`/`api`）
  优先于 `source.json` 声明；非法值忽略并回退声明
- 唯一入口：`shared.config.effective_capabilities(source_name)`；`merged_source_config()` 按有效 mode 取
  `ENGINE_DEFAULTS[mode]` 作基底并保留 `mode` 键（表单回显）
- core 分发层 `novelbase/core/downloader.py` 的 4 个函数接受可选 `mode_overrides`（能力名 → mode），
  由调用方（backend `task_manager` / 各路由、CLI）透传；`novelbase.source.capabilities()` 语义不变
- API：`GET /api/v2/config/sources/{name}` 返回 `capabilities`（有效）与 `declared_capabilities`（声明）；
  `PUT` 传 `config[cap].mode = null` 即删除覆盖
- 已知限制：不同 mode 的接口/参数互不通用，覆盖后不保证可用
```

`docs/project/config.md`：在「逐书源配置」节说明 `sites/{source_name}.yaml` 的 `{cap}.mode` 语义（覆盖声明、`null` 删除、非法值忽略）。

- [ ] **Step 3: 追加更新记录**

`docs/project/updates.md`：在最新一节追加本轮摘要（来源读点、详情页默认来源、mode 覆盖、设置/书源整合、headers 修复、CLI 删书清理），并注明测试数（`python -m pytest tests -q` 的实际结果）。

- [ ] **Step 4: 文档自检**

Run: `grep -rn "用户不再选 mode\|用户不选 mode" docs/` → 无命中
Run: `grep -rn "effective_capabilities" docs/` → 至少命中 `session-prompt.md` / `project/sources.md`
Run: `python -m pytest tests -q` → 0 failed

- [ ] **Step 5: 提交**

```bash
git add docs/session-prompt.md docs/project/sources.md docs/project/config.md docs/project/updates.md
git commit -F - <<'EOF'
docs: 修订 mode 约定（声明为默认、用户可覆盖）并补更新记录

session-prompt 的「mode 由书源声明、用户不再选」反转为「声明为默认、可逐能力覆盖」；
project/sources.md 与 config.md 补 effective_capabilities、mode_overrides、PUT 的 mode:null
语义与已知限制；updates.md 记录本轮变更与测试数。
EOF
```

---

## 完成后验证

- [ ] `python -m pytest tests -q` → 0 failed（基线 416 passed / 1 skipped，本轮预计 ~435 passed）
- [ ] `npx tsc --noEmit`（在 `frontend/`）→ 0 错；`npm run lint` → 无新增告警
- [ ] `grep -rn "capabilities(source_name)" backend cli` → 只剩 core 内部/无遗漏消费点（全部走 `effective_capabilities`）
- [ ] `grep -n "source_name" novelbase/models/novel.py` → 无命中（模型仍纯净）
- [ ] 端到端抽查：书架卡片显示来源 → 详情页显示来源 → 「检查更新」默认选中该书来源 → 设置页改某书源 `search` 的 mode → `GET /api/v2/config/sources/{name}` 的 `capabilities` 随之变化 → CLI `python -m cli source list` 显示同一有效 mode
- [ ] `git status --porcelain` → clean

## Self-Review 记录

- **spec 覆盖**：spec §1 读点 → T1/T2；§2 详情页默认来源 → T3；§3 mode 覆盖 → T5/T6/T7/T8；§4 前端整合 → T10/T11；§5 headers → T9；§6 CLI 清理 → T4；§「文档与约定修订」→ T12。spec 的「非目标」未被任何 Task 触碰。
- **类型一致性**：`effective_capabilities()`、`mode_overrides`（能力名 → mode）、`capabilities`（有效）/ `declared_capabilities`（声明）、`NovelMeta.source_name`、`SourceAccordion({name, info})` 在各 Task 间命名一致。
- **测试计数**：T1 +3；T4 +2；T5 +6；T6 +3；T7 +4；T8 +1 → 预计 435 passed（若某步实际数不同，以 `pytest` 实测为准并更新对应 Expected 行）。

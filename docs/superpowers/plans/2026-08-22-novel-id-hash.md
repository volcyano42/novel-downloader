# Novel.id 改为 hash(url) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `Novel.id` 从「各 source 手动拼平台前缀 + 源站 ID」改为「`sha256(canonical_url)[:32]` 中心化生成」，彻底去掉平台前缀并退役 `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE` / `get_source_for_id` / `origin_id` 等反查机制。

**Architecture:** 核心库新增 `novelbase/utils/urls.py`（`canonical_book_url` + `make_novel_id`），`downloader.resolve_meta()` 返回前统一赋值 id 并冗余写入 `novel.extra["platform"]`；`Novel.id` 加默认值 `""` 后 4 个 source 的 `novel_info` 不再拼 id；所有依赖「从 id 反查平台/URL」的机制退役，`resolve_chapter` 走既有 url 回退；另写仓库外迁移脚本重命名存量 `.db` 并同步库内数据与 favorites 表。

**Tech Stack:** Python 3.13、FastAPI、SQLite、yarl（已依赖）、pytest。

**Spec:** `docs/superpowers/specs/2026-08-22-novel-id-hash-design.md`

## Global Constraints

- id 格式：`sha256(canonical_url)[:32]`，32 位小写 hex，无前缀
- hash 输入必须是 `canonical_book_url(novel.url, platform)` 的结果；运行时与迁移脚本必须用同一函数，保证迁移结果与重新拉取一致
- `Novel.id` 加默认值 `""`；4 个 source 删除手动拼 id；`resolve_meta` 中心赋值 + `novel.extra["platform"] = name`
- 退役项：`get_source_for_id`、`Novel.origin_id`、各 source 的 `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE`、`resolve_book_url` 的 id 输入分支、前后端纯数字 id 输入逻辑
- `Chapter.id` / `Chapter.novel_id` 格式不变（fanqie 章节 id 仍为 itemId、92xs 仍为 url）
- 迁移脚本放 `novel-downloader-tools/scripts/`（仓库外，不进 git）
- git：commit 消息中文、一个方面一条 commit、显式 `git add <files>`（禁 `-A`）；dev 分支可自动提交推送
- 测试命令：`python -m pytest tests/ -v --tb=short`

---

### Task 1: 核心工具函数 `canonical_book_url` + `make_novel_id`

**Files:**
- Create: `novelbase/utils/urls.py`
- Test: `tests/test_urls.py`

**Interfaces:**
- Consumes: 无（纯函数）
- Produces:
  - `canonical_book_url(url: str, platform: str) -> str` — url 规范化
  - `make_novel_id(canonical_url: str) -> str` — 32 位 hex hash

- [ ] **Step 1: Write the failing test**

创建 `tests/test_urls.py`：

```python
import re

from novelbase.utils.urls import canonical_book_url, make_novel_id


def test_make_novel_id_consistent():
    url = "https://fanqienovel.com/page/7123456789012345678"
    assert make_novel_id(url) == make_novel_id(url)


def test_make_novel_id_different_urls_differ():
    assert make_novel_id("https://fanqienovel.com/page/1") != make_novel_id("https://fanqienovel.com/page/2")


def test_make_novel_id_format_32hex():
    assert re.fullmatch(r"[0-9a-f]{32}", make_novel_id("https://x.com/y"))


def test_canonical_lowercase_and_drop_query_fragment():
    assert canonical_book_url("https://FanqieNovel.com/page/123?a=1#frag", "fanqie") \
        == "https://fanqienovel.com/page/123"


def test_canonical_trailing_slash_removed():
    assert canonical_book_url("https://www.qidian.com/book/123/", "qidian") \
        == "https://www.qidian.com/book/123"


def test_canonical_92xs_book_to_html():
    assert canonical_book_url("http://www.92xs.info/book/456.html", "92xs") \
        == "http://www.92xs.info/html/456/"


def test_canonical_92xs_html_kept():
    assert canonical_book_url("http://www.92xs.info/html/456/", "92xs") \
        == "http://www.92xs.info/html/456/"


def test_canonical_qidian_info_to_book():
    assert canonical_book_url("https://www.qidian.com/info/123/", "qidian") \
        == "https://www.qidian.com/book/123"


def test_canonical_qidian_book_kept():
    assert canonical_book_url("https://www.qidian.com/book/123/", "qidian") \
        == "https://www.qidian.com/book/123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_urls.py -v --tb=short`
Expected: FAIL，`ModuleNotFoundError: No module named 'novelbase.utils.urls'`

- [ ] **Step 3: Write minimal implementation**

创建 `novelbase/utils/urls.py`：

```python
"""URL 规范化与 Novel.id 生成工具（Novel.id = sha256(canonical_url)[:32]）。"""

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit


def canonical_book_url(url: str, platform: str) -> str:
    """书源完整 URL 规范化：小写 scheme/host、去 query/fragment、去尾斜杠。

    platform 特例：
    - 92xs：/book/{id}.html 与 /html/{id}/ 统一为 http://www.92xs.info/html/{id}/
      （与 chapter_list 现行规则一致）
    - qidian：/info/{id}/ 统一为 /book/{id}/（BOOK_URL_TEMPLATE 标准形态）
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path
    if path not in ("", "/"):
        path = path.rstrip("/")
    result = urlunsplit((scheme, netloc, path, "", ""))

    if platform == "92xs":
        m = re.search(r"(?:/book/|/html/)(\d+)", path)
        if m:
            result = f"http://www.92xs.info/html/{m.group(1)}/"
    elif platform == "qidian":
        m = re.search(r"/info/(\d+)", path)
        if m:
            result = f"https://www.qidian.com/book/{m.group(1)}"
    return result


def make_novel_id(canonical_url: str) -> str:
    """由 canonical url 生成 32 位 hex 的 Novel.id（sha256 前 32 字符）。"""
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:32]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_urls.py -v --tb=short`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add novelbase/utils/urls.py tests/test_urls.py
git commit -m "feat: 新增 canonical_book_url 与 make_novel_id（Novel.id hash 化工具）"
```

---

### Task 2: Novel 模型 — id 加默认值、删除 origin_id

**Files:**
- Modify: `novelbase/models/novel.py:276-320`
- Test: `tests/test_models.py:257-280`

**Interfaces:**
- Consumes: 无
- Produces: `Novel.id: str = ""`（可省略传值）；`Novel.origin_id` 不再存在

- [ ] **Step 1: 删除 origin_id 相关测试用例**

在 `tests/test_models.py` 中删除这三个用例（约 257-280 行）：
- `test_origin_id_strips_platform_prefix`
- `test_origin_id_without_prefix_returns_id`
- `test_loads_origin_id_kwarg_ignored`

- [ ] **Step 2: Run tests to verify deletion doesn't break others**

Run: `python -m pytest tests/test_models.py -v --tb=short`
Expected: 其余用例 PASS

- [ ] **Step 3: 修改 Novel dataclass**

`novelbase/models/novel.py` 中 `Novel` 字段改为（`id` 移到默认值区，`cover` 之前；构造调用全部使用关键字，不受字段重排影响）：

```python
@dataclass
class Novel:
    title: str
    url: str
    serial: int
    author: str
    description: str
    tags: Sequence[str] | None = None
    count: int | None = None
    id: str = ""                  # 由 resolve_meta 中心赋值（hash id）
    cover: Illustration | None = None
    chapters: Chapters = field(default_factory=Chapters)
    extra: Box = field(default_factory=Box)
    # serial 自动模式标记：serial==0 的书源（如 92xs）进入后持续跟随本地章节数
    _serial_auto: bool = field(default=False, init=False, repr=False, compare=False)
```

删除 `origin_id` property 与 setter（原 291-300 行）。

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_models.py -v --tb=short`
Expected: PASS（其余用例均用关键字 `id=...` 构造）

- [ ] **Step 5: Commit**

```bash
git add novelbase/models/novel.py tests/test_models.py
git commit -m "refactor: Novel.id 加默认值并移除 origin_id 属性（hash id 无前缀可去）"
```

---

### Task 3: `resolve_meta` 中心化赋值 id + extra.platform

**Files:**
- Modify: `novelbase/core/downloader.py:113-134`
- Test: `tests/test_downloader.py`

**Interfaces:**
- Consumes: Task 1 的 `canonical_book_url` / `make_novel_id`
- Produces: `resolve_meta()` 返回的 Novel 满足：`id` 为 32 位 hex、`extra["platform"]` 为平台名

- [ ] **Step 1: 修改 resolve_meta**

`novelbase/core/downloader.py` 的 `resolve_meta`（当前 `return await fn(url=url, engine=engine, **kwargs)`）改为：

```python
    fn = _resolve(name, mode, "novel_info", variant=variant)
    novel = await fn(url=url, engine=engine, **kwargs)
    # id 中心化生成：hash(canonical url)，并冗余存平台（hash 后无法从 id 反推）
    novel.id = make_novel_id(canonical_book_url(novel.url, name))
    novel.extra["platform"] = name
    return novel
```

文件顶部新增 import：

```python
from ..utils.urls import canonical_book_url, make_novel_id
```

- [ ] **Step 2: 新增测试**

在 `tests/test_downloader.py` 的 `TestResolveMeta` 类中新增用例（复用既有 `asyncio.run` + `_make_engine()` + patch `novelbase.source.resolve` 的写法）：

```python
    def test_sets_hash_id_and_platform(self):
        """resolve_meta 中心化生成 hash id 并冗余写入 extra.platform"""
        import re
        engine = _make_engine()
        novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                      serial=1, author="a", description="d")

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
                async def _fake(url, engine, **kw):
                    return novel

                mock_resolve.return_value = _fake

                result = asyncio.run(resolve_meta("https://fanqienovel.com/page/7123456789012345678", engine))

        assert re.fullmatch(r"[0-9a-f]{32}", result.id)
        assert result.extra["platform"] == "fanqie"
```

注意：既有 `test_delegates_to_resolve` 只断言 `result is expected`（对象同一性），resolve_meta 覆盖 id 不影响其通过。

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_downloader.py -v --tb=short`
Expected: 新用例 PASS，既有用例不受影响（此时 source 仍拼旧 id，但被 resolve_meta 覆盖）

- [ ] **Step 4: Commit**

```bash
git add novelbase/core/downloader.py tests/test_downloader.py
git commit -m "feat: resolve_meta 中心化生成 hash id 并冗余写入 extra.platform"
```

---

### Task 4: 4 个 source 删除手动拼 id

**Files:**
- Modify:
  - `novelbase/sources/fanqie/_common.py:205`
  - `novelbase/sources/qidian/_common.py:103`
  - `novelbase/sources/qimao/_common.py:119`
  - `novelbase/sources/92xs/requests/default/novel_info.py:49-58`

**Interfaces:**
- Consumes: Task 2（`Novel.id` 有默认值）
- Produces: 各 source `novel_info` 构造 Novel 时不再传 `id`（也不再有拼 id 的局部变量）

- [ ] **Step 1: fanqie**

`novelbase/sources/fanqie/_common.py` 的 `parse_novel_info`（约 200-213 行）中 `id=f"fanqie_{standardize_id(book_url)}",` 一行删除（`id` 参数不传）。

- [ ] **Step 2: qidian**

`novelbase/sources/qidian/_common.py`（约 101-111 行）中 `id=f"qidian_{novel_id}",` 一行删除。

- [ ] **Step 3: qimao**

`novelbase/sources/qimao/_common.py`（约 119 行）`return Novel(url=book_url, id=f"qimao_{novel_id}", ...)` 中 `id=f"qimao_{novel_id}",` 删除。若 `novel_id = standardize_id(book_url) if book_url else ""` 不再被其他代码使用则一并删除该局部变量（确认 `parse_chapter_list` 的 `novel_id` 参数与之无关，其由调用方传入，保留）。

- [ ] **Step 4: 92xs**

`novelbase/sources/92xs/requests/default/novel_info.py`：删除「提取 book_id」段（约 49-53 行，含 `import re` / `from urllib.parse import urlparse` / `novel_id = f"92xs_{...}"`），`Novel(...)` 中删除 `id=novel_id,`。若 `re` / `urlparse` 不再被该文件其他代码使用，同步清理 import。

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS（resolve_meta 已中心赋值 id；不经过 resolve_meta 的用例不校验 id 内容）

- [ ] **Step 6: Commit**

```bash
git add novelbase/sources/fanqie/_common.py novelbase/sources/qidian/_common.py novelbase/sources/qimao/_common.py novelbase/sources/92xs/requests/default/novel_info.py
git commit -m "refactor: 删除 4 个 source 手动拼 id（id 改由 resolve_meta 中心生成）"
```

---

### Task 5: `get_source_for_id` 退役

**Files:**
- Modify: `novelbase/core/downloader.py:38-45, 174-179`
- Modify: `novelbase/__init__.py:7, 52`
- Test: `tests/test_downloader.py:43-93`

**Interfaces:**
- Consumes: 无
- Produces: `get_source_for_id` 不再存在；`resolve_chapter` 仅用 `get_source(chapter.url)`

- [ ] **Step 1: 改写测试**

`tests/test_downloader.py` 的 `TestResolveChapter` 三个用例（当前 patch `novelbase.core.downloader.get_source_for_id`）改写为 patch `get_source` 验证 url 回退，按既有 `asyncio.run` / `_make_engine()` / patch `novelbase.source.resolve` 风格。以第一个用例为例，三个用例统一把：

```python
        with patch("novelbase.core.downloader.get_source_for_id", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
```

改为：

```python
        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
```

第三个用例 `test_raises_when_no_source_found`（断言 `SourceNotFoundError`）把 `return_value=None` 从 `get_source_for_id` 移到 `get_source`，异常消息断言改为 `match="source not found"`（不变）。

- [ ] **Step 2: 删除函数与简化调用**

`novelbase/core/downloader.py`：
- 删除 `get_source_for_id` 函数（38-45 行）
- `resolve_chapter` 简化为：

```python
    name = get_source(chapter.url)
    if name is None:
        raise SourceNotFoundError(f"source not found for url: {chapter.url}")
```

- [ ] **Step 3: 更新导出**

`novelbase/__init__.py`：从 import（第 7 行）与 `__all__`（第 52 行）中移除 `get_source_for_id`。

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add novelbase/core/downloader.py novelbase/__init__.py tests/test_downloader.py
git commit -m "refactor: 移除 get_source_for_id（resolve_chapter 走 url 回退）"
```

---

### Task 6: `ID_PATTERN` 三件套退役 + `resolve_book_url` 简化

**Files:**
- Modify: `novelbase/source.py:48-79, 135-157`
- Modify: `novelbase/sources/fanqie/__init__.py`、`novelbase/sources/qidian/__init__.py`、`novelbase/sources/qimao/__init__.py`、`novelbase/sources/92xs/__init__.py`
- Modify: `novelbase/utils/build_manifest.py:19-27, 84, 108-109`
- Modify: `backend/routers/download.py:22-27, 38, 152-168`
- Modify: `cli/main.py:313-314`
- Modify: `frontend/src/api/endpoints.ts:222`

**Interfaces:**
- Consumes: 无
- Produces: `register_source()` 元数据不含 `id_pattern` / `origin_id_pattern` / `book_url_template`；`resolve_book_url(raw)` 仅接受 http(s) 输入

- [ ] **Step 1: source.py**

`novelbase/source.py`：
- `_scan_sources` 中删除 `id_pattern` / `origin_id_pattern` / `book_url_template` 三个字段的收集（72-74 行），并删除对 `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE` 的 `getattr`
- `resolve_book_url` 改为：

```python
def resolve_book_url(raw: str) -> str:
    """将输入转为完整 URL。

    - 已是完整 URL 则直接返回
    - 其他输入（含 hash id）无法识别时报 ValueError
    """
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    raise ValueError(f"无法识别书源或 ID 格式: {raw}")
```

- [ ] **Step 2: 各 source `__init__.py`**

4 个 source 的 `__init__.py` 中删除 `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE` 定义与对应注释；若 `import re` 只被它们使用则一并删除（fanqie/qidian/qimao/92xs 的 `__init__.py` 仅有 pattern 定义，`re` 随定义删除）。

- [ ] **Step 3: build_manifest.py**

`novelbase/utils/build_manifest.py`：删除对 `"ID_PATTERN"`, `"ORIGIN_ID_PATTERN"`, `"BOOK_URL_TEMPLATE"` 的收集（26-27 行）、`id_pattern` / `origin_id_pattern` 字段输出（84、108-109 行）及其 import。

- [ ] **Step 4: backend**

`backend/routers/download.py`：
- `_resolve_url` 保持不变（仍捕获 `ValueError` 转 400）
- `search` 接口（38 行）条件改为只识别 URL：

```python
    if query.startswith("http://") or query.startswith("https://"):
```

- `list_all_sources`（152-168 行）响应中删除 `id_pattern` 字段与 `id_pat` 变量

- [ ] **Step 5: cli**

`cli/main.py`（313-314 行）：`sources` 命令展示中删除 `id_pattern` / `origin_id_pattern` 字段输出。

- [ ] **Step 6: frontend 类型**

`frontend/src/api/endpoints.ts`（222 行）：`id_pattern: string` 从 `/download/sources` 响应类型中删除。

- [ ] **Step 7: Run tests + 类型检查**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 8: Commit**

```bash
git add novelbase/source.py novelbase/sources/fanqie/__init__.py novelbase/sources/qidian/__init__.py novelbase/sources/qimao/__init__.py novelbase/sources/92xs/__init__.py novelbase/utils/build_manifest.py backend/routers/download.py cli/main.py frontend/src/api/endpoints.ts
git commit -m "refactor: 退役 ID_PATTERN/ORIGIN_ID_PATTERN/BOOK_URL_TEMPLATE（hash id 不可反查）"
```

---

### Task 7: 前端 SearchBar 移除纯数字 id 猜测

**Files:**
- Modify: `frontend/src/features/bookshelf/SearchBar.tsx:124-137`

**Interfaces:**
- Consumes: 无
- Produces: `urlIdPlatform` 不存在；`effectiveUrlPlatform` 仅来自 URL 检测

- [ ] **Step 1: 移除 urlIdPlatform**

`frontend/src/features/bookshelf/SearchBar.tsx`：删除 `urlIdPlatform` 定义（124-130 行），`effectiveUrlPlatform` 改为 `const effectiveUrlPlatform = urlPlatform;`。

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/bookshelf/SearchBar.tsx
git commit -m "refactor: 搜索框移除纯数字 id 平台猜测（hash id 非数字）"
```

---

### Task 8: 存量迁移脚本（仓库外）

**Files:**
- Create: `novel-downloader-tools/scripts/migrate_novel_id.py`（不进 git）

**Interfaces:**
- Consumes: Task 1 的 `canonical_book_url` / `make_novel_id`；`novelbase.core.storage.SQLiteStorage`；`novelbase.source.platform_from_url`
- Produces: 全部存量 `.db` 重命名为 hash id，库内 `meta.id` / `illustrations.owner_id` 同步，favorites 表更新

- [ ] **Step 1: 编写脚本**

创建 `novel-downloader-tools/scripts/migrate_novel_id.py`：

```python
"""一次性迁移：Novel.id 从 {platform}_{origin_id} 改为 sha256(canonical url)[:32]。

用法:
    python migrate_novel_id.py [--dry-run]

行为:
    1. 遍历 app_data/storage/novels/*.db，读库内 meta 表（旧 id + url）
    2. new_id = make_novel_id(canonical_book_url(url, platform_from_url(url)))
    3. 更新库内 meta.id 与 illustrations.owner_id（novel 行），重命名文件
    4. 更新 user_data.db 的 favorites.novel_id
    5. 幂等：已存在 {new_id}.db 的旧文件跳过（视为已迁移）
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(r"D:\Linux\novel-downloader\novel-downloader")
sys.path.insert(0, str(REPO))

from novelbase.utils.urls import canonical_book_url, make_novel_id
from novelbase.source import platform_from_url

NOVELS_DIR = REPO / "app_data" / "storage" / "novels"
USER_DB = REPO / "app_data" / "storage" / "users" / "default" / "user_data.db"


def migrate(dry_run: bool = True) -> None:
    mapping: dict[str, str] = {}
    for db_file in sorted(NOVELS_DIR.glob("*.db")):
        old_id = db_file.stem
        with sqlite3.connect(str(db_file), timeout=15) as conn:
            row = conn.execute("SELECT id, url FROM meta").fetchone()
        if not row:
            print(f"skip (no meta): {db_file.name}")
            continue
        stored_id, url = row
        if stored_id != old_id:
            print(f"skip (id mismatch {stored_id} != file {old_id}): {db_file.name}")
            continue
        platform = platform_from_url(url)
        if not platform:
            print(f"skip (unknown platform): {db_file.name} ({url})")
            continue
        new_id = make_novel_id(canonical_book_url(url, platform))
        if new_id == old_id:
            continue
        mapping[old_id] = new_id
        print(f"{old_id} -> {new_id}  ({url})")

    if dry_run:
        print(f"\n[dry-run] {len(mapping)} books would be renamed; "
              f"{len(set(mapping.values()))} unique new ids")
        return

    for old_id, new_id in mapping.items():
        db_file = NOVELS_DIR / f"{old_id}.db"
        if (NOVELS_DIR / f"{new_id}.db").exists():
            print(f"WARN skip (target exists — 疑似同书重复入库, 保留旧文件): {old_id}.db -> {new_id}.db")
            continue
        with sqlite3.connect(str(db_file), timeout=15) as conn:
            conn.execute("UPDATE meta SET id = ? WHERE id = ?", (new_id, old_id))
            conn.execute("UPDATE illustrations SET owner_id = ? "
                         "WHERE owner_type = 'novel' AND owner_id = ?", (new_id, old_id))
        db_file.rename(NOVELS_DIR / f"{new_id}.db")
        print(f"renamed: {old_id}.db -> {new_id}.db")

    if mapping:
        with sqlite3.connect(str(USER_DB), timeout=15) as conn:
            for old_id, new_id in mapping.items():
                conn.execute("UPDATE favorites SET novel_id = ? WHERE novel_id = ?",
                             (new_id, old_id))
        print(f"favorites updated: {len(mapping)} rows")
    print("done")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv[1:]
    migrate(dry_run=dry)
```

- [ ] **Step 2: dry-run 验证**

Run: `python novel-downloader-tools/scripts/migrate_novel_id.py --dry-run`
Expected: 打印每本书 `old_id -> new_id` 与总数；不产生任何文件改动

- [ ] **Step 3: 抽查单本正确性**

对 dry-run 输出中任意一本书，用 `make_novel_id(canonical_book_url(url, platform))` 与 `resolve_meta` 对同一 url 的返回值比对：
Run: `python -c "import sys; sys.path.insert(0, r'D:\Linux\novel-downloader\novel-downloader'); from novelbase.utils.urls import canonical_book_url, make_novel_id; from novelbase.source import platform_from_url; print(make_novel_id(canonical_book_url('https://fanqienovel.com/page/7123456789012345678', platform_from_url('https://fanqienovel.com/page/7123456789012345678'))))"`
Expected: 输出 32 位 hex，与 dry-run 输出一致（示例值替换为实际抽查的 url）

- [ ] **Step 4: 用户确认后执行真实迁移**

Run: `python novel-downloader-tools/scripts/migrate_novel_id.py`
Expected: 文件重命名 + favorites 更新完成；**执行前必须经用户明确同意**（数据不可逆操作）

- [ ] **Step 5: 迁移后验证**

Run: `python -c "import sys; sys.path.insert(0, r'D:\Linux\novel-downloader\novel-downloader'); from backend.routers.storage import _get_storage; s=_get_storage(); print([(n.id, n.title) for n in s.iter_metas(include_images=False)])"`
Expected: 输出全部书籍，id 均为 32 位 hex，`load_meta` 可按新 id 读回

---

### Task 9: 全量回归 + 收尾

**Files:**
- Modify: 无（仅验证）

- [ ] **Step 1: 后端全量测试**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 2: 前端类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: 导入自检**

Run: `python -m tests.check_imports`（如该模块存在；否则运行 `python -c "import novelbase, backend, cli"`）
Expected: 无 ImportError（`get_source_for_id` 已从 `novelbase/__init__.py` 导出移除）

- [ ] **Step 4: 全局搜索残留引用**

Run: `grep -rn "get_source_for_id\|origin_id\|ID_PATTERN\|ORIGIN_ID_PATTERN\|BOOK_URL_TEMPLATE" novelbase/ backend/ cli/ frontend/src/ tests/ --include="*.py" --include="*.ts" --include="*.tsx" | grep -v __pycache__`
Expected: 仅剩文档/注释中的历史说明，无代码引用（`_manifest.py` 为构建产物不在 git 跟踪，忽略）

- [ ] **Step 5: 如有残留引用，修复并单独 commit**

若 Step 4 发现残留代码引用，按「一个方面一条 commit」修复并提交。

- [ ] **Step 6: 更新 CHANGELOG（如用户要求版本变更）**

本次为行为变更（id 格式），若用户要求更新版本号，按项目约定同步 `pyproject.toml` + `novelbase/__init__.py` + `CHANGELOG.md`；版本号不确定时先询问用户。

---

## Self-Review 结果

- **Spec 覆盖**：核心生成（Task 1/3/4）、Novel.id 默认值（Task 2）、依赖点退役（Task 5/6/7）、迁移（Task 8）、测试（各 Task 内嵌 + Task 9 回归）——spec 各节均有对应任务。
- **占位符**：无 TBD/TODO；每个代码步骤给出完整实现或精确改动位置。
- **类型一致性**：`canonical_book_url(url, platform) -> str`、`make_novel_id(canonical_url) -> str` 在 Task 1 定义，Task 3/8 引用一致；`resolve_book_url(raw)` 签名不变。

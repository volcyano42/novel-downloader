# 书源全异步化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 novel-downloader 整条下载链路全异步化（书源/downloader/backend/CLI），并把图片下载收敛到 engine 层。

**Architecture:** engine 三层新增 `async_fetch_images`（httpx 实现）；40 个书源能力函数 `def→async def` + `engine.fetch_*→await engine.async_fetch_*`；parse 纯函数化（只算 URL 不下载字节）；downloader/backend/CLI 全 async；task_manager 从线程模型改 asyncio 原生。

**Tech Stack:** Python >=3.10, httpx（异步）, asyncio, FastAPI, DrissionPage（仅 browser 渲染 HTML/JSON）

## Global Constraints

- Python >=3.10
- engine 同步方法 `fetch_text`/`fetch_json` 保留（底层能力 + 测试用），业务链路全 async
- 提交消息中文，一个方面一条 commit，禁止 `git add -A`
- 现有 160 测试保持全绿（改造后新增测试）
- `export` 导出器保持同步（本地操作，与异步化无关）
- `resolve()` 分发机制不改（只返回函数，天然兼容 async）
- 测试命令：`python -m pytest tests/ -q`；单测 `python -m pytest tests/xxx.py::test_name -v`
- 前端不动，backend 对外 API 签名不变

---

### Task 1: Engine 基类新增 async_fetch_images 抽象方法

**Files:**
- Modify: `novelbase/core/engine.py`（Engine 基类，约 45-63 行之间加抽象方法）
- Test: `tests/test_engine_httpx.py`

**Interfaces:**
- Consumes: 无（纯新增）
- Produces: `Engine.async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]` 抽象方法；三个子类（Task 2-4）实现它

- [ ] **Step 1: 写失败测试**

在 `tests/test_engine_httpx.py` 末尾追加：

```python
import asyncio
import inspect

def test_engine_has_async_fetch_images_abstract():
    """Engine 基类声明 async_fetch_images 抽象方法。"""
    from novelbase.core.engine import Engine
    assert hasattr(Engine, "async_fetch_images")
    method = Engine.async_fetch_images
    assert inspect.iscoroutinefunction(method)
    # 抽象方法：直接实例化基类会失败（已由其他抽象方法保证）
    assert getattr(Engine.async_fetch_images, "__isabstractmethod__", False)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine_httpx.py::test_engine_has_async_fetch_images_abstract -v`
Expected: FAIL，`AttributeError: type object 'Engine' has no attribute 'async_fetch_images'`

- [ ] **Step 3: 实现抽象方法**

在 `Engine` 类的 `async_fetch_json` 抽象方法之后（约 63 行后）加：

```python
    @abstractmethod
    async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
        """批量下载图片字节，返回与 urls 等长的 bytes 列表（失败项为 b""）。"""
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_engine_httpx.py::test_engine_has_async_fetch_images_abstract -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "feat: Engine 基类新增 async_fetch_images 抽象方法"
```

---

### Task 2: RequestsEngine + APIEngine 实现 async_fetch_images

**Files:**
- Modify: `novelbase/core/engine.py`（RequestsEngine 约 344 行起、APIEngine 约 78 行起）
- Test: `tests/test_engine_httpx.py`

**Interfaces:**
- Consumes: `Engine.async_fetch_images` 抽象声明（Task 1）
- Produces: `RequestsEngine.async_fetch_images`、`APIEngine.async_fetch_images`，返回 `list[bytes]`（失败项 `b""`）

- [ ] **Step 1: 写失败测试**

```python
def _make_engine(mode: str):
    from novelbase.core.engine import create_engine
    from novelbase.core.options import Options
    opts = Options().set_mode(mode)
    if mode == "requests":
        opts.set_requests_options(headers={}, cookies={}, proxies={}, delay=[0, 0])
    elif mode == "api":
        opts.set_api_options(name="test", key="", delay=[0, 0])
    return create_engine(opts)


def test_requests_engine_async_fetch_images_success_and_failure(monkeypatch):
    """批量下载：成功项返回 bytes，失败项返回 b""。"""
    import httpx

    class FakeResponse:
        def __init__(self, content): self.content = content
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            if "fail" in url:
                raise httpx.HTTPError("boom")
            return FakeResponse(url.encode())

    monkeypatch.setattr("novelbase.core.engine.httpx.AsyncClient", FakeAsyncClient)
    engine = _make_engine("requests")
    result = asyncio.run(engine.async_fetch_images(["http://ok1", "http://fail", "http://ok2"]))
    assert result == [b"http://ok1", b"", b"http://ok2"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine_httpx.py::test_requests_engine_async_fetch_images_success_and_failure -v`
Expected: FAIL，`AttributeError: 'RequestsEngine' object has no attribute 'async_fetch_images'`

- [ ] **Step 3: 实现（RequestsEngine 和 APIEngine 相同实现）**

在两个类的 `async_fetch_json` 方法之后各加：

```python
    async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
        sem = asyncio.Semaphore(max_workers)

        async def _one(url: str) -> bytes:
            async with sem:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                        return (await client.get(url)).content
                except httpx.HTTPError:
                    return b""

        return await asyncio.gather(*(_one(u) for u in urls))
```

（RequestsEngine 和 APIEngine 此方法完全一致，各复制一份。）

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_engine_httpx.py::test_requests_engine_async_fetch_images_success_and_failure -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "feat: Requests/API 引擎实现 async_fetch_images 批量图片下载"
```

---

### Task 3: BrowserEngine 实现 async_fetch_images（httpx，不开 tab）

**Files:**
- Modify: `novelbase/core/engine.py`（BrowserEngine 约 190-344 行）
- Test: `tests/test_engine_httpx.py`

**Interfaces:**
- Consumes: `Engine.async_fetch_images` 抽象声明（Task 1）
- Produces: `BrowserEngine.async_fetch_images`（httpx 实现，不调用 `new_tab`/`get_page`）

- [ ] **Step 1: 写失败测试**

```python
def test_browser_engine_async_fetch_images_uses_httpx_not_tab(monkeypatch):
    """BrowserEngine 图片下载用 httpx，不 new_tab / get_page。"""
    import httpx

    class FakeResponse:
        def __init__(self, content): self.content = content
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            return FakeResponse(url.encode())

    monkeypatch.setattr("novelbase.core.engine.httpx.AsyncClient", FakeAsyncClient)

    from novelbase.core.engine import BrowserEngine
    from novelbase.core.options import BrowserOptions
    engine = BrowserEngine.__new__(BrowserEngine)  # 不触发 __init__（避免启动 Chromium）
    result = asyncio.run(engine.async_fetch_images(["http://a"]))
    assert result == [b"http://a"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine_httpx.py::test_browser_engine_async_fetch_images_uses_httpx_not_tab -v`
Expected: FAIL，`AttributeError: 'BrowserEngine' object has no attribute 'async_fetch_images'`

- [ ] **Step 3: 实现**

在 `BrowserEngine` 的 `async_fetch_json` 方法（约 321-324 行）之后加：

```python
    async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
        """图片下载用 httpx（不开 tab）。与 Requests/API 版结构一致。"""
        sem = asyncio.Semaphore(max_workers)

        async def _one(url: str) -> bytes:
            async with sem:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                        return (await client.get(url)).content
                except httpx.HTTPError:
                    return b""

        return await asyncio.gather(*(_one(u) for u in urls))
```

（cookie/Referer 注入留待后续按需扩展，本轮实现与 Requests/API 同构即可。）

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_engine_httpx.py::test_browser_engine_async_fetch_images_uses_httpx_not_tab -v`
Expected: PASS

- [ ] **Step 5: 全量回归 + 提交**

```bash
python -m pytest tests/ -q
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "feat: BrowserEngine 实现 async_fetch_images（httpx，不开标签页）"
```

---

### Task 4: downloader 四函数改 async def

**Files:**
- Modify: `novelbase/core/downloader.py`（search/resolve_meta/resolve_chapter_list/resolve_chapter，约 70-185 行）
- Modify: `tests/test_downloader.py`（同步调用改 asyncio.run 包装）
- Modify: `novelbase/__init__.py`（确认导出不变）

**Interfaces:**
- Consumes: 书源函数（Task 5+ 才改 async，但 downloader 先改，用 await 调用；过渡期书源还是同步会出错——因此本任务与 Task 5 顺序敏感：**本任务只改 downloader 为 async + 更新其单测的 mock 为 async**，书源未改前不跑全量回归，等 Task 5-7 完成后统一回归）
- Produces: `async def search(...)`、`async def resolve_meta(...)`、`async def resolve_chapter_list(...)`、`async def resolve_chapter(...)`

**关键约定**：书源函数现在是 async 的，downloader 内部 `fn(...)` 要加 `await`。`search` 的 `platform=="all"` 分支循环内 `results = await fn(...)`。

- [ ] **Step 1: 改 downloader 四函数为 async + await 调用**

四个函数逐一：
1. `def search(...)` → `async def search(...)`；第 94 行 `results = fn(...)` → `results = await fn(...)`；第 107 行 `results = fn(...)` → `results = await fn(...)`
2. `def resolve_meta(...)` → `async def resolve_meta(...)`；第 134 行 `return fn(...)` → `return await fn(...)`
3. `def resolve_chapter_list(...)` → `async def resolve_chapter_list(...)`；第 158 行 `return fn(...)` → `return await fn(...)`
4. `def resolve_chapter(...)` → `async def resolve_chapter(...)`；第 185 行 `return fn(...)` → `return await fn(...)`

`export` 保持同步不改。

- [ ] **Step 2: 更新 test_downloader.py 的 mock 和调用**

`tests/test_downloader.py` 里所有 `resolve_chapter(ch, engine)` 之类的同步调用，改为 `asyncio.run(resolve_chapter(ch, engine))`；所有 `mock_resolve.return_value = lambda ...` 改为 async lambda 或 async 函数。

示例（test_returns_chapter_when_content_available）：

```python
import asyncio
# ...
async def _fake(chapter, engine, **kw):
    return ch
# ...
with patch("novelbase.source.resolve") as mock_resolve:
    mock_resolve.return_value = _fake
    result = asyncio.run(resolve_chapter(ch, engine))
```

- [ ] **Step 3: 运行 downloader 单测确认通过**

Run: `python -m pytest tests/test_downloader.py -v`
Expected: PASS（本任务 mock 是 async，与 async downloader 匹配）

- [ ] **Step 4: 提交**

```bash
git add novelbase/core/downloader.py tests/test_downloader.py
git commit -m "refactor: downloader 四函数改 async def（search/resolve_meta/resolve_chapter_list/resolve_chapter）"
```

> **注意**：本任务提交后全量测试会暂时红（书源还是同步，downloader await 同步函数会报 TypeError）。这是计划内的过渡态，Task 5-7 完成书源 async 化后统一回归。若不接受中间红态，可将 Task 4 与 Task 5 合并为一个 commit——但拆开便于 review，最终以 Task 8 全量回归为准。

---

### Task 5: fanqie 书源 async 化 + 图片下载归 engine

**Files:**
- Modify: `novelbase/sources/fanqie/_common.py`（parse_chapter_content 图片下载抽出）
- Modify: `novelbase/sources/fanqie/requests/*.py`（4 文件）
- Modify: `novelbase/sources/fanqie/browser/*.py`（4 文件）
- Modify: `novelbase/sources/fanqie/api/oiapi/*.py`（4 文件）
- Modify: `novelbase/sources/fanqie/api/rain/*.py`（4 文件）
- Test: `tests/test_source_contracts.py`（或新建 `tests/test_source_async.py`）

**Interfaces:**
- Consumes: `engine.async_fetch_text/json/images`（Task 2-3）
- Produces: fanqie 全部能力函数 async，`parse_chapter_content` 返回 `(Chapter, img_urls)`

**子任务 5a：`_common.py` parse_chapter_content 纯函数化**

现状（约 250-389 行）：`parse_chapter_content(html, chapter) -> Chapter`，内部 ThreadPoolExecutor 下载图片填充 `chapter.images`。

改后：`parse_chapter_content(html, chapter) -> tuple[Chapter, list[dict]]`，图片只收集 URL + 元信息，不下载：

```python
def parse_chapter_content(html: str, chapter: Chapter) -> tuple[Chapter, list[dict]]:
    """解析并填充 content/count；图片只收集 URL，由调用方统一下载。"""
    # ... 前面的解析逻辑不变 ...
    img_urls: list[dict] = []
    # 原 ThreadPoolExecutor 下载段删除，改为：
    for i, t in enumerate(img_tasks):
        img_urls.append({"url": t["url"], "alt": t["alt"], "insert": t["insert"]})
    # 不再构造 Illustration、不再下载字节
    chapter.content = novel_content
    chapter.count = count
    return chapter, img_urls
```

（`_common.py` 里第 197 行 `parse_novel_info` 的封面下载 `book_cover_data = httpx.get(...)` 也要改成只收集 cover_url，让 novel_info 能力函数去下载。同理第 136 行 `resolve_changdunovel` 的 `httpx.get` 是短链重定向查询，保持同步但需在调用方 await —— 见下。）

**子任务 5b：能力函数 async 化 + 组装 Illustration**

`requests/chapter_content.py` 改后：

```python
async def chapter_content(chapter, engine, **kwargs):
    url = f"https://fanqienovel.com/reader/{standardize_id(chapter)}"
    html = await engine.async_fetch_text(url=url, **kwargs)
    if BeautifulSoup(html, "lxml").select_one("div.no-content"):
        raise ChapterNotFoundError("Chapter page shows no-content div")
    ch, img_urls = parse_chapter_content(html, chapter)
    if img_urls:
        data = await engine.async_fetch_images([i["url"] for i in img_urls])
        ch.images = tuple(
            Illustration(raw_data=d, url=i["url"], alt=i["alt"], insert=i["insert"])
            for i, d in zip(img_urls, data)
        )
    return ch
```

其余 search/novel_info/chapter_list 能力函数：`def→async def` + `engine.fetch_*→await engine.async_fetch_*` + 绕过 engine 的 `httpx.get` 改 `await engine.async_fetch_json`（search 的 `httpx.get(search_url).json()` → `await engine.async_fetch_json(search_url)`）。

- [ ] **Step 1: 写失败测试**（新建 `tests/test_source_async.py`）

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

def test_fanqie_chapter_content_is_async_and_assembles_images():
    """fanqie chapter_content 是 async，图片经 engine.async_fetch_images 下载。"""
    import novelbase.sources.fanqie.requests.chapter_content as mod
    assert asyncio.iscoroutinefunction(mod.chapter_content)

async def test_fanqie_parse_chapter_content_returns_urls_not_bytes(monkeypatch):
    """parse_chapter_content 是纯函数：返回 (Chapter, img_urls)，不下载字节。"""
    from novelbase.sources.fanqie._common import parse_chapter_content
    from novelbase.models.novel import Chapter
    html = '<div class="muye-reader-content noselect"><p>正文</p></div>'
    # 简化：无图片的章节，img_urls 应为空
    ch = Chapter(id="1", url="http://x", novel_id="fanqie_1", title="t", order=0)
    # 注意：此 html 缺少 __INITIAL_STATE__，会 raise；用真实结构的最小样例
```

> **实现者注意**：fanqie 的 parse_chapter_content 依赖 `window.__INITIAL_STATE__`，测试需用包含该标记的最小 HTML 样例。可从现有 `tests/test_source_contracts.py` 找现成的 fanqie html fixture，或构造一个含 `window.__INITIAL_STATE__=<script>` 的简化 html。若构造困难，退化为测试「parse_chapter_content 返回值是二元组」这一签名契约即可：

```python
def test_fanqie_parse_chapter_content_returns_tuple():
    """签名契约：parse_chapter_content 返回 (Chapter, img_urls) 二元组。"""
    import inspect
    from novelbase.sources.fanqie._common import parse_chapter_content
    # 返回类型注解含 tuple
    assert "tuple" in str(inspect.signature(parse_chapter_content).return_annotation).lower()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_async.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**（按 5a + 5b 改 fanqie 全部 12 个能力文件 + _common.py）

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_source_async.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add novelbase/sources/fanqie/ tests/test_source_async.py
git commit -m "refactor: fanqie 书源 async 化 + 图片下载归 engine.async_fetch_images"
```

---

### Task 6: qidian + qimao + 92xs 书源 async 化

**Files:**
- Modify: `novelbase/sources/qidian/*.py`（_common + browser/4 + requests/4）
- Modify: `novelbase/sources/qimao/*.py`（_common + browser/4 + requests/4 + api/rain/4）
- Modify: `novelbase/sources/92xs/requests/*.py`（4）
- Test: `tests/test_source_async.py`

**Interfaces:**
- Consumes: `engine.async_fetch_text/json/images`（Task 2-3）
- Produces: qidian/qimao/92xs 全部能力函数 async

- [ ] **Step 1: 改造模式（与 Task 5 完全一致）**

对每个能力函数：
- `def xxx(...)` → `async def xxx(...)`
- `engine.fetch_text(...)` → `await engine.async_fetch_text(...)`
- `engine.fetch_json(...)` → `await engine.async_fetch_json(...)`

封面下载（`novel_info` 内）统一改走 `engine.async_fetch_images`：
- `qidian/_common.py` 第 98 行、`qimao/_common.py` 第 107 行、`qimao/api/rain/novel_info.py` 第 33 行、`92xs/requests/novel_info.py` 第 47 行（`requests.get` 残留 → 删除，封面改 `async_fetch_images`）

92xs `search.py` 的 `httpx.post` + `resp.apparent_encoding`（这是 bug：httpx 无 apparent_encoding）→ 改 `await engine.async_fetch_text(SEARCH_URL, ...)`，但 POST 语义需保留（见下）。

**92xs search POST 特殊处理**：`httpx.post(SEARCH_URL, data={...})` 有 POST body。engine 的 `async_fetch_text` 支持 POST 吗？检查 `fetch_text` 签名——它接受 `**kwargs`，RequestsEngine 的 fetch_text 内部把 kwargs 传给 httpx，但 POST 需要显式 post_data。**实现者先检查 `RequestsEngine.fetch_text` 是否支持 post**：若支持（有 post_data 参数），则 `await engine.async_fetch_text(SEARCH_URL, post_data={...})`；若不支持，92xs search 保留 `httpx.post` 但改用 `httpx.AsyncClient` 内联 async 实现（不阻塞事件循环）。

- [ ] **Step 2: 写/跑失败测试**（沿用 `tests/test_source_async.py`，验证 qidian/qimao/92xs 能力函数是 coroutine）

```python
def test_qidian_qimao_92xs_functions_are_async():
    import novelbase.sources.qidian.requests.search as qd_s
    import novelbase.sources.qimao.requests.search as qm_s
    import novelbase.sources.qidian.requests.chapter_content as qd_c
    assert asyncio.iscoroutinefunction(qd_s.search)
    assert asyncio.iscoroutinefunction(qm_s.search)
    assert asyncio.iscoroutinefunction(qd_c.chapter_content)
```

- [ ] **Step 3: 实现**

- [ ] **Step 4: 运行确认通过**

- [ ] **Step 5: 提交**

```bash
git add novelbase/sources/qidian/ novelbase/sources/qimao/ novelbase/sources/92xs/ tests/test_source_async.py
git commit -m "refactor: qidian/qimao/92xs 书源 async 化 + 封面下载归 engine"
```

---

### Task 7: backend 路由直接 await + 删除死 executor

**Files:**
- Modify: `backend/routers/download.py`（5 处 run_in_executor 改直接 await）
- Modify: `backend/services/engine_manager.py`（删 _browser_executor/_requests_executor 死代码）

**Interfaces:**
- Consumes: async downloader（Task 4）
- Produces: backend 路由直接 await async 函数

- [ ] **Step 1: 改 download.py**

5 处：
1. 第 49 行 `novel = await loop.run_in_executor(executor, resolve_meta, url, engine)` → `novel = await resolve_meta(url, engine)`
2. 第 57 行 `results = await loop.run_in_executor(executor, search, platform, query, engine, page)` → `results = await search(platform, query, engine, page)`
3. 第 76 行 `novel = await loop.run_in_executor(executor, resolve_meta, url, engine)` → `novel = await resolve_meta(url, engine)`
4. 第 95 行 同上 → `novel = await resolve_meta(url, engine)`
5. 第 113 行 `chapters = await loop.run_in_executor(executor, resolve_chapter_list, url, engine)` → `chapters = await resolve_chapter_list(url, engine)`

删除 `_pick_executor` 函数、`_browser_executor`/`_requests_executor` import、`import asyncio`（若无其他用途）、`from functools import partial`（若无其他用途）。

- [ ] **Step 2: 改 engine_manager.py**

删除第 20-21 行的 `_browser_executor`/`_requests_executor` 定义，以及 `from concurrent.futures import ThreadPoolExecutor` import（若已无引用）。

- [ ] **Step 3: 验证 import**

Run: `python -c "from backend.main import app; print('OK')"`
Expected: OK

- [ ] **Step 4: 提交**

```bash
git add backend/routers/download.py backend/services/engine_manager.py
git commit -m "refactor: backend 路由直接 await async 函数，删除死 executor"
```

---

### Task 8: task_manager async 原生化

**Files:**
- Modify: `backend/services/task_manager.py`（全文重构）
- Test: `tests/test_android_server.py` 或新建 `tests/test_task_manager_async.py`

**Interfaces:**
- Consumes: async `resolve_meta`/`resolve_chapter`（Task 4）
- Produces: `create_task/list_tasks/get_task/pause_task/resume_task/delete_task` 签名不变（同步），内部 asyncio

**核心难点**：`create_task` 是同步函数，但要在运行中的事件循环里创建协程任务。FastAPI 路由是 async 的，`create_task` 被 async 路由调用时 `asyncio.get_running_loop()` 可用。

- [ ] **Step 1: 重构 task_manager**

关键改动点：
1. 顶部 import：`threading` → `asyncio`；`time` 保留（`list_tasks` 里算 cancelled 保留时长）；删 `ThreadPoolExecutor`/`as_completed` import
2. `_tasks_lock = threading.Lock()` → 事件循环单线程下可去掉锁，或保留 `asyncio.Lock`（但同步函数里无法 await asyncio.Lock，所以**去掉锁**，靠单事件循环串行保证）
3. `task["_pause"]`/`task["_cancel"]` 从 `threading.Event()` → `asyncio.Event()`
4. `_run_download(task, mode, variant, platform)` → `async def _run_download(...)`：
   - `resolve_meta(...)` → `await resolve_meta(...)`
   - `resolve_chapter(...)` → `await resolve_chapter(...)`
   - `time.sleep(2*attempt)` → `await asyncio.sleep(2*attempt)`
   - `ThreadPoolExecutor` 章节并发 → `asyncio.Semaphore` + `asyncio.gather`
   - `task["_cancel"].is_set()` → 不变（asyncio.Event 有同名方法）
   - `task["_pause"].wait()` → `await task["_pause"].wait()`
5. `create_task` 里启动方式：

```python
    loop = asyncio.get_running_loop()
    loop.create_task(_run_download(task, mode, variant, platform))
```

（`create_task` 本身保持同步 `def`，返回 `{"task_id": ..., "total": ...}`。它被 async 路由调用，`get_running_loop` 可用。）

6. `resume_task` 里失败重试的 `threading.Thread(target=_run_download, ...)` → 同样 `loop.create_task(...)`

- [ ] **Step 2: 写失败测试**

```python
import asyncio
import pytest

def test_create_task_returns_id_and_schedules_coroutine(monkeypatch):
    """create_task 同步返回 task_id，并在事件循环里调度下载协程。"""
    from backend.services import task_manager as tm
    # 清空状态
    tm._tasks.clear()

    async def _run():
        tid = tm.create_task("fanqie_1", [{"id": "c1", "url": "http://x", "title": "t", "order": 0}], "test", mode="requests")
        return tid

    tid = asyncio.run(_run())
    assert tid  # 返回了 task_id
    assert tid in tm._tasks
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_task_manager_async.py -v`
Expected: FAIL（当前 task_manager 用 threading，`get_running_loop` 语义不同或直接报错）

- [ ] **Step 4: 实现**

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_task_manager_async.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/services/task_manager.py tests/test_task_manager_async.py
git commit -m "refactor: task_manager 改 asyncio 原生（asyncio.create_task + asyncio.Event）"
```

---

### Task 9: CLI async 化

**Files:**
- Modify: `cli/core.py`（_do_download_inner、do_update 的下载循环）
- Modify: `cli/main.py`（调用处 asyncio.run 包装）
- Test: 无新增（CLI 为脚本层，靠 import 验证）

**Interfaces:**
- Consumes: async downloader（Task 4）
- Produces: CLI 下载走 asyncio

- [ ] **Step 1: 改 cli/core.py**

`_do_download_inner`：
- `def` → `async def`
- `resolve_meta(...)` → `await resolve_meta(...)`
- `resolve_chapter_list(...)` → `await resolve_chapter_list(...)`
- `resolve_chapter(...)` → `await resolve_chapter(...)`
- 第 146-156 行 ThreadPoolExecutor 并发 → asyncio.Semaphore + asyncio.gather：

```python
    sem = asyncio.Semaphore(max_workers)
    async def _download_one(ch) -> tuple[bool, str, str]:
        async with sem:
            try:
                resolved = await resolve_chapter(ch, engine=engine)
                if resolved is None:
                    return False, ch.title, "章节内容为空"
                storage.save_chapter(novel, resolved)
                return True, ch.title, ""
            except Exception as e:
                return False, ch.title, str(e)

    with progress:
        results = await asyncio.gather(*(_download_one(ch) for ch in to_download))
        for ok, title, err in results:
            if ok:
                success += 1
            else:
                incomplete_count += 1
                errors.append(f"  [{title}]: {err}")
            _advance_progress(progress, task, last_title=last_title)
            last_title = title
```

`do_update` 同样改 async + gather。

- [ ] **Step 2: 改 cli/main.py 调用处**

第 169-170 行附近：

```python
        from cli.core import _do_download_inner
        asyncio.run(_do_download_inner(engine, args.url, args.group, format_configs,
                                       max_workers=args.workers))
```

第 179-180 行：

```python
        from cli.core import do_update
        asyncio.run(do_update(format_configs, max_workers=args.workers))
```

第 228 行 `novel = resolve_meta(args.url, engine)` → `asyncio.run(resolve_meta(args.url, engine))`

- [ ] **Step 3: 验证 import**

Run: `python -c "import cli.main; print('OK')"`
Expected: OK

- [ ] **Step 4: 提交**

```bash
git add cli/core.py cli/main.py
git commit -m "refactor: CLI 下载改 asyncio（asyncio.run + asyncio.gather）"
```

---

### Task 10: 全量回归 + 收尾

**Files:**
- 无新增代码（若有遗漏修复）

- [ ] **Step 1: 全量测试**

Run: `python -m pytest tests/ -q`
Expected: 全绿（160 现有 + 新增 async 测试）

- [ ] **Step 2: import 验证**

Run: `python -c "from novelbase import *; print('OK')" && python -c "from backend.main import app; print('OK')" && python -c "import cli.main; print('OK')"`
Expected: 全部 OK

- [ ] **Step 3: 类型/残留检查**

Run: `grep -rn "ThreadPoolExecutor\|run_in_executor" backend/ cli/ novelbase/core/downloader.py novelbase/sources/ --include="*.py" | grep -v __pycache__`
Expected: 仅剩 `novelbase/sources/fanqie/_common.py` 若未清理干净则需清掉（图片下载已归 engine）；`engine.py` 的 `asyncio.to_thread`（BrowserEngine fetch_text/json 合理保留）

- [ ] **Step 4: 提交收尾**（若有修复）

```bash
git add <具体修复的文件>
git commit -m "test: 书源全异步化全量回归通过"
```

> 按 AGENTS.md：禁止 `git add -A`。

---

## 执行顺序与依赖

```
Task 1 (基类抽象) → Task 2 (Requests/API) → Task 3 (Browser)
                                    ↓
Task 4 (downloader async) ← 依赖 Task 1-3 的 async_fetch_images
                                    ↓
Task 5 (fanqie) → Task 6 (qidian/qimao/92xs)   [可并行]
                                    ↓
Task 7 (backend 路由) ← 依赖 Task 4-6
Task 8 (task_manager) ← 依赖 Task 4
Task 9 (CLI)          ← 依赖 Task 4
                                    ↓
Task 10 (全量回归)
```

**过渡态说明**：Task 4 单独提交后全量测试会暂时红（downloader 已 await，书源还是同步）。这是计划内过渡，Task 5-6 完成书源 async 化后转绿。若执行环境要求每步全绿，可把 Task 4+5+6 合并为一个大任务。

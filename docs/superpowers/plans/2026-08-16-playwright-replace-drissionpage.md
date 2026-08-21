# Playwright 替换 DrissionPage 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 BrowserEngine 及 browser 书源的 DrissionPage 替换为 Playwright，让 browser 模式获得原生 async。

**Architecture:** BrowserEngine 改为懒启动（`__init__` 不启动浏览器，首次 async 调用时 `await` 启动），`async_fetch_text/json` 直接 `await` Playwright 原生 API（去掉 `asyncio.to_thread` 假异步）；同步 `fetch_text/json` 用独立浏览器会话（`asyncio.run` + `async with async_playwright()`）兼容基类接口。统一内置 chromium（`playwright install chromium`），不依赖系统 Chrome。

**Tech Stack:** Python 3.10+、playwright（async_api）、httpx、pytest、pytest-asyncio

## Global Constraints

- Python >=3.10（`str | None` 语法）
- 统一内置 chromium，不 `channel="chrome"`，不依赖系统 Chrome
- BrowserEngine 的 `async_fetch_*` 必须是真异步（不得 `asyncio.to_thread` 包装）
- `async_fetch_images` 保持 httpx 实现不变（图片下载不开浏览器）
- Engine 基类 `fetch_text/fetch_json` 同步抽象方法保留（三引擎接口不变）
- 提交消息中文，禁止 `git add -A`
- 现有 191 测试保持全绿（受影响的 browser 测试同步改写）
- Termux/Android 排除项从 `drissionpage` 改为 `playwright`

---

### Task 1: BrowserEngine 换 Playwright（懒启动 + 真异步）

**Files:**
- Modify: `pyproject.toml:17`（`drissionpage` → `playwright`）
- Modify: `requirements.txt:2`（`drissionpage` → `playwright`）
- Modify: `novelbase/core/engine.py:212-378`（BrowserEngine 整体重写）
- Modify: `tests/test_engine_httpx.py:133-159`（改写 browser 测试）

**Interfaces:**
- Consumes: `BrowserOptions`（`browser_type`/`headless`/`user_data_dir`/`viewport`/`extra_args`/`delay`/`timeout`/`retry_times`/`backoff_factor`，均在 `novelbase/core/options.py:28-37`）
- Produces:
  - `BrowserEngine.__init__(options)` — 同步，仅存 options + 懒启动状态（`_browser=None`、`_context=None`、`_playwright=None`），不启动浏览器
  - `async def new_page()` — 懒启动后返回 Playwright page（供书源交互）
  - `async def async_fetch_text(url, skip_delay=False, encoding=None, **kwargs) -> str`
  - `async def async_fetch_json(url, skip_delay=False, **kwargs) -> dict`
  - `def fetch_text(url, skip_delay=False, encoding=None, **kwargs) -> str` — 独立会话（`asyncio.run`）
  - `def fetch_json(url, skip_delay=False, **kwargs) -> dict` — 独立会话
  - `def close()` — 同步，关闭懒启动的 browser（无 loop 用 asyncio.run，有 loop 用 create_task）

- [ ] **Step 1: 写失败测试**

替换 `tests/test_engine_httpx.py` 的 browser 测试段（第 133-159 行的 `_browser_engine`、`test_browser_engine_has_async_methods`、`test_browser_engine_async_delegates_to_sync`）：

```python
import asyncio


class FakePlaywright:
    """mock playwright.async_api.async_playwright 的最小替身。

    FakePW 既是 context manager（支持 async with）又是 Playwright 实例（有 chromium）。
    """

    def __init__(self, monkeypatch):
        self.calls = []
        self._install(monkeypatch)

    def _install(self, monkeypatch):
        fake = self

        class FakePage:
            async def goto(self, url, timeout=None):
                fake.calls.append(("goto", url))
            async def content(self):
                fake.calls.append(("content",))
                return "<html>ok</html>"
            async def close(self):
                fake.calls.append(("page_close",))

        class FakeContext:
            async def new_page(self):
                fake.calls.append(("new_page",))
                return FakePage()
            async def close(self):
                fake.calls.append(("context_close",))

        class FakeBrowser:
            async def new_context(self, **kwargs):
                fake.calls.append(("new_context", kwargs))
                return FakeContext()
            async def new_page(self):
                fake.calls.append(("new_page",))
                return FakePage()
            async def close(self):
                fake.calls.append(("browser_close",))

        class FakeChromium:
            async def launch(self, headless=True, args=None):
                fake.calls.append(("launch", headless))
                return FakeBrowser()

        class FakePW:
            def __init__(self):
                self.chromium = FakeChromium()
            async def start(self):
                return self
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                fake.calls.append(("pw_stop",))

        import novelbase.core.engine as eng
        monkeypatch.setattr(eng, "_async_playwright", lambda: FakePW())


def _browser_engine():
    from novelbase.core.options import BrowserOptions
    from novelbase.core.engine import BrowserEngine
    return BrowserEngine(BrowserOptions(delay=(0, 0), headless=True))


def test_browser_engine_lazy_init(monkeypatch):
    """__init__ 不启动浏览器（懒启动），_browser 初始为 None。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()
    assert engine._browser is None
    assert fake.calls == []


def test_browser_engine_async_fetch_text_is_native(monkeypatch):
    """async_fetch_text 直接 await Playwright（不再委托同步 fetch_text）。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    # 懒启动 + goto + content 都被真实调用
    assert ("launch", True) in fake.calls
    assert ("new_context", {}) in fake.calls  # 无 user_data_dir/viewport 时 kwargs 为空
    assert ("new_page",) in fake.calls
    assert ("goto", "http://x") in fake.calls
    assert ("content",) in fake.calls


def test_browser_engine_sync_fetch_text_isolated_session(monkeypatch):
    """同步 fetch_text 用独立浏览器会话，不触碰懒启动的 self._browser。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()
    result = engine.fetch_text("http://sync", skip_delay=True)
    assert result == "<html>ok</html>"
    # 独立会话启停：browser 被 close，pw 被 stop
    assert ("browser_close",) in fake.calls
    assert ("pw_stop",) in fake.calls
    # 懒启动的 self._browser 仍为 None（未被触碰）
    assert engine._browser is None


def test_browser_engine_new_page_async(monkeypatch):
    """new_page 是 async 方法，懒启动后返回 page。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def _run():
        page = await engine.new_page()
        return page
    page = asyncio.run(_run())
    assert page is not None
    assert ("new_page",) in fake.calls
    assert engine._browser is not None  # 懒启动完成
```

删除原 `test_browser_engine_async_delegates_to_sync`（测的是假异步委托，改造后不适用）。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine_httpx.py -v -k "browser" 2>&1 | tail -20`
Expected: FAIL —— `AttributeError: module 'novelbase.core.engine' has no attribute '_async_playwright'`（或 engine 仍用 DrissionPage 导致 mock 不生效）

- [ ] **Step 3: 实现 BrowserEngine 重写**

`pyproject.toml` 第 17 行：`"drissionpage",` → `"playwright",`
`requirements.txt` 第 2 行：`drissionpage` → `playwright`

`novelbase/core/engine.py` 顶部新增 import（第 1-15 行区域）：

```python
def _async_playwright():
    from playwright.async_api import async_playwright
    return async_playwright()
```

替换 `BrowserEngine` 类（第 212-378 行）：

```python
class BrowserEngine(Engine):
    def __init__(self, options: BrowserOptions) -> None:
        super().__init__()
        self.name = "browser"
        self.options = options
        self._playwright = None
        self._browser = None
        self._context = None
        # 懒启动：__init__ 不启动浏览器，首次 async 调用时 _ensure_browser 启动

    def update_options(self, options: BrowserOptions) -> None:
        """热更新 delay/timeout/retry 等参数，不重建浏览器。

        browser_type / headless / user_data_dir / viewport / extra_args 变更才重建浏览器。
        """
        needs_rebuild = False
        for hard_attr in ("browser_type", "headless", "extra_args"):
            new_val = getattr(options, hard_attr, None)
            if new_val is not None and new_val != getattr(self.options, hard_attr, None):
                setattr(self.options, hard_attr, new_val)
                needs_rebuild = True
        new_ud = getattr(options, "user_data_dir", None)
        old_ud = getattr(self.options, "user_data_dir", None)
        if str(new_ud or "") != str(old_ud or ""):
            self.options.user_data_dir = options.user_data_dir
            needs_rebuild = True
        new_vp = getattr(options, "viewport", None)
        if new_vp is not None and new_vp != getattr(self.options, "viewport", None):
            self.options.viewport = new_vp
            needs_rebuild = True

        for attr in ("delay", "timeout", "retry_times", "backoff_factor"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

        if needs_rebuild:
            self._schedule_rebuild()

    def _schedule_rebuild(self) -> None:
        """标记浏览器需重建：下一次 async 调用前关闭旧 browser 并重建。"""
        # 已有运行中 loop 才真正关闭；无 loop（尚未启动）时置 None 即可
        if self._browser is not None or self._context is not None:
            self._close_running()

    def _close_running(self) -> None:
        browser, context, pw = self._browser, self._context, self._playwright
        self._browser = self._context = self._playwright = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._shutdown(browser, context, pw))
        else:
            loop.create_task(self._shutdown(browser, context, pw))

    @staticmethod
    async def _shutdown(browser, context, pw):
        for obj in (browser, context):
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass
        if pw is not None:
            try:
                await pw.stop()
            except Exception:
                pass

    async def _ensure_browser(self):
        if self._browser is not None:
            return
        pw = _async_playwright()
        self._playwright = await pw.start()
        browser_type = getattr(self._playwright, self.options.browser_type, None)
        if browser_type is None:
            raise ValueError(f"不支持的 browser_type: {self.options.browser_type}")
        self._browser = await browser_type.launch(
            headless=self.options.headless,
            args=self.options.extra_args or [],
        )
        ctx_kwargs = {}
        if self.options.user_data_dir:
            ctx_kwargs["user_data_dir"] = str(self.options.user_data_dir)
        if self.options.viewport:
            ctx_kwargs["viewport"] = self.options.viewport
        self._context = await self._browser.new_context(**ctx_kwargs)
        _log.info("BrowserEngine started: headless=%s", self.options.headless)

    async def new_page(self):
        """懒启动后返回一个新的 Playwright page（供书源交互）。"""
        await self._ensure_browser()
        return await self._context.new_page()

    async def _do_fetch_text(self, url, skip_delay=False, **kwargs):
        page = await self._context.new_page()
        try:
            for i in range(self.options.retry_times):
                if i > 0:
                    _log.warning(
                        "fetch_text retry %s/%s: url=%s",
                        i + 1, self.options.retry_times, mask_key(url[:120]),
                    )
                try:
                    await page.goto(url, timeout=self.options.timeout * 1000)
                    if not skip_delay:
                        await asyncio.sleep(random.uniform(*self.options.delay))
                    html = await page.content()
                    _log.debug("fetch_text ok: len=%s url=%s", len(html), mask_key(url[:120]))
                    return html
                except Exception as e:
                    backoff = self.options.backoff_factor * (2 ** i)
                    _log.debug("fetch_text attempt %s failed: %s; backoff %.1fs",
                               i + 1, e, backoff)
                    await asyncio.sleep(backoff)
            _log.error("fetch_text exhausted retries: url=%s", mask_key(url[:120]))
            raise NetworkError(
                f"fetch_text failed after {self.options.retry_times} retries",
                url=url,
            )
        finally:
            await page.close()

    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        """真异步：直接 await Playwright（不 to_thread）。"""
        _log.debug("async_fetch_text start: url=%s", mask_key(url[:120]))
        await self._ensure_browser()
        return await self._do_fetch_text(url, skip_delay=skip_delay, **kwargs)

    async def async_fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        text = await self.async_fetch_text(url=url, skip_delay=skip_delay, **kwargs)
        return json.loads(text)

    def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        """同步入口：独立浏览器会话（自启自停），不触碰懒启动的 browser。

        注意：不能在已运行的事件循环内调用（会抛 RuntimeError），
        异步上下文请用 async_fetch_text。
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "fetch_text 不能在异步上下文中同步调用，请改用 async_fetch_text"
            )
        return asyncio.run(self._fetch_in_isolated_session(url, skip_delay=skip_delay, **kwargs))

    async def _fetch_in_isolated_session(self, url, skip_delay=False, **kwargs) -> str:
        async with _async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.options.headless,
                args=self.options.extra_args or [],
            )
            try:
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=self.options.timeout * 1000)
                    return await page.content()
                finally:
                    await page.close()
            finally:
                await browser.close()

    def fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        text = self.fetch_text(url=url, skip_delay=skip_delay, **kwargs)
        return json.loads(text)

    async def async_fetch_images(self, urls, max_workers=5) -> list[bytes]:
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

    def close(self) -> None:
        super().close()
        if self._browser is not None or self._context is not None or self._playwright is not None:
            self._close_running()

    @property
    def browser(self) -> Any:
        """返回底层 Playwright browser 实例（懒启动后才有，否则 None）。"""
        return self._browser
```

删除 `get_page` / `new_page`（旧同步版）/ `_init_browser` / `_thread_local` / `_page_lock` / `_page_pool`。

注意：`page.goto` 的 `timeout` 单位是毫秒，`self.options.timeout` 是秒，需 `* 1000`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_engine_httpx.py -v 2>&1 | tail -20`
Expected: PASS（新增 4 个 browser 测试 + 原 requests/api 测试全绿）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests/ -q 2>&1 | tail -3`
Expected: 全绿（约 195 passed, 2 skipped）

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "重构: BrowserEngine 从 DrissionPage 换 Playwright（懒启动 + 真异步）"
```

---

### Task 2: qidian/qimao 书源交互改 Playwright API

**Files:**
- Modify: `novelbase/sources/qidian/browser/search.py`
- Modify: `novelbase/sources/qimao/browser/chapter_list.py`
- Test: `tests/test_browser_sources.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `async def new_page()`；Playwright page 的 `goto`/`locator`/`click`/`content`/`close`
- Produces: 书源函数签名不变——`async def search(query, engine, **kwargs) -> list[SearchResult]`、`async def chapter_list(url, engine, **kwargs) -> list[Chapter]`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_browser_sources.py`：

```python
import asyncio

from novelbase.sources.qidian.browser import search as qidian_search
from novelbase.sources.qimao.browser import chapter_list as qimao_chapter_list


class FakePage:
    """mock Playwright page：记录交互调用。"""

    def __init__(self, html="<html></html>"):
        self.html = html
        self.gotos = []
        self.clicks = []
        self.waits = []
        self.counts = []
        self.closed = False

    async def goto(self, url, timeout=None):
        self.gotos.append(url)

    async def content(self):
        return self.html

    def locator(self, selector):
        self.last_selector = selector
        return self

    async def click(self):
        self.clicks.append(self.last_selector)

    async def count(self):
        self.counts.append(self.last_selector)
        return 1  # 默认存在元素

    async def wait_for_timeout(self, ms):
        self.waits.append(ms)

    async def close(self):
        self.closed = True


class FakeEngine:
    """最小 engine：只实现书源用到的 new_page 和 async_fetch_text。"""

    def __init__(self, page):
        self._page = page
        self.new_page_calls = 0
        self.async_fetch_urls = []

    async def new_page(self):
        self.new_page_calls += 1
        return self._page

    async def async_fetch_text(self, url, skip_delay=False, **kwargs):
        self.async_fetch_urls.append(url)
        return self._page.html


def test_qidian_search_page1_uses_async_fetch_text():
    """page=1 不 new_page，直接 async_fetch_text。"""
    page = FakePage("<html>r1</html>")
    engine = FakeEngine(page)
    result = asyncio.run(qidian_search.search("斗罗", engine, page=1))
    assert engine.new_page_calls == 0  # 不 new_page
    assert engine.async_fetch_urls != []  # 走了 async_fetch_text
    assert isinstance(result, list)  # parse 对空 html 返回空列表


def test_qidian_search_page2_uses_new_page_and_click():
    """page>1 用 new_page + locator(click)，不再 to_thread。"""
    page = FakePage("<html>r2</html>")
    engine = FakeEngine(page)
    result = asyncio.run(qidian_search.search("斗罗", engine, page=2))
    assert engine.new_page_calls == 1
    assert page.clicks != []  # 点击了下一页
    assert page.closed is True
    assert isinstance(result, list)


def test_qimao_chapter_list_clicks_catalog_tab():
    """qimao 点击 .tab-inner 触发目录加载，不再 to_thread。"""
    page = FakePage("<html>catalog</html>")
    engine = FakeEngine(page)
    result = asyncio.run(qimao_chapter_list.chapter_list(
        "https://www.qimao.com/shuku/12345/", engine))
    assert engine.new_page_calls == 1
    assert page.clicks == [".tab-inner"]
    assert page.waits == [3000]
    assert page.closed is True
    assert isinstance(result, list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_browser_sources.py -v 2>&1 | tail -20`
Expected: FAIL —— 书源仍用 `engine.new_page()` 同步调用 + `asyncio.to_thread`，`new_page` 现在返回协程而非 page

- [ ] **Step 3: 实现书源改造**

`novelbase/sources/qidian/browser/search.py`：

```python
import asyncio

from .._common import parse_search_result
from novelbase.models.novel import SearchResult


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    search_url = f"https://www.qidian.com/so/{query}.html"

    if page > 1:
        # Playwright 原生 async：直接 await，不再 to_thread
        browser_page = await engine.new_page()
        try:
            await browser_page.goto(search_url)
            next_page_xpath = f"/html/body/div[1]/div[3]/div[1]/div[4]/div[2]/div/div/ul/li[{page}]"
            await browser_page.locator(f"xpath={next_page_xpath}").click()
            html = await browser_page.content()
        finally:
            await browser_page.close()
    else:
        html = await engine.async_fetch_text(search_url, **kwargs)

    return list(parse_search_result(html))
```

`novelbase/sources/qimao/browser/chapter_list.py`：

```python
"""qimao browser - fetch chapter list.
Browser engine needs to click the catalog tab to trigger chapter loading."""

from .._common import parse_chapter_list, standardize_id
from novelbase.models.novel import Chapter


async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"

    # Playwright 原生 async：直接 await，不再 to_thread
    page = await engine.new_page()
    try:
        await page.goto(url)
        catalog_tab = page.locator(".tab-inner")
        if await catalog_tab.count() > 0:
            await catalog_tab.click()
            await page.wait_for_timeout(3000)
        html = await page.content()
    finally:
        await page.close()

    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    return list(chapters)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_browser_sources.py -v 2>&1 | tail -20`
Expected: PASS（3 个书源测试全绿）

- [ ] **Step 5: Commit**

```bash
git add novelbase/sources/qidian/browser/search.py novelbase/sources/qimao/browser/chapter_list.py tests/test_browser_sources.py
git commit -m "重构: qidian/qimao browser 书源交互改 Playwright（去 to_thread）"
```

---

### Task 3: 打包脚本 + 排除项更新

**Files:**
- Modify: `scripts/build-portable.ps1:174,179`（Chrome 说明改 playwright install chromium）
- Modify: `scripts/build-portable.sh:181,248`（排除项 + 说明）
- Modify: `scripts/termux-preinstall.sh:41`（排除项）
- Modify: `.github/workflows/build-linux-arm64-termux.yml:54`（排除项）
- Modify: `android/app/build.gradle.kts:50`（排除项）

**Interfaces:**
- Consumes: 无（纯文本替换）
- Produces: 所有脚本/配置中的 `drissionpage` → `playwright`

- [ ] **Step 1: 批量替换排除项**

对以下 4 个文件执行替换：`drissionpage` → `playwright`（仅排除项，不涉及代码）

```bash
sed -i 's/drissionpage/playwright/g' \
  scripts/build-portable.sh \
  scripts/termux-preinstall.sh \
  .github/workflows/build-linux-arm64-termux.yml
# android/build.gradle.kts 手动替换（见下）
```

`android/app/build.gradle.kts:50`：`exclude("drissionpage")` → `exclude("playwright")`

- [ ] **Step 2: 更新 Chrome 说明**

`scripts/build-portable.ps1:174,179` 两处说明改为：

```powershell
  1. 如需使用 browser 模式（Playwright），运行 `playwright install chromium` 下载浏览器
  Playwright 首次调用前需下载匹配的 chromium（playwright install chromium）。
```

`scripts/build-portable.sh:248` 说明改为：

```
  - browser 模式（Playwright）需 `playwright install chromium`；Termux 版不含 browser 模式
```

- [ ] **Step 3: 验证无残留 + 语法**

```bash
cd "D:/Linux/novel-downloader/novel-downloader" && \
  grep -rn "drissionpage\|DrissionPage" --include="*.sh" --include="*.ps1" --include="*.yml" --include="*.kts" --include="*.toml" --include="*.txt" --include="*.py" . | grep -v __pycache__ | grep -v ".git/" || echo "零 drissionpage 残留" && \
  bash -n scripts/build-portable.sh scripts/termux-preinstall.sh && echo "sh 语法 OK"
```

Expected: 零 `drissionpage`/`DrissionPage` 残留 + sh 语法 OK

- [ ] **Step 4: Commit**

```bash
git add scripts/build-portable.ps1 scripts/build-portable.sh scripts/termux-preinstall.sh .github/workflows/build-linux-arm64-termux.yml android/app/build.gradle.kts
git commit -m "构建: 排除项 drissionpage 换 playwright + Chrome 说明改 playwright install chromium"
```

---

### Task 4: 全量回归 + 一致性校验

**Files:**
- 无代码改动（验证性任务）

**Interfaces:**
- Consumes: Task 1-3 全部产物

- [ ] **Step 1: 全量测试**

Run: `python -m pytest tests/ -q 2>&1 | tail -3`
Expected: 全绿（约 198 passed, 2 skipped）

- [ ] **Step 2: 三入口 import 验证**

Run: `python -c "from novelbase import *; print('novelbase OK')" && python -c "from backend.main import app; print('backend OK')" && python -c "import cli.main; print('cli OK')"`
Expected: 三入口 OK

- [ ] **Step 3: 全局残留确认**

Run: `grep -rn "DrissionPage\|drissionpage\|asyncio.to_thread" novelbase/ backend/ cli/ --include="*.py" | grep -v __pycache__ || echo "零残留"`
Expected: 零 DrissionPage/to_thread 残留（browser 相关）

- [ ] **Step 4: 文档一致性（不 commit）**

`AGENTS.md:36` 已写 `browser（Playwright）`，与代码一致，无需改。设计文档 `docs/superpowers/specs/2026-08-16-playwright-replace-drissionpage-design.md` 已存在（docs 不提交 git）。

确认：`git status --short` 仅含 Task 1-3 的已提交文件（工作区干净）。

- [ ] **Step 5: 提交收尾（如有遗漏）**

若 Step 3 发现遗漏文件，单独 commit：

```bash
git add <遗漏文件>
git commit -m "补: <描述>"
```

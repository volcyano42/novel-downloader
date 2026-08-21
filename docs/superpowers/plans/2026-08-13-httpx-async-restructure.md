# engine httpx 迁移 + 目录结构重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 novelbase 的 HTTP 层从 requests 迁移到 httpx（同步+异步双接口），并完成目录结构重构（shared 共享层 + backend/cli/frontend 上提 + storage 分层 + 默认值单一数据源）。

**Architecture:** 两个独立阶段。Phase A 只动 `novelbase/`（核心库内部：engine 换 httpx + 新增 async 方法 + 书源 requests→httpx），137 个现有测试作为回归基线。Phase B 只动外层（`services/backend`→`backend/`、`cli_lib`→`cli/`、新增 `shared/`、`scripts/`、storage 分层），novelbase 零改动。

**Tech Stack:** Python 3.10+、httpx 0.28、FastAPI、SQLite、pytest。

## Global Constraints

- Python `requires-python = ">=3.10"`（`pyproject.toml`）
- httpx 版本已装 0.28.1；httpx 从 dev 依赖提升为主依赖，删除 `Requests` 和 `urllib3`
- `app_data/` 和 `docs/` 均 gitignore，不提交
- 提交消息中文，一个方面一条 commit，禁止 `git add -A`
- 现有 137 tests 必须保持全绿（2 skipped 允许）
- novelbase 是纯核心库：零依赖应用层（不 import backend/cli/shared）

---

## Phase A：engine httpx 迁移 + 异步化（只动 novelbase/）

### Task A1: 依赖调整

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: 无
- Produces: `httpx` 成为主依赖；`requests`/`urllib3` 从主依赖移除

- [ ] **Step 1: 修改 pyproject.toml 依赖**

`dependencies` 中：删除 `"Requests",` 和 `"urllib3",`，新增 `"httpx",`。

```toml
dependencies = [
    "beautifulsoup4",
    "drissionpage",
    "fastapi",
    "httpx",
    "Pillow",
    "pillow-heif",
    "python-box",
    "PyYAML",
    "rich",
    "uvicorn",
    "yarl",
]
```

- [ ] **Step 2: 验证 httpx 可导入**

Run: `python -c "import httpx; print(httpx.__version__)"`
Expected: 输出 `0.28.1`（或更高版本号），无 ImportError

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "依赖: httpx 提升为主依赖，移除 requests/urllib3"
```

### Task A2: 新增编码探测工具

**Files:**
- Create: `novelbase/utils/encoding.py`
- Test: `tests/test_encoding.py`

**Interfaces:**
- Consumes: `charset_normalizer`（httpx 的传递依赖，已随 httpx 安装）
- Produces: `detect_encoding(content: bytes) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_encoding.py
from novelbase.utils.encoding import detect_encoding


def test_detect_encoding_utf8():
    content = "中文内容测试".encode("utf-8")
    assert detect_encoding(content) in ("utf-8", "utf_8", "utf8")


def test_detect_encoding_gbk():
    content = "中文内容".encode("gbk")
    result = detect_encoding(content)
    # gbk 或 gb18030 都算正确识别
    assert result.lower().replace("_", "").replace("-", "") in ("gbk", "gb18030", "cp936")


def test_detect_encoding_empty_returns_utf8():
    assert detect_encoding(b"") == "utf-8"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_encoding.py -v`
Expected: FAIL，`ModuleNotFoundError: novelbase.utils.encoding`

- [ ] **Step 3: 实现**

```python
# novelbase/utils/encoding.py
"""字节流编码探测 — 替代 requests 的 apparent_encoding（httpx 无此属性）。"""
from __future__ import annotations


def detect_encoding(content: bytes) -> str:
    """探测 bytes 的文本编码，优先 charset_normalizer，回退 utf-8。

    Args:
        content: 原始字节内容。

    Returns:
        探测出的编码名（如 "utf-8"、"gb18030"），无法探测时返回 "utf-8"。
    """
    if not content:
        return "utf-8"
    try:
        import charset_normalizer

        best = charset_normalizer.from_bytes(content).best()
        if best is not None and best.encoding:
            return best.encoding
    except ImportError:
        pass
    return "utf-8"
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_encoding.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add novelbase/utils/encoding.py tests/test_encoding.py
git commit -m "feat: 新增编码探测工具 detect_encoding（替代 apparent_encoding）"
```

### Task A3: RequestsEngine 换 httpx + 异步方法

**Files:**
- Modify: `novelbase/core/engine.py`（RequestsEngine 类，约 311-393 行）
- Test: `tests/test_engine_httpx.py`

**Interfaces:**
- Consumes: `novelbase.utils.encoding.detect_encoding`
- Produces:
  - `RequestsEngine.fetch_text(url, skip_delay=False, encoding=None, **kwargs) -> str`（同步，签名不变）
  - `RequestsEngine.fetch_json(url, skip_delay=False, **kwargs) -> dict`（同步，签名不变）
  - `RequestsEngine.async_fetch_text(url, skip_delay=False, encoding=None, **kwargs) -> str`（异步）
  - `RequestsEngine.async_fetch_json(url, skip_delay=False, **kwargs) -> dict`（异步）
  - `RequestsEngine.close()` 关闭 `_client` 和 `_async_client`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_engine_httpx.py
import asyncio
import httpx

from novelbase import create_engine, Options


def _requests_engine():
    opts = Options().set_mode("requests").set_requests_options(
        headers={"User-Agent": "test"},
        timeout=5,
        retry_times=1,
        delay=(0, 0),
    )
    return create_engine(opts)


def test_requests_engine_uses_httpx_client():
    engine = _requests_engine()
    assert isinstance(engine._client, httpx.Client)
    engine.close()


def test_requests_engine_fetch_text(monkeypatch):
    engine = _requests_engine()

    class FakeResp:
        content = "测试内容".encode("utf-8")
        encoding = "utf-8"

    def fake_get(url):
        return FakeResp()

    monkeypatch.setattr(engine._client, "get", fake_get)
    assert engine.fetch_text("http://x") == "测试内容"
    engine.close()


def test_requests_engine_has_async_methods():
    engine = _requests_engine()
    assert asyncio.iscoroutinefunction(engine.async_fetch_text)
    assert asyncio.iscoroutinefunction(engine.async_fetch_json)
    engine.close()


def test_requests_engine_async_fetch_text(monkeypatch):
    engine = _requests_engine()

    async def fake_get(url):
        class R:
            content = "异步内容".encode("utf-8")
            encoding = "utf-8"
        return R()

    monkeypatch.setattr(engine._get_async_client(), "get", fake_get)
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "异步内容"
    engine.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_engine_httpx.py -v`
Expected: FAIL（`engine` 对象无 `_client` 属性 / 无 `async_fetch_text` 方法）

- [ ] **Step 3: 实现 RequestsEngine 重写**

将 `RequestsEngine` 类的实现替换为 httpx 版本（同步 `fetch_text`/`fetch_json` 用 `httpx.Client`，新增 `async_fetch_text`/`async_fetch_json` 用 `httpx.AsyncClient`，删除 `threading.local` 线程池）：

```python
class RequestsEngine(Engine):

    def __init__(self, options: RequestsOptions) -> None:
        super().__init__()
        self.name = "requests"
        self.options = options
        self._client = httpx.Client(
            headers=options.headers,
            cookies=options.cookies,
            proxies=options.proxies or None,
            follow_redirects=True,
            timeout=options.timeout,
            transport=httpx.HTTPTransport(retries=options.retry_times),
        )
        self._async_client = None

    def update_options(self, options: RequestsOptions) -> None:
        for attr in ("delay", "timeout", "retry_times", "backoff_factor", "headers", "cookies", "proxies"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                headers=self.options.headers,
                cookies=self.options.cookies,
                proxies=self.options.proxies or None,
                follow_redirects=True,
                timeout=self.options.timeout,
                transport=httpx.AsyncHTTPTransport(retries=self.options.retry_times),
            )
        return self._async_client

    def fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        _log.debug("Requests fetch_text: url=%s", mask_key(url[:120]))
        try:
            response = self._client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

        enc = encoding or detect_encoding(response.content)
        text = response.content.decode(enc, errors="replace")
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        _log.debug("Requests fetch_text ok: len=%s", len(text))
        return text

    def fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        try:
            response = self._client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response.json()

    async def async_fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        client = self._get_async_client()
        response = await client.get(url)
        enc = encoding or detect_encoding(response.content)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.content.decode(enc, errors="replace")

    async def async_fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        client = self._get_async_client()
        response = await client.get(url)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.json()

    def close(self) -> None:
        super().close()
        try:
            self._client.close()
        except Exception:
            pass
        if self._async_client is not None:
            try:
                # AsyncClient.close() 是异步方法，需在事件循环里关；这里尽力关闭
                import asyncio as _aio
                try:
                    _aio.get_running_loop()
                except RuntimeError:
                    _aio.run(self._async_client.aclose())
            except Exception:
                pass
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_engine_httpx.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 运行全量回归**

Run: `python -m pytest tests/ -q`
Expected: 137+ passed（新增测试后总数增加），无 FAIL

- [ ] **Step 6: Commit**

```bash
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "重构: RequestsEngine 换 httpx.Client，新增 async_fetch_text/json"
```

### Task A4: APIEngine 换 httpx + 异步方法

**Files:**
- Modify: `novelbase/core/engine.py`（APIEngine 类，约 58-165 行）
- Test: `tests/test_engine_httpx.py`（追加）

**Interfaces:**
- Consumes: `detect_encoding`
- Produces: `APIEngine.async_fetch_text` / `APIEngine.async_fetch_json`，保留 `post_data`/`params` 分支

- [ ] **Step 1: 追加失败测试**

```python
# tests/test_engine_httpx.py 追加
def _api_engine():
    opts = Options().set_mode("api").set_api_options(
        name="test", key="k", timeout=5, retry_times=1, delay=(0, 0),
        params={"token": "abc"},
    )
    return create_engine(opts)


def test_api_engine_has_async_methods():
    engine = _api_engine()
    assert asyncio.iscoroutinefunction(engine.async_fetch_text)
    assert asyncio.iscoroutinefunction(engine.async_fetch_json)
    engine.close()


def test_api_engine_async_fetch_json_post(monkeypatch):
    engine = _api_engine()

    async def fake_post(url, data=None):
        class R:
            def json(self):
                return {"ok": True, "data": data}
        return R()

    monkeypatch.setattr(engine._get_async_client(), "post", fake_post)
    result = asyncio.run(engine.async_fetch_json("http://x", skip_delay=True, post_data={"id": "1"}))
    assert result["ok"] is True
    assert result["data"]["token"] == "abc"  # params 合并进 post_data
    engine.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_engine_httpx.py::test_api_engine_has_async_methods -v`
Expected: FAIL（无 `async_fetch_text`）

- [ ] **Step 3: 实现 APIEngine 重写**

APIEngine 结构与 RequestsEngine 相同，但保留 `params` 合并和 `post_data` 分支：

```python
class APIEngine(Engine):

    def __init__(self, options: APIOptions) -> None:
        super().__init__()
        self.name = "API"
        self.options = options
        self._client = httpx.Client(
            timeout=options.timeout,
            follow_redirects=True,
            transport=httpx.HTTPTransport(retries=options.retry_times),
        )
        self._async_client = None

    def update_options(self, options: APIOptions) -> None:
        for attr in ("delay", "timeout", "retry_times", "backoff_factor", "key", "params"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.options.timeout,
                follow_redirects=True,
                transport=httpx.AsyncHTTPTransport(retries=self.options.retry_times),
            )
        return self._async_client

    def _merge_post_data(self, post_data: dict[str, Any]) -> dict[str, Any]:
        if self.options.params:
            merged = dict(self.options.params)
            merged.update(post_data)
            return merged
        return post_data

    def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        _log.debug("API fetch_text: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = self._client.post(url, data=self._merge_post_data(post_data))
            else:
                response = self._client.get(url, params=self.options.params or None)
        except httpx.HTTPError as e:
            raise NetworkError(f"API request failed: {e}", url=url) from e
        enc = encoding or detect_encoding(response.content)
        text = response.content.decode(enc, errors="replace")
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        _log.debug("API fetch_text ok: len=%s", len(text))
        return text

    def fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        post_data = kwargs.pop('post_data', None)
        _log.debug("API fetch_json: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = self._client.post(url, data=self._merge_post_data(post_data))
            else:
                response = self._client.get(url, params=self.options.params or None)
        except httpx.HTTPError as e:
            raise NetworkError(f"API request failed: {e}", url=url) from e
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response.json()

    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        client = self._get_async_client()
        if post_data is not None:
            response = await client.post(url, data=self._merge_post_data(post_data))
        else:
            response = await client.get(url, params=self.options.params or None)
        enc = encoding or detect_encoding(response.content)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.content.decode(enc, errors="replace")

    async def async_fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        post_data = kwargs.pop('post_data', None)
        client = self._get_async_client()
        if post_data is not None:
            response = await client.post(url, data=self._merge_post_data(post_data))
        else:
            response = await client.get(url, params=self.options.params or None)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.json()

    def close(self) -> None:
        super().close()
        try:
            self._client.close()
        except Exception:
            pass
        if self._async_client is not None:
            try:
                import asyncio as _aio
                try:
                    _aio.get_running_loop()
                except RuntimeError:
                    _aio.run(self._async_client.aclose())
            except Exception:
                pass
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_engine_httpx.py -v`
Expected: PASS（全部通过）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 无 FAIL

- [ ] **Step 6: Commit**

```bash
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "重构: APIEngine 换 httpx.Client，新增 async_fetch_text/json"
```

### Task A5: BrowserEngine 加异步方法（asyncio.to_thread 包装）

**Files:**
- Modify: `novelbase/core/engine.py`（BrowserEngine 类，约 167-309 行）
- Test: `tests/test_engine_httpx.py`（追加）

**Interfaces:**
- Produces: `BrowserEngine.async_fetch_text` / `BrowserEngine.async_fetch_json`（委托给同步方法，经 `asyncio.to_thread`）

- [ ] **Step 1: 追加失败测试**

```python
# tests/test_engine_httpx.py 追加
def _browser_engine(monkeypatch):
    # 避免真实启动 Chromium：monkeypatch _init_browser
    import novelbase.core.engine as eng
    monkeypatch.setattr(eng.BrowserEngine, "_init_browser", lambda self: None)
    from novelbase.core.options import BrowserOptions
    return eng.BrowserEngine(BrowserOptions(delay=(0, 0), headless=True))


def test_browser_engine_has_async_methods(monkeypatch):
    engine = _browser_engine(monkeypatch)
    assert asyncio.iscoroutinefunction(engine.async_fetch_text)
    assert asyncio.iscoroutinefunction(engine.async_fetch_json)


def test_browser_engine_async_delegates_to_sync(monkeypatch):
    engine = _browser_engine(monkeypatch)
    calls = []

    def fake_fetch_text(url, skip_delay=False, encoding=None, **kwargs):
        calls.append(url)
        return "<html>ok</html>"

    monkeypatch.setattr(engine, "fetch_text", fake_fetch_text)
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    assert calls == ["http://x"]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_engine_httpx.py::test_browser_engine_has_async_methods -v`
Expected: FAIL

- [ ] **Step 3: 实现 BrowserEngine 异步方法**

在 `BrowserEngine` 类的 `fetch_json` 方法之后、`close` 之前插入：

```python
    async def async_fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        return await asyncio.to_thread(
            self.fetch_text, url=url, skip_delay=skip_delay, encoding=encoding, **kwargs
        )

    async def async_fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.fetch_json, url=url, skip_delay=skip_delay, **kwargs
        )
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_engine_httpx.py -v`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 无 FAIL

- [ ] **Step 6: Commit**

```bash
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "feat: BrowserEngine 新增 async_fetch_text/json（asyncio.to_thread 包装）"
```

### Task A6: Engine 基类加抽象 async 方法

**Files:**
- Modify: `novelbase/core/engine.py`（Engine 基类，约 21-56 行）
- Test: `tests/test_engine_httpx.py`（追加）

**Interfaces:**
- Produces: `Engine.async_fetch_text` / `Engine.async_fetch_json` 抽象方法（三个子类已实现）

- [ ] **Step 1: 追加失败测试**

```python
# tests/test_engine_httpx.py 追加
def test_engine_base_has_abstract_async_methods():
    from novelbase.core.engine import Engine
    assert "async_fetch_text" in Engine.__abstractmethods__
    assert "async_fetch_json" in Engine.__abstractmethods__
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_engine_httpx.py::test_engine_base_has_abstract_async_methods -v`
Expected: FAIL（抽象方法集合中无 async_fetch_text）

- [ ] **Step 3: 在 Engine 基类加抽象方法**

在 `Engine` 基类的 `fetch_json` 抽象方法后插入：

```python
    @abstractmethod
    async def async_fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        """异步版 fetch_text（GET/POST 返回纯文本）。"""
        ...

    @abstractmethod
    async def async_fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict:
        """异步版 fetch_json（GET/POST 返回解析后的 JSON）。"""
        ...
```

同时确认 `engine.py` 顶部 import 有 `import asyncio` 和 `import httpx`（替换原 `import requests`）。

- [ ] **Step 4: 运行确认通过 + 全量回归**

Run: `pytest tests/test_engine_httpx.py -v && python -m pytest tests/ -q`
Expected: 全部 PASS，无 FAIL

- [ ] **Step 5: Commit**

```bash
git add novelbase/core/engine.py tests/test_engine_httpx.py
git commit -m "feat: Engine 基类新增 async_fetch_text/json 抽象方法"
```

### Task A7: 书源文件 requests → httpx（12 个文件）

**Files:**
- Modify: 以下 12 个文件（把 `import requests` 换成 `import httpx`，`requests.get/post` → `httpx.get/post` 加 `follow_redirects=True`，`requests.RequestException` → `httpx.HTTPError`）：
  - `novelbase/sources/92xs/requests/search.py`
  - `novelbase/sources/fanqie/api/oiapi/novel_info.py`
  - `novelbase/sources/fanqie/api/rain/novel_info.py`
  - `novelbase/sources/fanqie/browser/search.py`
  - `novelbase/sources/fanqie/requests/search.py`
  - `novelbase/sources/fanqie/_common.py`
  - `novelbase/sources/qidian/_common.py`
  - `novelbase/sources/qimao/api/rain/novel_info.py`
  - `novelbase/sources/qimao/_common.py`

**Interfaces:**
- Consumes: 无（纯机械替换，函数签名不变）
- Produces: 书源函数签名不变，仍返回 SearchResult/Novel/Chapter

- [ ] **Step 1: 逐文件替换**

对每个文件执行同样的机械替换（以 `fanqie/requests/search.py` 为例）：

```python
# 改前
import requests
data = requests.get(search_url).json()

# 改后
import httpx
data = httpx.get(search_url, follow_redirects=True).json()
```

对 `_common.py` 中的 `requests.get(url, allow_redirects=True, timeout=10)` → `httpx.get(url, follow_redirects=True, timeout=10)`。

对 `requests.post(...)` → `httpx.post(..., follow_redirects=True)`。

对 `except requests.RequestException` → `except httpx.HTTPError`。

- [ ] **Step 2: 扫描残留 requests 引用**

Run: `grep -rn "import requests\|requests\.\|RequestException" --include="*.py" novelbase/ | grep -v __pycache__`
Expected: 无输出（novelbase 内无 requests 残留）

- [ ] **Step 3: 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 137+ passed，无 FAIL

- [ ] **Step 4: 冒烟测试（可选，需网络）**

Run: `python -c "from novelbase import search; from novelbase.core.engine import create_engine; from novelbase.core.options import Options; e = create_engine(Options().set_mode('requests')); r = search('fanqie', '修仙', e, skip_delay=True); print(len(r))"`
Expected: 打印结果数量（>0 为佳），无异常

- [ ] **Step 5: Commit**

```bash
git add novelbase/sources/
git commit -m "重构: 书源文件 requests 全量替换为 httpx"
```

### Task A8: 全量验证 Phase A

- [ ] **Step 1: 最终回归**

Run: `python -m pytest tests/ -q && python -c "from novelbase import *; print('OK')"`
Expected: 全部 PASS + OK

- [ ] **Step 2: 确认无 requests 残留**

Run: `grep -rn "requests" --include="*.py" novelbase/ | grep -v __pycache__ | grep -v "async_fetch\|requests mode\|mode.*requests"`
Expected: 仅剩字符串字面量（如 `"requests"` 作为 mode 名），无 `import requests`

---

## Phase B：目录结构重构（novelbase 零改动）

### Task B1: 新增 shared/ 包（config.py + user_data.py）

**Files:**
- Create: `shared/__init__.py`
- Create: `shared/user_data.py`（从 `cli_lib/user_db.py` 迁移，改 DB 路径）
- Create: `shared/config.py`（合并 `cli_lib/config.py` + `services/backend/services/config_service.py`）
- Test: `tests/test_shared_user_data.py`

**Interfaces:**
- Consumes: `novelbase.core.options`（默认值派生）
- Produces:
  - `shared.user_data.load_groups() / save_groups() / get_novel_group() / add_novel_to_group() / ensure_novel_in_group()`
  - `shared.user_data.load_favorites() / add_favorite() / remove_favorite() / is_favorite()`
  - `shared.user_data.add_search_history() / get_search_history() / clear_search_history()`
  - `shared.user_data.add_bookmark() / remove_bookmark() / get_bookmarks()`
  - `shared.config.load_main_config() / save_main_config() / load_site_config() / save_site_config() / load_format_configs() / save_fmt_config() / build_options() / get_database_url()`

- [ ] **Step 1: 创建 shared/user_data.py**

从 `cli_lib/user_db.py` 复制全部代码，仅改两处路径：

```python
# shared/user_data.py 顶部
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "app_data" / "storage" / "users" / "default" / "user_data.db"
GROUPS_YAML = ROOT / "app_data" / "config" / "groups.yaml"
```

其余函数体原样保留（`_connection`、`_ensure_schema`、groups/favorites/search_history/bookmarks 全部函数）。

- [ ] **Step 2: 写 user_data 迁移测试**

```python
# tests/test_shared_user_data.py
import sqlite3
from pathlib import Path

from shared import user_data


def test_user_data_db_path_under_users_default(tmp_path, monkeypatch):
    # 用 monkeypatch 覆盖模块级 DB_PATH
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.add_favorite("fanqie_123")
    assert user_data.load_favorites() == ["fanqie_123"]
    user_data.remove_favorite("fanqie_123")
    assert user_data.load_favorites() == []


def test_groups_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    assert user_data.add_novel_to_group("fanqie_1", "default")
    assert user_data.get_novel_group("fanqie_1") == "default"
    assert user_data.load_groups() == {"default": {"fanqie_1": {"pending_export": False}}}
```

- [ ] **Step 3: 运行确认通过**

Run: `pytest tests/test_shared_user_data.py -v`
Expected: PASS

- [ ] **Step 4: 创建 shared/config.py（合并两个 config）**

内容 = 合并 `cli_lib/config.py` 与 `services/backend/services/config_service.py`，默认值用 `_dataclass_defaults` 从 novelbase options 派生：

```python
# shared/config.py
"""配置加载 — 单一数据源：默认值从 novelbase.core.options 派生。"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Any

import yaml

from novelbase.core.options import BrowserOptions, RequestsOptions

# ── 路径 ──
def _get_app_data_dir() -> Path:
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        app_data = exe_dir / "app_data"
        if not app_data.exists():
            meipass = Path(sys._MEIPASS)
            src = meipass / "app_data"
            if src.exists():
                try:
                    _copy_dir(src, app_data)
                except (OSError, PermissionError):
                    app_data.mkdir(parents=True, exist_ok=True)
            else:
                app_data.mkdir(parents=True, exist_ok=True)
        return app_data
    return Path(__file__).resolve().parent.parent / "app_data"

def _copy_dir(src: Path, dst: Path, _max_depth: int = 10) -> None:
    if _max_depth < 0:
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_dir(item, target, _max_depth - 1)
        elif not target.exists():
            shutil.copy2(item, target)

APP_DATA = _get_app_data_dir()
CONFIG_DIR = APP_DATA / "config"

# ── 默认值单一数据源：从 dataclass 字段默认值派生 ──
def _dataclass_defaults(cls) -> dict:
    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:
            result[f.name] = f.default_factory()
    return result

ENGINE_DEFAULTS = {
    "browser": _dataclass_defaults(BrowserOptions),
    "requests": _dataclass_defaults(RequestsOptions),
    "api": {},
}

GLOBAL_DEFAULTS = {
    "name": "Novel下载器",
    "mode": "browser",
    "max_workers": 3,
    "log_level": "DEBUG",
    "notify": {"on_complete": True, "on_incomplete": True, "sound": "bell"},
}

FMT_DEFAULTS = {
    "txt": {"enabled": True, "encoding": "utf-8"},
    "epub": {"enabled": True, "compression": "deflate", "compresslevel": 9,
             "optimize_images": True, "jpeg_quality": 85, "max_image_width": 0, "include_toc": True},
    "img": {"enabled": True, "output_format": "original"},
}

# ── 工具 ──
def deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_yaml(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)

def _resolve_paths(value):
    app_data_str = str(APP_DATA)
    if isinstance(value, str):
        if value.startswith("app_data/") or value.startswith("app_data\\"):
            return value.replace("app_data", app_data_str, 1)
        return value
    if isinstance(value, list):
        return [_resolve_paths(v) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_paths(v) for k, v in value.items()}
    return value

# ── config.yaml ──
def load_main_config():
    path = CONFIG_DIR / "config.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def save_main_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "config.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

# ── sites ──
def load_site_config(platform):
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def save_site_config(platform, site_cfg):
    (CONFIG_DIR / "sites").mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "sites" / f"{platform}.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(site_cfg, f, allow_unicode=True, default_flow_style=False)

def load_platform_configs():
    result = {}
    sites_dir = CONFIG_DIR / "sites"
    if not sites_dir.is_dir():
        return result
    for p in sites_dir.glob("*.yaml"):
        platform = p.stem
        raw = load_yaml(p)
        entry = {}
        for mode in ("browser", "requests"):
            entry[mode] = deep_merge(ENGINE_DEFAULTS[mode], raw.get(mode, {}))
        api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
        entry["api"] = {k: v for k, v in api_section.items() if isinstance(v, dict)}
        entry["api_variants"] = list(entry["api"].keys())
        result[platform] = entry
    return result

def load_platform_raw(platform):
    return load_yaml(CONFIG_DIR / "sites" / f"{platform}.yaml")

def find_variant_options(variant):
    sites_dir = CONFIG_DIR / "sites"
    if not sites_dir.is_dir():
        return None
    for p in sites_dir.glob("*.yaml"):
        site = load_yaml(p)
        api = site.get("api", {})
        if isinstance(api, dict) and variant in api:
            if isinstance(api[variant], dict):
                return api[variant]
    return None

# ── formats ──
def load_format_configs():
    result = {}
    for fmt_key, defaults in FMT_DEFAULTS.items():
        raw = load_yaml(CONFIG_DIR / "formats" / f"{fmt_key}.yaml")
        fmt_data = raw.get(fmt_key, {}) if isinstance(raw, dict) else {}
        result[fmt_key] = deep_merge(defaults, fmt_data)
    return result

def save_format_config(fmt_key, data):
    save_yaml(CONFIG_DIR / "formats" / f"{fmt_key}.yaml", {fmt_key: data})

def save_fmt_config(fmt_name, data):
    (CONFIG_DIR / "formats").mkdir(parents=True, exist_ok=True)
    save_yaml(CONFIG_DIR / "formats" / f"{fmt_name}.yaml", data)

def load_fmt_config(fmt_name):
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

# ── 数据库 URL ──
def get_database_url():
    return f"sqlite:///{APP_DATA / 'storage' / 'novels' / 'catalog.db'}"

# ── build_options（从 cli_lib/config.py 迁移，改为 import shared.user_data）──
def build_options(cfg, site_cfg):
    from novelbase.core.options import Options
    options = Options()
    mode = cfg.get("mode") or site_cfg.get("mode", "browser")
    options.set_mode(mode)

    if mode == "browser":
        browser_cfg = site_cfg.get("browser", {})
        user_data_dir = browser_cfg.get("user_data_dir", "")
        if user_data_dir:
            ud_path = Path(user_data_dir)
            if not ud_path.is_absolute():
                ud_path = Path(__file__).parent.parent / ud_path
        else:
            ud_path = None
        options.set_browser_options(
            headless=browser_cfg.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=browser_cfg.get("timeout", 30),
            retry_times=browser_cfg.get("retry_times", 3),
            backoff_factor=browser_cfg.get("backoff_factor", 2),
            delay=tuple(browser_cfg.get("delay", [3, 5])),
            viewport=browser_cfg.get("viewport"),
        )
    elif mode == "api":
        api_section = site_cfg.get("api", {})
        for name, provider in api_section.items():
            if isinstance(provider, dict) and provider.get("enabled", True):
                env_key_name = f"{name.upper()}_API_KEY"
                api_key = os.environ.get(env_key_name) or provider.get("key", "")
                options.set_api_options(
                    name=name, key=api_key,
                    timeout=provider.get("timeout", 30),
                    retry_times=provider.get("retry_times", 3),
                    backoff_factor=provider.get("backoff_factor", 2),
                    delay=tuple(provider.get("delay", [3, 5])),
                    params=provider.get("params", {}),
                )
                break
    elif mode == "requests":
        req_cfg = site_cfg.get("requests", {})
        cookies_val = req_cfg.get("cookies")
        if isinstance(cookies_val, str) and cookies_val:
            cookies_dict = {}
            for item in cookies_val.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies_dict[k.strip()] = v.strip()
            cookies_val = cookies_dict
        elif not isinstance(cookies_val, dict):
            cookies_val = None
        options.set_requests_options(
            headers=req_cfg.get("headers"),
            cookies=cookies_val,
            proxies=req_cfg.get("proxies"),
            timeout=req_cfg.get("timeout", 30),
            retry_times=req_cfg.get("retry_times", 3),
            backoff_factor=req_cfg.get("backoff_factor", 2),
            delay=tuple(req_cfg.get("delay", [3, 5])),
        )

    storage_cfg = cfg.get("storage", {})
    database_url = storage_cfg.get("database_url", "") or "sqlite:///app_data/storage/novels/catalog.db"
    options.set_storage_options(backend="sqlite", database_url=database_url)
    return options
```

> 注：`build_options` 的 `api` 分支原逻辑里 `params=provider.get("params", {})`，若原代码为 `params=provider.get("params")`（None 默认），保持原样即可，此处按语义等价补齐，实施时以 `cli_lib/config.py` 原文为准。

- [ ] **Step 5: 创建 shared/__init__.py**

```python
# shared/__init__.py
"""共享应用层 — cli 和 backend 都依赖的配置与用户数据。"""
```

- [ ] **Step 6: Commit**

```bash
git add shared/ tests/test_shared_user_data.py
git commit -m "feat: 新增 shared 共享层（config 单一数据源 + user_data 归位）"
```

### Task B2: services/backend → backend/（import 改写）

**Files:**
- Move: `services/backend/` → `backend/`（git mv）
- Modify: `backend/main.py`、`backend/routers/*.py`、`backend/services/*.py` 所有 `services.backend.*` → `backend.*`、`services/` 路径引用
- Modify: `backend/routers/config.py`（`cli_lib.user_db` → `shared.user_data`，`config_service` → `shared.config`）

**Interfaces:**
- Consumes: `shared.config`、`shared.user_data`（Task B1）
- Produces: `backend.main:app`（FastAPI 应用，供 uvicorn/build 脚本引用）

- [ ] **Step 1: 移动目录**

```bash
git mv services/backend backend
rm services/__init__.py
rmdir services 2>/dev/null || true
```

- [ ] **Step 2: 批量改写 import**

`backend/` 下所有 `.py` 文件：`services.backend.` → `backend.`，`services/backend/` → `backend/`。

- [ ] **Step 3: 改写 config.py 跨层调用**

`backend/routers/config.py` 中：
- `from cli_lib.user_db import load_groups` → `from shared.user_data import load_groups`（共 5 处：load_groups/save_groups/load_favorites/add_favorite/remove_favorite）
- `from services.backend.services import config_service` → `from shared import config as config_service`（或改为 `import shared.config as config_service`）

- [ ] **Step 4: 验证导入**

Run: `python -c "from backend.main import app; print('OK')"`
Expected: OK（若因前端 dist 路径报错，先确认不影响 app 对象创建）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 无 FAIL

- [ ] **Step 6: Commit**

```bash
git add backend/ services/
git commit -m "重构: services/backend 上提为 backend/，跨层调用改走 shared"
```

### Task B3: services/frontend → frontend/

**Files:**
- Move: `services/frontend/` → `frontend/`（git mv）
- Modify: `backend/main.py`（`_find_frontend_dist` 路径）、`app.py`（npm 启动路径）

**Interfaces:**
- Consumes: 无
- Produces: `frontend/` 目录（vite 项目根）

- [ ] **Step 1: 移动目录**

```bash
git mv services/frontend frontend
```

- [ ] **Step 2: 改 backend/main.py 的 dist 定位**

`_find_frontend_dist()` 中所有 `"services" / "frontend" / "dist"` → `"frontend" / "dist"`。

- [ ] **Step 3: 改 app.py 的 npm 路径**

`app.py` 中 `ROOT / "services" / "frontend"` → `ROOT / "frontend"`。

- [ ] **Step 4: 验证前端构建**

Run: `cd frontend && npx tsc --noEmit --project tsconfig.app.json`
Expected: 无类型错误（若报错与本重构无关，记录但不阻塞）

- [ ] **Step 5: Commit**

```bash
git add frontend/ backend/main.py app.py
git commit -m "重构: services/frontend 上提为 frontend/"
```

### Task B4: cli.py + cli_lib → cli/

**Files:**
- Create: `cli/__init__.py`、`cli/main.py`（原 cli.py）、`cli/config.py`（原 cli_lib/config.py，删 groups 函数改走 shared）、`cli/core.py`（原 cli_lib/core.py）
- Delete: `cli.py`、`cli_lib/`

**Interfaces:**
- Consumes: `shared.config`、`shared.user_data`、`novelbase`
- Produces: `cli.main:main()`（CLI 入口）

- [ ] **Step 1: 创建 cli/ 包结构**

```bash
mkdir cli
git mv cli.py cli/main.py
git mv cli_lib/config.py cli/config.py
git mv cli_lib/core.py cli/core.py
git mv cli_lib/__init__.py cli/__init__.py
rm -rf cli_lib
```

- [ ] **Step 2: 改 cli/ 内部 import**

- `cli/config.py`：`from cli_lib.user_db import ...` → `from shared.user_data import ...`
- `cli/core.py`：`from cli_lib.config import ...` → `from cli.config import ...`
- `cli/main.py`：`from cli_lib.config import ...` → `from cli.config import ...`

- [ ] **Step 3: 验证 CLI 可导入**

Run: `python -m cli --help` 或 `python -c "import cli.main"`
Expected: 无 ImportError

- [ ] **Step 4: Commit**

```bash
git add cli/ && git rm cli.py cli_lib/ -r
git commit -m "重构: cli.py + cli_lib 合并为 cli/ 包，分组功能改走 shared"
```

### Task B5: scripts/ 收纳构建脚本

**Files:**
- Move: `build-nuitka.ps1`、`build-portable.ps1`、`build-portable.sh`、`build-pypi.ps1`、`build-pypi.sh` → `scripts/`
- Create: `scripts/migrate_storage.py`（storage 分层迁移）
- Modify: 构建脚本内的路径引用（`services.backend` → `backend`，`services/frontend` → `frontend`）

**Interfaces:**
- Consumes: `backend.main:app`、`frontend/`
- Produces: `scripts/` 目录（构建+迁移脚本）

- [ ] **Step 1: 移动脚本**

```bash
mkdir scripts
git mv build-nuitka.ps1 build-portable.ps1 build-portable.sh build-pypi.ps1 build-pypi.sh scripts/
```

- [ ] **Step 2: 改脚本路径引用**

`scripts/build-nuitka.ps1`：`--include-package=services.backend` → `--include-package=backend`，`services/frontend/dist` → `frontend/dist`，`services/backend/main.py` → `backend/main.py`。

`scripts/build-portable.sh`：`services/frontend` → `frontend`，`services.backend.main:app` → `backend.main:app`。

- [ ] **Step 3: 创建 migrate_storage.py**

```python
# scripts/migrate_storage.py
"""storage 分层迁移：storage/*.db → storage/novels/，user_data.db → storage/users/default/。"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORAGE = ROOT / "app_data" / "storage"


def main():
    novels_dir = STORAGE / "novels"
    users_dir = STORAGE / "users" / "default"
    novels_dir.mkdir(parents=True, exist_ok=True)
    users_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for db in sorted(STORAGE.glob("*.db")):
        if db.name == "user_data.db":
            target = users_dir / db.name
        elif db.name == "sync.ffs_db":
            continue  # FreeFileSync 元数据，跳过
        else:
            target = novels_dir / db.name
        if target.exists():
            print(f"跳过（已存在）: {db.name}")
            continue
        shutil.move(str(db), str(target))
        moved += 1
        print(f"移动: {db.name} → {target.relative_to(STORAGE)}")

    print(f"完成，共移动 {moved} 个文件")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add scripts/ && git rm build-nuitka.ps1 build-portable.ps1 build-portable.sh build-pypi.ps1 build-pypi.sh
git commit -m "重构: 构建脚本收纳进 scripts/，新增 storage 迁移脚本"
```

### Task B6: 全量验证 Phase B

- [ ] **Step 1: 最终回归**

Run: `python -m pytest tests/ -q`
Expected: 137+ passed，无 FAIL

- [ ] **Step 2: 验证三入口**

Run: `python -c "from backend.main import app; print('backend OK')" && python -c "import cli.main; print('cli OK')" && python -c "from shared import config, user_data; print('shared OK')"`
Expected: 三个 OK

- [ ] **Step 3: 更新 AGENTS.md 的 Commands 段落**

将 AGENTS.md 里的启动命令从 `services.backend.main:app` 改为 `backend.main:app`，`cd services/frontend` 改为 `cd frontend`。

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "文档: 更新 AGENTS.md 启动命令以匹配新目录结构"
```

---

## 执行顺序与依赖

```
Phase A（novelbase 内部，独立）
  A1 依赖 → A2 编码工具 → A3 RequestsEngine → A4 APIEngine
    → A5 BrowserEngine → A6 基类抽象 → A7 书源替换 → A8 验证

Phase B（外层，独立，但依赖 Phase A 完成后的稳定 novelbase）
  B1 shared → B2 backend 上提 → B3 frontend 上提 → B4 cli 合并
    → B5 scripts → B6 验证
```

Phase A 和 Phase B 可分别独立交付、独立验证。建议先完成 Phase A（核心库改造，风险集中在 novelbase），验证全绿后再做 Phase B（纯文件移动 + import 改写）。

# Engine 异步化设计（只增不改）

**日期**: 2026-08-12
**状态**: 已实施（2026-08-13，随 requests→httpx 迁移一并落地，commit 见 dev 分支）

> 实施说明：本设计与 `2026-08-12-requests-to-httpx-design.md` 合并实施——异步方法用 `httpx.AsyncClient`，同步方法也同步换成了 `httpx.Client`（httpx 一个库覆盖两种范式）。测试文件名为 `tests/test_engine_httpx.py`（非本设计第七节原写的 `test_engine_async.py`）。

---

## 一、动机

`novelbase/core/engine.py` 的三种引擎（`APIEngine` / `BrowserEngine` / `RequestsEngine`）的 `fetch_text` / `fetch_json` 全是**同步**方法。后端 FastAPI 路由（`async def`）只能通过 `loop.run_in_executor(executor, sync_fn, ...)` 把同步调用丢进线程池——这是"假异步"，线程池开销大、无法优雅取消。

本设计为引擎添加**异步方法**，为后续 downloader 异步化（`asyncio.gather` + `Semaphore`）和书源 HTTP 化铺路。

## 二、核心原则：只增不改

- ✅ 新增 `async_fetch_text` / `async_fetch_json` 方法
- ✅ 保留现有同步 `fetch_text` / `fetch_json`（书源函数仍同步调用它们，签名不变）
- ❌ 不删除、不改动任何现有方法
- ❌ 不改书源函数（40 个文件零改动）
- ❌ 不改 downloader（下一步再说）

命名规则：同步 `fetch_xxx` → 异步 `async_fetch_xxx`。

## 三、基类抽象方法

`Engine(ABC)` 新增两个抽象方法，三个子类各自实现：

```python
class Engine(ABC):
    # 现有同步方法（不动）
    @abstractmethod
    def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str: ...

    @abstractmethod
    def fetch_json(self, url, skip_delay=False, **kwargs) -> dict: ...

    # 新增异步方法
    @abstractmethod
    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str: ...

    @abstractmethod
    async def async_fetch_json(self, url, skip_delay=False, **kwargs) -> dict: ...
```

## 四、三个子类的异步实现

### 4.1 RequestsEngine / APIEngine — httpx.AsyncClient 真异步

这两个引擎底层都是 HTTP 请求（requests），异步版用 `httpx.AsyncClient` 真异步。

```python
class RequestsEngine(Engine):
    def __init__(self, options):
        # 现有同步 client 不动
        self._async_client = None  # 懒加载，首次 async 调用时创建

    def _get_async_client(self):
        if self._async_client is None:
            import httpx
            self._async_client = httpx.AsyncClient(
                timeout=self.options.timeout,
                headers=self.options.headers,
                cookies=self.options.cookies,
                proxies=self.options.proxies,
                follow_redirects=True,
            )
        return self._async_client

    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs):
        client = self._get_async_client()
        resp = await client.get(url)
        resp.encoding = encoding or resp.encoding or 'utf-8'
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return resp.text

    async def async_fetch_json(self, url, skip_delay=False, **kwargs):
        client = self._get_async_client()
        resp = await client.get(url)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return resp.json()
```

**关键差异（与同步版对照）**：

| 同步版 | 异步版 |
|--------|--------|
| `time.sleep()` | `await asyncio.sleep()`（不阻塞事件循环） |
| `requests.Session` | `httpx.AsyncClient` |
| 线程本地 session 池 | 单例 AsyncClient（连接池内建，天然复用） |

### 4.2 BrowserEngine — run_in_executor 包装

DrissionPage 是同步库，无法真异步。异步方法用 `asyncio.to_thread()` 包装现有同步逻辑：

```python
class BrowserEngine(Engine):
    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs):
        return await asyncio.to_thread(
            self.fetch_text, url=url, skip_delay=skip_delay, encoding=encoding, **kwargs
        )

    async def async_fetch_json(self, url, skip_delay=False, **kwargs):
        return await asyncio.to_thread(
            self.fetch_json, url=url, skip_delay=skip_delay, **kwargs
        )
```

对上层透明——调用方统一 `await engine.async_fetch_text(url)`，不关心底层是 httpx 还是线程池。

## 五、APIEngine 的特殊性

`APIEngine` 是代理模式（Rain.ink 等），有 `params` 参数和 `post_data` kwarg。异步版需完整复刻这些分支：

```python
async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs):
    post_data = kwargs.pop('post_data', None)
    client = self._get_async_client()
    if post_data is not None:
        # 合并 params（与同步 _request_post 一致）
        if self.options.params:
            merged = dict(self.options.params); merged.update(post_data)
            post_data = merged
        resp = await client.post(url, data=post_data)
    else:
        resp = await client.get(url, params=self.options.params)
    ...
```

## 六、依赖变化

`httpx` 目前只在 `[project.optional-dependencies].dev` 里（pytest 间接引入）。异步版 RequestsEngine/APIEngine 运行时需要 httpx，需把 `httpx` 从 dev 依赖**提升为主依赖**：

```toml
dependencies = [
    ...
    "httpx",        # 新增（从 dev 提升）
    ...
]
```

（`httpx` 已装 0.28.1，无需额外安装。）

## 七、测试

新增测试文件 `tests/test_engine_async.py`：

1. **接口存在性**：三个引擎实例都有 `async_fetch_text` / `async_fetch_json`，且是协程函数（`asyncio.iscoroutinefunction`）
2. **RequestsEngine 真异步**：mock httpx 响应，验证返回文本/JSON 正确
3. **BrowserEngine 包装**：`async_fetch_text` 调用 `asyncio.to_thread` 委托给 `fetch_text`（mock `fetch_text` 验证）
4. **同步方法未被破坏**：现有 `fetch_text`/`fetch_json` 签名不变，测试仍绿
5. **close 清理 AsyncClient**：close 时关闭 `_async_client`

## 八、不做的

- ❌ 不删除/修改现有同步 `fetch_text` / `fetch_json`
- ❌ 不改 `downloader.py`（异步 downloader 是下一步独立设计）
- ❌ 不改书源函数（40 个文件零改动）
- ❌ 不做 engine HTTP 端点（`/api/v2/engine/fetch_*` 是 HTTP 化阶段，另行设计）
- ❌ 不把 BrowserEngine "真异步化"（DrissionPage 不支持，`asyncio.to_thread` 是唯一方案）

## 九、风险与缓解

| 风险 | 缓解 |
|------|------|
| httpx 与 requests 行为差异（重定向、编码、代理） | async 版用 `follow_redirects=True` + 显式 encoding，与同步版对齐；测试覆盖 |
| AsyncClient 生命周期（未关闭泄漏连接） | `close()` 里同步关闭 `_async_client`；测试验证 |
| 双 client 并存导致配置不同步 | 两者读同一 `self.options`，`update_options` 时都生效 |
| `asyncio.to_thread` 需要 Python 3.9+ | 项目已 `requires-python = ">=3.10"`，满足 |

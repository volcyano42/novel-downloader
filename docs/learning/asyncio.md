# asyncio 异步 API 学习笔记

> 学习笔记 · 2026-08-15 · 基于 novelbase 全异步化改造的实战总结
> 代码示例均取自 `novelbase/` 真实代码，标注了文件与行号

## 0. 一句话总览

异步 = 单线程 + 协作式切换。核心只有两个关键字：`async def` 声明"这个函数可以暂停"，`await` 表示"在这里暂停，等这个异步操作完成"。

项目里实际用到的 asyncio API 就 8 个，每个都对应"替代了原来线程模型的某个东西"：

| 异步 API | 替代的原线程 API | 作用 |
|----------|----------------|------|
| `async def` / `await` | 普通函数 | 协程骨架 |
| `asyncio.sleep` | `time.sleep` | 异步睡眠 |
| `asyncio.gather` | `ThreadPoolExecutor` + `as_completed` | 并发调度 |
| `asyncio.Semaphore` | `max_workers` 参数 | 并发限流 |
| `asyncio.Event` | `threading.Event` | 协程间开关 |
| `asyncio.to_thread` | 直接调同步函数 | 同步库兜底 |
| `asyncio.run` | `threading.Thread` 启动 | 同步入口阻塞等完 |
| `get_running_loop().create_task` | `threading.Thread(daemon=True)` | 后台派发不阻塞 |
| `httpx.AsyncClient` | `requests.Session` | 真异步 HTTP |

---

## 1. `async def` / `await` —— 一切的基础

看 `RequestsEngine` 里同一方法的同步/异步两个版本（`novelbase/core/engine.py`）：

```python
# 同步版 —— 阻塞
def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
    response = self._client.get(url)          # ① 阻塞！没返回，线程卡死
    text = response.content.decode(...)
    if not skip_delay:
        time.sleep(random.uniform(*self.options.delay))  # ② 阻塞！干等
    return text

# 异步版 —— 不阻塞（同一方法，加了 async/await）
async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
    client = self._get_async_client()
    response = await client.get(url)          # ① 等响应期间让出控制权
    text = response.content.decode(...)
    if not skip_delay:
        await asyncio.sleep(random.uniform(*self.options.delay))  # ② 同样让出
    return text
```

**唯一区别就是 `await`**：同步版干等，异步版"我先去干别的，响应回来了再喊我"。

**要点**：
- `async def` 定义的是**协程函数**，调用它不会执行，只会返回一个协程对象
- `await` 后面必须跟"可等待对象"（协程 / Task / Future）
- `await client.get(url)` —— `client.get(url)` 返回协程，所以能 await

### 1.1 调用 async 函数 ≠ 启动事件循环

**关键认知**：调用 `async def` 函数只是"造了一个协程对象"，函数体一行都不会执行，也不会自动启动事件循环。

```python
async def hello():
    print("这行会执行吗？")   # ← 不会执行
    asyncio.get_running_loop()  # ← 也不会执行到

hello()   # 只返回 <coroutine>，丢弃，函数体根本没跑
# RuntimeWarning: coroutine 'hello' was never awaited
```

**实测对照**：

```python
# ① 直接调用 → 返回协程对象，不执行，get_running_loop 也不会被调用到
hello()

# ② asyncio.run → 启动事件循环 → 执行函数体 → get_running_loop 正常
asyncio.run(hello())

# ③ 在另一个 async 函数里 await → 也正常（外层最终被 run 驱动）
async def outer():
    await hello()   # hello 里的 get_running_loop 正常
asyncio.run(outer())
```

**一句话**：`get_running_loop()` 能成功的前提是"当前线程正在运行事件循环"，而事件循环**不会因为调用了 async 函数就自动出现**——必须 `asyncio.run()` 或框架（FastAPI/uvicorn）显式启动。

---

## 2. `asyncio.sleep()` vs `time.sleep()` —— 最直观的差异

```python
time.sleep(5)           # 阻塞整个线程 5 秒，其他协程全卡住 ❌
await asyncio.sleep(5)  # 挂起当前协程 5 秒，其他协程照跑 ✅
```

**关键理解**：事件循环里有 100 个协程，99 个都在 `await asyncio.sleep(5)`，这 5 秒里第 100 个协程可以正常跑。谁写了 `time.sleep(5)`，5 秒内所有协程全被冻住。**异步代码里绝不能出现 `time.sleep`**。

项目里的重试退避（`backend/services/task_manager.py`）：

```python
if attempt > 0:
    await asyncio.sleep(2 * attempt)   # 重试前退避，但不阻塞其他章节下载
```

---

## 3. `asyncio.gather()` —— 并发调度

最代表性的例子：图片批量下载 `RequestsEngine.async_fetch_images`（`novelbase/core/engine.py:447`）：

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

拆解：

```python
*(_one(u) for u in urls)   # 生成器展开：为每个 url 创建协程对象
# 等价于：_one(url1), _one(url2), _one(url3), ...

await asyncio.gather(...)  # 同时调度，全部完成才返回
# 返回 [图1bytes, 图2bytes, 图3bytes, ...]（按传入顺序）
```

**`gather` 三个特性**：
1. **并发**：所有协程同时开始（不是一个个来）
2. **保序**：返回值顺序 = 传入顺序（和完成先后无关）
3. **等待**：`await gather(...)` 等到全部完成

**对比线程池写法**（理解"异步替代了什么"的最佳对照）：

```python
# 改前：ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=5) as pool:
    futures = [pool.submit(_download_one, t) for t in img_tasks]
    for fut in as_completed(futures):   # as_completed：谁先完成先返回谁（乱序！）
        idx, data = fut.result()
        results[idx] = data             # 所以手动记 idx 再排序

# 改后：asyncio.gather —— 天然保序，不用手动排序，代码少一半
return await asyncio.gather(*(_one(u) for u in urls))
```

---

## 4. `asyncio.Semaphore()` —— 并发限流

```python
sem = asyncio.Semaphore(5)   # 计数器初始值 5

async def _one(url):
    async with sem:          # 进去前扣 1，出来加 1；扣到 0 后来者排队
        ...下载...
```

对比线程池：

```python
ThreadPoolExecutor(max_workers=5)   # 限制"最多 5 个线程"
asyncio.Semaphore(5)                # 限制"最多 5 个协程"
```

**关键理解**：解决同一个问题——"别一次性开太多并发"。章节下载 `max_workers=3` = 最多同时下 3 章；图片 `max_workers=5` = 最多同时下 5 张图。

---

## 5. `asyncio.to_thread()` —— 同步库的兜底手段（本项目现已不用）

旧实现 DrissionPage（浏览器）是**同步库**，`page.get()` 不能 await，当时的 `BrowserEngine` 用 `asyncio.to_thread` 兜底。2026-08-16 起换成 **Playwright**（`playwright.async_api`）后已改为**真异步**，`novelbase/core/engine.py:432-433`：

```python
async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
    """真异步：直接 await Playwright（不 to_thread）；浏览器失效时按 auto_reconnect 重建。"""
    await self._ensure_browser()
    for attempt in range(self.options.retry_times):
        ...
        return await self._do_fetch_text(url, skip_delay=skip_delay, **kwargs)
```

**`asyncio.to_thread(func, *args)` 做了什么**：
1. 把同步函数丢进一个**线程池**
2. 返回一个协程，可以 `await`
3. `await` 期间事件循环不阻塞（阻塞发生在那个线程里）

**三种引擎的"异步纯度"排序**：

| 引擎 | 实现 | 纯度 |
|------|------|------|
| RequestsEngine | `await client.get(url)`（httpx 真异步） | ⭐⭐⭐ |
| APIEngine | `await client.get(url)`（httpx 真异步） | ⭐⭐⭐ |
| BrowserEngine | `await playwright.async_api`（真异步 + page 池复用） | ⭐⭐⭐ |

**这就是为什么图片下载统一用 httpx 而不是浏览器**——图片是纯字节抓取，用浏览器是"杀鸡用牛刀还浪费内存开 tab"。

---

## 6. `asyncio.Event()` —— 暂停/取消的开关

Event 是个"布尔开关"。项目里用于下载任务的暂停/取消（`backend/services/task_manager.py`）：

```python
# 创建
task["_pause"] = asyncio.Event()   # 初始为 False

# 暂停：前端点暂停 → set() 拨到 True
def pause_task(task_id):
    task["_pause"].set()

# 下载协程检查开关（正确写法：轮询等 clear）
async def _wait_if_paused() -> bool:
    while task["_pause"].is_set():    # is_set() = 开关是真吗？
        task["status"] = "paused"
        await asyncio.sleep(0.1)      # 是就轮询等，直到 resume 把它 clear
        if task["_cancel"].is_set():
            return False
    task["status"] = "downloading"
    return True
```

**方法表**：

| 方法 | 作用 |
|------|------|
| `set()` | 开关拨到 True |
| `clear()` | 开关拨到 False |
| `is_set()` | 查询当前 True/False |
| `wait()` | ⚠️ 等它变 True（但已 True 就立即返回） |

**踩坑记录**：`wait()` 的语义是"等它变 True"，而暂停逻辑想要的是"等它变 False"（等 resume）。所以正确写法是 `while is_set(): await sleep(0.1)` 轮询，**不能用 `await wait()`**（已 set 时立即返回，暂停形同虚设）。

---

## 7. `httpx.AsyncClient` —— 真异步 HTTP 核心

`RequestsEngine` 的客户端管理（`novelbase/core/engine.py:397`）：

```python
def _get_async_client(self) -> httpx.AsyncClient:
    if self._async_client is None:
        self._async_client = httpx.AsyncClient(
            headers=self.options.headers,
            cookies=self.options.cookies,
            proxy=_resolve_proxy(self.options.proxies),
            follow_redirects=True,
            timeout=self.options.timeout,
            transport=httpx.AsyncHTTPTransport(retries=self.options.retry_times),
        )
    return self._async_client
```

**`httpx.AsyncClient` 是什么**：`requests.Session` 的异步版。

```python
# 同步版（requests 时代）
session = requests.Session()
resp = session.get(url)          # 阻塞

# 异步版（httpx 时代）
client = httpx.AsyncClient()
resp = await client.get(url)     # 不阻塞
```

**复用 vs 一次性**：
- `_get_async_client()` **复用**同一个 client，连接池/cookie 保留（像 Session）
- `async_fetch_images` 里每次 `async with httpx.AsyncClient(...)` 是**一次性**（下完就关）

复用快（连接复用）但要管理生命周期；一次性简单（自动关）但每次重建连接。

---

## 8. 三个"进异步世界"的入口

```python
# backend/services/task_manager.py 的 create_task（同步函数）
def create_task(novel_id, chapters, title, ...):
    ...
    loop = asyncio.get_running_loop()           # ① 拿到"当前正在跑的事件循环"
    loop.create_task(_run_download(task, ...))  # ② 往循环塞后台协程
    return {"task_id": ..., "total": ...}       # ③ 立即返回，不等待
```

| API | 干什么 | 什么时候用 |
|-----|--------|-----------|
| `asyncio.run(coro)` | 新建循环 → 跑协程 → 关闭循环 | 同步入口想**阻塞等完**（CLI 命令） |
| `get_running_loop()` | 拿到**已在跑**的循环 | 已身处异步里，想派后台任务 |
| `loop.create_task(coro)` | 往循环塞协程，**不阻塞** | "发起后立即返回，后台继续" |

**场景对照**：

```python
# CLI：同步脚本，要"等下载完成才返回"
asyncio.run(download(...))   # 阻塞直到下载完

# FastAPI：已是 async 路由，要"发起任务立即返回，下载后台跑"
loop = asyncio.get_running_loop()      # 路由已在事件循环里
loop.create_task(_run_download(...))   # 后台跑，路由立即 return
```

**要点**：`asyncio.run` 一个线程里只能调一次（它管整个循环生命周期）。FastAPI 已把循环跑起来了，路由里不能再 `asyncio.run`，要用 `get_running_loop().create_task()`。

### 8.1 `get_running_loop()` 是线程隔离的

`get_running_loop()` 返回的是"**当前线程**里正在运行的事件循环"，绝不会取到另一个线程的循环。原理是 Python 的事件循环用**线程局部存储（thread-local）**记录"这个线程当前在跑哪个 loop"：

```python
# asyncio 内部大致如此（简化）
_running_loop = threading.local()   # 每个线程一份，互不可见

def get_running_loop():
    loop = _running_loop.loop        # 只读当前线程的
    if loop is None:
        raise RuntimeError("no running event loop")
    return loop
```

**三个推论**：

1. **每个线程有自己的 running loop 上下文**，互不可见
2. **当前线程没在跑 loop** → `get_running_loop()` 直接抛 `RuntimeError`（不是返回别的线程的 loop）
3. **事件循环绑定线程**：线程 A 创建的 loop 只能在线程 A 上 `run_until_complete`，不能拿去线程 B 跑（loop 不是线程安全的）

**典型错误场景**：

```python
# 场景 1：在没 loop 的线程里调用
def sync_func():
    loop = asyncio.get_running_loop()   # ❌ RuntimeError: no running event loop

# 场景 2：主线程没有，但另一个线程有
def worker():
    asyncio.run(main())                  # 线程B 有自己的 loop
threading.Thread(target=worker).start()
loop = asyncio.get_running_loop()        # 主线程（线程A）❌ 还是 RuntimeError

# 场景 3：拿到 loop 后跨线程用（真正的坑）
loop = asyncio.new_event_loop()          # 线程A 创建
# 在线程B 里：
loop.run_until_complete(...)             # ❌ loop 绑定线程A，不能在线程B 跑
```

**澄清一个易混点**：`get_running_loop()` 不是"取到某个协程的循环"，而是"取到当前线程正在运行的循环"。协程本身不拥有循环，**线程才拥有循环**；一个线程同一时刻只能跑一个循环。

**为什么项目里能安全用**：`create_task` 是同步函数，但它的调用方是 async 路由（`download.py` 的 `download_chapters`），调用链是同步的——路由跑在事件循环里 → 同步调用 `create_task` → 此刻当前线程确实有 running loop。而 `asyncio.to_thread` 开的临时线程里**没有** running loop，谁在那里调 `get_running_loop()` 会直接抛 RuntimeError。

---

## 9. 事件循环到底是什么

**一句话**：事件循环是"调度器"，维护待办任务队列，不断问"谁可以继续跑了？"，让能跑的跑，等着的继续等。

```
事件循环（单线程）：
  循环开始
  ├─ 协程A：await client.get(url) → "我要等响应，挂起我"
  ├─ 协程B：await asyncio.sleep(5) → "我要睡5秒，挂起我"
  ├─ 协程C：继续执行 → "我没事干，继续跑"
  │
  │ （某时刻，A 的响应回来了）
  ├─ 协程A：被唤醒，继续执行
  │ （B 还在睡）
  │ ...
  循环结束
```

**为什么单线程却快**：小说下载是 **I/O 密集**（大部分时间等网络响应），不是 CPU 密集。单线程"等 A 时跑 B"就够了，不需要开 100 个线程（每线程占内存 + 要加锁）。

**对比项目**：原 ThreadPoolExecutor 开 3 个线程，每线程干等网络（浪费）；asyncio 一个线程，3 个协程轮流等/跑（高效）。

---

## 10. API 全景图

```
                        ┌─ asyncio.run()          同步入口阻塞等完（CLI）
       进入异步 ────────┤
                        └─ get_running_loop().create_task()  后台派发（FastAPI）

       定义协程 ──────── async def / await

       并发调度 ──────── asyncio.gather(*coros)        一起跑，保序返回
       并发限流 ──────── asyncio.Semaphore(n) + async with

       协程通信 ──────── asyncio.Event  set/clear/is_set/轮询等

       异步睡眠 ──────── await asyncio.sleep(n)         让出控制权
       同步库兜底 ────── await asyncio.to_thread(fn)    丢线程池

       真异步 I/O ────── httpx.AsyncClient + await client.get()
```

---

## 附录：异步心智模型三连问

1. **这函数会阻塞吗？** 有 I/O（网络/磁盘）→ 异步版用 `await`；纯 CPU（解析/正则）→ 保持同步
2. **要并发吗？** 是 → `gather` + `Semaphore`；否 → 顺序 `await`
3. **这是同步库吗？** 是 → `to_thread` 兜底；否 → 原生 async

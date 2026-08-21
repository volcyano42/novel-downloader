# 书源全异步化设计

> 日期：2026-08-13
> 状态：已确认

## 1. 背景与目标

novelbase 的 engine 三层（Requests/API/Browser）已完成 `async_fetch_text` / `async_fetch_json` 异步方法，但书源函数（45 个文件）、downloader、CLI、backend 仍是同步 + ThreadPoolExecutor 模型。本次将**整条下载链路全异步化**，并把散落在解析函数里的图片 I/O 收敛到 engine 层，实现「规则算 URL、框架做网络」的分层。

**目标性质**：学习项目，完整实践 asyncio 全链路。图片 I/O 是真实收益点；纯 CPU 解析改 async 无性能收益但无损失。

## 2. 设计决策

1. **同步+异步共存，边界收窄**：engine 层保留同步 `fetch_text`/`fetch_json`（底层能力 + 测试用）；业务链路（书源/downloader/CLI/backend）全部 async，不保留同步业务入口。
2. **图片 I/O 归 engine**：新增 `async_fetch_images`，parse 函数回归纯函数（只算 URL，不下载字节）。
3. **全链路并发**：章节下载 + 图片下载都用 `asyncio.gather` + `asyncio.Semaphore`。
4. **CLI**：下载函数 `async def`，入口 `asyncio.run()` 包装。
5. **task_manager async 原生**：`threading.Thread` → `asyncio.create_task`，`threading.Event` → `asyncio.Event`。

## 3. 分层架构

```
调用层
  ├─ backend 路由：async def，直接 await downloader 的 async 函数
  └─ CLI：cli/core.py 下载函数 async def，cli/main.py 用 asyncio.run()
        ↓
downloader 层（novelbase/core/downloader.py）
  └─ resolve_meta / resolve_chapter_list / resolve_chapter / search 全 async def
        ↓
resolve 分发层（novelbase/source.py）
  └─ resolve() 返回的书源函数全是 async 函数（resolve 本身不改，只返回函数）
        ↓
书源能力函数层（45 文件，全 async def）
  ├─ await engine.async_fetch_text / async_fetch_json
  ├─ parse 纯函数（同步，零 I/O）
  └─ await engine.async_fetch_images（图片）
        ↓
engine 层（已完成的 async 方法 + 新增 async_fetch_images）
```

## 4. 各层改动

### 4.1 engine：新增 async_fetch_images

在 Engine 基类声明抽象方法，三子类实现：

```python
# Engine 基类（ABC）
@abstractmethod
async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
    """批量下载图片字节，返回与 urls 等长的 bytes 列表（失败项为 b""）。"""
```

RequestsEngine / APIEngine / BrowserEngine 三个子类**统一用 httpx 实现**（`httpx.AsyncClient + Semaphore`），**不用 DrissionPage**。理由：图片下载是纯字节抓取，不需要 JS 渲染；用 DrissionPage 会 `new_tab()` 多开标签页浪费内存，且 `asyncio.to_thread` 会把线程带回已异步化的链路。BrowserEngine 版只需在相同结构上注入浏览器会话的 cookie/headers（Referer/UA）以复用登录态、过防盗链：

```python
async def async_fetch_images(self, urls, max_workers=5):
    sem = asyncio.Semaphore(max_workers)
    async def _one(url):
        async with sem:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                    return (await client.get(url)).content
            except httpx.HTTPError:
                return b""
    return await asyncio.gather(*(_one(u) for u in urls))
```

三个子类的差异仅在 `httpx.AsyncClient` 构造参数：Requests/API 用各自配置的 headers/cookies，Browser 用从 `self._browser` 会话提取的 cookie + Referer/UA。

### 4.2 书源能力函数：async def + parse 纯函数化

45 个书源文件的四类能力函数（search / novel_info / chapter_list / chapter_content）统一改：

- `def xxx(...)` → `async def xxx(...)`
- `engine.fetch_text(...)` → `await engine.async_fetch_text(...)`
- `engine.fetch_json(...)` → `await engine.async_fetch_json(...)`

**parse 纯函数化**：`_common.py` 里所有 parse 函数保持同步，但去掉内嵌的图片字节下载，改为返回「图片 URL 列表」，由书源能力函数统一调 `engine.async_fetch_images`。

**parse 返回约定（消除歧义）**：凡原本在 parse 内下载图片的 parse 函数，改为返回 `(结果, 图片URL列表)` 二元组，或直接在结果对象上挂 `image_urls` 字段。具体以 fanqie 的 `parse_chapter_content` 为例：

```python
# 改前：parse 内下载图片，返回 Chapter（images 已填充）
def parse_chapter_content(html, chapter) -> Chapter:
    ...
    img_data = [下载字节...]
    chapter.images = tuple(Illustration(...))
    return chapter

# 改后：parse 纯函数，返回 (Chapter, img_urls)
def parse_chapter_content(html, chapter) -> tuple[Chapter, list[dict]]:
    ...
    img_urls.append({"url": ..., "alt": ..., "insert": ...})  # 只算 URL + 元信息
    return chapter, img_urls
```

书源能力函数负责组装：

```python
async def chapter_content(chapter, engine, **kwargs):
    html = await engine.async_fetch_text(chapter.url)
    ch, img_urls = parse_chapter_content(html, chapter)       # 纯 CPU
    if img_urls:
        data = await engine.async_fetch_images([i["url"] for i in img_urls])
        ch.images = tuple(Illustration(raw_data=d, url=i["url"], alt=i["alt"], insert=i["insert"])
                          for i, d in zip(img_urls, data))
    return ch
```

受影响文件（含图片下载的）：
- `novelbase/sources/fanqie/_common.py` — parse_chapter_content 里的 ThreadPoolExecutor 图片下载抽出；返回 `(Chapter, img_urls)`
- `novelbase/sources/fanqie/requests/chapter_content.py`、`api/oiapi/chapter_content.py`、`api/rain/chapter_content.py` — 适配新的二元组返回，组装 Illustration
- `novelbase/sources/fanqie/api/oiapi/novel_info.py` — 封面下载改走 `engine.async_fetch_images`
- `novelbase/sources/92xs/requests/novel_info.py` — 封面下载（requests.get，顺带清理成 httpx）
- `novelbase/sources/qimao/api/rain/novel_info.py` — 封面下载

### 4.3 downloader：async def

`novelbase/core/downloader.py` 五个业务函数：

| 函数 | 改后 |
|------|------|
| search | `async def search(...)` |
| resolve_meta | `async def resolve_meta(...)` |
| resolve_chapter_list | `async def resolve_chapter_list(...)` |
| resolve_chapter | `async def resolve_chapter(...)` |
| export | 保持同步（本地 CPU + 文件写，无网络 I/O） |

同步版本删除（CLI 也全异步，无同步调用方）。`resolve()` 分发函数本身不改（它只返回书源函数，现在这些函数是 async 的，调用方 await）。

### 4.4 backend 路由：直接 await

`backend/routers/download.py` 里 5 处 `await loop.run_in_executor(executor, fn, ...)` 改成直接 `await fn(...)`。`engine_manager.py` 顶部两个未使用的 `_browser_executor` / `_requests_executor`（死代码）删除。

### 4.5 task_manager：async 原生

| 现状（线程模型） | 重构后（async 原生） |
|----------------|-------------------|
| `threading.Thread(target=_run_download)` | `asyncio.create_task(_run_download(...))` |
| `ThreadPoolExecutor` + `as_completed` | `asyncio.Semaphore` + `asyncio.gather` |
| `threading.Event()` 暂停/取消 | `asyncio.Event()` |
| `threading.Lock()` | `asyncio.Lock()` |
| `time.sleep(2*attempt)` 重试退避 | `await asyncio.sleep(2*attempt)` |

- `_run_download` 变 `async def`，`asyncio.create_task` 启动。
- 对外 API（create_task / list_tasks / get_task / pause_task / resume_task / delete_task）签名保持同步——它们只改状态 + 设 Event，无 I/O，FastAPI 路由直接调用，前端无感。
- `asyncio.Event` 的 set/wait/is_set 与 threading.Event 同名，`wait()` 加 await。

**暂停语义（优雅暂停）**：当前下载中的章节跑完后、下一章开始前停住。browser 的 `asyncio.to_thread` 不可中断，靠 engine timeout 兜底，不做「强制中断当前请求」。

暂停实现有三个检查点（`_wait_if_paused` helper 统一实现）：
1. **章节前检查点**：`_download_one` 开头，暂停中轮询 `await asyncio.sleep(0.1)` 等 resume（注意：**不能用 `await _pause.wait()`**——asyncio.Event 的 `wait()` 在 event 已 set 时立即返回，逻辑反了，暂停会形同虚设；必须 `while _pause.is_set(): await sleep` 轮询等 clear）。
2. **排队检查点**：`_run_one` 的 `async with sem:` 之前，排队协程拿信号量前先响应暂停，不占信号量。
3. **收尾检查点**：gather 结束后若 `_pause` 仍 set，则 `status="paused"` 并循环等待，resume 后重跑 `status=="pending"` 的剩余章节再收尾。

### 4.6 CLI：async def + asyncio.run

- `cli/core.py` 的 `_do_download_inner` 及章节下载循环改 `async def`，内部 asyncio 并发。
- `cli/main.py` 调用处 `asyncio.run(...)`。

## 5. 错误处理

- 图片下载失败返回 `b""`（与现状一致，失败不中断整章）。
- 章节下载的 ChapterNotFoundError / 通用异常捕获逻辑保持，只是 `time.sleep` 重试退避改 `await asyncio.sleep`。
- 取消语义：`asyncio.Event` 的 `set()` 后，下载协程在「开始前」和「落库前」两处检查点退出，行为与现状一致。

## 6. 测试

- 现有 160 测试保持全绿（engine 同步方法未删，测试不受影响）。
- 新增：
  - engine `async_fetch_images` 批量下载（成功/失败项/并发上限）。
  - BrowserEngine 的 `async_fetch_images` 用 httpx（mock 验证不调用 `new_tab`/`get_page`，且注入 cookie/Referer）。
  - 书源 async 函数能被 `asyncio.run` 调用并正确返回。
  - parse 纯函数返回 URL 列表、不下载字节（mock 验证无 I/O）。
  - task_manager async 原生：create/pause/resume/cancel 语义不变。
  - downloader async 函数 await 书源函数。

## 7. 不做的事

- 不改 export 导出器（本地操作，与异步化无关）。
- 不改 engine 同步方法（保留作为底层能力 + 测试）。
- 不改 resolve 分发机制（只返回函数，天然兼容 async）。
- 不改前端（backend 对外 API 签名不变）。

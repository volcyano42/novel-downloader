# requests → httpx 全量替换设计

**日期**: 2026-08-12
**状态**: 已确认，待实施
**前置**: 必须先完成 `2026-08-12-engine-async-design.md`（engine 异步化）再执行本替换

---

## 一、动机

engine 异步化完成后，项目中同时存在两个 HTTP 库：

- `requests`（同步，被 engine 同步方法和 12 个书源文件使用）
- `httpx`（异步，被 engine 的 `async_fetch_*` 使用）

维护两套 HTTP 库造成：API 不一致、连接池双份、认知负担。httpx 是 requests 的**兼容超集**——同步 `httpx.Client` 几乎一一对应 `requests.Session`，同时提供 `httpx.AsyncClient` 真异步。全量替换为 httpx 后，**一个库两用**。

## 二、替换范围

`requests` 在 novelbase 中共 **15 个文件**使用，分三类：

| 类别 | 文件 | 替换 |
|------|------|------|
| engine 核心 | `engine.py`（APIEngine + RequestsEngine 的 Session/Retry/代理/headers） | `requests.Session` → `httpx.Client` |
| 书源裸请求 | 12 个 `search.py` / `novel_info.py` / `_common.py` | `requests.get/post` → `httpx.get/post` |
| 异常类型 | 全部 15 处 `requests.RequestException` | `httpx.HTTPError` |

### 完整文件清单

```
novelbase/core/engine.py                    # APIEngine + RequestsEngine
novelbase/sources/92xs/requests/search.py
novelbase/sources/fanqie/api/oiapi/novel_info.py
novelbase/sources/fanqie/api/rain/novel_info.py
novelbase/sources/fanqie/browser/search.py
novelbase/sources/fanqie/requests/search.py
novelbase/sources/fanqie/_common.py
novelbase/sources/qidian/_common.py
novelbase/sources/qimao/api/rain/novel_info.py
novelbase/sources/qimao/_common.py
```

（另有 `92xs` 的 `requests/search.py` 使用 `requests.post`，一并处理。）

## 三、API 对照表

| requests | httpx |
|----------|-------|
| `requests.Session()` | `httpx.Client()` |
| `requests.get(url, timeout=...)` | `httpx.get(url, timeout=...)` |
| `requests.post(url, data=...)` | `httpx.post(url, data=...)` |
| `session.mount("https://", HTTPAdapter(...))` | 构造 `httpx.Client(transport=...)` |
| `session.headers = CaseInsensitiveDict(...)` | `httpx.Client(headers=...)`（`httpx.Headers` 天然不区分大小写） |
| `session.proxies = {...}` | `httpx.Client(proxies={...})` |
| `session.cookies` | `httpx.Client(cookies=...)` |
| `resp.text` | `resp.text` |
| `resp.content` | `resp.content` |
| `resp.json()` | `resp.json()` |
| `resp.encoding = 'utf-8'`（可写） | `resp.encoding`（只读，编码靠构造/`resp.charset_encoding`） |
| `resp.apparent_encoding`（chardet 探测） | ❌ 无，需自建探测 |
| `requests.RequestException` | `httpx.HTTPError`（基类） |
| `requests.RequestException`（超时） | `httpx.TimeoutException`（`HTTPError` 子类） |

## 四、三个必须处理的兼容性差异

### 4.1 重定向默认值相反

- requests：`allow_redirects=True`（默认跟随）
- httpx：`follow_redirects=False`（默认不跟随）

**影响**：`fanqie/_common.py` 的 `resolve_changdunovel` 依赖重定向解析 `book_id`，不显式设置会静默失败。

**处理**：所有 `httpx.get/post` 调用显式加 `follow_redirects=True`；或创建统一封装。

### 4.2 apparent_encoding 缺失

requests 的 `resp.apparent_encoding` 用 chardet 探测编码（对无 charset 声明的中文页面很关键）。httpx 无此属性。

**处理**：新建 `novelbase/utils/encoding.py` 提供探测函数，替代 `apparent_encoding`：

```python
def detect_encoding(content: bytes) -> str:
    """探测 bytes 编码，优先 chardet/chardet 缺省回退 utf-8。"""
    try:
        import charset_normalizer  # httpx 的依赖，已随 httpx 安装
        best = charset_normalizer.from_bytes(content).best()
        return best.encoding if best else 'utf-8'
    except ImportError:
        return 'utf-8'
```

（httpx 依赖 `charset_normalizer`，无需额外安装；若想更稳可加 `chardet`。）

### 4.3 重试机制写法不同

- requests：`urllib3.util.retry.Retry(total, backoff_factor, status_forcelist)` + `HTTPAdapter`
- httpx：`httpx.HTTPTransport(retries=N)`（只支持次数，不支持 backoff/status 过滤）

**影响**：`engine.py` 的 `_create_session` 现有 `Retry(total=retry_times, backoff_factor=..., status_forcelist=[500,502,503,504])` 无法直接平移。

**处理**：保留语义，自定义 transport：

```python
import httpx

def _create_transport(options) -> httpx.HTTPTransport:
    # httpx 原生 retries 无 backoff/status 过滤，退化为简单重试次数
    return httpx.HTTPTransport(retries=options.retry_times)

client = httpx.Client(transport=_create_transport(options), ...)
```

> 说明：`backoff_factor` 和 `status_forcelist` 的精细语义在 httpx 原生层丢失。如需完整保留，可后续引入 `httpx-retries` 插件或自定义 `transport`。首版先保留 `retry_times` 次数语义，`backoff_factor`/`status_forcelist` 标注为 TODO（见风险表）。

## 五、engine.py 改造要点

### 5.1 RequestsEngine

```python
class RequestsEngine(Engine):
    def __init__(self, options):
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

    def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs):
        resp = self._client.get(url)
        if encoding:
            return resp.content.decode(encoding, errors='replace')
        # 无显式编码时探测（替代 apparent_encoding）
        enc = detect_encoding(resp.content)
        return resp.content.decode(enc, errors='replace')
```

### 5.2 APIEngine

同 RequestsEngine，但保留 `params` 合并和 `post_data` 分支逻辑。

### 5.3 会话管理简化

requests 版用 `threading.local` + 锁维护线程隔离 session 池（因为 requests.Session 非线程安全）。httpx.Client **线程安全**，单例即可，删除 `_session_local`/`_session_lock`/`_sessions` 列表。

## 六、书源文件改造要点

书源里的裸请求是机械替换，但注意两点：

1. `requests.get(...).content` → `httpx.get(..., follow_redirects=True).content`
2. `requests.RequestException` → `httpx.HTTPError`

示例（`fanqie/requests/search.py`）：

```python
# 改前
import requests
data = requests.get(search_url).json()

# 改后
import httpx
data = httpx.get(search_url, follow_redirects=True).json()
```

## 七、依赖变化

```toml
dependencies = [
    ...
    "httpx",        # 保留（已在 engine 异步化阶段提升为主依赖）
    # "Requests",   # ❌ 移除
    # "urllib3",    # ❌ 移除（仅被 requests 的 Retry 使用）
    ...
]
```

> 注意：`DrissionPage` 可能间接依赖 requests，移除前需确认不破坏其内部。若破坏，保留 requests 但标记为"仅 DrissionPage 间接依赖"。

## 八、测试

1. **现有 137 个测试全绿**（替换后行为不回归）
2. 新增 `tests/test_engine_httpx.py`：
   - RequestsEngine.fetch_text 返回正确文本
   - 编码探测：无 charset 的页面能正确解码中文
   - 重定向：`follow_redirects=True` 生效
   - 代理/headers/cookies 透传
3. 书源冒烟：对每个平台跑一次 `search`，验证替换后书源仍能取到数据

## 九、实施顺序（严格）

1. 先完成 `engine-async-design`（异步方法落地）
2. 再执行本替换（requests → httpx）
3. 两者**不得混在一次提交**——异步化是"加方法"，替换是"改行为"，分开才能定位问题

## 十、不做的

- ❌ 不顺便改 downloader 的并发模型（`asyncio.gather` 是后续独立设计）
- ❌ 不改书源的解析逻辑（只改 HTTP 调用层）
- ❌ 不引入 `httpx-retries` 等插件（首版保留 retry_times 语义即可）
- ❌ 不替换 `DrissionPage`（BrowserEngine 的浏览器层，与 requests 无关）

## 十一、风险与缓解

| 风险 | 缓解 |
|------|------|
| `backoff_factor`/`status_forcelist` 语义丢失 | 首版只保留 retry_times；TODO 后续自定义 transport 补齐 |
| 编码探测不如 requests 的 apparent_encoding | 用 charset_normalizer（httpx 自带依赖）自建探测，测试覆盖中文页 |
| 重定向默认值相反导致书源静默失败 | 所有调用显式 `follow_redirects=True` + 书源冒烟测试 |
| DrissionPage 间接依赖 requests | 移除前验证；若依赖则保留 requests |
| 15 个文件机械替换漏改 | grep 扫描残留 `import requests`，CI 加检查 |

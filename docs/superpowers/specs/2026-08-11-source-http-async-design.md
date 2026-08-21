# 书源 HTTP 路由化 + 异步化 设计文档

**日期**: 2026-08-11
**状态**: 方案记录，暂不实施

---

## 一、动机

当前书源（`novelbase/sources/`）是纯 Python 模块，通过 `import_module` 动态加载。限制：
- 书源只能是 Python，无法用 Rust/Go 等语言编写
- 同步阻塞调用链，下载并发靠 `ThreadPoolExecutor`
- Nuitka 编译后需硬编码兜底（动态 import 失效）

目标：将书源改为 **语言无关的 HTTP 服务**，同时将整个 novelbase 调用链 **异步化**。

---

## 二、架构总览

```
FastAPI 主进程（端口 8000）
│
├── /api/v2/engine/fetch_text    ← engine HTTP 端点
├── /api/v2/engine/fetch_json
├── /api/v2/sources/register     ← 书源动态注册
├── /api/v2/sources/unregister
│
├── source.py.resolve()          ← 统一分发层（async def）
│     ├── Python 书源（同进程 await）
│     └── HTTP 书源（跨进程 httpx POST）
│
└── downloader.py                ← asyncio.gather 并发控制
```

### 调用链（下载单章）

```
downloader.resolve_chapter(chapter, engine)
  │  await
  ▼
source.resolve("fanqie", "browser", "chapter_content", variant)
  │  await httpx.post("http://127.0.0.1:9100/chapter_content", json=...)
  ▼
外部书源进程（Rust/Go/Node.js）
  │  await httpx.get("http://127.0.0.1:8000/api/v2/engine/fetch_text?url=...")
  ▼
engine HTTP 端点（Python 主进程内）
  │  httpx.AsyncClient / BrowserEngine(线程池)
  ▼
返回 HTML → 外部书源解析 → 返回 Chapter JSON
```

---

## 三、协议定义

### 3.1 书源注册

```
POST /api/v2/sources/register
Content-Type: application/json

{
  "name": "fanqie",
  "show_name": "番茄",
  "hosts": ["fanqienovel.com", "changdunovel.com"],
  "id_pattern": "^fanqie_(\\d{19})$",
  "origin_id_pattern": "^\\d{19}$",
  "capabilities": {
    "api": {
      "oiapi": ["search", "novel_info", "chapter_list", "chapter_content"],
      "rain": ["search", "novel_info", "chapter_list", "chapter_content"]
    },
    "browser": {"default": ["search", "novel_info", "chapter_list", "chapter_content"]},
    "requests": {"default": ["search", "novel_info", "chapter_list", "chapter_content"]}
  },
  "endpoint": "http://127.0.0.1:9100"
}

Response: {"ok": true, "message": "registered"}
```

### 3.2 调用书源

```
POST {endpoint}/{function}
Content-Type: application/json

// search
{"function": "search", "query": "修仙", "kwargs": {"page": 1}}

// novel_info
{"function": "novel_info", "url": "https://fanqienovel.com/...", "kwargs": {}}

// chapter_list
{"function": "chapter_list", "url": "https://fanqienovel.com/...", "kwargs": {}}

// chapter_content
{"function": "chapter_content", "chapter": {"id": "...", "url": "...", "title": "...", "order": 1, "novel_id": "..."}, "kwargs": {}}
```

### 3.3 engine 端点

```
GET /api/v2/engine/fetch_text?url={url}&encoding={encoding}&timeout={timeout}
Response: {"content": "<html>...", "status_code": 200, "url": "..."}

GET /api/v2/engine/fetch_json?url={url}&timeout={timeout}
Response: {"data": {...}, "status_code": 200}
```

### 3.4 序列化模型

所有 Novel/Chapter/SearchResult 在 HTTP 层统一为 JSON，与现有 `models/` dataclass 的 `loads()` 方法对齐：

```json
// SearchResult
{"title": "修仙从...", "author": "...", "url": "...", "platform": "fanqie", "description": "...", "cover_url": "..."}

// Chapter
{"id": "fanqie_xxx_ch_1", "url": "...", "novel_id": "fanqie_xxx", "title": "第一章", "order": 1, "content": "...", "images": [...]}

// Novel
{"title": "...", "url": "...", "id": "fanqie_xxx", "serial": 1000, "author": "...", "description": "...", "cover": {...}}
```

---

## 四、异步化方案

### 4.1 阶段 1：requests engine → httpx.AsyncClient

| 改前 | 改后 |
|------|------|
| `requests.Session` | `httpx.AsyncClient` |
| `engine.fetch_text(url)` 同步 | `async def fetch_text(url)` |
| `engine.fetch_json(url)` 同步 | `async def fetch_json(url)` |

收益：连接池复用、并发请求不占线程、取消传播。

### 4.2 阶段 2：BrowserEngine 线程池包装

DrissionPage 是同步库，无法真 async。封装方案：

```python
class BrowserEngine:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=3)

    async def fetch_text(self, url: str, **kwargs) -> str:
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._sync_fetch_text, url, kwargs
        )
```

对上层透明——调用方只用 `await engine.fetch_text(url)`，不关心底层是 httpx 还是线程池。

### 4.3 阶段 3：downloader 并发模型

```python
# 改前
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(_download_one, ch) for ch in chapters]
    for f in as_completed(futures):
        f.result()

# 改后
semaphore = asyncio.Semaphore(10)
async def _download_one(ch):
    async with semaphore:
        async with asyncio.timeout(30):
            return await resolve_chapter(ch, engine)

tasks = [_download_one(ch) for ch in chapters]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

收益：
- 1000 个协程共享 10 个并发槽，无线程切换
- `asyncio.timeout` 优雅超时
- `return_exceptions=True` 单章失败不影响其他章

### 4.4 各模块异步化决策

| 模块 | 方案 | 原因 |
|------|------|------|
| requests engine | `httpx.AsyncClient` | 真正 async，最大收益 |
| BrowserEngine | `run_in_executor` 包装 | DrissionPage 不支持 async |
| 书源解析 | `asyncio.to_thread` | 纯 CPU，丢线程池 |
| storage (SQLite) | 保持线程池 | 写入 <1ms，异步化无意义 |
| downloader | `asyncio.gather` + `Semaphore` | 并发 + 取消 + 超时 |

---

## 五、外部书源启动方案（B+C 混合）

### 5.1 配置格式

每个书源目录下放 `source.json`：

```json
{
  "name": "fanqie",
  "show_name": "番茄",
  "hosts": ["fanqienovel.com", "changdunovel.com"],
  "id_pattern": "^fanqie_(\\d{19})$",
  "origin_id_pattern": "^\\d{19}$",
  "capabilities": {
    "api": {"oiapi": [...], "rain": [...]},
    "browser": {"default": [...]},
    "requests": {"default": [...]}
  },
  "endpoint": "http://127.0.0.1:9100",
  "launch": {
    "command": ["./fanqie-source", "--port", "9100"],
    "health_check_url": "http://127.0.0.1:9100/health",
    "health_check_timeout": 10,
    "shutdown_timeout": 5
  }
}
```

### 5.2 Python 主进程行为

```
启动阶段:
  1. 扫描 sources/*/source.json
  2. 如果 launch 存在 → subprocess.Popen(command)
  3. 轮询 health_check_url 直到 200 或超时
  4. 如果 launch 不存在 → 假设进程已运行，POST endpoint/health 试探

运行阶段:
  5. resolve() 收到调用 → 查注册表找到 endpoint → httpx.post(endpoint, ...)

关闭阶段:
  6. 遍历所有子进程 → SIGTERM → 等 shutdown_timeout 秒 → SIGKILL
```

### 5.3 `command` 跨平台约定

| 约定 | 说明 |
|------|------|
| 相对路径 | 相对于 `source.json` 所在目录 |
| 可执行文件放在书源目录内 | `sources/fanqie/fanqie-source`（Linux）或 `fanqie-source.exe`（Windows） |
| Nuitka 打包 | `--include-data-dir=sources=sources` 一并打包 |

```json
// 跨平台示例
"command": ["./fanqie-source", "--port", "9100"]   // Linux
"command": [".\\fanqie-source.exe", "--port", "9100"]  // Windows
```

> 注：未来可通过 `"command_linux"` / `"command_windows"` 字段做平台区分，首版先不做。

### 5.4 端口分配

| 策略 | 方案 |
|------|------|
| 默认 | `source.json` 中硬编码端口（简单直观） |
| 冲突处理 | 启动失败（端口占用）→ 跳过该书源，日志 warning |
| 动态端口 | 未来可选：`"port": 0` → 主进程分配空闲端口 → 通过环境变量 `$SOURCE_PORT` 传给子进程 |

---

## 六、渐进实施路线

| 阶段 | 内容 | 改动量 | 独立收益 |
|------|------|--------|----------|
| 1 | requests engine → `httpx.AsyncClient` | 1 文件 | ⭐⭐⭐ 并发不占线程 |
| 2 | downloader → `asyncio.gather` + `Semaphore` | 2 文件 | ⭐⭐ 优雅并发/取消/超时 |
| 3 | engine HTTP 端点 (`/api/v2/engine/*`) | 1 文件 | ⭐⭐ 调试/监控接口 |
| 4 | `source.json` 加载 + `subprocess` 启动 | 2 文件 | ⭐⭐ 进程生命周期管理 |
| 5 | `resolve()` 支持 HTTP 书源 | 1 文件 | ⭐ 语言无关书源 |
| 6 | BrowserEngine `run_in_executor` 包装 | 1 文件 | ⭐ 接口统一 |

每步可独立交付，不依赖后续步骤。

---

## 七、不做的

- ❌ 全量书源解析改 async（纯 CPU，无收益，56 个文件改造成本太大）
- ❌ storage 换 aiosqlite（SQLite 串行写入是设计特性，异步不解决问题）
- ❌ BrowserEngine "真正异步化"（DrissionPage 不支持，线程池是唯一方案）
- ❌ 瘦 deb 分发（依赖缺口安装即坏，见 [packaging.md](../../build/packaging.md)）

---

## 八、风险与缓解

| 风险 | 缓解 |
|------|------|
| 外部书源崩溃 | `httpx.TimeoutException` → 跳过该章，error 记录 |
| 端口冲突 | 启动失败 → warning 日志，不影响其他书源 |
| 序列化不一致 | 与现有 `models/*.loads()` 对齐 JSON schema |
| 调试困难（分布式追踪） | 每个 HTTP 调用自动附加 `X-Request-ID` 头 |
| 性能回退（HTTP 开销） | localhost HTTP ~1-3ms，网站请求 ~200-2000ms，占比 <1% |

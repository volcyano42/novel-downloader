# Playwright 替换 DrissionPage 设计

> 日期：2026-08-16
> 状态：已确认（待实施）

## 1. 背景与目标

BrowserEngine 当前基于 **DrissionPage**（同步库）实现，`async_fetch_text/json` 靠 `asyncio.to_thread` 包装同步方法（假异步）。在全链路异步化（见 `2026-08-13-source-async-design.md`）后，BrowserEngine 成为三引擎中**唯一无法真异步**的一环：

| 引擎 | 异步实现 | 纯度 |
|------|---------|------|
| RequestsEngine | `await client.get()`（httpx 真异步） | ⭐⭐⭐ |
| APIEngine | `await client.get()`（httpx 真异步） | ⭐⭐⭐ |
| **BrowserEngine** | `await asyncio.to_thread(self.fetch_text)` | ⭐ 假异步 |

**目标**：用 **Playwright** 替换 DrissionPage，让 BrowserEngine 获得原生 async API，消除 to_thread 假异步；同时覆盖 Linux 无图形界面（服务器/CI/容器）的支持方案。

**额外收益**：`AGENTS.md:36` 一直写着引擎模式为 `browser（Playwright）`，而代码实际用 DrissionPage——替换使文档与实现归位。

## 2. 现状盘点

DrissionPage 依赖点共 **3 处代码 + 2 处依赖声明 + 4 处排除项**：

| 类别 | 位置 | 内容 |
|------|------|------|
| 代码 | `novelbase/core/engine.py:253` | `from DrissionPage import Chromium, ChromiumOptions`（BrowserEngine 唯一真依赖） |
| 代码 | `novelbase/sources/qidian/browser/search.py` | 翻页交互（`new_page/get/ele/click/html/close`，to_thread 包装） |
| 代码 | `novelbase/sources/qimao/browser/chapter_list.py` | 目录点击交互（`new_page/get/ele/click/wait/html/close`，to_thread 包装） |
| 依赖 | `pyproject.toml:17` | `drissionpage` |
| 依赖 | `requirements.txt:2` | `drissionpage` |
| 排除 | `.github/workflows/build-linux-arm64-termux.yml:54` | `grep -v "^drissionpage"` |
| 排除 | `android/app/build.gradle.kts:50` | `exclude("drissionpage")` |
| 排除 | `scripts/build-portable.sh:181` | `grep -v '^drissionpage'` |
| 排除 | `scripts/termux-preinstall.sh:41` | `grep -v "^drissionpage"` |

交互 API 面很窄（两个书源各 5-7 行），迁移复杂度低。当前两书源已把整段交互包进 `asyncio.to_thread`——换 Playwright 后可直接 `await`，去掉线程池包装。

## 3. 设计决策

### 3.1 原生 async 取代 to_thread

BrowserEngine 的 `async_fetch_text/json` 从 `asyncio.to_thread(self.fetch_text)` 改为直接 `await` Playwright 的 async API：

```python
# 改后（示意）
async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs):
    page = await self._get_page()
    try:
        await page.goto(url, timeout=self.options.timeout)
        html = await page.content()
    finally:
        await page.close()
    ...
```

### 3.2 页面生命周期模型

DrissionPage 现在是 `_thread_local` + `_page_pool`（线程独占页面）。Playwright 的模型是 `Browser → BrowserContext → Page`：

- **Browser**：`async_playwright().start()` 启动，BrowserEngine 生命周期内持有一个（chromium 类型）。
- **BrowserContext**：持有 cookie/登录态，Engine 持有一个默认 context。
- **Page**：每次请求 `await context.new_page()`，用完 `await page.close()`（不复用 page，避免状态串扰；context 复用保留 cookie）。

并发模型：Playwright 原生支持单 Browser + 多 Page 并发，无需 `_page_pool`/`_thread_local`，也无需 `_page_lock`。

### 3.3 统一内置 chromium（不依赖系统 Chrome）

**统一使用 `playwright install chromium` 内置浏览器**，不依赖系统 Chrome（去掉 channel="chrome" 分支，保持简单）：

- 版本锁定：内置 chromium 与 Playwright 版本绑定，行为可预测（反爬对抗时浏览器指纹/行为一致）。
- 部署可重复：`playwright install chromium` 一条命令，桌面/服务器/CI 全场景一致。
- 代价：下载 150-300MB 浏览器二进制到用户缓存目录（`~/.cache/ms-playwright/`），不进便携包。

BrowserEngine 启动参数通过 `BrowserOptions` 扩展 `headless` / `browser_args` 字段（无需 `channel`）。

### 3.4 错误处理与重试

保留现有重试语义（`retry_times` + 指数退避），退避从 `time.sleep` 改 `await asyncio.sleep`。新增 Playwright 特有异常映射：

- `TimeoutError`（导航超时）→ `NetworkError`
- `Error`（浏览器崩溃/关闭）→ `NetworkError`

## 4. Linux 无图形界面支持（专节）

Linux 服务器/CI/容器无图形界面，统一通过内置 chromium + headless 支持：

### 4.1 浏览器安装

```bash
# 下载 chromium 二进制 + 安装系统依赖（libnss3/libatk/libgbm 等，需 root）
playwright install --with-deps chromium
```

`--with-deps` 自动识别发行版装系统依赖，**不要手列 apt 包**（清单随发行版演进）。

### 4.2 各环境落地方式

| 环境 | 方案 |
|------|------|
| CI（ubuntu-latest） | `playwright install --with-deps chromium` 一步到位 |
| Docker 容器 | Dockerfile `RUN playwright install --with-deps chromium`；以 root 运行时 launch 加 `--no-sandbox` |
| 裸服务器（有 root） | `playwright install --with-deps chromium` |
| 桌面（Windows/Linux） | 同样 `playwright install chromium`（统一，不特判系统 Chrome） |

### 4.3 启动参数

无头环境 `headless=True`（Playwright 默认 headless）。**root 用户必须 `--no-sandbox`**（Chromium 沙箱在 root 下报错），通过 `browser_args` 传入：

```python
# Linux 无头 + root 场景
BrowserOptions(headless=True, browser_args=["--no-sandbox", "--disable-dev-shm-usage"])
```

`--disable-dev-shm-usage` 解决容器 `/dev/shm` 过小导致崩溃（Docker 默认 64MB）。

### 4.4 与 DrissionPage 时代的差异

DrissionPage 时代"用户装 Chrome + 自动下载 chromedriver"（`build-portable.ps1:174,179`）。Playwright 时代改为统一的 `playwright install chromium`（显式、版本锁定、不依赖系统 Chrome/chromedriver）。

## 5. 分层改动清单

| 层 | 文件 | 改动 |
|----|------|------|
| engine | `novelbase/core/engine.py` | BrowserEngine：`_init_browser` 改 async_playwright；`fetch_text/json` 改 async 原生；`async_fetch_*` 去 to_thread；删 `_thread_local/_page_pool/_page_lock`；`close` 改 `await browser.close()` |
| options | `novelbase/core/options.py` | BrowserOptions 加 `browser_args` 字段（headless 已有） |
| 书源 | `novelbase/sources/qidian/browser/search.py` | 交互改 Playwright（`goto/locator.click/content`），去 to_thread |
| 书源 | `novelbase/sources/qimao/browser/chapter_list.py` | 交互改 Playwright（`goto/locator.click/wait_for_timeout/content`），去 to_thread |
| 依赖 | `pyproject.toml` / `requirements.txt` | `drissionpage` → `playwright` |
| 打包 | `scripts/build-portable.ps1/.sh` | Chrome 安装说明改 `playwright install chromium`；排除项 `drissionpage` → `playwright` |
| 排除 | `.github/workflows/build-linux-arm64-termux.yml` / `android/app/build.gradle.kts` / `scripts/termux-preinstall.sh` | 排除项 `drissionpage` → `playwright` |
| 文档 | `AGENTS.md:36` | 已写 browser(Playwright)，无需改（替换即归位） |

## 6. 测试

- BrowserEngine 单测：mock `async_playwright`，验证 `async_fetch_text` 直接 `await`（不再 to_thread）。
- 书源单测：qidian/qimao browser 书源 mock page 对象，验证 `goto/locator/content` 调用。
- Linux 无头验证：CI 里 `playwright install --with-deps chromium` + headless 跑通 browser 模式（现有 build-linux-*.yml 已含 arm64 原生 runner）。
- 现有 189 测试保持全绿（BrowserEngine 测试需同步改写）。

## 7. 不做的事

- 不改 Requests/API 引擎（已是真异步）。
- 不预置 chromium 进便携包（用户自行 `playwright install chromium`，浏览器二进制存用户缓存目录）。
- Termux/Android 不引入 Playwright（browser 模式仍排除，仅替换排除项名称）。
- 不实现书源浏览器指纹/反爬增强（后续独立议题）。

## 8. 风险

1. **Playwright 打包/Nuitka 兼容**：onefile 下 Playwright 的 driver 启动需验证（可能需要 `--include-package=playwright` 及 driver 文件）。DrissionPage 打包路径已验证可用。
2. **qidian/qimao 书源真实可用性**：两书源的 browser 交互可能已无实际书源在用（死代码），替换前需确认——若死代码可一并清理。
3. **行为差异**：DrissionPage 的 `page.html` 是"已渲染 DOM"；Playwright 的 `page.content()` 语义相近但加载时机需用 `wait_for_selector` 显式等待（qimao 的 `wait(3)` 需改 `wait_for_timeout` 或 `wait_for_selector`）。
4. **依赖体积**：`playwright` 包本身比 `drissionpage` 小，但 `playwright install chromium` 的浏览器二进制大（150-300MB，存用户缓存目录，不进便携包；首次运行需联网下载）。

## 9. 交叉引用

- 本文档取代 `2026-08-13-source-async-design.md` 中 BrowserEngine 的 `asyncio.to_thread` 方案（该文档 4.1 节 BrowserEngine async 实现方式），改为 Playwright 原生 async。
- `async_fetch_images` 仍按已确认的 **httpx** 方案（`2026-08-13-source-async-design.md` 4.1 节已定），图片下载不用浏览器。
- 全链路 async 目标不变；本文档只改 BrowserEngine 的"如何异步"，不改"异步化范围"。

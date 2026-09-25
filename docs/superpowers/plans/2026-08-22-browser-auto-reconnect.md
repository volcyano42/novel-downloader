# BrowserOptions.auto_reconnect 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `BrowserOptions.auto_reconnect`（默认 False）：browser 模式的持久浏览器意外关闭时自动重建浏览器实例并重试当前抓取，而非直接 `NetworkError`。

**Architecture:** `novelbase/core/options.py` 加字段 + `set_browser_options` 透传；`novelbase/core/engine.py` 的 `_fetch_with_page` 遇「浏览器失效」异常直接抛出（不重试死 page），`async_fetch_text` 外层在 `auto_reconnect=True` 时捕获该类异常 → `_reset_browser()`（容错清理 + 清 page 池）→ `_ensure_browser()` 重建 → 重试（次数复用 `retry_times`）。同步 `fetch_text`（独立会话）与 `auto_reconnect=False` 行为不变。

**Tech Stack:** Python 3.13、Playwright、pytest。

**Spec:** `docs/superpowers/specs/2026-08-22-browser-auto-reconnect-design.md`

## Global Constraints

- `BrowserOptions.auto_reconnect: bool = False`（默认关，零退化）
- 仅「浏览器失效」类异常触发重建：Playwright `TargetClosedError` / `PlaywrightConnectionError` / 消息含 `browser`+`closed` 特征；普通超时/网络错不触发
- 重建走 `_ensure_browser()`（含 `_launch_lock` 并发保护），重建前 `_reset_browser()` 容错 close `_playwright`/`_browser`/`_context` 并清空 `_idle_pages`
- 重建重试次数复用 `retry_times`（默认 3），仍失败抛 `NetworkError`（不无限重试）
- 同步 `fetch_text`（isolated session 自启自停）不重建；`auto_reconnect=False` 行为与现状完全一致
- 测试命令：`python -m pytest tests/ -v --tb=short`
- git：commit 消息中文、显式 `git add <files>`、dev 分支可提交推送；若 `.git/hooks/pre-commit` 无法 spawn，用 `git commit --no-verify`

---

### Task 1: BrowserOptions 字段 + set_browser_options 透传

**Files:**
- Modify: `novelbase/core/options.py:28-37, 93-107`
- Test: `tests/test_options.py`

**Interfaces:**
- Consumes: 无
- Produces: `BrowserOptions.auto_reconnect: bool = False`；`Options.set_browser_options(..., auto_reconnect: bool = False)` 透传

- [ ] **Step 1: Write the failing test**

在 `tests/test_options.py` 追加两个用例：

```python
    def test_browser_options_auto_reconnect_default_false(self):
        b = BrowserOptions()
        assert b.auto_reconnect is False

    def test_set_browser_options_auto_reconnect(self):
        o = Options().set_browser_options(auto_reconnect=True)
        assert o.browser.auto_reconnect is True
```

（文件顶部需 `from novelbase.core.options import BrowserOptions`，若未导入则补 import。）

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_options.py -v --tb=short`
Expected: FAIL（`BrowserOptions` 无 `auto_reconnect` 属性 / `set_browser_options` 不接受该参数）

- [ ] **Step 3: Write minimal implementation**

`novelbase/core/options.py`：

```python
@dataclass
class BrowserOptions:
    browser_type: str = "chromium"
    delay: tuple[float, ...] = field(default_factory=lambda: (3.0, 5.0))
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    headless: bool = False
    user_data_dir: Path | str | None = None
    viewport: dict[str, int] | None = None
    extra_args: list[str] | None = None
    auto_reconnect: bool = False   # 浏览器意外关闭时自动重建并重试
```

`set_browser_options` 签名加 `auto_reconnect: bool = False`，构造 `BrowserOptions(...)` 时透传（`auto_reconnect=auto_reconnect`）。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_options.py -v --tb=short`
Expected: 新用例 PASS，既有用例不受影响

- [ ] **Step 5: Commit**

```bash
git add novelbase/core/options.py tests/test_options.py
git commit -m "feat: BrowserOptions 新增 auto_reconnect 字段（默认 False）"
```

---

### Task 2: BrowserEngine 重建逻辑

**Files:**
- Modify: `novelbase/core/engine.py:350-374, 390-394`
- Test: `tests/test_engine_reconnect.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `BrowserOptions.auto_reconnect`
- Produces:
  - `BrowserEngine._is_reconnectable_error(e) -> bool`（静态方法）
  - `BrowserEngine._reset_browser() -> None`（async）
  - `BrowserEngine._reconnect_browser() -> None`（async）
  - `async_fetch_text` 在 `auto_reconnect=True` 时重建重试

- [ ] **Step 1: Write the failing test**

创建 `tests/test_engine_reconnect.py`，参考 `tests/test_engine_httpx.py` 的 FakePlaywright 模式：

```python
"""BrowserEngine.auto_reconnect 重建逻辑测试。"""
import asyncio

import pytest

from novelbase.core.engine import BrowserEngine
from novelbase.core.exceptions import NetworkError
from novelbase.core.options import BrowserOptions


class FakePlaywright:
    """mock playwright：首轮 goto 抛浏览器失效异常，重建后成功。"""

    def __init__(self, monkeypatch):
        self.calls = []
        self.launch_count = 0
        self.fail_first_batch = False
        self._install(monkeypatch)

    def _install(self, monkeypatch):
        fake = self

        class FakePage:
            async def goto(self, url, timeout=None):
                fake.calls.append(("goto", url))
                if fake.fail_first_batch:
                    fake.fail_first_batch = False
                    raise RuntimeError("TargetClosedError: browser has been closed")
            async def content(self):
                fake.calls.append(("content",))
                return "<html>ok</html>"
            async def close(self):
                fake.calls.append(("page_close",))

        class FakeContext:
            def __init__(self):
                self.browser = FakeBrowser()
            async def new_page(self):
                fake.calls.append(("new_page",))
                return FakePage()
            async def close(self):
                fake.calls.append(("context_close",))

        class FakeBrowser:
            async def new_context(self, viewport=None):
                fake.calls.append(("new_context", viewport))
                return FakeContext()
            async def new_page(self):
                fake.calls.append(("new_page",))
                return FakePage()
            async def close(self):
                fake.calls.append(("browser_close",))

        class FakeChromium:
            async def launch(self, headless=True, args=None):
                fake.launch_count += 1
                fake.calls.append(("launch", headless))
                return FakeBrowser()

        class FakePW:
            def __init__(self):
                self.chromium = FakeChromium()
            async def start(self):
                return self
            async def stop(self):
                fake.calls.append(("pw_stop",))

        import novelbase.core.engine as eng
        monkeypatch.setattr(eng, "_async_playwright", lambda: FakePW())


def _engine(auto_reconnect: bool):
    return BrowserEngine(BrowserOptions(delay=(0, 0), headless=True,
                                        retry_times=3, auto_reconnect=auto_reconnect))


def test_reconnect_recovers_after_browser_closed(monkeypatch):
    """auto_reconnect=True：浏览器失效 → 重建 → 成功（launch 两次）。"""
    fake = FakePlaywright(monkeypatch)
    fake.fail_first_batch = True
    engine = _engine(auto_reconnect=True)
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    assert fake.launch_count == 2, f"应重建一次，实际 launch {fake.launch_count} 次"
    assert any(c[0] == "browser_close" for c in fake.calls)  # 旧浏览器被清理
    engine.close()


def test_no_reconnect_when_disabled(monkeypatch):
    """auto_reconnect=False：不重建，最终 NetworkError。"""
    fake = FakePlaywright(monkeypatch)
    fake.fail_first_batch = True
    engine = _engine(auto_reconnect=False)
    with pytest.raises(NetworkError):
        asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert fake.launch_count == 1, "auto_reconnect=False 不应重建"
    engine.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine_reconnect.py -v --tb=short`
Expected: FAIL（`_is_reconnectable_error` 不存在；`auto_reconnect` 时不会重建）

- [ ] **Step 3: Write minimal implementation**

`novelbase/core/engine.py` 新增三个方法并接入：

```python
    @staticmethod
    def _is_reconnectable_error(e: Exception) -> bool:
        """判定异常是否为「浏览器失效」类（仅此类触发自动重建）。"""
        msg = str(e).lower()
        name = type(e).__name__
        if name in ("TargetClosedError", "PlaywrightConnectionError", "BrowserClosedError"):
            return True
        return "browser" in msg and "closed" in msg

    async def _reset_browser(self) -> None:
        """容错清理残留浏览器/上下文/playwright，并清空 page 池。"""
        for obj in (self._playwright, self._browser, self._context):
            if obj is None:
                continue
            try:
                if hasattr(obj, "close"):
                    await obj.close()
            except Exception:
                pass
        self._playwright = None
        self._browser = None
        self._context = None
        self._idle_pages.clear()

    async def _reconnect_browser(self) -> None:
        """重建浏览器实例（重置后走 _ensure_browser 懒启动路径）。"""
        await self._reset_browser()
        await self._ensure_browser()
```

`_fetch_with_page` 重试循环的 except 分支改为：浏览器失效异常直接抛给上层（page 已死，继续重试无意义）：

```python
            except Exception as e:
                if self.options.auto_reconnect and self._is_reconnectable_error(e):
                    raise  # 浏览器失效 → 交给 async_fetch_text 层重建
                backoff = self.options.backoff_factor * (2 ** i)
                _log.debug("fetch_text attempt %s failed: %s; backoff %.1fs",
                           i + 1, e, backoff)
                await asyncio.sleep(backoff)
```

`async_fetch_text` 改为重建级重试：

```python
    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        """真异步：直接 await Playwright（不 to_thread）；浏览器失效时按 auto_reconnect 重建。"""
        _log.debug("async_fetch_text start: url=%s", mask_key(url[:120]))
        await self._ensure_browser()
        for attempt in range(self.options.retry_times):
            try:
                return await self._do_fetch_text(url, skip_delay=skip_delay, **kwargs)
            except Exception as e:
                if not (self.options.auto_reconnect and self._is_reconnectable_error(e)):
                    raise
                _log.warning("浏览器失效(%s)，重建浏览器后重试 %s/%s: url=%s",
                             e, attempt + 1, self.options.retry_times, mask_key(url[:120]))
                await self._reconnect_browser()
        _log.error("fetch_text exhausted reconnects: url=%s", mask_key(url[:120]))
        raise NetworkError(
            f"fetch_text failed after {self.options.retry_times} reconnects",
            url=url,
        )
```

（确认 `BrowserEngine.__init__` 已初始化 `_idle_pages`；若未初始化则补 `self._idle_pages: list = []`。）

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine_reconnect.py tests/test_engine_httpx.py -v --tb=short`
Expected: 新用例 PASS；既有 BrowserEngine 测试不受影响（`auto_reconnect` 默认 False，行为不变）

- [ ] **Step 5: Run full suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS（含既有 BrowserEngine 用例）

- [ ] **Step 6: Commit**

```bash
git add novelbase/core/engine.py tests/test_engine_reconnect.py
git commit -m "feat: BrowserEngine 支持浏览器失效自动重建（auto_reconnect）"
```

---

### Task 3: 配置透传（engine_manager / cli / schemas）

**Files:**
- Modify: `backend/services/engine_manager.py:150-160, 195-203`
- Modify: `cli/config.py:210-220`
- Modify: `backend/schemas/engine.py:25-33`
- Test: `tests/test_engine_manager.py`

**Interfaces:**
- Consumes: Task 1 的 `set_browser_options(auto_reconnect=...)`
- Produces: sites yaml `auto_reconnect` 配置与显式引擎 API 均可设置该字段

- [ ] **Step 1: schemas**

`backend/schemas/engine.py` 的 `BrowserOptionsData` 追加：

```python
    extra_args: list[str] | None = None
    auto_reconnect: bool = False
```

- [ ] **Step 2: engine_manager 两处透传**

`backend/services/engine_manager.py`：

`create_engine_for_request` 的 browser 分支 `set_browser_options(...)` 追加：

```python
            auto_reconnect=_cfg("auto_reconnect", False),
```

`_build_options` 的 browser 分支 `set_browser_options(...)` 追加：

```python
            auto_reconnect=b.auto_reconnect if hasattr(b, "auto_reconnect") else False,
```

- [ ] **Step 3: cli 透传**

`cli/config.py` 的 browser 分支 `set_browser_options(...)` 追加：

```python
            auto_reconnect=browser_cfg.get("auto_reconnect", False),
```

- [ ] **Step 4: 测试**

`tests/test_engine_manager.py` 若已有 browser options 构建测试，追加断言 `auto_reconnect` 透传（sites yaml 设 `auto_reconnect: true` → engine 的 `options.browser.auto_reconnect is True`）；若无合适挂点，在 `tests/test_engine_manager.py` 新增最小用例验证 `_build_options` 透传：

```python
def test_build_options_passes_auto_reconnect():
    from backend.services.engine_manager import _build_options
    from backend.schemas.engine import BrowserOptionsData
    b = BrowserOptionsData(auto_reconnect=True)
    opts = _build_options("browser", browser=b)
    assert opts.browser.auto_reconnect is True
```

（若 `_build_options` 未从 engine_manager 顶层导出，用 `from backend.services import engine_manager` 后访问。）

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_engine_manager.py tests/test_options.py -v --tb=short`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/engine_manager.py backend/schemas/engine.py cli/config.py tests/test_engine_manager.py
git commit -m "feat: auto_reconnect 配置透传（sites yaml + 显式引擎 API + CLI）"
```

---

## Self-Review 结果

- **Spec 覆盖**：字段+透传（Task 1）、BrowserEngine 重建机制含检测/重置/重建/接入（Task 2）、配置透传三处（Task 3）、测试（各 Task 内嵌）——spec 各节均有对应任务。
- **占位符**：无 TBD/TODO；每步给出完整代码或精确改动位置。
- **类型一致性**：`_is_reconnectable_error(e)` / `_reset_browser()` / `_reconnect_browser()` 在 Task 2 定义并被同 Task 接入引用；`set_browser_options(auto_reconnect=...)` Task 1 定义、Task 3 三处调用签名一致；`BrowserOptionsData.auto_reconnect` Task 3 定义并被 `_build_options` 消费。

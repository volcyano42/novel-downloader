# BrowserOptions.auto_reconnect 设计文档

**日期**: 2026-08-22
**状态**: 已确认，待实施

---

## 一、动机

browser 模式使用懒启动的持久 Playwright 浏览器（`BrowserEngine` 持有 `_playwright`/`_browser`/`_context`）。当浏览器窗口意外关闭（用户手关 / 崩溃 / 杀进程）后：

- `_browser`/`_context` 变为死对象，后续 `_acquire_page()` / `page.goto()` 持续抛错
- 现有重试循环每次仍从死的 context 借 page，全部失败后抛 `NetworkError`
- **不会自动重建浏览器**，需重启进程才恢复

目标：新增 `BrowserOptions.auto_reconnect` 选项，开启后浏览器意外关闭时自动重建浏览器实例并重试当前抓取。

## 二、字段定义

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
    auto_reconnect: bool = False   # 新增：浏览器意外关闭时自动重建并重试
```

默认 `False`：行为与现状完全一致（零退化）。`Options.set_browser_options()` 增加同名透传参数。

## 三、BrowserEngine 重建机制（novelbase/core/engine.py）

新增三个方法 + 一处接入：

### 3.1 `_is_reconnectable_error(e) -> bool`（静态方法）

判定异常是否为「浏览器失效」类，仅这类异常触发重建：
- `playwright` 的 `TargetClosedError`、`PlaywrightConnectionError`
- 其他异常消息含 `"browser"` + `"closed"` / `"Target page"` 等特征

普通超时、网络错误、页面内容解析失败**不**触发重建。

### 3.2 `_reset_browser()`

容错清理残留实例并置 None：
- `_playwright` / `_browser` / `_context` 各自 try/except close 后置 None
- **清空 page 池** `_idle_pages`（池内缓存的旧 page 已随浏览器死亡而失效）

### 3.3 `_reconnect_browser()`

```python
await self._reset_browser()
await self._ensure_browser()   # 重建全新浏览器实例
```

### 3.4 接入 `_do_fetch_text`（重建级重试）

```
重试循环（次数 = retry_times）：
    try:
        page = await self._acquire_page()
        result = await self._fetch_with_page(page, ...)
    except 浏览器失效异常 and auto_reconnect:
        await self._reconnect_browser()   # 重建后继续循环
    except 其他异常:
        close page（不归还）并继续循环
    成功 → release page / 失败全部重试 → NetworkError
```

重建重试次数复用 `retry_times`（默认 3），重建后仍失败则照旧抛 `NetworkError`（不无限重试）。`auto_reconnect=False` 时逻辑与现状等价。

## 四、配置透传

`auto_reconnect` 需可从 sites yaml / 显式引擎 API 配置：

| 位置 | 改动 |
|---|---|
| `novelbase/core/options.py` | `BrowserOptions` 字段 + `set_browser_options(..., auto_reconnect=False)` |
| `backend/services/engine_manager.py` `create_engine_for_request` | `set_browser_options(auto_reconnect=_cfg("auto_reconnect", False))` |
| `backend/services/engine_manager.py` `_build_options` | 从 `browser.auto_reconnect` 透传 |
| `cli/config.py` | `set_browser_options(auto_reconnect=browser_cfg.get("auto_reconnect", False))` |
| `backend/schemas/engine.py` | `BrowserOptionsData.auto_reconnect: bool = False` |

## 五、边界

- 只影响**懒启动的持久 browser**（async 路径，后端实际场景）；同步 `fetch_text` 走独立会话（每次自启自停），无需重建
- `auto_reconnect=False`（默认）行为不变
- 重建后失败 → `NetworkError`（不无限重试）
- 与 `_ensure_browser` 的并发锁（`_launch_lock`）兼容：重建走同一 `_ensure_browser` 路径

## 六、测试

- `tests/test_options.py`：`auto_reconnect` 字段默认值与 `set_browser_options` 透传
- `tests/test_engine_browser.py`（新增）：mock playwright——`_fetch_with_page` 抛浏览器失效异常时，`auto_reconnect=True` 触发重建并最终成功；`auto_reconnect=False` 不重建照旧失败；非失效异常不触发重建
- 现有全量回归

## 七、影响文件清单

```
novelbase/core/options.py              字段 + set_browser_options 透传
novelbase/core/engine.py               _is_reconnectable_error / _reset_browser / _reconnect_browser + _do_fetch_text 接入
backend/services/engine_manager.py     两处 set_browser_options 透传
backend/schemas/engine.py              BrowserOptionsData.auto_reconnect
cli/config.py                          透传
tests/test_options.py                  字段测试
tests/test_engine_browser.py（新）      重建逻辑测试
```

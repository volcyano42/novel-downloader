# 还原交互式 CLI（main.py）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 还原 2026-08-02 删除的交互式 CLI（根目录 `main.py` 入口 + 菜单式操作），适配 novelbase 全部 API 变更，去掉全部 box-drawing 装饰字符。

**Architecture:** 根目录新建 `main.py` 入口，交互层并入现有 `cli/` 包（新增 `interactive.py`/`menus.py`/`ui.py`/`notify.py`），复用现有 `cli/core.py`（async 下载/更新核心）与 `cli/config.py`（配置加载）零改动。交互主循环为同步，所有 async 调用经 `asyncio.run()` 包装。

**Tech Stack:** Python 3.10+、novelbase（async 下载器）、rich（进度条，仅 `cli/ui.py`）、yaml（配置）。

## Global Constraints

- 测试运行命令（本机无 Python，用 Docker 镜像 `nld-test:3.11`，Git Bash 需 `MSYS_NO_PATHCONV=1`）：
  `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest <args>`
- **零改动**：`cli/main.py`、`cli/core.py`、`cli/config.py` 三个文件一律不修改
- 交互式入口 `main.py` 放在**仓库根目录**（与旧版一致）
- 全部 box-drawing 装饰字符（`┌┐│├┤└┘─`）不得出现在新文件中（rich 进度条的 `█` 块字符除外）
- `id_pattern`/ID 反查机制已退役：不实现 `_build_url_from_id`，不做 hash id 反查
- Git 提交消息用中文；`git add` 显式指定文件，禁止 `git add -A`
- 本机无 Python，禁止 `python`/`py`/`pytest` 直接执行；验证一律走 Docker 或用户手动

---

### Task 1: cli/ui.py — 交互辅助层

**Files:**
- Create: `cli/ui.py`
- Test: `tests/test_interactive_cli.py`（本任务只写 `TestUi` 类）

**Interfaces:**
- Consumes: `novelbase.source.register_source()`（返回 `dict[str, dict]`，每项含 `show_name`）、`rich`（进度条）、`novelbase.utils.logger.get_logger`
- Produces:
  - `_select(message: str, choices: list[tuple[str, Any]] | dict[str, Any]) -> Any` — 编号菜单选择，`q`/EOF 返回 None
  - `_text_input(message: str) -> str | None` — 文本输入，空/EOF 返回 None
  - `_input_int(prompt: str, default: int) -> int` / `_input_float(prompt: str, default: float) -> float` — 带默认值数字输入
  - `_show_platforms() -> dict[str, str]` — `{显示标签: 内部名}`，动态发现注册 source
  - `_platform_label(labels: dict[str, str], name: str) -> str` — 内部名 → 显示标签
  - `_create_progress(total: int) -> tuple` / `_advance_progress(progress, task, advance=1, last_title="")` — rich 进度条
  - `parse_order_string(s: str, total: int) -> list[int]` — 解析章节范围 `'1-10,20,30-'`，返回 0 基索引排序去重列表

- [ ] **Step 1: 写失败测试** `tests/test_interactive_cli.py`

```python
# -*- coding: utf-8 -*-
"""交互式 CLI（cli/ui.py、cli/notify.py、cli/interactive.py）测试。"""
from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════
# cli.ui 交互辅助层
# ═══════════════════════════════════════════════════════════════

class TestUi:
    def test_parse_order_string_simple(self):
        from cli.ui import parse_order_string
        assert parse_order_string("1,2,3", 10) == [0, 1, 2]

    def test_parse_order_string_range(self):
        from cli.ui import parse_order_string
        assert parse_order_string("1-3", 10) == [0, 1, 2]

    def test_parse_order_string_open_end(self):
        from cli.ui import parse_order_string
        assert parse_order_string("8-", 10) == [7, 8, 9]

    def test_parse_order_string_open_start(self):
        from cli.ui import parse_order_string
        assert parse_order_string("-3", 10) == [0, 1, 2]

    def test_parse_order_string_mixed_dedup_sorted(self):
        from cli.ui import parse_order_string
        assert parse_order_string("3,1-2,5,5", 10) == [0, 1, 2, 4]

    def test_parse_order_string_empty(self):
        from cli.ui import parse_order_string
        assert parse_order_string("", 10) == []
        assert parse_order_string(" , ,", 10) == []

    def test_parse_order_string_clamped(self):
        from cli.ui import parse_order_string
        assert parse_order_string("1-99", 5) == [0, 1, 2, 3, 4]

    def test_select_dict(self, monkeypatch, capsys):
        from cli.ui import _select
        monkeypatch.setattr("builtins.input", lambda _: "2")
        assert _select("选一个", {"A": 1, "B": 2}) == 2

    def test_select_list_quit(self, monkeypatch):
        from cli.ui import _select
        monkeypatch.setattr("builtins.input", lambda _: "q")
        assert _select("选一个", [("A", 1), ("B", 2)]) is None

    def test_select_invalid_then_valid(self, monkeypatch, capsys):
        from cli.ui import _select
        inputs = iter(["abc", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        assert _select("选一个", [("A", 1), ("B", 2)]) == 1
        assert "输入错误" in capsys.readouterr().out

    def test_select_eof(self, monkeypatch):
        from cli.ui import _select
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        assert _select("选一个", [("A", 1)]) is None

    def test_text_input_value(self, monkeypatch):
        from cli.ui import _text_input
        monkeypatch.setattr("builtins.input", lambda _: "hello")
        assert _text_input("输入") == "hello"

    def test_text_input_blank(self, monkeypatch):
        from cli.ui import _text_input
        monkeypatch.setattr("builtins.input", lambda _: "   ")
        assert _text_input("输入") is None

    def test_text_input_eof(self, monkeypatch):
        from cli.ui import _text_input
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        assert _text_input("输入") is None

    def test_input_int_default_on_blank(self, monkeypatch):
        from cli.ui import _input_int
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _input_int("线程", 3) == 3

    def test_input_int_value(self, monkeypatch):
        from cli.ui import _input_int
        monkeypatch.setattr("builtins.input", lambda _: "5")
        assert _input_int("线程", 3) == 5

    def test_input_int_invalid(self, monkeypatch, capsys):
        from cli.ui import _input_int
        monkeypatch.setattr("builtins.input", lambda _: "abc")
        assert _input_int("线程", 3) == 3

    def test_input_float_value(self, monkeypatch):
        from cli.ui import _input_float
        monkeypatch.setattr("builtins.input", lambda _: "2.5")
        assert _input_float("延迟", 3.0) == 2.5

    def test_show_platforms(self, monkeypatch):
        from cli.ui import _show_platforms
        import novelbase.source as src_mod
        fake = {
            "fanqie": {"name": "fanqie", "show_name": "番茄", "hosts": ("fanqienovel.com",)},
            "qidian": {"name": "qidian", "show_name": "起点", "hosts": ("qidian.com",)},
        }
        monkeypatch.setattr(src_mod, "register_source", lambda: fake)
        labels = _show_platforms()
        assert labels == {"番茄 (fanqie)": "fanqie", "起点 (qidian)": "qidian"}

    def test_platform_label(self):
        from cli.ui import _platform_label
        labels = {"番茄 (fanqie)": "fanqie"}
        assert _platform_label(labels, "fanqie") == "番茄 (fanqie)"
        assert _platform_label(labels, "unknown") == "unknown"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'cli.ui'`）

- [ ] **Step 3: 写最小实现** `cli/ui.py`

```python
# -*- coding: utf-8 -*-
"""交互式 UI 辅助：菜单选择、文本输入、进度条、平台信息。"""

from __future__ import annotations

import sys
import unicodedata
from typing import Any

from novelbase.utils.logger import get_logger

_log = get_logger("cli.ui")


def _select(message: str, choices: list[tuple[str, Any]] | dict[str, Any]) -> Any:
    """显示编号菜单，返回选中值。choices 为 (label, value) 列表或 {label: value} 字典。q 或 EOF 返回 None。"""
    if isinstance(choices, dict):
        items = list(choices.items())
    else:
        items = list(choices)

    print(f"\n{message}")
    for i, (label, _) in enumerate(items, 1):
        print(f"  {i}. {label}")

    while True:
        try:
            raw = input("请输入数字 (q 退出): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw.lower() == "q":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx][1]
        except ValueError:
            pass
        print("输入错误，请重新输入")


def _text_input(message: str) -> str | None:
    """获取文本输入。空或 EOF 返回 None。"""
    try:
        return input(f"{message}: ").strip() or None
    except UnicodeDecodeError:
        try:
            sys.stdin.reconfigure(encoding="utf-8")
            return input(f"{message}: ").strip() or None
        except (UnicodeDecodeError, OSError):
            return None
    except (EOFError, KeyboardInterrupt):
        return None


def _input_int(prompt: str, default: int) -> int:
    """带默认值的整数输入。"""
    try:
        raw = input(f"{prompt} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("请输入数字")
        return default


def _input_float(prompt: str, default: float) -> float:
    """带默认值的浮点输入。"""
    try:
        raw = input(f"{prompt} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("请输入数字")
        return default


def _show_platforms() -> dict[str, str]:
    """返回 {显示标签: 内部名} 的平台映射，动态发现注册 source。"""
    try:
        from novelbase.source import register_source
        sources = register_source()
        return {f"{info.get('show_name', k)} ({k})": k for k, info in sources.items()}
    except Exception:
        return {}


def _platform_label(platform_labels: dict[str, str], name: str) -> str:
    """内部名 → 显示标签。"""
    rev = {v: k for k, v in platform_labels.items()}
    return rev.get(name, name)


def _create_progress(total: int):
    """创建 rich 进度条。"""
    from rich.console import Console
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    console = Console(stderr=True)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
    task = progress.add_task("[cyan]下载中...", total=total)
    return progress, task


def _advance_progress(progress, task, advance: int = 1, last_title: str = ""):
    """更新进度条。"""
    if last_title:
        progress.update(task, description=f"[cyan]{last_title[:40]}")
    progress.advance(task, advance)


def parse_order_string(s: str, total: int) -> list[int]:
    """解析章节范围字符串。格式: '1-10,20,30-'。返回 0 基索引、排序去重。"""
    result: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a.strip()) if a.strip() else 0
            end = int(b.strip()) if b.strip() else total
            result.extend(range(max(0, start - 1), min(total, end)))
        else:
            result.append(int(part) - 1)
    return sorted(set(result))
```

> 注：旧版 `_display_width`/`_pad_right`/`_pad_center` 是主菜单方框对齐专用，去方框后无调用者，按 YAGNI 不还原。

- [ ] **Step 4: 运行测试确认通过**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestUi -q`
Expected: PASS（17 passed）

- [ ] **Step 5: Commit**

```bash
git add cli/ui.py tests/test_interactive_cli.py
git commit -m "feat: 还原交互式 CLI 辅助层 cli/ui.py（去 box-drawing、无 ID 反查）"
```

---

### Task 2: cli/notify.py — 通知模块

**Files:**
- Create: `cli/notify.py`
- Test: `tests/test_interactive_cli.py`（追加 `TestNotify` 类）

**Interfaces:**
- Consumes: `novelbase.utils.logger.get_logger`
- Produces:
  - `bell(count: int = 1, interval: float = 0.15)` — 终端响铃
  - `system_notify(title: str, body: str = "")` — Windows 原生通知（PowerShell），失败回退响铃
  - `notify(config: dict, complete: int = 0, incomplete: int = 0)` — 按配置分发；`config` 键：`sound`（`"bell"|"system"|"none"`）、`on_complete`、`on_incomplete`；`config` 为空返回

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_interactive_cli.py`）

```python
# ═══════════════════════════════════════════════════════════════
# cli.notify 通知模块
# ═══════════════════════════════════════════════════════════════

class TestNotify:
    def test_notify_empty_config(self, monkeypatch):
        from cli import notify as mod
        monkeypatch.setattr(mod, "bell", lambda *a, **k: None)
        monkeypatch.setattr(mod, "system_notify", lambda *a, **k: None)
        mod.notify({}, complete=1, incomplete=1)  # 不抛异常即通过

    def test_notify_sound_none(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda *a, **k: calls.append("bell"))
        monkeypatch.setattr(mod, "system_notify", lambda *a, **k: calls.append("system"))
        mod.notify({"sound": "none"}, complete=1, incomplete=1)
        assert calls == []

    def test_notify_bell_on_complete(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda count=1, interval=0.15: calls.append(("bell", count)))
        monkeypatch.setattr(mod, "system_notify", lambda *a, **k: calls.append("system"))
        mod.notify({"sound": "bell"}, complete=2, incomplete=0)
        assert calls == [("bell", 1)]

    def test_notify_system_on_incomplete(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda *a, **k: calls.append("bell"))
        monkeypatch.setattr(mod, "system_notify", lambda title, body="": calls.append(("system", title, body)))
        mod.notify({"sound": "system"}, complete=0, incomplete=3)
        assert calls[0][0] == "system"
        assert "不完整章节" in calls[0][2]

    def test_notify_disabled_flags(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda *a, **k: calls.append("bell"))
        mod.notify({"sound": "bell", "on_complete": False, "on_incomplete": False},
                   complete=1, incomplete=1)
        assert calls == []

    def test_system_notify_fallback_bell(self, monkeypatch):
        from cli import notify as mod
        import subprocess
        calls = []
        def boom(*a, **k):
            raise Exception("powershell 不可用")
        monkeypatch.setattr(subprocess, "run", boom)
        monkeypatch.setattr(mod, "bell", lambda count=1, interval=0.15: calls.append(count))
        mod.system_notify("标题")
        assert calls == [1]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestNotify -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'cli.notify'`）

- [ ] **Step 3: 写最小实现** `cli/notify.py`

```python
# -*- coding: utf-8 -*-
"""通知模块：终端响铃 + Windows 系统通知。"""

from __future__ import annotations

import subprocess

from novelbase.utils.logger import get_logger

_log = get_logger("cli.notify")

DEFAULT_SOUND = "bell"
DEFAULT_ON_COMPLETE = True
DEFAULT_ON_INCOMPLETE = True


def bell(count: int = 1, interval: float = 0.15):
    """终端响铃 count 次，间隔 interval 秒。"""
    import time
    for i in range(count):
        print("\a", end="", flush=True)
        if i < count - 1:
            time.sleep(interval)


def system_notify(title: str, body: str = ""):
    """Windows 原生通知（PowerShell），失败回退响铃。"""
    try:
        subprocess.run(
            ["powershell", "-Command",
             f'[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications]'
             f'::CreateToastNotifier("{title}").Show(New-Object '
             f'Windows.UI.Notifications.ToastNotification(New-Object '
             f'Windows.Data.Xml.Dom.XmlDocument))'],
            timeout=5, capture_output=True,
        )
    except Exception:
        _log.debug("系统通知失败，回退到响铃")
        bell()


def notify(config: dict, complete: int = 0, incomplete: int = 0):
    """按配置触发通知。

    Args:
        config:     {"sound": "bell"|"system"|"none", "on_complete": bool, "on_incomplete": bool}
        complete:   成功下载章节数
        incomplete: 不完整章节数
    """
    if not config:
        return

    sound = config.get("sound", DEFAULT_SOUND)
    if sound == "none":
        return

    on_complete = config.get("on_complete", DEFAULT_ON_COMPLETE)
    on_incomplete = config.get("on_incomplete", DEFAULT_ON_INCOMPLETE)

    if complete > 0 and on_complete:
        msg = f"下载完成: {complete} 章"
        if sound == "bell":
            bell(count=1)
        elif sound == "system":
            system_notify("novel-downloader", msg)

    if incomplete > 0 and on_incomplete:
        msg = f"不完整章节: {incomplete} 章"
        if sound == "bell":
            bell(count=2, interval=0.15)
        elif sound == "system":
            system_notify("novel-downloader", msg)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestNotify -q`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add cli/notify.py tests/test_interactive_cli.py
git commit -m "feat: 还原交互式 CLI 通知模块 cli/notify.py"
```

---

### Task 3: cli/menus.py — 设置/导出/删除子菜单

**Files:**
- Create: `cli/menus.py`
- Test: `tests/test_interactive_cli.py`（追加 `TestMenus` 类）

**Interfaces:**
- Consumes:
  - `cli.config`: `save_main_config(cfg)`、`load_format_configs()`、`save_site_config(platform, site_cfg)`、`load_groups()`、`add_novel_to_group(novel_id, group)`
  - `cli.ui`: `_select`、`_text_input`、`_input_int`、`_input_float`、`_platform_label`、`_show_platforms`
  - `cli.core._get_storage()`（函数内 import，避免循环依赖）
  - `novelbase.export`、`novelbase.exporter.register_export_options`（`{fmt: opt_cls}` 映射）
- Produces:
  - `do_settings(cfg: dict, platform: str, site_cfg: dict) -> tuple[dict, dict]` — 设置主菜单入口
  - `_fmt_summary(cfg: dict) -> str` — 已启用格式摘要
  - `_settings_download(cfg, platform, site_cfg, labels)` / `_settings_site(cfg, platform, site_cfg)` / `_settings_format_list(cfg)` / `_settings_format_toggle(all_formats, enabled)` — 子菜单
  - `_settings_site_browser/api/requests(cfg, site_cfg)` — 三种模式站点设置
  - `do_export_menu(group: str, format_configs: dict)` — 选书 → 选格式 → `export()`
  - `do_delete() -> None` — 列表 + yes 确认删除，同步移出全部分组
  - `_get_delay(site_cfg, mode) -> tuple[float, float]` / `_set_delay(site_cfg, mode, lo, hi)` — 延迟读写辅助

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_interactive_cli.py`）

```python
# ═══════════════════════════════════════════════════════════════
# cli.menus 菜单系统
# ═══════════════════════════════════════════════════════════════

class TestMenus:
    def test_fmt_summary_empty(self):
        from cli.menus import _fmt_summary
        assert _fmt_summary({}) == "未设置"
        assert _fmt_summary({"download": {}}) == "未设置"

    def test_fmt_summary_enabled(self):
        from cli.menus import _fmt_summary
        cfg = {"download": {"formats": ["epub", "txt"]}}
        assert _fmt_summary(cfg) == "epub, txt"

    def test_get_set_delay(self):
        from cli.menus import _get_delay, _set_delay
        site_cfg = {"browser": {"delay": [1, 2]}}
        assert _get_delay(site_cfg, "browser") == (1.0, 2.0)
        _set_delay(site_cfg, "browser", 0.5, 1.5)
        assert _get_delay(site_cfg, "browser") == (0.5, 1.5)

    def test_get_delay_default(self):
        from cli.menus import _get_delay
        assert _get_delay({}, "requests") == (3.0, 6.0)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestMenus -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'cli.menus'`）

- [ ] **Step 3: 写最小实现** `cli/menus.py`

```python
# -*- coding: utf-8 -*-
"""菜单系统：设置菜单、导出菜单、删除菜单（交互式）。"""

from __future__ import annotations

from cli.config import (
    save_main_config, load_format_configs,
    save_site_config, load_groups,
)
from cli.ui import _select, _text_input, _input_int, _input_float, _platform_label, _show_platforms
from novelbase.utils.logger import get_logger

_log = get_logger("cli.menus")


# ── Settings menu ────────────────────────────────────────────


def do_settings(cfg: dict, platform: str, site_cfg: dict) -> tuple[dict, dict]:
    """设置菜单入口。返回 (cfg, site_cfg) 可能被修改。"""
    labels = _show_platforms()
    while True:
        fmt_str = _fmt_summary(cfg)
        print(f"\n[设置]")
        print(f" 平台: {_platform_label(labels, platform)}")
        print(f" 模式: {site_cfg.get('mode', 'browser')}")
        print(f" 1. 下载设置（线程/分组）")
        print(f" 2. 站点设置（{platform}）")
        print(f" 3. 格式设置  （{fmt_str}）")
        print(" 0. 返回主菜单（自动保存）")
        ch = input("请选择: ").strip()
        if ch == "1":
            _settings_download(cfg, platform, site_cfg, labels)
        elif ch == "2":
            _settings_site(cfg, platform, site_cfg)
        elif ch == "3":
            _settings_format_list(cfg)
        elif ch == "0":
            break
    return cfg, site_cfg


def _fmt_summary(cfg: dict) -> str:
    """已启用导出格式摘要。"""
    enabled = cfg.get("download", {}).get("formats", [])
    return ", ".join(enabled) if enabled else "未设置"


def _settings_download(cfg: dict, platform: str, site_cfg: dict, labels: dict) -> None:
    """下载设置子菜单。"""
    dl = cfg.setdefault("download", {})
    _log.debug("settings_download")

    mode = site_cfg.get("mode", "browser")
    print(f"\n[下载设置]")
    print(f" 当前模式: {mode}")
    print(" 1. 切换模式")
    print(f" 2. 下载线程数: {dl.get('max_workers', 3)}")
    print(f" 3. 下载分组: {dl.get('group', 'default')}")
    print(" 0. 返回")
    ch = input("请选择: ").strip()

    if ch == "1":
        modes = [("浏览器模式", "browser"), ("API 模式", "api"), ("Requests 模式", "requests")]
        sel = _select("选择模式", modes)
        if sel:
            site_cfg["mode"] = sel
            save_site_config(platform, site_cfg)
    elif ch == "2":
        n = _input_int("下载线程数", dl.get("max_workers", 3))
        dl["max_workers"] = n
        save_main_config(cfg)
    elif ch == "3":
        g = _text_input("输入分组名称")
        if g:
            dl["group"] = g
            save_main_config(cfg)


def _settings_site(cfg: dict, platform: str, site_cfg: dict) -> None:
    """站点设置子菜单。"""
    mode = site_cfg.get("mode", "browser")
    print(f"\n[{platform} 站点设置]")

    if mode == "browser":
        _settings_site_browser(cfg, site_cfg)
    elif mode == "api":
        _settings_site_api(cfg, site_cfg)
    elif mode == "requests":
        _settings_site_requests(cfg, site_cfg)

    save_site_config(platform, site_cfg)


def _settings_site_browser(cfg: dict, site_cfg: dict) -> None:
    """浏览器模式站点设置。"""
    browser = site_cfg.setdefault("browser", {})
    while True:
        lo, hi = _get_delay(site_cfg, "browser")
        print(f"\n  浏览器设置:")
        print(f"  1. 无头模式: {browser.get('headless', False)}")
        print(f"  2. 延迟: {lo}-{hi}s")
        print(f"  3. 超时: {browser.get('timeout', 30)}s")
        print(f"  4. 重试次数: {browser.get('retry_times', 3)}")
        print(f"  5. 回退系数: {browser.get('backoff_factor', 2)}")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            browser["headless"] = not browser.get("headless", False)
        elif ch == "2":
            lo = _input_float("最小延迟", lo)
            hi = _input_float("最大延迟", hi)
            _set_delay(site_cfg, "browser", lo, hi)
        elif ch == "3":
            browser["timeout"] = _input_int("超时(秒)", browser.get("timeout", 30))
        elif ch == "4":
            browser["retry_times"] = _input_int("重试次数", browser.get("retry_times", 3))
        elif ch == "5":
            browser["backoff_factor"] = _input_float("回退系数", browser.get("backoff_factor", 2))
        elif ch == "0":
            break


def _settings_site_api(cfg: dict, site_cfg: dict) -> None:
    """API 模式站点设置。"""
    api = site_cfg.setdefault("api", {})
    while True:
        print(f"\n  API 设置:")
        current_name = None
        for name, prov in api.items():
            if isinstance(prov, dict):
                current_name = name
                print(f"  提供商: {name} {'(启用)' if prov.get('enabled', True) else '(禁用)'}")
                print(f"  1. 切换提供商(当前: {name})")
                print(f"  2. 启用/禁用 {name}")
                print(f"  3. 超时: {prov.get('timeout', 30)}s")
                print(f"  4. 重试次数: {prov.get('retry_times', 3)}")
                break
        if current_name is None:
            print("  无 API 提供商配置")
            print("  0. 返回")
            ch = input("请选择: ").strip()
            if ch == "0":
                break
            continue
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            names = [n for n, v in api.items() if isinstance(v, dict)]
            if not names:
                print("没有可用提供商")
            else:
                choices = [(n, n) for n in names]
                sel = _select("选择提供商", choices)
                if sel:
                    for n in names:
                        api[n]["enabled"] = (n == sel)
        elif ch == "2":
            for name, prov in api.items():
                if isinstance(prov, dict):
                    prov["enabled"] = not prov.get("enabled", True)
                    print(f"{name} 已{'启用' if prov['enabled'] else '禁用'}")
                    break
        elif ch == "3":
            for name, prov in api.items():
                if isinstance(prov, dict):
                    prov["timeout"] = _input_int("超时(秒)", prov.get("timeout", 30))
                    break
        elif ch == "4":
            for name, prov in api.items():
                if isinstance(prov, dict):
                    prov["retry_times"] = _input_int("重试次数", prov.get("retry_times", 3))
                    break
        elif ch == "0":
            break


def _settings_site_requests(cfg: dict, site_cfg: dict) -> None:
    """Requests 模式站点设置。"""
    req = site_cfg.setdefault("requests", {})
    while True:
        lo, hi = _get_delay(site_cfg, "requests")
        print(f"\n  Requests 设置:")
        print(f"  1. 延迟: {lo}-{hi}s")
        print(f"  2. 超时: {req.get('timeout', 30)}s")
        print(f"  3. 重试次数: {req.get('retry_times', 3)}")
        print(f"  4. 回退系数: {req.get('backoff_factor', 2)}")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            lo = _input_float("最小延迟", lo)
            hi = _input_float("最大延迟", hi)
            _set_delay(site_cfg, "requests", lo, hi)
        elif ch == "2":
            req["timeout"] = _input_int("超时(秒)", req.get("timeout", 30))
        elif ch == "3":
            req["retry_times"] = _input_int("重试次数", req.get("retry_times", 3))
        elif ch == "4":
            req["backoff_factor"] = _input_float("回退系数", req.get("backoff_factor", 2))
        elif ch == "0":
            break


# ── Format settings ─────────────────────────────────────────


def _settings_format_list(cfg: dict) -> None:
    """格式开关列表。"""
    all_formats = load_format_configs()
    dl = cfg.setdefault("download", {})
    enabled = dl.setdefault("formats", [])

    while True:
        print(f"\n[格式设置]")
        for fmt in all_formats:
            mark = "✅" if fmt in enabled else "⬜"
            print(f"  {mark} {fmt}")
        print("\n  1. 启用/禁用")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            _settings_format_toggle(all_formats, enabled)
            save_main_config(cfg)
        elif ch == "0":
            break


def _settings_format_toggle(all_formats: dict, enabled: list) -> None:
    """切换格式启用状态。"""
    items = list(all_formats.keys())
    choices = [(f"{'✅' if f in enabled else '⬜'} {f}", f) for f in items]
    sel = _select("选择切换", choices)
    if sel:
        if sel in enabled:
            enabled.remove(sel)
        else:
            enabled.append(sel)


# ── Export menu ─────────────────────────────────────────────


def do_export_menu(group: str, format_configs: dict):
    """导出菜单：选书 → 选格式 → export()。仅存储操作，无需引擎。"""
    from cli.core import _get_storage
    from novelbase import export
    from novelbase.exporter import register_export_options

    storage = _get_storage()
    novels = list(storage.iter_metas())
    if not novels:
        print("书架上没有小说")
        return

    groups = load_groups()
    group_ids = set(groups.get(group, {}).keys()) if group != "default" else None
    novels_in_group = [n for n in novels if group == "default" or (group_ids and n.id in group_ids)]
    if not novels_in_group:
        print(f"分组 '{group}' 中没有小说")
        return

    print(f"\n可导出小说 ({len(novels_in_group)} 本):")
    for i, n in enumerate(novels_in_group, 1):
        print(f" {i}. {n.title} ({n.author})")
    try:
        raw = input("请输入编号: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(novels_in_group):
            return
    except ValueError:
        return

    novel = novels_in_group[idx]
    fmt_names = [f for f in format_configs if f in ["txt", "epub", "img"]]
    if not fmt_names:
        print("没有可用格式")
        return
    print("选择格式:")
    for i, f in enumerate(fmt_names, 1):
        print(f" {i}. {f}")
    try:
        raw = input("请输入编号: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw:
        return
    try:
        fidx = int(raw) - 1
        if fidx < 0 or fidx >= len(fmt_names):
            return
    except ValueError:
        return
    fmt = fmt_names[fidx]

    opt_cls_map = register_export_options()
    opt_cls = opt_cls_map.get(fmt)
    if opt_cls is None:
        print("无法获取导出选项")
        return
    fmt_cfg = format_configs.get(fmt, {})
    opts = opt_cls(**fmt_cfg)
    if opts is None:
        print("无法获取导出选项")
        return
    print(f"正在导出 '{novel.title}' → {fmt} ...")
    try:
        # export signature: (novel, options, format, **kwargs)
        result = export(novel, opts, fmt)
        print(f"导出完成: {result}")
    except Exception as e:
        print(f"导出失败: {e}")


# ── Delete menu ─────────────────────────────────────────────


def do_delete() -> None:
    """删除小说（yes 确认），并同步移出全部分组。仅存储操作，无需引擎。"""
    from cli.core import _get_storage
    from cli.config import save_groups

    storage = _get_storage()
    novels = list(storage.iter_metas())
    if not novels:
        print("书架上没有小说")
        return

    print(f"\n[删除小说]")
    for i, n in enumerate(novels, 1):
        print(f" {i}. {n.title} ({n.author})")
    try:
        raw = input("请输入编号 (q 取消): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw or raw.lower() == "q":
        return
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(novels):
            return
    except ValueError:
        return

    novel = novels[idx]
    print(f"\n确定删除 '{novel.title}'? (yes/no): ", end="")
    try:
        confirm = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if confirm == "yes":
        storage.delete_novel(novel.id)
        groups = load_groups()
        removed = False
        for g, ids in groups.items():
            if isinstance(ids, dict) and novel.id in ids:
                ids.pop(novel.id, None)
                removed = True
        if removed:
            save_groups(groups)
        print(f"已删除 '{novel.title}'")
        _log.info("用户删除小说: %s (%s)", novel.title, novel.id)
    else:
        print("取消删除")


# ── Delay helpers ───────────────────────────────────────────


def _get_delay(site_cfg: dict, mode: str) -> tuple[float, float]:
    """获取某模式的当前延迟范围。"""
    section = site_cfg.get(mode, {})
    delay = section.get("delay", (3, 6))
    if isinstance(delay, list):
        delay = tuple(delay)
    return delay[0], delay[1]


def _set_delay(site_cfg: dict, mode: str, lo: float, hi: float):
    """设置某模式的延迟范围。"""
    site_cfg.setdefault(mode, {})["delay"] = [lo, hi]
```

> 注：`do_delete` 相比旧版增强——删除后同步从 `groups.yaml` 全部组中移除该书（与 `cli/main.py` 的 `cmd_delete` 行为对齐）。

- [ ] **Step 4: 运行测试确认通过**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestMenus -q`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add cli/menus.py tests/test_interactive_cli.py
git commit -m "feat: 还原交互式 CLI 设置/导出/删除菜单 cli/menus.py"
```

---

### Task 4: cli/interactive.py — 交互主循环与菜单动作

**Files:**
- Create: `cli/interactive.py`
- Test: `tests/test_interactive_cli.py`（追加 `TestInteractive` 类）

**Interfaces:**
- Consumes:
  - `cli.config`: `load_main_config()`、`load_site_config(platform)`、`load_format_configs()`、`build_options(cfg, site_cfg)`、`add_novel_to_group(novel_id, group)`、`get_novel_group(novel_id, groups)`、`load_groups()`
  - `cli.core`: `_do_download_inner(engine, url, group, format_configs, max_workers=3, skip_delay=False, skip_export=True)`（async）、`do_update(format_configs, max_workers=3)`（async）、`_get_storage()`、`_create_progress`、`_advance_progress`
  - `cli.ui`: `_select`、`_text_input`
  - `cli.menus`: `do_settings`、`do_export_menu`、`do_delete`
  - `cli.notify.notify(config, complete, incomplete)`
  - `novelbase`: `resolve_meta(url, engine, skip_delay=False)`（async）、`search(platform, query, engine, skip_delay=False)`（async）、`resolve_chapter_list(url, engine, skip_delay=False)`（async）、`resolve_chapter(chapter, engine, skip_delay=False)`（async）、`create_engine(options)`
  - `novelbase.source`: `register_source()`、`platform_from_url(url) -> str | None`
  - `init_config`: `check_config()`、`init_all_config()`
- Produces:
  - `main()` — 交互式主菜单循环（根目录 `main.py` 入口委托至此）
  - `_platform_from_url(url: str) -> str` — 数据驱动平台推断，未知抛 `ValueError`
  - `_get_engine(platform: str)` — 从配置创建引擎
  - `do_search(query: str) -> tuple[str | None, str | None]` — 搜索/URL 识别，返回 `(url, platform)`
  - `do_download(url, group, format_configs, max_workers=3)` — 询问分组后复用 `_do_download_inner`
  - `do_update(format_configs, max_workers=3)` — 列表单选/全部更新
  - `do_visit_site() -> None` — browser 模式打开所选平台首页

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_interactive_cli.py`）

```python
# ═══════════════════════════════════════════════════════════════
# cli.interactive 交互主循环
# ═══════════════════════════════════════════════════════════════

class TestInteractive:
    def test_platform_from_url_fanqie(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("https://fanqienovel.com/page/7123456789012345678") == "fanqie"

    def test_platform_from_url_qidian(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("https://www.qidian.com/book/1012345678/") == "qidian"

    def test_platform_from_url_qimao(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("https://www.qimao.com/shuku/195958/") == "qimao"

    def test_platform_from_url_unknown_raises(self):
        from cli.interactive import _platform_from_url
        import pytest as _pytest
        with _pytest.raises(ValueError):
            _platform_from_url("https://example.com/novel/1")

    def test_platform_from_url_92xs_alias(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("http://www.92xs.info/html/96850/35632400.html") == "92xs"
```

> 注：`_platform_from_url` 依赖 `novelbase.source.platform_from_url` 的真实数据（fanqie/qidian/qimao/92xs 域名映射），不 mock——它是数据驱动行为的契约测试。若某平台不在注册源中（如私有源未设 `NLD_PRIVATE_SOURCES`），测试仅覆盖公开源。

- [ ] **Step 2: 运行测试确认失败**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestInteractive -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'cli.interactive'`）

- [ ] **Step 3: 写最小实现** `cli/interactive.py`

```python
# -*- coding: utf-8 -*-
"""交互式 CLI 主循环与菜单动作（根目录 main.py 委托至此）。"""

from __future__ import annotations

import asyncio

from cli.config import (
    load_main_config, load_site_config, load_format_configs,
    build_options, get_novel_group, load_groups,
)
from cli.ui import _select, _text_input, _create_progress, _advance_progress
from novelbase import (
    resolve_meta, resolve_chapter_list, resolve_chapter, search,
    create_engine,
)
from novelbase.source import register_source, platform_from_url
from novelbase.utils.logger import get_logger

_log = get_logger("cli.interactive")


def _platform_from_url(url: str) -> str:
    """从 URL 推断平台（数据驱动）。未知 URL 抛 ValueError。"""
    plat = platform_from_url(url)
    if plat:
        return plat
    raise ValueError(f"未识别书源 URL: {url}")


def _get_engine(platform: str = "fanqie"):
    """从当前配置创建引擎。"""
    cfg = load_main_config()
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)
    return create_engine(options)


# ── Search ──────────────────────────────────────────────────


def do_search(query: str) -> tuple[str | None, str | None]:
    """搜索小说。返回 (url, platform) 或 (None, None)。"""
    # URL 输入 → 自动推断平台
    if query.startswith("http://") or query.startswith("https://"):
        platform = _platform_from_url(query)
        engine = _get_engine(platform)
        try:
            novel = asyncio.run(resolve_meta(query, engine=engine, skip_delay=True))
            print(f"\n📖 {novel.title} — {novel.author}")
            return novel.url, platform
        except Exception as e:
            print(f"获取小说信息失败: {e}")
            return None, None
        finally:
            engine.close()

    # 关键字搜索 → 让用户选平台
    platforms = list(load_main_config().get("sites", {}).keys()) or list(register_source().keys())
    labels = {k: v.get("show_name", k) for k, v in register_source().items()}
    choices = [(labels.get(p, p), p) for p in platforms]
    platform = _select("选择平台", choices)
    if not platform:
        return None, None

    engine = _get_engine(platform)
    try:
        results = asyncio.run(search(platform, query, engine=engine, skip_delay=True))
    finally:
        engine.close()

    if not results:
        print("未找到结果")
        return None, None

    print(f"\n搜索 '{query}' 的结果:")
    for i, r in enumerate(results, 1):
        print(f" {i}. {r.title} — {r.author}")
    choices_list = [(f"{r.title} — {r.author}", i - 1) for i, r in enumerate(results, 1)]
    sel = _select("选择小说", choices_list)
    if sel is None:
        return None, None
    if 0 <= sel < len(results):
        return results[sel].url, platform
    return None, None


# ── Download ────────────────────────────────────────────────


def do_download(
    url: str, group: str,
    format_configs: dict, max_workers: int = 3,
) -> None:
    """交互式下载：询问分组后复用 cli.core 的全量下载（async 经 asyncio.run）。"""
    from cli.core import _do_download_inner

    platform = _platform_from_url(url)
    engine = _get_engine(platform)
    try:
        g = _text_input(f"归入分组 [{group}]")
        if g:
            group = g
        asyncio.run(_do_download_inner(
            engine, url, group, format_configs,
            max_workers=max_workers, skip_delay=True,
        ))
    finally:
        engine.close()


# ── Update ──────────────────────────────────────────────────


async def _update_one_async(novel, max_workers: int) -> int:
    """更新单本小说到最新章节。返回新增章节数。"""
    from cli.core import _get_storage

    storage = _get_storage()
    platform = _platform_from_url(novel.url)
    engine = _get_engine(platform)
    try:
        remote_chapters = await resolve_chapter_list(novel.url, engine=engine)
        if not remote_chapters:
            print("  无法获取远程章节")
            return 0

        existing = list(storage.load_chapters(novel.id))
        existing_set = {c.order for c in existing}
        new_chapters = [c for c in remote_chapters if c.order not in existing_set]

        if not new_chapters:
            print(f"  {len(existing)}/{len(remote_chapters)}")
            return 0

        print(f"  {len(existing)}/{len(remote_chapters)} \033[1;32m+{len(new_chapters)}\033[0m")

        sem = asyncio.Semaphore(max_workers)

        async def _dl(ch):
            async with sem:
                try:
                    resolved = await resolve_chapter(ch, engine=engine)
                    if resolved:
                        storage.save_chapter(novel, resolved)
                        return True
                except Exception:
                    pass
                return False

        results = await asyncio.gather(*(_dl(ch) for ch in new_chapters))
        ok = sum(1 for r in results if r)
        print(f"  下载 {ok}/{len(new_chapters)} 章")
        return ok
    except Exception as e:
        print(f"  更新失败: {e}")
        return 0
    finally:
        engine.close()


def do_update(format_configs: dict, max_workers: int = 3):
    """更新已有小说：展示分组列表，单选或全部更新。"""
    from cli.core import _get_storage, do_update as _do_update_all

    storage = _get_storage()
    groups = load_groups()

    all_novels = list(storage.iter_metas())
    if not all_novels:
        print("没有已下载的小说")
        return

    # 按分组排列
    grouped: dict[str, list] = {}
    ungrouped = []
    for n in all_novels:
        g = get_novel_group(n.id, groups)
        if g:
            grouped.setdefault(g, []).append(n)
        else:
            ungrouped.append(n)

    # 显示小说列表（分组区分）
    print(f"\n找到 {len(all_novels)} 本已下载小说：")
    idx = 0
    flat: list = []
    for g_name, novels in grouped.items():
        print(f"\n  [{g_name}]")
        for n in novels:
            idx += 1
            print(f"    {idx}. {n.title}  — {n.author}  [{n.id}]")
            flat.append(n)
    if ungrouped:
        print(f"\n  [未分组]")
        for n in ungrouped:
            idx += 1
            print(f"    {idx}. {n.title}  — {n.author}  [{n.id}]")
            flat.append(n)

    choices = [(f"{n.title}  — {n.author}", n) for n in flat]
    choices.append(("全部更新", "all"))
    choices.append(("返回", None))

    selection = _select("选择要更新的小说：", choices=choices)
    if selection is None:
        return

    if selection == "all":
        asyncio.run(_do_update_all(format_configs, max_workers=max_workers))
        return

    print(f"\n[{selection.title}] 正在更新...")
    ok = asyncio.run(_update_one_async(selection, max_workers))
    print(f"更新完成: 新增 {ok} 章")


# ── Visit site ──────────────────────────────────────────────


def do_visit_site() -> None:
    """用 BrowserEngine 打开所选平台网站。"""
    from novelbase import create_engine as _create_engine

    sources = register_source()
    labels = {k: v.get("show_name", k) for k, v in sources.items()}
    platform = _select("选择平台", [(labels.get(k, k), k) for k in sources.keys()])
    if not platform:
        return
    hosts = sources[platform].get("hosts", ())
    if not hosts:
        print(f"平台 {labels.get(platform, platform)} 没有配置网址")
        return
    url = f"https://{hosts[0]}"

    cfg = load_main_config()
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)
    options.set_mode("browser")
    engine = _create_engine(options)

    async def _open():
        page = await engine.new_page()
        await page.goto(url)
        input(f"\n已打开 {url}，按回车关闭浏览器...")

    try:
        asyncio.run(_open())
    finally:
        engine.close()


# ── Main menu ───────────────────────────────────────────────


def main():
    """交互式主菜单循环。"""
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("Novel下载器 启动中...")

    from init_config import check_config, init_all_config
    result = check_config()
    if result["missing"]:
        if result["all_missing"]:
            print("首次运行，正在从默认模板初始化配置...")
        init_all_config()
        print(f"已初始化 {len(result['missing'])} 个配置文件")

    while True:
        try:
            cfg = load_main_config()
            format_configs = load_format_configs()

            dl = cfg.get("download", {})
            group = dl.get("group", "default")
            max_workers = dl.get("max_workers", 3)

            print(f"\n分组: {group}    并发: {max_workers}")
            print("1. 🔍 搜索下载")
            print("2. 🔄 更新已有小说")
            print("3. 📤 导出小说")
            print("4. 🔁 重新导出")
            print("5. 🗑️  删除小说")
            print("6. ⚙️  设置")
            print("7. 🌐 访问网站")
            print("0. 🚪 退出")

            try:
                ch = input("请选择: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if ch == "1":
                query = _text_input("搜索关键词或 URL")
                if not query:
                    continue
                url, _platform = do_search(query)
                if url:
                    do_download(url, group, format_configs, max_workers)

            elif ch == "2":
                do_update(format_configs, max_workers)

            elif ch in ("3", "4"):
                from cli.menus import do_export_menu
                do_export_menu(group, format_configs)

            elif ch == "5":
                from cli.menus import do_delete
                do_delete()

            elif ch == "6":
                from cli.config import load_site_config as _lsc
                from cli.menus import do_settings
                cfg, site_cfg = do_settings(cfg, "fanqie", _lsc("fanqie"))

            elif ch == "7":
                do_visit_site()

            elif ch == "0":
                break

        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            _log.exception("主循环异常")
            print(f"发生错误: {e}")

    print("再见！")
```

> 注：下载/更新完成通知——`_do_download_inner` 内部在下载结束时调用 `cli.notify.notify`（见 cli/core.py 第 5 步附近；若当前版本未含，则交互层不额外加）。主循环不再重复通知。

- [ ] **Step 4: 运行测试确认通过**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/test_interactive_cli.py::TestInteractive -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 导入冒烟**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -c "from cli.interactive import main; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add cli/interactive.py tests/test_interactive_cli.py
git commit -m "feat: 还原交互式 CLI 主循环 cli/interactive.py（适配 async/新 API）"
```

---

### Task 5: main.py 入口

**Files:**
- Create: `main.py`（仓库根目录）

**Interfaces:**
- Consumes: `cli.interactive.main`
- Produces: 根目录可执行入口 `python main.py`

- [ ] **Step 1: 写实现** `main.py`

```python
"""novel-downloader 交互式 CLI 入口 — 委托到 cli.interactive.main。"""
from cli.interactive import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 导入冒烟**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -c "import main; print('OK')"`
Expected: `OK`（不进入主循环——`__name__ != "__main__"`）

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: 还原交互式 CLI 入口 main.py"
```

---

### Task 6: 全量回归与手动验证

**Files:**
- Test: `tests/`（全量）

- [ ] **Step 1: 全量 pytest 回归**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -m pytest tests/ -q`
Expected: 全部 PASS（现有 ~140 用例 + 新增 test_interactive_cli.py ~32 用例，0 failed）

- [ ] **Step 2: 非交互式入口回归（确保 cli/ 包未被破坏）**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app nld-test:3.11 python -c "import cli.main, cli.core, cli.config; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 手动验证清单（用户在本机执行，交互式需要 TTY）**

```bash
python main.py
```

依次验证：
1. 主菜单显示无方框字符（纯文字编号列表），显示分组/并发信息行
2. `1` 搜索下载：URL 输入 → 识别平台 → 询问分组 → 下载完成
3. `1` 搜索下载：关键词 → 选平台 → 选书 → 下载
4. `2` 更新已有小说：列表展示 → 单选更新 / `全部更新`
5. `3`/`4` 导出：选书 → 选格式 → 导出完成
6. `5` 删除：yes 确认 → 删除并移出分组
7. `6` 设置：下载/站点（三模式）/格式 各子菜单保存生效
8. `7` 访问网站：选平台 → 浏览器打开首页 → 回车关闭
9. `0` 退出；Ctrl+C 优雅退出

- [ ] **Step 4: 收尾自检**

Run: `git status` 与 `git log --oneline -6`
Expected: 5 个新增 commit（ui/notify/menus/interactive/main），工作区干净；`git diff HEAD` 仅含计划内文件。

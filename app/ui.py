# -*- coding: utf-8 -*-
"""Interactive UI helpers: menus, input, progress bars, platform info."""

from __future__ import annotations

import sys
from typing import Any

from novelbase.utils.logger import get_logger

_log = get_logger("app.ui")


# ── Input ────────────────────────────────────────────


def _select(message: str, choices: list[tuple[str, Any]] | dict[str, Any]) -> Any:
    """Display numbered menu, return selected value.

    choices: list of (label, value) tuples OR dict {label: value}.
    Returns None on 'q' or EOF.
    """
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
    """Get text input. Returns None on empty or EOF."""
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
    """Integer input with default."""
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
    """Float input with default."""
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


# ── Platforms ────────────────────────────────────────


def _show_platforms() -> dict[str, str]:
    """Return {display_label: internal_name} of available platforms.

    Dynamically discovers registered fetchers, falls back to hardcoded list.
    """
    try:
        from novelbase import get_fetchers
        fetchers = get_fetchers()
        labels = {
            "fanqie": "番茄小说 (fanqie)",
            "qidian": "起点中文网 (qidian)",
            "qimao":  "七猫小说 (qimao)",
        }
        return {labels.get(k, k): k for k in fetchers}
    except Exception:
        # Fallback
        return {
            "番茄小说 (fanqie)": "fanqie",
            "起点中文网 (qidian)": "qidian",
            "七猫小说 (qimao)":  "qimao",
        }


def _platform_label(platform_labels: dict[str, str], name: str) -> str:
    """Convert internal name to display label."""
    rev = {v: k for k, v in platform_labels.items()}
    return rev.get(name, name)


# ── Progress bar ─────────────────────────────────────


def _create_progress(total: int):
    """Create a rich progress bar."""
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
    """Update progress bar."""
    if last_title:
        progress.update(task, description=f"[cyan]{last_title[:40]}")
    progress.advance(task, advance)


# ── Chapter parsing ──────────────────────────────────


def parse_order_string(s: str, total: int) -> list[int]:
    """Parse chapter range string. Format: '1-10,20,30-'."""
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


def _build_url_from_id(novel_id: str) -> str:
    """novel_id -> platform URL."""
    from novelbase.fetchers.fanqie import FanqieFetcher
    from novelbase.fetchers.qidian import QidianFetcher
    from novelbase.fetchers.qimao import QimaoFetcher
    for fetcher_cls in (FanqieFetcher, QidianFetcher, QimaoFetcher):
        fetcher = fetcher_cls()
        url = fetcher.resolve_url_from_id(novel_id)
        if url:
            return url
    return ""

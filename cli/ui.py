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

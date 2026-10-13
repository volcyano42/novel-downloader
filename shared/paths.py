"""编译产物路径解析 — Nuitka / PyInstaller / 源码运行 三态统一。

为什么需要它：定位「exe 同目录的 app_data」曾有三份各自为政的实现，且都只认
PyInstaller 的 `sys.frozen`。Nuitka 产物不设该属性，于是三处一律走「源码运行」分支，
指向与 exe 无关的目录 —— 表现为用户报的「exe 无法识别同目录下的 app_data」。

Nuitka 4.1.3 onefile 实测（2026-10-14，`--mode=onefile` 产物）：
    sys.frozen               = False                        ← Nuitka 不设它（PyInstaller 专有标记）
    __compiled__             = True                         ← Nuitka 的真实标记
    sys.executable           = <Temp>/onefile_*/python.exe  ← 临时解包目录，不可用于定位用户目录
    sys.argv[0]              = <用户看到的 exe 路径>
    NUITKA_ONEFILE_DIRECTORY = <exe 所在目录>                ← onefile 专用
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_compiled() -> bool:
    """当前进程是否来自编译产物（Nuitka 的 `__compiled__` / PyInstaller 的 `sys.frozen`）。"""
    return "__compiled__" in globals() or getattr(sys, "frozen", False)


def exe_dir() -> Path | None:
    """编译产物（exe）所在目录；源码运行时返回 None。

    onefile 模式必须优先用 `NUITKA_ONEFILE_DIRECTORY`：此时 `sys.executable` 指向
    临时解包目录里的 `python.exe`，`__file__` 也在解包目录。standalone 模式与
    PyInstaller 下 `sys.executable` 就是 exe 本身。
    """
    if not is_compiled():
        return None
    onefile_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
    if onefile_dir:
        return Path(onefile_dir).resolve()
    return Path(sys.executable).resolve().parent

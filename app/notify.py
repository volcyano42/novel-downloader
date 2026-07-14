# -*- coding: utf-8 -*-
"""Notification module: terminal bell and Windows system notification."""

from __future__ import annotations

import subprocess

from novelbase.utils.logger import get_logger

_log = get_logger("app.notify")

DEFAULT_SOUND = "bell"
DEFAULT_ON_COMPLETE = True
DEFAULT_ON_INCOMPLETE = True


def bell(count: int = 1, interval: float = 0.15):
    """Terminal bell, count times with interval seconds between."""
    import time
    for i in range(count):
        print("\a", end="", flush=True)
        if i < count - 1:
            time.sleep(interval)


def system_notify(title: str, body: str = ""):
    """Windows native notification (PowerShell), fallback to bell on failure."""
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
    """Trigger notification based on config.

    Args:
        config:     {"sound": "bell"|"system"|"none", "on_complete": bool, "on_incomplete": bool}
        complete:   number of successfully downloaded chapters
        incomplete: number of incomplete chapters
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

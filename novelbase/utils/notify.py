"""跨平台通知模块 — 下载完成/不完整时弹出提示或播放提示音。

支持 Linux / macOS / Windows / Termux(Android)。
"""

import platform
import subprocess
import sys

from novelbase.utils.logger import get_logger

_log = get_logger("novelbase.notify")


def bell():
    """终端响铃 — 全平台通用。"""
    print("\a", end="", flush=True)


def system_notify(title: str, body: str = ""):
    """系统原生通知。"""
    system = platform.system()

    try:
        if system == "Linux":
            # 检测 Termux
            if "com.termux" in sys.executable or "termux" in platform.release().lower():
                subprocess.run(
                    ["termux-notification", "--title", title, "--content", body],
                    timeout=5, capture_output=True,
                )
            else:
                subprocess.run(
                    ["notify-send", title, body],
                    timeout=5, capture_output=True,
                )
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{body}" with title "{title}"'],
                timeout=5, capture_output=True,
            )
        elif system == "Windows":
            # Windows 10+ 用 PowerShell 弹 toast
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


def chapter_unavailable_notify(config: dict, chapter):
    """章节不可获取时发送通知。

    Args:
        config:  download.notify 配置字典
        chapter: 失败的 Chapter 对象
    """
    if not config:
        return

    sound = config.get("chapter_unavailable_sound", "bell")

    if sound == "bell":
        # 三短铃 — 区别于"完成"一声和"不完整"两声
        print("\a", end="", flush=True)
        import time
        time.sleep(0.1)
        print("\a", end="", flush=True)
        time.sleep(0.1)
        print("\a", end="", flush=True)
    elif sound == "system":
        system_notify(
            "novel-downloader — 章节不可获取",
            f"[{chapter.order}] {chapter.title}"
        )


def notify(config: dict, complete: int = 0, incomplete: int = 0):
    """根据配置触发通知。

    Args:
        config:     download.notify 配置字典
        complete:   成功下载的章节数
        incomplete: 不完整的章节数
    """
    if not config:
        return

    sound = config.get("sound", "bell")
    on_complete = config.get("on_complete", True)
    on_incomplete = config.get("on_incomplete", True)

    if complete > 0 and on_complete:
        msg = f"下载完成: {complete} 章"
        if sound == "bell":
            bell()
        elif sound == "system":
            system_notify("novel-downloader", msg)

    if incomplete > 0 and on_incomplete:
        msg = f"不完整章节: {incomplete} 章"
        if sound == "bell":
            # 两次短铃区分
            print("\a", end="", flush=True)
            import time
            time.sleep(0.15)
            bell()
        elif sound == "system":
            system_notify("novel-downloader", msg)

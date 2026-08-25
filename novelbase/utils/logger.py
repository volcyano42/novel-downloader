"""日志系统 — 模块导入时自动初始化，不暴露配置接口。"""
import logging
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

# ── Key 脱敏 ─────────────────────────────────────────

# 匹配 URL 中的 apikey 查询参数值（支持 URL 编码）
_APIKEY_RE = re.compile(r"(?<=apikey=)[^&\s]+")

# 匹配 POST body 中的 "key": "xxx" 值
_KEY_IN_BODY_RE = re.compile(r'"key"\s*:\s*"([^"]+)"')


def mask_key(text: str) -> str:
    """替换 API key 为前 4 后 4，中间变 *。

    自动处理 URL query 参数 (apikey=xxx) 和 JSON body 中的 key 字段。
    若 text 中不含 key 则原样返回。
    """
    def _mask_url(m: re.Match) -> str:
        raw = m.group()
        if len(raw) <= 8:
            return raw[:2] + "****" + raw[-2:] if len(raw) > 4 else "****"
        return raw[:4] + "****" + raw[-4:]

    def _mask_body(m: re.Match) -> str:
        raw = m.group(1)
        if len(raw) <= 8:
            masked = raw[:2] + "****" + raw[-2:] if len(raw) > 4 else "****"
        else:
            masked = raw[:4] + "****" + raw[-4:]
        return f'"key": "{masked}"'

    t = _APIKEY_RE.sub(_mask_url, text)
    t = _KEY_IN_BODY_RE.sub(_mask_body, t)
    return t


# ── 自动初始化 ───────────────────────────────────────

_init_lock = threading.Lock()
_initialized: bool = False
_log_file: Path | None = None


def _auto_configure() -> None:
    """系统缓存目录下初始化日志（线程安全，只执行一次）。"""
    global _initialized, _log_file

    with _init_lock:
        if _initialized:
            return
        _initialized = True

        root = logging.getLogger("novelbase")
        root.setLevel(logging.DEBUG)

        log_dir = Path(tempfile.gettempdir()) / f"novel-downloader-{datetime.now():%Y%m%d_%H%M%S}"
        log_dir.mkdir(parents=True, exist_ok=True)
        _log_file = log_dir / "novelbase.log"

        fh = logging.FileHandler(_log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
        root.propagate = False


# ── 模块导入时自动初始化 ─────────────────────────────────
_auto_configure()


def get_logger(name: str) -> logging.Logger:
    """返回 novelbase 层级下的子 logger。"""
    return logging.getLogger(name)

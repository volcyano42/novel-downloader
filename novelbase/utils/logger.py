import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class LogOptions:
    """日志配置"""
    enabled: bool = True
    output_dir: str | None = None   # None = 当前目录 logs/
    level: str = "DEBUG"            # DEBUG / INFO / WARNING / ERROR


_init_lock = threading.Lock()
_initialized: bool = False
_log_file: Path | None = None


def configure_logging(opts: LogOptions, force: bool = False) -> None:
    """设置全局日志配置。

    线程安全，多次调用只有第一次生效。
    ``force=True`` 可强制覆盖已初始化配置（exe 环境需要）。
    推荐在任何 get_logger / import nldlder 子模块之前调用。
    """
    global _initialized, _log_file

    with _init_lock:
        if _initialized and not force:
            return
        _initialized = True

        root = logging.getLogger("nldlder")
        root.setLevel(getattr(logging, opts.level.upper(), logging.DEBUG))

        if not opts.enabled:
            root.addHandler(logging.NullHandler())
            root.propagate = False
            return

        if opts.output_dir:
            log_dir = Path(opts.output_dir)
        else:
            log_dir = Path.cwd() / "logs"

        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _log_file = log_dir / f"{timestamp}.log"

        fh = logging.FileHandler(_log_file, encoding="utf-8")
        fh.setLevel(root.level)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
        root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """返回子 logger，继承 nldlder 父 logger 的 FileHandler。

    子 logger 自身不挂 handler，依赖 Python logging 层级传播。
    """
    if not _initialized:
        configure_logging(LogOptions())
    return logging.getLogger(name)

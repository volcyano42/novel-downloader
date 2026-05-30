import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class LogOptions:
    """日志配置"""
    enabled: bool = True
    output_dir: str | None = None   # None = 系统临时目录
    level: str = "DEBUG"            # DEBUG / INFO / WARNING / ERROR


_config: LogOptions | None = None
_log_dir: Path | None = None


def configure_logging(opts: LogOptions) -> None:
    """在应用启动时调用一次，设置全局日志配置。"""
    global _config, _log_dir
    _config = opts
    if opts.enabled and opts.output_dir:
        _log_dir = Path(opts.output_dir)
    elif opts.enabled:
        _log_dir = Path(tempfile.gettempdir()) / "novel-downloader"


def get_logger(name: str) -> logging.Logger:
    """返回以模块名命名的 logger，首次调用时按全局配置创建 handler。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    if _config is None:
        configure_logging(LogOptions())  # 未显式配置时使用默认值

    logger.setLevel(getattr(logging, _config.level.upper(), logging.DEBUG))

    if not _config.enabled:
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    _log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = _log_dir / f"{timestamp}.log"

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logger.level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.propagate = False

    return logger

"""全局运行时状态。"""
from __future__ import annotations

from pathlib import Path

from nldlder import NovelDownloader, Options, create_engine
from nldlder.core.storage import Storage

from .config import APP_DATA, CONFIG_DIR, load_configs, build_options

# ── 全局可变状态 ────────────────────────────────────────────────
cfg, site_cfg, format_configs, platform = load_configs()
mode = cfg.get("mode", "browser")
group = cfg.get("group", "default")
options = build_options(cfg, site_cfg)
storage = Storage(APP_DATA / "storage")
engine = create_engine(options)
dl = NovelDownloader(engine, options=options)

AVAILABLE_PLATFORMS = {}
PLATFORM_LABELS = {
    "fanqie": "番茄小说 (fanqie)",
    "qidian": "起点中文网 (qidian)",
}


def init_platforms():
    from nldlder import get_parsers
    global AVAILABLE_PLATFORMS
    AVAILABLE_PLATFORMS = get_parsers()


init_platforms()


def reload_engine():
    """从最新配置重建引擎和下载器。"""
    global cfg, site_cfg, format_configs, platform, mode, group, options, engine, dl
    cfg, site_cfg, format_configs, platform = load_configs()
    mode = cfg.get("mode", "browser")
    group = cfg.get("group", "default")
    options = build_options(cfg, site_cfg)
    if engine:
        engine.close()
    engine = create_engine(options)
    dl = NovelDownloader(engine, options=options)

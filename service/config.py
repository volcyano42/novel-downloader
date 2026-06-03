"""配置加载 — 与 main.py 共享逻辑。"""
from __future__ import annotations

from pathlib import Path

import yaml

from nldlder import Options

APP_DATA = Path(__file__).resolve().parent.parent / "app_data"
CONFIG_DIR = APP_DATA / "config"


def load_configs():
    """加载全部配置，返回 (cfg, site_cfg, format_configs, platform)。"""
    cfg_path = CONFIG_DIR / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    platform = cfg.get("platform", "fanqie")
    site_path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    site = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}
    fmts = {}
    fmt_dir = CONFIG_DIR / "formats"
    if fmt_dir.exists():
        for f in fmt_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for name, c in data.items():
                fmts[name] = c
    return cfg, site, fmts, platform


def build_options(cfg: dict, site_cfg: dict) -> Options:
    """从配置字典构建 Options 对象。"""
    options = Options()
    mode = cfg.get("mode", "browser")
    options.set_mode(mode)
    dc = cfg.get("download", {})
    options.set_download_options(max_workers=dc.get("max_workers", 3))

    if mode == "browser":
        bc = site_cfg.get("browser", {})
        ud = bc.get("user_data_dir", "")
        if ud:
            p = Path(ud)
            if not p.is_absolute():
                p = Path(__file__).resolve().parent.parent / p
        else:
            p = None
        options.set_browser_options(
            headless=bc.get("headless", False),
            user_data_dir=str(p) if p else None,
            timeout=bc.get("timeout", 30),
            retry_times=bc.get("retry_times", 3),
            backoff_factor=bc.get("backoff_factor", 2),
            delay=tuple(bc.get("delay", [3, 5])),
        )
    elif mode == "api":
        asec = site_cfg.get("api", {})
        for name, prov in asec.items():
            if isinstance(prov, dict) and prov.get("enabled", True):
                options.set_api_options(
                    name=name, key=prov.get("key", ""),
                    timeout=prov.get("timeout", 30),
                    retry_times=prov.get("retry_times", 3),
                    batch_size=prov.get("batch_size", 3),
                    backoff_factor=prov.get("backoff_factor", 2),
                    delay=tuple(prov.get("delay", [3, 5])),
                    params=prov.get("params", {}),
                )
                break
    elif mode == "requests":
        rc = site_cfg.get("requests", {})
        cv = rc.get("cookies")
        if isinstance(cv, str) and cv:
            cd = {}
            for item in cv.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cd[k.strip()] = v.strip()
            cv = cd
        elif not isinstance(cv, dict):
            cv = None
        options.set_requests_options(
            headers=rc.get("headers"), cookies=cv,
            proxies=rc.get("proxies"), timeout=rc.get("timeout", 30),
            retry_times=rc.get("retry_times", 3),
            backoff_factor=rc.get("backoff_factor", 2),
            delay=tuple(rc.get("delay", [3, 5])),
        )
    return options

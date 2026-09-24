"""引擎工厂 — 按 book source(source_name) + 能力声明的 mode 建引擎。

职责：读取三层合并配置 → 构建 Options → create_engine。
生命周期由调用方管理（用完必须 close）；缓存键 = (source_name, mode)。
"""

import json
import sys
import threading

from fastapi import HTTPException

from novelbase import Options, create_engine
from shared.config import merged_source_config

# ── 引擎缓存（全局，request 级别复用）──
_engine_cache: dict[str, object] = {}
# 保护 _engine_cache 并发读写。get_cached_engine 经 asyncio.to_thread 在
# 多线程并发执行，check-then-create 若无锁会双创建引擎（多启一个 Chromium）。
_engine_lock = threading.Lock()


def _capability_for_mode(source_name: str, mode: str) -> str | None:
    """按 mode 反查书源的能力段名（同名多段取 manifest 声明序第一个）。"""
    from novelbase.source import capabilities
    for cap, cap_mode in capabilities(source_name).items():
        if cap_mode == mode:
            return cap
    return None


def _fingerprint(source_name: str, mode: str) -> str:
    """生成缓存键（书源名 + mode）。

    BrowserEngine: (source_name, mode, browser_type, user_data_dir, viewport, headless)
    API/RequestsEngine: (source_name, mode)
    """
    import hashlib

    if mode == "browser":
        merged = merged_source_config(source_name)
        cap = _capability_for_mode(source_name, mode)
        cfg = merged.get(cap, {}) if cap else {}
        vp = cfg.get("viewport")
        raw = (
            f"{source_name}|{mode}|{cfg.get('browser_type','chromium')}|"
            f"{cfg.get('user_data_dir','')}|"
            f"{json.dumps(vp, sort_keys=True) if vp else ''}|"
            f"{cfg.get('headless', True)}"
        )
    else:
        raw = f"{source_name}|{mode}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached_engine(source_name: str, mode: str = "browser"):
    """从缓存取引擎，缓存未命中则创建。缓存键 = (source_name, mode)。

    首次创建后复用，不再每次 close。调用方不再负责生命周期。
    通过 invalidate_engine 或在 lifespan shutdown 时统一清理。
    """
    key = _fingerprint(source_name, mode)
    # 快速路径：缓存命中不加锁（高频，无副作用）
    engine = _engine_cache.get(key)
    if engine is not None:
        return engine

    # 慢路径：双重检查加锁，避免并发双创建
    with _engine_lock:
        engine = _engine_cache.get(key)
        if engine is not None:
            return engine
        engine = create_engine_for_request(source_name, mode)
        _engine_cache[key] = engine
        return engine


async def invalidate_engine(source_name: str, mode: str = "browser") -> bool:
    """关闭并移除指定引擎（配置更新时调用）。"""
    key = _fingerprint(source_name, mode)
    with _engine_lock:
        engine = _engine_cache.pop(key, None)
    if engine:
        await engine.aclose()
        return True
    return False


async def clear_engine_cache():
    """关闭所有缓存引擎（shutdown 时调用）。"""
    with _engine_lock:
        engines = list(_engine_cache.values())
        _engine_cache.clear()
    for engine in engines:
        await engine.aclose()


# ═══════════════════════════════════════════════════════════════════
# 引擎创建（请求级，不缓存）
# ═══════════════════════════════════════════════════════════════════

def _linux_default_browser_args() -> list[str] | None:
    """Linux 无桌面环境时返回 Chromium sandbox 兼容参数；非 Linux 返回 None。"""
    if sys.platform.startswith("linux"):
        return ["--no-sandbox", "--disable-gpu", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    return None

def create_engine_for_request(source_name: str, mode: str = "browser"):
    """按书源名 + 能力声明的 mode，从三层合并配置创建引擎实例。

    配置取自 `merged_source_config(source_name)` 中 mode 对应能力段（能力段名由
    `capabilities(source_name)` 反查）。每个请求调用一次，用完必须 close 释放资源。
    """
    merged = merged_source_config(source_name)
    cap = _capability_for_mode(source_name, mode)
    cfg: dict = merged.get(cap, {}) if cap else {}

    _cfg = lambda k, default=None: cfg.get(k, default)

    # ── API 模式 ──
    if mode == "api":
        if cap is None:
            raise HTTPException(400, f"书源 {source_name} 未声明 api 能力，无法创建 api 引擎")
        opts = Options().set_mode("api").set_api_options(
            key=cfg.get("key", ""),
            delay=tuple(cfg.get("delay", [3, 5])),
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            params=cfg.get("params"),
        )
        return create_engine(opts)

    # ── browser / requests ──
    opts = Options().set_mode(mode)
    if mode == "browser":
        vp = _cfg("viewport")
        opts = opts.set_browser_options(
            headless=_cfg("headless", True),
            browser_type=_cfg("browser_type", "chromium"),
            user_data_dir=_cfg("user_data_dir"),
            viewport={"width": vp["width"], "height": vp["height"]} if vp else None,
            delay=tuple(_cfg("delay", [3, 5])),
            timeout=_cfg("timeout", 30),
            retry_times=_cfg("retry_times", 3),
            backoff_factor=_cfg("backoff_factor", 2),
            extra_args=_cfg("extra_args") or _linux_default_browser_args(),
            auto_reconnect=_cfg("auto_reconnect", False),
        )
    elif mode == "requests":
        opts = opts.set_requests_options(
            headers=_cfg("headers"),
            cookies=_cfg("cookies", {}),
            proxies=_cfg("proxies", {}),
            delay=tuple(_cfg("delay", [3, 5])),
            timeout=_cfg("timeout", 30),
            retry_times=_cfg("retry_times", 3),
            backoff_factor=_cfg("backoff_factor", 2),
        )

    return create_engine(opts)

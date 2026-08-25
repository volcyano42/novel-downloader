"""引擎工厂 — 按 platform + mode + variant 从 sites/{platform}.yaml 创建引擎。

职责：读取配置 → 构建 Options → create_engine。
生命周期由调用方管理（用完必须 close）。
"""

import json
import os
import sys
import threading
import uuid

from fastapi import HTTPException

from novelbase import Options, create_engine
from shared.config import load_site_config, find_variant_options, get_mode_variant_config

# ── 引擎缓存（全局，request 级别复用）──
_engine_cache: dict[str, object] = {}
# 保护 _engine_cache 并发读写。get_cached_engine 经 asyncio.to_thread 在
# 多线程并发执行，check-then-create 若无锁会双创建引擎（多启一个 Chromium）。
_engine_lock = threading.Lock()


def _fingerprint(platform: str, mode: str, variant: str | None = None) -> str:
    """生成缓存键。

    BrowserEngine: (platform, mode, browser_type, user_data_dir, viewport, headless)
    APIEngine:     (platform, mode, variant)
    RequestsEngine:(platform, mode, "requests")
    """
    import hashlib

    if mode == "browser":
        site = load_site_config(platform)
        mode_cfg = get_mode_variant_config(site, mode, variant)
        vp = mode_cfg.get("viewport")
        raw = (
            f"{platform}|{mode}|{mode_cfg.get('browser_type','chromium')}|"
            f"{mode_cfg.get('user_data_dir','')}|"
            f"{json.dumps(vp, sort_keys=True) if vp else ''}|"
            f"{mode_cfg.get('headless', True)}"
        )
    elif mode == "api" and variant:
        raw = f"{platform}|{mode}|{variant}"
    else:
        raw = f"{platform}|{mode}|requests"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached_engine(platform: str,
                      mode: str = "browser",
                      variant: str | None = None):
    """从缓存取引擎，缓存未命中则创建。

    首次创建后复用，不再每次 close。调用方不再负责生命周期。
    通过 invalidate_engine 或在 lifespan shutdown 时统一清理。
    """
    key = _fingerprint(platform, mode, variant)
    # 快速路径：缓存命中不加锁（高频，无副作用）
    engine = _engine_cache.get(key)
    if engine is not None:
        return engine

    # 慢路径：双重检查加锁，避免并发双创建
    with _engine_lock:
        engine = _engine_cache.get(key)
        if engine is not None:
            return engine
        engine = create_engine_for_request(platform, mode, variant)
        _engine_cache[key] = engine
        return engine


async def invalidate_engine(platform: str,
                            mode: str = "browser",
                            variant: str | None = None) -> bool:
    """关闭并移除指定引擎（配置更新时调用）。"""
    key = _fingerprint(platform, mode, variant)
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


# ── 显式引擎实例（手动创建，key 为 engine_id）──
_explicit_engines: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════════════
# 引擎创建（请求级，不缓存）
# ═══════════════════════════════════════════════════════════════════

def _linux_default_browser_args() -> list[str] | None:
    """Linux 无桌面环境时返回 Chromium sandbox 兼容参数；非 Linux 返回 None。"""
    if sys.platform.startswith("linux"):
        return ["--no-sandbox", "--disable-gpu", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    return None

def create_engine_for_request(platform: str,
                              mode: str = "browser",
                              variant: str | None = None):
    """从 sites/{platform}.yaml 读取配置，创建引擎实例。

    每个请求调用一次，用完必须调用 engine.close() 释放资源。
    """
    site = load_site_config(platform)
    mode_cfg = get_mode_variant_config(site, mode, variant)

    _cfg = lambda k, default=None: mode_cfg.get(k, default)

    # ── API 模式：自动发现 platform 首个启用 variant ──
    if mode == "api" and not variant:
        api_section = site.get("api", {}) if isinstance(site.get("api"), dict) else {}
        for name, prov in api_section.items():
            if isinstance(prov, dict):
                variant = name
                break
        if not variant:
            raise HTTPException(400, f"平台 {platform} 的 API 模式没有启用任何 variant，请在站点配置中启用（如 oiapi/rain）或改用 requests/browser 模式")

    if mode == "api" and variant:
        prov_cfg = find_variant_options(variant)
        if prov_cfg is None:
            raise HTTPException(400, f"API variant '{variant}' 未启用或不存在，请在站点配置中启用它")
        key = os.environ.get(f"{variant.upper()}_API_KEY", "") or prov_cfg.get("key", "")
        opts = Options().set_mode("api").set_api_options(
            name=variant, key=key,
            delay=tuple(prov_cfg.get("delay", [3, 5])),
            timeout=prov_cfg.get("timeout", 30),
            retry_times=prov_cfg.get("retry_times", 3),
            backoff_factor=prov_cfg.get("backoff_factor", 2),
            params=prov_cfg.get("params"),
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
    elif mode == "api":
        raise HTTPException(400, f"平台 {platform} 的 API 模式没有可用的 variant，请在站点配置中启用一个")

    return create_engine(opts)


# ═══════════════════════════════════════════════════════════════════
# 显式引擎（手动管理 — 保留现有 API）
# ═══════════════════════════════════════════════════════════════════

def _build_options(mode: str, api=None, requests=None, browser=None) -> Options:
    """从 Pydantic 数据构建 Options 对象。"""
    opts = Options().set_mode(mode)
    if mode == "api" and api:
        a = api
        opts.set_api_options(name=a.name, delay=a.delay, timeout=a.timeout,
                             retry_times=a.retry_times, backoff_factor=a.backoff_factor,
                             key=a.key, params=a.params)
    elif mode == "requests" and requests:
        r = requests
        opts.set_requests_options(headers=r.headers, delay=r.delay, timeout=r.timeout,
                                  retry_times=r.retry_times, backoff_factor=r.backoff_factor,
                                  cookies=r.cookies, proxies=r.proxies)
    elif mode == "browser" and browser:
        b = browser
        opts.set_browser_options(browser_type=b.browser_type, delay=b.delay, timeout=b.timeout,
                                 retry_times=b.retry_times, backoff_factor=b.backoff_factor,
                                 headless=b.headless, user_data_dir=b.user_data_dir, viewport=b.viewport,
                                 extra_args=b.extra_args if hasattr(b, 'extra_args') and b.extra_args else _linux_default_browser_args(),
                                 auto_reconnect=b.auto_reconnect if hasattr(b, "auto_reconnect") else False)
    return opts


def _build_sub_options(mode: str, api=None, requests=None, browser=None):
    """从 Pydantic 数据构建子选项对象（APIOptions/RequestsOptions/BrowserOptions）。"""
    from novelbase.core.options import APIOptions, RequestsOptions, BrowserOptions
    if mode == "api" and api:
        a = api
        return APIOptions(name=a.name, delay=a.delay, timeout=a.timeout,
                          retry_times=a.retry_times, backoff_factor=a.backoff_factor,
                          key=a.key, params=a.params)
    elif mode == "requests" and requests:
        r = requests
        return RequestsOptions(headers=r.headers, delay=r.delay, timeout=r.timeout,
                               retry_times=r.retry_times, backoff_factor=r.backoff_factor,
                               cookies=r.cookies, proxies=r.proxies)
    elif mode == "browser" and browser:
        b = browser
        return BrowserOptions(browser_type=b.browser_type, delay=b.delay, timeout=b.timeout,
                              retry_times=b.retry_times, backoff_factor=b.backoff_factor,
                              headless=b.headless, user_data_dir=b.user_data_dir,
                              viewport=b.viewport, extra_args=b.extra_args)
    return None


def list_explicit_engines() -> list[dict]:
    return [
        {"id": eid, "mode": info["mode"], "platform": info.get("platform", "")}
        for eid, info in _explicit_engines.items()
    ]


def create_explicit_engine(mode: str, platform: str = "",
                           api=None, requests=None, browser=None) -> dict:
    engine_id = str(uuid.uuid4())[:8]
    opts = _build_options(mode, api, requests, browser)
    engine = create_engine(opts)
    _explicit_engines[engine_id] = {"engine": engine, "platform": platform, "mode": mode}
    return {"id": engine_id, "mode": mode, "platform": platform}


def get_explicit_engine(engine_id: str) -> dict | None:
    info = _explicit_engines.get(engine_id)
    if not info:
        return None
    return {"id": engine_id, "mode": info["mode"], "platform": info.get("platform", "")}


def update_explicit_engine(engine_id: str, mode: str,
                           api=None, requests=None, browser=None) -> dict | None:
    info = _explicit_engines.get(engine_id)
    if not info:
        return None
    sub_opts = _build_sub_options(mode, api, requests, browser)
    if sub_opts is None:
        return None
    info["engine"].update_options(sub_opts)
    info["mode"] = mode
    return {"id": engine_id, "mode": mode, "platform": info.get("platform", "")}


async def delete_explicit_engine(engine_id: str) -> bool:
    info = _explicit_engines.pop(engine_id, None)
    if info:
        eng = info["engine"]
        if hasattr(eng, "aclose"):
            await eng.aclose()
        elif hasattr(eng, "close"):
            eng.close()
        return True
    return False
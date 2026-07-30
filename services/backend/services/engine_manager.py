"""引擎工厂 — 按 platform + mode + provider 从 sites/{platform}.yaml 创建引擎。

职责：读取配置 → 构建 Options → create_engine。
生命周期由调用方管理（用完必须 close）。
"""

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from services.backend.services.config_service import load_site_config, find_provider_options
from novelbase import Options, create_engine


# ── 引擎缓存（全局，request 级别复用）──
_engine_cache: dict[str, object] = {}
_browser_executor = ThreadPoolExecutor(max_workers=1)
_requests_executor = ThreadPoolExecutor(max_workers=4)


def _fingerprint(platform: str, mode: str, provider: str | None = None) -> str:
    """生成缓存键。

    BrowserEngine: (platform, mode, browser_type, user_data_dir, viewport, headless)
    APIEngine:     (platform, mode, provider)
    RequestsEngine:(platform, mode, "requests")
    """
    import hashlib
    from novelbase.core.options import BrowserOptions

    if mode == "browser":
        site = load_site_config(platform)
        mode_cfg = site.get(mode, {}) if isinstance(site, dict) else {}
        vp = mode_cfg.get("viewport")
        raw = (
            f"{platform}|{mode}|{mode_cfg.get('browser_type','chromium')}|"
            f"{mode_cfg.get('user_data_dir','')}|"
            f"{json.dumps(vp, sort_keys=True) if vp else ''}|"
            f"{mode_cfg.get('headless', True)}"
        )
    elif mode == "api" and provider:
        raw = f"{platform}|{mode}|{provider}"
    else:
        raw = f"{platform}|{mode}|requests"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached_engine(platform: str,
                      mode: str = "browser",
                      provider: str | None = None):
    """从缓存取引擎，缓存未命中则创建。

    首次创建后复用，不再每次 close。调用方不再负责生命周期。
    通过 invalidate_engine 或在 lifespan shutdown 时统一清理。
    """
    key = _fingerprint(platform, mode, provider)
    if key in _engine_cache:
        engine = _engine_cache[key]
        return engine

    engine = create_engine_for_request(platform, mode, provider)
    _engine_cache[key] = engine
    return engine


def invalidate_engine(platform: str,
                      mode: str = "browser",
                      provider: str | None = None) -> bool:
    """关闭并移除指定引擎（配置更新时调用）。"""
    key = _fingerprint(platform, mode, provider)
    engine = _engine_cache.pop(key, None)
    if engine:
        engine.close()
        return True
    return False


def clear_engine_cache():
    """关闭所有缓存引擎（shutdown 时调用）。"""
    for key, engine in list(_engine_cache.items()):
        engine.close()
    _engine_cache.clear()


# ── 显式引擎实例（手动创建，key 为 engine_id）──
_explicit_engines: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════════════
# 引擎创建（请求级，不缓存）
# ═══════════════════════════════════════════════════════════════════

def create_engine_for_request(platform: str,
                              mode: str = "browser",
                              provider: str | None = None):
    """从 sites/{platform}.yaml 读取配置，创建引擎实例。

    每个请求调用一次，用完必须调用 engine.close() 释放资源。
    """
    site = load_site_config(platform)
    mode_cfg = site.get(mode, {}) if isinstance(site, dict) else {}

    _cfg = lambda k, default=None: mode_cfg.get(k, default)

    # ── API 模式：自动发现 platform 首个启用 provider ──
    if mode == "api" and not provider:
        api_section = site.get("api", {}) if isinstance(site.get("api"), dict) else {}
        for name, prov in api_section.items():
            if isinstance(prov, dict) and prov.get("enabled", True):
                provider = name
                break

    if mode == "api" and provider:
        prov_cfg = find_provider_options(provider) or {}
        key = os.environ.get(f"{provider.upper()}_API_KEY", "") or prov_cfg.get("key", "")
        opts = Options().set_mode("api").set_api_options(
            name=provider, key=key,
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
        raise ValueError(f"平台 {platform} 的 API 模式没有可用的 provider，请在站点配置中启用一个")

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
                                 headless=b.headless, user_data_dir=b.user_data_dir, viewport=b.viewport)
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
                              viewport=b.viewport)
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


def delete_explicit_engine(engine_id: str) -> bool:
    info = _explicit_engines.pop(engine_id, None)
    if info:
        eng = info["engine"]
        if hasattr(eng, "close"):
            eng.close()
        return True
    return False

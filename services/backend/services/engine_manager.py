"""引擎管理器 — 统一引擎缓存、指纹、热更新。"""
import hashlib
import json
import os
import uuid

from services.backend.services.config_service import load_config, load_site_config, find_provider_options
from nldlder import Options, create_engine
from nldlder.core.options import APIOptions, RequestsOptions, BrowserOptions

# ── 自动引擎缓存（下载/搜索用，key 为 "{engine_id}:{mode}" 或 "{engine_id}:api:{provider}"）──
_auto_engines: dict[str, tuple[object, str]] = {}

# ── 显式引擎实例（手动创建，key 为 engine_id）──
_explicit_engines: dict[str, dict] = {}


def _mode_fingerprint(mode_cfg: dict) -> str:
    """对模式配置做哈希，用于检测选项变更。"""
    return hashlib.md5(json.dumps(mode_cfg, sort_keys=True, default=str).encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════
# 自动引擎（下载/搜索）
# ═══════════════════════════════════════════════════════════════════

def get_or_create_engine(engine_id: str = "default", mode: str | None = None,
                         provider: str | None = None, platform: str | None = None):
    """获取或创建引擎（按指纹缓存），供下载/搜索端点使用。"""
    cfg = load_config()
    if mode is None:
        mode = cfg.get("mode", "browser")

    # ── API 模式：自动发现 platform 首个启用 provider ──
    if mode == "api" and not provider and platform:
        site = load_site_config(platform)
        api_section = site.get("api", {}) if isinstance(site.get("api"), dict) else {}
        for name, prov in api_section.items():
            if isinstance(prov, dict) and prov.get("enabled", True):
                provider = name
                break

    # ── API 模式：一个 provider 一个 engine ──
    if mode == "api" and provider:
        prov_cfg = find_provider_options(provider) or {}
        key = os.environ.get(f"{provider.upper()}_API_KEY", "") or prov_cfg.get("key", "")
        fp = _mode_fingerprint({**prov_cfg, "key": key})
        cache_key = f"{engine_id}:api:{provider}"
        if cache_key in _auto_engines:
            stored_engine, stored_fp = _auto_engines[cache_key]
            if stored_fp == fp:
                return stored_engine
            try:
                stored_engine.close()
            except Exception:
                pass
            del _auto_engines[cache_key]
        opts = Options().set_mode("api").set_api_options(
            name=provider, key=key,
            delay=tuple(prov_cfg.get("delay", [3, 5])),
            timeout=prov_cfg.get("timeout", 30),
            retry_times=prov_cfg.get("retry_times", 3),
            backoff_factor=prov_cfg.get("backoff_factor", 2),
            params=prov_cfg.get("params"),
        )
        engine = create_engine(opts)
        _auto_engines[cache_key] = (engine, fp)
        return engine

    # ── browser / requests / api(无provider) 模式 ──
    dl = cfg.get("download", {})
    mode_cfg = dl.get(mode, {})
    fp = _mode_fingerprint(mode_cfg)
    cache_key = f"{engine_id}:{mode}"

    if cache_key in _auto_engines:
        stored_engine, stored_fp = _auto_engines[cache_key]
        if stored_fp == fp:
            return stored_engine
        try:
            stored_engine.close()
        except Exception:
            pass
        del _auto_engines[cache_key]

    opts = Options().set_mode(mode)
    if mode == "browser":
        opts = opts.set_browser_options(
            headless=mode_cfg.get("headless", True),
            browser_type=mode_cfg.get("browser_type", "chromium"),
            user_data_dir=mode_cfg.get("user_data_dir"),
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )
    elif mode == "requests":
        opts = opts.set_requests_options(
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )
    elif mode == "api":
        opts = opts.set_api_options(
            name=mode_cfg.get("name", "default"),
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )

    engine = create_engine(opts)
    _auto_engines[cache_key] = (engine, fp)
    return engine


def reload_engine_options(mode: str):
    """重新加载指定 mode 的所有运行中引擎配置（热更新，不重建）。"""
    cfg = load_config()

    for cache_key, (engine, _old_fp) in list(_auto_engines.items()):
        parts = cache_key.split(":")
        if len(parts) < 2:
            continue

        if mode == "api":
            if parts[1] != "api":
                continue
            provider = parts[2] if len(parts) > 2 else None
            if provider:
                prov_cfg = find_provider_options(provider) or {}
                key = os.environ.get(f"{provider.upper()}_API_KEY", "") or prov_cfg.get("key", "")
                sub_opts = APIOptions(
                    name=provider, key=key,
                    delay=tuple(prov_cfg.get("delay", [3, 5])),
                    timeout=prov_cfg.get("timeout", 30),
                    retry_times=prov_cfg.get("retry_times", 3),
                    backoff_factor=prov_cfg.get("backoff_factor", 2),
                    params=prov_cfg.get("params"),
                )
                new_fp = _mode_fingerprint({**prov_cfg, "key": key})
            else:
                continue
        else:
            if parts[1] != mode:
                continue
            dl = cfg.get("download", {})
            mode_cfg = dl.get(mode, {})
            if mode == "browser":
                sub_opts = BrowserOptions(
                    headless=mode_cfg.get("headless", True),
                    browser_type=mode_cfg.get("browser_type", "chromium"),
                    user_data_dir=mode_cfg.get("user_data_dir"),
                    delay=tuple(mode_cfg.get("delay", [3, 5])),
                    timeout=mode_cfg.get("timeout", 30),
                    retry_times=mode_cfg.get("retry_times", 3),
                    backoff_factor=mode_cfg.get("backoff_factor", 2),
                )
            elif mode == "requests":
                sub_opts = RequestsOptions(
                    delay=tuple(mode_cfg.get("delay", [3, 5])),
                    timeout=mode_cfg.get("timeout", 30),
                    retry_times=mode_cfg.get("retry_times", 3),
                    backoff_factor=mode_cfg.get("backoff_factor", 2),
                )
            else:
                continue
            new_fp = _mode_fingerprint(mode_cfg)

        try:
            engine.update_options(sub_opts)
            _auto_engines[cache_key] = (engine, new_fp)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# 显式引擎（手动管理）
# ═══════════════════════════════════════════════════════════════════

def _build_options(mode: str, api=None, requests=None, browser=None) -> Options:
    """从 Pydantic 数据构建 Options 对象。"""
    opts = Options().set_mode(mode)
    if mode == "api" and api:
        a = api
        opts.set_api_options(name=a.name, enabled=a.enabled, delay=a.delay, timeout=a.timeout,
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
    if mode == "api" and api:
        a = api
        return APIOptions(name=a.name, enabled=a.enabled, delay=a.delay, timeout=a.timeout,
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
    return {"engine_id": engine_id, "mode": mode, "platform": platform}


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

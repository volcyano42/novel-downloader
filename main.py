import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# ═══════════════════════════════════════════════════════════════════
# 日志初始化 — 必须在 import nldlder 之前，否则子模块的
# get_logger() 会在 configure_logging() 之前触发，导致日志散落
# ═══════════════════════════════════════════════════════════════════

def _get_app_data_dir() -> Path:
    """获取应用数据目录。

    优先使用 ``NLD_APP_DATA`` 环境变量，未设置时回退到默认路径。
    PyInstaller 打包后 ``__file__`` 指向临时目录，改用 ``sys.executable`` 定位。
    """
    env_path = os.environ.get("NLD_APP_DATA")
    if env_path:
        return Path(env_path).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "app_data"
    return Path(__file__).parent / "app_data"


APP_DATA = _get_app_data_dir()
CONFIG_DIR = APP_DATA / "config"


def _resolve_paths(value):
    """递归替换 YAML 中 `app_data/` 开头的路径为实际 APP_DATA 目录。

    设置了 NLD_APP_DATA 环境变量时，`app_data/exports/...` → 实际路径/exports/...
    未设置时保持原样（app_data 本身就是相对路径，行为不变）。
    """
    app_data_str = str(APP_DATA)
    if isinstance(value, str):
        if value.startswith("app_data/") or value.startswith("app_data\\"):
            return value.replace("app_data", app_data_str, 1)
        return value
    if isinstance(value, list):
        return [_resolve_paths(v) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_paths(v) for k, v in value.items()}
    return value


def load_main_config() -> dict:
    """加载 app_data/config/config.yaml"""
    path = CONFIG_DIR / "config.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return _resolve_paths(yaml.safe_load(f) or {})
    return {}


# 通过 importlib 直接加载 logger 模块，绕过 nldlder/__init__.py
# （__init__.py 导入子模块时会触发 get_logger，必须在配置之后）
# exe 环境下文件路径不可用，回退为 import_module。
# import_module 会触发 nldlder.__init__ → get_logger → 自动初始化，
# 后续使用 force=True 覆盖为用户配置。
if getattr(sys, "frozen", False):
    _logger_mod = importlib.import_module("nldlder.utils.logger")
else:
    _logger_path = Path(__file__).parent / "nldlder" / "utils" / "logger.py"
    _spec = importlib.util.spec_from_file_location("nldlder.utils.logger", _logger_path)
    _logger_mod = importlib.util.module_from_spec(_spec)
    sys.modules["nldlder.utils.logger"] = _logger_mod
    _spec.loader.exec_module(_logger_mod)

configure_logging = _logger_mod.configure_logging
LogOptions = _logger_mod.LogOptions

# 立即按用户配置初始化日志
cfg = load_main_config()
configure_logging(LogOptions(**cfg.get("log", {})),
                  force=getattr(sys, "frozen", False))

from nldlder import (
    NovelDownloader, Options, create_engine,
    get_fetchers, search, login,
    LocalStorage, AntiCrawlError,
    split_into_groups, get_fetcher_for_url, get_fetcher_for_id, Chapters,
)
from nldlder.core.exceptions import ChapterNotFoundError
from nldlder.utils.logger import get_logger

_log = get_logger("nldlder.main")

# rich 和 concurrent.futures 延迟导入（减少 PyInstaller 启动时的模块加载量）
# 使用处: _create_progress(), do_download(), do_update()


def _select(message: str, choices: list[tuple[str, Any]]) -> Any:
    """显示选项菜单，返回选中的 value。

    choices: [(label, value), ...] 或 [("标签", value), ..., ("返回", None)]
    """
    print(f"\n{message}")
    for i, (label, _) in enumerate(choices, 1):
        print(f"  {i}. {label}")
    while True:
        raw = input("请输入数字 (q 退出): ").strip()
        if raw.lower() == "q":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx][1]
        except ValueError:
            pass
        print("输入错误，请重新输入")


def _text_input(message: str) -> str | None:
    """获取文本输入。"""
    try:
        return input(f"{message} ").strip() or None
    except UnicodeDecodeError:
        # WSL/部分终端 stdin 编码非 utf-8 导致中文输入崩溃
        try:
            sys.stdin.reconfigure(encoding="utf-8")
            return input(f"{message} ").strip() or None
        except (UnicodeDecodeError, OSError):
            return None


def _show_platforms() -> dict:
    """返回 {label: name} 的可用平台字典。"""
    fetchers = get_fetchers()
    labels = {
        "fanqie": "番茄小说 (fanqie)",
        "qidian": "起点中文网 (qidian)",
    }
    return {labels.get(k, k): k for k in fetchers}


def load_site_config(platform: str = "fanqie") -> dict:
    """加载 app_data/config/sites/{platform}.yaml"""
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return _resolve_paths(yaml.safe_load(f) or {})
    return {}

def load_format_configs() -> dict:
    """加载 app_data/config/formats/*.yaml

    返回 {fmt_name: config_dict}，例如:
        {"txt": {"enabled": true, "output_path": "app_data/exports/{group}/{file_name_template}", ...}, ...}
    """
    formats = {}
    formats_dir = CONFIG_DIR / "formats"
    if formats_dir.exists():
        for f in formats_dir.glob("*.yaml"):
            with open(f, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
                for name, cfg in data.items():
                    formats[name] = _resolve_paths(cfg)
    return formats

def build_options(cfg: dict, site_cfg: dict) -> Options:
    """从配置字典构建 Options 对象。"""
    options = Options()
    mode = cfg.get("mode", "browser")
    options.set_mode(mode)

    # 模式特定选项
    if mode == "browser":
        browser_cfg = site_cfg.get("browser", {})
        user_data_dir = browser_cfg.get("user_data_dir", "")
        if user_data_dir:
            ud_path = Path(user_data_dir)
            if not ud_path.is_absolute():
                ud_path = Path(__file__).parent / ud_path
        else:
            ud_path = None
        options.set_browser_options(
            headless=browser_cfg.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=browser_cfg.get("timeout", 30),
            retry_times=browser_cfg.get("retry_times", 3),
            backoff_factor=browser_cfg.get("backoff_factor", 2),
            delay=tuple(browser_cfg.get("delay", [3, 5])),
            viewport=browser_cfg.get("viewport"),
        )

    elif mode == "api":
        api_section = site_cfg.get("api", {})
        for name, provider in api_section.items():
            if isinstance(provider, dict) and provider.get("enabled", True):
                # 优先使用环境变量 {PROVIDER}_API_KEY，再回退到 YAML 配置
                env_key_name = f"{name.upper()}_API_KEY"
                api_key = os.getenv(env_key_name) or provider.get("key", "")
                options.set_api_options(
                    name=name,
                    key=api_key,
                    timeout=provider.get("timeout", 30),
                    retry_times=provider.get("retry_times", 3),
                    batch_size=provider.get("batch_size", 1),
                    backoff_factor=provider.get("backoff_factor", 2),
                    delay=tuple(provider.get("delay", [3, 5])),
                    params=provider.get("params", {}),
                )
                break

    elif mode == "requests":
        req_cfg = site_cfg.get("requests", {})
        cookies_val = req_cfg.get("cookies")
        if isinstance(cookies_val, str) and cookies_val:
            cookies_dict = {}
            for item in cookies_val.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies_dict[k.strip()] = v.strip()
            cookies_val = cookies_dict
        elif not isinstance(cookies_val, dict):
            cookies_val = None

        options.set_requests_options(
            headers=req_cfg.get("headers"),
            cookies=cookies_val,
            proxies=req_cfg.get("proxies"),
            timeout=req_cfg.get("timeout", 30),
            retry_times=req_cfg.get("retry_times", 3),
            backoff_factor=req_cfg.get("backoff_factor", 2),
            delay=tuple(req_cfg.get("delay", [3, 5])),
        )

    options.set_storage_options(base_dir=APP_DATA / "storage")

    return options

def do_login(platform: str):
    """打开浏览器让用户登录指定平台。

    登录始终使用 BrowserEngine，不受当前 mode 配置影响。
    """
    platform_labels = _show_platforms()
    platform_choice = _select(
        "选择网站：",
        choices=[(label, name) for label, name in platform_labels.items()] + [("返回", None)],
    )

    if platform_choice is None:
        return platform

    platform = platform_choice
    site_cfg = load_site_config(platform)

    print("\n正在打开浏览器，请在浏览器窗口中完成登录...")
    print("（程序将自动检测登录完成，最多等待 120 秒）\n")

    browser_cfg = site_cfg.get("browser", {})
    login_engine = create_engine(
        Options().set_mode("browser").set_browser_options(
            headless=False,
            user_data_dir=browser_cfg.get("user_data_dir") or None,
            timeout=browser_cfg.get("timeout", 30),
            retry_times=browser_cfg.get("retry_times", 3),
            backoff_factor=browser_cfg.get("backoff_factor", 2),
            delay=tuple(browser_cfg.get("delay", [3, 5])),
        )
    )
    try:
        cred = login(platform, login_engine)
        cookie_count = len(cred.cookies) if cred and cred.cookies else 0
        if cookie_count > 0:
            print(f"✓ 登录成功！获取到 {cookie_count} 个 cookies")
            site_path = CONFIG_DIR / "sites" / f"{platform}.yaml"
            with open(site_path, encoding="utf-8") as f:
                site_yaml = yaml.safe_load(f) or {}
            if "requests" not in site_yaml:
                site_yaml["requests"] = {}
            site_yaml["requests"]["cookies"] = cred.cookies
            with open(site_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(site_yaml, f, allow_unicode=True)
            print(f"  Cookies 已保存到 {site_path}")
        else:
            print("⚠ 登录完成但未获取到 cookies，请确认已在浏览器中完成登录")
    except Exception as e:
        print(f"✗ 登录失败: {e}")
    finally:
        login_engine.close()

def save_main_config(cfg: dict):
    """保存配置到 app_data/config/config.yaml"""
    path = CONFIG_DIR / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)

def save_site_config(platform: str, site_cfg: dict):
    """保存站点配置到 app_data/config/sites/{platform}.yaml"""
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(site_cfg, f, allow_unicode=True)

def do_settings(cfg: dict, platform: str, site_cfg: dict) -> str:
    """交互式设置菜单 — 层级结构，覆盖所有配置项。"""
    platform_labels = _show_platforms()
    all_formats = list(load_format_configs().keys())
    enabled_formats: list[str] = cfg.get("formats") or all_formats
    if enabled_formats == "all":
        enabled_formats = all_formats[:]

    while True:
        mode = cfg.get("mode", "browser")
        pname = cfg.get("platform", platform)
        plabel = _platform_label(platform_labels, pname)
        fmt_str = "、".join(enabled_formats)

        print("\n===== 设置菜单 =====")
        print(f" 1. 下载设置  （模式: {mode} | 平台: {plabel}）")
        print(f" 2. 站点设置  （{mode} 模式专属选项）")
        print(f" 3. 格式设置  （{fmt_str}）")
        print(f" 4. 日志设置")
        print(" 0. 返回主菜单（自动保存）")
        print("====================")

        choice = input("\n请选择编号: ").strip()

        if choice == "0":
            save_main_config(cfg)
            save_site_config(platform, site_cfg)
            print("✓ 配置已保存")
            break
        elif choice == "1":
            platform = _settings_download(cfg, platform, site_cfg, platform_labels)
        elif choice == "2":
            _settings_site(cfg, platform, site_cfg)
        elif choice == "3":
            _settings_format(cfg, all_formats, enabled_formats)
        elif choice == "4":
            _settings_log(cfg)
        else:
            print("无效选项，请重新选择")

    return platform


# ═══════════════════════════════════════════════════════════════════
# 设置子菜单 — 辅助函数
# ═══════════════════════════════════════════════════════════════════

def _platform_label(platform_labels: dict, name: str) -> str:
    for label, n in platform_labels.items():
        if n == name:
            return label
    return name


def _input_int(prompt: str, default: int | None = None) -> int | None:
    try:
        val = input(prompt).strip()
        return int(val) if val else default
    except ValueError:
        return None


def _input_float(prompt: str, default: float | None = None) -> float | None:
    try:
        val = input(prompt).strip()
        return float(val) if val else default
    except ValueError:
        return None


def _get_delay(site_cfg: dict, mode: str) -> list:
    if mode == "browser":
        return site_cfg.get("browser", {}).get("delay", [3, 5])
    elif mode == "api":
        for prov in site_cfg.get("api", {}).values():
            if isinstance(prov, dict) and prov.get("enabled", True):
                return prov.get("delay", [3, 5])
    return site_cfg.get("requests", {}).get("delay", [3, 5])


def _set_delay(site_cfg: dict, mode: str, lo: int, hi: int):
    if mode == "browser":
        site_cfg.setdefault("browser", {})["delay"] = [lo, hi]
    elif mode == "api":
        for prov in site_cfg.get("api", {}).values():
            if isinstance(prov, dict) and prov.get("enabled", True):
                prov["delay"] = [lo, hi]
                return
        # fallback: write to first api provider
        apis = site_cfg.setdefault("api", {})
        for prov in apis.values():
            if isinstance(prov, dict):
                prov["delay"] = [lo, hi]
                return
        apis["default"] = {"delay": [lo, hi]}
    else:
        site_cfg.setdefault("requests", {})["delay"] = [lo, hi]


def _save_fmt_config(fmt_name: str, data: dict):
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)


def _load_fmt_config(fmt_name: str) -> dict:
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# ── 下载设置子菜单 ──────────────────────────────────────────────

def _settings_download(cfg: dict, platform: str, site_cfg: dict,
                       platform_labels: dict) -> str:
    while True:
        mode = cfg.get("mode", "browser")
        pname = cfg.get("platform", platform)
        download_cfg = cfg.get("download", {})
        max_workers = download_cfg.get("max_workers", 3)
        group = cfg.get("group", "default")
        delay = _get_delay(site_cfg, mode)
        plabel = _platform_label(platform_labels, pname)

        print(f"\n--- 下载设置 ---")
        print(f" 1. 下载模式     [{mode}]")
        print(f" 2. 目标平台     [{plabel}]")
        print(f" 3. 下载延迟     {delay} 秒")
        print(f" 4. 下载线程数   [{max_workers}]")
        print(f" 5. 分组名称     [{group}]")
        print(" 0. 返回")

        choice = input("\n请选择编号: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            new_mode = _select(
                "选择下载模式：",
                choices=[
                    ("browser  - 浏览器自动化", "browser"),
                    ("api      - 调用公开 API", "api"),
                    ("requests - 模拟 HTTP 请求", "requests"),
                    ("取消", None),
                ],
            )
            if new_mode:
                cfg["mode"] = new_mode
                save_main_config(cfg)
                print(f"✓ 下载模式 → {new_mode}")
        elif choice == "2":
            new_plat = _select(
                "选择目标平台：",
                choices=[(label, name) for label, name in platform_labels.items()]
                       + [("取消", None)],
            )
            if new_plat and new_plat != pname:
                cfg["platform"] = new_plat
                save_main_config(cfg)
                # 重新加载站点配置
                site_cfg.clear()
                site_cfg.update(load_site_config(new_plat))
                platform = new_plat
                print(f"✓ 目标平台 → {_platform_label(platform_labels, new_plat)}")
        elif choice == "3":
            lo = _input_float(f"延迟下限（当前: {delay[0]}s）: ")
            hi = _input_float(f"延迟上限（当前: {delay[1]}s）: ")
            if lo is not None and hi is not None and 0 <= lo <= hi:
                _set_delay(site_cfg, mode, lo, hi)
                save_site_config(platform, site_cfg)
                print(f"✓ 延迟 → [{lo}, {hi}] 秒")
            elif lo is not None or hi is not None:
                print("下限应 ≤ 上限且 ≥ 0")
        elif choice == "4":
            n = _input_int(f"下载线程数（当前: {max_workers}）: ")
            if n is not None and n > 0:
                cfg.setdefault("download", {})["max_workers"] = n
                save_main_config(cfg)
                print(f"✓ 线程数 → {n}")
            elif n is not None:
                print("线程数必须 > 0")
        elif choice == "5":
            g = input(f"分组名称（当前: {group}）: ").strip()
            if g:
                cfg["group"] = g
                save_main_config(cfg)
                print(f"✓ 分组 → {g}")
        else:
            print("无效选项")

    return platform


# ── 站点设置子菜单 ──────────────────────────────────────────────

def _settings_site(cfg: dict, platform: str, site_cfg: dict):
    while True:
        mode = cfg.get("mode", "browser")

        if mode == "browser":
            b = site_cfg.get("browser", {})
            vp = b.get("viewport", {})
            vp_str = f"{vp.get('width', 1280)}x{vp.get('height', 720)}" if vp else "默认"
            ud = b.get("user_data_dir", "")
            ud_short = ud.split("/")[-1] if ud else "默认"

            print(f"\n--- 站点设置 (browser) ---")
            print(f" 1. 无头模式       [{b.get('headless', False)}]")
            print(f" 2. 用户数据目录   [{ud_short}]")
            print(f" 3. 视口大小       [{vp_str}]")
            print(f" 4. 超时时间       [{b.get('timeout', 30)}s]")
            print(f" 5. 重试次数       [{b.get('retry_times', 3)}]")
            print(f" 6. 操作延迟       {b.get('delay', [3, 5])}s")
            print(" 0. 返回")

            choice = input("\n请选择编号: ").strip()
            if choice == "0":
                break
            elif choice == "1":
                site_cfg.setdefault("browser", {})["headless"] = not b.get("headless", False)
                save_site_config(platform, site_cfg)
                print(f"✓ 无头模式 → {site_cfg['browser']['headless']}")
            elif choice == "2":
                path = input(f"用户数据目录路径（当前: {ud or '默认'}）\nEnter 使用默认: ").strip()
                if path:
                    site_cfg.setdefault("browser", {})["user_data_dir"] = path
                    save_site_config(platform, site_cfg)
                    print(f"✓ 用户数据目录 → {path}")
            elif choice == "3":
                w = _input_int(f"视口宽度（当前: {vp.get('width', 1280)}）: ")
                h = _input_int(f"视口高度（当前: {vp.get('height', 720)}）: ")
                if w and h:
                    site_cfg.setdefault("browser", {})["viewport"] = {"width": w, "height": h}
                    save_site_config(platform, site_cfg)
                    print(f"✓ 视口 → {w}x{h}")
            elif choice == "4":
                t = _input_float(f"超时时间（当前: {b.get('timeout', 30)}s）: ")
                if t is not None and t > 0:
                    site_cfg.setdefault("browser", {})["timeout"] = t
                    save_site_config(platform, site_cfg)
                    print(f"✓ 超时 → {t}s")
            elif choice == "5":
                n = _input_int(f"重试次数（当前: {b.get('retry_times', 3)}）: ")
                if n is not None and n >= 0:
                    site_cfg.setdefault("browser", {})["retry_times"] = n
                    save_site_config(platform, site_cfg)
                    print(f"✓ 重试次数 → {n}")
            elif choice == "6":
                lo = _input_float(f"延迟下限（当前: {b.get('delay', [3,5])[0]}s）: ")
                hi = _input_float(f"延迟上限（当前: {b.get('delay', [3,5])[1]}s）: ")
                if lo is not None and hi is not None and 0 <= lo <= hi:
                    site_cfg.setdefault("browser", {})["delay"] = [lo, hi]
                    save_site_config(platform, site_cfg)
                    print(f"✓ 延迟 → [{lo}, {hi}]s")
            else:
                print("无效选项")

        elif mode == "api":
            apis = site_cfg.get("api", {})
            # 找到当前启用的 provider
            active_prov = None
            active_cfg = {}
            for name, prov in apis.items():
                if isinstance(prov, dict) and prov.get("enabled", True):
                    active_prov = name
                    active_cfg = prov
                    break
            if not active_prov:
                active_prov = "无"
                active_cfg = {}

            providers = [n for n, p in apis.items() if isinstance(p, dict)]
            prov_list = "、".join(providers) if providers else "无"
            key_masked = active_cfg.get("key", "")[:4] + "****" if active_cfg.get("key") else "（未设置）"

            print(f"\n--- 站点设置 (api) ---")
            print(f" 1. API Provider  [{active_prov}]  可用: {prov_list}")
            print(f" 2. API Key       [{key_masked}]")
            print(f" 3. 批量大小      [{active_cfg.get('batch_size', 3)}]")
            print(f" 4. 超时时间      [{active_cfg.get('timeout', 30)}s]")
            print(f" 5. 重试次数      [{active_cfg.get('retry_times', 3)}]")
            print(f" 6. 请求延迟      {active_cfg.get('delay', [3, 5])}s")
            print(" 0. 返回")

            choice = input("\n请选择编号: ").strip()
            if choice == "0":
                break
            elif choice == "1":
                if not providers:
                    print("没有可用的 API Provider")
                    continue
                # toggle: enable selected, disable others
                sel = _select("选择 API Provider：",
                              choices=[(p, p) for p in providers] + [("取消", None)])
                if sel:
                    for name in apis:
                        if isinstance(apis[name], dict):
                            apis[name]["enabled"] = (name == sel)
                    save_site_config(platform, site_cfg)
                    print(f"✓ API Provider → {sel}")
            elif choice == "2":
                key = input(f"API Key（当前: {key_masked}，Enter 不更改）: ").strip()
                if key:
                    site_cfg.setdefault("api", {})
                    if active_prov and active_prov in site_cfg["api"]:
                        site_cfg["api"][active_prov]["key"] = key
                    save_site_config(platform, site_cfg)
                    print("✓ API Key 已保存")
            elif choice == "3":
                n = _input_int(f"批量大小（当前: {active_cfg.get('batch_size', 3)}）: ")
                if n is not None and n > 0:
                    if active_prov:
                        site_cfg["api"][active_prov]["batch_size"] = n
                    save_site_config(platform, site_cfg)
                    print(f"✓ 批量大小 → {n}")
            elif choice == "4":
                t = _input_float(f"超时时间（当前: {active_cfg.get('timeout', 30)}s）: ")
                if t is not None and t > 0:
                    if active_prov:
                        site_cfg["api"][active_prov]["timeout"] = t
                    save_site_config(platform, site_cfg)
                    print(f"✓ 超时 → {t}s")
            elif choice == "5":
                n = _input_int(f"重试次数（当前: {active_cfg.get('retry_times', 3)}）: ")
                if n is not None and n >= 0:
                    if active_prov:
                        site_cfg["api"][active_prov]["retry_times"] = n
                    save_site_config(platform, site_cfg)
                    print(f"✓ 重试次数 → {n}")
            elif choice == "6":
                d = active_cfg.get("delay", [3, 5])
                lo = _input_float(f"延迟下限（当前: {d[0]}s）: ")
                hi = _input_float(f"延迟上限（当前: {d[1]}s）: ")
                if lo is not None and hi is not None and 0 <= lo <= hi:
                    if active_prov:
                        site_cfg["api"][active_prov]["delay"] = [lo, hi]
                    save_site_config(platform, site_cfg)
                    print(f"✓ 延迟 → [{lo}, {hi}]s")
            else:
                print("无效选项")

        else:  # requests
            r = site_cfg.get("requests", {})
            cookies = r.get("cookies", {})
            cookie_count = len(cookies) if isinstance(cookies, dict) else 0
            ua = (r.get("headers", {}) or {}).get("User-Agent", "")
            ua_short = ua[:50] + "..." if len(ua) > 50 else ua
            proxies = r.get("proxies", {}) or {}
            proxy_str = ", ".join(f"{k}={v}" for k, v in proxies.items()) if proxies else "无"

            print(f"\n--- 站点设置 (requests) ---")
            print(f" 1. Cookies        [{cookie_count} 条]")
            print(f" 2. User-Agent     [{ua_short}]")
            print(f" 3. 代理           [{proxy_str}]")
            print(f" 4. 超时时间       [{r.get('timeout', 30)}s]")
            print(f" 5. 重试次数       [{r.get('retry_times', 3)}]")
            print(f" 6. 请求延迟       {r.get('delay', [3, 5])}s")
            print(" 0. 返回")

            choice = input("\n请选择编号: ").strip()
            if choice == "0":
                break
            elif choice == "1":
                print(f"当前 {cookie_count} 条 cookies。")
                print("提示：使用主菜单的「登录」功能可自动获取 cookies。")
                raw = input("手动输入 cookie 字符串（Enter 不更改）: ").strip()
                if raw:
                    cd = {}
                    for item in raw.split(";"):
                        item = item.strip()
                        if "=" in item:
                            k, v = item.split("=", 1)
                            cd[k.strip()] = v.strip()
                    site_cfg.setdefault("requests", {})["cookies"] = cd
                    save_site_config(platform, site_cfg)
                    print(f"✓ Cookies → {len(cd)} 条")
            elif choice == "2":
                ua_new = input(f"User-Agent（Enter 不更改）: ").strip()
                if ua_new:
                    site_cfg.setdefault("requests", {}).setdefault("headers", {})["User-Agent"] = ua_new
                    save_site_config(platform, site_cfg)
                    print("✓ User-Agent 已保存")
            elif choice == "3":
                print("格式: http=http://host:port 或 https=http://host:port")
                raw = input("代理地址（Enter 清除代理）: ").strip()
                site_cfg.setdefault("requests", {})["proxies"] = {}
                if raw:
                    for part in raw.replace(",", " ").split():
                        if "=" in part:
                            k, v = part.split("=", 1)
                            site_cfg["requests"]["proxies"][k.strip()] = v.strip()
                save_site_config(platform, site_cfg)
                print(f"✓ 代理已{'设置' if raw else '清除'}")
            elif choice == "4":
                t = _input_float(f"超时时间（当前: {r.get('timeout', 30)}s）: ")
                if t is not None and t > 0:
                    site_cfg.setdefault("requests", {})["timeout"] = t
                    save_site_config(platform, site_cfg)
                    print(f"✓ 超时 → {t}s")
            elif choice == "5":
                n = _input_int(f"重试次数（当前: {r.get('retry_times', 3)}）: ")
                if n is not None and n >= 0:
                    site_cfg.setdefault("requests", {})["retry_times"] = n
                    save_site_config(platform, site_cfg)
                    print(f"✓ 重试次数 → {n}")
            elif choice == "6":
                d = r.get("delay", [3, 5])
                lo = _input_float(f"延迟下限（当前: {d[0]}s）: ")
                hi = _input_float(f"延迟上限（当前: {d[1]}s）: ")
                if lo is not None and hi is not None and 0 <= lo <= hi:
                    site_cfg.setdefault("requests", {})["delay"] = [lo, hi]
                    save_site_config(platform, site_cfg)
                    print(f"✓ 延迟 → [{lo}, {hi}]s")
            else:
                print("无效选项")


# ── 格式设置子菜单 ──────────────────────────────────────────────

def _settings_format(cfg: dict, all_formats: list, enabled_formats: list):
    while True:
        fmt_str = "、".join(enabled_formats)
        print(f"\n--- 格式设置 ---")
        print(f" 已启用: {fmt_str}")
        for i, fmt in enumerate(all_formats, 1):
            print(f" {i}. {fmt.upper()} 设置")
        print(f" {len(all_formats) + 1}. 启用/禁用格式")
        print(" 0. 返回")

        choice = input("\n请选择编号: ").strip()
        if choice == "0":
            break
        elif choice == str(len(all_formats) + 1):
            _settings_format_toggle(cfg, all_formats, enabled_formats)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(all_formats):
                    fmt = all_formats[idx]
                    if fmt == "txt":
                        _settings_fmt_txt()
                    elif fmt == "epub":
                        _settings_fmt_epub()
                    elif fmt == "img":
                        _settings_fmt_img()
            except ValueError:
                print("无效选项")


def _settings_format_toggle(cfg: dict, all_formats: list, enabled_formats: list):
    print("\n选择要启用的格式（可多选，逗号分隔）:")
    toggle = {}
    for i, fmt in enumerate(all_formats, 1):
        checked = "✓" if fmt in enabled_formats else " "
        toggle[str(i)] = fmt
        print(f"  [{checked}] {i}. {fmt}")

    raw = input("\n请输入编号（如 1,3，Enter 不更改）: ").strip()
    if raw:
        selected = []
        for token in raw.replace(",", " ").split():
            token = token.strip()
            if token in toggle:
                selected.append(toggle[token])
        if selected:
            enabled_formats.clear()
            enabled_formats.extend(dict.fromkeys(selected))
            cfg["formats"] = list(enabled_formats)
            save_main_config(cfg)
            print(f"✓ 已启用: {', '.join(enabled_formats)}")


def _settings_fmt_txt():
    data = _load_fmt_config("txt")
    txt = data.get("txt", {})
    print(f"\n--- TXT 设置 ---")
    print(f" 1. 编码         [{txt.get('encoding', 'utf-8')}]")
    print(f" 2. 输出路径     [{txt.get('output_path', '')}]")
    print(f" 3. 文件名模板   [{txt.get('file_name_template', '{title}')}]")
    print(" 0. 返回")

    choice = input("\n请选择编号: ").strip()
    if choice == "1":
        enc = input(f"编码（当前: {txt.get('encoding', 'utf-8')}，如 utf-8/gbk）: ").strip()
        if enc:
            data.setdefault("txt", {})["encoding"] = enc
            _save_fmt_config("txt", data)
            print(f"✓ 编码 → {enc}")
    elif choice == "2":
        p = input(f"输出路径（当前: {txt.get('output_path', '')}）\n可用占位符: {{group}} {{title}} {{author}} {{novel_id}} {{date}} {{file_name_template}}\n: ").strip()
        if p:
            data.setdefault("txt", {})["output_path"] = p
            _save_fmt_config("txt", data)
            print("✓ 输出路径已保存")
    elif choice == "3":
        t = input(f"文件名模板（当前: {txt.get('file_name_template', '{title}')}）: ").strip()
        if t:
            data.setdefault("txt", {})["file_name_template"] = t
            _save_fmt_config("txt", data)
            print(f"✓ 文件名模板 → {t}")


def _settings_fmt_epub():
    data = _load_fmt_config("epub")
    ep = data.get("epub", {})
    print(f"\n--- EPUB 设置 ---")
    print(f" 1. 编码           [{ep.get('encoding', 'utf-8')}]")
    print(f" 2. 输出路径       [{ep.get('output_path', '')}]")
    print(f" 3. 文件名模板     [{ep.get('file_name_template', '{title}')}]")
    print(f" 4. 包含目录       [{ep.get('include_toc', True)}]")
    print(f" 5. 压缩算法       [{ep.get('compression', 'deflate')}]  deflate/bzip2/stored")
    print(f" 6. 压缩级别       [{ep.get('compresslevel', 9)}]  1-9")
    print(f" 7. 优化图片       [{ep.get('optimize_images', True)}]")
    print(f" 8. JPEG 质量      [{ep.get('jpeg_quality', 85)}]  1-100")
    print(f" 9. 图片最大宽度   [{ep.get('max_image_width', 0)}]  0=不缩放")
    print(" 0. 返回")

    choice = input("\n请选择编号: ").strip()
    epub = data.setdefault("epub", {})
    if choice == "1":
        enc = input(f"编码（当前: {ep.get('encoding', 'utf-8')}）: ").strip()
        if enc:
            epub["encoding"] = enc
            _save_fmt_config("epub", data)
            print(f"✓ 编码 → {enc}")
    elif choice == "2":
        p = input(f"输出路径（当前: {ep.get('output_path', '')}）: ").strip()
        if p:
            epub["output_path"] = p
            _save_fmt_config("epub", data)
            print("✓ 输出路径已保存")
    elif choice == "3":
        t = input(f"文件名模板（当前: {ep.get('file_name_template', '{title}')}）: ").strip()
        if t:
            epub["file_name_template"] = t
            _save_fmt_config("epub", data)
            print(f"✓ 文件名模板 → {t}")
    elif choice == "4":
        epub["include_toc"] = not ep.get("include_toc", True)
        _save_fmt_config("epub", data)
        print(f"✓ 包含目录 → {epub['include_toc']}")
    elif choice == "5":
        alg = _select("选择压缩算法：",
                      choices=[("deflate (标准)", "deflate"),
                               ("bzip2 (高压缩)", "bzip2"),
                               ("stored (不压缩)", "stored"),
                               ("取消", None)])
        if alg:
            epub["compression"] = alg
            _save_fmt_config("epub", data)
            print(f"✓ 压缩 → {alg}")
    elif choice == "6":
        n = _input_int(f"压缩级别（当前: {ep.get('compresslevel', 9)}，1-9）: ")
        if n is not None and 1 <= n <= 9:
            epub["compresslevel"] = n
            _save_fmt_config("epub", data)
            print(f"✓ 压缩级别 → {n}")
    elif choice == "7":
        epub["optimize_images"] = not ep.get("optimize_images", True)
        _save_fmt_config("epub", data)
        print(f"✓ 优化图片 → {epub['optimize_images']}")
    elif choice == "8":
        n = _input_int(f"JPEG 质量（当前: {ep.get('jpeg_quality', 85)}，1-100）: ")
        if n is not None and 1 <= n <= 100:
            epub["jpeg_quality"] = n
            _save_fmt_config("epub", data)
            print(f"✓ JPEG 质量 → {n}")
    elif choice == "9":
        n = _input_int(f"图片最大宽度（当前: {ep.get('max_image_width', 0)}，0=不缩放）: ")
        if n is not None and n >= 0:
            epub["max_image_width"] = n
            _save_fmt_config("epub", data)
            print(f"✓ 图片最大宽度 → {n}")


def _settings_fmt_img():
    data = _load_fmt_config("img")
    im = data.get("img", {})
    print(f"\n--- IMG 设置 ---")
    print(f" 1. 输出格式   [{im.get('output_format', 'original')}]  original/jpeg/png/webp")
    print(f" 2. 输出路径   [{im.get('output_path', '')}]")
    print(f" 3. 文件名模板 [{im.get('file_name_template', '{n}')}]")
    print(" 0. 返回")

    choice = input("\n请选择编号: ").strip()
    img_cfg = data.setdefault("img", {})
    if choice == "1":
        fmt = _select("选择输出格式：",
                      choices=[("original (原格式)", "original"),
                               ("jpeg", "jpeg"),
                               ("png", "png"),
                               ("webp", "webp"),
                               ("取消", None)])
        if fmt:
            img_cfg["output_format"] = fmt
            _save_fmt_config("img", data)
            print(f"✓ 输出格式 → {fmt}")
    elif choice == "2":
        p = input(f"输出路径（当前: {im.get('output_path', '')}）\n可用占位符: {{group}} {{title}} {{author}} {{novel_id}} {{date}}\n: ").strip()
        if p:
            img_cfg["output_path"] = p
            _save_fmt_config("img", data)
            print("✓ 输出路径已保存")
    elif choice == "3":
        t = input(f"文件名模板（当前: {im.get('file_name_template', '{n}')}，{{n}}=图片序号）: ").strip()
        if t:
            img_cfg["file_name_template"] = t
            _save_fmt_config("img", data)
            print(f"✓ 文件名模板 → {t}")


# ── 日志设置子菜单 ──────────────────────────────────────────────

def _settings_log(cfg: dict):
    while True:
        log_cfg = cfg.get("log", {})
        enabled = log_cfg.get("enabled", True)
        level = log_cfg.get("level", "INFO")
        out_dir = log_cfg.get("output_dir", "app_data/logs")

        print(f"\n--- 日志设置 ---")
        print(f" 1. 启用日志   [{enabled}]")
        print(f" 2. 日志级别   [{level}]  DEBUG/INFO/WARNING/ERROR")
        print(f" 3. 输出目录   [{out_dir}]")
        print(" 0. 返回")

        choice = input("\n请选择编号: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            cfg.setdefault("log", {})["enabled"] = not enabled
            save_main_config(cfg)
            print(f"✓ 日志 → {'开启' if cfg['log']['enabled'] else '关闭'}")
        elif choice == "2":
            new_level = _select("选择日志级别：",
                                choices=[("DEBUG", "DEBUG"), ("INFO", "INFO"),
                                         ("WARNING", "WARNING"), ("ERROR", "ERROR"),
                                         ("取消", None)])
            if new_level:
                cfg.setdefault("log", {})["level"] = new_level
                save_main_config(cfg)
                print(f"✓ 级别 → {new_level}")
        elif choice == "3":
            d = input(f"输出目录（当前: {out_dir}）: ").strip()
            if d:
                cfg.setdefault("log", {})["output_dir"] = d
                save_main_config(cfg)
                print(f"✓ 输出目录 → {d}")
        else:
            print("无效选项")

def do_search(engine, dl, platform: str, page: int = 1, query: str | None = None) -> str | None:
    """搜索小说，选择后返回小说 URL（或 None 表示取消）。

    Args:
        engine: 下载引擎实例
        query: 搜索关键词。为 None 时交互式输入。
        dl: NovelDownloader实例
        platform: 网站
        page: 页数
    """
    if query is None:
        query = _text_input("请输入搜索关键词：")
    if not query or not query.strip():
        return None

    print(f"\n正在搜索「{query}」...")
    try:
        results = search(platform, query, engine, page=page,skip_dalay = True)
    except Exception as e:
        print(f"✗ 搜索失败: {e}")
        return None

    if not results:
        print("未找到任何结果")
        return None

    choices = []
    for i, r in enumerate(results):
        name = getattr(r, "title", "") or ""
        author = getattr(r, "author", "") or ""
        desc = getattr(r, "description", "") or ""
        desc_short = desc[:60] + "..." if len(desc) > 60 else desc
        title = f"{name}  — {author}"
        if desc_short:
            title += f"  ({desc_short})"
        choices.append((title, i))

    choices.append(("返回", None))

    selected_idx = _select(
        f"搜索到 {len(results)} 个结果，选择要下载的小说：",
        choices=choices,
    )

    if selected_idx is None:
        return None

    return results[selected_idx].url

def _create_progress(total: int):
    from rich.console import Console
    from rich.progress import (
        Progress, BarColumn, TextColumn, TimeRemainingColumn,
        TaskProgressColumn,
    )
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("*"),
        TimeRemainingColumn(),
        transient=False,
        console=Console(force_terminal=True),
    )
    task = progress.add_task(
        "[cyan]Downloading...",
        total=total,
        completed=0,
    )
    return progress, task

def _advance_progress(progress, task, advance: int, last_title: str):
    progress.update(
        task,
        advance=advance,
        description=f"[cyan]Downloading...[/] — {last_title}",
    )


def parse_order_string(s: str, total: int) -> set[int]:
    """解析章节序号选择字符串，返回 1-indexed 的 order 集合。

    格式:
        5            → {5}
        1-100        → {1,2,...,100}
        50-          → {50,51,...,total}
        -50          → {1,2,...,50}
        1-10,20,30-40 → 并集
        all          → 全部

    Args:
        s:     用户输入的序号字符串。
        total: 章节总数，用于展开 "50-" 这种格式。
    """
    s = s.strip()
    if not s or s == "all":
        return set()

    result: set[int] = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            left = left.strip()
            right = right.strip()
            start = int(left) if left else 1
            end = int(right) if right else total
            result.update(range(start, end + 1))
        else:
            result.add(int(part))

    return result


def _build_url_from_id(novel_id: str) -> str:
    """根据 novel_id 匹配 Fetcher，构造小说页面 URL。"""
    fc = get_fetcher_for_id(novel_id)
    if fc is None:
        raise ValueError(f"无法识别 novel_id: {novel_id}")
    from nldlder.fetchers.fanqie import FanqieFetcher
    from nldlder.fetchers.qidian import QidianFetcher
    if fc is FanqieFetcher:
        return f"https://fanqienovel.com/page/{novel_id}"
    if fc is QidianFetcher:
        return f"https://www.qidian.com/book/{novel_id}/"
    raise ValueError(f"Fetcher {fc.__name__} 未配置 URL 模板")


def do_download(engine, dl, url: str, group: str, format_configs: dict, max_workers: int = 3):
    """下载单个小说：获取信息 → 章节列表 → 合并本地 → 下载新章 → 导出。

    Args:
        engine:         下载引擎
        dl:             NovelDownloader 实例
        url:            小说页面 URL
        group:          分组名（用于填充导出路径中的 {group} 占位符）
        format_configs: 导出格式配置 {fmt_name: cfg_dict}
    """
    _log.info("===== 开始下载: %s =====", url)

    storage = dl.storage

    # ── 1. 获取小说信息 ──────────────────────────────────────────
    print("正在获取小说信息...")
    novel = dl.fetch_meta(url, skip_delay = True)
    _log.info("小说: %s — %s | %s章 | %s字",
              novel.title, novel.author, novel.serial, novel.count or '未知')
    print(f"  书名：{novel.title}")
    print(f"  作者：{novel.author}")
    tags_str = "、".join(novel.tags) if novel.tags else ""
    print(f"  标签：{tags_str}")
    print(f"  字数：{novel.count or '未知'}")
    meta_path = storage.save_meta(novel)
    print(f"  元数据已保存 → {meta_path}")

    # ── 2. 获取章节列表 ──────────────────────────────────────────
    print("正在获取章节列表...")
    chapters = dl.fetch_chapter_list(novel.url, skip_delay = True)
    _log.info("章节列表: %d章", len(chapters))
    print(f"  共 {len(chapters)} 章")
    novel.update_chapter(chapters)

    # ── 3. 合并本地已有进度 ──────────────────────────────────────
    local_chapters = storage.load_chapters(novel.id)
    if local_chapters:
        _log.info("本地已有 %d章, 合并进度", len(local_chapters))
        novel.update_chapter(local_chapters)

    # ── 3.5 选择下载范围 ────────────────────────────────────────
    total_chapters = len(novel.chapters)
    print(f"\n共 {total_chapters} 章，请输入下载范围：")
    print("  格式: 1-100、50-、-50、1,3,5-10 或 all（全部）")
    raw = _text_input("章节范围 (留空=全部/继续下载): ")
    if raw and raw.strip() and raw.strip().lower() != "all":
        selected_orders = parse_order_string(raw, total_chapters)
        if selected_orders:
            filtered = Chapters(
                ch for ch in novel.chapters
                if ch.order in selected_orders
            )
            print(f"  已选择 {len(filtered)} 章")
            # ponytail: merge() 只覆盖匹配 id 不删除未匹配的，
            # 直接设 chapters 才是真正的范围过滤。
            novel.chapters = filtered

    incomplete = novel.chapters.incompleted_chapters
    target = list(incomplete) if incomplete else []
    if not target:
        print("所有章节已下载完毕！")
    else:
        print(f"待下载: {len(target)} 章")

        # 分批
        batch_size = dl._options.api.batch_size if dl._options.mode == "api" else 1
        groups = split_into_groups(target, batch_size)
        total = len(target)

        _log.info(
            "开始下载: %d章, %d批次, %d线程, batch_size=%d",
            total, len(groups), max_workers, batch_size,
        )

        # 进度追踪
        done = 0
        failed_chapters = 0
        _done_at_last_log = 0
        _log_interval = max(total // 10, 1)

        # 进度条
        progress_ctx, task = _create_progress(total)

        # 抓取器（同一实例可复用）
        fetcher_cls = get_fetcher_for_url(target[0].index_url)
        fetcher = fetcher_cls() if fetcher_cls else None

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with progress_ctx as progress:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_group = {
                        executor.submit(
                            dl.resolve_chapters, batch, fetcher=fetcher,
                        ): batch
                        for batch in groups
                    }
                    pending_futures = set(future_to_group.keys())

                    for future in as_completed(future_to_group):
                        batch = future_to_group[future]
                        pending_futures.discard(future)
                        try:
                            result_chapters = future.result(timeout=120)
                        except TimeoutError:
                            _log.error("批次下载超时 (120s)，标记失败: %d章", len(batch))
                            failed_chapters += len(batch)
                            continue
                        except ChapterNotFoundError as e:
                            _log.warning("章节内容获取失败，跳过: %s", e)
                            failed_chapters += len(batch)
                            continue
                        except AntiCrawlError:
                            _log.error("触发反爬机制，中断下载")
                            failed_chapters += len(batch)
                            for pf in pending_futures:
                                pf.cancel()
                                failed_chapters += len(future_to_group[pf])
                            raise

                        # 增量持久化
                        storage.save_chapter(novel, result_chapters)
                        novel.update_chapter(result_chapters)
                        done += len(result_chapters)

                        # 进度栏
                        last_title = result_chapters[-1].title if result_chapters else "?"
                        _advance_progress(progress, task, len(result_chapters), last_title)

                        # 周期日志
                        if done - _done_at_last_log >= _log_interval:
                            _done_at_last_log = done
                            _log.info("下载进度: %d/%d章 (%d%%)", done, total, done * 100 // total)

        except AntiCrawlError:
            remaining = total - done - failed_chapters
            if remaining > 0:
                print(f"⚠ 触发反爬，保存已下载部分（剩余 {remaining} 章未下载）...")
            else:
                print("⚠ 触发反爬，保存已下载部分...")
            print(f"  已保存 {done} 章到磁盘")
            raise

        # 完成统计
        if failed_chapters:
            _log.warning("下载结束: %d/%d章成功, %d章失败", done, total, failed_chapters)
        else:
            _log.info("下载完成: %d/%d章", done, total)

        # ── 统计输出 ──────────────────────────────────────────
        incomplete = novel.chapters.incompleted_chapters
        incomplete_count = len(incomplete) if incomplete else 0
        success = done - failed_chapters

        print(f"\n{'='*40}")
        print(f"  下载总结")
        print(f"{'='*40}")
        print(f"  总计: {total} 章  |  成功: {success} 章  |  失败: {failed_chapters} 章")
        if incomplete_count:
            print(f"  不完整: {incomplete_count} 章 (待下次更新)")
            print(f"  {'─'*36}")
            for ch in incomplete:
                short = ch.title[:6] + ("…" if len(ch.title) > 6 else "")
                print(f"    [{ch.order:>4}] {short}")
        else:
            print(f"  全部章节下载完成 ✓")
        print(f"{'='*40}")

    # ── 5. 导出 ──────────────────────────────────────────────────
    print("正在导出...")
    _do_export(novel, dl)
    print(f"  导出完成 → app_data/exports/{group}/")


def _do_export(novel, dl):
    """执行导出（通过 NovelDownloader.export）。"""
    dl.export(novel)


def do_re_export(group: str, format_configs: dict, dl):
    """重新导出已下载的小说（不重新下载，仅从 storage 读取后导出）。"""
    storage = dl.storage
    storage_dir = APP_DATA / "storage"

    if not storage_dir.exists():
        print("未找到已下载的小说（storage 目录不存在）")
        return

    novel_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
    if not novel_dirs:
        print("未找到已下载的小说")
        return

    novels_info = []
    for d in novel_dirs:
        meta = storage.load_meta(d.name)
        if meta:
            novels_info.append(meta)

    if not novels_info:
        print("未找到有效的小说元数据")
        return

    print(f"\n找到 {len(novels_info)} 本已下载小说：")
    for i, novel in enumerate(novels_info, 1):
        print(f"  {i}. {novel.title}  — {novel.author}  [{novel.id}]")

    choices = [(f"{n.title}  — {n.author}  [{n.id}]", n) for n in novels_info]
    choices.append(("▸ 全部导出", "all"))
    choices.append(("返回", None))

    selection = _select("选择要导出的小说：", choices=choices)

    if selection is None:
        return

    targets = novels_info if selection == "all" else [selection]

    total = len(targets)
    for i, novel in enumerate(targets, 1):
        print(f"\n── [{i}/{total}] 正在导出: {novel.title} ──")
        try:
            local = storage.load_chapters(novel.id)
            if local:
                novel.update_chapter(local)
            _do_export(novel, dl)
            print(f"  导出完成 → app_data/exports/{group}/")
        except Exception as e:
            print(f"✗ 导出失败: {e}")
            _log.exception("re-export failed: %s", novel.title)

    print("\n导出完成！")


def do_delete():
    """扫描 storage 目录，选择小说并彻底删除本地数据。"""
    storage = LocalStorage(APP_DATA / "storage")
    storage_dir = APP_DATA / "storage"

    if not storage_dir.exists():
        print("未找到已下载的小说（storage 目录不存在）")
        return

    novel_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
    if not novel_dirs:
        print("未找到已下载的小说")
        return

    novels_info = []
    for d in novel_dirs:
        meta = storage.load_meta(d.name)
        if meta:
            novels_info.append(meta)

    if not novels_info:
        print("未找到有效的小说元数据")
        return

    print(f"\n找到 {len(novels_info)} 本已下载小说：")
    for i, novel in enumerate(novels_info, 1):
        print(f"  {i}. {novel.title}  — {novel.author}  [{novel.id}]")

    choices = [(f"{n.title}  — {n.author}  [{n.id}]", n) for n in novels_info]
    choices.append(("▸ 全部删除", "all"))
    choices.append(("返回", None))

    selection = _select("选择要删除的小说：", choices=choices)

    if selection is None:
        return

    targets = novels_info if selection == "all" else [selection]

    # 二次确认
    if selection == "all":
        confirm = _select(
            f"⚠ 确定要彻底删除全部 {len(targets)} 本小说的本地数据？此操作不可恢复！",
            choices=[("取消", False), ("确认删除", True)],
        )
    else:
        confirm = _select(
            f"⚠ 确定要彻底删除「{targets[0].title}」的本地数据？此操作不可恢复！",
            choices=[("取消", False), ("确认删除", True)],
        )

    if not confirm:
        print("已取消")
        return

    total = len(targets)
    for i, novel in enumerate(targets, 1):
        print(f"[{i}/{total}] 正在删除: {novel.title}...", end=" ")
        try:
            storage.delete_novel(novel.id)
            print("✓")
        except Exception as e:
            print(f"✗ 失败: {e}")
            _log.exception("delete failed: %s", novel.title)

    print(f"\n删除完成！共删除 {len(targets)} 部小说")


def do_update(engine, dl, group: str, format_configs: dict, max_workers: int = 3):
    """扫描 storage 目录下所有已下载小说，支持单选/全选更新。"""
    storage = dl.storage
    storage_dir = APP_DATA / "storage"

    if not storage_dir.exists():
        print("未找到已下载的小说（storage 目录不存在）")
        return

    novel_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
    if not novel_dirs:
        print("未找到已下载的小说")
        return

    novels_info = []
    for d in novel_dirs:
        meta = storage.load_meta(d.name)
        if meta:
            novels_info.append(meta)

    if not novels_info:
        print("未找到有效的小说元数据")
        return

    print(f"\n找到 {len(novels_info)} 本已下载小说：")
    for i, novel in enumerate(novels_info, 1):
        print(f"  {i}. {novel.title}  — {novel.author}  [{novel.id}]")

    choices = [(f"{n.title}  — {n.author}  [{n.id}]", n) for n in novels_info]
    choices.append(("▸ 全部更新", "all"))
    choices.append(("返回", None))

    selection = _select("选择要更新的小说：", choices=choices)

    if selection is None:
        return

    targets = novels_info if selection == "all" else [selection]

    total = len(targets)
    for i, novel in enumerate(targets, 1):
        print(f"\n── [{i}/{total}] 正在更新: {novel.title} ──")
        try:
            mw = cfg.get("download", {}).get("max_workers", 3)
            do_download(engine, dl, novel.url, group, format_configs, max_workers=mw)
        except AntiCrawlError:
            print("⚠ 触发反爬，更新中断（已保存部分进度）")
        except Exception as e:
            print(f"✗ 更新失败: {e}")
            _log.exception("update failed: %s", novel.title)

    print("\n更新完成！")


# ═══════════════════════════════════════════════════════════════════
# 主菜单
# ═══════════════════════════════════════════════════════════════════

def main():
    _log.info("===== novel-downloader CLI start =====")

    # 加载配置
    cfg = load_main_config()
    group = cfg.get("group", "default")
    mode = cfg.get("mode", "browser")
    platform = cfg.get("platform", "fanqie")

    site_cfg = load_site_config(platform)
    format_configs = load_format_configs()

    if not format_configs:
        _log.warning("未找到导出格式配置（app_data/config/formats/ 为空）")

    options = build_options(cfg, site_cfg)

    # 注册导出格式到 options，由 cfg.formats 控制 enabled
    enabled_formats = cfg.get("formats")
    from nldlder.utils.registry import register_export_options
    _opt_cls_map = register_export_options()
    for fmt, fmt_cfg in format_configs.items():
        opt_cls = _opt_cls_map.get(fmt)
        if opt_cls is None:
            continue
        raw_path = fmt_cfg.get("output_path", "").replace("{group}", group)
        extra = {k: fmt_cfg[k] for k in (
            "encoding", "file_name_template",
            "css_style", "include_toc",
        ) if k in fmt_cfg}
        opt = opt_cls(output_path=raw_path, **extra)
        options.set_export_options(opt)

    # cfg.formats 控制哪些格式启用（None/"all" = 全部启用）
    if enabled_formats and enabled_formats != "all":
        for fmt in format_configs:
            options.enable_format(fmt, enabled=(fmt in enabled_formats))

    # 延迟初始化引擎和下载器（首次使用时创建）
    print(f"平台: {platform}  |  模式: {mode}  |  分组: {group}")
    engine = None
    dl = None

    def _get_engine_dl():
        nonlocal engine, dl
        if engine is None:
            _log.debug("creating engine: mode=%s", mode)
            e = create_engine(options)
            d = NovelDownloader(e, options=options)
            engine, dl = e, d
        return engine, dl

    platform_labels = _show_platforms()

    try:
        while True:
            platform_label = platform_labels.get(platform, platform)

            # 平台选择行
            platform_choices = []
            for label, name in platform_labels.items():
                prefix = "▸ " if name == platform else "  "
                platform_choices.append((f"{prefix}{label}", name))

            action = _select(
                f"平台: {platform_label}  |  分组: {group}  |  模式: {mode}",
                choices=[
                    ("切换平台", "switch_platform"),
                    ("登录", "login"),
                    ("下载（搜索或输入 URL）", "download"),
                    ("更新已下载", "update"),
                    ("重新导出", "re_export"),
                    ("删除小说", "delete"),
                    ("设置", "settings"),
                    ("退出", "quit"),
                ],
            )

            if action is None or action == "quit":
                break

            elif action == "switch_platform":
                new_platform = _select(
                    "选择平台：",
                    choices=[(label, name) for label, name in platform_labels.items()] + [("取消", None)],
                )
                if new_platform and new_platform != platform:
                    platform = new_platform
                    site_cfg = load_site_config(platform)
                    options = build_options(cfg, site_cfg)
                    if engine is not None:
                        engine.close()
                    engine, dl = None, None
                    print(f"✓ 已切换到: {platform_labels.get(platform, platform)}")

            elif action == "login":
                do_login(platform)

            elif action == "settings":
                old_platform = platform
                platform = do_settings(cfg, platform, site_cfg)
                if platform != old_platform:
                    site_cfg = load_site_config(platform)
                    options = build_options(cfg, site_cfg)
                    if engine is not None:
                        engine.close()
                    engine, dl = None, None
                else:
                    options = build_options(cfg, site_cfg)
                    if engine is not None:
                        engine.close()
                    engine, dl = None, None
                print("✓ 设置已应用")

            elif action == "download":
                raw = _text_input("请输入小说链接、novel_id 或搜索关键词：")
                if not raw or not raw.strip():
                    continue

                raw = raw.strip()

                # URL 或 novel_id → 直接下载
                if raw.startswith("http://") or raw.startswith("https://"):
                    url = raw
                elif get_fetcher_for_id(raw):
                    print(f"  识别为 novel_id，平台: {get_fetcher_for_id(raw).__name__}")
                    url = _build_url_from_id(raw)
                else:
                    url = None

                if url:
                    try:
                        e, d = _get_engine_dl()
                        mw = cfg.get("download", {}).get("max_workers", 3)
                        do_download(e, d, url, group, format_configs, max_workers=mw)
                    except AntiCrawlError:
                        print("⚠ 触发反爬，下载中断（已保存部分进度）")
                    except Exception as e:
                        print(f"✗ 下载失败: {e}")
                        _log.exception("download failed")
                else:
                    # 作为搜索关键词
                    try:
                        e, d = _get_engine_dl()
                        url = do_search(e, d, platform, query=raw)
                    except Exception as e:
                        print(f"✗ 搜索失败: {e}")
                        url = None
                    if url:
                        try:
                            e, d = _get_engine_dl()
                            mw = cfg.get("download", {}).get("max_workers", 3)
                            do_download(e, d, url, group, format_configs, max_workers=mw)
                        except AntiCrawlError:
                            print("⚠ 触发反爬，下载中断（已保存部分进度）")
                        except Exception as e:
                            print(f"✗ 下载失败: {e}")
                            _log.exception("download failed")

            elif action == "re_export":
                try:
                    e, d = _get_engine_dl()
                    do_re_export(group, format_configs, d)
                except Exception as e:
                    print(f"✗ 导出失败: {e}")
                    _log.exception("re_export failed")

            elif action == "delete":
                try:
                    do_delete()
                except Exception as e:
                    print(f"✗ 删除失败: {e}")
                    _log.exception("delete failed")

            elif action == "update":
                try:
                    e, d = _get_engine_dl()
                    mw = cfg.get("download", {}).get("max_workers", 3)
                    do_update(e, d, group, format_configs, max_workers=mw)
                except Exception as e:
                    print(f"✗ 更新失败: {e}")
                    _log.exception("update failed")

            print()  # 空行分隔

    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        if engine is not None:
            engine.close()
        _log.info("===== novel-downloader CLI end =====")


if __name__ == "__main__":
    main()

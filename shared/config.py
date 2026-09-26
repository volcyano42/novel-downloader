# shared/config.py
"""配置加载 — 单一数据源：默认值从 novelbase.core.options 派生。"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import MISSING, fields
from pathlib import Path

import yaml

from novelbase.core.options import BrowserOptions, RequestsOptions


# ── 路径 ──
def _get_app_data_dir() -> Path:
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        app_data = exe_dir / "app_data"
        if not app_data.exists():
            meipass = Path(sys._MEIPASS)
            src = meipass / "app_data"
            if src.exists():
                try:
                    _copy_dir(src, app_data)
                except (OSError, PermissionError):
                    app_data.mkdir(parents=True, exist_ok=True)
            else:
                app_data.mkdir(parents=True, exist_ok=True)
        return app_data
    return Path(__file__).resolve().parent.parent / "app_data"

def _copy_dir(src: Path, dst: Path, _max_depth: int = 10) -> None:
    if _max_depth < 0:
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_dir(item, target, _max_depth - 1)
        elif not target.exists():
            shutil.copy2(item, target)

APP_DATA = _get_app_data_dir()
CONFIG_DIR = APP_DATA / "config"

# ── 默认值单一数据源：从 dataclass 字段默认值派生 ──
def _dataclass_defaults(cls) -> dict:
    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:
            result[f.name] = f.default_factory()
    return result

ENGINE_DEFAULTS = {
    "browser": _dataclass_defaults(BrowserOptions),
    "requests": _dataclass_defaults(RequestsOptions),
    "api": {},
}

# dataclass 默认用 None 表示「空」，而真实书源的 source.json 用 ""/{}/[]。
# 脚手架产物必须与真实书源字面同构（spec §4.3(b)），故按字段给出对应空值。
_BLANK_BY_FIELD: dict[str, object] = {
    "user_data_dir": "",
    "key": "",
    "viewport": {},
    "cookies": {},
    "proxies": {},
    "params": {},
    "extra_args": [],
}


def _normalize_blank(key: str, value):
    """dataclass 的 None 默认 → 真实 source.json 使用的空值（可变容器浅拷贝，避免共享）。"""
    if value is not None:
        return value
    blank = _BLANK_BY_FIELD.get(key)
    if isinstance(blank, dict):
        return dict(blank)
    if isinstance(blank, list):
        return list(blank)
    return blank


def _normalize_delay(value):
    """真实书源的 delay 写成整数列表 `[0, 0]`；dataclass 默认是 `(0.0, 0.0)`。

    仅作 JSON 字面归一（不影响三级合并路径——`merged_source_config` 直读
    `ENGINE_DEFAULTS`，不经过本函数）。
    """
    if isinstance(value, (list, tuple)):
        return [int(x) for x in value]
    return value


def mode_defaults(mode: str) -> dict:
    """该 mode 的出厂默认字段（系统默认层），供脚手架生成 `source.json.common`。

    `ENGINE_DEFAULTS["api"]` 是空 dict（api 的 Options 由 `set_api_options` 单独消费），
    脚手架需要 key/params——这里从 `APIOptions` 的 dataclass 默认派生，**不改
    `ENGINE_DEFAULTS`**（避免影响 `merged_source_config` 的三层合并结果）。
    """
    if mode == "api":
        from novelbase.core.options import APIOptions
        defaults: dict = _dataclass_defaults(APIOptions)
    else:
        defaults = dict(ENGINE_DEFAULTS.get(mode, {}))
    return {
        k: (_normalize_delay(v) if k == "delay" else _normalize_blank(k, v))
        for k, v in defaults.items()
    }


GLOBAL_DEFAULTS = {
    "max_workers": 3,
    "notify": {"on_complete": True, "on_incomplete": True, "sound": "bell"},
}

FMT_DEFAULTS = {
    "txt": {"enabled": True, "encoding": "utf-8"},
    "epub": {"enabled": True, "compression": "deflate", "compresslevel": 9,
             "optimize_images": True, "jpeg_quality": 85, "max_image_width": 0, "include_toc": True},
    "img": {"enabled": True, "output_format": "original"},
}

# ── 工具 ──
def deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_yaml(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)

def _resolve_paths(value):
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

# ── config.yaml ──
def load_main_config():
    path = CONFIG_DIR / "config.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def load_config() -> dict:
    """别名，兼容 backend 路由的旧调用名。"""
    return load_main_config()

def save_main_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "config.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

# ── sites ──
def load_site_config(platform):
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def save_site_config(platform, site_cfg):
    (CONFIG_DIR / "sites").mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "sites" / f"{platform}.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(site_cfg, f, allow_unicode=True, default_flow_style=False)

def _user_site_cfg(source_name: str) -> dict:
    """读取用户层 sites/{source_name}.yaml（原始 dict，不做 app_data 路径解析）。"""
    return load_yaml(CONFIG_DIR / "sites" / f"{source_name}.yaml")


VALID_MODES = ("browser", "requests", "api")


def effective_capabilities(source_name: str) -> dict[str, str]:
    """有效 mode 映射：用户层 `sites/{source_name}.yaml` 的 `{cap}.mode` 覆盖 `source.json` 声明。

    - 未覆盖 / 覆盖值非法（不在 `VALID_MODES`）→ 取书源声明
    - 未知书源 → `{}`（与 `capabilities()` 的宽容语义一致）
    """
    from novelbase.source import capabilities
    declared = capabilities(source_name)
    if not declared:
        return {}
    user = _user_site_cfg(source_name)
    out: dict[str, str] = {}
    for cap, mode in declared.items():
        section = user.get(cap) if isinstance(user.get(cap), dict) else {}
        override = section.get("mode")
        out[cap] = override if override in VALID_MODES else mode
    return out


def merged_source_config(source_name: str) -> dict[str, dict]:
    """三层合并某书源的逐能力配置。

    返回 `{capability: 该能力段三层合并后的完整字段}`；未知书源返回 `{}`。
    三层：ENGINE_DEFAULTS[mode]（系统默认）→ `source.json.default_config[cap]`（书源出厂，
    已含 `common` 合并）→ `sites/{source_name}.yaml[cap]`（用户层）。
    **mode 取有效值**（`effective_capabilities()`：用户层 `{cap}.mode` 覆盖声明），
    且用户层的 `mode` 键**保留**在输出中（前端表单需回显）。
    不变量：输出的 `mode` **恒等于有效 mode**（`effective_capabilities()[cap]`），
    用户层的 `mode` 键（含非法值 / YAML `null`）不参与覆盖。
    """
    from novelbase.source import get_manifest
    caps = effective_capabilities(source_name)
    if not caps:
        return {}
    manifest = get_manifest(source_name)
    user = _user_site_cfg(source_name)
    out: dict[str, dict] = {}
    for cap, mode in caps.items():
        base = deep_merge(ENGINE_DEFAULTS.get(mode, {}), manifest["default_config"][cap])
        base["mode"] = mode  # 不变量：base 已写入有效 mode
        user_cap = user.get(cap) if isinstance(user.get(cap), dict) else {}
        # 用户层 mode 键不再参与覆盖（否则非法值 / None 会污染有效 mode 与字段集的
        # 一致性：该段字段集按有效 mode 构建，mode 也必须等于有效 mode）。
        user_cap = {k: v for k, v in user_cap.items() if k != "mode"}
        out[cap] = deep_merge(base, user_cap)
    return out


def is_source_enabled(source_name: str) -> bool:
    """书源是否启用：用户层顶层 `enabled` 覆盖 `source.json` 的出厂值。"""
    from novelbase.source import get_manifest
    user = _user_site_cfg(source_name)
    if isinstance(user.get("enabled"), bool):
        return user["enabled"]
    return bool(get_manifest(source_name).get("enabled", False))


SOURCE_CONCURRENCY_DEFAULT = 1


def _is_positive_int(value) -> bool:
    """非 bool 的正整数（bool 是 int 子类，须排除，避免 True 被当作 1）。"""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def source_concurrency(source_name: str) -> int:
    """该书源的并发额度：用户层顶层 `concurrency` 覆盖 `source.json` 顶层，缺省 1。

    非法值（非正整数）忽略并回退默认；未知书源同样返回默认。
    """
    from novelbase.source import get_manifest
    from novelbase.sources.manifest import ManifestError

    user = _user_site_cfg(source_name)
    if _is_positive_int(user.get("concurrency")):
        return user["concurrency"]
    try:
        declared = get_manifest(source_name).get("concurrency")
    except (KeyError, ManifestError):
        return SOURCE_CONCURRENCY_DEFAULT
    return declared if _is_positive_int(declared) else SOURCE_CONCURRENCY_DEFAULT


def enabled_source_names() -> list[str]:
    """排序后的启用书源 source_name 列表（「启用集」的唯一入口）。

    = 「用户层 / 出厂 `enabled`」。
    """
    from novelbase.source import list_sources
    return sorted(n for n in list_sources() if is_source_enabled(n))

# ── formats ──
def load_format_configs():
    result = {}
    for fmt_key, defaults in FMT_DEFAULTS.items():
        raw = load_yaml(CONFIG_DIR / "formats" / f"{fmt_key}.yaml")
        fmt_data = raw.get(fmt_key, {}) if isinstance(raw, dict) else {}
        result[fmt_key] = deep_merge(defaults, fmt_data)
    return result

def save_format_config(fmt_key, data):
    save_yaml(CONFIG_DIR / "formats" / f"{fmt_key}.yaml", {fmt_key: data})

def save_fmt_config(fmt_name, data):
    (CONFIG_DIR / "formats").mkdir(parents=True, exist_ok=True)
    save_yaml(CONFIG_DIR / "formats" / f"{fmt_name}.yaml", data)

def load_fmt_config(fmt_name):
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

# ── 数据库 URL ──
def get_database_url():
    # database_url 充当"目录定位器"：SQLiteStorage 取 parent 作为 base_dir，
    # 文件本身（.dir 占位）从不创建，真正的库是 base_dir 下每本小说的 <id>.db。
    return f"sqlite:///{APP_DATA / 'storage' / 'novels' / '.dir'}"

# ── build_options（按 source_name + mode 从三层合并配置组 Options）──
def build_options(source_name: str, mode: str) -> Options:
    """按书源名 + mode 组 Options，字段取自 `merged_source_config(source_name)` 的对应能力段。

    能力段由 mode 反查（`effective_capabilities(source_name)` 里 mode 匹配的能力段；一个
    书源的各能力段通常同 mode）。未知书源 / 无匹配段时退回 `ENGINE_DEFAULTS[mode]`。
    """
    from novelbase.core.options import Options

    merged = merged_source_config(source_name)
    caps = effective_capabilities(source_name)
    cfg: dict = {}
    for cap, cap_mode in caps.items():
        if cap_mode == mode:
            cfg = merged.get(cap, {})
            break
    if not cfg:
        cfg = dict(ENGINE_DEFAULTS.get(mode, {}))

    options = Options().set_mode(mode)
    if mode == "browser":
        user_data_dir = cfg.get("user_data_dir", "")
        if user_data_dir:
            ud_path = Path(user_data_dir)
            if not ud_path.is_absolute():
                ud_path = Path(__file__).parent.parent / ud_path
        else:
            ud_path = None
        options.set_browser_options(
            headless=cfg.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            delay=tuple(cfg.get("delay", [0, 0])),
            viewport=cfg.get("viewport"),
            auto_reconnect=cfg.get("auto_reconnect", False),
        )
    elif mode == "api":
        options.set_api_options(
            key=cfg.get("key", ""),
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            delay=tuple(cfg.get("delay", [0, 0])),
            params=cfg.get("params", {}),
        )
    elif mode == "requests":
        cookies_val = cfg.get("cookies")
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
            headers=cfg.get("headers"),
            cookies=cookies_val,
            proxies=cfg.get("proxies"),
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            delay=tuple(cfg.get("delay", [0, 0])),
        )

    options.set_storage_options(backend="sqlite", database_url=get_database_url())
    return options

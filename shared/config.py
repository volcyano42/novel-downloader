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
from novelbase.source import add_source_root as _add_source_root
from shared.paths import exe_dir


# ── 路径 ──
def _get_app_data_dir() -> Path:
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    compiled_dir = exe_dir()          # Nuitka（__compiled__）/ PyInstaller（sys.frozen）
    if compiled_dir is not None:
        app_data = compiled_dir / "app_data"
        if not app_data.exists():
            # PyInstaller 一次性包内默认配置（Nuitka 产物不带 app_data，直接建目录）
            meipass = getattr(sys, "_MEIPASS", None)
            src = Path(meipass) / "app_data" if meipass else None
            if src is not None and src.exists():
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


def user_sources_dir() -> Path:
    """用户书源根：`<APP_DATA>/sources`（懒创建，与 `library/` 同约定）。

    把源目录解压进去即生效，无需环境变量、无需重装——这是「书源与 core
    结构分离」后官方源之外的正规扩展入口。
    """
    return APP_DATA / "sources"


# 把用户源根接入 novelbase 的发现层（shared → novelbase 单向依赖）。
# novelbase 不认识 app_data 布局，也不反向 import shared，保持可 pip install 的纯库定位。
_add_source_root(user_sources_dir())

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

# ── sources ──
def load_source_config(source_name):
    path = CONFIG_DIR / "sources" / f"{source_name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def save_source_config(source_name, source_cfg):
    (CONFIG_DIR / "sources").mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "sources" / f"{source_name}.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(source_cfg, f, allow_unicode=True, default_flow_style=False)

def _user_source_cfg(source_name: str) -> dict:
    """读取用户层 sources/{source_name}.yaml（原始 dict，不做 app_data 路径解析）。"""
    return load_yaml(CONFIG_DIR / "sources" / f"{source_name}.yaml")


VALID_MODES = ("browser", "requests", "api")

# 用户层 yaml 的顶层「元数据」键：不是引擎参数，不参与引擎字段合并。
# 2026-10-25 起一个书源只有一个 mode 和一套参数（不再按能力分化），
# 所以引擎参数的来源就是 yaml 顶层（除去这几个键）。
_SOURCE_META_KEYS = frozenset({"source_group", "source_alias", "concurrency", "enabled", "mode"})


def effective_capabilities(source_name: str) -> dict[str, str]:
    """有效 mode 映射：用户层 `sources/{source_name}.yaml` 顶层 `mode` 覆盖 `source.json` 声明。

    **一个书源只有一个 mode，所有能力共享**（不再按能力分化）。返回形状仍是
    `{capability: mode}`（所有值相同），以保持公共 API 稳定。

    - 未覆盖 / 覆盖值非法（不在 `VALID_MODES`）→ 取书源声明
    - 未知书源 → `{}`（与 `capabilities()` 的宽容语义一致）
    """
    from novelbase.source import capabilities
    declared = capabilities(source_name)
    if not declared:
        return {}
    override = _user_source_cfg(source_name).get("mode")
    mode = override if override in VALID_MODES else next(iter(declared.values()))
    return {cap: mode for cap in declared}


def merged_source_config(source_name: str) -> dict[str, dict]:
    """三层合并某书源的配置。

    返回 `{capability: 完整字段}`；未知书源返回 `{}`。

    **2026-10-25 起书源只有一个 mode 和一套参数，不再按能力分化**，所以每个能力
    拿到的字段完全相同；保留 `{capability: …}` 形状只是为了让下游按能力取用的
    写法不必改动。

    三层（优先级从低到高）：
    `ENGINE_DEFAULTS[mode]` → `source.json` 顶层字段 → `sources/{source_name}.yaml` 顶层字段。

    不变量：输出的 `mode` 恒等于 `effective_capabilities()[cap]`，用户层的 `mode`
    （含非法值 / YAML `null`）不参与字段覆盖。
    """
    from novelbase.source import get_manifest
    caps = effective_capabilities(source_name)
    if not caps:
        return {}
    manifest = get_manifest(source_name)
    user = _user_source_cfg(source_name)
    user_fields = {k: v for k, v in user.items() if k not in _SOURCE_META_KEYS}
    out: dict[str, dict] = {}
    for cap, mode in caps.items():
        base = deep_merge(ENGINE_DEFAULTS.get(mode, {}), manifest["default_config"][cap])
        base["mode"] = mode  # 不变量：base 已写入有效 mode
        out[cap] = deep_merge(base, user_fields)
    return out


def _user_top(source_name: str, key: str) -> str:
    """用户层顶层字符串字段（strip 后）；非字符串 / 缺失 → ""。"""
    value = _user_source_cfg(source_name).get(key)
    return value.strip() if isinstance(value, str) else ""


def _declared_top(source_name: str, key: str) -> str:
    """出厂 `source.json` 顶层字符串字段；缺失 / manifest 异常 / 非字符串 → ""。"""
    from novelbase.source import get_manifest
    from novelbase.sources.manifest import ManifestError
    try:
        value = get_manifest(source_name).get(key)
    except (KeyError, ManifestError):
        return ""
    return value.strip() if isinstance(value, str) else ""


def source_group(source_name: str) -> str:
    """书源分组名：用户层顶层 `source_group` → 出厂 `source.json` 顶层 → `""`（未分组）。

    空串视为「未设」（PUT 用空串表达「清除覆盖」），故 `or` 短路即可。
    """
    return _user_top(source_name, "source_group") or _declared_top(source_name, "source_group")


def source_alias(source_name: str) -> str:
    """书源别名：用户层顶层 `source_alias` → 出厂 `source.json` 顶层 → `""`（未设）。"""
    return _user_top(source_name, "source_alias") or _declared_top(source_name, "source_alias")


def display_name(source_name: str) -> str:
    """显示名（CLI / 日志的唯一入口）：别名优先，未设则回落 `source_name`。"""
    return source_alias(source_name) or source_name


def default_source_names() -> list[str]:
    """默认参与集：**全部**书源（无任何环境相关过滤）。

    历史：曾按 「用户层 / 出厂 `enabled`」的启用集过滤，该机制已随 spec D1/D2
    废弃并删除；「本环境不支持的引擎」这一维度也随 v4.5.1 移除 Android 套壳而消失。
    """
    from novelbase.source import list_sources
    return sorted(list_sources())


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

    user = _user_source_cfg(source_name)
    if _is_positive_int(user.get("concurrency")):
        return user["concurrency"]
    try:
        declared = get_manifest(source_name).get("concurrency")
    except (KeyError, ManifestError):
        return SOURCE_CONCURRENCY_DEFAULT
    return declared if _is_positive_int(declared) else SOURCE_CONCURRENCY_DEFAULT


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
                # 相对路径：`app_data/...` 前缀映射到真实 APP_DATA（对齐 cli/config.py::_resolve_paths），
                # 其余相对路径按 app_data 的父目录（源码运行=仓库根，编译产物=exe 同目录）解析。
                # ⚠️ 不要用 `Path(__file__).parent.parent`：Nuitka onefile 下 `__file__` 在临时解包目录，
                # 会让浏览器 profile 落到临时目录 —— 登录态每次启动重置（该 bug 曾在 dev 下修过一次）。
                raw = ud_path.as_posix()
                if raw.startswith("app_data/"):
                    ud_path = APP_DATA / raw[len("app_data/"):]
                else:
                    ud_path = APP_DATA.parent / ud_path
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

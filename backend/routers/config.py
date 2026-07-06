"""Config 路由 — 读写 app_data/config/config.yaml，暴露全部引擎/格式/输出参数。"""
from pathlib import Path
import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["config"])

_config_dir = Path(__file__).parent.parent.parent / "app_data" / "config"

# ── 默认值 ──────────────────────────────────────────────

_DEFAULTS = {
    "name": "Novel下载器",
    "mode": "browser",
    "max_workers": 5,
    "log_level": "INFO",
    "output_path": "app_data/exports/{group}/{title}",
    "file_template": "{title}",
    "browser": {
        "headless": True,
        "browser_type": "chromium",
        "user_data_dir": "app_data/browser/Chromium/User Data",
        "delay": [3.0, 5.0],
        "timeout": 30.0,
        "retry_times": 3,
        "backoff_factor": 2.0,
    },
    "requests": {
        "delay": [3.0, 5.0],
        "timeout": 30.0,
        "retry_times": 3,
        "backoff_factor": 2.0,
    },
    "api": {
        "delay": [3.0, 5.0],
        "timeout": 30.0,
        "retry_times": 3,
        "backoff_factor": 2.0,
    },
    "txt": {
        "enabled": True,
        "encoding": "utf-8",
        "output_path": "app_data/exports/{name}",
        "file_name_template": "{name}",
    },
    "epub": {
        "enabled": True,
        "compression": "deflate",
        "compresslevel": 9,
        "optimize_images": True,
        "jpeg_quality": 85,
        "max_image_width": 0,
        "include_toc": True,
        "output_path": "app_data/exports/{name}",
        "file_name_template": "{name}",
    },
    "img": {
        "enabled": True,
        "output_format": "original",
        "output_path": "app_data/exports/{name}",
        "file_name_template": "{n}",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并 override 到 base，返回新 dict。"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(name: str) -> dict:
    path = _config_dir / name
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    return _load_yaml("config.yaml")

def _api_providers() -> dict[str, list[str]]:
    """返回每个平台启用的 API 提供商。"""
    sites_dir = _config_dir / "sites"
    result: dict[str, list[str]] = {}
    if not sites_dir.is_dir():
        return result
    for p in sites_dir.glob("*.yaml"):
        site = p.stem
        cfg = _load_yaml(f"sites/{site}.yaml")
        api = cfg.get("api", {}) if isinstance(cfg.get("api"), dict) else {}
        providers = [k for k, v in api.items() if isinstance(v, dict)]
        if providers:
            result[site] = providers
    return result


# ── GET — 扁平化返回全部参数 ──────────────────────────────

@router.get("")
async def get_config():
    raw = load_config()
    log = raw.get("log", {}) or {}
    dl = raw.get("download", {}) or {}
    out = raw.get("output", {}) or {}
    fmts = raw.get("formats", {}) or {}

    def _fmt(key: str) -> dict:
        return _deep_merge(_DEFAULTS[key], fmts.get(key, {}))

    def _engine(key: str) -> dict:
        return _deep_merge(_DEFAULTS[key], dl.get(key, {}))

    return {
        "name": raw.get("name", _DEFAULTS["name"]),
        "mode": raw.get("mode", _DEFAULTS["mode"]),
        "max_workers": dl.get("max_workers", _DEFAULTS["max_workers"]),
        "log_level": log.get("level", _DEFAULTS["log_level"]),
        "output_path": out.get("path", _DEFAULTS["output_path"]),
        "file_template": out.get("file_template", _DEFAULTS["file_template"]),
        "browser": _engine("browser"),
        "requests": _engine("requests"),
        "api": _engine("api"),
        "txt": _fmt("txt"),
        "epub": _fmt("epub"),
        "img": _fmt("img"),
        "api_providers": _api_providers(),
        "groups": _load_yaml("groups.yaml"),
    }


# ── PUT — 扁平入，嵌套写回 YAML ────────────────────────────

@router.put("")
async def save_config(body: dict):
    raw = load_config()

    # 顶层标量
    for key in ("name", "mode"):
        if key in body:
            raw[key] = body[key]

    # download 块
    dl = raw.setdefault("download", {})
    if "max_workers" in body:
        dl["max_workers"] = body["max_workers"]
    for engine in ("browser", "requests", "api"):
        if engine in body and isinstance(body[engine], dict):
            dl[engine] = _deep_merge(dl.get(engine, {}), body[engine])

    # formats 块
    fmts = raw.setdefault("formats", {})
    for fmt_key in ("txt", "epub", "img"):
        if fmt_key in body and isinstance(body[fmt_key], dict):
            fmts[fmt_key] = _deep_merge(fmts.get(fmt_key, {}), body[fmt_key])

    # log 块
    if "log_level" in body:
        raw.setdefault("log", {})["level"] = body["log_level"]

    # output 块
    out = raw.setdefault("output", {})
    if "output_path" in body:
        out["path"] = body["output_path"]
    if "file_template" in body:
        out["file_template"] = body["file_template"]

    with open(_config_dir / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, default_flow_style=False)
    return {"status": "ok"}

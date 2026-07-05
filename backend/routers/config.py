"""Config 路由 — 读取 app_data/config/ 下的配置文件。"""
from pathlib import Path
import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["config"])

_config_dir = Path(__file__).parent.parent.parent / "app_data" / "config"

def _load_yaml(name: str) -> dict:
    path = _config_dir / name
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}

def load_config() -> dict:
    return _load_yaml("config.yaml")

@router.get("")
async def get_config():
    cfg = load_config()
    return {
        "name": cfg.get("name", "Novel下载器"),
        "platform": cfg.get("platform", "fanqie"),
        "mode": cfg.get("mode", "browser"),
        "formats": cfg.get("formats", ["txt"]),
        "max_workers": cfg.get("download", {}).get("max_workers", 1) if isinstance(cfg.get("download"), dict) else 1,
        "groups": _load_yaml("groups.yaml"),
    }

"""Config 路由 — 读取 app_data/config/config.yaml。"""
from pathlib import Path
import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["config"])

_config_path = Path(__file__).parent.parent.parent / "app_data" / "config" / "config.yaml"

def load_config() -> dict:
    if not _config_path.exists():
        return {}
    with open(_config_path) as f:
        return yaml.safe_load(f) or {}

@router.get("")
async def get_config():
    cfg = load_config()
    return {
        "name": cfg.get("name", "Novel下载器"),
        "platform": cfg.get("platform", "fanqie"),
        "mode": cfg.get("mode", "browser"),
        "formats": cfg.get("formats", ["txt"]),
        "max_workers": cfg.get("download", {}).get("max_workers", 1) if isinstance(cfg.get("download"), dict) else 1,
    }

"""配置初始化 — 从 template/config/（默认）复制到 app_data/config/（运行时）。

设计：
  template/config/  ← 默认配置模板，跟随代码版本（跨 CLI/WebUI 共用）
  app_data/config/  ← 运行时配置，用户可修改，gitignored
"""
import os
import shutil
import sys
from pathlib import Path


def _get_root() -> Path:
    """应用根目录，兼容 PyInstaller / Nuitka / 源码运行。"""
    if getattr(sys, "frozen", False):                     # PyInstaller
        return Path(sys._MEIPASS)
    if "__compiled__" in globals():                       # Nuitka
        return Path(os.path.dirname(os.path.abspath(__file__)))
    return Path(__file__).resolve().parent                # dev


def _template_dir() -> Path:
    """模板源目录。"""
    return _get_root() / "template" / "config"


def _target_dir() -> Path:
    """运行时目标目录。优先 NLD_APP_DATA env；frozen/compiled → exe 同目录；dev → 项目根。"""
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve() / "config"
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.executable).parent / "app_data" / "config"
    return Path(__file__).resolve().parent / "app_data" / "config"


def _user_db_target_dir() -> Path:
    """user_data.db 运行时目标目录（storage/users/default/）。"""
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve() / "storage" / "users" / "default"
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.executable).parent / "app_data" / "storage" / "users" / "default"
    return Path(__file__).resolve().parent / "app_data" / "storage" / "users" / "default"


# ═══════════════════════════════════════════════════
# 检查
# ═══════════════════════════════════════════════════

def check_config() -> dict:
    """检查 app_data/config/ 配置完整性。

    Returns:
        {'missing': ['sites/fanqie.yaml', ...], 'all_missing': True/False}
    """
    template = _template_dir()
    target = _target_dir()
    missing: list[str] = []

    # 主配置（groups 已迁移到 user_data.db，不再复制 groups.yaml）
    for name in ("config.yaml",):
        if not (target / name).exists() and (template / name).exists():
            missing.append(name)

    # 站点配置
    tmpl_sites = template / "sites"
    tgt_sites = target / "sites"
    if tmpl_sites.is_dir():
        for f in tmpl_sites.glob("*.yaml"):
            if not (tgt_sites / f.name).exists():
                missing.append(f"sites/{f.name}")

    # 格式配置
    tmpl_fmts = template / "formats"
    tgt_fmts = target / "formats"
    if tmpl_fmts.is_dir():
        for f in tmpl_fmts.glob("*.yaml"):
            if not (tgt_fmts / f.name).exists():
                missing.append(f"formats/{f.name}")

    # 统计模板文件总数判断是否全部缺失
    total_tmpl = sum(1 for _ in template.rglob("*.yaml"))
    all_missing = total_tmpl > 0 and len(missing) == total_tmpl

    return {"missing": missing, "all_missing": all_missing}


# ═══════════════════════════════════════════════════
# 初始化（不检查，直接复制）
# ═══════════════════════════════════════════════════

def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def init_main_config() -> list[str]:
    """初始化 config.yaml（groups 已迁移到 user_data.db）。"""
    template = _template_dir()
    target = _target_dir()
    initialized: list[str] = []
    for name in ("config.yaml",):
        src = template / name
        dst = target / name
        if src.exists():
            _copy_file(src, dst)
            initialized.append(str(dst))
    return initialized


def init_site_config(platform: str) -> list[str]:
    """初始化 sites/{platform}.yaml。platform="all" 初始化全部。"""
    template = _template_dir() / "sites"
    target = _target_dir() / "sites"
    initialized: list[str] = []
    if not template.is_dir():
        return initialized
    files = (
        list(template.glob("*.yaml"))
        if platform == "all"
        else [template / f"{platform}.yaml"]
    )
    for src in files:
        if src.exists():
            _copy_file(src, target / src.name)
            initialized.append(str(target / src.name))
    return initialized


def init_export_config(format: str) -> list[str]:
    """初始化 formats/{format}.yaml。format="all" 初始化全部。"""
    template = _template_dir() / "formats"
    target = _target_dir() / "formats"
    initialized: list[str] = []
    if not template.is_dir():
        return initialized
    files = (
        list(template.glob("*.yaml"))
        if format == "all"
        else [template / f"{format}.yaml"]
    )
    for src in files:
        if src.exists():
            _copy_file(src, target / src.name)
            initialized.append(str(target / src.name))
    return initialized


def init_user_db() -> list[str]:
    """初始化 user_data.db 空表模板（storage/users/default/，不存在才复制）。

    模板由 shared/user_data.py 的 _SCHEMA_SQL 生成（四张空表），运行时
    user_data.py 的 _ensure_schema 兜底建表（CREATE TABLE IF NOT EXISTS 幂等）。
    """
    template = _get_root() / "template" / "storage" / "users" / "default" / "user_data.db"
    dst = _user_db_target_dir() / "user_data.db"
    if template.exists() and not dst.exists():
        _copy_file(template, dst)
        return [str(dst)]
    return []


def init_all_config() -> list[str]:
    """初始化全部（main + all sites + all formats + user_data.db 模板）。"""
    result: list[str] = []
    result.extend(init_main_config())
    result.extend(init_site_config("all"))
    result.extend(init_export_config("all"))
    result.extend(init_user_db())
    return result

"""配置初始化 — 从 app/config/（默认）复制到 app_data/config/（运行时）。

设计：
  app/config/        ← 默认配置模板，跟随代码版本
  app_data/config/   ← 运行时配置，用户可修改，gitignored

初始化时只创建不覆盖 — 已有的用户配置不会被修改。
之后会链接到 main.py，在启动时自动执行。
"""
from pathlib import Path
import shutil
import sys


def _project_root() -> Path:
    """返回项目根目录（app/ 的父目录）。"""
    return Path(__file__).resolve().parent.parent


def init_config(force: bool = False) -> list[str]:
    """初始化 app_data/config/。

    从 app/config/ 复制文件到 app_data/config/。
    默认不覆盖已有文件（force=True 可强制覆盖）。

    Returns:
        已初始化的文件路径列表（相对于项目根目录）。
    """
    root = _project_root()
    template_dir = root / "app" / "config"
    target_dir = root / "app_data" / "config"

    initialized: list[str] = []

    for src in template_dir.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(template_dir)
        dst = target_dir / rel
        if dst.exists() and not force:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        initialized.append(str(Path("app_data/config") / rel))

    return initialized


def main():
    """命令行入口 — python -m app.init_config [--force]"""
    force = "--force" in sys.argv
    files = init_config(force=force)
    action = "强制覆盖" if force else "初始化"
    if files:
        print(f"{action}完成 ({len(files)}):")
        for f in files:
            print(f"  {f}")
    else:
        print("配置已存在，跳过（使用 --force 强制覆盖）")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""把**不能公开**的书源从仓库搬到用户源根 `<APP_DATA>/sources/`。

与 `migrate_sources_to_builtin.py` 的分工：

| 脚本 | 动作 | 目的 |
|---|---|---|
| `migrate_sources_to_builtin.py` | `novelbase/sources/{dir}` → `novelbase/sources/builtin/{dir}` | **结构**分离（官方源收进 builtin，随包发行） |
| 本脚本 | `novelbase/sources/builtin/{dir}` → `<APP_DATA>/sources/{dir}` | **合规**分离（敏感源出仓，不进任何仓库） |

搬走的源仍可用——`<APP_DATA>/sources` 是标准用户源根，由 `shared.config` 注册，
加载路径与官方源完全相同。默认 dry-run，`--apply` 才动盘。

名单依据 `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 与
`PUBLIC_MANIFEST.md` 的红名单（7 个源）；残留的 3 个（`fanqie_requests_default` /
`fanqie_browser_default` / `fanqie_api_oiapi`）留在 `builtin/` 随包公开。

迁移后需要一起处理（否则仓库自测会红）：

- `tests/conftest.py` 的 `PRIVATE_SOURCE_DIRS` 缺席跳过机制
- `template/config/sources/{name}.yaml` 的 7 份种子配置
- `pyproject.toml` / `PUBLIC_MANIFEST.md` 里这 7 条 exclude 的语义（文件已在仓库外）

用法::

    python scripts/migrate_private_sources_out.py            # 只看计划
    python scripts/migrate_private_sources_out.py --apply    # 执行
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUILTIN_DIR = REPO_ROOT / "novelbase" / "sources" / "builtin"
MANIFEST_NAME = "source.json"

# 不能进公开仓库的源（逆向/破解实现、第三方代理直取平台内容）。
# 与 pyproject.toml [tool.novel-downloader.migration] exclude 的 7 条一一对应。
PRIVATE_SOURCE_DIRS = (
    "qidian_requests_default",
    "qidian_browser_default",
    "qimao_requests_default",
    "qimao_browser_default",
    "qimao_api_rain",
    "92xs_requests_default",
    "fanqie_api_rain",
)


def plan_moves(builtin_dir: Path, dest_root: Path) -> list[tuple[Path, Path]]:
    """列出待搬的 `(源目录, 目标目录)`。

    只取 `PRIVATE_SOURCE_DIRS` 里**确实存在于** `builtin_dir` 的目录（部分迁移过也安全）；
    不按目录内容猜测——名单是显式的，免得哪天新增一个敏感源被悄悄留下。
    """
    builtin_dir = Path(builtin_dir)
    dest_root = Path(dest_root)
    moves: list[tuple[Path, Path]] = []
    for name in PRIVATE_SOURCE_DIRS:
        src = builtin_dir / name
        if not src.is_dir() or not (src / MANIFEST_NAME).is_file():
            continue
        moves.append((src, dest_root / name))
    return moves


def _drop_pycache(root: Path) -> None:
    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def apply_moves(
    moves: list[tuple[Path, Path]], *, dry_run: bool = True
) -> list[str]:
    """执行搬迁。先全量校验目标冲突，任何一个已存在就整体放弃。"""
    conflicts = [dst for _, dst in moves if dst.exists()]
    if conflicts:
        listed = "\n".join(f"  {c}" for c in conflicts)
        raise FileExistsError(
            f"目标目录已存在，放弃搬迁（未移动任何文件）：\n{listed}\n"
            f"如确认要覆盖，请先手动移走目标目录。"
        )

    lines: list[str] = []
    for src, dst in moves:
        lines.append(f"{src} -> {dst}")
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        _drop_pycache(dst)
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="把不能公开的书源从 novelbase/sources/builtin/ 搬到 <APP_DATA>/sources/"
    )
    ap.add_argument("--apply", action="store_true", help="真正执行搬迁（默认 dry-run）")
    ap.add_argument("--builtin-dir", default=str(DEFAULT_BUILTIN_DIR), help="官方源目录")
    ap.add_argument("--dest", default=None, help="目标源根（默认 <APP_DATA>/sources）")
    args = ap.parse_args(argv)

    if args.dest:
        dest_root = Path(args.dest)
    else:
        from shared.config import user_sources_dir

        dest_root = user_sources_dir()

    moves = plan_moves(Path(args.builtin_dir), dest_root)
    if not moves:
        print(f"没有需要搬迁的书源（{args.builtin_dir} 下已无红名单源）")
        return 0

    lines = apply_moves(moves, dry_run=not args.apply)
    verb = "已搬迁" if args.apply else "计划搬迁"
    print(f"{verb} {len(lines)} 个书源 → {dest_root}：")
    for line in lines:
        print(f"  {line}")
    if not args.apply:
        print("\n这是 dry-run，磁盘未改动。确认无误后加 --apply 执行。")
    else:
        print(
            "\n下一步（否则仓库自测会红）："
            "\n  1. 确认 tests/conftest.py 的缺席跳过机制覆盖这 7 个源"
            "\n  2. 删除 template/config/sources/ 下对应的 7 份种子配置"
            "\n  3. 更新 pyproject.toml / PUBLIC_MANIFEST.md 里这 7 条 exclude 的说明"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

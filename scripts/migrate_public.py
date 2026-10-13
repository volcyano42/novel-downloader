#!/usr/bin/env python3
"""migrate_public.py — 按 PUBLIC_MANIFEST 白名单把 private 子集**同步**到 public。

与 `check_public.py` 的分工：本脚本负责「复制白名单文件 + 删除 public 中的残留」，
`check_public.py` 负责事后校验（缺失 / 多余 / 敏感三道防线）。二者共用同一份白名单
与排除清单（`pyproject.toml` 的 `[tool.novel-downloader.migration] exclude`）。

**迁移是「同步」而非「只增」**：public 中既不在白名单、也不在
`check_public.PUBLIC_ONLY_FILES` 的文件一律删除。

用法：
    python scripts/migrate_public.py                    # 执行同步
    python scripts/migrate_public.py --dry-run          # 只预览将发生的变化
    python scripts/migrate_public.py --public ../other  # 指定 public 仓库位置

同步后**必须**再跑 `python scripts/check_public.py`，通过后才可在 public 提交。
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

PRIVATE_DEFAULT = Path(__file__).resolve().parent.parent
PUBLIC_DEFAULT = PRIVATE_DEFAULT.parent / "novel-crawler"


def _load_check_public(private_root: Path):
    """复用 check_public.py 的清单解析与白名单判定（避免两处规则漂移）。"""
    spec = importlib.util.spec_from_file_location(
        "check_public", private_root / "scripts" / "check_public.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"无法加载 {private_root / 'scripts' / 'check_public.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(private: Path, public: Path, dry_run: bool = False) -> dict[str, list[str]]:
    """把 private 的白名单子集同步到 public；返回各类变更清单。"""
    cp = _load_check_public(private)
    exclude = cp.load_exclude_patterns(private)

    copied: list[str] = []
    updated: list[str] = []
    keep: set[str] = set()

    # 1) 白名单文件 → public（记录应存在集，供第 2 步判残留）
    for src in cp._iter_files(private):
        rel = src.relative_to(private).as_posix()
        if not cp.is_whitelisted(rel, exclude):
            continue
        keep.add(rel)
        dst = public / rel
        existed = dst.exists()
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        (updated if existed else copied).append(rel)

    # 2) public 中不在应存在集、也不在 public 自维护清单里的文件 → 删除
    removed: list[str] = []
    for path in cp._iter_files(public):
        rel = path.relative_to(public).as_posix()
        if rel in keep or rel in cp.PUBLIC_ONLY_FILES:
            continue
        if not dry_run:
            path.unlink()
        removed.append(rel)

    # 3) 收尾：删掉因第 2 步而空掉的目录（跳过 .git）
    pruned: list[str] = []
    if not dry_run:
        for directory in sorted(
            (d for d in public.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)
        ):
            if ".git" in directory.relative_to(public).parts:
                continue
            try:
                if not any(directory.iterdir()):
                    directory.rmdir()
                    pruned.append(directory.relative_to(public).as_posix())
            except OSError:
                pass

    return {"copied": copied, "updated": updated, "removed": removed, "pruned": pruned}


def main() -> int:
    parser = argparse.ArgumentParser(description="public 同步（复制白名单 + 删除残留）")
    parser.add_argument("--private", type=Path, default=PRIVATE_DEFAULT, help="private 仓库根")
    parser.add_argument("--public", type=Path, default=PUBLIC_DEFAULT, help="public 仓库根")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写任何文件")
    args = parser.parse_args()

    private = args.private.resolve()
    public = args.public.resolve()
    if not public.is_dir():
        print(f"public 目录不存在：{public}", file=sys.stderr)
        return 1

    result = migrate(private, public, args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "已执行"
    print(
        f"[{mode}] 新增 {len(result['copied'])} / 更新 {len(result['updated'])} / "
        f"删除 {len(result['removed'])} / 清理空目录 {len(result['pruned'])}"
    )
    for rel in sorted(result["removed"]):
        print(f"  [删除] {rel}")
    print("\n下一步：python scripts/check_public.py（通过后才可在 public 提交）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

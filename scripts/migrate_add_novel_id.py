#!/usr/bin/env python3
"""为现有 chapter JSON 文件添加 novel_id 字段。

用法: python scripts/migrate_add_novel_id.py [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE_DIR = PROJECT_ROOT / "app_data" / "storage"


def migrate(dry_run: bool = False):
    if not STORAGE_DIR.exists():
        print(f"storage 目录不存在: {STORAGE_DIR}")
        return

    total_novels = 0
    total_chapters = 0

    for novel_dir in sorted(STORAGE_DIR.iterdir()):
        if not novel_dir.is_dir():
            continue
        novel_id = novel_dir.name
        chapters_dir = novel_dir / "chapters"
        if not chapters_dir.is_dir():
            continue

        novel_files = list(chapters_dir.glob("*.json"))
        if not novel_files:
            continue

        total_novels += 1

        for f in sorted(novel_files):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"  跳过损坏文件: {f}")
                continue

            old_novel_id = data.get("novel_id")
            if old_novel_id and old_novel_id == novel_id:
                continue  # 已是最新，跳过

            data["novel_id"] = novel_id

            if not dry_run:
                f.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")

            if old_novel_id:
                print(f"  [{novel_id}] {f.name}: {old_novel_id!r} → {novel_id!r}")
            else:
                print(f"  [{novel_id}] {f.name}: 新增 novel_id={novel_id!r}")
            total_chapters += 1

    action = "将会修改" if dry_run else "已更新"
    print(f"\n{action} {total_novels} 本小说, {total_chapters} 个章节")


def main():
    p = argparse.ArgumentParser(description="为旧章节 JSON 添加 novel_id 字段")
    p.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    args = p.parse_args()

    if args.dry_run:
        print("[DRY RUN] 预览模式，不会实际修改文件\n")

    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

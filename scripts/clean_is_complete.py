#!/usr/bin/env python3
"""移除旧 chapter JSON 中的 is_complete 字段。

用法: python scripts/clean_is_complete.py [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
STORAGE_DIR = PROJECT_ROOT / "app_data" / "storage"


def clean(dry_run=False):
    total = 0
    for novel_dir in sorted(STORAGE_DIR.iterdir()):
        if not novel_dir.is_dir():
            continue
        chapters_dir = novel_dir / "chapters"
        if not chapters_dir.is_dir():
            continue
        for f in chapters_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if "is_complete" not in data:
                continue
            del data["is_complete"]
            total += 1
            if not dry_run:
                f.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
            print(f"  [{novel_dir.name}] {f.name}: 已移除 is_complete")

    action = "将会移除" if dry_run else "已移除"
    print(f"\n{action} {total} 个文件的 is_complete 字段")


def main():
    p = argparse.ArgumentParser(description="清理旧 JSON 中的 is_complete 字段")
    p.add_argument("--dry-run", action="store_true", help="仅预览")
    args = p.parse_args()
    if args.dry_run:
        print("[DRY RUN]\n")
    clean(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

"""一次性脚本：修复 DB 中 chapters 的 order 序号（0-based → 1-based）。

用法：
    python scripts/fix_chapter_order.py [--dry-run]

--dry-run: 只检查不修改。
"""

import sqlite3
import sys
from pathlib import Path

PROJECT = Path(__file__).parent.parent
STORAGE = PROJECT / "app_data" / "storage"

DRY_RUN = "--dry-run" in sys.argv


def fix_db(db_path: Path) -> tuple[int, int]:
    """Fix one DB. Returns (total_chapters, incremented_chapters)."""
    conn = sqlite3.connect(str(db_path))
    try:
        # 检查是否存在 chapters 表
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chapters'"
        )
        if not cur.fetchone():
            return 0, 0

        # 查最小 order
        row = conn.execute('SELECT MIN("order") FROM chapters').fetchone()
        if row is None or row[0] is None:
            return 0, 0

        min_order = row[0]
        if min_order != 0:
            return conn.execute('SELECT COUNT(*) FROM chapters').fetchone()[0], 0

        total = conn.execute('SELECT COUNT(*) FROM chapters').fetchone()[0]
        if DRY_RUN:
            return total, total

        conn.execute('UPDATE chapters SET "order" = "order" + 1')
        conn.commit()
        return total, total
    finally:
        conn.close()


def main():
    dbs = sorted(STORAGE.glob("*.db"))
    if not dbs:
        print(f"未找到 DB 文件: {STORAGE}")
        return

    print(f"{'[DRY RUN] ' if DRY_RUN else ''}扫描 {len(dbs)} 个数据库...\n")
    fixed = 0
    skipped = 0

    for db_path in dbs:
        total, changed = fix_db(db_path)
        if total == 0:
            continue
        if changed > 0:
            print(f"  [FIX] {db_path.name}: {total} 章，order +1")
            fixed += 1
        else:
            print(f"  [SKIP] {db_path.name}: {total} 章，已是 1-based，跳过")
            skipped += 1

    print(f"\n完成: 修复 {fixed} 个，跳过 {skipped} 个")
    if DRY_RUN:
        print("(dry run，未实际修改)")


if __name__ == "__main__":
    main()

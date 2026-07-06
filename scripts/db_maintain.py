#!/usr/bin/env python3
"""SQLite 数据库维护脚本：

1. 移除旧 schema 中的 is_complete / images_json 列
2. 列出/恢复不完整章节（content 为 NULL 的章节）

用法:
    python scripts/db_maintain.py --list         # 列出不完整章节
    python scripts/db_maintain.py --fix-schema   # 移除旧列（is_complete, images_json, cover_json）
    python scripts/db_maintain.py --fix-schema --restore  # 修复 schema 并尝试恢复
"""

import argparse
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def list_incomplete(db_path: str):
    conn = connect(db_path)
    rows = conn.execute("""
        SELECT c.novel_id, c.id, c.title, c."order", n.title as novel_title
        FROM chapters c
        JOIN novels n ON n.id = c.novel_id
        WHERE c.content IS NULL
        ORDER BY n.title, c."order"
    """).fetchall()
    if not rows:
        print("没有不完整章节 ✓")
        return
    print(f"\n不完整章节: {len(rows)} 章\n")
    for r in rows:
        print(f"  [{r['novel_title']}] 第{r['order']}章 {r['title']}")


def fix_schema(db_path: str, dry_run=False):
    """移除 is_complete / images_json / cover_json 等旧列。"""
    conn = connect(db_path)
    cur = conn.execute("PRAGMA table_info(chapters)")
    cols = [r[1] for r in cur.fetchall()]

    if "is_complete" not in cols and "images_json" not in cols:
        print("Schema 已是最新，无需修改 ✓")
        return

    if dry_run:
        print("[DRY RUN] 将会移除 chapters.is_complete 列")
        return

    # 重建 chapters 表，移除 is_complete 和 images_json 列
    conn.executescript("""
        CREATE TABLE chapters_new (
            id          TEXT NOT NULL,
            novel_id    TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
            url         TEXT NOT NULL,
            title       TEXT NOT NULL,
            "order"     INTEGER NOT NULL DEFAULT 0,
            volume      TEXT,
            content     TEXT,
            time        REAL,
            count       INTEGER,
            PRIMARY KEY (novel_id, id)
        );
        INSERT INTO chapters_new
            SELECT id, novel_id, url, title, "order", volume, content, time, count
            FROM chapters;
        DROP TABLE chapters;
        ALTER TABLE chapters_new RENAME TO chapters;
        CREATE INDEX IF NOT EXISTS idx_chapters_novel ON chapters(novel_id, "order");
    """)
    # 同样清理 novels 表的 cover_json 列（图片已迁移到 illustrations）
    cur = conn.execute("PRAGMA table_info(novels)")
    novel_cols = [r[1] for r in cur.fetchall()]
    if "cover_json" in novel_cols:
        conn.executescript("""
            CREATE TABLE novels_new (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                url         TEXT NOT NULL,
                author      TEXT NOT NULL DEFAULT '',
                serial      INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL DEFAULT '',
                tags        TEXT NOT NULL DEFAULT '[]',
                count       INTEGER,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO novels_new SELECT
                id, title, url, author, serial, description, tags, count, created_at
            FROM novels;
            DROP TABLE novels;
            ALTER TABLE novels_new RENAME TO novels;
        """)
    conn.commit()
    print("Schema 已更新：移除 is_complete / images_json ✓")


def restore_incomplete(db_path: str):
    """尝试重新下载不完整章节。"""
    from main import APP_DATA, load_main_config, load_site_config, build_options
    from nldlder import create_engine, NovelDownloader, get_fetcher_for_id
    from nldlder.core.storage import SQLiteStorage
    from nldlder.core.options import StorageOptions
    from nldlder.models.novel import Chapter
    from nldlder.utils.notify import notify as do_notify

    cfg = load_main_config()
    mode = cfg.get("mode", "requests")

    s = SQLiteStorage(StorageOptions(backend="sqlite", database_url=f"sqlite:///{db_path}"))

    # 找出不完整章节
    incomplete = []
    for novel in s.iter_metas():
        for ch in s._iter_chapters(novel.id):
            if ch.content is None:
                incomplete.append((novel, ch))

    if not incomplete:
        print("没有不完整章节 ✓")
        return

    print(f"\n发现 {len(incomplete)} 章不完整\n")

    # 按小说分组
    by_novel: dict[str, list] = {}
    for novel, ch in incomplete:
        by_novel.setdefault(novel.id, []).append((novel, ch))

    for novel_id, items in by_novel.items():
        novel = items[0][0]
        chapters = [ch for _, ch in items]
        platform = _detect_platform(novel.url)

        print(f"\n── {novel.title} [{platform}]: {len(chapters)} 章 ──")

        site_cfg = load_site_config(platform)
        cfg["mode"] = mode
        options = build_options(cfg, site_cfg)
        engine = create_engine(options)
        dl = NovelDownloader(engine, options=options)

        fetcher_cls = get_fetcher_for_id(novel.id)
        fetcher = fetcher_cls() if fetcher_cls else None

        success = 0
        for ch in chapters:
            try:
                result = dl.resolve_chapter(ch, fetcher=fetcher)
                if result is not None:
                    s.save_chapter(novel, result)
                    success += 1
                    print(f"  [{ch.order}] {ch.title} ✓")
                else:
                    print(f"  [{ch.order}] {ch.title} ✗ (不可获取)")
            except Exception as e:
                print(f"  [{ch.order}] {ch.title} ✗ ({e})")

        engine.close()

    # 通知
    notify_cfg = cfg.get("download", {}).get("notify", {})
    if notify_cfg:
        do_notify(notify_cfg, complete=success, incomplete=len(incomplete) - success)


def _detect_platform(url: str) -> str:
    if "qimao.com" in url:
        return "qimao"
    if "fanqienovel.com" in url:
        return "fanqie"
    if "qidian.com" in url:
        return "qidian"
    return "fanqie"


def main():
    p = argparse.ArgumentParser(description="SQLite 数据库维护")
    p.add_argument("--db", default="app_data/storage/novels.db", help="数据库路径")
    p.add_argument("--list", action="store_true", help="列出不完整章节")
    p.add_argument("--fix-schema", action="store_true", help="移除旧 is_complete / images_json 列")
    p.add_argument("--restore", action="store_true", help="重新下载不完整章节")
    p.add_argument("--dry-run", action="store_true", help="仅预览")
    args = p.parse_args()

    db = str(_PROJECT_ROOT / args.db) if not args.db.startswith("/") else args.db

    did_something = False

    if args.fix_schema:
        fix_schema(db, dry_run=args.dry_run)
        did_something = True

    if args.restore:
        restore_incomplete(db)
        did_something = True

    if args.list or not did_something:
        list_incomplete(db)


if __name__ == "__main__":
    main()

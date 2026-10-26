#!/usr/bin/env python3
"""一次性迁移：user_data.db → config/library/{books.yaml, search_history.jsonl}。

旧库（`app_data/storage/users/default/user_data.db`）里的 4 张表搬到两个能手改的
文本文件，然后把旧库备份到 `config/library/user_data.db.migrated` 并删掉
`storage/users/`。

用法：
    python scripts/migrate_user_data.py              # dry-run，只打印将要写入的内容
    python scripts/migrate_user_data.py --apply       # 真正落盘
    python scripts/migrate_user_data.py --apply --force   # 目标已存在也覆盖

背景见 docs/superpowers/specs/2026-10-26-user-data-to-files-design.md。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import APP_DATA                    # noqa: E402
from shared.user_data import _atomic_write, _dump_books   # noqa: E402


def _read_title(novels_dir: Path, novel_id: str) -> str | None:
    """从 `novels/<id>.db` 的 meta.title 读书名；任何失败返回 None。"""
    db = novels_dir / f"{novel_id}.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        try:
            row = conn.execute("SELECT title FROM meta LIMIT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row and row[0] else None


_CHECKPOINT_BUSY_TIMEOUT_MS = 2000   # checkpoint 最多等这么久就报 busy（库只几十 KB）


def _collect(db_path: Path, novels_dir: Path, *, checkpoint: bool) -> tuple[dict, list[dict], int]:
    """读旧库 → (books, history, bookmarks_rowcount)。

    `checkpoint=True` 时先做 `PRAGMA wal_checkpoint(TRUNCATE)`：WAL 里可能有还没
    合并进主库的写入（进程被关掉时不会自动合并），而收尾要 `shutil.copy2` 主库做
    备份 —— 不先 checkpoint，备份文件会缺掉那些行。checkpoint 可能因其它连接而
    busy，这时**必须报错而不是继续**（否则备份静默不完整）。

    dry-run 传 `checkpoint=False`：读取视图本身就包含 WAL 内容，不需要也不应该
    去改旧库。
    """
    conn = sqlite3.connect(str(db_path), timeout=15)
    try:
        if checkpoint:
            # checkpoint 最多等 2s 就放弃：库只有几十 KB，等这么久还没拿到锁说明
            # 确实有别的进程在用，早点报错比静默写出残缺备份好
            conn.execute(f"PRAGMA busy_timeout = {_CHECKPOINT_BUSY_TIMEOUT_MS}")
            busy = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
            if busy:
                raise RuntimeError(
                    f"WAL checkpoint 未完成（busy={busy}）：可能有其它进程正在用 {db_path}"
                    "（例如 backend / app.py）。关掉它再重试，否则备份会不完整。"
                )

        books: dict[str, dict] = {}

        for group, novel_id, pending in conn.execute(
            "SELECT group_name, novel_id, pending_export FROM groups"
        ):
            entry = books.setdefault(str(novel_id), {})
            entry.setdefault("groups", {})[str(group)] = (
                {"pending_export": True} if pending else {}
            )

        for novel_id, source_name in conn.execute(
            "SELECT novel_id, source_name FROM novel_sources"
        ):
            if source_name:
                books.setdefault(str(novel_id), {})["source"] = source_name

        for novel_id, favorited_at in conn.execute(
            "SELECT novel_id, favorited_at FROM favorites"
        ):
            entry = books.setdefault(str(novel_id), {})
            entry["favorite"] = True
            if favorited_at:
                entry["favorited_at"] = favorited_at

        # 书名最后补，只补能读到的（孤儿书没有 books/<id>.db）
        for novel_id in list(books):
            title = _read_title(novels_dir, novel_id)
            if title:
                books[novel_id]["title"] = title

        history = [
            {
                "id": hid,
                "source_name": source_name or "",
                "keyword": keyword,
                "searched_at": searched_at or "",
            }
            for hid, source_name, keyword, searched_at in conn.execute(
                "SELECT id, source_name, keyword, searched_at FROM search_history ORDER BY id"
            )
        ]

        try:
            bookmarks = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise           # locked / corrupt 不能当成「没有这张表」
            bookmarks = 0       # 很老的库里没这张表
    finally:
        conn.close()

    return books, history, bookmarks


def migrate(app_data: Path, apply: bool = False, force: bool = False) -> dict:
    """把旧库搬成两个文本文件。

    返回 `{"books": int, "history": int, "skipped": str | None, "written": list[str]}`。
    `skipped` 非 None 表示没有迁移（旧库不存在 / 目标已存在且未 force）。
    """
    app_data = Path(app_data)
    db_path = app_data / "storage" / "users" / "default" / "user_data.db"
    novels_dir = app_data / "storage" / "novels"
    library_dir = app_data / "config" / "library"
    books_path = library_dir / "books.yaml"
    history_path = library_dir / "search_history.jsonl"
    backup_path = library_dir / "user_data.db.migrated"

    result: dict = {
        "books": 0, "history": 0, "bookmarks_dropped": 0,
        "skipped": None, "written": [],
    }

    if not db_path.exists():
        result["skipped"] = f"旧库不存在：{db_path}"
        return result

    # 先判目标，再读旧库：--apply 但目标已存在时本来就啥都不做，
    # 不该先去对旧库做 TRUNCATE checkpoint（旧库被占时用户会看到莫名其妙的 busy 错误）
    if apply and not force and (books_path.exists() or history_path.exists()):
        result["skipped"] = f"目标已存在（要覆盖请加 --force）：{library_dir}"
        return result

    books, history, bookmarks = _collect(db_path, novels_dir, checkpoint=apply)
    result["books"] = len(books)
    result["history"] = len(history)
    result["bookmarks_dropped"] = bookmarks

    if not apply:
        return result

    library_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(books_path, _dump_books(books))
    ordered = sorted(history, key=lambda r: (r["searched_at"], r["id"]))
    _atomic_write(
        history_path,
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered),
    )
    result["written"] += [str(books_path), str(history_path)]

    # 备份放在账本同目录（不破坏「storage/ 只留 novels」），再删 users/
    shutil.copy2(db_path, backup_path)
    result["written"].append(str(backup_path))
    shutil.rmtree(app_data / "storage" / "users", ignore_errors=True)

    return result


def _print_report(result: dict, applied: bool) -> None:
    if result["skipped"]:
        print(f"未迁移：{result['skipped']}")
        return
    print(f"读源：{result['books']} 本书 / {result['history']} 条搜索历史")
    if result["bookmarks_dropped"]:
        print(f"丢弃：{result['bookmarks_dropped']} 条 bookmarks（无任何调用者的死功能）")
    if not applied:
        print("（dry-run）加 --apply 才真正写入。")
        return
    for path in result["written"]:
        print(f"  写入 {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 user_data.db 迁移成 config/library/ 下两个可手改的文本文件"
    )
    parser.add_argument("--app-data", default=str(APP_DATA),
                        help=f"app_data 目录（默认 {APP_DATA}）")
    parser.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    parser.add_argument("--force", action="store_true",
                        help="目标文件已存在时也覆盖")
    args = parser.parse_args(argv)

    result = migrate(Path(args.app_data), apply=args.apply, force=args.force)
    _print_report(result, args.apply)
    return 0 if result["skipped"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())

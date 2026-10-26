"""用户数据层 — books.yaml 书维度账本 + 搜索历史。

- 书维度（分组 / 收藏 / 来源 / 书名）存 `app_data/config/library/books.yaml`，
  可手改；全量重写走"临时文件 + fsync + os.replace"，写前留一份 `.bak`。
- 搜索历史暂存 `app_data/storage/users/default/user_data.db`，
  待迁移到同目录的 `search_history.jsonl`。

并发保护：进程内 `threading.Lock`（backend 单进程，`uvicorn.run(app)` 不带 workers）。
"""
import logging
import os
import shutil
import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime
from typing import Optional

import yaml

from shared.config import APP_DATA, CONFIG_DIR

_log = logging.getLogger("user_db")

# ── 路径 ──
# 全部派生自 shared.config（优先级 NLD_APP_DATA > 编译产物 exe 同目录 > 仓库根）。
# ⚠️ 不要用 `Path(__file__).resolve().parent.parent`：Nuitka onefile 下 `__file__` 在
# **临时解包目录**，读写会落在解包目录（每次运行新建空文件）。
LIBRARY_DIR = CONFIG_DIR / "library"
BOOKS_PATH = LIBRARY_DIR / "books.yaml"
HISTORY_PATH = LIBRARY_DIR / "search_history.jsonl"
NOVELS_DIR = APP_DATA / "storage" / "novels"

_lock = threading.Lock()

# 搜索历史（尚未迁移）
DB_PATH = APP_DATA / "storage" / "users" / "default" / "user_data.db"


class LibraryCorruptError(RuntimeError):
    """`books.yaml` 存在但不是合法 YAML dict。

    读写都抛，**绝不降级成空 dict** —— 否则下一次写入（下载热路径上的
    `set_novel_source`）会把整本账本重写成一条。
    """


# ═══════════════════════════════ books.yaml ═══════════════════════════════

_BOOKS_HEADER = """\
# 书维度账本（程序维护，可手改）。key = novel_id（sha256(url)[:32]）。
# title 由程序从 novels/<id>.db 的 meta.title 同步，手改会被覆盖。
# groups 下每本书可属多个组，pending_export 是组级属性。
# 其余字段省略即默认：favorite=false / source 未知 / 无收藏时间。
"""

# 序列化时的固定字段顺序（手改时肉眼可比对）
_FIELD_ORDER = ("title", "groups", "favorite", "favorited_at", "source")

_FAVORITED_AT_FMT = "%Y-%m-%d %H:%M:%S"


def _load_books() -> dict[str, dict]:
    """读 books.yaml 原始 dict。文件不存在 → {}。

    解析失败或顶层不是 dict → `LibraryCorruptError`；值为 None 的条目归一成 {}。
    """
    path = BOOKS_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise LibraryCorruptError(f"{path}: YAML 解析失败：{exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LibraryCorruptError(
            f"{path}: 顶层必须是映射（dict），实际是 {type(data).__name__}"
        )
    return {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items()}


def _ordered(book: dict) -> dict:
    """按固定字段顺序输出，未知字段（用户手写的）按原顺序跟在后面。"""
    out = {k: book[k] for k in _FIELD_ORDER if k in book}
    out.update({k: v for k, v in book.items() if k not in _FIELD_ORDER})
    return out


def _dump_books(books: dict) -> str:
    """book dict → yaml 文本（含固定头注释）。纯函数，供迁移脚本复用。"""
    body = {nid: _ordered(b) for nid, b in books.items()}
    text = yaml.safe_dump(
        body, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    return _BOOKS_HEADER + text


def _atomic_write(path: Path, text: str) -> None:
    """临时文件 + fsync + os.replace（同目录 rename 在 POSIX 上原子）。

    写前把上一版留成 `.bak`，手改写坏后还能捞回来。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except OSError:          # 备份只是附加价值，失败不阻断正式写入
            pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)  # 上次中断残留
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _save_books(books: dict) -> None:
    """修剪空条目后落盘。调用方必须已持有 `_lock`。"""
    pruned = {nid: b for nid, b in books.items() if b}
    _atomic_write(BOOKS_PATH, _dump_books(pruned))


def _read_title(novel_id: str) -> Optional[str]:
    """从 `novels/<id>.db` 的 `meta.title` 读书名；任何失败返回 None（不阻断调用方）。"""
    db = NOVELS_DIR / f"{novel_id}.db"
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


# ═══════════════════════════════ Groups ═══════════════════════════════

def load_groups() -> dict:
    """返回 {group_name: {novel_id: {组属性}}}。"""
    with _lock:
        books = _load_books()
    result: dict = {}
    for novel_id, book in books.items():
        for group, attrs in (book.get("groups") or {}).items():
            result.setdefault(str(group), {})[novel_id] = dict(attrs or {})
    return result


def save_groups(groups: dict) -> None:
    """全量重建 `groups` 字段 —— 只动它，`title` / `favorite` / `source` 原样保留。"""
    with _lock:
        books = _load_books()
        for book in books.values():
            book.pop("groups", None)
        for group, novels in groups.items():
            if not isinstance(novels, dict):
                continue
            for novel_id, attrs in novels.items():
                entry = books.setdefault(str(novel_id), {})
                entry.setdefault("groups", {})[str(group)] = dict(attrs or {})
        _save_books(books)


def get_novel_group(novel_id: str) -> Optional[str]:
    """该书的第一个组名；不属于任何组返回 None（多组时返回哪个未定义）。"""
    with _lock:
        book = _load_books().get(novel_id) or {}
    groups = book.get("groups") or {}
    return next(iter(groups), None)


def add_novel_to_group(novel_id: str, group: str) -> bool:
    """加入 `group`，并先把该书移出所有其它组（沿用旧的单组语义）。

    返回 True 表示发生了实际变化（新增 / 换组 / 顺带移出了别的组），
    已在唯一的目标组里返回 False。
    """
    with _lock:
        books = _load_books()
        entry = books.setdefault(novel_id, {})
        current = entry.get("groups") or {}
        if list(current) == [group]:
            return False
        attrs = dict(current.get(group) or {})
        entry["groups"] = {group: attrs}
        _save_books(books)
        return True


def ensure_novel_in_group(novel_id: str) -> None:
    """不属于任何组时加入 `default`。"""
    if get_novel_group(novel_id) is None:
        add_novel_to_group(novel_id, "default")


# ═══════════════════════════════ Favorites ═══════════════════════════════

def load_favorites() -> list[str]:
    """已收藏的 novel_id，按收藏时间倒序（无时间戳的排最后）。"""
    with _lock:
        books = _load_books()
    favs = [
        (book.get("favorited_at") or "", novel_id)
        for novel_id, book in books.items()
        if book.get("favorite") is True
    ]
    favs.sort(key=lambda pair: (pair[0] != "", pair[0]), reverse=True)
    return [novel_id for _, novel_id in favs]


def add_favorite(novel_id: str) -> bool:
    """收藏。返回 True 表示新收藏。"""
    with _lock:
        books = _load_books()
        entry = books.setdefault(novel_id, {})
        if entry.get("favorite") is True:
            return False
        entry["favorite"] = True
        entry["favorited_at"] = datetime.now().strftime(_FAVORITED_AT_FMT)
        _save_books(books)
        return True


def remove_favorite(novel_id: str) -> bool:
    """取消收藏。返回 True 表示确实删除了。"""
    with _lock:
        books = _load_books()
        entry = books.get(novel_id) or {}
        if entry.get("favorite") is not True:
            return False
        entry.pop("favorite", None)
        entry.pop("favorited_at", None)
        _save_books(books)
        return True


def is_favorite(novel_id: str) -> bool:
    with _lock:
        book = _load_books().get(novel_id) or {}
    return book.get("favorite") is True


# ═══════════════════════════════ Novel Sources ═══════════════════════════════

def set_novel_source(novel_id: str, source_name: str) -> None:
    """记录某本书的来源（空 source_name 跳过，不建孤儿条目）。

    顺带从 `meta.title` 同步书名 —— 这是账本里 `title` 的唯一写入口，
    所以书名保持与入库数据一致（手改 `title` 会被这里覆盖）。
    """
    if not source_name:
        return
    title = _read_title(novel_id)          # 锁外做 IO
    with _lock:
        books = _load_books()
        entry = books.setdefault(novel_id, {})
        entry["source"] = source_name
        if title:
            entry["title"] = title
        _save_books(books)


def get_novel_source(novel_id: str) -> Optional[str]:
    """返回该书来源；无记录返回 None。"""
    with _lock:
        book = _load_books().get(novel_id) or {}
    return book.get("source")


def get_novel_sources(novel_ids: Sequence[str]) -> dict[str, str]:
    """批量查询（供列表 join 用）。只返回命中的 id；空输入返回 {}。"""
    ids = list(novel_ids)
    if not ids:
        return {}
    with _lock:
        books = _load_books()
    return {
        novel_id: (books.get(novel_id) or {})["source"]
        for novel_id in ids
        if (books.get(novel_id) or {}).get("source")
    }


def delete_novel_source(novel_id: str) -> bool:
    """删书时清理。返回 True 表示确实删除了。"""
    with _lock:
        books = _load_books()
        entry = books.get(novel_id) or {}
        if "source" not in entry:
            return False
        entry.pop("source", None)
        _save_books(books)
        return True


# ═══════════════════════════════ 搜索历史（暂用 SQLite） ═══════════════════════════════

def _connection() -> sqlite3.Connection:
    """获取连接，自动建表。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS groups (
        group_name   TEXT NOT NULL,
        novel_id     TEXT NOT NULL,
        pending_export INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (group_name, novel_id)
    );

    CREATE TABLE IF NOT EXISTS favorites (
        novel_id     TEXT PRIMARY KEY,
        favorited_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        note         TEXT
    );

    CREATE TABLE IF NOT EXISTS search_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name  TEXT NOT NULL,
        keyword      TEXT NOT NULL,
        searched_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        UNIQUE(source_name, keyword)
    );
    CREATE INDEX IF NOT EXISTS idx_search_history_time
        ON search_history(searched_at DESC);

    CREATE TABLE IF NOT EXISTS bookmarks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        platform        TEXT NOT NULL,
        novel_id        TEXT NOT NULL,
        chapter_index   INTEGER NOT NULL,
        chapter_title   TEXT,
        note            TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        UNIQUE(platform, novel_id, chapter_index)
    );

    CREATE TABLE IF NOT EXISTS novel_sources (
        novel_id     TEXT PRIMARY KEY,
        source_name  TEXT NOT NULL,
        updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """建表。旧库（按 platform 存）的 search_history 整表 drop 重建，不迁移旧数据。"""
    old_cols = {r[1] for r in conn.execute("PRAGMA table_info(search_history)")}
    if "platform" in old_cols:
        conn.execute("DROP TABLE search_history")
        conn.commit()
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def add_search_history(source_name: str, keyword: str) -> None:
    conn = _connection()
    conn.execute(
        """INSERT INTO search_history(source_name, keyword, searched_at)
           VALUES (?, ?, datetime('now','localtime'))
           ON CONFLICT(source_name, keyword)
           DO UPDATE SET searched_at = datetime('now','localtime')""",
        (source_name, keyword),
    )
    conn.commit()


def get_search_history(limit: int = 50) -> list[dict]:
    conn = _connection()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM search_history ORDER BY searched_at DESC LIMIT ?",
        (limit,),
    ).fetchall()]


def delete_search_history(history_id: int) -> bool:
    """删除单条搜索历史，返回是否删除了记录。"""
    conn = _connection()
    cur = conn.execute(
        "DELETE FROM search_history WHERE id = ?", (history_id,)
    )
    conn.commit()
    return cur.rowcount > 0


def clear_search_history() -> None:
    conn = _connection()
    conn.execute("DELETE FROM search_history")
    conn.commit()


# ═══════════════════════════════ Bookmarks（无调用者，待删） ═══════════════════════════════

def add_bookmark(platform: str, novel_id: str, chapter_index: int,
                 chapter_title: str = None, note: str = None) -> bool:
    conn = _connection()
    try:
        conn.execute(
            "INSERT INTO bookmarks(platform, novel_id, chapter_index, chapter_title, note) VALUES (?,?,?,?,?)",
            (platform, novel_id, chapter_index, chapter_title, note),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_bookmark(platform: str, novel_id: str, chapter_index: int) -> bool:
    conn = _connection()
    cur = conn.execute(
        "DELETE FROM bookmarks WHERE platform=? AND novel_id=? AND chapter_index=?",
        (platform, novel_id, chapter_index),
    )
    conn.commit()
    return cur.rowcount > 0


def get_bookmarks(novel_id: str = None, platform: str = None) -> list[dict]:
    conn = _connection()
    if novel_id:
        rows = conn.execute(
            "SELECT * FROM bookmarks WHERE novel_id=? ORDER BY chapter_index",
            (novel_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM bookmarks ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]

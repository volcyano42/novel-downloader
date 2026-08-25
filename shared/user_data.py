"""用户数据层 — SQLite 存储 groups / favorites / search_history / bookmarks。

所有表存放在 app_data/storage/users/default/user_data.db，首次打开时自动建表
并从 groups.yaml 迁移旧数据。
"""
import logging
import sqlite3
from pathlib import Path
from typing import Optional

_log = logging.getLogger("user_db")

# 数据库路径（与 config 的存储目录一致）
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "app_data" / "storage" / "users" / "default" / "user_data.db"
GROUPS_YAML = ROOT / "app_data" / "config" / "groups.yaml"


def _connection() -> sqlite3.Connection:
    """获取连接，自动建表 + 迁移。"""
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
        platform     TEXT NOT NULL,
        mode         TEXT NOT NULL DEFAULT '',
        variant      TEXT NOT NULL DEFAULT '',
        keyword      TEXT NOT NULL,
        searched_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """建表 + 迁移 groups.yaml。"""
    # ── 建表 ──
    conn.executescript(_SCHEMA_SQL)
    conn.commit()

    # ── 迁移 search_history（加列 / fanqie 填充 / 去重 / 唯一索引）──
    _migrate_search_history(conn)

    # ── 迁移 groups.yaml → groups 表（仅首次，表为空且 yaml 存在时）──
    cur = conn.execute("SELECT COUNT(*) FROM groups")
    if cur.fetchone()[0] == 0 and GROUPS_YAML.exists():
        _log.info("migrating groups.yaml → user_data.db")
        _migrate_groups_yaml(conn)


def _migrate_search_history(conn: sqlite3.Connection) -> None:
    """search_history 迁移：加列 → fanqie 填充 → 清理重复 → 唯一索引。

    PRAGMA user_version 一次性守卫：迁移只执行一次；之后连接直接跳过，
    避免 UPDATE 反复改写迁移后写入的 fanqie mode='' 新记录。
    """
    if conn.execute("PRAGMA user_version").fetchone()[0] >= 1:
        return
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(search_history)")}
    if "mode" not in cols:
        conn.execute("ALTER TABLE search_history ADD COLUMN mode TEXT NOT NULL DEFAULT ''")
    if "variant" not in cols:
        conn.execute("ALTER TABLE search_history ADD COLUMN variant TEXT NOT NULL DEFAULT ''")
    # 旧数据无 mode 信息：fanqie 按 api 模式处理（主 variant rain），其余平台留空
    conn.execute(
        "UPDATE search_history SET mode = 'api', variant = 'rain' "
        "WHERE platform = 'fanqie' AND mode = ''"
    )
    # 清理重复：每组保留 searched_at 最新（并列取 id 最大）一条
    conn.execute("""
        DELETE FROM search_history WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY platform, keyword, mode, variant
                    ORDER BY searched_at DESC, id DESC
                ) AS rn FROM search_history
            ) WHERE rn = 1
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_search_history_dedup "
        "ON search_history(platform, keyword, mode, variant)"
    )
    # 标记迁移完成（随本事务提交生效；异常回滚则下次可重试）
    conn.execute("PRAGMA user_version = 1")
    conn.commit()


def _migrate_groups_yaml(conn: sqlite3.Connection) -> None:
    """读 groups.yaml 写入 groups 表，完成后重命名为 .migrated。"""
    import yaml

    with GROUPS_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    count = 0
    for group_name, novels in data.items():
        if not isinstance(novels, dict):
            continue
        for novel_id, meta in novels.items():
            pe = 1 if (isinstance(meta, dict) and meta.get("pending_export")) else 0
            conn.execute(
                "INSERT OR IGNORE INTO groups(group_name, novel_id, pending_export) VALUES (?,?,?)",
                (group_name, novel_id, pe),
            )
            count += 1
    conn.commit()

    # 重命名备份
    migrated_path = GROUPS_YAML.with_suffix(".yaml.migrated")
    GROUPS_YAML.rename(migrated_path)
    _log.info("migrated %d entries, backed up to %s", count, migrated_path)


# ═══════════════════════════════ Groups ═══════════════════════════════

def load_groups() -> dict:
    """返回 {group_name: {novel_id: {"pending_export": bool}}}。"""
    conn = _connection()
    rows = conn.execute("SELECT group_name, novel_id, pending_export FROM groups").fetchall()
    result: dict = {}
    for r in rows:
        g = r["group_name"]
        if g not in result:
            result[g] = {}
        result[g][r["novel_id"]] = {"pending_export": bool(r["pending_export"])}
    return result


def save_groups(groups: dict) -> None:
    """全量覆盖 groups 表。"""
    conn = _connection()
    conn.execute("DELETE FROM groups")
    for group_name, novels in groups.items():
        if not isinstance(novels, dict):
            continue
        for novel_id, meta in novels.items():
            pe = 1 if (isinstance(meta, dict) and meta.get("pending_export")) else 0
            conn.execute(
                "INSERT INTO groups(group_name, novel_id, pending_export) VALUES (?,?,?)",
                (group_name, novel_id, pe),
            )
    conn.commit()


def get_novel_group(novel_id: str) -> Optional[str]:
    conn = _connection()
    r = conn.execute(
        "SELECT group_name FROM groups WHERE novel_id = ?", (novel_id,)
    ).fetchone()
    return r["group_name"] if r else None


def add_novel_to_group(novel_id: str, group: str) -> bool:
    """添加 novel_id 到指定组。已有则跳过。会先从旧组移除。"""
    conn = _connection()
    conn.execute("DELETE FROM groups WHERE novel_id = ? AND group_name != ?",
                 (novel_id, group))
    try:
        conn.execute(
            "INSERT INTO groups(group_name, novel_id, pending_export) VALUES (?,?,0)",
            (group, novel_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def ensure_novel_in_group(novel_id: str) -> None:
    if get_novel_group(novel_id) is None:
        add_novel_to_group(novel_id, "default")


# ═══════════════════════════════ Favorites ═══════════════════════════════

def load_favorites() -> list[str]:
    """返回已收藏的 novel_id 列表。"""
    conn = _connection()
    return [r["novel_id"] for r in conn.execute(
        "SELECT novel_id FROM favorites ORDER BY favorited_at DESC"
    ).fetchall()]


def add_favorite(novel_id: str) -> bool:
    """添加收藏。返回 True 表示新收藏。"""
    conn = _connection()
    try:
        conn.execute("INSERT INTO favorites(novel_id) VALUES (?)", (novel_id,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_favorite(novel_id: str) -> bool:
    """取消收藏。返回 True 表示确实删除了。"""
    conn = _connection()
    cur = conn.execute("DELETE FROM favorites WHERE novel_id = ?", (novel_id,))
    conn.commit()
    return cur.rowcount > 0


def is_favorite(novel_id: str) -> bool:
    conn = _connection()
    return conn.execute(
        "SELECT 1 FROM favorites WHERE novel_id = ?", (novel_id,)
    ).fetchone() is not None


# ═══════════════════════════════ Search History ═══════════════════════════════

def add_search_history(platform: str, keyword: str, mode: str = "", variant: str = "") -> None:
    conn = _connection()
    conn.execute(
        """INSERT INTO search_history(platform, keyword, mode, variant, searched_at)
           VALUES (?, ?, ?, ?, datetime('now','localtime'))
           ON CONFLICT(platform, keyword, mode, variant)
           DO UPDATE SET searched_at = datetime('now','localtime')""",
        (platform, keyword, mode, variant),
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


# ═══════════════════════════════ Bookmarks ═══════════════════════════════

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

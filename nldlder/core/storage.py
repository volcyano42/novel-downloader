"""小说数据持久化 — 支持 local（JSON 文件）和 sqlite 两种后端。

用法::

    from nldlder.core.storage import create_storage
    from nldlder.core.options import StorageOptions

    opts = StorageOptions(backend="local", base_dir="app_data/storage")
    store = create_storage(opts)

    opts2 = StorageOptions(backend="sqlite", db_path="app_data/storage/novels.db")
    store2 = create_storage(opts2)
"""

import json
import shutil
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Sequence
from .options import StorageOptions
from ..models.novel import Novel, Chapter, Chapters
from ..utils.logger import get_logger

_log = get_logger("nldlder.core.storage")


# ═══════════════════════════════════════════════════════════════════
# 工厂
# ═══════════════════════════════════════════════════════════════════

def _parse_sqlite_url(database_url: str) -> Path:
    """解析 SQLite 连接字符串，返回本地文件路径。

    支持格式:
        sqlite:///relative/path/to/db    → 相对路径
        sqlite:////absolute/path/to/db   → 绝对路径
        sqlite://host:port/path          → 远程（暂不支持，抛异常）
    """
    url = database_url.strip()
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if path.startswith("/"):
            return Path(path)       # sqlite:////absolute → /absolute
        return Path(path)           # sqlite:///relative → relative
    if url.startswith("sqlite://"):
        # sqlite://host/path → 远程，暂不支持
        raise ValueError(
            f"远程 SQLite 暂不支持: {url!r}。"
            f"请使用 postgresql 后端或本地 sqlite:///path。"
        )
    # 裸路径，直接返回
    return Path(url)


def create_storage(config: StorageOptions) -> "BaseStorage":
    """根据配置创建对应的 Storage 实例。"""
    if config.backend == "sqlite":
        return SQLiteStorage(config)
    if config.backend == "postgresql":
        return PostgreSQLStorage(config)
    return LocalStorage(config)


class BaseStorage(ABC):
    """小说数据存储抽象基类。"""

    @abstractmethod
    def save_meta(self, novel: Novel) -> object:
        """保存小说元数据，返回写入标识。"""
        ...

    @abstractmethod
    def load_meta(self, novel_id: str) -> Novel | None:
        """加载小说元数据，不存在时返回 None。"""
        ...

    @abstractmethod
    def iter_metas(self) -> Iterator[Novel]:
        """逐条遍历所有小说元数据。"""
        ...

    @abstractmethod
    def save_chapter(self, novel: Novel, chapters: Sequence[Chapter] | Chapter) -> list:
        """保存章节内容，返回写入标识列表。"""
        ...

    @abstractmethod
    def load_chapter(self, novel_id: str, chapter_id: str) -> Chapter | None:
        """读取单个章节。
        
        novel_id 用于定位小说并推导 novel_url。
        """
        ...

    @abstractmethod
    def load_chapters(self, novel_id: str) -> Chapters:
        """读取某部小说的全部章节。"""
        ...

    @abstractmethod
    def delete_novel(self, novel_id: str) -> None:
        """彻底删除某部小说的所有数据。"""
        ...


class LocalStorage(BaseStorage):
    """本地 JSON 文件存储。

    目录结构::

        base_dir/
            {novel_id}/
                meta.json
                chapters/
                    {chapter_id}.json
    """

    def __init__(self, config: "StorageOptions | Path | str"):
        from .options import StorageOptions
        if isinstance(config, StorageOptions):
            self.base_dir = Path(config.base_dir)
        else:
            self.base_dir = Path(config)

    # ── 路径工具 ──

    def _novel_dir(self, novel_id: str) -> Path:
        return self.base_dir / novel_id

    def _meta_path(self, novel_id: str) -> Path:
        return self._novel_dir(novel_id) / "meta.json"

    def _chapters_dir(self, novel_id: str) -> Path:
        return self._novel_dir(novel_id) / "chapters"

    def _chapter_path(self, novel_id: str, chapter_id: str) -> Path:
        return self._chapters_dir(novel_id) / f"{chapter_id}.json"

    # ── 元数据 ──

    def save_meta(self, novel: Novel) -> Path:
        _log.debug("save_meta: id=%s", novel.id)
        path = self._meta_path(novel.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "title": novel.title,
            "url": novel.url,
            "id": novel.id,
            "serial": novel.serial,
            "author": novel.author,
            "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None,
            "count": novel.count,
            "cover": novel.cover.to_json() if novel.cover else None,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_meta(self, novel_id: str) -> Novel | None:
        path = self._meta_path(novel_id)
        if not path.exists():
            return None
        json_data = json.loads(path.read_text(encoding="utf-8"))
        return Novel.loads(**json_data)

    def iter_metas(self) -> Iterator[Novel]:
        if not self.base_dir.exists():
            return
        for entry in sorted(self.base_dir.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "meta.json"
            if not meta_path.exists():
                continue
            try:
                json_data = json.loads(meta_path.read_text(encoding="utf-8"))
                yield Novel.loads(**json_data)
            except (json.JSONDecodeError, KeyError, TypeError):
                _log.warning("跳过损坏的 meta 文件: %s", meta_path)

    # ── 章节 ──

    def save_chapter(self, novel: Novel, chapters: Sequence[Chapter] | Chapter) -> list[Path]:
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        saved = []
        for chapter in chapters:
            path = self._chapter_path(novel.id, chapter.id)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "id": chapter.id, "url": chapter.url, "title": chapter.title,
                "order": chapter.order, "volume": chapter.volume,
                "content": chapter.content, "time": chapter.time,
                "count": chapter.count,
                "images": [img.to_json() for img in chapter.images],
            }
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            saved.append(path)
        return saved

    def load_chapter(self, novel_id: str, chapter_id: str) -> Chapter | None:
        path = self._chapter_path(novel_id, chapter_id)
        if not path.exists():
            return None
        json_data = json.loads(path.read_text(encoding="utf-8"))
        json_data.setdefault("novel_id", novel_id)
        return Chapter.loads(**json_data)

    def load_chapters(self, novel_id: str) -> Chapters:
        return Chapters(self._iter_chapters(novel_id))

    def _iter_chapters(self, novel_id: str) -> Iterator[Chapter]:
        chapters_dir = self._chapters_dir(novel_id)
        if not chapters_dir.exists():
            return
        for file in chapters_dir.glob("*.json"):
            try:
                ch = self.load_chapter(novel_id, file.stem)
                if ch is not None:
                    yield ch
            except (json.JSONDecodeError, KeyError, TypeError):
                _log.warning("跳过损坏的章节文件: %s", file)

    # ── 删除 ──

    def delete_novel(self, novel_id: str) -> None:
        _log.info("delete_novel: id=%s", novel_id)
        path = self._novel_dir(novel_id)
        if path.exists():
            shutil.rmtree(path)


# ═══════════════════════════════════════════════════════════════════
# SQLiteStorage — SQLite 数据库存储
# ═══════════════════════════════════════════════════════════════════

class SQLiteStorage(BaseStorage):
    """SQLite 数据库存储。

    表结构::

        novels (id TEXT PK, title, url, author, serial, description,
                tags, count, cover_json, created_at)
        chapters (id TEXT PK, novel_id TEXT FK, url, title, "order",
                  volume, content, time, count)
    """

    def __init__(self, config: StorageOptions):
        url = config.database_url
        if url:
            db_path = _parse_sqlite_url(url)
        else:
            db_path = Path(config.base_dir) / "novels.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # timeout: 写锁等待秒数（默认 5s，加长避免并发读写报 database is locked）
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            # WSL / 网络文件系统不支持 WAL，降级为 DELETE
            _log.warning("WAL 模式不可用，降级为 DELETE journal")
            conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS novels (
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
                CREATE TABLE IF NOT EXISTS chapters (
                    id          TEXT NOT NULL,
                    novel_id    TEXT NOT NULL REFERENCES novels(id),
                    url         TEXT NOT NULL,
                    title       TEXT NOT NULL,
                    "order"     INTEGER NOT NULL DEFAULT 0,
                    volume      TEXT,
                    content     TEXT,
                    time        REAL,
                    count       INTEGER,
                                        PRIMARY KEY (novel_id, id)
                );
                CREATE TABLE IF NOT EXISTS illustrations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_type  TEXT NOT NULL CHECK(owner_type IN ('novel','chapter')),
                    owner_id    TEXT NOT NULL,
                    alt         TEXT,
                    url         TEXT NOT NULL,
                    insert_pos  INTEGER,
                    raw_data    BLOB,
                    format      TEXT,
                    UNIQUE(owner_type, owner_id, insert_pos)
                );
                CREATE INDEX IF NOT EXISTS idx_chapters_novel
                    ON chapters(novel_id, "order");
                CREATE INDEX IF NOT EXISTS idx_illustrations_owner
                    ON illustrations(owner_type, owner_id);
            """)

    # ── 元数据 ──

    def save_meta(self, novel: Novel) -> str:
        _log.debug("save_meta sqlite: id=%s", novel.id)
        tags_json = json.dumps(list(novel.tags) if novel.tags else [], ensure_ascii=False)
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO novels (id, title, url, author, serial,
                    description, tags, count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (novel.id, novel.title, novel.url, novel.author, novel.serial,
                  novel.description, tags_json, novel.count))
            self._save_illustration(conn, 'novel', novel.id, novel.cover)
        return novel.id

    def load_meta(self, novel_id: str) -> Novel | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, url, author, serial, description, tags, count "
                "FROM novels WHERE id = ?", (novel_id,)
            ).fetchone()
        if row is None:
            return None
        cover = self._load_illustration(novel_id, 'novel', novel_id)
        return self._row_to_novel(row, cover)

    def iter_metas(self) -> Iterator[Novel]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, url, author, serial, description, tags, count "
                "FROM novels ORDER BY title"
            ).fetchall()
        for row in rows:
            cover = self._load_illustration(row[0], 'novel', row[0])
            yield self._row_to_novel(row, cover)

    @staticmethod
    def _row_to_novel(row: tuple, cover=None) -> Novel:
        tags = json.loads(row[6]) if row[6] else []
        return Novel(
            id=row[0], title=row[1], url=row[2], author=row[3],
            serial=row[4], description=row[5], tags=tuple(tags),
            count=row[7], cover=cover,
        )

    # ── 插图（内部辅助） ──

    @staticmethod
    def _save_illustration(conn, owner_type: str, owner_id: str,
                           img: "Illustration | None"):
        if img is None or not img.raw_data:
            return
        # 先删旧，再插入（避免 COALESCE 在 UNIQUE 中不兼容）
        conn.execute(
            "DELETE FROM illustrations WHERE owner_type = ? AND owner_id = ? "
            "AND insert_pos IS ?",
            (owner_type, owner_id, img.insert)
        )
        conn.execute("""
            INSERT INTO illustrations
                (owner_type, owner_id, alt, url, insert_pos, raw_data, format)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (owner_type, owner_id, img.alt, img.url or '',
              img.insert, img.raw_data, img.image_format))

    def _load_illustration(self, conn_or_id, owner_type: str,
                           owner_id: str) -> "Illustration | None":
        """加载单张插图（封面）。conn 可以是 connection 或 novel_id。"""
        if isinstance(conn_or_id, str):
            with self._connect() as conn:
                return self._load_illustration(conn, owner_type, conn_or_id)
        row = conn_or_id.execute(
            "SELECT alt, url, insert_pos, raw_data, format "
            "FROM illustrations WHERE owner_type = ? AND owner_id = ? "
            "ORDER BY insert_pos LIMIT 1",
            (owner_type, owner_id)
        ).fetchone()
        if row is None:
            return None
        from ..models.novel import Illustration
        return Illustration(raw_data=row[3], alt=row[0], insert=row[2], url=row[1])

    def _load_illustrations(self, owner_type: str,
                            owner_id: str) -> tuple["Illustration", ...]:
        """加载所有插图（章节）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT alt, url, insert_pos, raw_data, format "
                "FROM illustrations WHERE owner_type = ? AND owner_id = ? "
                "ORDER BY insert_pos",
                (owner_type, owner_id)
            ).fetchall()
        from ..models.novel import Illustration
        return tuple(
            Illustration(raw_data=r[3], alt=r[0], insert=r[2], url=r[1])
            for r in rows
        )

    # ── 章节 ──

    def save_chapter(self, novel: Novel, chapters: Sequence[Chapter] | Chapter) -> list[str]:
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        saved = []
        with self._connect() as conn:
            for ch in chapters:
                conn.execute("""
                    INSERT OR REPLACE INTO chapters
                        (id, novel_id, url, title, "order", volume,
                         content, time, count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ch.id, novel.id, ch.url, ch.title, ch.order, ch.volume,
                      ch.content, ch.time, ch.count))
                for img in ch.images:
                    self._save_illustration(conn, 'chapter', ch.id, img)
                saved.append(ch.id)
        return saved

    def load_chapter(self, novel_id: str, chapter_id: str) -> Chapter | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, url, title, \"order\", volume, content, time, count "
                "FROM chapters WHERE novel_id = ? AND id = ?",
                (novel_id, chapter_id)
            ).fetchone()
        if row is None:
            return None
        images = self._load_illustrations('chapter', chapter_id)
        return self._row_to_chapter(row, novel_id, images)

    def load_chapters(self, novel_id: str) -> Chapters:
        return Chapters(self._iter_chapters(novel_id))

    def _iter_chapters(self, novel_id: str) -> Iterator[Chapter]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, url, title, \"order\", volume, content, time, count "
                "FROM chapters WHERE novel_id = ? ORDER BY \"order\"",
                (novel_id,)
            ).fetchall()
        for row in rows:
            images = self._load_illustrations('chapter', row[0])
            yield self._row_to_chapter(row, novel_id, images)

    @staticmethod
    def _row_to_chapter(row: tuple, novel_id: str,
                        images: tuple = ()) -> Chapter:
        return Chapter(
            id=row[0], url=row[1], title=row[2], order=row[3],
            volume=row[4], content=row[5], time=row[6], count=row[7],
            images=images,
            novel_id=novel_id,
        )

    # ── 删除 ──

    def delete_novel(self, novel_id: str) -> None:
        _log.info("delete_novel sqlite: id=%s", novel_id)
        with self._connect() as conn:
            conn.execute("DELETE FROM illustrations WHERE owner_id IN "
                         "(SELECT id FROM chapters WHERE novel_id = ?)", (novel_id,))
            conn.execute("DELETE FROM illustrations WHERE owner_type = 'novel' "
                         "AND owner_id = ?", (novel_id,))
            conn.execute("DELETE FROM chapters WHERE novel_id = ?", (novel_id,))
            conn.execute("DELETE FROM novels WHERE id = ?", (novel_id,))


class PostgreSQLStorage(BaseStorage):
    """PostgreSQL 数据库存储（远程/本地均可）。

    连接字符串格式::

        postgresql://user:password@host:5432/dbname
        postgresql://user:password@localhost:5432/novels

    依赖: ``pip install psycopg2-binary``
    """

    def __init__(self, config: StorageOptions):
        self.database_url = config.database_url
        if not self.database_url:
            raise ValueError("PostgreSQL 需要配置 database_url，"
                             "如 postgresql://user:pass@host:5432/dbname")
        self._ensure_psycopg2()
        self._init_db()

    @staticmethod
    def _ensure_psycopg2():
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            raise ImportError(
                "PostgreSQL 后端需要 psycopg2。安装: pip install psycopg2-binary"
            )

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self.database_url)

    def _init_db(self):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS novels (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    url         TEXT NOT NULL,
                    author      TEXT NOT NULL DEFAULT '',
                    serial      INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    tags        JSONB NOT NULL DEFAULT '[]',
                    count       INTEGER,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS chapters (
                    id          TEXT NOT NULL,
                    novel_id    TEXT NOT NULL REFERENCES novels(id),
                    url         TEXT NOT NULL,
                    title       TEXT NOT NULL,
                    "order"     INTEGER NOT NULL DEFAULT 0,
                    volume      TEXT,
                    content     TEXT,
                    time        DOUBLE PRECISION,
                    count       INTEGER,
                                        PRIMARY KEY (novel_id, id)
                );
                CREATE TABLE IF NOT EXISTS illustrations (
                    id          SERIAL PRIMARY KEY,
                    owner_type  TEXT NOT NULL CHECK(owner_type IN ('novel','chapter')),
                    owner_id    TEXT NOT NULL,
                    alt         TEXT,
                    url         TEXT NOT NULL,
                    insert_pos  INTEGER,
                    raw_data    BYTEA,
                    format      TEXT,
                    UNIQUE(owner_type, owner_id, COALESCE(insert_pos, -1))
                );
                CREATE INDEX IF NOT EXISTS idx_chapters_novel
                    ON chapters(novel_id, "order");
                CREATE INDEX IF NOT EXISTS idx_illustrations_owner
                    ON illustrations(owner_type, owner_id);
            """)

    # ── 插图（内部辅助） ──

    @staticmethod
    def _save_illustration(cur, owner_type: str, owner_id: str,
                           img: "Illustration | None"):
        if img is None or not img.raw_data:
            return
        from psycopg2 import Binary
        cur.execute("""
            INSERT INTO illustrations
                (owner_type, owner_id, alt, url, insert_pos, raw_data, format)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (owner_type, owner_id, COALESCE(insert_pos, -1)) DO UPDATE SET
                alt=EXCLUDED.alt, url=EXCLUDED.url,
                raw_data=EXCLUDED.raw_data, format=EXCLUDED.format
        """, (owner_type, owner_id, img.alt, img.url or '',
              img.insert, Binary(img.raw_data), img.image_format))

    def _load_illustration(self, owner_type: str,
                           owner_id: str) -> "Illustration | None":
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT alt, url, insert_pos, raw_data, format "
                "FROM illustrations WHERE owner_type = %s AND owner_id = %s "
                "ORDER BY insert_pos LIMIT 1",
                (owner_type, owner_id)
            )
            row = cur.fetchone()
        if row is None:
            return None
        from ..models.novel import Illustration
        raw = bytes(row[3]) if row[3] else b""
        return Illustration(raw_data=raw, alt=row[0], insert=row[2], url=row[1])

    def _load_illustrations(self, owner_type: str,
                            owner_id: str) -> tuple["Illustration", ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT alt, url, insert_pos, raw_data, format "
                "FROM illustrations WHERE owner_type = %s AND owner_id = %s "
                "ORDER BY insert_pos",
                (owner_type, owner_id)
            )
            rows = cur.fetchall()
        from ..models.novel import Illustration
        return tuple(
            Illustration(raw_data=bytes(r[3]) if r[3] else b"",
                         alt=r[0], insert=r[2], url=r[1])
            for r in rows
        )

    # ── 元数据 ──

    def save_meta(self, novel: Novel) -> str:
        _log.debug("save_meta pg: id=%s", novel.id)
        tags_json = json.dumps(list(novel.tags) if novel.tags else [])
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO novels (id, title, url, author, serial,
                    description, tags, count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title, url=EXCLUDED.url,
                    author=EXCLUDED.author, serial=EXCLUDED.serial,
                    description=EXCLUDED.description, tags=EXCLUDED.tags,
                    count=EXCLUDED.count
            """, (novel.id, novel.title, novel.url, novel.author,
                  novel.serial, novel.description, tags_json, novel.count))
            self._save_illustration(cur, 'novel', novel.id, novel.cover)
        return novel.id

    def load_meta(self, novel_id: str) -> Novel | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, url, author, serial, description, "
                "tags, count FROM novels WHERE id = %s",
                (novel_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        cover = self._load_illustration('novel', novel_id)
        return self._row_to_novel(row, cover)

    def iter_metas(self) -> Iterator[Novel]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, url, author, serial, description, "
                "tags, count FROM novels ORDER BY title"
            )
            rows = cur.fetchall()
        for row in rows:
            cover = self._load_illustration('novel', row[0])
            yield self._row_to_novel(row, cover)

    @staticmethod
    def _row_to_novel(row: tuple, cover=None) -> Novel:
        tags = row[6] if isinstance(row[6], list) else json.loads(row[6] or "[]")
        return Novel(
            id=row[0], title=row[1], url=row[2], author=row[3],
            serial=row[4], description=row[5], tags=tuple(tags),
            count=row[7], cover=cover,
        )

    # ── 章节 ──

    def save_chapter(self, novel: Novel, chapters: Sequence[Chapter] | Chapter) -> list[str]:
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        saved = []
        with self._connect() as conn, conn.cursor() as cur:
            for ch in chapters:
                cur.execute("""
                    INSERT INTO chapters (id, novel_id, url, title, "order",
                        volume, content, time, count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (novel_id, id) DO UPDATE SET
                        url=EXCLUDED.url, title=EXCLUDED.title,
                        "order"=EXCLUDED."order", volume=EXCLUDED.volume,
                        content=EXCLUDED.content, time=EXCLUDED.time,
                        count=EXCLUDED.count
                """, (ch.id, novel.id, ch.url, ch.title, ch.order, ch.volume,
                      ch.content, ch.time, ch.count))
                for img in ch.images:
                    self._save_illustration(cur, 'chapter', ch.id, img)
                saved.append(ch.id)
        return saved

    def load_chapter(self, novel_id: str, chapter_id: str) -> Chapter | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, url, title, \"order\", volume, content, "
                "time, count "
                "FROM chapters WHERE novel_id = %s AND id = %s",
                (novel_id, chapter_id)
            )
            row = cur.fetchone()
        if row is None:
            return None
        images = self._load_illustrations('chapter', chapter_id)
        return self._row_to_chapter(row, novel_id, images)

    def load_chapters(self, novel_id: str) -> Chapters:
        return Chapters(self._iter_chapters(novel_id))

    def _iter_chapters(self, novel_id: str) -> Iterator[Chapter]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, url, title, \"order\", volume, content, "
                "time, count "
                "FROM chapters WHERE novel_id = %s ORDER BY \"order\"",
                (novel_id,)
            )
            rows = cur.fetchall()
        for row in rows:
            images = self._load_illustrations('chapter', row[0])
            yield self._row_to_chapter(row, novel.id, images)

    @staticmethod
    def _row_to_chapter(row: tuple, novel_id: str,
                        images: tuple = ()) -> Chapter:
        return Chapter(
            id=row[0], url=row[1], title=row[2], order=row[3],
            volume=row[4], content=row[5], time=row[6], count=row[7],
            images=images,
            novel_id=novel_id,
        )

    def delete_novel(self, novel_id: str) -> None:
        _log.info("delete_novel pg: id=%s", novel_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM illustrations WHERE owner_id IN "
                        "(SELECT id FROM chapters WHERE novel_id = %s)", (novel_id,))
            cur.execute("DELETE FROM illustrations WHERE owner_type = 'novel' "
                        "AND owner_id = %s", (novel_id,))
            cur.execute("DELETE FROM chapters WHERE novel_id = %s", (novel_id,))
            cur.execute("DELETE FROM novels WHERE id = %s", (novel_id,))

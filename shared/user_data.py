"""用户数据层 — 两个可手改的文本文件，都在 `app_data/config/library/` 下。

- `books.yaml` 书维度账本（分组 / 收藏 / 来源 / 书名）：全量读写，重写走
  "临时文件 + fsync + os.replace"，写前留一份 `.bak`。
- `search_history.jsonl` 搜索历史：只追加；读取时按 (书源, 关键词) 去重，
  超过 `_HISTORY_MAX_LINES` 行压缩到 `_HISTORY_KEEP` 行。

并发保护：进程内 `threading.Lock`（backend 单进程，`uvicorn.run(app)` 不带 workers）。
"""
import json
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

_TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _now() -> str:
    """本地时间字符串 `%Y-%m-%d %H:%M:%S`（字符串序 = 时间序）。"""
    return datetime.now().strftime(_TIME_FMT)


def _validate_entry(path: Path, key, entry: dict) -> None:
    """手写的 groups 结构不对时明确报错，而不是在后面某个 `.get()` 上抛 AttributeError。"""
    groups = entry.get("groups")
    if groups is None:
        return
    if not isinstance(groups, dict):
        raise LibraryCorruptError(
            f"{path}: {key}.groups 必须是映射（{{组名: {{属性}}}}），"
            f"实际是 {type(groups).__name__}"
        )
    for group, attrs in groups.items():
        if attrs is not None and not isinstance(attrs, dict):
            raise LibraryCorruptError(
                f"{path}: {key}.groups.{group} 必须是映射或留空，"
                f"实际是 {type(attrs).__name__}"
            )


def _load_books() -> dict[str, dict]:
    """读 books.yaml 原始 dict。文件不存在 → {}。

    以下情况一律 `LibraryCorruptError`（**绝不降级**）：
    - YAML 语法错、顶层不是映射
    - 文件是 0 字节（正常重写永远带注释头，空文件只可能是写到一半）
    - 条目值是标量/列表（归一成 {} 会害它在下次重写时被静默删掉）
    - 条目里 `groups` 不是映射，或组属性不是映射

    值为 null 的条目（`n1:` 后面空着）归一成 {}。
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
        if path.stat().st_size == 0:
            raise LibraryCorruptError(f"{path}: 文件为空（可能写到一半），请从 .bak 恢复")
        return {}                       # 只有注释头 —— 合法的空账本
    if not isinstance(data, dict):
        raise LibraryCorruptError(
            f"{path}: 顶层必须是映射（dict），实际是 {type(data).__name__}"
        )

    books: dict[str, dict] = {}
    for key, value in data.items():
        if value is None:
            books[str(key)] = {}
            continue
        if not isinstance(value, dict):
            raise LibraryCorruptError(
                f"{path}: 条目 {key!r} 必须是映射，实际是 {type(value).__name__}"
            )
        _validate_entry(path, key, value)
        books[str(key)] = value
    return books


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
        entry["favorited_at"] = _now()
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


# ═══════════════════════════════ 搜索历史（search_history.jsonl） ═══════════════════════════════
#
# append-only：写入只追加一行，同一 `(source_name, keyword)` 再次搜索时也追加
# （新时间戳），去重在读取时做 —— 这样高频写是 O(1)，不需要读-改-写整个文件。

_HISTORY_MAX_LINES = 250     # 超过这个行数触发压缩
_HISTORY_KEEP = 200          # 压缩后保留的最近条数

_next_id_cache: Optional[int] = None      # 下一个可用 id（进程内缓存，None = 未读过文件）


def _read_history_rows() -> list[dict]:
    """逐行解析。坏行 / 缺 id / id 非整数 一律跳过，不 abort 整个读取。"""
    path = HISTORY_PATH
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            hid = obj.get("id")
            if not isinstance(hid, int) or isinstance(hid, bool):
                continue
            keyword = obj.get("keyword")
            if not isinstance(keyword, str) or not keyword:
                continue
            rows.append({
                "id": hid,
                "source_name": obj.get("source_name") or "",
                "keyword": keyword,
                "searched_at": obj.get("searched_at") or "",
            })
    return rows


def _dedup(rows: list[dict]) -> list[dict]:
    """按 (source_name, keyword) 保留 searched_at 最新的一条，再按时间倒序。"""
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["source_name"], row["keyword"])
        prev = latest.get(key)
        if (
            prev is None
            or row["searched_at"] > prev["searched_at"]
            or (row["searched_at"] == prev["searched_at"] and row["id"] > prev["id"])
        ):
            latest[key] = row
    return sorted(latest.values(), key=lambda r: (r["searched_at"], r["id"]), reverse=True)


def _dump_history(rows: list[dict]) -> str:
    """按时间正序落盘（手看时从旧到新）。"""
    ordered = sorted(rows, key=lambda r: (r["searched_at"], r["id"]))
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ordered)


def _append_row(row: dict) -> None:
    """追加一行。文件末尾没有换行符时先补一个，否则两行会被拼成一条。"""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    needs_newline = False
    if HISTORY_PATH.exists() and HISTORY_PATH.stat().st_size:
        with HISTORY_PATH.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) != b"\n"
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _allocate_id(rows: list[dict]) -> int:
    """下一个 id。调用方持锁。

    每次都与文件里的 max 对齐：另一个进程或手改把文件改大之后，缓存不能给出
    已经用过的 id（重了会让 `delete_search_history` 连带删掉另一条）。
    """
    global _next_id_cache
    file_max = max((r["id"] for r in rows), default=0)
    if _next_id_cache is None or _next_id_cache <= file_max:
        _next_id_cache = file_max + 1
    new_id = _next_id_cache
    _next_id_cache = new_id + 1
    return new_id


def get_search_history(limit: int = 50) -> list[dict]:
    """按时间去重倒序返回，最多 limit 条。"""
    with _lock:
        rows = _dedup(_read_history_rows())
    return rows[:limit]


def add_search_history(source_name: str, keyword: str) -> None:
    """记一条搜索。同 (书源, 关键词) 不去重，只追加。"""
    if not keyword:
        return          # 空关键词写进去既读不出也删不掉
    with _lock:
        rows = _read_history_rows()
        row = {
            "id": _allocate_id(rows),
            "source_name": source_name,
            "keyword": keyword,
            "searched_at": _now(),
        }
        _append_row(row)
        if len(rows) + 1 > _HISTORY_MAX_LINES:
            # 注意带上刚追加的 row：rows 是追加前的快照，漏了它会把最新一条压掉
            _atomic_write(HISTORY_PATH, _dump_history(_dedup(rows + [row])[:_HISTORY_KEEP]))


def delete_search_history(history_id: int) -> bool:
    """删一条历史 —— 连同所有同 (书源, 关键词) 的物理行（否则去重后它还在）。"""
    with _lock:
        rows = _read_history_rows()
        target = next((r for r in rows if r["id"] == history_id), None)
        if target is None:
            return False
        key = (target["source_name"], target["keyword"])
        kept = [r for r in rows if (r["source_name"], r["keyword"]) != key]
        _atomic_write(HISTORY_PATH, _dump_history(kept))
        return True


def clear_search_history() -> None:
    global _next_id_cache
    with _lock:
        _atomic_write(HISTORY_PATH, "")
        _next_id_cache = None

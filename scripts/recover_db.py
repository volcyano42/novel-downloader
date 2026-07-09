#!/usr/bin/env python3
"""从损坏的 SQLite .db 中恢复小说数据，重建干净库。

用法::

    python scripts/recover_db.py app_data/storage/7499553647647263806.db

输出: 同名目录下生成 <id>_recovered.db，或覆盖原文件（加 --replace）
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime


def extract_meta(raw: bytes) -> dict | None:
    """从原始字节中提取 meta 信息。"""
    text = raw.decode("utf-8", errors="replace")
    meta = {}

    # 书名 — 在 SQLite 记录中通常紧随 CREATE TABLE 附近或独立行
    # 尝试找紧跟在 schema 后的第一条 meta 记录
    title_matches = re.findall(
        r'(?:title|书名)[:\s]*[「《]?(.{4,50})[」》]?',
        text[:1_000_000],  # 前面部分
    )
    if title_matches:
        meta["title"] = title_matches[0].strip('"\'「」《》')

    # 作者
    author_matches = re.findall(r'作者[：:]\s*(.{2,20})', text[:1_000_000])
    if author_matches:
        meta["author"] = author_matches[0].strip()

    # URL
    url_matches = re.findall(r'(https?://[^\s\x00]{10,200})', text[:1_000_000])
    if url_matches:
        meta["url"] = url_matches[0]

    # serial (连载状态)
    if "完结" in text[:500_000] or "完本" in text[:500_000]:
        meta["serial"] = 1
    else:
        meta["serial"] = 0

    # 简介
    desc_matches = re.findall(r'(?:简介|描述|description)[：:\s]*(.{20,500})', text[:1_000_000])
    if desc_matches:
        meta["description"] = desc_matches[0].strip()

    # 标签
    tag_matches = re.findall(r'\["([^"]+)"(?:,\s*"([^"]+)")*\]', text[:1_000_000])
    if tag_matches:
        meta["tags"] = [t for t in tag_matches[0] if t]

    # 检测到的书名（优先用 chapter 中常见的前缀来推断）
    chapter_titles = re.findall(
        r'第([\d零一二三四五六七八九十百千]+)章[：:\s]*([^\n\x00\r]{1,60})',
        text[:5_000_000],
    )
    if chapter_titles:
        meta["chapter_count"] = len(chapter_titles)

    return meta if meta else None


# UTF-8: 第 = \xe7\xac\xac, 章 = \xe7\xab\xa0
_CHAPTER_PREFIX = b'\xe7\xac\xac'        # "第"
_CHAPTER_SUFFIX = b'\xe7\xab\xa0'        # "章"
_FULLWIDTH_COLON = b'\xef\xbc\x9a'       # "："


def _parse_chapter_title(raw: bytes, offset: int) -> tuple[int, str] | None:
    """尝试从 offset 处解析 '第N章...' 返回 (order, suffix) 或 None。"""
    i = offset
    end = min(offset + 80, len(raw))

    # 跳过 "第"
    if raw[i:i+3] != _CHAPTER_PREFIX:
        return None
    i += 3

    # 读数字
    digits = b""
    while i < end and 0x30 <= raw[i] <= 0x39:  # '0'-'9'
        digits += bytes([raw[i]])
        i += 1
    if not digits:
        return None

    # 跳过 "章" 和可选的冒号/空格
    if raw[i:i+3] == _CHAPTER_SUFFIX:
        i += 3
    else:
        return None

    # 跳过冒号（全角或半角）和空格
    while i < end and raw[i:i+1] in (b':', b' ') or raw[i:i+3] == _FULLWIDTH_COLON:
        if raw[i:i+3] == _FULLWIDTH_COLON:
            i += 3
        else:
            i += 1
    while i < end and raw[i:i+1] == b' ':
        i += 1

    # 读标题后缀（到换行或控制字符）
    suffix_start = i
    while i < end and raw[i] not in (0x00, 0x0a, 0x0d) and raw[i] >= 0x20:
        i += 1
    suffix = raw[suffix_start:i].decode("utf-8", errors="replace").strip()

    try:
        order = int(digits.decode("ascii"))
    except ValueError:
        return None

    return (order, suffix)


def extract_chapters_stream(path: str) -> list[dict]:
    """流式扫描文件提取章节。

    策略: 逐字节扫描 '第' (E7 AC AC)，找到后解析 '第N章'，用章节标题
    作为边界切分正文。
    """
    file_size = os.path.getsize(path)

    # 第一遍: 快速扫描找所有章节位置 (用 bytes.find 比 regex 快得多)
    positions = []
    chunk_size = 20 * 1024 * 1024  # 20MB
    offset = 0
    overlap = 200

    with open(path, "rb") as f:
        carry = b""
        while offset < file_size:
            f.seek(offset)
            chunk = carry + f.read(chunk_size)
            if not chunk or len(chunk) <= len(carry):
                break

            # 在 chunk 中找所有 "第" 并尝试解析
            search_pos = 0
            while True:
                idx = chunk.find(_CHAPTER_PREFIX, search_pos)
                if idx == -1:
                    break
                result = _parse_chapter_title(chunk, idx)
                if result:
                    abs_pos = offset + idx - len(carry)
                    positions.append((abs_pos, result[0], result[1]))
                search_pos = idx + 3  # 跳过 "第"

            carry = chunk[-overlap:] if len(chunk) > overlap else b""
            offset += len(chunk) - len(carry)

    if not positions:
        return []

    # 去重 + 排序
    seen = set()
    unique = []
    for p in positions:
        if p[1] not in seen:
            seen.add(p[1])
            unique.append(p)
    positions = sorted(unique, key=lambda x: x[0])

    print(f"  找到 {len(positions)} 个章节标题")

    # 第二遍: 按章节边界读取内容
    chapters = []
    with open(path, "rb") as f:
        for i, (pos, order, suffix) in enumerate(positions):
            # 确定读取范围: 从当前标题末尾到下一个标题开头
            read_start = pos + 50  # 跳过标题本身的字节
            if i + 1 < len(positions):
                read_end = positions[i + 1][0]
            else:
                read_end = min(pos + 5_000_000, file_size)  # 最后一章最多读 5MB

            if read_end <= read_start:
                continue

            f.seek(read_start)
            raw = f.read(read_end - read_start)

            text = raw.decode("utf-8", errors="replace")
            # 清理二进制垃圾
            text = re.sub(r'\x00+', '', text)
            text = re.sub(r'^[\x00-\x08\x0b\x0c\x0e-\x1f]+', '', text)
            # 去掉卷标行
            text = re.sub(r'^第[一二三四五六七八九十百千]+卷[：:\s]*[^\n]*\n?', '', text)
            text = text.strip()

            if len(text) > 50:
                chapters.append({
                    "id": str(uuid.uuid4()),
                    "url": "",
                    "title": f"第{order}章{' ' + suffix if suffix else ''}",
                    "order": order,
                    "content": text,
                })

    return chapters


def rebuild_db(meta: dict, chapters: list[dict], output_path: str) -> None:
    """用提取的数据重建 SQLite 数据库。"""
    conn = sqlite3.connect(output_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # 创建表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
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
            id          TEXT PRIMARY KEY,
            url         TEXT NOT NULL,
            title       TEXT NOT NULL,
            "order"     INTEGER NOT NULL DEFAULT 0,
            volume      TEXT,
            content     TEXT,
            time        REAL,
            count       INTEGER
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
        CREATE INDEX IF NOT EXISTS idx_chapters_order
            ON chapters("order");
        CREATE INDEX IF NOT EXISTS idx_illustrations_owner
            ON illustrations(owner_type, owner_id);
    """)

    novel_id = meta.get("id", str(uuid.uuid4()))
    tags = meta.get("tags", [])
    tags_json = json.dumps(tags, ensure_ascii=False)

    # 写入 meta
    conn.execute(
        """INSERT OR REPLACE INTO meta (id, title, url, author, serial,
           description, tags, count, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            novel_id,
            meta.get("title", "未知书名"),
            meta.get("url", ""),
            meta.get("author", ""),
            meta.get("serial", 0),
            meta.get("description", ""),
            tags_json,
            len(chapters),
            datetime.now().isoformat(),
        ),
    )

    # 写入章节
    for ch in sorted(chapters, key=lambda c: c["order"]):
        conn.execute(
            """INSERT OR REPLACE INTO chapters (id, url, title, "order", content)
               VALUES (?, ?, ?, ?, ?)""",
            (ch["id"], ch.get("url", ""), ch["title"], ch["order"], ch["content"]),
        )

    conn.commit()
    conn.close()

    print(f"  书名: {meta.get('title', '未知')}")
    print(f"  作者: {meta.get('author', '未知')}")
    print(f"  章节: {len(chapters)} 章")
    print(f"  输出: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="从损坏的 SQLite .db 恢复小说数据")
    parser.add_argument("db_path", help="损坏的 .db 文件路径")
    parser.add_argument("--output", "-o", help="输出路径（默认: <原名>_recovered.db）")
    parser.add_argument("--replace", action="store_true", help="覆盖原文件")
    args = parser.parse_args()

    src = args.db_path
    if not os.path.exists(src):
        print(f"错误: 文件不存在 — {src}")
        sys.exit(1)

    file_size = os.path.getsize(src)
    print(f"读取: {src} ({file_size / 1024 / 1024:.1f} MB)")

    # 只读前 10MB 提取 meta（meta 在文件头）
    with open(src, "rb") as f:
        head = f.read(10_000_000)
    print("提取 meta ...")
    meta = extract_meta(head)

    # 流式扫描章节（不加载全文件）
    print("提取章节 ...")
    chapters = extract_chapters_stream(src)

    if not chapters:
        print("错误: 未能提取到任何章节数据")
        sys.exit(1)

    # 用章节标题推断书名（如果 meta 没提取到）
    if not meta or not meta.get("title"):
        # 从章节内容中推断
        text = raw.decode("utf-8", errors="replace")
        # 扫描内容中重复出现的角色名/小说特征来确认
        meta = meta or {}
        # 从章节标题猜测 — 找第1章的完整标题作为参考
        first_ch = chapters[0] if chapters else {}
        meta["title"] = meta.get("title") or "恢复的小说"

    if args.replace:
        output = src
        # 先备份原文件
        backup = src + ".bak"
        os.rename(src, backup)
        print(f"原文件备份为: {backup}")
    elif args.output:
        output = args.output
    else:
        base = os.path.splitext(src)[0]
        output = f"{base}_recovered.db"

    print("重建数据库 ...")
    rebuild_db(meta, chapters, output)

    # 校验
    print("校验 ...")
    conn = sqlite3.connect(output)
    result = conn.execute("PRAGMA integrity_check").fetchone()
    conn.close()
    if result[0] == "ok":
        print("  ✓ 数据库完整")
    else:
        print(f"  ⚠ {result[0]}")


if __name__ == "__main__":
    main()

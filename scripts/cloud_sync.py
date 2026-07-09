#!/usr/bin/env python3
"""novels.db 云同步 — 七牛 Kodo 直链备份/恢复。

依赖::

    pip install qiniu requests

环境变量::

    export QINIU_ACCESS_KEY=...
    export QINIU_SECRET_KEY=...
    export QINIU_BUCKET=novels-backup
    export QINIU_DOMAIN=http://xxx.bkt.clouddn.com  # 可选

用法::

    python scripts/cloud_sync.py push              # 上传全部小说
    python scripts/cloud_sync.py push <novel_id>   # 上传指定小说
    python scripts/cloud_sync.py pull              # 下载全部小说
    python scripts/cloud_sync.py pull <novel_id>   # 下载指定小说
    python scripts/cloud_sync.py status            # 对比本地与云端
    python scripts/cloud_sync.py delete <novel_id> # 从云端删除备份
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Optional


# ── 配置 ──

def _require_config() -> tuple[str, str, str, str]:
    ak = os.environ.get("QINIU_ACCESS_KEY", "")
    sk = os.environ.get("QINIU_SECRET_KEY", "")
    bucket = os.environ.get("QINIU_BUCKET", "")
    domain = os.environ.get("QINIU_DOMAIN", "")
    if not all([ak, sk, bucket]):
        print("错误: 请先设置七牛密钥环境变量：")
        print("  export QINIU_ACCESS_KEY=...")
        print("  export QINIU_SECRET_KEY=...")
        print("  export QINIU_BUCKET=...")
        sys.exit(1)
    return ak, sk, bucket, domain


# ── 安全快照 ──

def _snapshot(src_path: str, dst_path: str) -> None:
    """在线快照 — SQLite backup API，不阻塞读写。"""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    src.backup(dst)
    dst.close()
    src.close()


def _integrity_check(db_path: str) -> bool:
    """检查数据库是否完整。"""
    conn = sqlite3.connect(db_path)
    result = conn.execute("PRAGMA integrity_check").fetchone()
    conn.close()
    return result[0] == "ok"


# ── 七牛操作 ──

def _qiniu_auth():
    from qiniu import Auth
    ak, sk, _, _ = _require_config()
    return Auth(ak, sk)


def _base_url() -> str:
    """拼接七牛域名，自动补 http://。"""
    _, _, bucket, domain = _require_config()
    domain = domain or f"{bucket}.bkt.clouddn.com"
    if not domain.startswith("http"):
        domain = "http://" + domain
    return domain.rstrip("/")


def _qiniu_upload(local_path: str, remote_key: str) -> str:
    """上传文件到七牛，返回直链 URL。"""
    from qiniu import Auth, put_file_v2
    ak, sk, bucket, domain = _require_config()
    q = Auth(ak, sk)
    token = q.upload_token(bucket, remote_key, 3600)
    ret, info = put_file_v2(token, remote_key, local_path)
    if info.status_code != 200:
        raise RuntimeError(f"上传失败: {info.status_code} {info.text_body}")
    url = f"{_base_url()}/{remote_key}"
    return url


def _qiniu_download(remote_key: str, local_path: str) -> None:
    """从七牛直链下载文件。"""
    import requests
    url = f"{_base_url()}/{remote_key}"
    resp = requests.get(url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"下载失败: {resp.status_code}")
    data = resp.content
    # SQLite 文件头校验 — CDN 可能返回缓存的错误页
    if not data.startswith(b"SQLite format 3\x00"):
        preview = data[:200].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"下载的不是 SQLite 数据库（{len(data)} 字节），可能是 CDN 缓存了错误页面。\n"
            f"  请运行 push --manifest-only --refresh-cdn 刷新缓存后重试。\n"
            f"  内容预览: {preview}"
        )
    with open(local_path, "wb") as f:
        f.write(data)


def _qiniu_list(prefix: str = "novels/") -> list[str]:
    """列出七牛上指定前缀的所有文件。"""
    from qiniu import Auth, BucketManager
    ak, sk, bucket, _ = _require_config()
    q = Auth(ak, sk)
    bm = BucketManager(q)
    keys = []
    marker = None
    while True:
        ret, eof, info = bm.list(bucket, prefix=prefix, marker=marker, limit=1000)
        if ret and "items" in ret:
            for item in ret["items"]:
                keys.append(item["key"])
        if eof:
            break
        marker = ret.get("marker") if ret else None
    return keys


def _qiniu_delete(remote_key: str) -> None:
    """从七牛删除文件。"""
    from qiniu import Auth, BucketManager
    ak, sk, bucket, _ = _require_config()
    q = Auth(ak, sk)
    bm = BucketManager(q)
    ret, info = bm.delete(bucket, remote_key)
    if info.status_code != 200:
        raise RuntimeError(f"删除失败: {info.status_code} {info.text_body}")


# ── CDN 刷新 ──

def _cdn_refresh(urls: list[str]) -> None:
    """刷新七牛 CDN 缓存。"""
    from qiniu import CdnManager
    cdn = CdnManager(_qiniu_auth())
    ret, info = cdn.refresh_urls(urls)
    if info.status_code != 200:
        raise RuntimeError(f"CDN 刷新失败: {info.status_code} {info.text_body}")
    print(f"  🔄 CDN 刷新已提交 ({len(urls)} 个 URL)")


# ── manifest：轻量元数据清单 ──

def _read_novel_meta(db_path: str) -> dict | None:
    """从 per-novel .db 读取元数据。"""
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        meta = conn.execute(
            "SELECT title, author FROM meta"
        ).fetchone()
        if not meta:
            conn.close()
            return None
        chapter_count = conn.execute(
            "SELECT COUNT(*) FROM chapters"
        ).fetchone()[0]
        last = conn.execute(
            "SELECT title FROM chapters ORDER BY \"order\" DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return {
            "title": meta[0],
            "author": meta[1],
            "chapter_count": chapter_count,
            "last_chapter": last[0] if last else "",
        }
    except sqlite3.Error:
        return None


def _make_manifest(novel_id: str, db_path: str) -> dict:
    """生成本地小说的 manifest。"""
    meta = _read_novel_meta(db_path) or {}
    return {
        "novel_id": novel_id,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "chapter_count": meta.get("chapter_count", 0),
        "last_chapter": meta.get("last_chapter", ""),
        "db_size": os.path.getsize(db_path),
    }


def _qiniu_download_json(remote_key: str) -> dict | None:
    """从七牛下载 manifest JSON。"""
    import requests
    url = f"{_base_url()}/{remote_key}"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.json()


# ── 本地文件管理 ──

def _get_local_db_dir() -> Path:
    """获取本地小说库目录。"""
    base = os.environ.get("NOVELS_STORAGE_DIR", "app_data/storage")
    return Path(base)


def _local_novels() -> list[str]:
    """列出本地所有小说 ID。"""
    d = _get_local_db_dir()
    ids = []
    for f in sorted(d.glob("*.db")):
        ids.append(f.stem)
    return ids


# ── 命令 ──

def cmd_push(novel_id: Optional[str] = None, manifest_only: bool = False, refresh_cdn: bool = False):
    """上传：snapshot → 上传七牛。"""
    local_dir = _get_local_db_dir()
    if novel_id:
        targets = [novel_id]
    else:
        targets = _local_novels()

    if not targets:
        print("本地没有小说可上传。")
        return

    for nid in targets:
        db_path = local_dir / f"{nid}.db"
        if not db_path.exists():
            print(f"  ✗ {nid} — 文件不存在，跳过")
            continue

        snapshot_path = None
        if not manifest_only:
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            snapshot_path = tmp.name
            tmp.close()

        try:
            if not manifest_only:
                _snapshot(str(db_path), snapshot_path)
                remote_key = f"novels/{nid}.db"
                url = _qiniu_upload(snapshot_path, remote_key)
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                print(f"  ✓ {nid} ({size_mb:.1f}MB) → {url}")
            # 上传 manifest
            manifest = _make_manifest(nid, str(db_path))
            manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as mt:
                mt.write(manifest_bytes)
                mt.flush()
                _qiniu_upload(mt.name, f"novels/{nid}.manifest.json")
            os.remove(mt.name)
            if manifest_only:
                print(f"  ✓ {nid} — manifest 已更新 ({manifest['chapter_count']} 章)")
            # CDN 刷新
            if refresh_cdn:
                refresh_urls = [f"{_base_url()}/novels/{nid}.manifest.json"]
                if not manifest_only:
                    refresh_urls.append(f"{_base_url()}/novels/{nid}.db")
                _cdn_refresh(refresh_urls)
        finally:
            if snapshot_path:
                try:
                    os.remove(snapshot_path)
                except FileNotFoundError:
                    pass


def cmd_pull(novel_id: Optional[str] = None):
    """下载恢复：下载 → 完整性校验 → 原子替换。"""
    local_dir = _get_local_db_dir()
    local_dir.mkdir(parents=True, exist_ok=True)
    remote_keys = [k for k in _qiniu_list("novels/") if k.endswith(".db")]

    if novel_id:
        remote_key = f"novels/{novel_id}.db"
        if remote_key not in remote_keys:
            print(f"  ✗ {novel_id} — 云端不存在")
            return
        remote_keys = [remote_key]

    if not remote_keys:
        print("云端没有小说备份。")
        return

    for key in remote_keys:
        nid = Path(key).stem
        db_path = local_dir / f"{nid}.db"
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            download_path = tmp.name

        try:
            _qiniu_download(key, download_path)
            if not _integrity_check(download_path):
                print(f"  ✗ {nid} — 下载的文件损坏，跳过")
                continue

            # 替换（shutil.move 兼容跨盘，Windows temp 与目标盘可能不同）
            shutil.move(download_path, str(db_path))
            # 清理旧 WAL/SHM（新连接会自动重建）
            for ext in ("-wal", "-shm"):
                try:
                    os.remove(str(db_path) + ext)
                except FileNotFoundError:
                    pass
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"  ✓ {nid} ({size_mb:.1f}MB) — 已恢复")
        finally:
            try:
                os.remove(download_path)
            except FileNotFoundError:
                pass


def cmd_delete(novel_id: Optional[str] = None):
    """从云端删除备份。"""
    if not novel_id:
        print("错误: delete 必须指定 novel_id，不支持一键全删。")
        sys.exit(1)

    remote_key = f"novels/{novel_id}.db"
    remote_keys = _qiniu_list("novels/")
    if remote_key not in remote_keys:
        print(f"  ✗ {novel_id} — 云端不存在")
        return

    _qiniu_delete(remote_key)
    _qiniu_delete(f"novels/{novel_id}.manifest.json")
    print(f"  ✓ {novel_id} — 已从云端删除")


def cmd_status():
    """对比本地与云端 — 基于 manifest 展示书名、章节数、差异。"""
    local_dir = _get_local_db_dir()
    local_ids = set(_local_novels())

    # 下载所有云端 manifest（轻量 JSON，几 KB）
    all_keys = _qiniu_list("novels/")
    remote_db_keys = {k for k in all_keys if k.endswith(".db")}
    remote_ids = {Path(k).stem for k in remote_db_keys}

    # 解析云端 manifest
    cloud_meta: dict[str, dict] = {}
    for nid in remote_ids:
        manifest = _qiniu_download_json(f"novels/{nid}.manifest.json")
        if manifest:
            cloud_meta[nid] = manifest

    # 分类
    only_local = local_ids - remote_ids
    only_remote = remote_ids - local_ids
    both = local_ids & remote_ids

    ahead = []
    behind = []
    synced = []

    for nid in sorted(both):
        local = _read_novel_meta(str(local_dir / f"{nid}.db")) or {}
        remote = cloud_meta.get(nid, {})
        lc = local.get("chapter_count", 0)
        rc = remote.get("chapter_count", 0)
        title = local.get("title") or remote.get("title") or nid

        if lc > rc:
            ahead.append((title, lc, rc, local.get("last_chapter", "")))
        elif lc < rc:
            behind.append((title, lc, rc, remote.get("last_chapter", "")))
        else:
            synced.append((title, lc, local.get("last_chapter", "")))

    # 输出
    print(f"本地 {len(local_ids)} 本  |  云端 {len(remote_ids)} 本\n")

    if ahead:
        print(f"本地领先 ({len(ahead)} 本) — 需 push:")
        for title, lc, rc, last in ahead:
            print(f"  ↑ {title}")
            print(f"    本地 {lc} 章 / 云端 {rc} 章  ·  最后: {last}")
        print()

    if behind:
        print(f"云端领先 ({len(behind)} 本) — 需 pull:")
        for title, lc, rc, last in behind:
            print(f"  ↓ {title}")
            print(f"    本地 {lc} 章 / 云端 {rc} 章  ·  云端最后: {last}")
        print()

    if synced:
        print(f"已同步 ({len(synced)} 本):")
        for title, count, last in sorted(synced):
            print(f"  ✓ {title}  ({count} 章)")
        print()

    if only_local:
        print(f"仅本地 ({len(only_local)} 本) — push 上传:")
        for nid in sorted(only_local):
            local = _read_novel_meta(str(local_dir / f"{nid}.db")) or {}
            title = local.get("title", nid)
            count = local.get("chapter_count", 0)
            print(f"  → {title}  ({count} 章)")

    if only_remote:
        print(f"仅云端 ({len(only_remote)} 本) — pull 下载:")
        for nid in sorted(only_remote):
            remote = cloud_meta.get(nid, {})
            title = remote.get("title", nid)
            count = remote.get("chapter_count", 0)
            print(f"  → {title}  ({count} 章)")


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(description="novels.db 云同步 — 七牛 Kodo")
    sub = parser.add_subparsers(dest="cmd")

    p_push = sub.add_parser("push", help="上传到七牛")
    p_push.add_argument("novel_id", nargs="?", help="小说 ID，不指定则上传全部")
    p_push.add_argument("--manifest-only", action="store_true", help="仅重新上传 manifest，不传 .db")
    p_push.add_argument("--refresh-cdn", action="store_true", help="上传后刷新 CDN 缓存")

    p_pull = sub.add_parser("pull", help="从七牛下载恢复")
    p_pull.add_argument("novel_id", nargs="?", help="小说 ID，不指定则下载全部")

    p_delete = sub.add_parser("delete", help="从云端删除备份")
    p_delete.add_argument("novel_id", nargs="?", help="小说 ID（必填）")

    sub.add_parser("status", help="对比本地与云端")

    args = parser.parse_args()

    if args.cmd == "push":
        cmd_push(args.novel_id, manifest_only=args.manifest_only, refresh_cdn=args.refresh_cdn)
    elif args.cmd == "pull":
        cmd_pull(args.novel_id)
    elif args.cmd == "delete":
        cmd_delete(args.novel_id)
    elif args.cmd == "status":
        cmd_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

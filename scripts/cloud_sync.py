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
import os
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


def _qiniu_upload(local_path: str, remote_key: str) -> str:
    """上传文件到七牛，返回直链 URL。"""
    from qiniu import Auth, put_file
    ak, sk, bucket, domain = _require_config()
    q = Auth(ak, sk)
    token = q.upload_token(bucket, remote_key, 3600)
    ret, info = put_file(token, remote_key, local_path)
    if info.status_code != 200:
        raise RuntimeError(f"上传失败: {info.status_code} {info.text_body}")
    url = domain.rstrip("/") + "/" + remote_key if domain else f"http://{bucket}.bkt.clouddn.com/{remote_key}"
    return url


def _qiniu_download(remote_key: str, local_path: str) -> None:
    """从七牛直链下载文件。"""
    import requests
    _, _, _, domain = _require_config()
    base = domain.rstrip("/") if domain else f"http://{_require_config()[2]}.bkt.clouddn.com"
    url = f"{base}/{remote_key}"
    resp = requests.get(url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"下载失败: {resp.status_code}")
    with open(local_path, "wb") as f:
        f.write(resp.content)


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

def cmd_push(novel_id: Optional[str] = None):
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

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            snapshot_path = tmp.name

        try:
            _snapshot(str(db_path), snapshot_path)
            remote_key = f"novels/{nid}.db"
            url = _qiniu_upload(snapshot_path, remote_key)
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"  ✓ {nid} ({size_mb:.1f}MB) → {url}")
        finally:
            try:
                os.remove(snapshot_path)
            except FileNotFoundError:
                pass


def cmd_pull(novel_id: Optional[str] = None):
    """下载恢复：下载 → 完整性校验 → 原子替换。"""
    local_dir = _get_local_db_dir()
    local_dir.mkdir(parents=True, exist_ok=True)
    remote_keys = _qiniu_list("novels/")

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

            # 原子替换
            os.replace(download_path, str(db_path))
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
    print(f"  ✓ {novel_id} — 已从云端删除")


def cmd_status():
    """对比本地与云端。"""
    local_ids = set(_local_novels())
    remote_keys = _qiniu_list("novels/")
    remote_ids = {Path(k).stem for k in remote_keys}

    only_local = local_ids - remote_ids
    only_remote = remote_ids - local_ids
    both = local_ids & remote_ids

    print(f"本地: {len(local_ids)} 本 | 云端: {len(remote_ids)} 本\n")

    if both:
        print(f"已同步 ({len(both)} 本):")
        for nid in sorted(both):
            local_size = os.path.getsize(_get_local_db_dir() / f"{nid}.db") / (1024 * 1024)
            print(f"  ✓ {nid} ({local_size:.1f}MB)")

    if only_local:
        print(f"\n仅本地 ({len(only_local)} 本) — 运行 push 上传:")
        for nid in sorted(only_local):
            local_size = os.path.getsize(_get_local_db_dir() / f"{nid}.db") / (1024 * 1024)
            print(f"  → {nid} ({local_size:.1f}MB)")

    if only_remote:
        print(f"\n仅云端 ({len(only_remote)} 本) — 运行 pull 下载:")
        for nid in sorted(only_remote):
            print(f"  → {nid}")


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(description="novels.db 云同步 — 七牛 Kodo")
    sub = parser.add_subparsers(dest="cmd")

    p_push = sub.add_parser("push", help="上传到七牛")
    p_push.add_argument("novel_id", nargs="?", help="小说 ID，不指定则上传全部")

    p_pull = sub.add_parser("pull", help="从七牛下载恢复")
    p_pull.add_argument("novel_id", nargs="?", help="小说 ID，不指定则下载全部")

    p_delete = sub.add_parser("delete", help="从云端删除备份")
    p_delete.add_argument("novel_id", nargs="?", help="小说 ID（必填）")

    sub.add_parser("status", help="对比本地与云端")

    args = parser.parse_args()

    if args.cmd == "push":
        cmd_push(args.novel_id)
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

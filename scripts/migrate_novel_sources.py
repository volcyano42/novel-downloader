"""把小说库里遗留的 Novel.source_name 迁移到 user_data.db 的 novel_sources。

幂等：可重复执行，已存在的行按最新值 UPSERT。

不复用 scripts/migrate_storage.py —— 那是文件布局迁移（storage/*.db →
storage/novels/），与此处的内容迁移职责无关。
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:          # 允许 `python scripts/migrate_novel_sources.py`
    sys.path.insert(0, str(ROOT))

from novelbase.core.options import StorageOptions      # noqa: E402
from novelbase.core.storage import create_storage      # noqa: E402
from shared.config import get_database_url             # noqa: E402
from shared.user_data import set_novel_source          # noqa: E402


# 域名 → 出厂 source_name（2026-09-25 用户裁决；子域按后缀匹配）
DOMAIN_SOURCE_MAP = {
    "fanqienovel.com": "fanqie-api-rain",
    "qimao.com": "qimao-api-rain",
    "92xs.info": "92xs-requests-default",
    "qidian.com": "qidian-browser-default",
}


def _infer_source_from_url(url: str) -> str:
    """按 URL 域名推断出厂书源；未知域名返回空串（不猜）。"""
    host = urlparse(url or "").netloc.lower().split(":")[0]
    for domain, source_name in DOMAIN_SOURCE_MAP.items():
        if host == domain or host.endswith("." + domain):
            return source_name
    return ""


def migrate(novels) -> tuple[int, int]:
    """搬运一批 Novel 的来源。返回 (迁移数, 跳过数)。"""
    moved = skipped = 0
    for novel in novels:
        source_name = (getattr(novel, "source_name", "")
                       or _infer_source_from_url(getattr(novel, "url", "")))
        if not source_name:
            skipped += 1
            continue
        set_novel_source(novel.id, source_name)
        moved += 1
    return moved, skipped


def main() -> None:
    """命令行入口：两种后端都扫。

    注意：**sqlite 后端的 meta 表没有 `source_name` 列**（`SQLiteStorage._row_to_novel`
    用固定列构造 `Novel`），故 sqlite 侧必然 0 条；游离属性只出现在 **local JSON
    后端**的旧数据上（`Novel.loads(**json_data)` 的 `**kwargs` setattr）。两者都扫是
    为了兼容仍在使用 local 后端的旧库。
    """
    moved = skipped = 0

    sqlite_storage = create_storage(
        StorageOptions(backend="sqlite", database_url=get_database_url()))
    m, s = migrate(list(sqlite_storage.iter_metas()))
    moved += m
    skipped += s

    local_dir = ROOT / "app_data" / "storage"
    if local_dir.is_dir():
        try:
            local_storage = create_storage(
                StorageOptions(backend="local", base_dir=str(local_dir)))
            m, s = migrate(list(local_storage.iter_metas()))
            moved += m
            skipped += s
        except Exception as e:                       # local 后端缺失/为空时不应中断
            print(f"local 后端扫描跳过: {e}")

    print(f"完成：迁移 {moved} 条，跳过 {skipped} 条（无来源）")


if __name__ == "__main__":
    main()

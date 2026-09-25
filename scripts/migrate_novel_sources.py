"""把小说库里遗留的 Novel.source_name 迁移到 user_data.db 的 novel_sources。

幂等：可重复执行，已存在的行按最新值 UPSERT。

不复用 scripts/migrate_storage.py —— 那是文件布局迁移（storage/*.db →
storage/novels/），与此处的内容迁移职责无关。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:          # 允许 `python scripts/migrate_novel_sources.py`
    sys.path.insert(0, str(ROOT))

from novelbase.core.options import StorageOptions      # noqa: E402
from novelbase.core.storage import create_storage      # noqa: E402
from shared.config import get_database_url             # noqa: E402
from shared.user_data import set_novel_source          # noqa: E402


def migrate(novels) -> tuple[int, int]:
    """搬运一批 Novel 的来源。返回 (迁移数, 跳过数)。"""
    moved = skipped = 0
    for novel in novels:
        source_name = getattr(novel, "source_name", "") or ""
        if not source_name:
            skipped += 1
            continue
        set_novel_source(novel.id, source_name)
        moved += 1
    return moved, skipped


def main() -> None:
    storage = create_storage(StorageOptions(backend="sqlite",
                                            database_url=get_database_url()))
    moved, skipped = migrate(list(storage.iter_metas()))
    print(f"完成：迁移 {moved} 条，跳过 {skipped} 条（无来源）")


if __name__ == "__main__":
    main()

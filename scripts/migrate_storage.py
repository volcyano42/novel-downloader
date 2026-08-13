"""storage 分层迁移：storage/*.db → storage/novels/，user_data.db → storage/users/default/。

幂等：已迁移的文件跳过。不删除源文件（move 是原子重命名）。
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORAGE = ROOT / "app_data" / "storage"


def main():
    novels_dir = STORAGE / "novels"
    users_dir = STORAGE / "users" / "default"
    novels_dir.mkdir(parents=True, exist_ok=True)
    users_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for db in sorted(STORAGE.glob("*.db")):
        if db.name == "user_data.db":
            target = users_dir / db.name
        elif db.name == "sync.ffs_db":
            continue  # FreeFileSync 元数据，跳过
        else:
            target = novels_dir / db.name
        if target.exists():
            print(f"跳过（已存在）: {db.name}")
            continue
        shutil.move(str(db), str(target))
        moved += 1
        print(f"移动: {db.name} → {target.relative_to(STORAGE)}")

    print(f"完成，共移动 {moved} 个文件")


if __name__ == "__main__":
    main()

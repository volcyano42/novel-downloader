"""存量来源迁移：正确搬运 + 幂等。"""
from novelbase.models.novel import Novel
from shared import user_data


def _fake_novel(novel_id: str, source_name: str) -> Novel:
    n = Novel(title="t", url=f"https://x/{novel_id}", id=novel_id,
              serial=1, author="a", description="d")
    n.source_name = source_name          # 模拟旧 JSON 残留的游离属性
    return n


def test_migrate_moves_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    from scripts import migrate_novel_sources as m
    novels = [
        _fake_novel("n1", "fanqie-api-rain"),
        _fake_novel("n2", "qimao-api-rain"),
        _fake_novel("n3", ""),           # 无来源 → 跳过
    ]

    moved, skipped = m.migrate(novels)
    assert (moved, skipped) == (2, 1)
    assert user_data.get_novel_source("n1") == "fanqie-api-rain"
    assert user_data.get_novel_source("n3") is None

    # 幂等：再跑一遍，值不变、仍报同样统计
    moved2, skipped2 = m.migrate(novels)
    assert (moved2, skipped2) == (2, 1)
    assert user_data.get_novel_source("n1") == "fanqie-api-rain"

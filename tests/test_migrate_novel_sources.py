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


class _FakeStorage:
    def __init__(self, novels):
        self._novels = novels

    def iter_metas(self, include_images: bool = True):
        return iter(self._novels)


def _prep_main(tmp_path, monkeypatch):
    """把 user_data 与 ROOT/local 目录都指向 tmp，隔离真实数据。"""
    from scripts import migrate_novel_sources as m
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    (tmp_path / "app_data" / "storage").mkdir(parents=True)
    return m


def test_main_covers_both_backends_and_tolerates_local_failure(tmp_path, monkeypatch, capsys):
    m = _prep_main(tmp_path, monkeypatch)
    calls = []

    # 场景 1：两后端都正常 → 两后端都被调用、统计合并
    def ok_create_storage(opts):
        calls.append(opts.backend)
        if opts.backend == "sqlite":
            return _FakeStorage([_fake_novel("s1", "")])          # 0 迁移 1 跳过
        return _FakeStorage([_fake_novel("l1", "fanqie-api-rain"),
                             _fake_novel("l2", "")])              # 1 迁移 1 跳过

    monkeypatch.setattr(m, "create_storage", ok_create_storage)
    m.main()
    assert calls == ["sqlite", "local"]                           # 两后端都被调用
    assert user_data.get_novel_source("l1") == "fanqie-api-rain"  # local 真正搬运
    assert "迁移 1 条，跳过 2 条" in capsys.readouterr().out      # 统计合并

    # 场景 2：local 抛错 → 不中断，sqlite 结果仍保留
    def bad_create_storage(opts):
        if opts.backend == "sqlite":
            return _FakeStorage([_fake_novel("s2", "qimao-api-rain")])  # 1 迁移
        raise RuntimeError("local 后端不可用")

    monkeypatch.setattr(m, "create_storage", bad_create_storage)
    m.main()                                                      # 不抛异常
    out = capsys.readouterr().out
    assert "local 后端扫描跳过" in out
    assert "迁移 1 条，跳过 0 条" in out                          # sqlite 结果保留
    assert user_data.get_novel_source("s2") == "qimao-api-rain"

from shared import config as sc


def test_merged_source_config_three_layers(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "source_name": n, "enabled": True,
        "default_config": {"search": {"mode": "requests", "timeout": 30, "retry_times": 3}},
    })
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["mode"] == "requests"
    assert merged["search"]["timeout"] == 30          # 第 2 层
    # 第 3 层覆盖
    sc.save_site_config("demo-requests-default", {"search": {"timeout": 99}})
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["timeout"] == 99


def test_is_source_enabled_user_override(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.list_sources", lambda: ["a-x-default"])
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {"enabled": False})
    assert sc.is_source_enabled("a-x-default") is False                # 出厂 false
    sc.save_site_config("a-x-default", {"enabled": True})              # 用户层覆盖
    assert sc.is_source_enabled("a-x-default") is True
    assert sc.enabled_source_names() == ["a-x-default"]

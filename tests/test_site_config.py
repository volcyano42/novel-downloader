"""site 配置三层合并（merged_source_config）测试。

三层：ENGINE_DEFAULTS[mode]（系统默认）→ source.json.default_config[cap]（书源出厂）
→ sites/{source_name}.yaml[cap]（用户层）。未知书源返回 {}。
"""
from shared import config as sc


def test_merged_source_config_unknown_source_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {})
    assert sc.merged_source_config("nope") == {}


def test_merged_source_config_engine_defaults_then_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "default_config": {"search": {"mode": "requests", "timeout": 30, "retry_times": 7}},
    })
    merged = sc.merged_source_config("demo-requests-default")
    # 第 1 层 ENGINE_DEFAULTS["requests"] 提供的字段仍在
    assert merged["search"]["backoff_factor"] == sc.ENGINE_DEFAULTS["requests"]["backoff_factor"]
    # 第 2 层 manifest 覆盖
    assert merged["search"]["timeout"] == 30
    assert merged["search"]["retry_times"] == 7
    assert merged["search"]["mode"] == "requests"


def test_merged_source_config_user_layer_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "default_config": {"search": {"mode": "requests", "timeout": 30, "retry_times": 3}},
    })
    sc.save_site_config("demo-requests-default", {"search": {"timeout": 99}})
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["timeout"] == 99
    # 用户层未覆盖的字段保留第 2 层值
    assert merged["search"]["retry_times"] == 3


def test_merged_source_config_user_mode_is_ignored(monkeypatch, tmp_path):
    """用户层不决定 mode；即使写了 mode 也忽略，mode 恒取书源声明。"""
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "default_config": {"search": {"mode": "requests"}},
    })
    sc.save_site_config("demo-requests-default", {"search": {"mode": "browser", "timeout": 5}})
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["mode"] == "requests"
    assert merged["search"]["timeout"] == 5

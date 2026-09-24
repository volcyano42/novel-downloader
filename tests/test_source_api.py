import pytest

from novelbase.source import capabilities, get_manifest, list_sources, resolve


def test_list_sources_contains_ten_new_names():
    names = list_sources()
    assert "fanqie-requests-default" in names
    assert "92xs-requests-default" in names
    assert "fanqie" not in names                  # 旧的平台名不再是书源名
    assert "fanqie_requests_default" not in names  # 目录名不是 source_name（下划线 vs 连字符）
    assert len(set(names)) == len(names)


def test_get_manifest_identity():
    m = get_manifest("92xs-requests-default")
    assert m["source_name"] == "92xs-requests-default"
    assert isinstance(m["enabled"], bool)


def test_get_manifest_unknown():
    with pytest.raises(KeyError):
        get_manifest("nope")


def test_capabilities_returns_capability_to_mode():
    caps = capabilities("92xs-requests-default")
    assert caps == {
        "search": "requests",
        "novel_info": "requests",
        "chapter_list": "requests",
        "chapter_content": "requests",
    }
    assert capabilities("nope") == {}


def test_resolve_returns_function_and_mode():
    fn, mode = resolve("92xs-requests-default", "search")
    assert callable(fn)
    assert mode == "requests"
    assert fn.__name__ == "search"


def test_resolve_unknown_capability():
    with pytest.raises(ValueError):
        resolve("92xs-requests-default", "canonical_url")


def test_resolve_signature_check():
    """resolve 返回的函数必须含 CAPABILITY_META 声明的必需参数。"""
    fn, _ = resolve("92xs-requests-default", "novel_info")
    assert {"url", "engine"} <= set(fn.__code__.co_varnames[: fn.__code__.co_argcount])


def test_platform_concepts_removed():
    import novelbase.source as s
    for gone in ("platform_from_url", "register_source"):
        assert not hasattr(s, gone), f"{gone} 应已删除"


def test_get_manifest_checks_capability_files(tmp_path, monkeypatch):
    """能力段 ⇔ .py 文件双向一致：get_manifest 时校验（spec 规则 1）。"""
    import novelbase.source as s
    from novelbase.sources.manifest import ManifestError

    d = tmp_path / "demo_requests_default"
    d.mkdir()
    (d / "source.json").write_text(
        '{"source_name": "demo-requests-default", "enabled": true, '
        '"default_config": {"search": {"mode": "requests"}}}', encoding="utf-8")
    # 缺 search.py → check_capability_files 抛 ManifestError
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))
    with pytest.raises(ManifestError):
        s.get_manifest("demo-requests-default")


def test_compiled_mode_reads_manifest(monkeypatch):
    """编译模式（__compiled__ 在 globals）下，list_sources/get_manifest 走 _manifest。"""
    import novelbase.source as s

    fake_sources = {"demo_requests_default": {
        "source_name": "demo-requests-default",
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }}
    monkeypatch.setattr(s, "_is_compiled", lambda: True)
    monkeypatch.setattr(s, "_compiled_sources", lambda: fake_sources)
    monkeypatch.setattr(s, "_compiled_dir_by_source",
                        lambda: {"demo-requests-default": "demo_requests_default"})

    assert s.list_sources() == ["demo-requests-default"]
    assert s.capabilities("demo-requests-default") == {"search": "requests"}
    assert s.get_manifest("demo-requests-default")["enabled"] is True


def test_split_source_name():
    from novelbase.source import split_source_name
    assert split_source_name("fanqie-requests-default") == ("fanqie", "requests", "default")
    assert split_source_name("qimao-api-rain") == ("qimao", "api", "rain")
    assert split_source_name("92xs-requests-default") == ("92xs", "requests", "default")
    assert split_source_name("fanqie") == ("fanqie", "", "")


def test_resolve_source_name():
    from novelbase.source import resolve_source_name
    # 已是书源名 → 原样
    assert resolve_source_name("fanqie-requests-default") == "fanqie-requests-default"
    # 站点名 + mode → 该 mode 的唯一书源
    assert resolve_source_name("fanqie", "requests") == "fanqie-requests-default"
    # 站点名 + mode + variant → 精确命中
    assert resolve_source_name("fanqie", "api", "rain") == "fanqie-api-rain"
    # api 无 variant → 取该站点首个 api 书源
    assert resolve_source_name("fanqie", "api").startswith("fanqie-api-")
    with pytest.raises(KeyError):
        resolve_source_name("nope", "requests")

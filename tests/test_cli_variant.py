"""CLI variant 解析与 build_options 的 variant 感知测试。

规则：variant 数量 ≤1 时直接使用唯一项；多于 1 个时——
- 交互式 CLI（main.py → cli/interactive）：询问用户选择，会话级记住
- 非交互 CLI（cli.py → cli/main）：未指定 --variant 时提示并列出所有名称后退出
"""
import pytest

import cli.config
import cli.main


def _site(browser=None, requests=None, api=None) -> dict:
    cfg = {}
    if browser is not None:
        cfg["browser"] = browser
    if requests is not None:
        cfg["requests"] = requests
    if api is not None:
        cfg["api"] = api
    return cfg


# ── cli.config.resolve_variant ──


def test_resolve_variant_single_browser_returns_it():
    site = _site(browser={"default": {"headless": True}})
    assert cli.config.resolve_variant(site, "browser") == "default"


def test_resolve_variant_single_api_returns_it():
    site = _site(api={"rain": {"key": ""}})
    assert cli.config.resolve_variant(site, "api") == "rain"


def test_resolve_variant_multiple_unset_returns_none():
    site = _site(api={"oiapi": {"key": ""}, "rain": {"key": ""}})
    assert cli.config.resolve_variant(site, "api") is None


def test_resolve_variant_multiple_explicit():
    site = _site(api={"oiapi": {"key": ""}, "rain": {"key": ""}})
    assert cli.config.resolve_variant(site, "api", "rain") == "rain"


def test_resolve_variant_missing_raises():
    site = _site(api={"oiapi": {"key": ""}})
    with pytest.raises(ValueError):
        cli.config.resolve_variant(site, "api", "nope")


def test_resolve_variant_none_available():
    assert cli.config.resolve_variant({}, "api") is None


# ── cli.config.build_options 的 variant 感知 ──


def test_build_options_api_explicit_variant():
    site = _site(api={
        "oiapi": {"key": "k1", "timeout": 30},
        "rain": {"key": "k2", "timeout": 99},
    })
    opts = cli.config.build_options({"mode": "api"}, site, "rain")
    assert opts.mode == "api"
    assert opts.api.name == "rain"
    assert opts.api.timeout == 99


def test_build_options_api_unset_takes_first_enabled():
    site = _site(api={
        "oiapi": {"key": "k1"},
        "rain": {"key": "k2", "enabled": False},
    })
    opts = cli.config.build_options({"mode": "api"}, site)
    assert opts.api.name == "oiapi"


def test_build_options_api_missing_variant_raises():
    site = _site(api={"oiapi": {"key": ""}})
    with pytest.raises(ValueError):
        cli.config.build_options({"mode": "api"}, site, "nope")


def test_build_options_browser_explicit_variant():
    site = _site(browser={
        "default": {"headless": True},
        "rain": {"headless": False},
    })
    opts = cli.config.build_options({"mode": "browser"}, site, "rain")
    assert opts.browser.headless is False


def test_build_options_browser_unset_prefers_default():
    site = _site(browser={
        "default": {"headless": True},
        "rain": {"headless": False},
    })
    opts = cli.config.build_options({"mode": "browser"}, site)
    assert opts.browser.headless is True


# ── 非交互 CLI（cli.main._resolve_variant）──


def test_main_resolve_variant_multiple_requires_flag(capsys, monkeypatch):
    site = _site(api={"oiapi": {"key": ""}, "rain": {"key": ""}})
    monkeypatch.setattr(cli.main, "load_site_config", lambda p: site)
    with pytest.raises(SystemExit) as exc:
        cli.main._resolve_variant("fanqie", "api", None)
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "--variant" in out
    assert "oiapi" in out and "rain" in out


def test_main_resolve_variant_single_defaults(monkeypatch):
    site = _site(browser={"default": {"headless": True}})
    monkeypatch.setattr(cli.main, "load_site_config", lambda p: site)
    assert cli.main._resolve_variant("fanqie", "browser", None) == "default"


def test_main_resolve_variant_explicit(monkeypatch):
    site = _site(api={"oiapi": {"key": ""}, "rain": {"key": ""}})
    monkeypatch.setattr(cli.main, "load_site_config", lambda p: site)
    assert cli.main._resolve_variant("fanqie", "api", "rain") == "rain"


# ── 交互式 CLI（cli.interactive._resolve_variant）──


def test_interactive_resolve_variant_asks_and_caches(monkeypatch):
    import cli.interactive as it
    site = _site(api={"oiapi": {"key": ""}, "rain": {"key": ""}})
    monkeypatch.setattr(it, "load_site_config", lambda p: site)
    monkeypatch.setattr(it, "_select", lambda msg, choices: "rain")
    assert it._resolve_variant("fanqie", "api") == "rain"

    # 会话级缓存：第二次不再询问
    calls: list = []
    monkeypatch.setattr(it, "_select", lambda msg, choices: calls.append(1) or "oiapi")
    assert it._resolve_variant("fanqie", "api") == "rain"
    assert calls == []
    it._variant_cache.clear()


def test_interactive_resolve_variant_cancel_falls_back(monkeypatch):
    import cli.interactive as it
    site = _site(api={"oiapi": {"key": ""}, "rain": {"key": ""}})
    monkeypatch.setattr(it, "load_site_config", lambda p: site)
    monkeypatch.setattr(it, "_select", lambda msg, choices: None)
    assert it._resolve_variant("fanqie", "api") == "oiapi"
    it._variant_cache.clear()


def test_interactive_resolve_variant_single_no_ask(monkeypatch):
    import cli.interactive as it
    site = _site(browser={"default": {"headless": True}})
    monkeypatch.setattr(it, "load_site_config", lambda p: site)
    assert it._resolve_variant("fanqie", "browser") == "default"

# -*- coding: utf-8 -*-
"""交互式 CLI（cli/ui.py、cli/notify.py、cli/interactive.py、cli/menus.py）测试。"""
from __future__ import annotations


# ═══════════════════════════════════════════════════════════════
# cli.ui 交互辅助层
# ═══════════════════════════════════════════════════════════════

class TestUi:
    def test_parse_order_string_simple(self):
        from cli.ui import parse_order_string
        assert parse_order_string("1,2,3", 10) == [0, 1, 2]

    def test_parse_order_string_range(self):
        from cli.ui import parse_order_string
        assert parse_order_string("1-3", 10) == [0, 1, 2]

    def test_parse_order_string_open_end(self):
        from cli.ui import parse_order_string
        assert parse_order_string("8-", 10) == [7, 8, 9]

    def test_parse_order_string_open_start(self):
        from cli.ui import parse_order_string
        assert parse_order_string("-3", 10) == [0, 1, 2]

    def test_parse_order_string_mixed_dedup_sorted(self):
        from cli.ui import parse_order_string
        assert parse_order_string("3,1-2,5,5", 10) == [0, 1, 2, 4]

    def test_parse_order_string_empty(self):
        from cli.ui import parse_order_string
        assert parse_order_string("", 10) == []
        assert parse_order_string(" , ,", 10) == []

    def test_parse_order_string_clamped(self):
        from cli.ui import parse_order_string
        assert parse_order_string("1-99", 5) == [0, 1, 2, 3, 4]

    def test_select_dict(self, monkeypatch, capsys):
        from cli.ui import _select
        monkeypatch.setattr("builtins.input", lambda _: "2")
        assert _select("选一个", {"A": 1, "B": 2}) == 2

    def test_select_list_quit(self, monkeypatch):
        from cli.ui import _select
        monkeypatch.setattr("builtins.input", lambda _: "q")
        assert _select("选一个", [("A", 1), ("B", 2)]) is None

    def test_select_invalid_then_valid(self, monkeypatch, capsys):
        from cli.ui import _select
        inputs = iter(["abc", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        assert _select("选一个", [("A", 1), ("B", 2)]) == 1
        assert "输入错误" in capsys.readouterr().out

    def test_select_eof(self, monkeypatch):
        from cli.ui import _select
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        assert _select("选一个", [("A", 1)]) is None

    def test_text_input_value(self, monkeypatch):
        from cli.ui import _text_input
        monkeypatch.setattr("builtins.input", lambda _: "hello")
        assert _text_input("输入") == "hello"

    def test_text_input_blank(self, monkeypatch):
        from cli.ui import _text_input
        monkeypatch.setattr("builtins.input", lambda _: "   ")
        assert _text_input("输入") is None

    def test_text_input_eof(self, monkeypatch):
        from cli.ui import _text_input
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        assert _text_input("输入") is None

    def test_input_int_default_on_blank(self, monkeypatch):
        from cli.ui import _input_int
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _input_int("线程", 3) == 3

    def test_input_int_value(self, monkeypatch):
        from cli.ui import _input_int
        monkeypatch.setattr("builtins.input", lambda _: "5")
        assert _input_int("线程", 3) == 5

    def test_input_int_invalid(self, monkeypatch, capsys):
        from cli.ui import _input_int
        monkeypatch.setattr("builtins.input", lambda _: "abc")
        assert _input_int("线程", 3) == 3

    def test_input_float_value(self, monkeypatch):
        from cli.ui import _input_float
        monkeypatch.setattr("builtins.input", lambda _: "2.5")
        assert _input_float("延迟", 3.0) == 2.5

    def test_show_sources(self, monkeypatch):
        from cli.ui import _show_sources
        import novelbase.source as src_mod
        monkeypatch.setattr(src_mod, "list_sources", lambda: ["fanqie-api-rain", "92xs-requests-default"])
        labels = _show_sources()
        assert labels == {"fanqie-api-rain": "fanqie-api-rain", "92xs-requests-default": "92xs-requests-default"}

    def test_source_label(self):
        from cli.ui import _source_label
        labels = {"fanqie-requests-default": "fanqie-requests-default"}
        assert _source_label(labels, "fanqie-requests-default") == "fanqie-requests-default"
        assert _source_label(labels, "unknown") == "unknown"


# ═══════════════════════════════════════════════════════════════
# cli.notify 通知模块
# ═══════════════════════════════════════════════════════════════

class TestNotify:
    def test_notify_empty_config(self, monkeypatch):
        from cli import notify as mod
        monkeypatch.setattr(mod, "bell", lambda *a, **k: None)
        monkeypatch.setattr(mod, "system_notify", lambda *a, **k: None)
        mod.notify({}, complete=1, incomplete=1)  # 不抛异常即通过

    def test_notify_sound_none(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda *a, **k: calls.append("bell"))
        monkeypatch.setattr(mod, "system_notify", lambda *a, **k: calls.append("system"))
        mod.notify({"sound": "none"}, complete=1, incomplete=1)
        assert calls == []

    def test_notify_bell_on_complete(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda count=1, interval=0.15: calls.append(("bell", count)))
        monkeypatch.setattr(mod, "system_notify", lambda *a, **k: calls.append("system"))
        mod.notify({"sound": "bell"}, complete=2, incomplete=0)
        assert calls == [("bell", 1)]

    def test_notify_system_on_incomplete(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda *a, **k: calls.append("bell"))
        monkeypatch.setattr(mod, "system_notify", lambda title, body="": calls.append(("system", title, body)))
        mod.notify({"sound": "system"}, complete=0, incomplete=3)
        assert calls[0][0] == "system"
        assert "不完整章节" in calls[0][2]

    def test_notify_disabled_flags(self, monkeypatch):
        from cli import notify as mod
        calls = []
        monkeypatch.setattr(mod, "bell", lambda *a, **k: calls.append("bell"))
        mod.notify({"sound": "bell", "on_complete": False, "on_incomplete": False},
                   complete=1, incomplete=1)
        assert calls == []

    def test_system_notify_fallback_bell(self, monkeypatch):
        from cli import notify as mod
        import subprocess
        calls = []
        def boom(*a, **k):
            raise Exception("powershell 不可用")
        monkeypatch.setattr(subprocess, "run", boom)
        monkeypatch.setattr(mod, "bell", lambda count=1, interval=0.15: calls.append(count))
        mod.system_notify("标题")
        assert calls == [1]


# ═══════════════════════════════════════════════════════════════
# cli.menus 菜单系统（书源维度）
# ═══════════════════════════════════════════════════════════════

class TestMenus:
    def test_fmt_summary_empty(self):
        from cli.menus import _fmt_summary
        assert _fmt_summary({}) == "未设置"
        assert _fmt_summary({"download": {}}) == "未设置"

    def test_fmt_summary_enabled(self):
        from cli.menus import _fmt_summary
        cfg = {"download": {"formats": ["epub", "txt"]}}
        assert _fmt_summary(cfg) == "epub, txt"

    def test_get_delay_from_merged(self, monkeypatch):
        from cli import menus
        monkeypatch.setattr(menus, "merged_source_config",
                            lambda n: {"search": {"delay": [1, 2]}})
        assert menus._get_delay("a-x-default", "search") == (1.0, 2.0)
        assert menus._get_delay("a-x-default", "missing") == (0, 0)

    def test_get_delay_default(self, monkeypatch):
        from cli import menus
        monkeypatch.setattr(menus, "merged_source_config", lambda n: {})
        assert menus._get_delay("a-x-default", "requests") == (0, 0)

    def test_set_delay_writes_user_layer(self, monkeypatch, tmp_path):
        import cli.config as ccfg
        monkeypatch.setattr(ccfg, "CONFIG_DIR", tmp_path)
        from cli import menus
        menus._set_delay("a-x-default", "search", 0.5, 1.5)
        from cli.config import load_site_config
        assert load_site_config("a-x-default")["search"]["delay"] == [0.5, 1.5]

    def test_do_settings_download_threads(self, monkeypatch, tmp_path):
        import cli.config as ccfg
        monkeypatch.setattr(ccfg, "CONFIG_DIR", tmp_path)
        from cli import menus
        monkeypatch.setattr(menus, "save_main_config", lambda cfg: None)
        inputs = iter(["1", "1", "8", "0", "0"])
        monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
        cfg = {}
        menus.do_settings(cfg)
        assert cfg["download"]["max_workers"] == 8

    def test_settings_source_edit_capability_field(self, monkeypatch, tmp_path):
        import cli.config as ccfg
        monkeypatch.setattr(ccfg, "CONFIG_DIR", tmp_path)
        from cli import menus
        monkeypatch.setattr(menus, "list_sources", lambda: ["a-x-default"])
        monkeypatch.setattr(menus, "effective_capabilities", lambda n: {"search": "requests"})
        monkeypatch.setattr(menus, "merged_source_config",
                            lambda n: {"search": {"mode": "requests", "timeout": 30, "delay": [3, 6]}})
        monkeypatch.setattr(menus, "_select", lambda *a, **k: "a-x-default")
        # do_settings=2 → _select 选源 → 详情=1(search 配置) → 编辑=2(超时) → 输入 42 → 0 → 0 → 0
        inputs = iter(["2", "1", "2", "42", "0", "0", "0"])
        monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
        menus.do_settings({})
        from cli.config import load_site_config
        assert load_site_config("a-x-default")["search"]["timeout"] == 42


# ═══════════════════════════════════════════════════════════════
# cli.interactive 交互主循环（书源维度）
# ═══════════════════════════════════════════════════════════════

class _FakeResult:
    def __init__(self, title, author, url, source_name):
        self.title = title
        self.author = author
        self.url = url
        self.source_name = source_name


class TestInteractive:
    def test_do_search_keyword_uses_all_sources(self, monkeypatch, capsys):
        from cli import interactive as mod
        monkeypatch.setattr(mod, "default_source_names", lambda: ["a-x-default"])
        seen = []

        async def fake_search(sources, query, engines, **kw):
            seen.append(list(sources))
            return ()

        monkeypatch.setattr(mod, "search", fake_search)
        url, name = mod.do_search("测试")
        assert seen == [["a-x-default"]] and url is None
        assert "未找到结果" in capsys.readouterr().out

    def test_do_search_keyword_backend_error(self, monkeypatch, capsys):
        from cli import interactive as mod

        async def boom(*a, **k):
            raise RuntimeError("网络错误")

        monkeypatch.setattr(mod, "default_source_names", lambda: ["fanqie-requests-default"])
        monkeypatch.setattr(mod, "search", boom)
        url, name = mod.do_search("测试")
        assert url is None and name is None
        assert "搜索失败" in capsys.readouterr().out

    def test_do_search_keyword_aggregates_all_sources(self, monkeypatch, capsys):
        from cli import interactive as mod
        calls = []

        async def fake_search(sources, query, engines, **kw):
            calls.append(list(sources))
            src = sources[0]
            return (_FakeResult(f"书-{src}", "作者", f"https://x/{src}", src),)

        monkeypatch.setattr(mod, "default_source_names", lambda: ["a-x-default", "b-y-default"])
        monkeypatch.setattr(mod, "search", fake_search)
        monkeypatch.setattr(mod, "_select", lambda *a, **k: 0)
        url, name = mod.do_search("测试")
        assert calls == [["a-x-default"], ["b-y-default"]]
        assert name == "a-x-default"
        assert url == "https://x/a-x-default"

    def test_do_search_no_sources(self, monkeypatch, capsys):
        from cli import interactive as mod
        monkeypatch.setattr(mod, "default_source_names", lambda: [])
        url, name = mod.do_search("测试")
        assert url is None and name is None
        assert "没有可用的书源" in capsys.readouterr().out

    def test_do_search_url_manual_source(self, monkeypatch, capsys):
        from cli import interactive as mod

        class _Novel:
            url = "https://x/1"
            title = "书"
            author = "作者"

        async def fake_meta(url, source_name, engines, **kw):
            return _Novel()

        monkeypatch.setattr(mod, "list_sources", lambda: ["a-x-default"])
        monkeypatch.setattr(mod, "_select", lambda *a, **k: "a-x-default")
        monkeypatch.setattr(mod, "resolve_meta", fake_meta)
        url, name = mod.do_search("https://x/1")
        assert url == "https://x/1" and name == "a-x-default"

    def test_do_download_selects_source(self, monkeypatch):
        from cli import interactive as mod
        import cli.core as core
        seen = {}

        async def fake_inner(source_name, url, group, format_configs, **kw):
            seen["source_name"] = source_name
            seen["url"] = url

        monkeypatch.setattr(mod, "list_sources", lambda: ["a-x-default"])
        monkeypatch.setattr(mod, "_select", lambda *a, **k: "a-x-default")
        monkeypatch.setattr(mod, "_text_input", lambda *a, **k: None)
        monkeypatch.setattr(core, "_do_download_inner", fake_inner)
        mod.do_download("https://x/1", "默认", {})
        assert seen == {"source_name": "a-x-default", "url": "https://x/1"}

    def test_do_download_cancel_returns(self, monkeypatch, capsys):
        from cli import interactive as mod
        import cli.core as core
        called = []

        async def fake_inner(*a, **k):
            called.append(True)

        monkeypatch.setattr(mod, "list_sources", lambda: ["a-x-default", "b-y-default"])
        monkeypatch.setattr(mod, "_select", lambda *a, **k: None)  # 用户取消选源
        monkeypatch.setattr(mod, "_text_input", lambda *a, **k: None)
        monkeypatch.setattr(core, "_do_download_inner", fake_inner)
        mod.do_download("https://x/1", "默认", {})
        assert called == []                     # 取消不得回退首源、不得触发下载
        assert "已取消" in capsys.readouterr().out

    def test_update_one_async_uses_source_name(self, monkeypatch, capsys):
        import asyncio
        from cli import interactive as mod
        import cli.core as core

        class _Novel:
            source_name = ""
            extra = {"platform": "old-platform"}  # 旧键非空也不应被使用
            id = "x"
            url = "u"

        monkeypatch.setattr(core, "_get_storage", lambda: object())
        rc = asyncio.run(mod._update_one_async(_Novel(), 3))
        assert rc == 0
        assert "无法确定书源" in capsys.readouterr().out

    def test_visit_site_removed(self):
        from cli import interactive as mod
        assert not hasattr(mod, "do_visit_site")

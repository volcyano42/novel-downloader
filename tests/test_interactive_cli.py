# -*- coding: utf-8 -*-
"""交互式 CLI（cli/ui.py、cli/notify.py、cli/interactive.py）测试。"""
from __future__ import annotations

import pytest


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

    def test_show_platforms(self, monkeypatch):
        from cli.ui import _show_platforms
        import novelbase.source as src_mod
        fake = {
            "fanqie": {"name": "fanqie", "show_name": "番茄", "hosts": ("fanqienovel.com",)},
            "qidian": {"name": "qidian", "show_name": "起点", "hosts": ("qidian.com",)},
        }
        monkeypatch.setattr(src_mod, "register_source", lambda: fake)
        labels = _show_platforms()
        assert labels == {"番茄 (fanqie)": "fanqie", "起点 (qidian)": "qidian"}

    def test_platform_label(self):
        from cli.ui import _platform_label
        labels = {"番茄 (fanqie)": "fanqie"}
        assert _platform_label(labels, "fanqie") == "番茄 (fanqie)"
        assert _platform_label(labels, "unknown") == "unknown"


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
# cli.menus 菜单系统
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

    def test_get_set_delay(self):
        from cli.menus import _get_delay, _set_delay
        site_cfg = {"browser": {"delay": [1, 2]}}
        assert _get_delay(site_cfg, "browser") == (1.0, 2.0)
        _set_delay(site_cfg, "browser", 0.5, 1.5)
        assert _get_delay(site_cfg, "browser") == (0.5, 1.5)

    def test_get_delay_default(self):
        from cli.menus import _get_delay
        assert _get_delay({}, "requests") == (3.0, 6.0)


# ═══════════════════════════════════════════════════════════════
# cli.interactive 交互主循环
# ═══════════════════════════════════════════════════════════════

class TestInteractive:
    def test_platform_from_url_fanqie(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("https://fanqienovel.com/page/7123456789012345678") == "fanqie"

    def test_platform_from_url_qidian(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("https://www.qidian.com/book/1012345678/") == "qidian"

    def test_platform_from_url_qimao(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("https://www.qimao.com/shuku/195958/") == "qimao"

    def test_platform_from_url_unknown_raises(self):
        from cli.interactive import _platform_from_url
        import pytest as _pytest
        with _pytest.raises(ValueError):
            _platform_from_url("https://example.com/novel/1")

    def test_platform_from_url_92xs_alias(self):
        from cli.interactive import _platform_from_url
        assert _platform_from_url("http://www.92xs.info/html/96850/35632400.html") == "92xs"

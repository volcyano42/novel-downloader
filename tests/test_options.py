"""配置层测试：Options / APIOptions / RequestsOptions / BrowserOptions / ExportOptions"""
from __future__ import annotations

import pytest

from novelbase.core.options import (
    Options, APIOptions, RequestsOptions, BrowserOptions,
    ExportOptions,
)


# ═══════════════════════════════════════════════════════════════
# 子选项 dataclass
# ═══════════════════════════════════════════════════════════════

class TestAPIOptions:
    def test_defaults(self):
        o = APIOptions()
        assert o.name is None
        assert o.delay == (3, 5)
        assert o.timeout == 30
        assert o.retry_times == 3
        assert o.backoff_factor == 2
        assert o.key is None
        assert o.params is None

    def test_custom(self):
        o = APIOptions(name="myapi", key="sk-xxx", params={"site": "fanqie"})
        assert o.name == "myapi"
        assert o.key == "sk-xxx"
        assert o.params == {"site": "fanqie"}


class TestRequestsOptions:
    def test_defaults(self):
        o = RequestsOptions()
        assert "Mozilla" in o.headers["User-Agent"]
        assert o.cookies is None
        assert o.proxies is None

    def test_custom(self):
        o = RequestsOptions(
            headers={"User-Agent": "custom"},
            cookies={"session": "abc"},
            proxies={"http": "http://proxy:8080"},
        )
        assert o.headers["User-Agent"] == "custom"
        assert o.cookies == {"session": "abc"}
        assert o.proxies == {"http": "http://proxy:8080"}


class TestBrowserOptions:
    def test_defaults(self):
        o = BrowserOptions()
        assert o.browser_type == "chromium"
        assert o.headless is False
        assert o.user_data_dir is None
        assert o.viewport is None
        assert o.extra_args is None

    def test_custom(self):
        o = BrowserOptions(
            browser_type="firefox", headless=True,
            user_data_dir="/tmp/data", viewport={"width": 1920, "height": 1080},
        )
        assert o.browser_type == "firefox"
        assert o.headless is True
        assert o.viewport["width"] == 1920

    def test_extra_args(self):
        o = BrowserOptions(extra_args=["--no-sandbox", "--remote-debugging-port=9222"])
        assert o.extra_args == ["--no-sandbox", "--remote-debugging-port=9222"]

    def test_browser_options_auto_reconnect_default_false(self):
        b = BrowserOptions()
        assert b.auto_reconnect is False


class TestExportOptions:
    def test_create(self):
        o = ExportOptions(output_path="/tmp/out")
        assert str(o.output_path) == "/tmp/out"
        assert o.enabled is True
        assert o.file_name_template == "{name}"

    def test_custom(self):
        o = ExportOptions(
            output_path="/tmp/{title}.txt", enabled=False,
            file_name_template="{title}",
        )
        assert o.enabled is False


# ═══════════════════════════════════════════════════════════════
# Options 聚合
# ═══════════════════════════════════════════════════════════════

class TestOptions:
    def test_default_mode(self):
        o = Options()
        assert o.mode == "api"

    def test_set_mode(self):
        o = Options()
        o.set_mode("browser")
        assert o.mode == "browser"
        assert o.set_mode("requests") is o  # 链式调用

    def test_set_mode_no_validation(self):
        """目前不校验 mode 值，非法值也可设置"""
        o = Options().set_mode("invalid")
        assert o.mode == "invalid"

    def test_set_api_options(self):
        o = Options().set_api_options(name="test", key="sk-xxx")
        assert o.api.name == "test"
        assert o.api.key == "sk-xxx"

    def test_set_requests_options(self):
        o = Options().set_requests_options(timeout=60, cookies={"a": "b"})
        assert o.requests.timeout == 60
        assert o.requests.cookies == {"a": "b"}

    def test_set_browser_options(self):
        o = Options().set_browser_options(headless=True, browser_type="firefox")
        assert o.browser.headless is True
        assert o.browser.browser_type == "firefox"

    def test_set_browser_options_none_values(self):
        o = Options().set_browser_options(user_data_dir=None, viewport=None)
        assert o.browser.user_data_dir is None
        assert o.browser.viewport is None

    def test_set_browser_options_auto_reconnect(self):
        o = Options().set_browser_options(auto_reconnect=True)
        assert o.browser.auto_reconnect is True

    def test_set_export(self):
        opt = ExportOptions(format="txt", output_path="/tmp/out")
        o = Options().set_export(opt)
        assert o.export is opt
        assert o.export.format == "txt"

    def test_enable_export(self):
        opt = ExportOptions(format="txt", output_path="/tmp/out")
        o = Options().set_export(opt)
        o.enable_export(False)
        assert o.export.enabled is False
        o.enable_export(True)
        assert o.export.enabled is True

    def test_export_none_by_default(self):
        o = Options()
        assert o.export is None
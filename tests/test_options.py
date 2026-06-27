"""配置层测试：Options / APIOptions / RequestsOptions / BrowserOptions / ExportOptions"""
from __future__ import annotations

import pytest

from nldlder.core.options import (
    Options, APIOptions, RequestsOptions, BrowserOptions,
    ExportOptions,
)
from nldlder.utils.logger import LogOptions


# ═══════════════════════════════════════════════════════════════
# 子选项 dataclass
# ═══════════════════════════════════════════════════════════════

class TestAPIOptions:
    def test_defaults(self):
        o = APIOptions()
        assert o.enabled is True
        assert o.name is None
        assert o.delay == (3, 5)
        assert o.timeout == 30
        assert o.retry_times == 3
        assert o.batch_size == 1
        assert o.backoff_factor == 2
        assert o.key is None
        assert o.params is None

    def test_custom(self):
        o = APIOptions(name="myapi", key="sk-xxx", batch_size=5, params={"site": "fanqie"})
        assert o.name == "myapi"
        assert o.key == "sk-xxx"
        assert o.batch_size == 5
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

    def test_custom(self):
        o = BrowserOptions(
            browser_type="firefox", headless=True,
            user_data_dir="/tmp/data", viewport={"width": 1920, "height": 1080},
        )
        assert o.browser_type == "firefox"
        assert o.headless is True
        assert o.viewport["width"] == 1920


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
        o = Options().set_api_options(name="test", key="sk-xxx", batch_size=10)
        assert o.api.name == "test"
        assert o.api.key == "sk-xxx"
        assert o.api.batch_size == 10

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

    def test_set_log_options(self):
        o = Options().set_log_options(level="INFO", enabled=True, output_dir="/tmp/logs")
        assert o.log.level == "INFO"
        assert o.log.output_dir == "/tmp/logs"

    def test_log_options_default(self):
        o = Options()
        assert isinstance(o.log, LogOptions)

    def test_set_export_options(self):
        opt = ExportOptions(output_path="/tmp/out")
        opt.format = "txt"  # set_export_options 需要 format 属性
        o = Options().set_export_options(opt)
        assert "txt" in o.exports

    def test_enable_format(self):
        opt = ExportOptions(output_path="/tmp/out")
        opt.format = "txt"
        o = Options().set_export_options(opt)
        o.enable_format("txt", enabled=False)
        assert o.exports["txt"].enabled is False

    def test_enable_format_missing_key(self):
        """enable_format 未注册的格式抛出 KeyError"""
        o = Options()
        with pytest.raises(KeyError):
            o.enable_format("ghost")

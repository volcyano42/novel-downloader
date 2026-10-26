"""delay 出厂默认 [0, 0]（不设置 = 不限速）；用户层显式 delay 仍生效。"""
import pytest

import shared.config as config_service

REQUESTS_SRC = "92xs-requests-default"
BROWSER_SRC = "fanqie-browser-default"
API_SRC = "fanqie-api-rain"


@pytest.fixture
def isolated_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sources = tmp_path / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    return sources


def test_unconfigured_delay_defaults_to_zero(isolated_sources):
    """未配置 delay 时，三个能力的 delay 均为出厂默认 (0, 0)。"""
    assert config_service.build_options(REQUESTS_SRC, "requests").requests.delay == (0, 0)
    assert config_service.build_options(BROWSER_SRC, "browser").browser.delay == (0, 0)
    assert config_service.build_options(API_SRC, "api").api.delay == (0, 0)


def test_user_layer_delay_override(isolated_sources):
    """用户层显式 delay 优先于出厂默认。"""
    (isolated_sources / f"{REQUESTS_SRC}.yaml").write_text(
        "delay: [2, 3]\n", encoding="utf-8")
    assert config_service.build_options(REQUESTS_SRC, "requests").requests.delay == (2, 3)

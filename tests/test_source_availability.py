# -*- coding: utf-8 -*-
"""环境能力表：`NLD_PLATFORM` / `supported_modes` / 可用性 / 启用集 / API 与 core 兜底。

桌面（未设 `NLD_PLATFORM`）必须与历史行为完全一致；`NLD_PLATFORM=android` 时
browser 一律不可用（书源不进启用集、覆盖被忽略、写入口 400）。
"""
import asyncio
import sys

import httpx
import pytest

from shared import config as sc

BROWSER_CAPS = {"search": "browser", "novel_info": "browser",
                "chapter_list": "browser", "chapter_content": "browser"}
REQUESTS_CAPS = {"search": "requests", "novel_info": "requests",
                 "chapter_list": "requests", "chapter_content": "requests"}


@pytest.fixture
def isolated_sites(tmp_path, monkeypatch):
    """隔离用户层 sites 目录（不读写真实 app_data/config）。"""
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    return tmp_path / "sites"


def _patch_sources(monkeypatch, capabilities_map, enabled=True):
    """把书源清单 / 声明能力 / 出厂启用状态钉成给定值。"""
    monkeypatch.setattr("novelbase.source.list_sources", lambda: sorted(capabilities_map))
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: dict(capabilities_map.get(n, {})))
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda n: {"source_name": n, "enabled": enabled, "default_config": {}})


def _get(app, path: str):
    async def _call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(_call())


def _put(app, path: str, payload: dict):
    async def _call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.put(path, json=payload)

    return asyncio.run(_call())


# ── 环境声明 ─────────────────────────────────────────────────

def test_platform_defaults_to_desktop(monkeypatch):
    monkeypatch.delenv("NLD_PLATFORM", raising=False)
    assert sc.platform() == "desktop"
    assert sc.supported_modes() == sc.VALID_MODES


def test_supported_modes_android_excludes_browser(monkeypatch):
    monkeypatch.setenv("NLD_PLATFORM", "android")
    assert sc.platform() == "android"
    assert sc.supported_modes() == sc.ANDROID_MODES == ("requests", "api")
    assert "browser" not in sc.supported_modes()


def test_supported_modes_invalid_platform_falls_back_to_all(monkeypatch):
    monkeypatch.setenv("NLD_PLATFORM", "ios")
    assert sc.platform() == "desktop"
    assert sc.supported_modes() == sc.VALID_MODES


# ── 有效能力与覆盖回退 ───────────────────────────────────────

def _write_user_override(tmp_path, source_name, cap, mode):
    """在用户层 sites/{source}.yaml 写一条 {cap}.mode 覆盖。"""
    sc.save_site_config(source_name, {cap: {"mode": mode}})


def test_override_applies_on_desktop(isolated_sites, tmp_path, monkeypatch):
    monkeypatch.delenv("NLD_PLATFORM", raising=False)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS})
    _write_user_override(tmp_path, "demo-requests-default", "search", "browser")

    caps = sc.effective_capabilities("demo-requests-default")
    assert caps["search"] == "browser"          # 桌面：覆盖生效（历史行为）
    assert sc.is_source_available("demo-requests-default") is True


def test_override_ignored_on_android(isolated_sites, tmp_path, monkeypatch):
    monkeypatch.setenv("NLD_PLATFORM", "android")
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS})
    _write_user_override(tmp_path, "demo-requests-default", "search", "browser")

    caps = sc.effective_capabilities("demo-requests-default")
    assert caps["search"] == "requests"         # Android：不可用覆盖被忽略，回退声明值
    assert sc.available_capabilities("demo-requests-default") == REQUESTS_CAPS
    assert sc.is_source_available("demo-requests-default") is True


# ── 可用性与启用集 ───────────────────────────────────────────

def test_is_source_available_desktop_vs_android(isolated_sites, monkeypatch):
    _patch_sources(monkeypatch, {"a-browser-default": BROWSER_CAPS,
                                 "b-requests-default": REQUESTS_CAPS})

    monkeypatch.delenv("NLD_PLATFORM", raising=False)
    assert sc.is_source_available("a-browser-default") is True

    monkeypatch.setenv("NLD_PLATFORM", "android")
    assert sc.is_source_available("a-browser-default") is False   # 全能力 browser → 整源不可用
    assert sc.is_source_available("b-requests-default") is True
    assert sc.available_capabilities("a-browser-default") == {}
    assert sc.is_source_available("no-such-source") is False      # 未知书源


def test_enabled_source_names_filters_unavailable(isolated_sites, monkeypatch):
    _patch_sources(monkeypatch, {"a-browser-default": BROWSER_CAPS,
                                 "b-requests-default": REQUESTS_CAPS})

    monkeypatch.delenv("NLD_PLATFORM", raising=False)
    assert sc.enabled_source_names() == ["a-browser-default", "b-requests-default"]

    monkeypatch.setenv("NLD_PLATFORM", "android")
    assert sc.enabled_source_names() == ["b-requests-default"]


def test_mixed_mode_source_is_unavailable_on_android(isolated_sites, monkeypatch):
    """混 mode 私有源在 Android 上整源判不可用（不做「半可用」）。"""
    mixed = {"search": "requests", "novel_info": "requests",
             "chapter_list": "browser", "chapter_content": "requests"}
    _patch_sources(monkeypatch, {"c-mixed-default": mixed})
    monkeypatch.setenv("NLD_PLATFORM", "android")
    assert sc.is_source_available("c-mixed-default") is False
    assert sc.enabled_source_names() == []


# ── API 出口 ─────────────────────────────────────────────────

@pytest.fixture
def android_app(isolated_sites, monkeypatch):
    monkeypatch.setenv("NLD_PLATFORM", "android")
    from backend.main import app
    return app


def test_sources_api_reports_available(android_app):
    r = _get(android_app, "/api/v2/download/sources")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["fanqie-browser-default"]["available"] is False
    assert data["fanqie-requests-default"]["available"] is True
    assert data["fanqie-browser-default"]["enabled"] is True      # 出厂启用仍如实回报（前端置灰）


def test_source_config_get_is_allowed_for_unavailable_source(android_app):
    r = _get(android_app, "/api/v2/config/sources/fanqie-browser-default")
    assert r.status_code == 200                                  # GET 必须放行（否则无法置灰展示）
    assert r.json()["data"]["available"] is False


def test_source_config_put_rejects_enabling_unavailable_source(android_app):
    r = _put(android_app, "/api/v2/config/sources/fanqie-browser-default", {"enabled": True})
    assert r.status_code == 400


def test_source_config_put_rejects_unsupported_mode(android_app):
    r = _put(android_app, "/api/v2/config/sources/fanqie-requests-default",
             {"config": {"search": {"mode": "browser"}}})
    assert r.status_code == 400


def test_source_config_put_allows_supported_write(android_app):
    r = _put(android_app, "/api/v2/config/sources/fanqie-requests-default",
             {"config": {"search": {"mode": "api"}}, "enabled": False})
    assert r.status_code == 200


def test_environment_api(android_app):
    r = _get(android_app, "/api/v2/config/environment")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["platform"] == "android"
    assert data["supported_modes"] == ["requests", "api"]


def test_search_rejects_unavailable_source(android_app):
    r = _get(android_app, "/api/v2/download/search?query=abc&source=fanqie-browser-default")
    assert r.status_code == 400


# ── core 兜底异常 ────────────────────────────────────────────

def test_async_playwright_raises_mode_unavailable(monkeypatch):
    from novelbase.core import engine as eng
    from novelbase.core.exceptions import ModeUnavailableError

    monkeypatch.setitem(sys.modules, "playwright.async_api", None)  # 令 import 抛 ImportError
    with pytest.raises(ModeUnavailableError) as ei:
        eng._async_playwright()
    assert ei.value.mode == "browser"
    assert "browser" in str(ei.value)

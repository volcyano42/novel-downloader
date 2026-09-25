"""backend download 路由的运行时契约（T7 定型后的新形状）。

不启 TestClient/lifespan（避免 Windows 下 lifespan 挂起），直接 `asyncio.run`
调 async 路由函数；monkeypatch 书源 `resolve`、引擎工厂、模块级依赖，验证：
- `/sources` 平铺形状 `{source_name: {capabilities: {cap: mode}, enabled: bool}}`。
- `/search`：`source` 空 → 并发全部启用书源（`enabled_source_names()`）；单书源 →
  引擎按 `source_name` 绑定；`query` 为 URL 时 `source` 必填（400）；URL 结果带 `source_name`。
- `/novel`、`/novel/{id}`、`/novel/{id}/chapters` 的 Query 仅 `source`（=source_name），
  URL 无法推断书源时要求显式 `source`。
- `/novel/{id}/chapter` 把 `source`/`novel_url` 透传给 `task_manager.create_task`。
- 旧 `platform`/`mode`/`variant` 面（`/platform`、`/detect`、`_pick_source`）已删除。
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend.routers import download as dl
from backend.schemas import FetchMetaRequest, DownloadChapterRequest
from backend.services import source_guard
from novelbase.models.novel import Chapters, Novel, SearchResult


def _allow_sources(monkeypatch, *names):
    """把边界校验（require_known_source）的已知书源收窄为给定的虚拟名。"""
    monkeypatch.setattr(source_guard, "list_sources", lambda: list(names))


def _patch_engine_factory(monkeypatch):
    """替换 dl 模块内的引擎工厂，记录 (source_name, mode)，返回占位 engine。"""
    seen: list[tuple[str, str]] = []

    def fake(source_name, mode):
        seen.append((source_name, mode))
        return object()

    monkeypatch.setattr(dl, "get_cached_engine", fake)
    return seen


def test_sources_shape_is_flat(monkeypatch):
    monkeypatch.setattr(dl, "list_sources", lambda: ["92xs-requests-default"])
    monkeypatch.setattr(dl, "effective_capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(dl, "is_source_enabled", lambda n: True)
    out = asyncio.run(dl.list_all_sources())
    assert out == {"92xs-requests-default": {"capabilities": {"search": "requests"}, "enabled": True}}


def test_sources_include_disabled(monkeypatch):
    """列全部书源（含未启用），enabled 走 is_source_enabled(name)。"""
    monkeypatch.setattr(dl, "list_sources", lambda: ["a-x-default", "b-y-default"])
    monkeypatch.setattr(dl, "effective_capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(dl, "is_source_enabled", lambda n: n == "a-x-default")
    out = asyncio.run(dl.list_all_sources())
    assert out["a-x-default"]["enabled"] is True
    assert out["b-y-default"]["enabled"] is False


def test_search_empty_source_uses_enabled(monkeypatch):
    """空 source → 对每个启用书源各发一次 search(...)，每次只带该源。"""
    monkeypatch.setattr(dl, "enabled_source_names", lambda: ["a-x-default", "b-y-default"])
    called = []

    async def fake_search(sources, query, engines, **kw):
        called.append(list(sources))
        return ()

    monkeypatch.setattr(dl, "search", fake_search)
    asyncio.run(dl.search_novels(query="关键词", source=""))
    assert sorted(called) == [["a-x-default"], ["b-y-default"]]


def test_search_single_source_binds_engine(monkeypatch):
    seen = _patch_engine_factory(monkeypatch)
    captured = {}

    async def fake_search(sources, query, engines, **kw):
        captured["sources"] = list(sources)
        captured["engine"] = engines("requests")
        return ()

    monkeypatch.setattr(dl, "search", fake_search)
    asyncio.run(dl.search_novels(query="关键词", source="92xs-requests-default"))
    assert captured["sources"] == ["92xs-requests-default"]
    assert seen == [("92xs-requests-default", "requests")]


def test_parallel_same_mode_uses_per_source_engine(monkeypatch):
    """并发多个同 mode 书源时，每个源必须拿到自己的引擎（修复共享首个源引擎的缺陷）。"""
    monkeypatch.setattr(dl, "enabled_source_names",
                        lambda: ["a-requests-default", "b-requests-default"])
    engine_calls = []
    monkeypatch.setattr(dl, "get_cached_engine",
                        lambda name, mode: engine_calls.append((name, mode)) or f"engine:{name}")

    per_source_engine = {}

    async def fake_search(sources, query, engines, **kw):
        assert len(sources) == 1, f"每源应各发一次单源 search，实际 {sources}"
        name = sources[0]
        per_source_engine[name] = engines("requests")
        return (SearchResult(title=name, author="x", url=f"https://x/{name}",
                             source_name=name),)

    monkeypatch.setattr(dl, "search", fake_search)
    out = asyncio.run(dl.search_novels(query="关键词", source=""))

    # 修复前：两个源都会拿到共享解析器里「首个源」(a) 的引擎。
    assert per_source_engine == {"a-requests-default": "engine:a-requests-default",
                                 "b-requests-default": "engine:b-requests-default"}
    assert sorted(engine_calls) == [("a-requests-default", "requests"),
                                    ("b-requests-default", "requests")]
    assert {r.source_name for r in out} == {"a-requests-default", "b-requests-default"}


def test_parallel_one_source_fails_others_survive(monkeypatch):
    """单个源抛错时不影响其它源（复刻 core 的单源静默跳过）。"""
    monkeypatch.setattr(dl, "enabled_source_names",
                        lambda: ["bad-requests-default", "good-requests-default"])
    monkeypatch.setattr(dl, "get_cached_engine", lambda name, mode: object())

    async def fake_search(sources, query, engines, **kw):
        if sources[0] == "bad-requests-default":
            raise RuntimeError("boom")
        return (SearchResult(title="ok", author="a", url="https://x/1",
                             source_name=sources[0]),)

    monkeypatch.setattr(dl, "search", fake_search)
    out = asyncio.run(dl.search_novels(query="关键词", source=""))
    assert [r.source_name for r in out] == ["good-requests-default"]


def test_url_search_requires_source(monkeypatch):
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="https://x/1", source=""))
    assert ei.value.status_code == 400


def test_url_search_returns_source_name(monkeypatch):
    async def fake_novel(url, engine, **kw):
        return Novel(url=url, title="T", author="A", serial=1, description="d")

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_novel, "requests"))
    seen = _patch_engine_factory(monkeypatch)
    out = asyncio.run(dl.search_novels(query="http://www.92xs.info/book/9999.html",
                                       source="92xs-requests-default"))
    assert out[0].title == "T"
    assert out[0].source_name == "92xs-requests-default"
    assert seen == [("92xs-requests-default", "requests")]


def test_resolve_meta_route_requires_source(monkeypatch):
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.resolve_meta_route(
            body=FetchMetaRequest(url="https://fanqienovel.com/page/7123456789012345678"),
            source=""))
    assert ei.value.status_code == 400


def test_resolve_meta_route_with_source(monkeypatch):
    async def fake_novel(url, engine, **kw):
        return Novel(url=url, title="T", author="A", serial=2, description="d")

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_novel, "requests"))
    seen = _patch_engine_factory(monkeypatch)
    body = FetchMetaRequest(url="https://fanqienovel.com/page/7123456789012345678")
    out = asyncio.run(dl.resolve_meta_route(body=body, source="fanqie-requests-default"))
    assert out["title"] == "T"
    assert seen == [("fanqie-requests-default", "requests")]


def test_chapter_list_route_with_source(monkeypatch):
    async def fake_cl(url, engine, **kw):
        return Chapters([])

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_cl, "requests"))
    seen = _patch_engine_factory(monkeypatch)
    out = asyncio.run(dl.resolve_chapter_list_route(
        novel_id="abc", url="http://www.92xs.info/book/9999.html",
        source="92xs-requests-default"))
    assert out == []
    assert seen == [("92xs-requests-default", "requests")]


def test_download_chapters_passes_source(monkeypatch):
    recorded = {}

    def fake_create_task(novel_id, chapters, title, source_name, novel_url):
        recorded.update(novel_id=novel_id, chapters=chapters, title=title,
                        source_name=source_name, novel_url=novel_url)
        return {"task_id": "x", "total": len(chapters)}

    monkeypatch.setattr(dl.task_manager, "create_task", fake_create_task)
    body = [DownloadChapterRequest(id="c1", url="u", novel_id="n1", title="t", order=1)]
    out = asyncio.run(dl.download_chapters(novel_id="n1", body=body, title="T",
                                           source="92xs-requests-default",
                                           novel_url="http://x/1"))
    assert out == {"task_id": "x", "total": 1}
    assert recorded["source_name"] == "92xs-requests-default"
    assert recorded["novel_url"] == "http://x/1"


def test_platform_and_detect_gone():
    assert not hasattr(dl, "detect_platform")
    assert not hasattr(dl, "list_platforms")
    assert not hasattr(dl, "_pick_source")


def test_search_result_data_uses_source_name():
    from backend.schemas import SearchResultData
    r = SearchResultData(title="t", author="a", url="http://x", source_name="92xs-requests-default")
    assert r.source_name == "92xs-requests-default"
    assert not hasattr(r, "platform")


# ── config 路由按书源（T8）────────────────────────────

def test_get_source_config_merged(monkeypatch, tmp_path):
    from backend.routers import config as cfg
    monkeypatch.setattr(cfg.config_service, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg.config_service, "merged_source_config",
                        lambda n: {"search": {"mode": "requests", "timeout": 30}})
    monkeypatch.setattr(cfg.config_service, "is_source_enabled", lambda n: True)
    monkeypatch.setattr(cfg.config_service, "capabilities", lambda n: {"search": "requests"}, raising=False)
    out = asyncio.run(cfg.get_source_config("92xs-requests-default"))
    assert out["enabled"] is True and out["config"]["search"]["timeout"] == 30


def test_get_source_config_shape(monkeypatch):
    """GET /config/sources/{name} 契约形状：{source_name, enabled, capabilities,
    declared_capabilities, config}（capabilities 为有效 mode）。"""
    from backend.routers import config as cfg
    monkeypatch.setattr(cfg.config_service, "merged_source_config", lambda n: {"search": {"mode": "requests"}})
    monkeypatch.setattr(cfg.config_service, "is_source_enabled", lambda n: False)
    monkeypatch.setattr(cfg, "capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(cfg, "effective_capabilities", lambda n: {"search": "browser"})
    _allow_sources(monkeypatch, "demo-requests-default")
    out = asyncio.run(cfg.get_source_config("demo-requests-default"))
    assert set(out.keys()) == {"source_name", "enabled", "capabilities",
                               "declared_capabilities", "config"}
    assert out["source_name"] == "demo-requests-default"
    assert out["enabled"] is False
    assert out["capabilities"] == {"search": "browser"}
    assert out["declared_capabilities"] == {"search": "requests"}
    assert out["config"] == {"search": {"mode": "requests"}}


def test_get_config_has_no_mode(monkeypatch):
    """GET /config 不再返回 mode。"""
    from backend.routers import config as cfg
    monkeypatch.setattr(cfg.config_service, "load_config",
                        lambda: {"download": {"max_workers": 5}})
    out = asyncio.run(cfg.get_config())
    assert "mode" not in out
    assert out["max_workers"] == 5
    assert out["notify"]["on_complete"] is True


def test_save_source_config_writes_user_layer_only(monkeypatch, tmp_path):
    """PUT /config/sources/{name} 只写用户层：顶层 enabled + 逐能力段 deep_merge，不写三层全量。"""
    import yaml
    from backend.routers import config as cfg
    monkeypatch.setattr(cfg.config_service, "CONFIG_DIR", tmp_path)
    _allow_sources(monkeypatch, "demo-requests-default")
    asyncio.run(cfg.save_source_config(
        "demo-requests-default",
        {"enabled": False, "config": {"search": {"timeout": 99}}},
    ))
    path = tmp_path / "sites" / "demo-requests-default.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["enabled"] is False
    assert data["search"]["timeout"] == 99
    # 未提供的出厂字段 / 其它能力段不应被灌入用户层
    assert set(data.keys()) == {"enabled", "search"}


def test_save_source_config_deep_merges_existing(monkeypatch, tmp_path):
    """再次 PUT 时保留用户层既有字段（deep_merge 而非整体覆盖）。"""
    from backend.routers import config as cfg
    monkeypatch.setattr(cfg.config_service, "CONFIG_DIR", tmp_path)
    _allow_sources(monkeypatch, "demo-requests-default")
    asyncio.run(cfg.save_source_config("demo-requests-default", {"config": {"search": {"timeout": 99}}}))
    asyncio.run(cfg.save_source_config("demo-requests-default", {"config": {"search": {"retry_times": 7}}}))
    merged = cfg.config_service.load_yaml(tmp_path / "sites" / "demo-requests-default.yaml")
    assert merged["search"] == {"timeout": 99, "retry_times": 7}


def test_old_sites_routes_gone():
    """旧 /config/sites/{website} 及其处理函数删除，无 shim。"""
    from backend.routers import config as cfg
    assert not hasattr(cfg, "get_site")
    assert not hasattr(cfg, "save_site")
    paths = {r.path for r in cfg.router.routes}
    assert "/api/v2/config/sources/{source_name}" in paths
    assert "/api/v2/config/sites/{website}" not in paths


def test_engine_router_and_schemas_gone():
    """explicit engine API 整体删除：路由模块、schemas、main 注册全部消失。"""
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.routers.engine")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.schemas.engine")
    import backend.schemas as schemas
    assert not hasattr(schemas, "CreateEngineRequest")
    assert not hasattr(schemas, "UpdateEngineRequest")
    import backend.main as main_mod
    paths = set(main_mod.app.openapi()["paths"])
    assert not any(p.startswith("/api/v2/engine") for p in paths)


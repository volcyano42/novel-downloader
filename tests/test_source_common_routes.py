"""PUT/GET 的 common 契约（spec: 2026-10-14-source-common-config-design.md）。"""
import asyncio

import yaml

from backend.routers import config as cfg_router
from backend.services import source_guard


def _setup(tmp_path, monkeypatch, initial: dict | None = None):
    monkeypatch.setattr(cfg_router.config_service, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(source_guard, "list_sources", lambda: ["demo-api-default"])
    # 书源声明的能力：_user_sections 按它求交、converge 按它判定「全部能力段」
    monkeypatch.setattr(cfg_router, "capabilities", lambda n: {c: "api" for c in CAPS})
    (tmp_path / "sites").mkdir(parents=True, exist_ok=True)
    if initial is not None:
        (tmp_path / "sites" / "demo-api-default.yaml").write_text(
            yaml.safe_dump(initial, allow_unicode=True), encoding="utf-8")
    return tmp_path / "sites" / "demo-api-default.yaml"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_put_common_writes_and_clears_capability_keys(tmp_path, monkeypatch):
    """写 common.key 时，各能力段里的 key 被删除（否则旧值优先、改了不生效）。"""
    path = _setup(tmp_path, monkeypatch, {
        "search": {"mode": "api", "key": "old"},
        "novel_info": {"mode": "api", "key": "old"},
    })
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"key": "new"}}))
    data = _load(path)
    assert data["common"]["key"] == "new"
    assert "key" not in data["search"]
    assert "key" not in data["novel_info"]
    assert data["search"]["mode"] == "api"          # 其它键不受影响


def test_put_common_null_deletes_key(tmp_path, monkeypatch):
    """{common: {k: null}} 删除该键。"""
    path = _setup(tmp_path, monkeypatch, {"common": {"timeout": 30, "key": "x"}})
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"key": None}}))
    data = _load(path)
    assert "key" not in data["common"]
    assert data["common"]["timeout"] == 30


def test_get_reports_user_overrides(tmp_path, monkeypatch):
    """GET 返回各能力段在用户层实际出现的键。"""
    _setup(tmp_path, monkeypatch, {"common": {"key": "x"},
                                   "search": {"mode": "api", "delay": [1, 1]}})
    monkeypatch.setattr(cfg_router, "effective_capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router, "capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router.config_service, "merged_source_config",
                        lambda n: {"search": {"mode": "api"}})
    monkeypatch.setattr(cfg_router.config_service, "source_concurrency", lambda n: 1)
    monkeypatch.setattr(cfg_router.config_service, "source_group", lambda n: "")
    monkeypatch.setattr(cfg_router.config_service, "source_alias", lambda n: "")
    out = asyncio.run(cfg_router.get_source_config("demo-api-default"))
    # delay 在 common 里没有该键 → 算覆盖；mode 不属于共享字段，不计入
    assert out["user_overrides"]["search"] == ["delay"]
    assert out["user_overrides"].get("novel_info") in (None, [])


def _patch_caps(monkeypatch):
    """「全部能力段」按**书源声明的能力**判定，所以 converge 相关测试必须提供它。"""
    monkeypatch.setattr(cfg_router, "capabilities",
                        lambda n: {c: "api" for c in
                                   ("search", "novel_info", "chapter_list", "chapter_content")})


def test_converge_moves_identical_keys_to_common(tmp_path, monkeypatch):
    """全部能力段都有且取值相同的键 → 搬到 common 并从各段删除。"""
    path = _setup(tmp_path, monkeypatch, {
        "search": {"timeout": 30}, "novel_info": {"timeout": 30},
        "chapter_list": {"timeout": 30}, "chapter_content": {"timeout": 30, "delay": [9, 9]},
    })
    _patch_caps(monkeypatch)
    out = asyncio.run(cfg_router.converge_source_config("demo-api-default"))
    data = _load(path)
    assert data["common"]["timeout"] == 30
    assert all("timeout" not in data.get(c, {}) for c in
               ("search", "novel_info", "chapter_list", "chapter_content"))
    assert data["chapter_content"]["delay"] == [9, 9]     # 不一致的键原地保留
    assert "timeout" in [c["key"] for c in out["converged"]]
    assert "delay" in [c["key"] for c in out["kept"]]


def test_converge_keeps_partial_coverage_keys(tmp_path, monkeypatch):
    """只出现在部分能力段的键不收敛（否则其余段会从继承出厂变成继承 common）。"""
    path = _setup(tmp_path, monkeypatch, {"search": {"key": "x"}, "novel_info": {"key": "x"}})
    _patch_caps(monkeypatch)
    asyncio.run(cfg_router.converge_source_config("demo-api-default"))
    data = _load(path)
    assert "common" not in data or "key" not in data.get("common", {})
    assert data["search"]["key"] == "x"


# ── review 修复：mode 不属于 common（否则用户层 mode 覆盖会被删，生效 mode 静默回退）──

CAPS = ("search", "novel_info", "chapter_list", "chapter_content")


def test_converge_never_converges_mode(tmp_path, monkeypatch):
    """`mode` 永不被收敛：否则各段 mode 覆盖被删、生效 mode 回落到书源声明。"""
    path = _setup(tmp_path, monkeypatch, {
        c: {"mode": "requests", "timeout": 30} for c in CAPS
    })
    _patch_caps(monkeypatch)
    out = asyncio.run(cfg_router.converge_source_config("demo-api-default"))
    data = _load(path)
    assert "mode" not in [c["key"] for c in out["converged"]]
    assert "mode" not in data.get("common", {})
    assert all(data[c]["mode"] == "requests" for c in CAPS)   # 各段覆盖保留
    assert "timeout" in [c["key"] for c in out["converged"]]  # 其它键照常收敛


def test_put_common_mode_is_ignored(tmp_path, monkeypatch):
    """PUT 传 `common.mode` 不得写入、也不得删除各能力段的 mode 覆盖。"""
    path = _setup(tmp_path, monkeypatch, {"search": {"mode": "requests"}})
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"mode": "browser"}}))
    data = _load(path)
    assert "mode" not in data.get("common", {})
    assert data["search"]["mode"] == "requests"


def test_put_common_deep_merges_nested_values(tmp_path, monkeypatch):
    """common 的嵌套值按 deep_merge 写入（与能力段一致，不整体替换）。"""
    path = _setup(tmp_path, monkeypatch, {"common": {"params": {"a": 1, "b": 2}}})
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"params": {"b": 9}}}))
    data = _load(path)
    assert data["common"]["params"] == {"a": 1, "b": 9}


def test_get_exposes_common_and_override_semantics(tmp_path, monkeypatch):
    """GET 返回用户层 common 原始值；user_overrides 只标「与 common 值不同」的键。"""
    _setup(tmp_path, monkeypatch, {
        "common": {"timeout": 30},
        "search": {"mode": "api", "timeout": 30},       # 与 common 同值 → 不算覆盖
        "novel_info": {"mode": "api", "timeout": 45},   # 与 common 不同 → 算覆盖
    })
    monkeypatch.setattr(cfg_router, "effective_capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router.config_service, "merged_source_config",
                        lambda n: {"search": {"mode": "api"}})
    monkeypatch.setattr(cfg_router.config_service, "source_concurrency", lambda n: 1)
    monkeypatch.setattr(cfg_router.config_service, "source_group", lambda n: "")
    monkeypatch.setattr(cfg_router.config_service, "source_alias", lambda n: "")
    out = asyncio.run(cfg_router.get_source_config("demo-api-default"))
    assert out["common"] == {"timeout": 30}
    assert "timeout" not in out["user_overrides"]["search"]
    assert "timeout" in out["user_overrides"]["novel_info"]

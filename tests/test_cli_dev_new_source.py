"""`dev new-source` 扁平脚手架测试（`new-variant` 已删除）。

直接调用 `cli.main._scaffold_source`（不跑子进程），monkeypatch 注入 sources 根
（`cli.main._SOURCES_ROOT`）与配置目录（`cli.config.CONFIG_DIR` /
`shared.config.CONFIG_DIR`），全部为真实文件操作。
"""

import json

import pytest

import cli.config
import cli.main

_FUNCS = ("search", "novel_info", "chapter_list", "chapter_content")


def _setup(monkeypatch, tmp_path):
    """构造可注入环境：sources 根 + 配置目录，返回 (root, cfg_dir)。"""
    root = tmp_path / "sources"
    root.mkdir()
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    monkeypatch.setattr(cli.main, "_SOURCES_ROOT", root)
    monkeypatch.setattr(cli.config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("shared.config.CONFIG_DIR", cfg_dir)
    return root, cfg_dir


def test_new_source_builds_flat_layout(monkeypatch, tmp_path):
    root, cfg_dir = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-requests-default", ["requests"])
    d = root / "demo_requests_default"  # 目录名 = source_name 的下划线形式
    assert (d / "__init__.py").is_file()
    assert (d / "source.json").is_file()
    for fn in _FUNCS:
        assert (d / f"{fn}.py").is_file()
    assert (cfg_dir / "sites" / "demo-requests-default.yaml").is_file()  # 默认建用户配置


def test_new_source_manifest_valid(monkeypatch, tmp_path):
    """生成的 `source.json` 通过 manifest 校验；`source_name` 用连字符。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-requests-default", ["requests"])
    from novelbase.sources.manifest import load_manifest

    d = root / "demo_requests_default"
    manifest = load_manifest(d)  # 不抛 ManifestError
    assert manifest["source_name"] == "demo-requests-default"
    assert set(manifest["default_config"]) == set(_FUNCS)
    for cap in _FUNCS:
        assert manifest["default_config"][cap]["mode"] == "requests"


def test_new_source_common_includes_factory_defaults(monkeypatch, tmp_path):
    """脚手架 common 必须与真实书源一致：除 mode 外带上该 mode 的出厂默认字段。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-requests-default", ["requests"])
    common = json.loads(
        (root / "demo_requests_default" / "source.json").read_text(encoding="utf-8")
    )["common"]
    assert common["mode"] == "requests"
    for key in ("timeout", "retry_times", "backoff_factor", "delay",
                "headers", "cookies", "proxies"):
        assert key in common, key
    # 空值须与真实书源字面同构（None → {}/""）
    assert common["cookies"] == {}
    assert common["proxies"] == {}
    assert isinstance(common["headers"], dict) and common["headers"]
    # delay 须与真实书源逐字同构（整数列表 [0, 0]，而非 [0.0, 0.0]）
    assert common["delay"] == [0, 0], common["delay"]
    # 类型也须为 int（JSON 字面 0 而非 0.0）；否则 [0.0, 0.0] == [0, 0] 也会通过
    assert all(type(x) is int for x in common["delay"]), common["delay"]


def test_new_source_api_common_includes_key_and_params(monkeypatch, tmp_path):
    """api 的出厂默认不在 ENGINE_DEFAULTS（空 dict），须由 APIOptions 派生。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-api-rain", ["api"])
    common = json.loads(
        (root / "demo_api_rain" / "source.json").read_text(encoding="utf-8")
    )["common"]
    assert common["mode"] == "api"
    for key in ("timeout", "retry_times", "backoff_factor", "delay", "key", "params"):
        assert key in common, key
    assert common["key"] == ""
    assert common["params"] == {}
    assert common["delay"] == [0, 0], common["delay"]
    # 类型也须为 int（JSON 字面 0 而非 0.0）；否则 [0.0, 0.0] == [0, 0] 也会通过
    assert all(type(x) is int for x in common["delay"]), common["delay"]


def test_new_source_browser_common_blank_values_match_real_sources(monkeypatch, tmp_path):
    """dataclass 的 None 默认须规范化为真实书源用的 ""/{}/[]（用户裁决：spec §4.3(b) 优先）。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-browser-default", ["browser"])
    common = json.loads(
        (root / "demo_browser_default" / "source.json").read_text(encoding="utf-8")
    )["common"]
    assert common["user_data_dir"] == ""
    assert common["viewport"] == {}
    assert common["extra_args"] == []
    assert common["browser_type"] == "chromium"
    assert common["delay"] == [0, 0], common["delay"]
    # 类型也须为 int（JSON 字面 0 而非 0.0）；否则 [0.0, 0.0] == [0, 0] 也会通过
    assert all(type(x) is int for x in common["delay"]), common["delay"]


def test_new_source_no_config_skips_user_config(monkeypatch, tmp_path):
    root, cfg_dir = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-requests-default", ["requests"], write_config=False)
    assert not (cfg_dir / "sites" / "demo-requests-default.yaml").exists()


def test_new_source_async_template(monkeypatch, tmp_path):
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-requests-default", ["requests"])
    for fn in _FUNCS:
        content = (root / "demo_requests_default" / f"{fn}.py").read_text(encoding="utf-8")
        assert f"async def {fn}" in content
        assert "FeatureNotSupportedError" in content


def test_new_variant_and_platform_helpers_removed():
    for gone in ("_scaffold_variant", "_resolve_variant",
                 "_resolve_platform", "_source_name"):
        assert not hasattr(cli.main, gone)


# ── 子命令参数表：统一 `--source`，无 platform/mode/variant ──


def test_cli_search_source_optional(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cli", "search", "关键词"])
    args = cli.main._parse_args()
    assert args.source == ""          # 可空 = 并发全部启用书源
    assert args.page == 1
    assert not hasattr(args, "platform")
    assert not hasattr(args, "mode")
    assert not hasattr(args, "variant")


def test_cli_download_source_required(monkeypatch):
    monkeypatch.setattr("sys.argv",
                        ["cli", "download", "--source", "a-b-default",
                         "--url", "https://x/"])
    args = cli.main._parse_args()
    assert args.source == "a-b-default"
    assert not hasattr(args, "mode")
    assert not hasattr(args, "variant")

    monkeypatch.setattr("sys.argv", ["cli", "download", "--url", "https://x/"])
    with pytest.raises(SystemExit):      # --source 必填
        cli.main._parse_args()


def test_cli_info_source_required(monkeypatch):
    monkeypatch.setattr("sys.argv",
                        ["cli", "info", "--source", "a-b-default", "--url", "https://x/"])
    args = cli.main._parse_args()
    assert args.source == "a-b-default"


def test_cli_update_no_mode_variant(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cli", "update"])
    args = cli.main._parse_args()
    assert not hasattr(args, "platform")
    assert not hasattr(args, "mode")
    assert not hasattr(args, "variant")


def test_cli_dev_has_no_new_variant(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cli", "dev", "new-source", "--name", "x"])
    args = cli.main._parse_args()
    assert args.no_config is False
    monkeypatch.setattr("sys.argv", ["cli", "dev", "new-variant", "--source", "x",
                                     "--mode", "api", "--variant", "y"])
    with pytest.raises(SystemExit):      # new-variant 已删除
        cli.main._parse_args()

"""cli.config 按书源构建 Options 的回归测试。

variant 概念已随「书源扁平化」取消：Options 由
`cli.config.build_options(source_name, mode)` 按书源三层合并配置构建，
不再有 `mode_variants` / `resolve_variant` 辅助，也不再按 (cfg, site_cfg, variant) 组装。
"""
import cli.config


def test_build_options_by_source(monkeypatch):
    import cli.config
    monkeypatch.setattr("shared.config.merged_source_config",
                        lambda n: {"search": {"mode": "requests", "timeout": 42}})
    opts = cli.config.build_options("92xs-requests-default", "requests")
    assert opts.mode == "requests"


def test_variant_helpers_removed():
    import cli.config
    assert not hasattr(cli.config, "resolve_variant")
    assert not hasattr(cli.config, "mode_variants")

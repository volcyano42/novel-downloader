"""CLI 书源列表显示有效 mode（用户层 {cap}.mode 覆盖声明）。"""
import argparse

import shared.config as config_service

KNOWN = "92xs-requests-default"


def test_cmd_source_list_shows_effective_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    (sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    from cli import main as cli_main
    cli_main.cmd_source(argparse.Namespace(source_command="list", json=False))

    out = capsys.readouterr().out
    # 逐源取行：仓库内其它源本就声明 search:requests，断言不可作用于整体输出。
    line = next(ln for ln in out.splitlines() if ln.lstrip().startswith(f"- {KNOWN}"))
    assert "search:browser" in line          # 有效 mode
    assert "search:requests" not in line     # 该源声明值不再直出

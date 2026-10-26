"""CLI 书源列表显示有效 mode（用户层 {cap}.mode 覆盖声明），并钉住分发透传。"""
import argparse
import asyncio
import json
import types

import cli.core as cli_core
import shared.config as config_service

KNOWN = "92xs-requests-default"


def _override_search_browser(tmp_path):
    """在用户层把 KNOWN 源的 search.mode 覆盖为 browser。"""
    sources = tmp_path / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / f"{KNOWN}.yaml").write_text("mode: browser\n", encoding="utf-8")


def test_cmd_source_list_shows_effective_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    _override_search_browser(tmp_path)

    from cli import main as cli_main
    cli_main.cmd_source(argparse.Namespace(source_command="list", json=False))

    out = capsys.readouterr().out
    # 逐源取行：仓库内其它源本就声明 search:requests，断言不可作用于整体输出。
    # 输出行形如「- <别名>  [<分组>]  (<source_name>)  capabilities: ...」——按括号里的
    # source_name 定位，不依赖行首（别名可被用户覆盖、分组可为空）。
    line = next(ln for ln in out.splitlines() if f"({KNOWN})" in ln)
    assert "search:browser" in line          # 有效 mode（顶层 mode 对所有能力生效）
    assert "search:requests" not in line     # 该源声明值不再直出


def test_cmd_source_json_shows_effective_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    _override_search_browser(tmp_path)

    from cli import main as cli_main
    cli_main.cmd_source(argparse.Namespace(source_command="list", json=True))

    payload = json.loads(capsys.readouterr().out)
    caps = payload[KNOWN]["capabilities"]

    from novelbase.source import capabilities
    assert capabilities(KNOWN)["search"] == "requests"   # 声明值仍为 requests
    assert caps["search"] == "browser"                   # JSON 分支输出覆盖后的有效值


def test_download_inner_passes_engine_per_capability(monkeypatch):
    """下载路径必须按能力取引擎：novel_info / chapter_list 各传对应实例。

    （chapter_content 的映射由 test_cli_engine_modes.py 的 getter 用例覆盖：
    本用例让章节列表为空以终止流程，避免触发存储与导出。）
    """
    monkeypatch.setattr(cli_core, "effective_capabilities",
                        lambda n: {"novel_info": "requests", "chapter_list": "requests",
                                   "chapter_content": "browser"})
    monkeypatch.setattr(cli_core, "build_options",
                        lambda name, mode: types.SimpleNamespace(mode=mode))
    monkeypatch.setattr(cli_core, "create_engine", lambda options: f"engine:{options.mode}")
    captured = {}

    async def fake_resolve_meta(url, source_name, engine, skip_delay=False, **kw):
        captured["meta"] = (engine, skip_delay)
        return types.SimpleNamespace(url=url, title="T", author="A")

    async def fake_resolve_chapter_list(url, source_name, engine, skip_delay=False, **kw):
        captured["cl"] = (engine, skip_delay)
        return []

    monkeypatch.setattr(cli_core, "resolve_meta", fake_resolve_meta)
    monkeypatch.setattr(cli_core, "resolve_chapter_list", fake_resolve_chapter_list)

    asyncio.run(cli_core._do_download_inner(KNOWN, "https://x/page/1", "default", {}))

    assert captured["meta"] == ("engine:requests", False)
    assert captured["cl"] == ("engine:requests", False)


def test_cmd_source_list_shows_group_and_alias(monkeypatch, capsys):
    """`sources list` 显示别名与分组；`--json` 用 source_name / source_alias / source_group 键。"""
    from cli import main as cli_main

    monkeypatch.setattr("novelbase.source.list_sources", lambda: ["demo-requests-default"])
    monkeypatch.setattr(cli_main, "effective_capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("shared.config.source_alias", lambda n: "演示源")
    monkeypatch.setattr("shared.config.source_group", lambda n: "演示组")

    class Args:
        source_command = "list"
        json = True

    cli_main.cmd_source(Args())
    out = capsys.readouterr().out
    assert '"source_name": "demo-requests-default"' in out
    assert '"source_alias": "演示源"' in out
    assert '"source_group": "演示组"' in out
    assert '"enabled"' not in out


def test_cmd_source_list_json_alias_empty_when_unset(monkeypatch, capsys):
    """未设别名时 `--json` 的 source_alias 为 ""（与 source_group 一致，不回落 source_name）。"""
    from cli import main as cli_main

    monkeypatch.setattr("novelbase.source.list_sources", lambda: ["demo-requests-default"])
    monkeypatch.setattr(cli_main, "effective_capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("shared.config.source_alias", lambda n: "")
    monkeypatch.setattr("shared.config.source_group", lambda n: "")

    class Args:
        source_command = "list"
        json = True

    cli_main.cmd_source(Args())
    out = capsys.readouterr().out
    assert '"source_alias": ""' in out
    assert '"source_alias": "demo-requests-default"' not in out


def test_cmd_config_only_touches_missing(monkeypatch, capsys):
    """`config init` 只对缺失项调用 init_* —— 不整体调用（避免覆盖用户配置）。

    `init_config.init_*()` 内部是无条件 copy2，因此命令必须先取 check_config 的
    缺失清单再逐项调用；本用例用记录器钉住这一行为（不碰文件系统）。
    """
    import init_config
    from cli import main as cli_main

    calls: list[str] = []

    class Args:
        config_command = "init"
        all = False
        main = False
        sources = None
        formats = None
        user_db = False

    monkeypatch.setattr(init_config, "check_config",
                        lambda: {"missing": ["config.yaml", "sources/demo-r-default.yaml"],
                                 "all_missing": False})
    monkeypatch.setattr(init_config, "init_main_config",
                        lambda: (calls.append("main"), ["/tmp/config.yaml"])[1])
    monkeypatch.setattr(init_config, "init_source_config",
                        lambda name: (calls.append(f"sources:{name}"), [f"/tmp/sources/{name}.yaml"])[1])
    monkeypatch.setattr(init_config, "init_user_db",
                        lambda: (calls.append("user-db"), [])[1])

    def _forbidden(*_a, **_k):  # 若命令走了 init_export_config 就说明过滤失效
        raise AssertionError("不该调用 init_export_config（formats 不在缺失清单里）")

    monkeypatch.setattr(init_config, "init_export_config", _forbidden)

    cli_main.cmd_config(Args())

    assert calls == ["main", "sources:demo-r-default", "user-db"]
    out = capsys.readouterr().out
    assert "已初始化 2 个配置项" in out

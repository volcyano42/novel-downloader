"""dev new-variant / new-source async 模板测试。

直接调用 cli.main._scaffold_variant / _scaffold_source（不跑子进程），
monkeypatch 注入 sources 根（cli.main._SOURCES_ROOT）与 sites 配置目录
（cli.config.CONFIG_DIR），全部为真实文件操作。
"""
import pytest

import cli.config
import cli.main


def _setup(monkeypatch, tmp_path, source="demo", site_cfg=None):
    """构造可注入环境：sources 根 + 站点配置文件，返回 (root, cfg_dir)。"""
    root = tmp_path / "sources"
    root.mkdir()
    (root / source).mkdir()

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    monkeypatch.setattr(cli.main, "_SOURCES_ROOT", root)
    monkeypatch.setattr(cli.config, "CONFIG_DIR", cfg_dir)

    if site_cfg is not None:
        cli.config.save_site_config(source, site_cfg)
    return root, cfg_dir


_SITE = {
    "api": {
        "oiapi": {"key": "", "timeout": 30},
        "rain": {"key": "", "timeout": 99},
    },
    "requests": {"default": {"timeout": 30}},
}


def test_new_variant_success(monkeypatch, tmp_path):
    root, cfg_dir = _setup(monkeypatch, tmp_path, site_cfg=_SITE)
    cli.main._scaffold_variant("demo", "api", "oiapi2")

    # 代码脚手架
    vdir = root / "demo" / "api" / "oiapi2"
    assert vdir.is_dir()
    assert (vdir / "__init__.py").exists()
    for fn in ("search", "novel_info", "chapter_list", "chapter_content"):
        content = (vdir / f"{fn}.py").read_text(encoding="utf-8")
        assert f"async def {fn}" in content
        assert "FeatureNotSupportedError" in content

    # 配置块：模板（第一个 dict 值）被复制，模板本身未改动
    site = cli.config.load_site_config("demo")
    assert "oiapi2" in site["api"]
    assert site["api"]["oiapi2"] == site["api"]["oiapi"]
    assert set(site["api"]) == {"oiapi", "rain", "oiapi2"}


@pytest.mark.parametrize("source,with_cfg", [
    ("nope", True),    # 书源代码目录不存在（配置存在）
    ("demo", False),   # 站点配置文件不存在（代码目录存在）
])
def test_new_variant_source_missing(monkeypatch, tmp_path, capsys,
                                    source, with_cfg):
    _setup(monkeypatch, tmp_path, source="demo",
           site_cfg=_SITE if with_cfg else None)
    with pytest.raises(SystemExit) as exc:
        cli.main._scaffold_variant(source, "api", "oiapi2")
    assert exc.value.code == 1
    assert f"书源 {source} 不存在" in capsys.readouterr().err


def test_new_variant_mode_missing(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, site_cfg=_SITE)
    with pytest.raises(SystemExit) as exc:
        cli.main._scaffold_variant("demo", "browser", "oiapi2")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "browser" in err            # 报错的 mode 被指出
    assert "api" in err and "requests" in err  # 列出可用 mode


def test_new_variant_variant_exists(monkeypatch, tmp_path, capsys):
    root, _ = _setup(monkeypatch, tmp_path, site_cfg=_SITE)

    # 配置中已存在该 variant
    with pytest.raises(SystemExit) as exc:
        cli.main._scaffold_variant("demo", "api", "rain")
    assert exc.value.code == 1
    assert "已存在" in capsys.readouterr().err

    # 代码目录已存在（配置无该 variant），且绝不覆盖已有文件
    vdir = root / "demo" / "requests" / "foo"
    vdir.mkdir(parents=True)
    (vdir / "marker.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cli.main._scaffold_variant("demo", "requests", "foo")
    assert exc.value.code == 1
    assert "已存在" in capsys.readouterr().err
    assert (vdir / "marker.txt").read_text(encoding="utf-8") == "keep"


def test_new_variant_no_template(monkeypatch, tmp_path, capsys):
    site = dict(_SITE)
    site["browser"] = {}  # mode key 存在但无 variant 可作模板
    _setup(monkeypatch, tmp_path, site_cfg=site)
    with pytest.raises(SystemExit) as exc:
        cli.main._scaffold_variant("demo", "browser", "oiapi2")
    assert exc.value.code == 1
    assert "没有可复制的 variant" in capsys.readouterr().err


@pytest.mark.parametrize("variant", ["../evil", "a/b", "a:b", "a b", "bad*name"])
def test_new_variant_invalid_name(monkeypatch, tmp_path, capsys, variant):
    """非法 variant 名：退出码 1 且不产生任何文件（代码/配置）。"""
    root, _ = _setup(monkeypatch, tmp_path, site_cfg=_SITE)
    with pytest.raises(SystemExit) as exc:
        cli.main._scaffold_variant("demo", "api", variant)
    assert exc.value.code == 1
    assert "含非法字符" in capsys.readouterr().err
    # 不产生文件：代码目录下无新目录，站点配置未新增 variant
    assert list((root / "demo").iterdir()) == []
    site = cli.config.load_site_config("demo")
    assert set(site["api"]) == {"oiapi", "rain"}


def test_new_source_template_async(monkeypatch, tmp_path):
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo", ["requests"])
    for fn in ("search", "novel_info", "chapter_list", "chapter_content"):
        content = (root / "demo" / "requests" / f"{fn}.py").read_text(
            encoding="utf-8")
        assert f"async def {fn}" in content

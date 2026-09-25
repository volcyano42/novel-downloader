"""CLI 引擎解析：按 mode 懒建并缓存，且 options_hook 对每个 mode 都生效。

背景：`cmd_download`/`cmd_info` 曾传 `lambda m: engine`（单引擎、忽略 mode），
跨能力 mode 不同的书源会错用首个 mode 的引擎。
"""
import cli.core


class _FakeOptions:
    def __init__(self, mode):
        self.mode = mode


def test_make_engines_builds_per_mode_and_applies_hook(monkeypatch):
    built: list[str] = []
    hooked: list[str] = []

    monkeypatch.setattr(cli.core, "build_options", lambda name, mode: _FakeOptions(mode))

    def fake_create(options):
        built.append(options.mode)
        return {"engine_for": options.mode}

    monkeypatch.setattr(cli.core, "create_engine", fake_create)

    engines = cli.core._make_engines("x-requests-default", options_hook=lambda o: hooked.append(o.mode))

    assert engines("requests") is engines("requests")   # 同 mode 复用缓存
    engines("browser")

    assert built == ["requests", "browser"]
    assert hooked == ["requests", "browser"]
    assert set(engines.cache) == {"requests", "browser"}


def test_get_engine_defaults_to_first_capability_mode(monkeypatch):
    monkeypatch.setattr(cli.core, "capabilities", lambda name: {"search": "browser", "chapter_content": "requests"})
    seen: list[str] = []

    class _Opt(_FakeOptions):
        pass

    monkeypatch.setattr(cli.core, "build_options", lambda name, mode: _Opt(mode))
    monkeypatch.setattr(cli.core, "create_engine", lambda options: seen.append(options.mode) or object())

    cli.core._get_engine("x-browser-default", None)
    assert seen == ["browser"]

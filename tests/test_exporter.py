"""导出器动态发现测试 — 内置格式 + NLD_PRIVATE_EXPORTERS 外部目录。"""
import importlib

import novelbase.exporter as exporter_mod


def _reload_exporter():
    """清空缓存并重新加载模块，确保每次测试拿到最新扫描结果。"""
    exporter_mod._cache_exporter = None
    exporter_mod._cache_export_opts = None
    return importlib.reload(exporter_mod)


def test_builtin_exporters_discovered():
    """内置三格式 txt/epub/img 自动发现。"""
    _reload_exporter()
    exporters = exporter_mod.register_exporter()
    options = exporter_mod.register_export_options()
    assert set(exporters.keys()) == {"txt", "epub", "img"}
    assert set(options.keys()) == {"txt", "epub", "img"}


def test_list_exporter_formats_and_options():
    """list_exporter_formats 返回格式列表。"""
    _reload_exporter()
    assert exporter_mod.list_exporter_formats() == ["epub", "img", "txt"]


def test_external_exporter_discovered(tmp_path, monkeypatch):
    """NLD_PRIVATE_EXPORTERS 指向的目录里的格式被自动发现。"""
    # 写一个自定义导出器：XLSX 格式
    (tmp_path / "xlsx.py").write_text(
        "from dataclasses import dataclass\n"
        "from novelbase.core.options import ExportOptions\n"
        "@dataclass\n"
        "class XLSXExportOptions(ExportOptions):\n"
        "    format: str = 'xlsx'\n"
        "def export(chapters, novel, options=None, **kwargs):\n"
        "    return 'xlsx-exported'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NLD_PRIVATE_EXPORTERS", str(tmp_path))
    _reload_exporter()

    exporters = exporter_mod.register_exporter()
    assert "xlsx" in exporters
    assert exporters["xlsx"](None, None) == "xlsx-exported"


def test_external_overrides_builtin(tmp_path, monkeypatch):
    """外部与内置同格式时，外部直接替换内置。"""
    (tmp_path / "txt.py").write_text(
        "from dataclasses import dataclass\n"
        "from novelbase.core.options import ExportOptions\n"
        "@dataclass\n"
        "class TXTExportOptions(ExportOptions):\n"
        "    format: str = 'txt'\n"
        "def export(chapters, novel, options=None, **kwargs):\n"
        "    return 'external-txt'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NLD_PRIVATE_EXPORTERS", str(tmp_path))
    _reload_exporter()

    exporters = exporter_mod.register_exporter()
    # 外部 txt 替换了内置 txt
    assert exporters["txt"](None, None) == "external-txt"
    # 其他内置格式不受影响
    assert "epub" in exporters
    assert "img" in exporters


def test_no_env_var_no_external(tmp_path, monkeypatch):
    """未设置环境变量时，外部目录不参与扫描（零退化）。"""
    monkeypatch.delenv("NLD_PRIVATE_EXPORTERS", raising=False)
    _reload_exporter()
    exporters = exporter_mod.register_exporter()
    assert set(exporters.keys()) == {"txt", "epub", "img"}


def test_bad_signature_exporter_skipped(tmp_path, monkeypatch):
    """export 函数签名缺 chapters/novel 的外部导出器被跳过，不炸。"""
    (tmp_path / "bad.py").write_text(
        "from dataclasses import dataclass\n"
        "from novelbase.core.options import ExportOptions\n"
        "@dataclass\n"
        "class BADExportOptions(ExportOptions):\n"
        "    format: str = 'bad'\n"
        "def export(options=None):\n"  # 缺 chapters/novel
        "    return 'bad-exported'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NLD_PRIVATE_EXPORTERS", str(tmp_path))
    _reload_exporter()

    exporters = exporter_mod.register_exporter()
    # 签名错误的导出器被跳过
    assert "bad" not in exporters
    # 内置格式不受影响
    assert set(exporters.keys()) == {"txt", "epub", "img"}


# tests/test_source_layout.py
from pathlib import Path

import pytest

from novelbase.sources.contracts import CAPABILITY_META
from novelbase.sources.manifest import check_capability_files, load_manifest

SOURCES = Path(__file__).resolve().parents[1] / "novelbase" / "sources"

# 每个新书源目录的 mode 归属 = 其原 {platform}/{mode}/{variant} 路径里的 mode。
# 这是「能力矩阵未被改坏」的真断言：4 个能力的 mode 必须与迁移前一致。
EXPECTED_MODE = {
    "fanqie_api_oiapi": "api",
    "fanqie_api_rain": "api",
    "fanqie_browser_default": "browser",
    "fanqie_requests_default": "requests",
    "qidian_browser_default": "browser",
    "qidian_requests_default": "requests",
    "qimao_api_rain": "api",
    "qimao_browser_default": "browser",
    "qimao_requests_default": "requests",
    "92xs_requests_default": "requests",
}

# 目录名 → source_name（Global Constraints 表）
DIR_TO_SOURCE_NAME = {
    "fanqie_api_oiapi": "fanqie-api-oiapi",
    "fanqie_api_rain": "fanqie-api-rain",
    "fanqie_browser_default": "fanqie-browser-default",
    "fanqie_requests_default": "fanqie-requests-default",
    "qidian_browser_default": "qidian-browser-default",
    "qidian_requests_default": "qidian-requests-default",
    "qimao_api_rain": "qimao-api-rain",
    "qimao_browser_default": "qimao-browser-default",
    "qimao_requests_default": "qimao-requests-default",
    "92xs_requests_default": "92xs-requests-default",
}


@pytest.mark.parametrize("dirname", sorted(EXPECTED_MODE))
def test_source_dir_has_identity_and_capabilities(dirname):
    d = SOURCES / dirname
    assert d.is_dir(), f"缺少书源目录 {dirname}"
    manifest = load_manifest(d)
    assert manifest["source_name"] == DIR_TO_SOURCE_NAME[dirname]
    check_capability_files(d, manifest)          # 能力段 ⇔ .py 文件
    assert (d / "__init__.py").is_file()


@pytest.mark.parametrize("dirname", sorted(EXPECTED_MODE))
def test_source_dir_mode_matches_legacy(dirname):
    """每个新书源的 4 个能力 mode 与迁移前目录层级一致（防能力矩阵改坏）。"""
    manifest = load_manifest(SOURCES / dirname)
    assert set(manifest["default_config"]) == set(CAPABILITY_META), dirname
    for cap, section in manifest["default_config"].items():
        assert section["mode"] == EXPECTED_MODE[dirname], f"{dirname}.{cap}"


def test_no_legacy_platform_dirs():
    """旧的 {platform}/{mode}/{variant} 四层目录不再存在。"""
    for legacy in ("fanqie", "qidian", "qimao", "92xs"):
        assert not (SOURCES / legacy).exists(), f"旧目录未删除: {legacy}"

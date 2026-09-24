# -*- coding: utf-8 -*-
"""CI 导入检查：运行在 github workflow 中"""
import sys

sys.path.insert(0, ".")

from novelbase import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    export as do_export,
    Options,
    create_engine,
    list_sources,
    get_exporters,
    get_exporter_options,
    search,
    LocalStorage,
    AntiCrawlError,
    Novel,
    Chapter,
    Chapters,
    NovelDownloaderError,
)
import novelbase

print("✓ novelbase v" + novelbase.__version__ + " 导入成功")

# 书源扁平化后，source_name 与目录名解耦；此处断言 10 个内置书源都已被发现。
_EXPECTED_SOURCES = {
    "92xs-requests-default",
    "fanqie-api-oiapi",
    "fanqie-api-rain",
    "fanqie-browser-default",
    "fanqie-requests-default",
    "qidian-browser-default",
    "qidian-requests-default",
    "qimao-api-rain",
    "qimao-browser-default",
    "qimao-requests-default",
}
_missing = _EXPECTED_SOURCES - set(list_sources())
assert not _missing, f"缺少书源: {sorted(_missing)}"

print("  注册的 Source: " + str(list_sources()))
print("  注册的导出器: " + str(list(get_exporters().keys())))

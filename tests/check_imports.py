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
print("  注册的 Source: " + str(list_sources()))
print("  注册的导出器: " + str(list(get_exporters().keys())))

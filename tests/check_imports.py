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

# 书源扁平化后，source_name 与目录名解耦。此处断言「内置根下每个书源目录都被发现」——
# 不硬编码源名，公开子集（public 只保留 fanqie 两个源）同样成立。
from pathlib import Path

import novelbase.sources as _sources_pkg

from novelbase.sources.manifest import scan_source_names

_builtin_root = Path(_sources_pkg.__file__).resolve().parent / "builtin"
_declared = set(scan_source_names([_builtin_root]))
_discovered = set(list_sources())
_missing = _declared - _discovered
assert _discovered, "未发现任何书源"
assert not _missing, f"内置书源目录未被发现: {sorted(_missing)}"

print("  注册的 Source: " + str(list_sources()))
print("  注册的导出器: " + str(list(get_exporters().keys())))

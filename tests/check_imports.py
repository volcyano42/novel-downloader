"""CI 导入检查：运行在 github workflow 中"""
import sys

sys.path.insert(0, ".")

from nldlder import (
    NovelDownloader,
    Options,
    create_engine,
    get_fetchers,
    get_exporters,
    get_exporter_options,
    search,
    login,
    split_into_groups,
    LocalStorage,
    AntiCrawlError,
    Novel,
    Chapter,
    Chapters,
    NovelDownloaderError,
    configure_logging,
    LogOptions,
)
import nldlder

print("✓ nldlder v" + nldlder.__version__ + " 导入成功")
print("  注册的 Fetcher: " + str(list(get_fetchers().keys())))
print("  注册的导出器: " + str(list(get_exporters().keys())))

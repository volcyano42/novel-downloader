from typing import Iterable, Sequence, TypeVar

from .engine import BrowserEngine, APIEngine, RequestsEngine
from .exceptions import FetcherNotFoundError
from .options import Options, ExportOptions
from .storage import LocalStorage
from ..exporters.base import BASEExporter
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, Chapters, SearchResult
from ..fetchers.base import BaseFetcher
from ..utils.logger import get_logger

_T = TypeVar('_T')

_log = get_logger("nldlder.core.downloader")

def get_fetcher_for_url(url: str):
    """根据 URL 查找匹配的 Fetcher 类。"""
    from ..utils.registry import register_fetcher
    from yarl import URL
    parsed = URL(url)
    for fetcher_cls in register_fetcher().values():
        if parsed.host in fetcher_cls.host:
            return fetcher_cls
    return None


def get_fetcher_for_id(novel_id: str):
    """根据裸 novel_id 查找匹配的 Fetcher 类。

    遍历所有已注册 Fetcher 的 ``id_pattern``，命中则返回该类。
    ``id_pattern`` 须包含一个捕获组，调用方通过 ``.group(1)`` 提取纯净 ID。
    """
    from ..utils.registry import register_fetcher
    for fetcher_cls in register_fetcher().values():
        if fetcher_cls.id_pattern and fetcher_cls.id_pattern.match(novel_id):
            return fetcher_cls
    return None


def get_fetchers() -> dict[str, type[BaseFetcher]]:
    """返回所有已注册的 Fetcher 类（{platform: FetcherCls}）。"""
    from ..utils.registry import register_fetcher
    return register_fetcher()


def get_exporters() -> dict[str, type[BASEExporter]]:
    """返回所有已注册的 Exporter 类（{format: ExporterCls}）。"""
    from ..utils.registry import register_exporter
    return register_exporter()


def get_exporter_options() -> dict[str, type[ExportOptions]]:
    from ..utils.registry import register_export_options
    return register_export_options()


def split_into_groups(target: Sequence[_T], group: int) -> tuple[Sequence[_T], ...]:
    """将章节列表按批次大小分组。"""
    return tuple(target[i:i + group] for i in range(0, len(target), group))


def search(platform: str,
           query: str,
           engine,
           page: int = 1,
           **kwargs) -> tuple[SearchResult, ...]:
    """搜索小说。

    Args:
        platform: 平台标识（如 ``"fanqie"``）。
        query:    搜索关键词。
        engine:   下载引擎实例。
        page:     页码，从 1 开始。
    """
    fetcher_cls = get_fetchers().get(platform)
    if fetcher_cls is None:
        raise FetcherNotFoundError(f"fetcher not found: {platform}")
    fetcher = fetcher_cls()
    return fetcher.fetch_search_result(search_ref=query, engine=engine, page=page, **kwargs)


def login(platform: str, engine: BrowserEngine) -> AuthCredential:
    """登录指定平台。

    Args:
        platform: 平台标识。
        engine:   下载引擎实例。
    """
    fetcher_cls = get_fetchers().get(platform)
    if fetcher_cls is None:
        raise FetcherNotFoundError(f"fetcher not found: {platform}")
    fetcher = fetcher_cls()
    return fetcher.login(engine=engine)

class NovelDownloader:
    """小说下载编排器。

    不持有 Novel 或 Fetcher 状态，每次调用独立解析。
    """

    def __init__(self,
                 engine,
                 options: Options | None = None):
        """
        Args:
            engine:  下载引擎（由调用者创建和管理，可多实例共享）。
            options: 下载配置（影响 batch_size 等）。
        """
        self._engine = engine
        self._options = options or Options()
        self._storage_instance: LocalStorage | None = None

    def fetch_meta(self, url: str, **kwargs) -> Novel:
        """获取小说元数据。

        Args:
            url: 小说页面 URL。

        Returns:
            包含书名、作者、简介、封面等信息的 Novel 对象。
        """
        fetcher = self._resolve_fetcher(url)
        return fetcher.fetch_novel_info(novel_ref=url, engine=self._engine, **kwargs)

    def fetch_chapter_list(self, url: str, **kwargs) -> Chapters:
        """获取章节列表。

        Args:
            url: 小说页面 URL。

        Returns:
            按 order 排序的章节列表。
        """
        fetcher = self._resolve_fetcher(url)
        return fetcher.fetch_chapter_list(novel_ref=url, engine=self._engine, **kwargs)

    def resolve_chapters(self,
                        chapters: Sequence[Chapter] | Chapter,
                        fetcher=None, **kwargs) -> Chapters:
        """下载一批章节。

        Args:
            chapters: 要下载的章节列表。
            fetcher:   可选抓取器实例。为 None 时自动从首个章节 URL 解析。

        Returns:
            已下载完成的章节（Chapters 对象）。
        """
        if not chapters:
            return Chapters()
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        if fetcher is None:
            fetcher = self._resolve_fetcher(chapters[0].index_url)
        return fetcher.fetch_chapter_content(chapter_ref=chapters, engine=self._engine, **kwargs)

    def export(self, novel: Novel, format: Iterable[str] | None = None, **kwargs):

        from ..utils.registry import register_exporter, register_export_options

        exporters = register_exporter()
        export_opts_map = register_export_options()

        # 确定要导出的格式
        if format is not None:
            candidates = list(format)
        else:
            candidates = list(self._options.exports.keys())

        for fmt in candidates:
            # 跳过没有对应导出器的格式
            exporter_cls = exporters.get(fmt)
            if exporter_cls is None:
                continue
            # 跳过未启用或没有选项类的格式
            opt = self._options.exports.get(fmt)
            if opt is None or not opt.enabled:
                continue
            opt_cls = export_opts_map.get(fmt)
            if opt_cls is None:
                continue
            exporter = exporter_cls(options=opt)
            exporter.export(novel.chapters, novel, **kwargs)

    @property
    def engine(self) -> APIEngine | RequestsEngine | BrowserEngine:
        return self._engine

    @property
    def storage(self) -> LocalStorage:
        """获取当前配置的 Storage 实例（惰性初始化）。"""
        if self._storage_instance is None:
            storage_opts = self._options.storage
            if storage_opts is None:
                raise RuntimeError(
                    "StorageOptions not configured. "
                    "Call options.set_storage_options(base_dir=...) first."
                )
            self._storage_instance = LocalStorage(storage_opts)
        return self._storage_instance

    @staticmethod
    def _resolve_fetcher(url: str):
        fetcher_cls = get_fetcher_for_url(url)
        if fetcher_cls is None:
            raise FetcherNotFoundError(f"fetcher not found for: {url}")
        return fetcher_cls()

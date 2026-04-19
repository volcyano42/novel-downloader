import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence, Any
from models.auth import AuthCredential
from models.novel import Novel, Chapter, Chapters, SearchResult

from core.exceptions import FeatureNotSupportedError
from core.progress import DownloadProgress
from core.engine import create_engine, Engine
from core.options import Options
from core.storage import Storage

from parsers.base import BaseParser
threading_lock = threading.Lock()

class NovelDownloader:
    def __init__(self, options: Options):
        self._options = options
        self._engine = None
        self._parser = None
        self._progress = None
        app_data_dir = Path(__file__).parent.parent.parent / "app_data"
        if novel_storage_dir:=self._options.storage:pass
        else:
            os.environ.get("NOVEL_STORAGE_DIR", app_data_dir / "storage")
            novel_storage_dir = app_data_dir / "storage"
        self._storage = Storage(novel_storage_dir)
        self.create_engine(options)

    @staticmethod
    def get_search_info(search_ref: str,
                        parser,
                        engine,
                        page: int = 0,
                        choice: int | None = None) -> Sequence[SearchResult] | str | None:
        search_result = parser.parse_search_info(search_ref=search_ref,
                                                 engine=engine,
                                                 page=page,
                                                 choice=choice)
        return search_result

    @staticmethod
    def get_novel_info(url: str, parser,engine) -> Novel | None:
        novel = parser.parse_novel_info(novel_ref=url, engine = engine)
        return novel

    @staticmethod
    def get_chapter_list(novel: Novel, parser,engine) -> Chapters | None:
        chapter_list = parser.parse_chapter_list(novel_ref=novel, engine = engine)
        return chapter_list

    @staticmethod
    def get_chapter_content(chapters: Sequence[Chapter], parser,engine) -> Chapters:
        chapters = parser.parse_chapter_content(chapter_ref=chapters, engine = engine)
        return chapters

    @staticmethod
    def get_parser_for_url(url) -> Any:
        from utils.registry import register_parser
        parser_item = register_parser()
        for name, parser in parser_item.items():
            if parser.can_handle(url):
                return parser
        else:
            return None

    @staticmethod
    def get_parsers() -> dict[str, Any]:
        from utils.registry import register_parser
        return register_parser()

    @staticmethod
    def get_exporters() -> dict[str, Any]:
        from utils.registry import register_exporter
        return register_exporter()

    @staticmethod
    def split_into_groups(target: Sequence[Chapter], group: int) -> tuple[Sequence[Chapter], ...]:
        return tuple([target[i:i + group] for i in range(0, len(target), group)])

    def login(self, platform: str) -> AuthCredential:
        if self._parser: parser = self._parser
        else:parser = self.get_parsers().get(platform)
        if isinstance(parser, BaseParser):
            return parser.login(engine=self._engine)
        else:
            raise FeatureNotSupportedError("login", f"Not Supported Platform: {platform}")

    def search(self, search_ref, page: int = 0, choice: int | None = None):

        search_result = self.get_search_info(search_ref=search_ref,
                                             parser=self._parser,
                                             engine=self._engine,
                                             page=page,
                                             choice=choice)
        return search_result

    def download(self, url: str, orders: Sequence[int] | None = None):
        if self._parser: parser = self._parser
        else: parser = self.get_parser_for_url(url)
        novel = self.get_novel_info(url=url, parser=parser, engine=self._engine)
        if novel is None:
            raise ValueError(f"Not Supported Url: {url}")
        all_chapters = self.get_chapter_list(novel=novel, parser=parser, engine=self._engine)
        if all_chapters is None:
            raise ValueError(f"Can not get chapter list: {url}")
        self._progress = DownloadProgress(novel.url)
        if progress := self._progress.load(self._storage.get_progress_path(novel.id)):
            self._progress = progress
        else:
            self._progress = DownloadProgress(novel.url)
            self._storage.save_progress(self._progress, novel.id)
        novel.update_chapter(all_chapters)
        existing_chapters = self._storage.load_chapters(novel.id)
        if existing_chapters: novel.update_chapter(existing_chapters)
        incompleted_chapters = novel.chapters.get_incompleted_chapters()
        if incompleted_chapters is None:incompleted_chapters = []
        target_chapters = list(incompleted_chapters) + list(chapter for chapter in all_chapters
                                                       if chapter not in existing_chapters)
        target_chapters.sort(key=lambda x: x.order)
        # 分配任务
        if orders:
            target_chapters = []
            for order in orders:
                if chapter := novel.chapters.get_chapter_by_order(order):
                    target_chapters.append(chapter)

        split_groups = self._options.api.batch_size if self._options.mode == "api" else 1
        group_chapters = self.split_into_groups(target=target_chapters, group=split_groups)

        from exporters.txt import TXTExporter, TXTExportOptions
        txt_options = TXTExportOptions(output_dir=Path(__file__).parent.parent.parent /"app_data" / "txt")
        txt_exporter = TXTExporter(options=txt_options, novel=novel)
        txt_exporter.export(novel.chapters)
        with ThreadPoolExecutor(max_workers=self._options.download.max_workers) as executor:
            future_to_chapter = [
                executor.submit(self.get_chapter_content, chapter, parser, self._engine)
                for chapter in group_chapters
            ]

            for future in as_completed(future_to_chapter):

                    result_chapters = future.result()
                    self._storage.save_chapter(novel, result_chapters)
                    self._progress.add_downloaded_chapter_id(result_chapters)
                    self._progress.update_timestamp()
                    self._storage.save_progress(self._progress, novel.id)
                    txt_exporter.export(novel.chapters)

    def create_engine(self, options: Options):
        self._engine = create_engine(options)

    def mount_engine(self, engine):
        self._engine = engine

    def mount_storage(self, storage_dir: Path | str):
        self._storage = Storage(storage_dir)

    def mount_parser(self, parser: Any | None):
        self._parser = parser

    @property
    def storage(self) -> Storage:
        return self._storage
    @property
    def parser(self) -> Any:
        return self._parser
    @property
    def engine(self) -> Engine:
        return self._engine

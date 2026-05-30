from abc import ABC, abstractmethod
from typing import Sequence, Iterable

from ..models.auth import AuthCredential
from ..models.novel import SearchResult, Novel, Chapter, Chapters


class BaseParser(ABC):

    @staticmethod
    @abstractmethod
    def can_handle(identifier: str) -> bool:
        pass

    @abstractmethod
    def login(self, engine, **kwargs) -> AuthCredential:
        pass

    @abstractmethod
    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          choice: int | None = None,
                          **kwargs) -> Sequence[SearchResult] | str | None:
        pass

    @abstractmethod
    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        pass

    @abstractmethod
    def parse_chapter_list(self, novel_ref: Novel, engine, **kwargs) -> Chapters:
        pass

    @abstractmethod
    def parse_chapter_content(self,
                              chapter_ref: Iterable[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        """解析并填充特定数据"""
        pass

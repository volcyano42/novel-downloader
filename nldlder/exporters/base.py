from abc import ABC, abstractmethod
from typing import Iterable

from models.novel import Chapter, Novel


class BaseExporter(ABC):

    @abstractmethod
    def __init__(self,options, novel: Novel):
        self.options = options
        self.novel = novel

    @abstractmethod
    def export(self, chapters: Chapter | Iterable[Chapter], **kwargs):
        """导出"""
        pass


from abc import ABC, abstractmethod
from typing import Iterable

from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel


class BASEExporter(ABC):

    def __init__(self, options: ExportOptions):
        self.options = options

    @abstractmethod
    def export(self, chapters: Chapter | Iterable[Chapter], meta: Novel, **kwargs):
        """导出"""
        pass


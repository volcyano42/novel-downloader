import re
from abc import ABC, abstractmethod
from typing import Any, Sequence

from nldlder.core.exceptions import FeatureNotSupportedError
from nldlder.models.auth import AuthCredential
from nldlder.models.novel import SearchResult, Novel, Chapter, Chapters


class BaseFetcher(ABC):

    host: tuple[str, ...] = ()
    id_pattern: re.Pattern | None = None  # 匹配裸 novel_id，用 group(1) 提取

    def login(self, engine, **kwargs: Any) -> AuthCredential:
        """登录目标站点。

        成功返回 AuthCredential（含 cookies），失败或不支持时
        raise ``FeatureNotSupportedError``。
        """
        raise FeatureNotSupportedError(f"{type(self).__name__} 不支持登录")

    @abstractmethod
    def fetch_search_result(self,
                            search_ref: str,
                            engine,
                            page: int = 1,
                            **kwargs: Any) -> tuple[SearchResult, ...]:
        """搜索小说，返回搜索结果列表。

        Args:
            search_ref: 搜索关键词（书名或作者名）。
            engine:     下载引擎实例（用于发起 HTTP 请求）。
            page:       页码，从 1 开始。

        Returns:
            搜索结果元组，每项含 ``title``／``author``／``url``／
            ``description``。无结果返回空元组 ``()``。
        """
        ...

    @abstractmethod
    def fetch_novel_info(self, novel_ref: str, engine, **kwargs: Any) -> Novel:
        """解析小说详情页，返回 Novel 对象。

        Args:
            novel_ref: 小说页面 URL 或 HTML。
            engine:    下载引擎实例。

        Returns:
            Novel 对象。
        """
        ...

    @abstractmethod
    def fetch_chapter_list(self, novel_ref: str, engine, **kwargs: Any) -> Chapters:
        """解析章节目录，返回待填充的 Chapters 列表。

        Args:
            novel_ref: 小说页面 URL 或 HTML。
            engine:    下载引擎实例。

        Returns:
            Chapters 对象，每章应填充 id / url / title / order / volume。
            content / is_complete 等字段留空。
        """
        ...

    @abstractmethod
    def fetch_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs: Any) -> Chapters:
        """解析并填充章节正文内容。

        Args:
            chapter_ref: 待填充的 Chapter 列表（API/Browser parser）
                         或章节 HTML 字符串（HTML parser 内部调用）。
            engine:      下载引擎实例。

        Returns:
            已填充 content / is_complete / images 的 Chapters。
        """
        ...

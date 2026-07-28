import re
from typing import Any

from novelbase.core.exceptions import FeatureNotSupportedError
from novelbase.models.auth import AuthCredential
from novelbase.models.novel import SearchResult, Novel, Chapter, Chapters

NAME = "qidian"
BASE_URLS = ["www.qidian.com", "book.qidian.com"]


def _use_fetcher(engine):
    if engine.name == "browser":
        from .browser import search, fetch_novel, fetch_chapter_list, fetch_chapter, login as _login
        return search, fetch_novel, fetch_chapter_list, fetch_chapter, _login
    elif engine.name == "requests":
        from .requests import search, fetch_novel, fetch_chapter_list, fetch_chapter
        return search, fetch_novel, fetch_chapter_list, fetch_chapter, None
    elif engine.name == "API":
        raise FeatureNotSupportedError("起点中文网不支持 API 模式")
    else:
        raise ValueError(f"Unknown engine: {engine.name!r}")


class QidianFetcher:
    host = ("www.qidian.com", "book.qidian.com")
    id_pattern = re.compile(r"^(?:/(book|info)/?)?(\d{10})/?$")

    def login(self, engine, **kwargs) -> AuthCredential:
        _, _, _, _, _login = _use_fetcher(engine=engine)
        if _login is None:
            raise FeatureNotSupportedError("Not Supported login by this engine")
        return _login(engine=engine, **kwargs)

    def fetch_search_result(self, query: str, engine, **kwargs: Any) -> tuple[SearchResult, ...]:
        search_fn, _, _, _, _ = _use_fetcher(engine=engine)
        return tuple(search_fn(query=query, engine=engine, **kwargs))

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        _, fetch_novel_fn, _, _, _ = _use_fetcher(engine=engine)
        return fetch_novel_fn(url=url, engine=engine, **kwargs)

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:
        _, _, fetch_cl_fn, _, _ = _use_fetcher(engine=engine)
        return fetch_cl_fn(url=url, engine=engine, **kwargs)

    def fetch_chapter_content(self, chapter: Chapter, engine, **kwargs: Any) -> Chapter | None:
        _, _, _, fetch_ch_fn, _ = _use_fetcher(engine=engine)
        return fetch_ch_fn(chapter=chapter, engine=engine, **kwargs)

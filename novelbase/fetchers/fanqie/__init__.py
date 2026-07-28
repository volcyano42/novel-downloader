import re
from typing import Any

from novelbase.core.exceptions import FeatureNotSupportedError
from novelbase.models.auth import AuthCredential
from novelbase.models.novel import SearchResult, Novel, Chapter, Chapters

from ._common import resolve_changdunovel

NAME = "fanqie"
BASE_URLS = ["fanqienovel.com", "changdunovel.com"]


def _use_fetcher(engine):
    """根据 engine 类型返回对应的子模块函数集合。"""
    if engine.name == "browser":
        from .browser import search, fetch_novel, fetch_chapter_list, fetch_chapter, login as _login
        return search, fetch_novel, fetch_chapter_list, fetch_chapter, _login
    elif engine.name == "requests":
        from .requests import search, fetch_novel, fetch_chapter_list, fetch_chapter
        return search, fetch_novel, fetch_chapter_list, fetch_chapter, None
    elif engine.name == "API":
        api_name = engine.options.name
        if api_name is None or api_name == "oiapi":
            from .api.oiapi import search, fetch_novel, fetch_chapter_list, fetch_chapter
            return search, fetch_novel, fetch_chapter_list, fetch_chapter, None
        if api_name == "rain":
            from .api.rain import search, fetch_novel, fetch_chapter_list, fetch_chapter
            return search, fetch_novel, fetch_chapter_list, fetch_chapter, None
        raise ValueError(
            f"Unsupported API backend: {api_name!r}. "
            f"Only 'oiapi' and 'rain' are supported."
        )
    else:
        raise ValueError(f"Unknown engine: {engine.name}")


class FanqieFetcher:
    host = ("fanqienovel.com", "changdunovel.com")
    id_pattern = re.compile(r"^(?:book_id=?)?(\d{19})$")

    def login(self, engine, **kwargs) -> AuthCredential:
        _search, _novel, _chlist, _ch, _login = _use_fetcher(engine=engine)
        if _login is None:
            raise FeatureNotSupportedError("Not Supported login by this engine")
        return _login(engine=engine, **kwargs)

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs: Any) -> tuple[SearchResult, ...]:
        search_fn, _, _, _, _ = _use_fetcher(engine=engine)
        return tuple(search_fn(query=query, engine=engine, **kwargs))

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        url = resolve_changdunovel(url)
        _, fetch_novel_fn, _, _, _ = _use_fetcher(engine=engine)
        return fetch_novel_fn(url=url, engine=engine, **kwargs)

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        url = resolve_changdunovel(url)
        _, _, fetch_cl_fn, _, _ = _use_fetcher(engine=engine)
        return fetch_cl_fn(url=url, engine=engine, **kwargs)

    def fetch_chapter_content(self,
                              chapter: Chapter,
                              engine,
                              **kwargs: Any) -> Chapter | None:
        _, _, _, fetch_ch_fn, _ = _use_fetcher(engine=engine)
        return fetch_ch_fn(chapter=chapter, engine=engine, **kwargs)

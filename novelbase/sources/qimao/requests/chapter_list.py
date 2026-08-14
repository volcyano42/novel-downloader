"""qimao requests - fetch chapter list.
Note: qimao chapter catalog is loaded by client-side JS in the initial SSR HTML.
If the catalog is missing from SSR HTML, fallback to reader sidebar (partial only).
For the full catalog, use browser engine."""

from .._common import parse_chapter_list, standardize_id
from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter


async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    html = await engine.async_fetch_text(url=url, **kwargs)
    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    if len(chapters) == 0:
        raise ChapterNotFoundError(
            "qimao chapter catalog not found in initial HTML (loaded by JS), "
            "please use browser engine or provide catalog page HTML"
        )
    return list(chapters)

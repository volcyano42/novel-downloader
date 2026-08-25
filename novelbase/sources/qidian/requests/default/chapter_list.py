from novelbase.models.novel import Novel, Chapter
from ..._common import parse_chapter_list


async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    url = url.url if isinstance(url, Novel) else url
    html = await engine.async_fetch_text(url=url, **kwargs)
    chapters = parse_chapter_list(html, url=url)
    return list(chapters) if chapters else []

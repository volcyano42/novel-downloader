from .._common import parse_chapter_list
from novelbase.models.novel import Novel, Chapter


def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    url = url.url if isinstance(url, Novel) else url
    html = engine.fetch_text(url=url, **kwargs)
    chapters = parse_chapter_list(html, url=url)
    return list(chapters) if chapters else []

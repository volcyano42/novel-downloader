from .._common import parse_novel_info
from novelbase.models.novel import Novel


def novel_info(url: str, engine, **kwargs) -> Novel:
    html = engine.fetch_text(url=url, **kwargs)
    return parse_novel_info(html, url=url)

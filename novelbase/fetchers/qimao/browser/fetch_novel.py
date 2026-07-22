"""qimao browser - fetch novel info."""

from .._common import parse_novel_info, standardize_id
from novelbase.models.novel import Novel


def fetch_novel(url: str, engine, **kwargs) -> Novel:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    html = engine.fetch_text(url=url, **kwargs)
    return parse_novel_info(html, url=url)

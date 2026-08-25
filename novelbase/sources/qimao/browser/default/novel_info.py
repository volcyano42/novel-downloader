"""qimao browser - fetch novel info."""

from novelbase.models.novel import Novel, Illustration
from ..._common import parse_novel_info, standardize_id


async def novel_info(url: str, engine, **kwargs) -> Novel:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    html = await engine.async_fetch_text(url=url, **kwargs)
    novel = parse_novel_info(html, url=url)
    if novel.cover and novel.cover.url:
        data = await engine.async_fetch_images([novel.cover.url])
        novel.cover = Illustration(
            raw_data=data[0], alt=novel.cover.alt, url=novel.cover.url
        )
    return novel

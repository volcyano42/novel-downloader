from bs4 import BeautifulSoup

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Illustration
from ..._common import standardize_id, parse_chapter_content


async def chapter_content(chapter, engine, **kwargs):
    url = f"https://fanqienovel.com/reader/{standardize_id(chapter)}"
    html = await engine.async_fetch_text(url=url, **kwargs)

    if BeautifulSoup(html, "lxml").select_one("div.no-content"):
        raise ChapterNotFoundError("Chapter page shows no-content div")

    result = parse_chapter_content(html, chapter)
    if result is None:
        return None
    ch, img_urls = result
    if img_urls:
        data = await engine.async_fetch_images([i["url"] for i in img_urls])
        ch.images = tuple(
            Illustration(raw_data=d, url=i["url"], alt=i["alt"], insert=i["insert"])
            for i, d in zip(img_urls, data)
        )
    return ch

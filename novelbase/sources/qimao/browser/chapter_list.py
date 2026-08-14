"""qimao browser - fetch chapter list.
Browser engine needs to click the catalog tab to trigger chapter loading."""

import asyncio

from .._common import parse_chapter_list, standardize_id
from novelbase.models.novel import Chapter


async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"

    # DrissionPage 是同步库，页面前进/点击等交互放到线程池
    def _sync():
        page = engine.new_page()
        try:
            page.get(url)
            catalog_tab = page.ele(".tab-inner")
            if catalog_tab:
                catalog_tab.click()
                page.wait(3)
            return page.html
        finally:
            page.close()

    html = await asyncio.to_thread(_sync)
    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    return list(chapters)

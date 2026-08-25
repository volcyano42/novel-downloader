"""qimao browser - fetch chapter list.
Browser engine needs to click the catalog tab to trigger chapter loading."""

from novelbase.models.novel import Chapter
from ..._common import parse_chapter_list, standardize_id


async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"

    # Playwright 原生 async：直接 await，不再 to_thread
    page = await engine.new_page()
    try:
        await page.goto(url)
        catalog_tab = page.locator(".tab-inner")
        if await catalog_tab.count() > 0:
            await catalog_tab.click()
            await page.wait_for_timeout(3000)
        html = await page.content()
    finally:
        await page.close()

    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    return list(chapters)

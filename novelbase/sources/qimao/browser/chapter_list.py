"""qimao browser - fetch chapter list.
Browser engine needs to click the catalog tab to trigger chapter loading."""

from .._common import parse_chapter_list, standardize_id
from novelbase.models.novel import Chapter


def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    # Browser: click catalog tab to trigger chapter loading
    page = engine.new_page()
    try:
        page.get(url)
        catalog_tab = page.ele(".tab-inner")
        if catalog_tab:
            catalog_tab.click()
            page.wait(3)
        html = page.html
    finally:
        page.close()
    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    return list(chapters)

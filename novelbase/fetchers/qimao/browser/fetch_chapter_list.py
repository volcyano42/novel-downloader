"""七猫 browser 模式 - 获取章节目录�?
浏览器引擎下需要点击「作品目录」tab 以触发章节加载�?"""

from .._common import parse_chapter_list, standardize_id
from novelbase.models.novel import Chapter


def fetch_chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    # 浏览器引擎：需要点击「作品目录」tab 以触发章节加�?    page = engine.new_page()
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

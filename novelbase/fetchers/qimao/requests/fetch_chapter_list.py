"""七猫 requests 模式 - 获取章节目录�?
注意：七猫的章节目录由客户端 JS 动态加载，初始 HTML 中可能不包含完整目录�?�?SSR HTML 中缺失目录，会尝试从阅读页侧边栏获取（仅部分章节）�?完整目录建议使用浏览器引擎�?"""

from .._common import parse_chapter_list, standardize_id
from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter


def fetch_chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    html = engine.fetch_text(url=url, **kwargs)
    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    if len(chapters) == 0:
        raise ChapterNotFoundError(
            "七猫章节目录未在初始 HTML 中找到（�?JS 动态加载）�?
            "请使用浏览器引擎或提供目录页 HTML"
        )
    return list(chapters)

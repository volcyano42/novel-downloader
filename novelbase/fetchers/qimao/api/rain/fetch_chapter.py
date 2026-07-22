"""七猫 API（Rain）模�?- 获取章节正文�?""

from ..._common import _api_url
from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter


def fetch_chapter(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    """解析并填�?content, count, (True)�?""
    # chapter.id from Rain API is the chapter ID directly (e.g. "17061706560001")
    api_url = _api_url(engine, type=4, id=chapter.novel_id, chapterid=chapter.id)
    response = engine.fetch_json(api_url, **kwargs)

    code = response.get("code")
    if code is not None and code != 0 and str(code) != "0":
        raise ChapterNotFoundError(message=f"Chapter content error: code={code}")

    data = response.get("data", {})
    raw_content = data.get("content", "")
    content = raw_content.strip()
    # Unescape HTML entities in content
    content = content.replace("&#8722;", "�?).replace("&#9450;", "�?)
    # Replace <br/> tags with double newlines to create proper paragraph breaks
    content = content.replace("<br/>", "\n\n").replace("<br />", "\n\n")
    if not content:
        raise ChapterNotFoundError("Rain API returned empty chapter content")

    chapter.content = content
    chapter.count = len(content)

    return chapter

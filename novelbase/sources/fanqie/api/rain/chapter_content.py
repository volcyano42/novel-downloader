from novelbase.core.exceptions import ChapterNotFoundError

from ..._common import standardize_id
from ._helpers import _api_url


def chapter_content(chapter, engine, **kwargs):
    """解析并填充content, count"""
    item_id = standardize_id(chapter)
    url = _api_url(engine, type=4, itemid=item_id)
    response = engine.fetch_json(url, **kwargs)

    if response.get("code") != 0 and str(response.get("code")) != "0":
        err_msg = response.get("data", {}).get("content", "Unknown error")
        raise ChapterNotFoundError(message=f"Chapter content error: {err_msg}")

    data = response.get("data", {})
    title = data.get("title", "")
    raw_content = data.get("content", "")
    content = raw_content.strip()
    content = content.replace("</p>", "\n\n")
    if content.startswith(title):
        content = content[len(title):].strip()

    chapter.content = content
    chapter.count = len(content)

    return chapter

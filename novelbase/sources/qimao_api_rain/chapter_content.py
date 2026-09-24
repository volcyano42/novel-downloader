"""qimao API (Rain) - fetch chapter content."""

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter


def _api_url(engine, **params) -> str:
    """Rain API URL builder."""
    key = engine.options.key
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://v3.rain.ink/qimao/?apikey={key}&{qs}"

async def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    """Parse and fill content, count."""
    api_url = _api_url(engine, type=4, id=chapter.novel_id, chapterid=chapter.id)
    response = await engine.async_fetch_json(api_url, **kwargs)

    code = response.get("code")
    if code is not None and code != 0 and str(code) != "0":
        raise ChapterNotFoundError(message=f"Chapter content error: code={code}")

    data = response.get("data", {})
    raw_content = data.get("content", "")
    content = raw_content.strip()
    content = content.replace("&#8722;", "\u2212").replace("&#9450;", "\u24da")
    content = content.replace("<br/>", "\n\n").replace("<br />", "\n\n")
    if not content:
        raise ChapterNotFoundError("Rain API returned empty chapter content")

    chapter.content = content
    chapter.count = len(content)

    return chapter

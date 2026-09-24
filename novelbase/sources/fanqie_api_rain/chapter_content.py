import re

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Novel, Chapter


def _api_url(engine, **params) -> str:
    key = engine.options.key
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    base = f"https://v3.rain.ink/fanqie/?apikey={key}"
    return f"{base}&{qs}" if qs else base


def standardize_id(ref: str | Novel | Chapter) -> str:

    if isinstance(ref, Novel):
        ref = ref.url
    if isinstance(ref, Chapter):
        ref = ref.url
    if isinstance(ref, str):
        if re.match(r"^\d{19}$", ref):
            return ref
        if search := re.search(r"book_id=(\d{19})", ref):
            return search.group(1)
        if search := re.search(r"\d{19}", ref):
            return search.group(0)
    raise ValueError(f"ref {ref} Non conformance")


async def chapter_content(chapter, engine, **kwargs):
    """解析并填充content, count"""
    item_id = standardize_id(chapter)
    url = _api_url(engine, type=4, itemid=item_id)
    response = await engine.async_fetch_json(url, **kwargs)

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

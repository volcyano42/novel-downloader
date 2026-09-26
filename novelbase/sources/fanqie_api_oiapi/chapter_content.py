import re

from novelbase.core.exceptions import AntiCrawlError, ChapterNotFoundError
from novelbase.models.novel import Novel, Chapter


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
    novel_id = standardize_id(chapter.novel_id)
    post_data = {
        "id": novel_id,
        "chapter": str(chapter.order),
        "key": engine.options.key,
        "method": "chapter",
        "type": "json"
    }
    response = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

    data_list = response.get('data')
    if not data_list:
        message = response.get('message', "")
        if message == "请检测章节选择是否正确":          # 章节越界（code=-3）
            raise ChapterNotFoundError(message=f"Invalid chapter order: {chapter.order}")
        elif "Trying to access array offset" in message:   # 频控（保留既有特判）
            raise AntiCrawlError("OIAPI request frequency too high, PHP backend rejected")
        else:
            raise ChapterNotFoundError(message=f"OIAPI unexpected response: {message}")

    # 契约实测 2026-09-26：data 为 list（首项含 content/word_number/
    # chapter_id/chapter_title/volume_name…）；兼容 dict 形态。
    first = data_list[0] if isinstance(data_list, list) else next(iter(data_list.values()), {})
    chapter.content = (first.get('content') or '').replace(
        f"{first.get('chapter_title', '')}\n\n", "")
    chapter.count = int(first.get('word_number') or 0)

    return chapter

from novelbase.core.exceptions import AntiCrawlError, ChapterNotFoundError

from ..._common import standardize_id


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

    data_list: dict = response.get('data', {})
    if not data_list:
        message = response.get('message', "")
        if message == "请检测章节选择是否正确":
            raise ChapterNotFoundError(message=f"Invalid chapter order: {chapter.order}")
        elif message == "实例化失败：Trying to access array offset on value of type bool line 197 in api.php":
            raise AntiCrawlError("OIAPI request frequency too high, PHP backend rejected")
        else:
            raise ChapterNotFoundError(message=f"OIAPI unexpected response: {message}")

    for data in data_list.values() if isinstance(data_list, dict) else []:
        chapter.content = data.get('content', '').replace(f"{data.get('chapter_title', '')}\n\n", "")
        chapter.count = data.get('word_number', 0)
        break

    return chapter

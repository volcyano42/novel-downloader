"""章节目录（番茄 app API，all_items 全量目录）。

接口：GET https://reading.snssdk.com/reading/bookapi/directory/all_items/v1/
参数：公共参数链 + book_id
响应 data.item_data_list：[{item_id, title, volume_name, chapter_word_number,
first_pass_time, chapter_type, ...}] —— 含真实标题与卷名（2026-08-23 实测，
四件套签名下可用；此前仅 x-gorgon 签名时返回空）。

注意：item_data_list 是否覆盖全书取决于该书规模与分页策略，必要时可结合
book_info_md5 / catalog_data_md5 / item_data_list_md5 增量参数拉取。
"""
from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters
from ._client import HOST_APP, common_params, signed_get_json
from ..._common import standardize_id


async def chapter_list(url: str, engine, **kwargs) -> Chapters:
    book_id = standardize_id(url)
    params = common_params(engine)
    params["book_id"] = book_id
    data = await signed_get_json(f"{HOST_APP}/reading/bookapi/directory/all_items/v1/", params)

    item_list = ((data.get("data") or {}).get("item_data_list")) or []
    if not item_list:
        raise ChapterNotFoundError(f"appapi: empty item_data_list for book_id={book_id}")

    chapters = []
    for order, item in enumerate(item_list, 1):
        item_id = item.get("item_id")
        if not item_id:
            continue
        title = item.get("title") or f"第{order}章"
        chapter = Chapter(
            title=title,
            url=f"https://fanqienovel.com/reader/{item_id}",
            novel_id=book_id,
            id=str(item_id),
            order=order,
            volume=item.get("volume_name"),
            time=item.get("first_pass_time"),
            count=item.get("chapter_word_number"),
        )
        chapters.append(chapter)
    return Chapters(chapters)

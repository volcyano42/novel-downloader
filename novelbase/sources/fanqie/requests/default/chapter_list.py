from ..._common import standardize_id, parse_chapter_list


async def chapter_list(url: str, engine, **kwargs) -> list:
    url = f"https://fanqienovel.com/page/{standardize_id(url)}"
    html = await engine.async_fetch_text(url=url, **kwargs)
    return list(parse_chapter_list(html=html))

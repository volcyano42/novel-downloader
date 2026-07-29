from .._common import standardize_id, parse_novel_info


def novel_info(url: str, engine, **kwargs):
    url = f"https://fanqienovel.com/page/{standardize_id(url)}"
    html = engine.fetch_text(url=url, **kwargs)
    return parse_novel_info(html=html)

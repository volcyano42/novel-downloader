from .._common import parse_search_result, extract_json


def search(query: str, engine, **kwargs) -> list:
    page = kwargs.pop("page", 1)
    search_url = f"https://fanqienovel.com/search?keyword={query}&page={page}"
    html = engine.fetch_text(url=search_url, **kwargs)

    # 搜索结果页嵌入 __INITIAL_STATE__ JSON
    json_data = extract_json(html)
    return list(parse_search_result(data=json_data))

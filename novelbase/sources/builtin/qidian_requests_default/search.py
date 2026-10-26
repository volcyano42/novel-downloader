from novelbase.core.exceptions import FeatureNotSupportedError
from novelbase.models.novel import SearchResult


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    raise FeatureNotSupportedError("起点中文网不支持 Requests 获取搜索结果")

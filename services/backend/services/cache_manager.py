"""缓存管理器 — 预留基类，后续引擎/搜索/章节缓存统一对接此接口。"""
from abc import ABC, abstractmethod
from typing import Any


class CacheManager(ABC):
    """缓存抽象，当前为占位。未来实现 TTL / LRU / 序列化。"""

    @abstractmethod
    def get(self, key: str) -> Any | None: ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl: float | None = None) -> None: ...

    @abstractmethod
    def invalidate(self, key: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


class NoopCacheManager(CacheManager):
    """空缓存实现 — 不做任何缓存，始终穿透。"""

    def get(self, key: str) -> None:
        return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        pass

    def invalidate(self, key: str) -> None:
        pass

    def clear(self) -> None:
        pass

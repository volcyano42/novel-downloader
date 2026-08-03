"""Source 能力协议与元数据。

Protocol 类声明四项核心能力的函数签名（供 IDE 与文档参考）；
CAPABILITY_META 是能力元数据的单一数据源，替代 FUNC_FILE_MAP。

**新增能力类型**：只需在 CAPABILITY_META 加一条，capabilities()/resolve() 自动感知。
**新增源平台**：直接在 sources/ 下创建目录/文件即可，无需修改任何注册表。
"""

from typing import Any, Protocol


class SearchFunc(Protocol):
    """搜索小说。

    签名: (query: str, engine, **kwargs) -> 搜索结果序列
    """
    def __call__(self, query: str, engine: Any, **kwargs: Any) -> Any: ...


class NovelInfoFunc(Protocol):
    """获取小说元数据。

    签名: (url: str, engine, **kwargs) -> Novel
    """
    def __call__(self, url: str, engine: Any, **kwargs: Any) -> Any: ...


class ChapterListFunc(Protocol):
    """获取章节列表。

    签名: (url: str, engine, **kwargs) -> Chapters
    """
    def __call__(self, url: str, engine: Any, **kwargs: Any) -> Any: ...


class ChapterContentFunc(Protocol):
    """下载章节内容。

    签名: (chapter, engine, **kwargs) -> Chapter | None
    """
    def __call__(self, chapter: Any, engine: Any, **kwargs: Any) -> Any: ...


# ═══════════════════════════════════════════════════════════════════
# 能力元数据 — 单一数据源
# ═══════════════════════════════════════════════════════════════════
#
# key:     能力名（与源目录中的 .py 文件名一致）
#   file_stem:       文件名 stem（不含 .py）
#   required_params: resolve() 运行时签名校验所需的参数名
#
# 注意: 这是能力 *类型* 的元数据，不是源平台列表。
# 源平台通过文件系统扫描动态发现，不在任何地方硬编码。

CAPABILITY_META: dict[str, dict] = {
    "search":          {"file_stem": "search",          "required_params": ("query",   "engine")},
    "novel_info":      {"file_stem": "novel_info",      "required_params": ("url",     "engine")},
    "chapter_list":    {"file_stem": "chapter_list",    "required_params": ("url",     "engine")},
    "chapter_content": {"file_stem": "chapter_content", "required_params": ("chapter", "engine")},
}

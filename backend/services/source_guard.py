"""按 source_name 取参的 HTTP 边界校验。

core 层对未知书源是宽容语义（`novelbase.source.capabilities()` 与
`shared.config.merged_source_config()` 都返回 `{}`），但 HTTP 入口不应把
「书源名写错」当成空配置继续跑（读未知书源的配置会 `KeyError` → 500）。
本模块是**唯一**校验点，避免各路由各写一份。
"""

from fastapi import HTTPException

from novelbase.source import list_sources


def require_known_source(source_name: str) -> str:
    """书源名必须存在（`list_sources()`），否则 404。"""
    if source_name not in list_sources():
        raise HTTPException(404, f"未知书源: {source_name}")
    return source_name

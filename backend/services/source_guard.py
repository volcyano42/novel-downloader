"""按 source_name 取参的 HTTP 边界校验。

core 层对未知书源是宽容语义（`novelbase.source.capabilities()` 与
`shared.config.merged_source_config()` 都返回 `{}`），但 HTTP 入口不应把
「书源名写错」当成空配置继续跑（`is_source_enabled()` 会 `KeyError` → 500）。
本模块是**唯一**校验点，避免各路由各写一份。
"""

from fastapi import HTTPException

from novelbase.source import list_sources
from shared.config import effective_capabilities, is_source_available, supported_modes


def require_known_source(source_name: str) -> str:
    """书源名必须存在（`list_sources()`），否则 404。"""
    if source_name not in list_sources():
        raise HTTPException(404, f"未知书源: {source_name}")
    return source_name


def require_available_source(source_name: str) -> str:
    """书源必须在本环境可用（如 Android 不支持 browser），否则 400。

    「本环境不支持」是用户可理解的输入问题（不是服务端故障），故 400；与
    `require_known_source` 的 404 一起构成 HTTP 边界的**唯一**校验点。
    只用于**执行 / 写**入口：GET 配置读取必须放行，否则前端无法置灰展示。
    """
    if not is_source_available(source_name):
        blocked = sorted({m for m in effective_capabilities(source_name).values()
                          if m not in supported_modes()})
        detail = "、".join(blocked) if blocked else "未知引擎"
        raise HTTPException(400, f"本环境不支持 {detail}，无法使用书源: {source_name}")
    return source_name


def require_supported_mode(mode: str, *, source_name: str, capability: str = "") -> str:
    """mode 必须在本环境可用（如 Android 无 browser），否则 400。

    用于**写**入口（书源配置的 mode 覆盖）：把「设成本环境装不上的引擎」挡在落盘之前。
    """
    if mode not in supported_modes():
        where = f"{source_name}/{capability}" if capability else source_name
        raise HTTPException(400, f"本环境不支持引擎 {mode}: {where}")
    return mode

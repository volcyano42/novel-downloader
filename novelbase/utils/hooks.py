"""用户扩展 Hook — 下载流程切入点和章节过滤器。"""

from dataclasses import dataclass, field
from typing import Callable

from novelbase.models.novel import Chapter, Novel


@dataclass
class SourceHooks:
    """下载流程 Hook，所有回调默认 no-op。

    用法::

        hooks = SourceHooks(
            chapter_filter=lambda ch: ch.order <= 100,  # 只下载前 100 章
            on_chapter_done=lambda ch, novel: print(f"完成: {ch.title}"),
            on_finish=lambda novel: print("全部下载完成!"),
        )
    """

    chapter_filter: Callable[[Chapter], bool] = field(
        default=lambda _: True
    )
    """返回 False 跳过该章（在下载前调用）。"""

    on_chapter_done: Callable[[Chapter, Novel], None] = field(
        default=lambda ch, novel: None
    )
    """每章下载完成后回调（已落盘）。"""

    on_finish: Callable[[Novel], None] = field(
        default=lambda novel: None
    )
    """全部下载完成后回调。"""

    on_error: Callable[[Chapter, Exception], None] = field(
        default=lambda ch, exc: None
    )
    """单章下载失败时回调。"""

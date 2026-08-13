"""导出器契约与元数据。

Protocol 类声明导出函数的签名（供 IDE 与文档参考）；
EXPORT_REQUIRED_PARAMS 是导出函数签名校验的单一数据源。

**新增导出格式**：写一个 .py 文件，内含
    - 一个继承 ExportOptions 且带 format 字段的 *ExportOptions 类
    - 一个顶层 export(chapters, novel, options=None, **kwargs) 函数
  放在 exporters/ 目录或 NLD_PRIVATE_EXPORTERS 指向的外部目录即可，
  无需修改任何注册表。
"""

from pathlib import Path
from typing import Any, Protocol

from ..core.options import ExportOptions
from ..models.novel import Novel


class ExportFunc(Protocol):
    """导出函数签名。

    签名: (chapters, novel, options=None, **kwargs) -> Path
    """

    def __call__(
        self,
        chapters,
        novel: Novel,
        options: ExportOptions | None = None,
        **kwargs: Any,
    ) -> Path: ...


# 导出函数运行时签名校验所需的参数名（与 sources/contracts.py 的
# CAPABILITY_META["required_params"] 语义一致）
EXPORT_REQUIRED_PARAMS: tuple[str, ...] = ("chapters", "novel")

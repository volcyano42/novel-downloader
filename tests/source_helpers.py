"""测试辅助：按 `source_name` 加载书源能力模块。

书源可能来自任意源根（官方 `novelbase/sources/builtin/` 或用户根
`<APP_DATA>/sources/`，后者不随仓库发行），因此**不能**再用
`import_module("novelbase.sources.builtin.{dir}")` 这种包路径 —— 源一旦出仓就断。
这里走发现层拿到真实目录，再按文件路径加载，与生产代码同一条路径。
"""

from __future__ import annotations

import importlib.util
from types import ModuleType

import pytest

# 提前 import：`shared.config` 在 import 时把 <APP_DATA>/sources 注册进发现层。
# collect 阶段若没这一步，已出仓到用户源根的源会被判为「不存在」。
import shared.config  # noqa: F401


def load_source_module(
    source_name: str, capability: str, *, module_level: bool = False
) -> ModuleType:
    """加载 `{源根}/{dir}/{capability}.py` 模块；源不可用时 `pytest.skip`。

    测试需要访问能力函数之外的模块符号（私有解析辅助、常量表）时用本函数；
    只调能力函数本身时应直接用 `novelbase.source.resolve()`。

    `module_level=True` 供模块级调用（collect 期），否则 pytest 拒绝 skip。
    """
    from novelbase.source import _source_dir

    d = _source_dir(source_name)
    if d is None:
        pytest.skip(
            f"书源 {source_name} 不可用（未安装或已出仓到用户源根）",
            allow_module_level=module_level,
        )
    path = d / f"{capability}.py"
    if not path.is_file():
        pytest.skip(
            f"书源 {source_name} 没有 {capability} 能力",
            allow_module_level=module_level,
        )
    mod_name = f"nld_test_src.{d.name}.{capability}"
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    if spec is None or spec.loader is None:
        pytest.skip(f"无法为 {path} 构造模块 spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

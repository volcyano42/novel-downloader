"""能力文件可运行性回归检查：AST 未定义名检查。

Task 3 把旧 `_common.py`/`_helpers.py` 逐字内联进各能力文件时，曾漏补函数体
依赖的模块级 import（qimao 8 个文件，运行时 `NameError`）。而 `load_manifest` /
`check_capability_files` / `import` 都不执行函数体，结构测试全部绿灯也拦不住。

本测试在 AST 层面检查：每个能力文件的每个函数体里，所有被加载的名字
（`Name` 节点的 Load 上下文）都必须能解析到 —— 要么是 builtins，要么来自
模块级 import / 模块级赋值 / 模块级 def，要么是该函数作用域内的参数与局部绑定。
无第三方依赖（标准库 `ast` / `builtins`）。
"""
import ast
import builtins
from pathlib import Path

import pytest

SOURCES = Path(__file__).resolve().parents[1] / "novelbase" / "sources"

# 10 个书源目录（与 test_source_layout.EXPECTED_MODE 一致）
EXPECTED_MODE = {
    "fanqie_api_oiapi": "api",
    "fanqie_api_rain": "api",
    "fanqie_browser_default": "browser",
    "fanqie_requests_default": "requests",
    "qidian_browser_default": "browser",
    "qidian_requests_default": "requests",
    "qimao_api_rain": "api",
    "qimao_browser_default": "browser",
    "qimao_requests_default": "requests",
    "92xs_requests_default": "requests",
}

CAPABILITIES = ("search", "novel_info", "chapter_list", "chapter_content")


def _collect_targets(node, out: set) -> None:
    """把赋值目标里的名字收集进 out（Tuple/List/Starred 递归）。"""
    if isinstance(node, ast.Name):
        out.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            _collect_targets(elt, out)
    elif isinstance(node, ast.Starred):
        _collect_targets(node.value, out)
    # Subscript / Attribute 不是名字绑定，忽略


def _arg_names(args: ast.arguments) -> set:
    names = {a.arg for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _module_bindings(tree: ast.Module) -> set:
    """模块级可用的名字：import 引入 / def / class / 赋值目标 / 注解赋值。"""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    names.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                _collect_targets(t, names)
        elif isinstance(node, ast.AnnAssign):
            _collect_targets(node.target, names)
    return names


def _function_bindings(func: ast.AST) -> set:
    """函数作用域内绑定的名字（参数 + 赋值 + for/with/except/comprehension/walrus 等）。"""
    names: set = set()
    if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names |= _arg_names(func.args)
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                _collect_targets(t, names)
        elif isinstance(node, ast.AnnAssign):
            _collect_targets(node.target, names)
        elif isinstance(node, ast.NamedExpr):
            _collect_targets(node.target, names)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _collect_targets(node.target, names)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    _collect_targets(item.optional_vars, names)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                names.add(node.name)
        elif isinstance(node, ast.comprehension):
            _collect_targets(node.target, names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names |= _arg_names(node.args)  # 内层函数参数也属本作用域链
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    names.add(a.asname or a.name)
    return names


def undefined_names(source: str) -> set:
    """返回 source 中所有函数体内无法解析的加载名字（可能为空的 set）。"""
    tree = ast.parse(source)
    available_top = set(dir(builtins)) | _module_bindings(tree)
    undefined: set = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            available = available_top | _function_bindings(node)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    if sub.id not in available:
                        undefined.add(sub.id)
    return undefined


def test_undefined_name_checker_detects_missing_import():
    """检查器自身有效性：漏 import 的源码必须报出缺失名字。"""
    bad = (
        "from novelbase.models.novel import SearchResult\n"
        "\n"
        "def parse_search_result(html):\n"
        "    soup = BeautifulSoup(html, 'lxml')\n"
        "    return SearchResult(title='x')\n"
    )
    assert "BeautifulSoup" in undefined_names(bad)


@pytest.mark.parametrize("dirname", sorted(EXPECTED_MODE))
def test_capability_files_have_no_undefined_names(dirname):
    """该书源的 4 个能力文件函数体不得引用未定义名（捕获内联漏 import 回归）。"""
    problems = {}
    for cap in CAPABILITIES:
        path = SOURCES / dirname / f"{cap}.py"
        if not path.is_file():
            continue
        undef = undefined_names(path.read_text(encoding="utf-8"))
        if undef:
            problems[cap] = sorted(undef)
    assert not problems, (
        f"{dirname} 的能力文件函数体存在未定义名（疑似漏 import）: {problems}"
    )

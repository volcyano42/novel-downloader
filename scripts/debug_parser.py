#!/usr/bin/env python3
"""HTML 解析器调试工具 — 加载 HTML 文件，打印结构，测试 CSS 选择器。

用法:
    # 打印 HTML 骨架（标签树）
    python scripts/debug_parser.py --html qimao_html/novel_success

    # 测试 CSS 选择器
    python scripts/debug_parser.py --html qimao_html/novel_success --selector ".book-information .title .txt"

    # 测试多个选择器
    python scripts/debug_parser.py --html qimao_html/search_result \
        --selector "ul.search-book-list li" \
        --selector ".s-tit a"

    # 打印匹配元素的文本内容
    python scripts/debug_parser.py --html qimao_html/novel_success \
        --selector ".tags-wrap .qm-tag" --text

    # 打印匹配元素的属性
    python scripts/debug_parser.py --html qimao_html/novel_success \
        --selector ".wrap-pic img" --attr src
"""

import argparse
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def print_skeleton(html: str, max_depth: int = 4):
    """打印 HTML 骨架（标签树）。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    def _walk(el, depth=0, prefix=""):
        if depth > max_depth:
            return
        if not hasattr(el, "name") or el.name is None:
            return

        # 构建标签描述
        cls = el.get("class")
        id_ = el.get("id")
        tag_str = el.name
        if id_:
            tag_str += f"#{id_}"
        if cls:
            tag_str += "." + ".".join(cls)

        # 统计子元素
        children = [c for c in (el.children if hasattr(el, "children") else [])
                    if hasattr(c, "name") and c.name is not None]
        child_info = f"  ({len(children)} children)" if children else ""

        indent = "  " * depth
        print(f"{indent}{prefix}{tag_str}{child_info}")

        for child in children:
            _walk(child, depth + 1, "")

    print(f"\nHTML 骨架 (max_depth={max_depth}):\n")
    _walk(soup)
    print()


def test_selector(html: str, selector: str, show_text: bool, show_attr: str):
    """测试 CSS 选择器并打印结果。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    elements = soup.select(selector)

    print(f"\n选择器: {selector}")
    print(f"匹配: {len(elements)} 个元素\n")

    for i, el in enumerate(elements[:20]):
        print(f"  [{i}] <{el.name}>", end="")
        cls = el.get("class")
        if cls:
            print(f" .{' '.join(cls)}", end="")

        if show_attr:
            val = el.get(show_attr, "")
            print(f"\n      {show_attr}={val!r}", end="")

        if show_text:
            text = el.get_text(strip=True)[:200]
            if text:
                print(f"\n      text={text!r}", end="")
        print()

    if len(elements) > 20:
        print(f"  ... 还有 {len(elements) - 20} 个未显示")


def main():
    p = argparse.ArgumentParser(
        description="HTML 解析器调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--html", required=True, help="HTML 文件路径")
    p.add_argument("--selector", "-s", action="append", default=[],
                   help="CSS 选择器（可多次指定）")
    p.add_argument("--text", action="store_true", help="显示匹配元素的文本内容")
    p.add_argument("--attr", default="", help="显示匹配元素的属性值（如 src、href）")
    p.add_argument("--skeleton", action="store_true", default=True,
                   help="打印 HTML 骨架（默认开启）")
    p.add_argument("--no-skeleton", action="store_true", help="不打印 HTML 骨架")
    args = p.parse_args()

    path = Path(args.html)
    if not path.exists():
        print(f"✗ 文件不存在: {args.html}")
        sys.exit(1)

    html = path.read_text(encoding="utf-8")
    print(f"文件: {args.html}  ({len(html):,} bytes)")

    if not args.no_skeleton:
        print_skeleton(html)

    for selector in args.selector:
        test_selector(html, selector, args.text, args.attr)

    if not args.selector and args.no_skeleton:
        p.print_help()


if __name__ == "__main__":
    main()

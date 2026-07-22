#!/usr/bin/env python3
"""Fetcher 调试工具 — 本地 HTML 文件解析 / 实时请求测试。

用法:
    # 本地 HTML 文件解析
    python scripts/debug_fetcher.py --platform qimao --action search --html qimao_html/search_result
    python scripts/debug_fetcher.py --platform qimao --action novel --html qimao_html/novel_success
    python scripts/debug_fetcher.py --platform qimao --action chapters --html qimao_html/chapter_list
    python scripts/debug_fetcher.py --platform qimao --action content --html qimao_html/chapter_success --chapter-id "195958-499610"

    # 实时请求
    python scripts/debug_fetcher.py --platform qimao --action search --live "盖世神医"
    python scripts/debug_fetcher.py --platform qimao --action novel --live 195958
    python scripts/debug_fetcher.py --platform qimao --action chapters --live 195958
    python scripts/debug_fetcher.py --platform qimao --action content --live "195958-499610"

    # 指定引擎
    python scripts/debug_fetcher.py --platform qimao --action novel --live 195958 --engine browser
"""

import argparse
import importlib
import json
import sys
import traceback
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from novelbase.models.novel import Chapter
from novelbase.utils.registry import register_fetcher

def _get_fetcher_class(platform: str) -> type:
    fetchers = register_fetcher()
    cls = fetchers.get(platform)
    if cls is None:
        print(f"✗ 未知平台: {platform}")
        print(f"  可用: {list(fetchers.keys())}")
        sys.exit(1)
    return cls

def _get_parser_class(platform: str):
    """尝试导入 {Platform}HTMLParser。"""
    module_name = f"novelbase.fetchers.{platform}"
    class_name = f"{platform.capitalize()}HTMLParser"
    try:
        mod = importlib.import_module(module_name)
        return getattr(mod, class_name)
    except (ImportError, AttributeError) as e:
        print(f"✗ 无法加载 {class_name}: {e}")
        sys.exit(1)

def _get_standardize_id(platform: str):
    """尝试导入 standardize_id 函数。"""
    module_name = f"novelbase.fetchers.{platform}"
    try:
        mod = importlib.import_module(module_name)
        return getattr(mod, "standardize_id", None)
    except ImportError:
        return None

def cmd_search_html(parser_cls, html_path: str):
    html = Path(html_path).read_text(encoding="utf-8")
    results = parser_cls.parse_search_result(html)
    print(f"\n搜索结果: {len(results)} 条\n")
    for i, r in enumerate(results, 1):
        desc = (r.description or "")[:100]
        print(f"  [{i}] {r.title}")
        print(f"      作者: {r.author}")
        print(f"      URL:  {r.url}")
        print(f"      简介: {desc}")
        print()

def cmd_novel_html(parser_cls, html_path: str, url: str = ""):
    html = Path(html_path).read_text(encoding="utf-8")
    novel = parser_cls.parse_novel_info(html, url=url)
    print(f"\n小说信息:")
    print(f"  书名: {novel.title}")
    print(f"  作者: {novel.author}")
    print(f"  URL:  {novel.url}")
    print(f"  ID:   {novel.id}")
    print(f"  章节: {len(novel.chapters)}/{novel.serial} 章")
    print(f"  字数: {novel.count}")
    print(f"  标签: {novel.tags}")
    print(f"  简介: {novel.description}")
    if novel.cover:
        print(f"  封面: {novel.cover.image_format or '未知'} "
              f"({len(novel.cover.raw_data)} bytes)")

def cmd_chapters_html(parser_cls, html_path: str, novel_id: str = ""):
    html = Path(html_path).read_text(encoding="utf-8")
    chapters = parser_cls.parse_chapter_list(html, novel_id=novel_id)
    print(f"\n章节目录: {len(chapters)} 章\n")
    for ch in list(chapters)[:10]:
        print(f"  [{ch.order:4d}] {ch.title}")
        print(f"           URL: {ch.url}")
        print(f"           ID:  {ch.id}")
    if len(chapters) > 10:
        print(f"  ... (共 {len(chapters)} 章，仅显示前 10)")
        # 显示最后 3 章
        print(f"\n  末尾:")
        for ch in list(chapters)[-3:]:
            print(f"  [{ch.order:4d}] {ch.title}")

def cmd_content_html(parser_cls, html_path: str, chapter_id: str = "",
                     chapter_title: str = "", chapter_url: str = ""):
    html = Path(html_path).read_text(encoding="utf-8")
    ch = Chapter(
        id=chapter_id or "unknown",
        url=chapter_url or "unknown",
        novel_id="unknown",
        title=chapter_title or "unknown",
        order=1,
    )
    result = parser_cls.parse_chapter_content(html, ch)
    print(f"\n章节正文:")
    print(f"  标题: {result.title}")
    print(f"  字数: {result.count}")
    # is_complete removed
    content = result.content or ""
    if len(content) > 300:
        print(f"  正文预览 (前 300 字):")
        print(f"  {content[:300]}...")
    else:
        print(f"  正文:")
        print(f"  {content}")

# ═══════════════════════════════════════════════════════════════════
# 实时请求
# ═══════════════════════════════════════════════════════════════════

def _build_engine(platform: str, engine_mode: str):
    from main import load_main_config, load_site_config, build_options
    from novelbase import create_engine

    cfg = load_main_config()
    cfg["mode"] = engine_mode
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)
    return create_engine(options)

def cmd_live_search(platform: str, engine_mode: str, query: str):
    engine = _build_engine(platform, engine_mode)
    try:
        from main import load_main_config, load_site_config, build_options
        from novelbase.core.downloader import search
        results = search(platform, query, engine)
        if not results:
            print("未找到任何结果")
            return
        print(f"\n搜索结果: {len(results)} 条\n")
        for i, r in enumerate(results, 1):
            desc = (r.description or "")[:100]
            print(f"  [{i}] {r.title}")
            print(f"      作者: {r.author}")
            print(f"      URL:  {r.url}")
            print(f"      简介: {desc}")
            print()
    finally:
        engine.close()

def cmd_live_novel(platform: str, engine_mode: str, novel_id: str):
    s_id = _get_standardize_id(platform)
    if s_id:
        novel_id = s_id(novel_id)

    engine = _build_engine(platform, engine_mode)
    try:
        fetcher_cls = _get_fetcher_class(platform)
        fetcher = fetcher_cls()
        novel = fetcher.fetch_novel_info(novel_id, engine)
        print(f"\n小说信息:")
        print(f"  书名: {novel.title}")
        print(f"  作者: {novel.author}")
        print(f"  URL:  {novel.url}")
        print(f"  ID:   {novel.id}")
        print(f"  章节: {len(novel.chapters)}/{novel.serial} 章")
        print(f"  字数: {novel.count}")
        print(f"  标签: {novel.tags}")
        print(f"  简介: {novel.description}")
        if novel.cover:
            print(f"  封面: {novel.cover.image_format or '未知'} "
                  f"({len(novel.cover.raw_data)} bytes)")
    finally:
        engine.close()

def cmd_live_chapters(platform: str, engine_mode: str, novel_id: str):
    s_id = _get_standardize_id(platform)
    if s_id:
        novel_id = s_id(novel_id)

    engine = _build_engine(platform, engine_mode)
    try:
        fetcher_cls = _get_fetcher_class(platform)
        fetcher = fetcher_cls()
        chapters = fetcher.fetch_chapter_list(novel_id, engine)
        print(f"\n章节目录: {len(chapters)} 章\n")
        for ch in list(chapters)[:10]:
            print(f"  [{ch.order:4d}] {ch.title}")
            print(f"           URL: {ch.url}")
            print(f"           ID:  {ch.id}")
        if len(chapters) > 10:
            print(f"  ... (共 {len(chapters)} 章，仅显示前 10)")
            for ch in list(chapters)[-3:]:
                print(f"  [{ch.order:4d}] {ch.title}")
    finally:
        engine.close()

def cmd_live_content(platform: str, engine_mode: str, chapter_id: str):
    s_id = _get_standardize_id(platform)
    if s_id:
        chapter_id = s_id(chapter_id)

    engine = _build_engine(platform, engine_mode)
    try:
        fetcher_cls = _get_fetcher_class(platform)
        fetcher = fetcher_cls()

        # 构造一个临时 Chapter 用于传递
        if "-" in chapter_id:
            book_id, ch_id = chapter_id.split("-", 1)
            url = f"https://www.{'qimao' if platform == 'qimao' else 'fanqienovel' if platform == 'fanqie' else 'qidian'}.com/{'shuku' if platform == 'qimao' else 'page' if platform == 'fanqie' else 'book'}/{book_id}/"
            chapter_url = url
        else:
            chapter_url = chapter_id

        ch = Chapter(id=chapter_id, url=chapter_url, novel_id="", title="", order=1)
        result = fetcher.fetch_chapter_content(ch, engine)
        ch = result[0]
        print(f"\n章节正文:")
        print(f"  标题: {ch.title}")
        print(f"  字数: {ch.count}")
        # is_complete removed
        content = ch.content or ""
        if len(content) > 300:
            print(f"  正文预览 (前 300 字):")
            print(f"  {content[:300]}...")
        else:
            print(f"  正文:")
            print(f"  {content}")
    finally:
        engine.close()

# ═══════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        description="Fetcher 调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--platform", "-p", required=True, help="平台 (fanqie/qidian/qimao)")
    p.add_argument("--action", "-a", required=True,
                   choices=["search", "novel", "chapters", "content"],
                   help="调试动作")
    p.add_argument("--html", help="本地 HTML 文件路径（离线模式）")
    p.add_argument("--live", help="实时请求参数（搜索关键词 / novel_id / chapter_id）")
    p.add_argument("--engine", "-e", default="requests", help="引擎 (requests/browser/api)")
    p.add_argument("--url", default="", help="小说 URL（配合 novel/chapters 动作）")
    p.add_argument("--chapter-id", default="", help="章节 ID（配合 content 动作）")
    p.add_argument("--chapter-title", default="", help="章节标题（配合 content 动作）")
    args = p.parse_args()

    parser_cls = _get_parser_class(args.platform)

    if args.html:
        # 离线模式：解析本地 HTML
        if not Path(args.html).exists():
            print(f"✗ 文件不存在: {args.html}")
            sys.exit(1)

        handlers = {
            "search":   lambda: cmd_search_html(parser_cls, args.html),
            "novel":    lambda: cmd_novel_html(parser_cls, args.html, args.url),
            "chapters": lambda: cmd_chapters_html(parser_cls, args.html, args.url),
            "content":  lambda: cmd_content_html(parser_cls, args.html,
                                                  args.chapter_id, args.chapter_title),
        }
        handlers[args.action]()

    elif args.live:
        # 在线模式：实时请求
        handlers = {
            "search":   lambda: cmd_live_search(args.platform, args.engine, args.live),
            "novel":    lambda: cmd_live_novel(args.platform, args.engine, args.live),
            "chapters": lambda: cmd_live_chapters(args.platform, args.engine, args.live),
            "content":  lambda: cmd_live_content(args.platform, args.engine, args.live),
        }
        handlers[args.action]()

    else:
        print("请指定 --html 或 --live")

if __name__ == "__main__":
    main()

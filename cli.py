#!/usr/bin/env python3
"""非交互命令行入口。

用法:
    python cli.py search --platform qimao "关键词"
    python cli.py download --platform qimao --engine requests --url "https://..."
    python cli.py update --platform fanqie --group default
    python cli.py export --group default --format epub
    python cli.py info --url "https://www.qimao.com/shuku/195958/"
"""

import argparse
import os
import sys
from pathlib import Path

# ── 确保项目根在 sys.path ──────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ── 复用 main.py 的配置加载 ─────────────────────────────────────
from main import (
    APP_DATA, CONFIG_DIR,
    load_main_config, load_site_config, load_format_configs, load_groups,
    build_options, add_novel_to_group, ensure_novel_in_group,
)
from novelbase import create_engine, fetch_meta, get_fetcher_for_url
from novelbase.utils.logger import get_logger

_log = get_logger("novelbase.cli")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="novelbase — 小说下载器命令行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ── search ──
    sp = sub.add_parser("search", help="搜索小说")
    sp.add_argument("query", help="搜索关键词")
    sp.add_argument("--platform", "-p", default="fanqie", help="平台 (fanqie/qidian/qimao)")
    sp.add_argument("--engine", "-e", default="requests", help="引擎 (requests/browser/api)")
    sp.add_argument("--page", type=int, default=1, help="页码")

    # ── download ──
    dp = sub.add_parser("download", help="下载小说")
    dp.add_argument("--platform", "-p", default="fanqie", help="平台")
    dp.add_argument("--engine", "-e", default="requests", help="引擎")
    dp.add_argument("--url", "-u", required=True, help="小说页面 URL")
    dp.add_argument("--group", "-g", default="default", help="分组名")
    dp.add_argument("--workers", "-w", type=int, default=3, help="下载线程数")

    # ── update ──
    up = sub.add_parser("update", help="更新已下载小说")
    up.add_argument("--platform", "-p", default="fanqie", help="平台")
    up.add_argument("--engine", "-e", default="requests", help="引擎")
    up.add_argument("--group", "-g", default="default", help="分组名")
    up.add_argument("--workers", "-w", type=int, default=3, help="下载线程数")

    # ── export ──
    ep = sub.add_parser("export", help="重新导出已下载小说")
    ep.add_argument("--group", "-g", default="default", help="分组名")
    ep.add_argument("--format", "-f", default="epub", help="导出格式 (epub/txt/img)")

    # ── info ──
    ip = sub.add_parser("info", help="查看小说信息")
    ip.add_argument("--url", "-u", required=True, help="小说页面 URL")
    ip.add_argument("--platform", "-p", default="fanqie", help="平台")
    ip.add_argument("--engine", "-e", default="requests", help="引擎")

    return p.parse_args()


def _get_engine(platform: str, engine_mode: str):
    """根据平台和引擎模式创建 engine。"""
    cfg = load_main_config()
    cfg["mode"] = engine_mode
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)

    # 注册导出格式 — 单格式模式
    format_configs = load_format_configs()
    from novelbase.utils.registry import register_export_options
    _opt_cls_map = register_export_options()
    group = cfg.get("group", "default")
    active_format = next(iter(format_configs), None)  # 取第一个配置的格式
    fmt_cfg = format_configs.get(active_format, {}) if active_format else {}
    opt_cls = _opt_cls_map.get(active_format) if active_format else None
    if opt_cls and fmt_cfg:
        raw_path = fmt_cfg.get("output_path", "").replace("{group}", group)
        extra = {k: fmt_cfg[k] for k in (
            "encoding", "file_name_template", "css_style", "include_toc",
        ) if k in fmt_cfg}
        opt = opt_cls(output_path=raw_path, **extra)
        options.set_export(opt)

    return create_engine(options), format_configs


def cmd_search(args):
    engine, format_configs = _get_engine(args.platform, args.engine)
    try:
        from novelbase.core.downloader import search
        results = search(args.platform, args.query, engine, page=args.page)
        if not results:
            print("未找到任何结果")
            return
        print(f"\n找到 {len(results)} 个结果：\n")
        for i, r in enumerate(results, 1):
            desc = (r.description or "")[:80]
            print(f"  {i:2d}. {r.title}")
            print(f"      作者: {r.author}")
            print(f"      URL:  {r.url}")
            if desc:
                print(f"      简介: {desc}")
            print()
    finally:
        engine.close()


def cmd_download(args):
    engine, format_configs = _get_engine(args.platform, args.engine)
    try:
        from main import do_download
        do_download(engine, engine, args.url, args.group, format_configs,
                    max_workers=args.workers)
    finally:
        engine.close()


def cmd_update(args):
    engine, format_configs = _get_engine(args.platform, args.engine)
    try:
        from main import do_update
        do_update(engine, engine, args.group, format_configs, max_workers=args.workers)
    finally:
        engine.close()


def cmd_export(args):
    cfg = load_main_config()
    fmt_cfg = load_format_configs()
    if args.format not in fmt_cfg:
        print(f"格式 '{args.format}' 未在 app_data/config/formats/ 中配置")
        sys.exit(1)

    engine, _ = _get_engine("fanqie", "requests")  # 导出不需要真实引擎
    try:
        from main import do_export_menu
        do_export_menu(args.group, fmt_cfg, engine)
    finally:
        engine.close()


def cmd_info(args):
    engine, _ = _get_engine(args.platform, args.engine)
    try:
        print(f"正在获取: {args.url}")
        novel = fetch_meta(args.url, engine)
        print(f"\n  书名：{novel.title}")
        print(f"  作者：{novel.author}")
        print(f"  URL： {novel.url}")
        print(f"  ID：  {novel.id}")
        print(f"  章节：{novel.serial} 章")
        print(f"  字数：{novel.count or '未知'}")
        tags_str = "、".join(novel.tags) if novel.tags else ""
        print(f"  标签：{tags_str}")
        print(f"  简介：{novel.description}")
        if novel.cover and novel.cover.image_format:
            print(f"  封面：{novel.cover.image_format} ({len(novel.cover.raw_data)} bytes)")
    finally:
        engine.close()


def main():
    args = _parse_args()
    dispatch = {
        "search":   cmd_search,
        "download": cmd_download,
        "update":   cmd_update,
        "export":   cmd_export,
        "info":     cmd_info,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

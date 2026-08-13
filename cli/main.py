#!/usr/bin/env python3
"""非交互命令行入口。

用法:
    python cli.py search --platform qimao "关键词"
    python cli.py download --mode requests --url "https://..."
    python cli.py update --platform fanqie --group default
    python cli.py export --group default --format epub
    python cli.py info --url "https://www.qimao.com/shuku/195958/"
"""

import argparse
import os
import sys
from pathlib import Path

# ── 确保项目根在 sys.path ──────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ── 复用 app.config 的配置加载 ─────────────────────────────────
from cli.config import (
    load_main_config, load_site_config, load_format_configs, load_groups,
    build_options, add_novel_to_group, ensure_novel_in_group,
)
from novelbase import create_engine, resolve_meta, get_source
from novelbase.utils.logger import get_logger

_log = get_logger("novelbase.cli")


def _platform_from_url(url: str) -> str:
    """从 URL 推断平台（数据驱动）。"""
    from novelbase.source import platform_from_url
    plat = platform_from_url(url)
    if plat:
        return plat
    raise ValueError(f"未识别书源 URL: {url}")


def _resolve_platform(args) -> str:
    """解析平台：优先用 --platform，否则从 URL 推断。"""
    if getattr(args, "platform", None):
        return args.platform
    url = getattr(args, "url", "")
    return _platform_from_url(url) if url else "fanqie"


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
    sp.add_argument("--mode", "-m", default="requests", help="模式 (requests/browser/api)")
    sp.add_argument("--page", type=int, default=1, help="页码")

    # ── download ──
    dp = sub.add_parser("download", help="下载小说")
    dp.add_argument("--platform", "-p", default=None, help="平台（可从 URL 自动推断）")
    dp.add_argument("--mode", "-m", default="requests", help="模式")
    dp.add_argument("--url", "-u", required=True, help="小说页面 URL")
    dp.add_argument("--group", "-g", default="default", help="分组名")
    dp.add_argument("--workers", "-w", type=int, default=3, help="下载线程数")

    # ── update ──
    up = sub.add_parser("update", help="更新已下载小说")
    up.add_argument("--platform", "-p", default="fanqie", help="平台")
    up.add_argument("--mode", "-m", default="requests", help="模式")
    up.add_argument("--group", "-g", default="default", help="分组名")
    up.add_argument("--workers", "-w", type=int, default=3, help="下载线程数")

    # ── export ──
    ep = sub.add_parser("export", help="重新导出已下载小说")
    ep.add_argument("--group", "-g", default="default", help="分组名")
    ep.add_argument("--format", "-f", default="epub", help="导出格式 (epub/txt/img)")

    # ── delete ──
    dp2 = sub.add_parser("delete", help="删除已下载小说")
    dp2.add_argument("--id", required=True, help="小说 ID（如 fanqie_7123456789012345678）")

    # ── novel ──
    np = sub.add_parser("novel", help="已下载小说管理")
    np_sub = np.add_subparsers(dest="novel_command", required=True)
    np_list = np_sub.add_parser("list", help="列出已下载小说")
    np_list.add_argument("--group", "-g", default=None, help="按分组过滤")

    # ── source（sources 为别名）──
    sp = sub.add_parser("source", aliases=["sources"], help="书源管理")
    sp_sub = sp.add_subparsers(dest="source_command", required=True)
    sp_list = sp_sub.add_parser("list", help="列出可用书源")
    sp_list.add_argument("--json", action="store_true", help="JSON 输出")

    # ── info ──
    ip = sub.add_parser("info", help="查看小说信息")
    ip.add_argument("--url", "-u", required=True, help="小说页面 URL")
    ip.add_argument("--platform", "-p", default=None, help="平台（可从 URL 自动推断）")
    ip.add_argument("--mode", "-m", default="requests", help="模式")

    # ── dev ──
    dv = sub.add_parser("dev", help="开发工具")
    dv_sub = dv.add_subparsers(dest="dev_command")

    ns = dv_sub.add_parser("new-source", help="创建新书源脚手架")
    ns.add_argument("--name", required=True, help="书源名称")
    ns.add_argument("--modes", default="requests", help="模式列表，逗号分隔 (requests,browser,api)")

    ls = dv_sub.add_parser("list-sources", help="列出所有可用书源")
    ls.add_argument("--json", action="store_true", help="仅列出 JSON 规则源")

    return p.parse_args()


def _get_engine(platform: str, mode: str):
    """根据平台和引擎模式创建 engine。"""
    cfg = load_main_config()
    cfg["mode"] = mode
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)

    # 注册导出格式 — 单格式模式
    format_configs = load_format_configs()
    from novelbase.exporter import register_export_options
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
    engine, format_configs = _get_engine(args.platform, args.mode)
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
    engine, format_configs = _get_engine(_resolve_platform(args), args.mode)
    try:
        from cli.core import _do_download_inner
        _do_download_inner(engine, args.url, args.group, format_configs,
                           max_workers=args.workers)
    finally:
        engine.close()


def cmd_update(args):
    engine, format_configs = _get_engine(args.platform, args.mode)
    try:
        from cli.core import do_update
        do_update(format_configs, max_workers=args.workers)
    finally:
        engine.close()


def cmd_export(args):
    fmt_cfg = load_format_configs()
    if args.format not in fmt_cfg:
        print(f"格式 '{args.format}' 未在 app_data/config/formats/ 中配置")
        sys.exit(1)

    from cli.config import load_groups
    from cli.core import _get_storage
    from novelbase import export
    from novelbase.exporter import register_export_options

    storage = _get_storage()
    novels = list(storage.iter_metas())
    if not novels:
        print("书架上没有小说")
        return

    groups = load_groups()
    group_ids = set(groups.get(args.group, {}).keys()) if args.group != "default" else None
    targets = [n for n in novels if args.group == "default" or (group_ids and n.id in group_ids)]
    if not targets:
        print(f"分组 '{args.group}' 中没有小说")
        return

    opt_cls = register_export_options().get(args.format)
    if opt_cls is None:
        print(f"无法获取导出选项: {args.format}")
        return

    for novel in targets:
        opts = opt_cls(**fmt_cfg.get(args.format, {}))
        print(f"导出 '{novel.title}' → {args.format} ...")
        try:
            result = export(novel, opts, args.format)
            print(f"  完成: {result}")
        except Exception as e:
            print(f"  导出失败: {e}")


def cmd_info(args):
    engine, _ = _get_engine(_resolve_platform(args), args.mode)
    try:
        print(f"正在获取: {args.url}")
        novel = resolve_meta(args.url, engine)
        print(f"\n  书名：{novel.title}")
        print(f"  作者：{novel.author}")
        print(f"  URL： {novel.url}")
        print(f"  ID：  {novel.id}")
        print(f"  章节：{len(novel.chapters)}/{novel.serial} 章")
        print(f"  字数：{novel.count or '未知'}")
        tags_str = "、".join(novel.tags) if novel.tags else ""
        print(f"  标签：{tags_str}")
        print(f"  简介：{novel.description}")
        if novel.cover and novel.cover.image_format:
            print(f"  封面：{novel.cover.image_format} ({len(novel.cover.raw_data)} bytes)")
    finally:
        engine.close()


def cmd_delete(args):
    """删除已下载小说（含章节/封面），并从全部分组移除。"""
    from cli.config import load_groups, save_groups
    from cli.core import _get_storage

    storage = _get_storage()
    novel_id = args.id
    novel = storage.load_meta(novel_id)
    if novel is None:
        print(f"小说不存在: {novel_id}")
        sys.exit(1)

    storage.delete_novel(novel_id)

    groups = load_groups()
    removed = False
    for g, novels in groups.items():
        if isinstance(novels, dict) and novel_id in novels:
            novels.pop(novel_id, None)
            removed = True
    save_groups(groups)

    print(f"已删除《{novel.title}》 ({novel_id})" + ("，并移出分组" if removed else ""))


def cmd_novel(args):
    """已下载小说管理。"""
    from cli.config import load_groups
    from cli.core import _get_storage

    if args.novel_command != "list":
        return

    storage = _get_storage()
    novels = list(storage.iter_metas())
    if not novels:
        print("书架上没有小说")
        return

    groups = load_groups()
    if args.group:
        gids = set(groups.get(args.group, {}).keys())
        novels = [n for n in novels if n.id in gids]
        if not novels:
            print(f"分组 '{args.group}' 中没有小说")
            return

    print(f"共 {len(novels)} 本小说：")
    for i, n in enumerate(novels, 1):
        g = next((g for g, ids in groups.items() if n.id in ids), "未分组")
        print(f"  {i:2d}. {n.title}  — {n.author}  [{n.id}]  ({g})")


def cmd_source(args):
    """书源管理。"""
    from novelbase.source import register_source

    if args.source_command != "list":
        return

    sources = register_source()
    if args.json:
        import json
        payload = {
            name: {
                "name": meta.get("name"),
                "show_name": meta.get("show_name", name),
                "hosts": list(meta.get("hosts", ())),
                "id_pattern": getattr(meta.get("id_pattern"), "pattern", None),
                "origin_id_pattern": getattr(meta.get("origin_id_pattern"), "pattern", None),
            }
            for name, meta in sources.items()
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"可用书源 ({len(sources)}):")
    for name, meta in sources.items():
        show = meta.get("show_name", name)
        hosts = ", ".join(meta.get("hosts", ()))
        print(f"  - {name} ({show})   hosts: {hosts}")


def cmd_dev(args):
    """开发工具。"""
    if args.dev_command == "list-sources":
        from novelbase.source import list_sources as _ls_py

        if args.json:
            print("JSON 规则源已移除")
            return

        py_sources = _ls_py()
        print(f"Python 源 ({len(py_sources)}):")
        for s in py_sources:
            print(f"  - {s}")

    elif args.dev_command == "new-source":
        _scaffold_source(args.name, args.modes.split(","))


def _scaffold_source(name: str, modes: list[str]):
    """生成新书源脚手架。"""
    source_dir = Path(__file__).parent.parent / "novelbase" / "sources" / name
    source_dir.mkdir(parents=True, exist_ok=True)

    (source_dir / "__init__.py").write_text(
        f'NAME = "{name}"\nBASE_URLS = ["example.com"]\n', encoding="utf-8")
    (source_dir / "_common.py").write_text(
        '"""共享解析函数。"""\n', encoding="utf-8")

    for mode in modes:
        mode = mode.strip()
        mode_dir = source_dir / mode
        mode_dir.mkdir(exist_ok=True)
        (mode_dir / "__init__.py").touch()

        for fn in ("search", "novel_info", "chapter_list", "chapter_content"):
            (mode_dir / f"{fn}.py").write_text(
                f'"""TODO: implement {fn} for {name}/{mode}."""\n'
                f'from novelbase.core.exceptions import FeatureNotSupportedError\n\n'
                f'def {fn}(*args, **kwargs):\n'
                f'    raise FeatureNotSupportedError("TODO")\n',
                encoding="utf-8")

    print(f"书源脚手架已创建: novelbase/sources/{name}/")
    for mode in modes:
        print(f"  {mode}/  search.py, novel_info.py, chapter_list.py, chapter_content.py")


def main():
    args = _parse_args()
    dispatch = {
        "search":   cmd_search,
        "download": cmd_download,
        "update":   cmd_update,
        "export":   cmd_export,
        "delete":   cmd_delete,
        "novel":    cmd_novel,
        "source":   cmd_source,
        "sources":  cmd_source,
        "info":     cmd_info,
        "dev":      cmd_dev,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

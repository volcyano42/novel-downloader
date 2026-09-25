#!/usr/bin/env python3
"""非交互命令行入口。

用法:
    python cli.py search "关键词"                          # 并发全部启用书源
    python cli.py search --source fanqie-requests-default "关键词"
    python cli.py download --source fanqie-requests-default --url "https://..."
    python cli.py update
    python cli.py export --group default --format epub
    python cli.py info --source fanqie-requests-default --url "https://..."
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# ── 确保项目根在 sys.path ──────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ── 复用 app.config 的配置加载 ─────────────────────────────────
from cli.config import load_main_config, load_format_configs
from novelbase import resolve_meta
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
    sp.add_argument("--source", "-s", default="",
                    help="书源名 source_name；省略 = 并发全部启用书源")
    sp.add_argument("--page", type=int, default=1, help="页码")

    # ── download ──
    dp = sub.add_parser("download", help="下载小说")
    dp.add_argument("--source", "-s", required=True, help="书源名 source_name")
    dp.add_argument("--url", "-u", required=True, help="小说页面 URL")
    dp.add_argument("--group", "-g", default="default", help="分组名")
    dp.add_argument("--workers", "-w", type=int, default=3, help="下载线程数")

    # ── update ──
    up = sub.add_parser("update", help="更新已下载小说")
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

    # ── sources ──
    sp = sub.add_parser("sources", help="书源管理")
    sp_sub = sp.add_subparsers(dest="source_command", required=True)
    sp_list = sp_sub.add_parser("list", help="列出可用书源")
    sp_list.add_argument("--json", action="store_true", help="JSON 输出")

    # ── info ──
    ip = sub.add_parser("info", help="查看小说信息")
    ip.add_argument("--source", "-s", required=True, help="书源名 source_name")
    ip.add_argument("--url", "-u", required=True, help="小说页面 URL")

    # ── dev ──
    dv = sub.add_parser("dev", help="开发工具")
    dv_sub = dv.add_subparsers(dest="dev_command")

    ns = dv_sub.add_parser("new-source", help="创建新书源脚手架")
    ns.add_argument("--name", required=True, help="书源名 source_name（如 demo-requests-default）")
    ns.add_argument("--modes", default="requests", help="模式，逗号分隔 (requests,browser,api)")
    ns.add_argument("--no-config", action="store_true",
                    help="不生成默认用户配置 app_data/config/sites/{source_name}.yaml")

    ls = dv_sub.add_parser("list-sources", help="列出所有可用书源")
    ls.add_argument("--json", action="store_true", help="仅列出 JSON 规则源")

    return p.parse_args()


def _apply_export_options(options) -> dict:
    """把当前生效的导出格式配置装配到 Options（单格式模式），返回 format_configs 供复用。"""
    format_configs = load_format_configs()
    from novelbase.exporter import register_export_options
    _opt_cls_map = register_export_options()
    group = load_main_config().get("group", "default")
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
    return format_configs


def cmd_search(args):
    from novelbase.core.downloader import search
    from cli.core import _make_engines
    from shared.config import enabled_source_names

    sources = [args.source] if args.source else enabled_source_names()
    if not sources:
        print("没有启用的书源")
        return

    async def _search_one(name: str):
        # 每个源各用自己的引擎（杜绝「同 mode 源共用首个源引擎」）。
        engines = _make_engines(name)
        try:
            return await search([name], args.query, engines, page=args.page)
        except Exception as e:      # 某源失败静默跳过：不影响其它源
            print(f"  [{name}] 搜索失败: {e}")
            return ()
        finally:
            for eng in engines.cache.values():
                try:
                    eng.close()
                except Exception:
                    pass

    async def _run():
        groups = await asyncio.gather(*(_search_one(n) for n in sources))
        return [r for group in groups for r in group]

    results = asyncio.run(_run())
    if not results:
        print("未找到任何结果")
        return
    print(f"\n找到 {len(results)} 个结果：\n")
    for i, r in enumerate(results, 1):
        desc = (r.description or "")[:80]
        print(f"  {i:2d}. {r.title}")
        print(f"      作者: {r.author}")
        print(f"      书源: {getattr(r, 'source_name', '')}")
        print(f"      URL:  {r.url}")
        if desc:
            print(f"      简介: {desc}")
        print()


def cmd_download(args):
    source_name = args.source
    from cli.core import _do_download_inner, _make_engines

    format_configs = load_format_configs()
    engines = _make_engines(source_name, options_hook=_apply_export_options)
    try:
        asyncio.run(_do_download_inner(source_name, args.url, args.group, format_configs,
                                       max_workers=args.workers, engines=engines))
    finally:
        for eng in engines.cache.values():
            try:
                eng.close()
            except Exception:
                pass


def cmd_update(args):
    format_configs = load_format_configs()
    from cli.core import do_update
    asyncio.run(do_update(format_configs, max_workers=args.workers))


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
    source_name = args.source
    from cli.core import _make_engines

    engines = _make_engines(source_name, options_hook=_apply_export_options)
    try:
        print(f"正在获取: {args.url}")
        novel = asyncio.run(resolve_meta(args.url, source_name, engines))
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
        for eng in engines.cache.values():
            try:
                eng.close()
            except Exception:
                pass


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
    from novelbase.source import list_sources, capabilities

    if args.source_command != "list":
        return

    names = list_sources()
    if args.json:
        import json
        payload = {
            name: {
                "name": name,
                "show_name": name,
                "capabilities": capabilities(name),
            }
            for name in names
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"可用书源 ({len(names)}):")
    for name in names:
        caps = capabilities(name)
        cap_str = ", ".join(f"{c}:{m}" for c, m in caps.items()) or "无"
        print(f"  - {name}   capabilities: {cap_str}")


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
        _scaffold_source(args.name, args.modes.split(","),
                         write_config=not args.no_config)


_SOURCES_ROOT = Path(__file__).parent.parent / "novelbase" / "sources"

# 脚手架函数清单与文件模板。
# 必须保持 async def：novelbase/core/downloader.py 以 await fn(...) 调用书源函数。
_SCAFFOLD_FUNCTIONS = ("search", "novel_info", "chapter_list", "chapter_content")

_FUNC_TEMPLATE = (
    '"""TODO: implement {fn} for {source_name}."""\n'
    'from novelbase.core.exceptions import FeatureNotSupportedError\n\n'
    'async def {fn}(*args, **kwargs):\n'
    '    raise FeatureNotSupportedError("TODO")\n'
)


def _scaffold_source(name: str, modes: list[str], write_config: bool = True):
    """生成新书源脚手架（扁平一层结构）。

    - 目录名 = `name` 的下划线形式；`source.json.source_name` 用原名（连字符）。
    - 生成空 `__init__.py` + `source.json` + 4 个能力文件（`search` /
      `novel_info` / `chapter_list` / `chapter_content`）。
    - `write_config=True` 时额外生成默认用户配置 `sites/{name}.yaml`。

    出厂 `enabled`（D4）：api 类默认 `false`，requests/browser 类默认 `true`。
    """
    mode = (modes[0].strip() if modes else "") or "requests"
    source_dir = _SOURCES_ROOT / name.replace("-", "_")
    source_dir.mkdir(parents=True, exist_ok=True)

    (source_dir / "__init__.py").write_text("", encoding="utf-8")

    enabled = mode != "api"
    from shared.config import mode_defaults
    manifest = {
        "source_name": name,
        "enabled": enabled,
        "common": {"mode": mode, **mode_defaults(mode)},
        "default_config": {fn: {} for fn in _SCAFFOLD_FUNCTIONS},
    }
    (source_dir / "source.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for fn in _SCAFFOLD_FUNCTIONS:
        (source_dir / f"{fn}.py").write_text(
            _FUNC_TEMPLATE.format(fn=fn, source_name=name), encoding="utf-8")

    if write_config:
        from shared.config import save_site_config
        save_site_config(name, {"enabled": enabled,
                                **{fn: {} for fn in _SCAFFOLD_FUNCTIONS}})

    print(f"书源脚手架已创建: novelbase/sources/{source_dir.name}/")
    print("  __init__.py, source.json, "
          + ", ".join(f"{fn}.py" for fn in _SCAFFOLD_FUNCTIONS))
    if write_config:
        print(f"用户配置已创建: app_data/config/sites/{name}.yaml")




def main():
    args = _parse_args()
    dispatch = {
        "search":   cmd_search,
        "download": cmd_download,
        "update":   cmd_update,
        "export":   cmd_export,
        "delete":   cmd_delete,
        "novel":    cmd_novel,
        "sources":  cmd_source,
        "info":     cmd_info,
        "dev":      cmd_dev,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

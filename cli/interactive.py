# -*- coding: utf-8 -*-
"""交互式 CLI 主循环与菜单动作（根目录 main.py 委托至此）。"""

from __future__ import annotations

import asyncio

from cli.config import (
    load_main_config, load_site_config, load_format_configs,
    build_options, get_novel_group, load_groups,
)
from cli.ui import _select, _text_input, _create_progress, _advance_progress
from novelbase import (
    resolve_meta, resolve_chapter_list, resolve_chapter, search,
    create_engine,
)
from novelbase.source import list_sources
from novelbase.utils.logger import get_logger

_log = get_logger("cli.interactive")


def _get_engine(source_name: str = "fanqie", mode: str | None = None):
    """从当前配置创建引擎。mode 缺省时按 config 或书源能力推断。"""
    from novelbase.source import capabilities

    cfg = load_main_config()
    site_cfg = load_site_config(source_name)
    if mode is None:
        caps = capabilities(source_name)
        mode = cfg.get("mode") or next(iter(caps.values()), None)
    if mode:
        cfg["mode"] = mode
    options = build_options(cfg, site_cfg)
    return create_engine(options)


def _make_engines(source_name: str):
    """构造 engines 解析器：`engines(mode) -> engine`（按 mode 懒建并缓存）。

    最小实现；完整改造（并发全启用书源搜索、手选书源交互）留后续 CLI 计划。
    """
    cache: dict[str, object] = {}

    def _engines(mode: str):
        if mode not in cache:
            cache[mode] = _get_engine(source_name, mode)
        return cache[mode]

    return _engines


# -- Search ---------------------------------------------------


def do_search(query: str) -> tuple[str | None, str | None]:
    """搜索小说。返回 (url, source_name) 或 (None, None)。"""
    # URL 输入 → core 已无 URL→书源推断能力，需用户手选书源
    if query.startswith("http://") or query.startswith("https://"):
        source_names = list_sources()
        platform = _select("选择书源", [(n, n) for n in source_names]) if source_names else None
        if not platform:
            return None, None
        engines = _make_engines(platform)
        try:
            novel = asyncio.run(resolve_meta(query, platform, engines, skip_delay=True))
            print(f"\n📖 {novel.title} — {novel.author}")
            return novel.url, platform
        except Exception as e:
            print(f"获取小说信息失败: {e}")
            return None, None

    # 关键字搜索 → 让用户选书源（标签直接用 source_name，show_name 已取消）
    source_names = list(load_main_config().get("sites", {}).keys()) or list_sources()
    platform = _select("选择书源", [(n, n) for n in source_names])
    if not platform:
        return None, None

    engines = _make_engines(platform)
    try:
        results = asyncio.run(search([platform], query, engines, skip_delay=True))
    except Exception as e:
        print(f"搜索失败: {e}")
        return None, None

    if not results:
        print("未找到结果")
        return None, None

    print(f"\n搜索 '{query}' 的结果:")
    for i, r in enumerate(results, 1):
        print(f" {i}. {r.title} — {r.author}")
    choices_list = [(f"{r.title} — {r.author}", i - 1) for i, r in enumerate(results, 1)]
    sel = _select("选择小说", choices_list)
    if sel is None:
        return None, None
    if 0 <= sel < len(results):
        return results[sel].url, platform
    return None, None


# -- Download -------------------------------------------------


def do_download(
    url: str, group: str,
    format_configs: dict, max_workers: int = 3,
) -> None:
    """交互式下载：询问分组后复用 cli.core 的全量下载（async 经 asyncio.run）。"""
    from cli.core import _do_download_inner

    source_names = list_sources()
    if not source_names:
        print("没有可用书源")
        return
    platform = _select("选择书源", [(n, n) for n in source_names]) or source_names[0]
    engine = _get_engine(platform)
    try:
        g = _text_input(f"归入分组 [{group}]")
        if g:
            group = g
        asyncio.run(_do_download_inner(
            engine, url, group, format_configs,
            max_workers=max_workers, skip_delay=True,
        ))
    finally:
        engine.close()


# -- Update ---------------------------------------------------


async def _update_one_async(novel, max_workers: int) -> int:
    """更新单本小说到最新章节。返回新增章节数。"""
    from cli.core import _get_storage

    storage = _get_storage()
    source_name = getattr(novel, "source_name", "") or novel.extra.get("platform", "")
    engines = _make_engines(source_name)
    try:
        remote_chapters = await resolve_chapter_list(novel.url, source_name, engines)
        if not remote_chapters:
            print("  无法获取远程章节")
            return 0

        existing = list(storage.load_chapters(novel.id))
        existing_set = {c.order for c in existing}
        new_chapters = [c for c in remote_chapters if c.order not in existing_set]

        if not new_chapters:
            print(f"  {len(existing)}/{len(remote_chapters)}")
            return 0

        print(f"  {len(existing)}/{len(remote_chapters)} \033[1;32m+{len(new_chapters)}\033[0m")

        sem = asyncio.Semaphore(max_workers)

        async def _dl(ch):
            async with sem:
                try:
                    resolved = await resolve_chapter(ch, source_name, engines)
                    if resolved:
                        storage.save_chapter(novel, resolved)
                        return True
                except Exception:
                    pass
                return False

        results = await asyncio.gather(*(_dl(ch) for ch in new_chapters))
        ok = sum(1 for r in results if r)
        print(f"  下载 {ok}/{len(new_chapters)} 章")
        return ok
    except Exception as e:
        print(f"  更新失败: {e}")
        return 0


def do_update(format_configs: dict, max_workers: int = 3):
    """更新已有小说：展示分组列表，单选或全部更新。"""
    from cli.core import _get_storage, do_update as _do_update_all

    storage = _get_storage()
    groups = load_groups()

    all_novels = list(storage.iter_metas())
    if not all_novels:
        print("没有已下载的小说")
        return

    # 按分组排列
    grouped: dict[str, list] = {}
    ungrouped = []
    for n in all_novels:
        g = get_novel_group(n.id, groups)
        if g:
            grouped.setdefault(g, []).append(n)
        else:
            ungrouped.append(n)

    # 显示小说列表（分组区分）
    print(f"\n找到 {len(all_novels)} 本已下载小说：")
    idx = 0
    flat: list = []
    for g_name, novels in grouped.items():
        print(f"\n  [{g_name}]")
        for n in novels:
            idx += 1
            print(f"    {idx}. {n.title}  — {n.author}  [{n.id}]")
            flat.append(n)
    if ungrouped:
        print(f"\n  [未分组]")
        for n in ungrouped:
            idx += 1
            print(f"    {idx}. {n.title}  — {n.author}  [{n.id}]")
            flat.append(n)

    choices = [(f"{n.title}  — {n.author}", n) for n in flat]
    choices.append(("全部更新", "all"))
    choices.append(("返回", None))

    selection = _select("选择要更新的小说：", choices=choices)
    if selection is None:
        return

    if selection == "all":
        asyncio.run(_do_update_all(format_configs, max_workers=max_workers))
        return

    print(f"\n[{selection.title}] 正在更新...")
    ok = asyncio.run(_update_one_async(selection, max_workers))
    print(f"更新完成: 新增 {ok} 章")


# -- Visit site -----------------------------------------------


def do_visit_site() -> None:
    """用 BrowserEngine 打开所选平台网站。"""
    from novelbase import create_engine as _create_engine

    sources = list_sources()
    platform = _select("选择书源", [(n, n) for n in sources])
    if not platform:
        return
    # source.json 已无 hosts，无法推断首页 → 用占位 URL
    url = f"https://{platform}"

    cfg = load_main_config()
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)
    options.set_mode("browser")
    engine = _create_engine(options)

    async def _open():
        page = await engine.new_page()
        await page.goto(url)
        input(f"\n已打开 {url}，按回车关闭浏览器...")

    try:
        asyncio.run(_open())
    finally:
        engine.close()


# -- Main menu ------------------------------------------------


def main():
    """交互式主菜单循环。"""
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("Novel下载器 启动中...")

    from init_config import check_config, init_all_config
    result = check_config()
    if result["missing"]:
        if result["all_missing"]:
            print("首次运行，正在从默认模板初始化配置...")
        init_all_config()
        print(f"已初始化 {len(result['missing'])} 个配置文件")

    while True:
        try:
            cfg = load_main_config()
            format_configs = load_format_configs()

            dl = cfg.get("download", {})
            group = dl.get("group", "default")
            max_workers = dl.get("max_workers", 3)

            print(f"\n分组: {group}    并发: {max_workers}")
            print("1. 🔍 搜索下载")
            print("2. 🔄 更新已有小说")
            print("3. 📤 导出小说")
            print("4. 🔁 重新导出")
            print("5. 🗑️  删除小说")
            print("6. ⚙️  设置")
            print("7. 🌐 访问平台")
            print("0. 🚪 退出")

            try:
                ch = input("请选择: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if ch == "1":
                query = _text_input("搜索关键词或 URL")
                if not query:
                    continue
                url, _platform = do_search(query)
                if url:
                    do_download(url, group, format_configs, max_workers)

            elif ch == "2":
                do_update(format_configs, max_workers)

            elif ch in ("3", "4"):
                from cli.menus import do_export_menu
                do_export_menu(group, format_configs)

            elif ch == "5":
                from cli.menus import do_delete
                do_delete()

            elif ch == "6":
                from cli.config import load_site_config as _lsc
                from cli.menus import do_settings
                cfg, site_cfg = do_settings(cfg, "fanqie", _lsc("fanqie"))

            elif ch == "7":
                do_visit_site()

            elif ch == "0":
                break

        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            _log.exception("主循环异常")
            print(f"发生错误: {e}")

    print("再见！")

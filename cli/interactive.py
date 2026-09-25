# -*- coding: utf-8 -*-
"""交互式 CLI 主循环与菜单动作（根目录 main.py 委托至此）。"""

from __future__ import annotations

import asyncio

from cli.config import (
    load_main_config, load_format_configs,
    build_options, get_novel_group, load_groups,
)
from cli.ui import _select, _text_input
from shared.config import enabled_source_names
from novelbase import (
    resolve_meta, resolve_chapter_list, resolve_chapter, search,
    create_engine,
)
from novelbase.source import list_sources
from novelbase.utils.logger import get_logger
from shared.user_data import get_novel_source

_log = get_logger("cli.interactive")


def _get_engine(source_name: str = "fanqie", mode: str | None = None):
    """按书源名创建引擎；mode 缺省取书源首个能力声明的 mode。"""
    from novelbase.source import capabilities

    if mode is None:
        caps = capabilities(source_name)
        mode = next(iter(caps.values()), "browser")
    options = build_options(source_name, mode)
    return create_engine(options)


def _make_engines(source_name: str):
    """构造 engines 解析器：`engines(mode) -> engine`（按 mode 懒建并缓存）。

    缓存暴露为 `_engines.cache`，便于调用方结束时 close 所有引擎。
    """
    cache: dict[str, object] = {}

    def _engines(mode: str):
        if mode not in cache:
            cache[mode] = _get_engine(source_name, mode)
        return cache[mode]

    _engines.cache = cache  # type: ignore[attr-defined]
    return _engines


# -- Search ---------------------------------------------------


def do_search(query: str) -> tuple[str | None, str | None]:
    """搜索小说。返回 (url, source_name) 或 (None, None)。

    关键字分支：并发全部「启用书源」（`enabled_source_names()`），结果汇总标注来源
    后由用户选择；URL 分支：core 已无 URL→书源推断能力，需用户手选书源。
    """
    if query.startswith("http://") or query.startswith("https://"):
        source_names = list_sources()
        if not source_names:
            print("没有可用书源")
            return None, None
        source_name = _select("选择书源", [(n, n) for n in source_names])
        if not source_name:
            return None, None
        engines = _make_engines(source_name)
        try:
            novel = asyncio.run(resolve_meta(query, source_name, engines, skip_delay=True))
            print(f"\n📖 {novel.title} — {novel.author}")
            return novel.url, source_name
        except Exception as e:
            print(f"获取小说信息失败: {e}")
            return None, None
        finally:
            for eng in getattr(engines, "cache", {}).values():
                try:
                    eng.close()
                except Exception:
                    pass

    # 关键字搜索 → 并发全部启用书源，结果汇总标注来源
    sources = enabled_source_names()
    if not sources:
        print("没有启用的书源")
        return None, None

    async def _run():
        async def _one(name: str):
            # 每个源各用自己的引擎（杜绝「同 mode 源共用首个源引擎」）
            engines = _make_engines(name)
            try:
                return await search([name], query, engines, skip_delay=True)
            except Exception as e:      # 单个源失败静默跳过：不影响其它源
                print(f"  [{name}] 搜索失败: {e}")
                return ()
            finally:
                for eng in getattr(engines, "cache", {}).values():
                    try:
                        eng.close()
                    except Exception:
                        pass

        groups = await asyncio.gather(*(_one(n) for n in sources))
        return [r for group in groups for r in group]

    results = asyncio.run(_run())
    if not results:
        print("未找到结果")
        return None, None

    print(f"\n搜索 '{query}' 的结果:")
    for i, r in enumerate(results, 1):
        print(f" {i}. {r.title} — {r.author}  [{getattr(r, 'source_name', '')}]")
    choices_list = [(f"{r.title} — {r.author} [{getattr(r, 'source_name', '')}]", i - 1)
                    for i, r in enumerate(results, 1)]
    sel = _select("选择小说", choices_list)
    if sel is None:
        return None, None
    if 0 <= sel < len(results):
        return results[sel].url, getattr(results[sel], "source_name", "")
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
    source_name = _select("选择书源", [(n, n) for n in source_names])
    if not source_name:
        print("已取消选择书源")
        return
    engines = _make_engines(source_name)
    try:
        g = _text_input(f"归入分组 [{group}]")
        if g:
            group = g
        asyncio.run(_do_download_inner(
            source_name, url, group, format_configs,
            max_workers=max_workers, skip_delay=True, engines=engines,
        ))
    finally:
        for eng in getattr(engines, "cache", {}).values():
            try:
                eng.close()
            except Exception:
                pass


# -- Update ---------------------------------------------------


async def _update_one_async(novel, max_workers: int) -> int:
    """更新单本小说到最新章节。返回新增章节数。"""
    from cli.core import _get_storage

    storage = _get_storage()
    source_name = get_novel_source(novel.id) or ""
    if not source_name:
        print("  无法确定书源")
        return 0
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
                from cli.menus import do_settings
                cfg = do_settings(cfg)

            elif ch == "0":
                break

        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            _log.exception("主循环异常")
            print(f"发生错误: {e}")

    print("再见！")

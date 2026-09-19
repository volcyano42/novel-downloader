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
from novelbase.source import register_source, platform_from_url
from novelbase.utils.logger import get_logger

_log = get_logger("cli.interactive")

# 会话内记住 (platform, mode) → variant 选择，避免每次创建引擎重复询问
_variant_cache: dict[tuple[str, str], str] = {}


def _platform_from_url(url: str) -> str:
    """从 URL 推断平台（数据驱动）。未知 URL 抛 ValueError。"""
    plat = platform_from_url(url)
    if plat:
        return plat
    raise ValueError(f"未识别书源 URL: {url}")


def _resolve_variant(platform: str, mode: str) -> str | None:
    """解析当前 mode 的 variant：≤1 个直接用唯一项；多于一个时询问并会话级记住。"""
    from cli.config import mode_variants, resolve_variant as _resolve
    site_cfg = load_site_config(platform)
    resolved = _resolve(site_cfg, mode, None)
    if resolved is not None:
        return resolved
    variants = mode_variants(site_cfg, mode)
    if len(variants) <= 1:
        return variants[0] if variants else None
    key = (platform, mode)
    if key in _variant_cache:
        return _variant_cache[key]
    sel = _select(f"平台 {platform} 的 {mode} 模式有 {len(variants)} 个 variant，请选择", [(v, v) for v in variants])
    if sel is None:
        sel = variants[0]
        print(f"未选择，使用默认 variant: {sel}")
    _variant_cache[key] = sel
    return sel


def _get_engine(platform: str = "fanqie"):
    """从当前配置创建引擎（variant 按当前 mode 解析）。"""
    cfg = load_main_config()
    site_cfg = load_site_config(platform)
    mode = cfg.get("mode") or site_cfg.get("mode", "browser")
    options = build_options(cfg, site_cfg, _resolve_variant(platform, mode))
    return create_engine(options)


# -- Search ---------------------------------------------------


def do_search(query: str) -> tuple[str | None, str | None]:
    """搜索小说。返回 (url, platform) 或 (None, None)。"""
    # URL 输入 → 自动推断平台
    if query.startswith("http://") or query.startswith("https://"):
        platform = _platform_from_url(query)
        engine = _get_engine(platform)
        try:
            novel = asyncio.run(resolve_meta(query, engine=engine, skip_delay=True))
            print(f"\n📖 {novel.title} — {novel.author}")
            return novel.url, platform
        except Exception as e:
            print(f"获取小说信息失败: {e}")
            return None, None
        finally:
            engine.close()

    # 关键字搜索 → 让用户选平台
    platforms = list(load_main_config().get("sites", {}).keys()) or list(register_source().keys())
    labels = {k: v.get("show_name", k) for k, v in register_source().items()}
    choices = [(labels.get(p, p), p) for p in platforms]
    platform = _select("选择平台", choices)
    if not platform:
        return None, None

    engine = _get_engine(platform)
    try:
        results = asyncio.run(search(platform, query, engine=engine, skip_delay=True))
    except Exception as e:
        print(f"搜索失败: {e}")
        return None, None
    finally:
        engine.close()

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

    platform = _platform_from_url(url)
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
    platform = _platform_from_url(novel.url)
    engine = _get_engine(platform)
    try:
        remote_chapters = await resolve_chapter_list(novel.url, engine=engine)
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
                    resolved = await resolve_chapter(ch, engine=engine)
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
    finally:
        engine.close()


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

    sources = register_source()
    labels = {k: v.get("show_name", k) for k, v in sources.items()}
    platform = _select("选择平台", [(labels.get(k, k), k) for k in sources.keys()])
    if not platform:
        return
    hosts = sources[platform].get("hosts", ())
    if not hosts:
        print(f"平台 {labels.get(platform, platform)} 没有配置网址")
        return
    url = f"https://{hosts[0]}"

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

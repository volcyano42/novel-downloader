# -*- coding: utf-8 -*-
"""Core operations: download, update (non-interactive, used by cli.py)."""

from __future__ import annotations

from cli.config import (
    load_main_config, load_groups, load_site_config, add_novel_to_group,
    build_options,
)
from novelbase import (
    resolve_meta, resolve_chapter_list, resolve_chapter, export,
    create_engine, StorageOptions,
)
from novelbase.core.storage import create_storage
from novelbase.utils.logger import get_logger

_log = get_logger("cli.core")

_storage = None


def _create_progress(total: int):
    """Create a rich progress bar."""
    from rich.console import Console
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    console = Console(stderr=True)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
    task = progress.add_task("[cyan]下载中...", total=total)
    return progress, task


def _advance_progress(progress, task, advance: int = 1, last_title: str = ""):
    """Update progress bar."""
    if last_title:
        progress.update(task, description=f"[cyan]{last_title[:40]}")
    progress.advance(task, advance)


def _get_storage():
    """获取或创建全局存储实例。"""
    global _storage
    if _storage is None:
        from shared.config import get_database_url
        _storage = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))
    return _storage


def _platform_from_url(url: str) -> str:
    """从 URL 推断平台（数据驱动）。"""
    from novelbase.source import platform_from_url
    plat = platform_from_url(url)
    if plat:
        return plat
    raise ValueError(f"未识别书源 URL: {url}")


def _get_engine(platform: str = "fanqie", mode: str | None = None,
                variant: str | None = None):
    """Create a fresh engine from current config.

    mode/variant：指定时用于创建引擎（与 cli.main._get_engine 一致）；
    缺省保持原行为（config.yaml 的 mode / variant 自动选择）。
    """
    cfg = load_main_config()
    if mode:
        cfg["mode"] = mode
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg, variant)
    return create_engine(options)


# ── Download ─────────────────────────────────────────


async def _do_download_inner(
    engine, url: str, group: str,
    format_configs: dict, max_workers: int = 3, skip_delay: bool=False,
    skip_export: bool = True,
) -> None:
    """Core download flow (engine provided). Non-interactive: 全量下载。"""
    import asyncio

    # 1. Get metadata
    print("正在获取小说信息...")
    try:
        novel = await resolve_meta(url, engine=engine, skip_delay=skip_delay)
    except Exception as e:
        print(f"获取小说信息失败: {e}")
        return
    print(f"📖 {novel.title} — {novel.author}")

    # 2. Get chapter list
    print("正在获取章节列表...")
    try:
        chapters = await resolve_chapter_list(novel.url, engine=engine, skip_delay=skip_delay)
    except Exception as e:
        print(f"获取章节列表失败: {e}")
        return

    if not chapters:
        print("没有可下载的章节")
        return

    print(f"共 {len(chapters)} 章")

    # 3. Merge with existing chapters
    storage = _get_storage()
    novel_id = novel.id

    storage.save_meta(novel)
    add_novel_to_group(novel_id, group)

    existing = list(storage.load_chapters(novel_id))
    existing_set = {c.order for c in existing}
    to_download = [c for c in chapters if c.order not in existing_set]
    skipped = len(chapters) - len(to_download)

    if skipped:
        print(f"跳过 {skipped} 章已有章节")
    if not to_download:
        print("所有章节已下载")
        return

    # 4. Concurrent download
    progress, task = _create_progress(len(to_download))
    success = 0
    incomplete_count = 0
    errors: list[str] = []

    sem = asyncio.Semaphore(max_workers)

    async def _download_one(ch) -> tuple[bool, str, str]:
        async with sem:
            try:
                resolved = await resolve_chapter(ch, engine=engine)
                if resolved is None:
                    return False, ch.title, "章节内容为空"
                storage.save_chapter(novel, resolved)
                return True, ch.title, ""
            except Exception as e:
                return False, ch.title, str(e)
            finally:
                # 每章完成立即推进进度条（逐章实时；每章恰好推进一次，不重复计数）
                _advance_progress(progress, task, last_title=ch.title)

    with progress:
        results = await asyncio.gather(*(_download_one(ch) for ch in to_download))
        for ok, title, err in results:
            if ok:
                success += 1
            else:
                incomplete_count += 1
                errors.append(f"  [{title}]: {err}")

    print(f"\n下载完成: 成功 {success}, 跳过 {skipped}, 不完整 {incomplete_count}")
    if errors:
        print("错误详情:")
        for e in errors[:10]:
            print(e)
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个错误")

    # 5. Export (skipped by default — use `cli.py export` instead)
    if not skip_export:
        dl = load_main_config().get("download", {})
        enabled_formats = dl.get("formats", [])
        if enabled_formats:
            print("正在导出...")
            for fmt in enabled_formats:
                fmt_cfg = format_configs.get(fmt, {})
                if not fmt_cfg:
                    continue
                from novelbase.exporter import register_export_options
                opt_cls_map = register_export_options()
                opt_cls = opt_cls_map.get(fmt)
                if opt_cls is None:
                    print(f"  {fmt}: 跳过（无配置）")
                    continue
                opts = opt_cls(**fmt_cfg)
                try:
                    result = export(novel, opts, fmt)
                    print(f"  {fmt}: {result}")
                except Exception as e:
                    print(f"  {fmt}: 导出失败 — {e}")
        else:
            print("未设置导出格式，跳过导出")


# ── Update ───────────────────────────────────────────


async def do_update(format_configs: dict, max_workers: int = 3,
                    mode: str | None = None, variant: str | None = None):
    """非交互更新：全部已下载小说更新到最新章节。

    mode/variant：更新引擎的创建参数（如 --mode api --variant oiapi）；
    None 时按每本小说平台使用 config 默认引擎。
    """
    import asyncio
    from cli.config import get_novel_group

    storage = _get_storage()
    groups = load_groups()

    # 加载全部小说
    all_novels = list(storage.iter_metas())
    if not all_novels:
        print("没有已下载的小说")
        return

    # 按分组排列（仅展示）
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
    for g_name, novels in grouped.items():
        print(f"\n  [{g_name}]")
        for n in novels:
            idx += 1
            print(f"    {idx}. {n.title}  — {n.author}  [{n.id}]")
    if ungrouped:
        print(f"\n  [未分组]")
        for n in ungrouped:
            idx += 1
            print(f"    {idx}. {n.title}  — {n.author}  [{n.id}]")

    print("\n全部更新：")
    targets = all_novels

    total = len(targets)
    updated = 0
    for i, novel in enumerate(targets, 1):
        print(f"\n── [{i}/{total}] 正在更新: {novel.title} ──")
        platform = _platform_from_url(novel.url)
        engine = _get_engine(platform, mode, variant)
        try:
            remote_chapters = await resolve_chapter_list(novel.url, engine=engine)
            if not remote_chapters:
                print("  无法获取远程章节")
                continue

            existing = list(storage.load_chapters(novel.id))
            existing_set = {c.order for c in existing}
            new_chapters = [c for c in remote_chapters if c.order not in existing_set]

            if not new_chapters:
                print(f"  {len(existing)}/{len(remote_chapters)}")
                continue

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
            updated += ok

        except Exception as e:
            print(f"  更新失败: {e}")
        finally:
            engine.close()

    print(f"\n更新完成: 共更新 {updated} 章")

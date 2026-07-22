# -*- coding: utf-8 -*-
"""Core operations: login, search, download, update, main menu loop."""

from __future__ import annotations

from app.config import (
    load_main_config, load_groups, load_site_config, load_format_configs,
    save_site_config, add_novel_to_group,
    build_options,
)
from app.menus import do_settings, do_export_menu, do_delete
from app.ui import (
    _select, _text_input,
    _create_progress, _advance_progress, parse_order_string, _build_url_from_id,
    _display_width, _pad_right, _pad_center,
)
from novelbase import (
    fetch_meta, fetch_chapter_list, resolve_chapter, export,
    create_engine, search, login,
)
from novelbase.utils.logger import get_logger

_log = get_logger("app.core")


def _platform_from_url(url: str) -> str:
    """从 URL 推断平台。"""
    if "fanqienovel.com" in url or "changdunovel.com" in url:
        return "fanqie"
    if "qidian.com" in url:
        return "qidian"
    if "qimao.com" in url:
        return "qimao"
    return "fanqie"


def _get_engine(platform: str = "fanqie"):
    """Create a fresh engine from current config."""
    cfg = load_main_config()
    site_cfg = load_site_config(platform)
    options = build_options(cfg, site_cfg)
    return create_engine(options)


# ── Login ────────────────────────────────────────────


def do_login() -> None:
    """Open browser for user to log in, then save cookies to site config."""
    platforms = list(load_main_config().get("sites", {}).keys()) or ["fanqie", "qidian", "qimao"]
    labels = {p: p for p in platforms}
    platform = _select("选择平台", [(labels.get(p, p), p) for p in platforms])
    if not platform:
        return
    site_cfg = load_site_config(platform)
    cfg = load_main_config()
    options = build_options(cfg, site_cfg)
    engine = create_engine(options)
    try:
        cred = login(platform, engine)
        if cred:
            site_cfg.setdefault("browser", {})["cookies"] = cred.model_dump()
            save_site_config(platform, site_cfg)
            print("登录成功，cookies 已保存")
        else:
            print("登录失败：未获取到凭据")
    finally:
        engine.close()


# ── Search ───────────────────────────────────────────


def do_search(query: str) -> tuple[str | None, str | None]:
    """Search novels. Returns (url, platform) or (None, None)."""
    # URL 输入 → 自动推断平台
    if query.startswith("http://") or query.startswith("https://"):
        platform = _platform_from_url(query)
        engine = _get_engine(platform)
        try:
            novel = fetch_meta(query, engine=engine, skip_delay=True)
            print(f"\n📖 {novel.title} — {novel.author}")
            return novel.url, platform
        except Exception as e:
            print(f"获取小说信息失败: {e}")
            return None, None
        finally:
            engine.close()

    # 关键字搜索 → 让用户选平台
    platforms = list(load_main_config().get("sites", {}).keys()) or ["fanqie", "qidian", "qimao"]
    choices = [(p, p) for p in platforms]
    platform = _select("选择平台", choices)
    if not platform:
        return None, None

    engine = _get_engine(platform)
    try:
        results = search(platform, query, engine=engine, skip_delay=True)
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


# ── Download ─────────────────────────────────────────


def do_download(
    url: str, group: str,
    format_configs: dict, max_workers: int = 3,
) -> None:
    """Core download flow. Creates engine internally."""
    platform = _platform_from_url(url)
    engine = _get_engine(platform)
    try:
        _do_download_inner(engine, url, group, format_configs, max_workers, skip_delay=True)
    finally:
        engine.close()


def _do_download_inner(
    engine, url: str, group: str,
    format_configs: dict, max_workers: int = 3, skip_delay: bool=False
) -> None:
    """Core download flow (engine provided)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 1. Get metadata
    print("正在获取小说信息...")
    try:
        novel = fetch_meta(url, engine=engine, skip_delay=skip_delay)
    except Exception as e:
        print(f"获取小说信息失败: {e}")
        return
    print(f"📖 {novel.title} — {novel.author}")

    # 2. Get chapter list
    print("正在获取章节列表...")
    try:
        chapters = fetch_chapter_list(novel.url, engine=engine, skip_delay=skip_delay)
    except Exception as e:
        print(f"获取章节列表失败: {e}")
        return

    if not chapters:
        print("没有可下载的章节")
        return

    print(f"共 {len(chapters)} 章")

    # Chapter selection
    show_detail = input("是否选择要下载的章节? (y/n): ").strip().lower()
    if show_detail == "y":
        print(f"共 {len(chapters)} 章，输入范围 (如 1-10,20,30-): ", end="")
        try:
            raw = input().strip()
        except (EOFError, KeyboardInterrupt):
            return
        indices = parse_order_string(raw, len(chapters))
        if not indices:
            return
        chapters = [chapters[i] for i in indices]
        print(f"已选择 {len(chapters)} 章")

    # 3. Merge with existing chapters
    storage = _get_storage()
    novel_id = novel.id

    storage.save_meta(novel)

    # Check if novel is new — ask for group assignment
    existing_groups = load_groups()
    is_new = all(
        novel_id not in ids
        for ids in existing_groups.values()
        if isinstance(ids, dict)
    )
    if is_new:
        all_groups = list(existing_groups.keys()) or ["default"]
        print(f"\n新小说归入哪个分组？可选: {', '.join(all_groups)}")
        group_input = input(f"分组名称 [default]: ").strip()
        if group_input:
            group = group_input
        else:
            group = "default"
    # else: keep existing group — don't reassign
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
    last_title = ""

    def _download_one(ch) -> tuple[bool, str, str]:
        try:
            resolved = resolve_chapter(ch, engine=engine)
            if resolved is None:
                return False, ch.title, "章节内容为空"
            storage.save_chapter(novel, resolved)
            return True, ch.title, ""
        except Exception as e:
            return False, ch.title, str(e)

    with progress:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_download_one, ch): ch for ch in to_download}
            for fut in as_completed(futures):
                ok, title, err = fut.result()
                if ok:
                    success += 1
                else:
                    incomplete_count += 1
                    errors.append(f"  [{title}]: {err}")
                _advance_progress(progress, task, last_title=last_title)
                last_title = title

    print(f"\n下载完成: 成功 {success}, 跳过 {skipped}, 不完整 {incomplete_count}")
    if errors:
        print("错误详情:")
        for e in errors[:10]:
            print(e)
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个错误")

    # 5. Export
    dl = load_main_config().get("download", {})
    enabled_formats = dl.get("formats", [])
    if enabled_formats:
        print("正在导出...")
        for fmt in enabled_formats:
            fmt_cfg = format_configs.get(fmt, {})
            if not fmt_cfg:
                continue
            from novelbase.utils.registry import register_export_options
            opts = register_export_options(fmt, fmt_cfg)
            if opts is None:
                print(f"  {fmt}: 跳过（无配置）")
                continue
            try:
                result = export(novel, opts, fmt)
                print(f"  {fmt}: {result}")
            except Exception as e:
                print(f"  {fmt}: 导出失败 — {e}")
    else:
        print("未设置导出格式，跳过导出")

    # 6. Notify
    from app.notify import notify
    notify_cfg = load_main_config().get("download", {}).get("notify", {})
    if notify_cfg:
        notify(notify_cfg, complete=success, incomplete=incomplete_count)


# ── Update ───────────────────────────────────────────


def do_update(format_configs: dict, max_workers: int = 3):
    """列出全部已下载小说（分组区分），支持单选/全选更新。引擎在选择后才创建。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.config import get_novel_group

    storage = _get_storage()
    groups = load_groups()

    # 加载全部小说
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
    flat = []  # [(novel, display_label)]
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

    choices = [(f"{n.title}  — {n.author}  [{n.id}]", n) for n in flat]
    choices.append(("▸ 全部更新", "all"))
    choices.append(("返回", None))

    selection = _select("选择要更新的小说：", choices=choices)
    if selection is None:
        return

    targets = flat if selection == "all" else [selection]

    total = len(targets)
    updated = 0
    for i, novel in enumerate(targets, 1):
        print(f"\n── [{i}/{total}] 正在更新: {novel.title} ──")
        platform = _platform_from_url(novel.url)
        engine = _get_engine(platform)
        try:
            remote_chapters = fetch_chapter_list(novel.url, engine=engine)
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

            def _dl(ch):
                try:
                    resolved = resolve_chapter(ch, engine=engine)
                    if resolved:
                        storage.save_chapter(novel, resolved)
                        return True
                except Exception:
                    pass
                return False

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_dl, ch): ch for ch in new_chapters}
                ok = 0
                for fut in as_completed(futures):
                    if fut.result():
                        ok += 1
            print(f"  下载 {ok}/{len(new_chapters)} 章")
            updated += ok

        except Exception as e:
            print(f"  更新失败: {e}")
        finally:
            engine.close()

    print(f"\n更新完成: 共更新 {updated} 章")


# ── Main menu ────────────────────────────────────────


def main():
    """Main menu loop."""
    print("Novel下载器 启动中...")

    while True:
        try:
            cfg = load_main_config()
            format_configs = load_format_configs()

            dl = cfg.get("download", {})
            group = dl.get("group", "default")
            max_workers = dl.get("max_workers", 3)

            BOX_W = 48
            items = [
                "1. 🔍 搜索下载",
                "2. 🔄 更新已有小说",
                "3. 📤 导出小说",
                "4. 🔁 重新导出",
                "5. 🗑️  删除小说",
                "6. ⚙️  设置",
                "7. 🔑 登录",
                "0. 🚪 退出",
            ]
            print(f"\n┌{'─'*(BOX_W+2)}┐")
            info_line = f"分组: {group}    并发: {max_workers}"
            print(f"│ {_pad_right(info_line, BOX_W)} │")
            print(f"├{'─'*(BOX_W+2)}┤")
            for item in items:
                print(f"│ {_pad_right(item, BOX_W)} │")
            print(f"└{'─'*(BOX_W+2)}┘")

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
                    if not (url.startswith("http://") or url.startswith("https://")):
                        url = _build_url_from_id(url)
                    do_download(url, group, format_configs, max_workers)

            elif ch == "2":
                do_update(format_configs, max_workers)

            elif ch == "3":
                do_export_menu(group, format_configs)

            elif ch == "4":
                do_export_menu(group, format_configs)

            elif ch == "5":
                do_delete()

            elif ch == "6":
                from app.config import load_site_config as _lsc
                cfg, site_cfg = do_settings(cfg, "fanqie", _lsc("fanqie"))

            elif ch == "7":
                do_login()

            elif ch == "0":
                break

        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            _log.exception("主循环异常")
            print(f"发生错误: {e}")

    print("再见！")

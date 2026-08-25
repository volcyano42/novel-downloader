# -*- coding: utf-8 -*-
"""菜单系统：设置菜单、导出菜单、删除菜单（交互式）。"""

from __future__ import annotations

from cli.config import (
    save_main_config, load_format_configs,
    save_site_config, load_groups,
)
from cli.ui import _select, _text_input, _input_int, _input_float, _platform_label, _show_platforms
from novelbase.utils.logger import get_logger

_log = get_logger("cli.menus")


# -- Settings menu --------------------------------------------


def do_settings(cfg: dict, platform: str, site_cfg: dict) -> tuple[dict, dict]:
    """设置菜单入口。返回 (cfg, site_cfg) 可能被修改。"""
    labels = _show_platforms()
    while True:
        fmt_str = _fmt_summary(cfg)
        print(f"\n[设置]")
        print(f" 平台: {_platform_label(labels, platform)}")
        print(f" 模式: {site_cfg.get('mode', 'browser')}")
        print(f" 1. 下载设置（线程/分组）")
        print(f" 2. 站点设置（{platform}）")
        print(f" 3. 格式设置  （{fmt_str}）")
        print(" 0. 返回主菜单（自动保存）")
        ch = input("请选择: ").strip()
        if ch == "1":
            _settings_download(cfg, platform, site_cfg, labels)
        elif ch == "2":
            _settings_site(cfg, platform, site_cfg)
        elif ch == "3":
            _settings_format_list(cfg)
        elif ch == "0":
            break
    return cfg, site_cfg


def _fmt_summary(cfg: dict) -> str:
    """已启用导出格式摘要。"""
    enabled = cfg.get("download", {}).get("formats", [])
    return ", ".join(enabled) if enabled else "未设置"


def _settings_download(cfg: dict, platform: str, site_cfg: dict, labels: dict) -> None:
    """下载设置子菜单。"""
    dl = cfg.setdefault("download", {})
    _log.debug("settings_download")

    mode = site_cfg.get("mode", "browser")
    print(f"\n[下载设置]")
    print(f" 当前模式: {mode}")
    print(" 1. 切换模式")
    print(f" 2. 下载线程数: {dl.get('max_workers', 3)}")
    print(f" 3. 下载分组: {dl.get('group', 'default')}")
    print(" 0. 返回")
    ch = input("请选择: ").strip()

    if ch == "1":
        modes = [("浏览器模式", "browser"), ("API 模式", "api"), ("Requests 模式", "requests")]
        sel = _select("选择模式", modes)
        if sel:
            site_cfg["mode"] = sel
            save_site_config(platform, site_cfg)
    elif ch == "2":
        n = _input_int("下载线程数", dl.get("max_workers", 3))
        dl["max_workers"] = n
        save_main_config(cfg)
    elif ch == "3":
        g = _text_input("输入分组名称")
        if g:
            dl["group"] = g
            save_main_config(cfg)


def _settings_site(cfg: dict, platform: str, site_cfg: dict) -> None:
    """站点设置子菜单。"""
    mode = site_cfg.get("mode", "browser")
    print(f"\n[{platform} 站点设置]")

    if mode == "browser":
        _settings_site_browser(cfg, site_cfg)
    elif mode == "api":
        _settings_site_api(cfg, site_cfg)
    elif mode == "requests":
        _settings_site_requests(cfg, site_cfg)

    save_site_config(platform, site_cfg)


def _settings_site_browser(cfg: dict, site_cfg: dict) -> None:
    """浏览器模式站点设置。"""
    browser = site_cfg.setdefault("browser", {}).setdefault("default", {})
    while True:
        lo, hi = _get_delay(site_cfg, "browser")
        print(f"\n  浏览器设置:")
        print(f"  1. 无头模式: {browser.get('headless', False)}")
        print(f"  2. 延迟: {lo}-{hi}s")
        print(f"  3. 超时: {browser.get('timeout', 30)}s")
        print(f"  4. 重试次数: {browser.get('retry_times', 3)}")
        print(f"  5. 回退系数: {browser.get('backoff_factor', 2)}")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            browser["headless"] = not browser.get("headless", False)
        elif ch == "2":
            lo = _input_float("最小延迟", lo)
            hi = _input_float("最大延迟", hi)
            _set_delay(site_cfg, "browser", lo, hi)
        elif ch == "3":
            browser["timeout"] = _input_int("超时(秒)", browser.get("timeout", 30))
        elif ch == "4":
            browser["retry_times"] = _input_int("重试次数", browser.get("retry_times", 3))
        elif ch == "5":
            browser["backoff_factor"] = _input_float("回退系数", browser.get("backoff_factor", 2))
        elif ch == "0":
            break


def _settings_site_api(cfg: dict, site_cfg: dict) -> None:
    """API 模式站点设置。"""
    api = site_cfg.setdefault("api", {})
    while True:
        print(f"\n  API 设置:")
        current_name = None
        for name, prov in api.items():
            if isinstance(prov, dict):
                current_name = name
                print(f"  提供商: {name} {'(启用)' if prov.get('enabled', True) else '(禁用)'}")
                print(f"  1. 切换提供商(当前: {name})")
                print(f"  2. 启用/禁用 {name}")
                print(f"  3. 超时: {prov.get('timeout', 30)}s")
                print(f"  4. 重试次数: {prov.get('retry_times', 3)}")
                break
        if current_name is None:
            print("  无 API 提供商配置")
            print("  0. 返回")
            ch = input("请选择: ").strip()
            if ch == "0":
                break
            continue
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            names = [n for n, v in api.items() if isinstance(v, dict)]
            if not names:
                print("没有可用提供商")
            else:
                choices = [(n, n) for n in names]
                sel = _select("选择提供商", choices)
                if sel:
                    for n in names:
                        api[n]["enabled"] = (n == sel)
        elif ch == "2":
            for name, prov in api.items():
                if isinstance(prov, dict):
                    prov["enabled"] = not prov.get("enabled", True)
                    print(f"{name} 已{'启用' if prov['enabled'] else '禁用'}")
                    break
        elif ch == "3":
            for name, prov in api.items():
                if isinstance(prov, dict):
                    prov["timeout"] = _input_int("超时(秒)", prov.get("timeout", 30))
                    break
        elif ch == "4":
            for name, prov in api.items():
                if isinstance(prov, dict):
                    prov["retry_times"] = _input_int("重试次数", prov.get("retry_times", 3))
                    break
        elif ch == "0":
            break


def _settings_site_requests(cfg: dict, site_cfg: dict) -> None:
    """Requests 模式站点设置。"""
    req = site_cfg.setdefault("requests", {}).setdefault("default", {})
    while True:
        lo, hi = _get_delay(site_cfg, "requests")
        print(f"\n  Requests 设置:")
        print(f"  1. 延迟: {lo}-{hi}s")
        print(f"  2. 超时: {req.get('timeout', 30)}s")
        print(f"  3. 重试次数: {req.get('retry_times', 3)}")
        print(f"  4. 回退系数: {req.get('backoff_factor', 2)}")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            lo = _input_float("最小延迟", lo)
            hi = _input_float("最大延迟", hi)
            _set_delay(site_cfg, "requests", lo, hi)
        elif ch == "2":
            req["timeout"] = _input_int("超时(秒)", req.get("timeout", 30))
        elif ch == "3":
            req["retry_times"] = _input_int("重试次数", req.get("retry_times", 3))
        elif ch == "4":
            req["backoff_factor"] = _input_float("回退系数", req.get("backoff_factor", 2))
        elif ch == "0":
            break


# -- Format settings -----------------------------------------


def _settings_format_list(cfg: dict) -> None:
    """格式开关列表。"""
    all_formats = load_format_configs()
    dl = cfg.setdefault("download", {})
    enabled = dl.setdefault("formats", [])

    while True:
        print(f"\n[格式设置]")
        for fmt in all_formats:
            mark = "✅" if fmt in enabled else "⬜"
            print(f"  {mark} {fmt}")
        print("\n  1. 启用/禁用")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "1":
            _settings_format_toggle(all_formats, enabled)
            save_main_config(cfg)
        elif ch == "0":
            break


def _settings_format_toggle(all_formats: dict, enabled: list) -> None:
    """切换格式启用状态。"""
    items = list(all_formats.keys())
    choices = [(f"{'✅' if f in enabled else '⬜'} {f}", f) for f in items]
    sel = _select("选择切换", choices)
    if sel:
        if sel in enabled:
            enabled.remove(sel)
        else:
            enabled.append(sel)


# -- Export menu ---------------------------------------------


def do_export_menu(group: str, format_configs: dict):
    """导出菜单：选书 → 选格式 → export()。仅存储操作，无需引擎。"""
    from cli.core import _get_storage
    from novelbase import export
    from novelbase.exporter import register_export_options

    storage = _get_storage()
    novels = list(storage.iter_metas())
    if not novels:
        print("书架上没有小说")
        return

    groups = load_groups()
    group_ids = set(groups.get(group, {}).keys()) if group != "default" else None
    novels_in_group = [n for n in novels if group == "default" or (group_ids and n.id in group_ids)]
    if not novels_in_group:
        print(f"分组 '{group}' 中没有小说")
        return

    print(f"\n可导出小说 ({len(novels_in_group)} 本):")
    for i, n in enumerate(novels_in_group, 1):
        print(f" {i}. {n.title} ({n.author})")
    try:
        raw = input("请输入编号: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(novels_in_group):
            return
    except ValueError:
        return

    novel = novels_in_group[idx]
    fmt_names = [f for f in format_configs if f in ["txt", "epub", "img"]]
    if not fmt_names:
        print("没有可用格式")
        return
    print("选择格式:")
    for i, f in enumerate(fmt_names, 1):
        print(f" {i}. {f}")
    try:
        raw = input("请输入编号: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw:
        return
    try:
        fidx = int(raw) - 1
        if fidx < 0 or fidx >= len(fmt_names):
            return
    except ValueError:
        return
    fmt = fmt_names[fidx]

    opt_cls_map = register_export_options()
    opt_cls = opt_cls_map.get(fmt)
    if opt_cls is None:
        print("无法获取导出选项")
        return
    fmt_cfg = format_configs.get(fmt, {})
    opts = opt_cls(**fmt_cfg)
    if opts is None:
        print("无法获取导出选项")
        return
    print(f"正在导出 '{novel.title}' → {fmt} ...")
    try:
        # export signature: (novel, options, format, **kwargs)
        result = export(novel, opts, fmt)
        print(f"导出完成: {result}")
    except Exception as e:
        print(f"导出失败: {e}")


# -- Delete menu ---------------------------------------------


def do_delete() -> None:
    """删除小说（yes 确认），并同步移出全部分组。仅存储操作，无需引擎。"""
    from cli.core import _get_storage
    from cli.config import save_groups

    storage = _get_storage()
    novels = list(storage.iter_metas())
    if not novels:
        print("书架上没有小说")
        return

    print(f"\n[删除小说]")
    for i, n in enumerate(novels, 1):
        print(f" {i}. {n.title} ({n.author})")
    try:
        raw = input("请输入编号 (q 取消): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw or raw.lower() == "q":
        return
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(novels):
            return
    except ValueError:
        return

    novel = novels[idx]
    print(f"\n确定删除 '{novel.title}'? (yes/no): ", end="")
    try:
        confirm = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if confirm == "yes":
        storage.delete_novel(novel.id)
        groups = load_groups()
        removed = False
        for g, ids in groups.items():
            if isinstance(ids, dict) and novel.id in ids:
                ids.pop(novel.id, None)
                removed = True
        if removed:
            save_groups(groups)
        print(f"已删除 '{novel.title}'")
        _log.info("用户删除小说: %s (%s)", novel.title, novel.id)
    else:
        print("取消删除")


# -- Delay helpers -------------------------------------------


def _get_delay(site_cfg: dict, mode: str) -> tuple[float, float]:
    """获取某模式的当前延迟范围。"""
    section = site_cfg.get(mode, {}).get("default", {})
    delay = section.get("delay", (3, 6))
    if isinstance(delay, list):
        delay = tuple(delay)
    return delay[0], delay[1]


def _set_delay(site_cfg: dict, mode: str, lo: float, hi: float):
    """设置某模式的延迟范围。"""
    site_cfg.setdefault(mode, {}).setdefault("default", {})["delay"] = [lo, hi]

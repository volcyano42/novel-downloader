# -*- coding: utf-8 -*-
"""菜单系统：设置菜单、导出菜单、删除菜单（交互式）。"""

from __future__ import annotations

from cli.config import (
    save_main_config, load_format_configs,
    save_site_config, load_site_config, load_groups,
)
from cli.ui import _select, _text_input, _input_int, _input_float
from shared.config import merged_source_config, is_source_enabled
from novelbase.source import list_sources, capabilities
from novelbase.utils.logger import get_logger

_log = get_logger("cli.menus")


# -- Settings menu --------------------------------------------


def do_settings(cfg: dict) -> dict:
    """设置菜单入口（书源维度）。返回可能被修改的 cfg。"""
    while True:
        fmt_str = _fmt_summary(cfg)
        print(f"\n[设置]")
        print(f" 1. 下载设置（线程/分组）")
        print(f" 2. 书源设置")
        print(f" 3. 格式设置  （{fmt_str}）")
        print(" 0. 返回主菜单（自动保存）")
        ch = input("请选择: ").strip()
        if ch == "1":
            _settings_download(cfg)
        elif ch == "2":
            _settings_source(cfg)
        elif ch == "3":
            _settings_format_list(cfg)
        elif ch == "0":
            break
    return cfg


def _fmt_summary(cfg: dict) -> str:
    """已启用导出格式摘要。"""
    enabled = cfg.get("download", {}).get("formats", [])
    return ", ".join(enabled) if enabled else "未设置"


def _settings_download(cfg: dict) -> None:
    """下载设置子菜单（线程/分组）。"""
    dl = cfg.setdefault("download", {})
    _log.debug("settings_download")

    print(f"\n[下载设置]")
    print(f" 1. 下载线程数: {dl.get('max_workers', 3)}")
    print(f" 2. 下载分组: {dl.get('group', 'default')}")
    print(" 0. 返回")
    ch = input("请选择: ").strip()

    if ch == "1":
        dl["max_workers"] = _input_int("下载线程数", dl.get("max_workers", 3))
        save_main_config(cfg)
    elif ch == "2":
        g = _text_input("输入分组名称")
        if g:
            dl["group"] = g
            save_main_config(cfg)


def _settings_source(cfg: dict) -> None:
    """书源设置：选书源 → 逐能力段编辑。"""
    names = list_sources()
    if not names:
        print("没有可用书源")
        return
    source_name = _select("选择书源", [(n, n) for n in names])
    if not source_name:
        return
    _settings_source_detail(cfg, source_name)


def _settings_source_detail(cfg: dict, source_name: str) -> None:
    """单书源详情：启用开关 + 各能力段入口。"""
    while True:
        caps = capabilities(source_name)
        enabled = is_source_enabled(source_name)
        print(f"\n[{source_name} 设置]  状态: {'启用' if enabled else '禁用'}")
        print(f" 1. {'禁用' if enabled else '启用'}该书源")
        entries = list(caps.items())
        for i, (cap, mode) in enumerate(entries, 2):
            print(f" {i}. {cap}（{mode}）配置")
        print(" 0. 返回")
        ch = input("请选择: ").strip()
        if ch == "0":
            return
        if ch == "1":
            _toggle_source_enabled(source_name)
            continue
        try:
            idx = int(ch) - 2
        except ValueError:
            continue
        if 0 <= idx < len(entries):
            _edit_capability(source_name, entries[idx][0], entries[idx][1])


def _toggle_source_enabled(source_name: str) -> None:
    """切换书源启用状态（写入用户层顶层 enabled）。"""
    user = load_site_config(source_name)
    new_val = not is_source_enabled(source_name)
    user["enabled"] = new_val
    save_site_config(source_name, user)
    print(f"{source_name} 已{'启用' if new_val else '禁用'}")


def _set_cap_field(source_name: str, capability: str, field: str, value) -> None:
    """写入用户层某能力段的单个字段。"""
    user = load_site_config(source_name)
    user.setdefault(capability, {})[field] = value
    save_site_config(source_name, user)


def _edit_capability(source_name: str, capability: str, mode: str) -> None:
    """按能力段 mode 编辑字段（browser/api/requests）。"""
    while True:
        merged = merged_source_config(source_name).get(capability, {})
        lo, hi = _get_delay(source_name, capability)
        print(f"\n  [{capability}（{mode}）配置]")
        print(f"  1. 延迟: {lo}-{hi}s")
        if mode == "browser":
            print(f"  2. 无头模式: {merged.get('headless', False)}")
            print(f"  3. 超时: {merged.get('timeout', 30)}s")
            print(f"  4. 重试次数: {merged.get('retry_times', 3)}")
            print(f"  5. 回退系数: {merged.get('backoff_factor', 2)}")
        elif mode == "api":
            print(f"  2. Key: {merged.get('key', '')}")
            print(f"  3. 超时: {merged.get('timeout', 30)}s")
            print(f"  4. 重试次数: {merged.get('retry_times', 3)}")
            print(f"  5. 回退系数: {merged.get('backoff_factor', 2)}")
        else:  # requests 及未知 mode 的通用字段
            print(f"  2. 超时: {merged.get('timeout', 30)}s")
            print(f"  3. 重试次数: {merged.get('retry_times', 3)}")
            print(f"  4. 回退系数: {merged.get('backoff_factor', 2)}")
        print("  0. 返回")
        ch = input("请选择: ").strip()
        if ch == "0":
            return
        if ch == "1":
            lo = _input_float("最小延迟", lo)
            hi = _input_float("最大延迟", hi)
            _set_delay(source_name, capability, lo, hi)
            continue
        if mode == "browser":
            spec = {"2": ("headless", "bool"), "3": ("timeout", "int"),
                    "4": ("retry_times", "int"), "5": ("backoff_factor", "float")}
        elif mode == "api":
            spec = {"2": ("key", "str"), "3": ("timeout", "int"),
                    "4": ("retry_times", "int"), "5": ("backoff_factor", "float")}
        else:
            spec = {"2": ("timeout", "int"), "3": ("retry_times", "int"),
                    "4": ("backoff_factor", "float")}
        entry = spec.get(ch)
        if not entry:
            continue
        field, kind = entry
        cur = merged.get(field, "")
        if kind == "bool":
            _set_cap_field(source_name, capability, field, not bool(cur))
        elif kind == "int":
            _set_cap_field(source_name, capability, field, _input_int(field, int(cur or 0)))
        elif kind == "float":
            _set_cap_field(source_name, capability, field, _input_float(field, float(cur or 0)))
        else:
            _set_cap_field(source_name, capability, field, _text_input(field) or str(cur))


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
        from shared.user_data import delete_novel_source
        delete_novel_source(novel.id)
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


def _get_delay(source_name: str, capability: str) -> tuple[float, float]:
    """获取某书源某能力段三层合并后的当前延迟范围。"""
    merged = merged_source_config(source_name).get(capability, {})
    delay = merged.get("delay", (3, 6))
    if isinstance(delay, list):
        delay = tuple(delay)
    return delay[0], delay[1]


def _set_delay(source_name: str, capability: str, lo: float, hi: float) -> None:
    """设置某书源某能力段的延迟范围（写入用户层）。"""
    user = load_site_config(source_name)
    user.setdefault(capability, {})["delay"] = [lo, hi]
    save_site_config(source_name, user)

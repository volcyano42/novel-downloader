#!/usr/bin/env python3
"""导出器调试工具 — 从 storage 读取数据并测试导出。

用法:
    python scripts/debug_exporter.py --novel-id 195958 --format epub
    python scripts/debug_exporter.py --novel-id 195958 --format txt
    python scripts/debug_exporter.py --list              # 列出已下载小说
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from main import APP_DATA, load_format_configs, load_main_config, build_options
from nldlder.utils.registry import register_exporter


def cmd_list():
    storage_dir = APP_DATA / "storage"
    if not storage_dir.exists():
        print("storage 目录不存在")
        return

    from nldlder import LocalStorage
    storage = LocalStorage(storage_dir)
    novel_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
    if not novel_dirs:
        print("无已下载小说")
        return

    print(f"\n已下载小说 ({len(novel_dirs)} 本):\n")
    for d in sorted(novel_dirs):
        meta = storage.load_meta(d.name)
        if meta:
            print(f"  [{meta.id}] {meta.title}  — {meta.author}  ({meta.serial}章)")


def cmd_export(novel_id: str, fmt: str):
    storage_dir = APP_DATA / "storage"
    if not storage_dir.exists():
        print("storage 目录不存在")
        return

    from nldlder import LocalStorage, NovelDownloader, create_engine
    storage = LocalStorage(storage_dir)

    # 加载小说元数据和章节
    meta = storage.load_meta(novel_id)
    if meta is None:
        print(f"✗ 未找到小说: {novel_id}")
        return

    chapters = storage.load_chapters(novel_id)
    if chapters:
        meta.update_chapter(chapters)

    print(f"小说: {meta.title}  — {meta.author}")
    print(f"章节: {len(meta.chapters)} 章 (已完成: {len(meta.chapters.completed_chapters or [])})")

    # 创建 engine + downloader
    cfg = load_main_config()
    cfg["mode"] = "requests"
    from main import load_site_config
    site_cfg = load_site_config("fanqie")  # 导出不依赖平台
    options = build_options(cfg, site_cfg)

    # 设置导出格式
    fmt_configs = load_format_configs()
    if fmt not in fmt_configs:
        print(f"✗ 格式 '{fmt}' 未在 app_data/config/formats/ 中配置")
        print(f"  可用: {list(fmt_configs.keys())}")
        return

    fmt_cfg = fmt_configs[fmt]
    from nldlder.utils.registry import register_export_options
    opt_cls_map = register_export_options()
    opt_cls = opt_cls_map.get(fmt)
    if opt_cls is None:
        print(f"✗ 未找到导出器: {fmt}")
        return

    group = cfg.get("group", "default")
    raw_path = fmt_cfg.get("output_path", "").replace("{group}", group)
    extra = {k: fmt_cfg[k] for k in (
        "encoding", "file_name_template", "css_style", "include_toc",
    ) if k in fmt_cfg}
    opt = opt_cls(output_path=raw_path, **extra)
    options.set_export_options(opt)

    engine = create_engine(options)
    dl = NovelDownloader(engine, options=options)
    try:
        print(f"\n正在导出为 {fmt}...")
        dl.export(meta)
        print(f"✓ 导出完成 → {raw_path}")
    finally:
        engine.close()


def main():
    p = argparse.ArgumentParser(description="导出器调试工具")
    p.add_argument("--list", "-l", action="store_true", help="列出已下载小说")
    p.add_argument("--novel-id", help="小说 ID")
    p.add_argument("--format", "-f", default="epub", help="导出格式 (epub/txt/img)")
    args = p.parse_args()

    if args.list:
        cmd_list()
    elif args.novel_id:
        cmd_export(args.novel_id, args.format)
    else:
        p.print_help()


if __name__ == "__main__":
    main()

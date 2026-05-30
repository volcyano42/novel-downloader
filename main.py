"""
novel-downloader — 交互式 CLI
功能：登录 / 搜索 / 更新 / 下载
配置文件：app_data/config/*.yaml
导出路径：app_data/{group}/{novel.name}/
"""
import sys
from pathlib import Path

import yaml

try:
    import questionary
    _HAS_QUESTIONARY = True
except ImportError:
    _HAS_QUESTIONARY = False

from nldlder import (
    NovelDownloader, Options, create_engine,
    get_exporter_options, get_exporters,
    search, login,
)
from nldlder.core.storage import Storage
from nldlder.core.exceptions import AntiCrawlError
from nldlder.utils.logger import get_logger

_log = get_logger("nldlder.main")

APP_DATA = Path(__file__).parent / "app_data"
CONFIG_DIR = APP_DATA / "config"

# ═══════════════════════════════════════════════════════════════════
# 交互工具 — questionary 优先，无 TTY 时降级为 input()
# ═══════════════════════════════════════════════════════════════════

def _select(message: str, choices: list[tuple[str, object]]) -> object | None:
    """显示选项菜单，返回选中的 value。

    choices: [(label, value), ...] 或 [("标签", value), ..., ("返回", None)]

    questionary 可用时使用上下键选择；不可用时降级为数字输入。
    """
    if _HAS_QUESTIONARY:
        try:
            q_choices = [
                questionary.Choice(title=label, value=value)
                for label, value in choices
            ]
            return questionary.select(message, choices=q_choices).ask()
        except Exception:
            pass  # 降级到 input()

    # ── input() 降级 ──
    print(f"\n{message}")
    for i, (label, _) in enumerate(choices, 1):
        print(f"  {i}. {label}")
    while True:
        raw = input("请输入数字 (q 退出): ").strip()
        if raw.lower() == "q":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx][1]
        except ValueError:
            pass
        print("输入错误，请重新输入")


def _text_input(message: str) -> str | None:
    """获取文本输入。"""
    if _HAS_QUESTIONARY:
        try:
            return questionary.text(message).ask()
        except Exception:
            pass
    return input(f"{message} ").strip() or None


# ═══════════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════════

def load_main_config() -> dict:
    """加载 app_data/config/config.yaml"""
    path = CONFIG_DIR / "config.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def load_site_config(platform: str = "fanqie") -> dict:
    """加载 app_data/config/sites/{platform}.yaml"""
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def load_format_configs() -> dict:
    """加载 app_data/config/formats/*.yaml

    返回 {fmt_name: config_dict}，例如:
        {"txt": {"enabled": true, "output_path": "app_data/export/{group}/{file_name_template}", ...}, ...}
    """
    formats = {}
    formats_dir = CONFIG_DIR / "formats"
    if formats_dir.exists():
        for f in formats_dir.glob("*.yaml"):
            with open(f, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
                for name, cfg in data.items():
                    formats[name] = cfg
    return formats

def build_options(cfg: dict, site_cfg: dict) -> Options:
    """从配置字典构建 Options 对象。"""
    options = Options()
    mode = cfg.get("mode", "browser")
    options.set_mode(mode)

    # 下载选项
    download_cfg = cfg.get("download", {})
    options.set_download_options(
        max_workers=download_cfg.get("max_workers", 3)
    )

    # 模式特定选项
    if mode == "browser":
        browser_cfg = site_cfg.get("browser", {})
        user_data_dir = browser_cfg.get("user_data_dir", "")
        if user_data_dir:
            ud_path = Path(user_data_dir)
            if not ud_path.is_absolute():
                ud_path = Path(__file__).parent / ud_path
        else:
            ud_path = None
        options.set_browser_options(
            headless=browser_cfg.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=browser_cfg.get("timeout", 30),
            retry_times=browser_cfg.get("retry_times", 3),
            backoff_factor=browser_cfg.get("backoff_factor", 2),
            delay=tuple(browser_cfg.get("delay", [3, 5])),
            viewport=browser_cfg.get("viewport"),
        )

    elif mode == "api":
        api_section = site_cfg.get("api", {})
        # 取第一个启用的 provider
        for name, provider in api_section.items():
            if isinstance(provider, dict) and provider.get("enabled", True):
                options.set_api_options(
                    name=name,
                    key=provider.get("key", ""),
                    timeout=provider.get("timeout", 30),
                    retry_times=provider.get("retry_times", 3),
                    batch_size=provider.get("batch_size", 3),
                    backoff_factor=provider.get("backoff_factor", 2),
                    delay=tuple(provider.get("delay", [3, 5])),
                    params=provider.get("params", {}),
                )
                break

    elif mode == "requests":
        req_cfg = site_cfg.get("requests", {})
        cookies_val = req_cfg.get("cookies")
        if isinstance(cookies_val, str) and cookies_val:
            # 字符串格式 "k1=v1; k2=v2" → dict
            cookies_dict = {}
            for item in cookies_val.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies_dict[k.strip()] = v.strip()
            cookies_val = cookies_dict
        elif not isinstance(cookies_val, dict):
            cookies_val = None

        options.set_requests_options(
            headers=req_cfg.get("headers"),
            cookies=cookies_val,
            proxies=req_cfg.get("proxies"),
            timeout=req_cfg.get("timeout", 30),
            retry_times=req_cfg.get("retry_times", 3),
            backoff_factor=req_cfg.get("backoff_factor", 2),
            delay=tuple(req_cfg.get("delay", [3, 5])),
        )

    return options

# ═══════════════════════════════════════════════════════════════════
# 核心功能
# ═══════════════════════════════════════════════════════════════════

def do_login(engine):
    """打开浏览器让用户手动登录番茄小说。"""
    platform_choice = _select(
        "选择网站：",
        choices=[
            ("番茄小说 (fanqie)", "fanqie"),
            ("返回", None),
        ],
    )

    if platform_choice is None:
        return

    print("\n正在打开浏览器，请在浏览器窗口中完成登录...")
    print("（程序将自动检测登录完成，最多等待 120 秒）\n")

    try:
        cred = login(platform_choice, engine)
        cookie_count = len(cred.cookies) if cred and cred.cookies else 0
        if cookie_count > 0:
            print(f"✓ 登录成功！获取到 {cookie_count} 个 cookies")
        else:
            print("⚠ 登录完成但未获取到 cookies，请确认已在浏览器中完成登录")
    except Exception as e:
        print(f"✗ 登录失败: {e}")


def do_search(engine, dl) -> str | None:
    """搜索小说，选择后返回小说 URL（或 None 表示取消）。"""
    query = _text_input("请输入搜索关键词：")
    if not query or not query.strip():
        return None

    print(f"\n正在搜索「{query}」...")
    try:
        results = search("fanqie", query, engine)
    except Exception as e:
        print(f"✗ 搜索失败: {e}")
        return None

    if not results:
        print("未找到任何结果")
        return None

    choices = []
    for r in results:
        name = getattr(r, "name", "") or ""
        author = getattr(r, "author", "") or ""
        desc = getattr(r, "description", "") or ""
        desc_short = desc[:60] + "..." if len(desc) > 60 else desc
        title = f"{name}  — {author}"
        if desc_short:
            title += f"  ({desc_short})"
        choices.append((title, r.url))

    choices.append(("返回", None))

    selected_url = _select(
        f"搜索到 {len(results)} 个结果，选择要下载的小说：",
        choices=choices,
    )

    return selected_url


def do_download(engine, dl, url: str, group: str, format_configs: dict):
    """下载单个小说：获取信息 → 章节列表 → 合并本地 → 下载新章 → 导出。

    Args:
        engine:         下载引擎
        dl:             NovelDownloader 实例
        url:            小说页面 URL
        group:          分组名（用于填充导出路径中的 {group} 占位符）
        format_configs: 导出格式配置 {fmt_name: cfg_dict}
    """
    _log.info("===== 开始下载: %s =====", url)

    storage = Storage(APP_DATA / "storage")

    # ── 1. 获取小说信息 ──────────────────────────────────────────
    print("正在获取小说信息...")
    novel = dl.fetch_novel(url)
    print(f"  书名：{novel.name}")
    print(f"  作者：{novel.author}")
    tags_str = "、".join(novel.tags) if novel.tags else ""
    print(f"  标签：{tags_str}")
    print(f"  字数：{novel.count or '未知'}")
    storage.save_meta(novel)

    # ── 2. 获取章节列表 ──────────────────────────────────────────
    print("正在获取章节列表...")
    chapters = dl.fetch_chapter_list(novel)
    print(f"  共 {len(chapters)} 章")
    novel.update_chapter(chapters)

    # ── 3. 合并本地已有进度 ──────────────────────────────────────
    local_chapters = storage.load_chapters(novel.id)
    if local_chapters:
        novel.update_chapter(local_chapters)

    # ── 4. 筛选未下载章节 ────────────────────────────────────────
    incomplete = novel.chapters.get_incompleted_chapters()
    target = list(incomplete) if incomplete else []
    if not target:
        print("所有章节已下载完毕！")
    else:
        print(f"待下载: {len(target)} 章")
        try:
            downloaded = dl.download_chapters(target)
            print(f"  下载完成: {len(downloaded)} 章")
        except AntiCrawlError:
            print("⚠ 触发反爬，保存已下载部分...")
            if dl.partial:
                storage.save_chapter(novel, dl.partial)
                storage.save_progress(dl.progress, novel.id)
                novel.update_chapter(dl.partial)
            raise
        else:
            storage.save_chapter(novel, downloaded)
            storage.save_progress(dl.progress, novel.id)
            novel.update_chapter(downloaded)

    # ── 5. 导出 ──────────────────────────────────────────────────
    print("正在导出...")
    _do_export(novel, group, format_configs)
    print(f"  导出完成 → app_data/export/{group}/")


def _do_export(novel, group: str, format_configs: dict):
    """执行导出。

    从配置中读取 output_path 模板，填充 {group} 和 {file_name_template}，
    然后传给各导出器。TXT/EPUB 的 output_path 是精确文件路径，
    IMG 的 output_path 是图片输出目录。
    """
    registered = get_exporters()
    export_options_map = get_exporter_options()

    for fmt, fmt_cfg in format_configs.items():
        if not fmt_cfg.get("enabled", True):
            continue

        exporter_cls = registered.get(fmt)
        if exporter_cls is None:
            _log.debug("跳过未知格式: %s", fmt)
            continue

        opt_cls = export_options_map.get(fmt)
        if opt_cls is None:
            _log.debug("跳过无选项类的格式: %s", fmt)
            continue

        # 构建 output_path：填充 {group} 和 {file_name_template}
        raw_path = fmt_cfg.get("output_path", "")
        raw_path = raw_path.replace("{group}", group)
        raw_path = raw_path.replace(
            "{file_name_template}", fmt_cfg.get("file_name_template", "{name}")
        )
        # TXT / EPUB 追加扩展名
        if fmt != "img":
            ext = fmt_cfg.get("extension", "default")
            if ext == "default":
                ext = f".{fmt}"
            raw_path = raw_path + ext

        # 从格式配置提取其他构造参数
        extra = {}
        for k in ("encoding", "file_name_template", "extension",
                   "css_style", "include_toc"):
            if k in fmt_cfg:
                extra[k] = fmt_cfg[k]

        export_opts = opt_cls(output_path=raw_path, **extra)
        exporter = exporter_cls(options=export_opts, novel=novel)
        exporter.export(novel.chapters)
        _log.info("Exported: %s → %s", fmt, raw_path)


def do_update(engine, dl, group: str, format_configs: dict):
    """扫描 storage 目录下所有已下载小说，支持单选/全选更新。"""
    storage = Storage(APP_DATA / "storage")
    storage_dir = APP_DATA / "storage"

    if not storage_dir.exists():
        print("未找到已下载的小说（storage 目录不存在）")
        return

    novel_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
    if not novel_dirs:
        print("未找到已下载的小说")
        return

    # 收集所有小说的元数据
    novels_info = []
    for d in novel_dirs:
        meta = storage.load_meta(d.name)
        if meta:
            novels_info.append(meta)

    if not novels_info:
        print("未找到有效的小说元数据")
        return

    print(f"\n找到 {len(novels_info)} 本已下载小说：")
    for i, novel in enumerate(novels_info, 1):
        local = storage.load_chapters(novel.id)
        downloaded = len(local) if local else 0
        print(f"  {i}. {novel.name}  (已下载 {downloaded} 章)")

    # 让用户选择
    choices = [(f"{n.name}  — {n.author}", n) for n in novels_info]
    choices.append(("▸ 全部更新", "all"))
    choices.append(("返回", None))

    selection = _select("选择要更新的小说：", choices=choices)

    if selection is None:
        return

    targets = novels_info if selection == "all" else [selection]

    for novel in targets:
        print(f"\n── 正在更新: {novel.name} ──")
        try:
            do_download(engine, dl, novel.url, group, format_configs)
        except AntiCrawlError:
            print("⚠ 触发反爬，更新中断（已保存部分进度）")
        except Exception as e:
            print(f"✗ 更新失败: {e}")
            _log.exception("update failed: %s", novel.name)

    print("\n更新完成！")


# ═══════════════════════════════════════════════════════════════════
# 主菜单
# ═══════════════════════════════════════════════════════════════════

def main():
    _log.info("===== novel-downloader CLI start =====")

    # 加载配置
    cfg = load_main_config()
    group = cfg.get("group", "default")
    mode = cfg.get("mode", "browser")
    site_cfg = load_site_config("fanqie")
    format_configs = load_format_configs()

    if not format_configs:
        _log.warning("未找到导出格式配置（app_data/config/formats/ 为空）")

    options = build_options(cfg, site_cfg)

    # 初始化引擎和下载器
    print(f"模式: {mode}  |  分组: {group}")
    _log.debug("creating engine: mode=%s", mode)
    engine = create_engine(options)
    dl = NovelDownloader(engine, options=options)

    try:
        while True:
            action = _select(
                f"当前分组: {group}  |  模式: {mode}",
                choices=[
                    ("🔑 登录", "login"),
                    ("🔍 搜索 & 下载", "search"),
                    ("🔄 更新已下载", "update"),
                    ("📥 直接下载 (输入 URL)", "download"),
                    ("退出", "quit"),
                ],
            )

            if action is None or action == "quit":
                break

            elif action == "login":
                do_login(engine)

            elif action == "search":
                url = do_search(engine, dl)
                if url:
                    try:
                        do_download(engine, dl, url, group, format_configs)
                    except AntiCrawlError:
                        print("⚠ 触发反爬，下载中断（已保存部分进度）")
                    except Exception as e:
                        print(f"✗ 下载失败: {e}")
                        _log.exception("download failed")

            elif action == "download":
                url = _text_input(
                    "请输入小说链接（如 https://fanqienovel.com/page/...）："
                )
                if url and url.strip():
                    try:
                        do_download(engine, dl, url.strip(), group, format_configs)
                    except AntiCrawlError:
                        print("⚠ 触发反爬，下载中断（已保存部分进度）")
                    except Exception as e:
                        print(f"✗ 下载失败: {e}")
                        _log.exception("download failed")

            elif action == "update":
                try:
                    do_update(engine, dl, group, format_configs)
                except Exception as e:
                    print(f"✗ 更新失败: {e}")
                    _log.exception("update failed")

            print()  # 空行分隔

    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        engine.close()
        _log.info("===== novel-downloader CLI end =====")


if __name__ == "__main__":
    main()

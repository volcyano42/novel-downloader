"""UI 冒烟：headless Chromium 逐路径截图 + 断言。用法见 --help。"""
import argparse, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CHECKS = [
    # (路径, 期望落地的 pathname, 必须可见的文本)
    ("/bookshelf", "/bookshelf", "书架"),
    ("/downloads", "/downloads", "下载"),
    ("/settings/sources", "/settings/sources", "书源"),
    ("/settings/download", "/settings/download", "并发与性能"),
    ("/settings/export", "/settings/export", "导出格式"),
    ("/settings/notify", "/settings/notify", "通知"),
    ("/settings", "/settings/sources", "书源"),
    ("/sources", "/settings/sources", "书源"),
    ("/search-tab", "/search-tab", "搜索"),
]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:4173")
    ap.add_argument("--out", default="../tmp/nld-ui-smoke",
                    help="截图输出目录；默认落到仓库外的 ../tmp/（仓库 .gitignore 不忽略 tmp/，"
                         "默认值必须避免在仓库内落盘）")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: list[str] = []
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
        page.on("console",
                lambda m: console_errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        for path, expect_path, expect_text in CHECKS:
            console_errors.clear()
            # 不用 networkidle：本应用有 React Query 轮询与 SSE，网络可能长期不空闲
            page.goto(args.base_url + path, wait_until="domcontentloaded")
            name = (path.strip("/") or "root").replace("/", "-") + ".png"
            try:
                page.get_by_text(expect_text, exact=False).first.wait_for(state="visible", timeout=20000)
                text_seen = True
            except Exception:
                text_seen = False
            page.screenshot(path=str(out / name), full_page=True)
            if page.url.split(args.base_url)[-1] != expect_path:
                failures.append(f"失败 {path}: 落地路径 {page.url} != {expect_path}")
            elif not text_seen:
                failures.append(f"失败 {path}: 未找到文本 {expect_text!r}"
                                + (f"（页面报错：{console_errors[:2]}）" if console_errors else ""))
            elif console_errors:
                failures.append(f"失败 {path}: 页面运行时报错 {console_errors[:2]}")
            else:
                print(f"完成 {path} -> {out / name}")

        # 附加 1（Review Focus #1）：深层链接刷新后仍可达
        page.goto(args.base_url + "/settings/export", wait_until="domcontentloaded")
        page.reload(wait_until="domcontentloaded")
        try:
            page.get_by_text("导出格式", exact=False).first.wait_for(state="visible", timeout=20000)
            print("完成 /settings/export（刷新后仍可达）")
        except Exception:
            failures.append("失败 /settings/export: 刷新后未渲染「导出格式」")

        # 附加 2（Review Focus #2）：停在子路由时全局侧边栏仍高亮「设置」
        page.goto(args.base_url + "/settings/download", wait_until="domcontentloaded")
        try:
            page.get_by_text("并发与性能", exact=False).first.wait_for(state="visible", timeout=20000)
        except Exception:
            failures.append("失败 /settings/download: 未渲染「并发与性能」")
        cls = page.locator("aside a").filter(has_text="设置").first.get_attribute("class") or ""
        if "bg-indigo-50" in cls:
            print("完成 全局导航在 /settings/download 下高亮「设置」")
        else:
            failures.append(f"失败 全局导航未高亮「设置」（class={cls!r}）")

        # 附加 3（Review Focus #3）：窄屏（< md）下二级导航四项可见
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(args.base_url + "/settings/sources", wait_until="domcontentloaded")
        for lbl in ("书源", "下载与性能", "导出格式", "通知"):
            try:
                mobile.get_by_role("link", name=lbl).first.wait_for(state="visible", timeout=20000)
                print(f"完成 窄屏二级导航可见: {lbl}")
            except Exception:
                failures.append(f"失败 窄屏二级导航不可见: {lbl}")
        mobile.screenshot(path=str(out / "settings-mobile.png"), full_page=True)
        mobile.close()
        browser.close()
    for f in failures:
        print(f, file=sys.stderr)
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())

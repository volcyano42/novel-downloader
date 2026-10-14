"""UI 冒烟：headless Chromium 逐路径截图 + 断言。用法见 --help。"""
import argparse, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CHECKS = [
    # (路径, 期望落地的 pathname, 必须可见的文本)
    ("/bookshelf", "/bookshelf", "书架"),
    ("/downloads", "/downloads", "下载"),
    ("/settings", "/settings", "书源"),
    ("/sources", "/settings", "书源"),
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
        browser.close()
    for f in failures:
        print(f, file=sys.stderr)
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())

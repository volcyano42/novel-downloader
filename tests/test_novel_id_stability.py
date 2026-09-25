"""id 稳定性：重构不得改变书源生成/返回的 url（防 novel_id 漂移，spec:255）。

`Novel.id = make_novel_id(novel.url)`，而 `novel.url` 由书源自身的 url
拼接逻辑决定。因此只要书源的 url 生成逻辑（域名 / 路径模板）被改动，
存量小说的 id 就会漂移。本模块以 **离线、无网络、无浏览器** 的方式锁死它：

1. `test_source_url_templates_unchanged`：用 `ast` 提取每个书源能力模块里的
   URL 模板（含 `://` 的字符串常量，以及 f-string 拼接出的模板），与写死的
   快照**逐字**比对。改动任一书源的 url 生成逻辑（如把
   `https://fanqienovel.com/page/{}` 改成 `.../html/{}`、改 92xs 的域名）
   → 快照不等 → 变红（变异验证见 final-fix-report.md）。
2. `test_92xs_novel_info_passes_url_through`：真调 `92xs.novel_info`（stub engine），
   断言返回的 `novel.url` 与输入 `/book/{id}.html` 逐字一致——若书源改为把它
   「规范化」成 `/html/{id}/` 则变红。
3. `test_make_novel_id_stable_for_typical_urls`：`make_novel_id` 哈希本身稳定。
"""
import asyncio
import ast
import importlib
from pathlib import Path

from novelbase.utils.urls import make_novel_id

SOURCES = Path(__file__).resolve().parents[1] / "novelbase" / "sources"

# {source_name: (典型 novel.url, make_novel_id(url))}
STABLE = {
    "92xs-requests-default":   ("http://www.92xs.info/book/9999.html", "293af2df7c5561ec56995462caf24871"),
    "fanqie-requests-default": ("https://fanqienovel.com/page/7123456789012345678", "ace9f3fa0bbb2f9f5dff75687612cda2"),
    "qidian-requests-default": ("https://www.qidian.com/book/1012345678/", "be10875dc3ca3985813a83110d18c92c"),
    "qimao-requests-default":  ("https://www.qimao.com/shuku/195958/", "4afb6803aa4d6440123faa8affbe6612"),
}


# 书源 url 生成逻辑的快照：{相对 sources/ 的路径: [url 模板...]}
# 提取：含 "://" 的裸字符串常量 + f-string 拼接模板（常量段拼接、插值处记为 "{}"）。
EXPECTED_URL_TEMPLATES: dict[str, list[str]] = {
    "92xs_requests_default/chapter_list.py": [
        "http://www.92xs.info",
        "http://www.92xs.info/html/{}/",
    ],
    "92xs_requests_default/novel_info.py": [
        "http://www.92xs.info{}",
    ],
    "92xs_requests_default/search.py": [
        "http://www.92xs.info",
        "http://www.92xs.info/modules/article/search.php",
    ],
    "fanqie_api_oiapi/chapter_content.py": [
        "https://oiapi.net/api/FqRead",
    ],
    "fanqie_api_oiapi/chapter_list.py": [
        "https://fanqienovel.com/reader/",
        "https://oiapi.net/api/FqRead",
    ],
    "fanqie_api_oiapi/novel_info.py": [
        "https://fanqienovel.com/page/{}",
        "https://oiapi.net/api/FqRead",
    ],
    "fanqie_api_oiapi/search.py": [
        "https://fanqienovel.com/page/{}",
        "https://oiapi.net/api/FqRead",
    ],
    "fanqie_api_rain/chapter_content.py": [
        "https://v3.rain.ink/fanqie/?apikey={}",
    ],
    "fanqie_api_rain/chapter_list.py": [
        "https://fanqienovel.com/reader/{}",
        "https://v3.rain.ink/fanqie/?apikey={}",
    ],
    "fanqie_api_rain/novel_info.py": [
        "https://fanqienovel.com/page/{}",
        "https://v3.rain.ink/fanqie/?apikey={}",
    ],
    "fanqie_api_rain/search.py": [
        "https://fanqienovel.com/page/{}",
        "https://v3.rain.ink/fanqie/?apikey={}",
    ],
    "fanqie_browser_default/chapter_content.py": [
        "https://fanqienovel.com/reader/{}",
    ],
    "fanqie_browser_default/chapter_list.py": [
        "https://fanqienovel.com/page/",
        "https://fanqienovel.com/page/{}",
        "https://fanqienovel.com/reader/",
    ],
    "fanqie_browser_default/novel_info.py": [
        "https://fanqienovel.com/page/{}",
    ],
    "fanqie_browser_default/search.py": [
        "https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/?aid=1967&offset=0&q={}",
        "https://fanqienovel.com/page/{}",
    ],
    "fanqie_requests_default/chapter_content.py": [
        "https://fanqienovel.com/reader/{}",
    ],
    "fanqie_requests_default/chapter_list.py": [
        "https://fanqienovel.com/page/",
        "https://fanqienovel.com/page/{}",
        "https://fanqienovel.com/reader/",
    ],
    "fanqie_requests_default/novel_info.py": [
        "https://fanqienovel.com/page/{}",
    ],
    "fanqie_requests_default/search.py": [
        "https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/?aid=1967&offset=0&q={}",
        "https://fanqienovel.com/page/{}",
    ],
    "qidian_browser_default/search.py": [
        "https://www.qidian.com/so/{}.html",
    ],
    "qimao_api_rain/chapter_content.py": [
        "https://v3.rain.ink/qimao/?apikey={}&{}",
    ],
    "qimao_api_rain/chapter_list.py": [
        "https://v3.rain.ink/qimao/?apikey={}&{}",
        "https://www.qimao.com/shuku/{}-{}/",
    ],
    "qimao_api_rain/novel_info.py": [
        "https://v3.rain.ink/qimao/?apikey={}&{}",
        "https://www.qimao.com/shuku/{}/",
    ],
    "qimao_api_rain/search.py": [
        "https://v3.rain.ink/qimao/?apikey={}&{}",
        "https://www.qimao.com/shuku/{}/",
    ],
    "qimao_browser_default/chapter_list.py": [
        "https://www.qimao.com/shuku/{}/",
        "https://www.qimao.com{}",
    ],
    "qimao_browser_default/novel_info.py": [
        "https://www.qimao.com/shuku/{}/",
    ],
    "qimao_browser_default/search.py": [
        "https://www.qimao.com/search/index/?keyword={}",
    ],
    "qimao_requests_default/chapter_list.py": [
        "https://www.qimao.com/shuku/{}/",
        "https://www.qimao.com{}",
    ],
    "qimao_requests_default/novel_info.py": [
        "https://www.qimao.com/shuku/{}/",
    ],
    "qimao_requests_default/search.py": [
        "https://www.qimao.com/search/index/?keyword={}",
        "https://www.qimao.com/search/index/?keyword={}&page={}",
    ],
}

# novel_info 直接透传输入 url 的书源（其 novel.url == 输入 url，不得「规范化」）
PASSTHROUGH_NOVEL_INFO = ("qidian_requests_default",)


def _collect_url_templates(root: Path) -> dict[str, list[str]]:
    """用 ast 提取每个能力模块里的 url 模板。"""
    out: dict[str, list[str]] = {}
    for p in sorted(root.rglob("*.py")):
        if p.name == "__init__.py":
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        templates: set[str] = set()
        skip: set[int] = set()
        # f-string：把常量段拼成模板，插值处记 "{}"
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                skip.update(id(x) for x in ast.walk(node))
                s = "".join(
                    v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
                    for v in node.values
                )
                if "://" in s:
                    templates.add(s)
        # 裸字符串常量（跳过已并入 f-string 模板的片段）
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in skip:
                    continue
                if "://" in node.value:
                    templates.add(node.value)
        if templates:
            out[p.relative_to(root).as_posix()] = sorted(templates)
    return out


def test_make_novel_id_stable_for_typical_urls():
    for source_name, (url, expected) in STABLE.items():
        assert make_novel_id(url) == expected, source_name


def test_source_url_templates_unchanged():
    """书源 url 生成逻辑（域名/路径模板）逐字不变。"""
    actual = _collect_url_templates(SOURCES)
    assert actual == EXPECTED_URL_TEMPLATES, (
        "书源 url 生成逻辑发生变化（会导致 novelty_id 漂移）:\n"
        f"新增/修改: {set(actual) ^ set(EXPECTED_URL_TEMPLATES) or '（键相同，比对值）'}"
    )


def test_passthrough_novel_info_has_no_url_literal():
    """透传型书源 novel_info 里没有 url 模板（不构造/规范化 novel.url）。

    对**实际扫描结果**断言（`_collect_url_templates` 读源码 AST），而非对静态
    常量断言：若该文件新增含 `://` 的字面量（即开始构造/规范化 novel.url），
    `scanned` 会包含该键 → 变红。
    """
    scanned = _collect_url_templates(SOURCES)
    for src in PASSTHROUGH_NOVEL_INFO:
        key = f"{src}/novel_info.py"
        assert (SOURCES / key).is_file(), f"被检查的源码文件不存在：{SOURCES / key}"
        assert key not in scanned, (
            f"{key} 含 url 模板，透传型书源不得构造/规范化 novel.url：{scanned.get(key)}"
        )

class _StubEngine:
    """最小 engine stub：只提供 novel_info 需要的两个协程（不联网）。"""

    async def async_fetch_text(self, url, **kwargs):
        return "<html><body></body></html>"

    async def async_fetch_images(self, urls):
        return [b"" for _ in urls]


def test_92xs_novel_info_passes_url_through():
    """92xs novel_info 透传输入 url，不得把 /book/{id}.html 规范化为 /html/{id}/。"""
    mod = importlib.import_module("novelbase.sources.92xs_requests_default.novel_info")
    url = "http://www.92xs.info/book/9999.html"
    novel = asyncio.run(mod.novel_info(url, _StubEngine()))
    assert novel.url == url

"""id 稳定性：重构不得改变书源返回的 url（防 novel_id 漂移，spec:255）。

两层兜底：
1. 每个书源典型 novel.url 的 make_novel_id 输出写死哈希（迁移前实测值）；
2. 静态断言 92xs novel_info 不把 /book/{id}.html 规范化为 /html/{id}/。
"""
from pathlib import Path

from novelbase.utils.urls import make_novel_id

SOURCES = Path(__file__).resolve().parents[1] / "novelbase" / "sources"

# {source_name: (典型 novel.url, 迁移前 make_novel_id(url) 前 32 位)}
STABLE = {
    "92xs-requests-default":   ("http://www.92xs.info/book/9999.html", "293af2df7c5561ec56995462caf24871"),
    "fanqie-requests-default": ("https://fanqienovel.com/page/7123456789012345678", "ace9f3fa0bbb2f9f5dff75687612cda2"),
    "qidian-requests-default": ("https://www.qidian.com/book/1012345678/", "be10875dc3ca3985813a83110d18c92c"),
    "qimao-requests-default":  ("https://www.qimao.com/shuku/195958/", "4afb6803aa4d6440123faa8affbe6612"),
}


def test_make_novel_id_stable_for_typical_urls():
    for source_name, (url, expected) in STABLE.items():
        assert make_novel_id(url) == expected, source_name


def test_92xs_novel_info_url_not_normalized():
    """92xs novel_info 透传输入 url，不得把 /book/{id}.html 规范化为 /html/{id}/。"""
    src = (SOURCES / "92xs_requests_default" / "novel_info.py").read_text(encoding="utf-8")
    assert "/html/" not in src

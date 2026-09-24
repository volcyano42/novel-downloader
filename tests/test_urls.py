import re

from novelbase.utils.urls import make_novel_id


def test_make_novel_id_consistent():
    url = "https://fanqienovel.com/page/7123456789012345678"
    assert make_novel_id(url) == make_novel_id(url)


def test_make_novel_id_different_urls_differ():
    assert make_novel_id("https://fanqienovel.com/page/1") != make_novel_id("https://fanqienovel.com/page/2")


def test_make_novel_id_format_32hex():
    assert re.fullmatch(r"[0-9a-f]{32}", make_novel_id("https://x.com/y"))


def test_make_novel_id_is_filename_safe():
    """id 会当文件名（{id}.db）与 URL 路径段用，必须不含 "/" ":" 等字符。"""
    assert re.fullmatch(r"[0-9a-f]{32}", make_novel_id("http://www.92xs.info/book/536.html?a=1#f"))


def test_make_novel_id_differs_on_url_form():
    """已知行为：不对 url 做规范化，故同一本书的不同 url 形态会得到不同 id。

    92xs 的 /book/{id}.html 与 /html/{id}/ 是两个 id——入库与后续使用必须保持同一形态。
    （旧实现用平台特例把它们归一；现在归一由书源负责，core 不再兜底。）
    """
    a = make_novel_id("http://www.92xs.info/book/536.html")
    b = make_novel_id("http://www.92xs.info/html/536/")
    assert a != b

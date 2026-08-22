import re

from novelbase.utils.urls import canonical_book_url, make_novel_id


def test_make_novel_id_consistent():
    url = "https://fanqienovel.com/page/7123456789012345678"
    assert make_novel_id(url) == make_novel_id(url)


def test_make_novel_id_different_urls_differ():
    assert make_novel_id("https://fanqienovel.com/page/1") != make_novel_id("https://fanqienovel.com/page/2")


def test_make_novel_id_format_32hex():
    assert re.fullmatch(r"[0-9a-f]{32}", make_novel_id("https://x.com/y"))


def test_canonical_lowercase_and_drop_query_fragment():
    assert canonical_book_url("https://FanqieNovel.com/page/123?a=1#frag", "fanqie") \
        == "https://fanqienovel.com/page/123"


def test_canonical_trailing_slash_removed():
    assert canonical_book_url("https://www.qidian.com/book/123/", "qidian") \
        == "https://www.qidian.com/book/123"


def test_canonical_92xs_book_to_html():
    assert canonical_book_url("http://www.92xs.info/book/456.html", "92xs") \
        == "http://www.92xs.info/html/456/"


def test_canonical_92xs_html_kept():
    assert canonical_book_url("http://www.92xs.info/html/456/", "92xs") \
        == "http://www.92xs.info/html/456/"


def test_canonical_qidian_info_to_book():
    assert canonical_book_url("https://www.qidian.com/info/123/", "qidian") \
        == "https://www.qidian.com/book/123"


def test_canonical_qidian_book_kept():
    assert canonical_book_url("https://www.qidian.com/book/123/", "qidian") \
        == "https://www.qidian.com/book/123"

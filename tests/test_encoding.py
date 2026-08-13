# tests/test_encoding.py
from novelbase.utils.encoding import detect_encoding


def test_detect_encoding_utf8():
    content = "中文内容测试".encode("utf-8")
    assert detect_encoding(content) in ("utf-8", "utf_8", "utf8")


def test_detect_encoding_gbk():
    content = "中文内容".encode("gbk")
    result = detect_encoding(content).lower()
    assert result in ("gb18030", "gbk", "gb2312", "cp936")


def test_detect_encoding_gbk_long():
    content = "这是一段比较长的中文测试文本用来验证编码探测的准确性".encode("gbk")
    result = detect_encoding(content).lower()
    assert result in ("gb18030", "gbk", "gb2312", "cp936")


def test_detect_encoding_empty_returns_utf8():
    assert detect_encoding(b"") == "utf-8"

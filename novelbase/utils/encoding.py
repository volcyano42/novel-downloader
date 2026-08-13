# novelbase/utils/encoding.py
"""字节流编码探测 — 替代 requests 的 apparent_encoding（httpx 无此属性）。"""
from __future__ import annotations


def detect_encoding(content: bytes) -> str:
    """探测 bytes 的文本编码，优先 chardet，回退 utf-8。

    Args:
        content: 原始字节内容。

    Returns:
        探测出的编码名（如 "utf-8"、"GB18030"），无法探测时返回 "utf-8"。
    """
    if not content:
        return "utf-8"
    try:
        import chardet

        result = chardet.detect(content)
        enc = result.get("encoding")
        if enc:
            # chardet 返回 GB2312 时用 GB18030（超集）避免生僻字乱码
            if enc.lower() in ("gb2312", "gbk"):
                return "GB18030"
            return enc
    except ImportError:
        pass
    return "utf-8"

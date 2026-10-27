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
            enc_lower = enc.lower()
            # chardet 返回 GB2312/GBK 时用 GB18030（超集）避免生僻字乱码
            if enc_lower in ("gb2312", "gbk"):
                return "GB18030"
            if enc_lower in ("utf-8", "utf_8", "utf8", "gb18030", "big5"):
                return enc
            # chardet 对短文本可能误判（confidence 低且非中文/UTF-8），如把 GBK
            # 短文本判成 IBM855。低 confidence 时用 GB18030 试解码，成功且含 CJK
            # 字符则认定为中文。
            if result.get("confidence", 1.0) < 0.5:
                try:
                    text = content.decode("gb18030")
                except UnicodeDecodeError:
                    pass
                else:
                    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
                        return "GB18030"
            return enc
    except ImportError:
        pass
    return "utf-8"

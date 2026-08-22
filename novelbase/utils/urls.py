"""URL 规范化与 Novel.id 生成工具（Novel.id = sha256(canonical_url)[:32]）。"""

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit


def canonical_book_url(url: str, platform: str) -> str:
    """书源完整 URL 规范化：小写 scheme/host、去 query/fragment、去尾斜杠。

    platform 特例：
    - 92xs：/book/{id}.html 与 /html/{id}/ 统一为 http://www.92xs.info/html/{id}/
      （与 chapter_list 现行规则一致）
    - qidian：/info/{id}/ 统一为 /book/{id}/（BOOK_URL_TEMPLATE 标准形态）
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path
    if path not in ("", "/"):
        path = path.rstrip("/")
    result = urlunsplit((scheme, netloc, path, "", ""))

    if platform == "92xs":
        m = re.search(r"(?:/book/|/html/)(\d+)", path)
        if m:
            result = f"http://www.92xs.info/html/{m.group(1)}/"
    elif platform == "qidian":
        m = re.search(r"/info/(\d+)", path)
        if m:
            result = f"https://www.qidian.com/book/{m.group(1)}"
    return result


def make_novel_id(canonical_url: str) -> str:
    """由 canonical url 生成 32 位 hex 的 Novel.id（sha256 前 32 字符）。"""
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:32]

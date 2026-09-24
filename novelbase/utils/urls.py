"""Novel 的物理文件名 / 对外标识：sha256(url) 前 32 位。

- 书源返回的 url **原样**存入库内 `meta.id`（可读、可按 url 查书）
- 磁盘文件名与对外标识（API / 前端 / CLI 用的 id）用 `sha256(url)[:32]`：
  url 含 "/" ":" 等字符，直接作文件名在 Windows 上非法，作 URL 路径段会被截断
  （实测：Starlette 路由参数接不住，而且 `%2F` 也会被 ASGI 解码回 "/"）
"""

import hashlib


def make_novel_id(url: str) -> str:
    """由书源返回的原始 url 生成 32 位 hex 标识（sha256 前 32 字符）。

    幂等：同 url 结果相同；不同 url 结果不同。
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]

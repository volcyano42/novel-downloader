"""正文内容（番茄 app API）— 任意章节尚未打通，首章可通过 detail 接口获取。

任意章节正文接口：GET https://api.fanqiesdk.com/api/novel/book/reader/content/v1
参数：公共参数链 + book_id / item_id / support_image / epub_parser_level / advanced

已知限制（2026-08-23 实测）：
- 四件套签名（x-gorgon/x-argus/x-ladon/x-khronos）已解锁搜索/详情/全量目录等接口；
- 但 content 正文接口返回 1101001 —— 需正确 `y` 加密头 + 有效设备会话
  （registerkey 返回 500002 verify fail，需真实注册设备，metasec fp 由 native 生成）。
- 可用正文来源一：detail 接口 data.content 返回首章明文 HTML（无需 y/registerkey，
  2026-08-23 实测 code=0，正文 1862 字与第 1 章 chapter_word_number 一致）——见
  first_chapter_content()。
- 可用正文来源二：detail 接口 data.chapter_item / 相关字段可能含更多信息（未深挖）。
详见 privacy/_analysis/api_report.md §5.1c/§5.1d。
"""
import re

from novelbase.core.exceptions import ChapterNotFoundError, NovelNotFoundError
from ._client import HOST_APP, common_params, signed_get_json
from ..._common import standardize_id


async def chapter_content(chapter, engine, **kwargs) -> None:
    """任意章节正文 —— 暂不可用（app 逆向方案已放弃，2026-08-24 实测：
    模拟器 ARM 转译下 frida/HTTP 通道触发成功率低 + 单章超时 280s，不可用于批量下载；
    详见 privacy/逆向分析-番茄小说API-进展.md §6.9/§6.10）。"""
    book_id = standardize_id(chapter.novel_id)
    item_id = standardize_id(chapter)
    raise ChapterNotFoundError(
        f"appapi 任意章节正文不可用（app 逆向方案已放弃，需真机 frida 或 web 接口）："
        f"book_id={book_id} item_id={item_id}"
    )


async def first_chapter_content(url: str, engine, **kwargs) -> str:
    """首章明文正文（detail 接口 data.content，无需 y 头/设备会话）。

    实测（2026-08-23，book_id=7569904647276612670）：
      GET {HOST_APP}/reading/bookapi/detail/v1/?book_id=X（四件套签名）
      → code=0，data.content 为首章 HTML，去标签后 1862 字
        == chapter_list 第 1 章的 chapter_word_number（1862）。

    返回去除 HTML 标签后的纯文本正文；仅适用于**首章**。
    """
    book_id = standardize_id(url)
    params = common_params(engine)
    params["book_id"] = book_id
    data = await signed_get_json(f"{HOST_APP}/reading/bookapi/detail/v1/", params)

    if data.get("code") != 0:
        raise NovelNotFoundError(f"appapi detail 失败: code={data.get('code')} msg={data.get('message')}")

    content = ((data.get("data") or {}).get("content")) or ""
    if not content:
        raise ChapterNotFoundError(f"appapi detail 无 data.content（首章正文）: book_id={book_id}")

    text = re.sub(r"<[^>]+>", "", content)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text

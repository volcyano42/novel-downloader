"""文件名模板构建工具。"""
import re


class SafeDict(dict):
    """str.format_map 用的安全字典：缺失的 key 保留占位符而非抛 KeyError。"""
    def __missing__(self, key):
        return "{" + key + "}"


def sanitize_filename(name: str) -> str:
    """移除文件系统不允许的字符。"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

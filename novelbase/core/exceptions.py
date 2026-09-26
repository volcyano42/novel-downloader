"""novel-downloader 自定义异常体系。

所有自定义异常继承自 ``NovelDownloaderError``，按职责分为：
- 网络层: ``NetworkError``
- 认证层: ``AuthenticationError``
- 资源层: ``NovelNotFoundError``, ``ChapterNotFoundError``
- 解析层: ``ParseError``, ``SourceNotFoundError``
- 功能层: ``FeatureNotSupportedError``
- 存储层: ``StorageError``
- 反爬层: ``AntiCrawlError``
"""


class NovelDownloaderError(Exception):
    """所有自定义异常的基类。"""
    pass


class NetworkError(NovelDownloaderError):
    """网络请求失败。

    包括超时、连接错误、重试耗尽等场景。
    """

    def __init__(self, message: str = "Network request failed", url: str | None = None):
        self.url = url
        detail = f"{message}" + (f": {url}" if url else "")
        super().__init__(detail)


class AuthenticationError(NovelDownloaderError):
    """登录或认证失败。"""

    def __init__(self, platform: str, message: str = "Authentication failed"):
        self.platform = platform
        super().__init__(f"{message}: {platform}")


class NovelNotFoundError(NovelDownloaderError):
    """小说未找到或不支持的 URL。"""

    def __init__(self, message: str = "Novel not found", url: str | None = None):
        self.url = url
        detail = f"{message}" + (f": {url}" if url else "")
        super().__init__(detail)


class ChapterNotFoundError(NovelDownloaderError):
    """章节不存在或无法获取内容。"""

    def __init__(self, message: str = "Chapter not found", url: str | None = None):
        self.url = url
        detail = f"{message}" + (f": {url}" if url else "")
        super().__init__(detail)


class ParseError(NovelDownloaderError):
    """内容解析失败（HTML 结构异常、数据格式不符合预期等）。"""

    def __init__(self, message: str = "Parse error", detail: str | None = None):
        self.detail = detail
        msg = f"{message}" + (f" — {detail}" if detail else "")
        super().__init__(msg)


class SourceNotFoundError(NovelDownloaderError):
    """未找到数据源。"""

    def __init__(self, message: str = "Source not found"):
        super().__init__(message)


class FeatureNotSupportedError(NovelDownloaderError):
    """请求的功能在当前模式下不被支持。"""

    def __init__(self, message: str = "Feature not supported"):
        super().__init__(message)


class ModeUnavailableError(NovelDownloaderError):
    """本环境不支持该引擎 mode（依赖缺失 / 构建时被排除）。

    与 ``FeatureNotSupportedError`` 的区别：后者是「该功能在这个模式下不支持」
    （如某书源的 requests 模式不提供搜索）；本异常是「这个 mode 在本环境根本装不上」
    （如 Android APK 构建时排除了 playwright，无法使用 browser）。
    调用方的可用性判定在 `shared.config.supported_modes()`（环境能力表）；
    本异常只负责让「漏网」得到明确语义，而不是裸 `ImportError`。
    """

    def __init__(self, mode: str, reason: str | None = None):
        self.mode = mode
        self.reason = reason
        detail = f"本环境不支持 {mode} 引擎" + (f"：{reason}" if reason else "")
        super().__init__(detail)


class StorageError(NovelDownloaderError):
    """存储读写操作失败（文件不存在、权限不足、序列化错误等）。"""

    def __init__(self, message: str = "Storage operation failed", path: str | None = None):
        self.path = path
        detail = f"{message}" + (f": {path}" if path else "")
        super().__init__(detail)


class AntiCrawlError(NovelDownloaderError):
    """触发了目标网站的反爬虫策略。

    包括：请求频率过高被限流、IP 被封、需要验证码/人机验证才能继续等场景。
    收到此异常时应考虑增大延迟、切换 IP 或等待冷却。
    """

    def __init__(self,
                 message: str = "Anti-crawl protection triggered",
                 url: str | None = None,
                 retry_after: float | None = None):
        self.url = url
        self.retry_after = retry_after
        parts = [message]
        if url:
            parts.append(f"url={url}")
        if retry_after is not None:
            parts.append(f"retry_after={retry_after}s")
        super().__init__("; ".join(parts))

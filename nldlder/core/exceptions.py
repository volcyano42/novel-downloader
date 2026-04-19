class NovelDownloaderError(Exception):
    pass

class ChapterNotFoundError(NovelDownloaderError):
    def __init__(self, chapter_url: str, message: str = "Chapter not found"):
        self.chapter_url = chapter_url
        super().__init__(f"{message}: {chapter_url}")

class FeatureNotSupportedError(NovelDownloaderError):
    def __init__(self, feature: str, message: str = "Feature not supported"):
        self.feature = feature
        super().__init__(f"{message}: {feature}")
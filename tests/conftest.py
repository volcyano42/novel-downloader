import pytest

from novelbase.models.novel import Illustration, Chapter, Chapters, Novel, SearchResult

# ── Illustration fixtures ─────────────────────────────────────

@pytest.fixture
def img_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 20  # 模拟 PNG 头部

@pytest.fixture
def illustration(img_bytes: bytes) -> Illustration:
    return Illustration(raw_data=img_bytes, alt="封面", insert=0, url="https://example.com/cover.png")

# ── Chapter fixtures ──────────────────────────────────────────

@pytest.fixture
def chapter_1() -> Chapter:
    return Chapter(
        id="ch1", url="https://example.com/novel/ch1",
        novel_id="https://example.com/novel",
        title="第一章 开端", order=1, volume="第一卷",
        content="这是第一章的内容。", time=1000.0, count=1200,
    )

@pytest.fixture
def chapter_2() -> Chapter:
    return Chapter(
        id="ch2", url="https://example.com/novel/ch2",
        novel_id="https://example.com/novel",
        title="第二章 发展", order=2, volume="第一卷",
        content="这是第二章的内容。", time=2000.0, count=1500,
    )

@pytest.fixture
def chapter_3_incomplete() -> Chapter:
    return Chapter(
        id="ch3", url="https://example.com/novel/ch3",
        novel_id="https://example.com/novel",
        title="第三章 未完", order=3, volume="第二卷",
        content=None, time=None, count=None,
        
    )

@pytest.fixture
def chapters(chapter_1, chapter_2, chapter_3_incomplete) -> Chapters:
    return Chapters([chapter_1, chapter_2, chapter_3_incomplete])

# ── Novel fixtures ────────────────────────────────────────────

@pytest.fixture
def novel(chapters: Chapters, illustration: Illustration) -> Novel:
    return Novel(
        title="测试小说", url="https://example.com/novel",
        id="novel123", serial=3, author="测试作者",
        description="这是一本测试小说。",
        tags=["奇幻", "测试"], count=100000,
        cover=illustration, chapters=chapters,
    )

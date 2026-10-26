import pytest

from novelbase.models.novel import Illustration, Chapter, Chapters, Novel, SearchResult


@pytest.fixture(autouse=True)
def _isolate_nld_env(monkeypatch):
    """隔离 NLD_* 环境变量，防止跨用例泄漏。"""
    monkeypatch.delenv("NLD_APP_DATA", raising=False)


@pytest.fixture(autouse=True)
def _isolate_user_data_paths(monkeypatch, tmp_path):
    """把 `shared.user_data` 的四个路径常量指到 tmp_path。

    这里是 autouse 而不是让每个测试自带 fixture：曾经有过一次真实的翻车 ——
    某个测试只隔离了新常量，而实现当时还走旧的 `DB_PATH`，结果对用户真实的
    `app_data/storage/users/default/user_data.db` 执行了 `DELETE FROM
    search_history`，清掉了 10 条搜索历史。默认隔离比“记得隔离”可靠。

    各测试文件自己的 `lib` fixture 会再覆盖一遍（幂等，路径同源）。
    """
    from shared import user_data

    library = tmp_path / "_isolated_library"
    monkeypatch.setattr(user_data, "LIBRARY_DIR", library)
    monkeypatch.setattr(user_data, "BOOKS_PATH", library / "books.yaml")
    monkeypatch.setattr(user_data, "HISTORY_PATH", library / "search_history.jsonl")
    monkeypatch.setattr(user_data, "NOVELS_DIR", tmp_path / "_isolated_novels")
    monkeypatch.setattr(user_data, "_next_id_cache", None)

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


# ═══════════════════════════════════════════════════════════
# 红名单书源缺席时的整模块跳过
# ═══════════════════════════════════════════════════════════
#
# 这 7 个源不进仓库（见 scripts/migrate_private_sources_out.py），装在用户源根
# <APP_DATA>/sources 里。新机器 / 公开子集没有它们时，下列测试模块会因为书源
# 不存在而必然失败 —— 那是「环境没装源」，不是「代码坏了」，所以整模块 skip
# 而不是让 pytest 变红。源装回去后自动恢复跑。

_PRIVATE_SOURCE_NAMES = (
    "92xs-requests-default",
    "qidian-requests-default",
    "qidian-browser-default",
    "qimao-requests-default",
    "qimao-browser-default",
    "qimao-api-rain",
    "fanqie-api-rain",
)

# 无红名单源时必然失败的模块（2026-10-26 实测得出，非估计）。
_PRIVATE_DEPENDENT_MODULES = frozenset({
    "test_backend_config_routes",
    "test_backend_download_routes",
    "test_cli_effective_mode",
    "test_config_effective_mode",
    "test_delay_default",
    "test_engine_hot_update",
    "test_source_api",
    "test_source_contracts",
    "test_source_names_unique",
    "test_task_manager_async",
})


def _missing_private_sources() -> list[str]:
    """缺失的红名单源；发现层出错（撞名等）时不在此处拦，交给测试自身暴露。"""
    try:
        from novelbase.source import list_sources

        present = set(list_sources())
    except Exception:  # noqa: BLE001 - collect 阶段不应因环境问题中断整轮收集
        return []
    return [name for name in _PRIVATE_SOURCE_NAMES if name not in present]


def pytest_collection_modifyitems(config, items):
    missing = _missing_private_sources()
    if not missing:
        return
    reason = (
        f"红名单书源未安装（{len(missing)}/{len(_PRIVATE_SOURCE_NAMES)} 缺失："
        f"{', '.join(missing)}）—— 见 scripts/migrate_private_sources_out.py"
    )
    for item in items:
        module = getattr(item, "module", None)
        if module is None:
            continue
        short = module.__name__.rsplit(".", 1)[-1]
        if short in _PRIVATE_DEPENDENT_MODULES:
            item.add_marker(pytest.mark.skip(reason=reason))

"""check_public 迁移校验测试 — 三道防线（缺失/多余/敏感）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_public

# 与真实 pyproject.toml [tool.novel-downloader.migration] exclude 一致的非迁移清单
EXCLUDE = [
    "novelbase/sources/qidian/**",
    "novelbase/sources/qimao/**",
    "novelbase/sources/92xs/**",
    "novelbase/sources/fanqie/api/rain/**",
    "novelbase/utils/_manifest.py",
    "frontend/node_modules/**",
    "frontend/dist/**",
    "android/.gradle/**",
    "android/app/build/**",
    "android/local.properties",
    "android/keystore.properties",
    "android/*.jks",
    "docs/superpowers/**",
    "docs/session-prompt.md",
    "docs/learning/**",
    "tests/test_source_async.py",
    "tests/test_source_contracts.py",
    "tests/test_browser_sources.py",
    "**/__pycache__/**",
    "**/*.pyc",
]


def _make_files(root: Path, files: dict[str, str]):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _make_pyproject(private: Path):
    """写入含非迁移清单的 pyproject.toml（已存在则追加 migration 段）。"""
    p = private / "pyproject.toml"
    lines = ["[tool.novel-downloader.migration]", "exclude = ["]
    lines += [f'    "{x}",' for x in EXCLUDE]
    lines.append("]")
    with p.open("a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(lines) + "\n")


def _full_public(private: Path, public: Path):
    """按白名单复制 private → public（模拟完整迁移）。"""
    for p in private.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(private).as_posix()
        if check_public.is_whitelisted(rel, EXCLUDE):
            dst = public / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())


class TestWhitelist:
    def test_fanqie_requests_included(self):
        assert check_public.is_whitelisted("novelbase/sources/fanqie/requests/search.py", EXCLUDE) is True

    def test_fanqie_api_excluded(self):
        assert check_public.is_whitelisted("novelbase/sources/fanqie/api/rain/novel_info.py", EXCLUDE) is False

    def test_qidian_excluded(self):
        assert check_public.is_whitelisted("novelbase/sources/qidian/requests/search.py", EXCLUDE) is False

    def test_superpowers_docs_excluded(self):
        assert check_public.is_whitelisted("docs/superpowers/specs/x-design.md", EXCLUDE) is False

    def test_app_data_excluded(self):
        assert check_public.is_whitelisted("app_data/config/config.yaml", EXCLUDE) is False

    def test_readme_included(self):
        assert check_public.is_whitelisted("README.md", EXCLUDE) is True


class TestCheck:
    def test_ok_when_full_migration(self, tmp_path):
        private = tmp_path / "private"
        public = tmp_path / "public"
        _make_files(private, {
            "novelbase/__init__.py": "x",
            "novelbase/sources/fanqie/requests/search.py": "y",
            "README.md": "readme",
            "app_data/config/config.yaml": "secret",
        })
        _make_pyproject(private)
        public.mkdir()
        _full_public(private, public)
        assert check_public.check(private, public) == []

    def test_missing_file_detected(self, tmp_path):
        private = tmp_path / "private"
        public = tmp_path / "public"
        _make_files(private, {
            "novelbase/__init__.py": "x",
            "backend/main.py": "y",
        })
        _make_pyproject(private)
        public.mkdir()
        _full_public(private, public)
        (public / "backend" / "main.py").unlink()  # 模拟漏迁
        errors = check_public.check(private, public)
        assert any("[缺失]" in e and "backend/main.py" in e for e in errors)

    def test_extra_file_detected(self, tmp_path):
        private = tmp_path / "private"
        public = tmp_path / "public"
        _make_files(private, {"novelbase/__init__.py": "x"})
        _make_pyproject(private)
        public.mkdir()
        _full_public(private, public)
        _make_files(public, {"secret_key.txt": "do-not-publish"})  # 模拟误迁
        errors = check_public.check(private, public)
        assert any("[多余]" in e and "secret_key.txt" in e for e in errors)

    def test_sensitive_content_detected(self, tmp_path):
        private = tmp_path / "private"
        public = tmp_path / "public"
        _make_files(private, {"novelbase/__init__.py": "x"})
        _make_pyproject(private)
        public.mkdir()
        _full_public(private, public)
        _make_files(public, {"backend/leak.py": "client_secret = 'abc'"})  # 白名单路径但含真实密钥模式
        errors = check_public.check(private, public)
        assert any("[敏感]" in e and "client_secret" in e for e in errors)

    def test_missing_public_dir_returns_missing_errors(self, tmp_path):
        private = tmp_path / "private"
        _make_files(private, {"novelbase/__init__.py": "x"})
        _make_pyproject(private)
        errors = check_public.check(private, tmp_path / "nope")
        assert any("[缺失]" in e for e in errors)

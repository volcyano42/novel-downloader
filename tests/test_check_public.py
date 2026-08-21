"""check_public 迁移校验测试 — 三道防线（缺失/多余/敏感）。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_public


def _make_files(root: Path, files: dict[str, str]):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _full_public(private: Path, public: Path):
    """按白名单复制 private → public（模拟完整迁移）。"""
    for p in private.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(private).as_posix()
        if check_public.is_whitelisted(rel):
            dst = public / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())


class TestWhitelist:
    def test_fanqie_requests_included(self):
        assert check_public.is_whitelisted("novelbase/sources/fanqie/requests/search.py") is True

    def test_fanqie_api_excluded(self):
        assert check_public.is_whitelisted("novelbase/sources/fanqie/api/rain/novel_info.py") is False

    def test_qidian_excluded(self):
        assert check_public.is_whitelisted("novelbase/sources/qidian/requests/search.py") is False

    def test_superpowers_docs_excluded(self):
        assert check_public.is_whitelisted("docs/superpowers/specs/x-design.md") is False

    def test_app_data_excluded(self):
        assert check_public.is_whitelisted("app_data/config/config.yaml") is False

    def test_readme_included(self):
        assert check_public.is_whitelisted("README.md") is True


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
        public.mkdir()
        _full_public(private, public)
        (public / "backend" / "main.py").unlink()  # 模拟漏迁
        errors = check_public.check(private, public)
        assert any("[缺失]" in e and "backend/main.py" in e for e in errors)

    def test_extra_file_detected(self, tmp_path):
        private = tmp_path / "private"
        public = tmp_path / "public"
        _make_files(private, {"novelbase/__init__.py": "x"})
        public.mkdir()
        _full_public(private, public)
        _make_files(public, {"secret_key.txt": "do-not-publish"})  # 模拟误迁
        errors = check_public.check(private, public)
        assert any("[多余]" in e and "secret_key.txt" in e for e in errors)

    def test_sensitive_content_detected(self, tmp_path):
        private = tmp_path / "private"
        public = tmp_path / "public"
        _make_files(private, {"novelbase/__init__.py": "x"})
        public.mkdir()
        _full_public(private, public)
        _make_files(public, {"backend/leak.py": "client_secret = 'abc'"})  # 白名单路径但含真实密钥模式
        errors = check_public.check(private, public)
        assert any("[敏感]" in e and "client_secret" in e for e in errors)

    def test_missing_public_dir_returns_missing_errors(self, tmp_path):
        private = tmp_path / "private"
        _make_files(private, {"novelbase/__init__.py": "x"})
        errors = check_public.check(private, tmp_path / "nope")
        assert any("[缺失]" in e for e in errors)

"""Tests for backend.schemas.export_config."""
import pytest
from pydantic import ValidationError

from backend.schemas.export_config import (
    DownloadConfigExportOptions,
    Epub3ExtensionDetail,
)


class TestEpub3ExtensionDetail:
    def test_defaults(self):
        d = Epub3ExtensionDetail()
        assert d.page_direction == "vertical"

    def test_explicit(self):
        d = Epub3ExtensionDetail(page_direction="horizontal")
        assert d.page_direction == "horizontal"

    def test_invalid_direction(self):
        with pytest.raises(ValidationError):
            Epub3ExtensionDetail(page_direction="diagonal")


class TestDownloadConfigExportOptions:
    def test_minimal(self):
        """Default exporter is download_config, extensions empty."""
        opts = DownloadConfigExportOptions()
        assert opts.exporter == "download_config"
        assert opts.extensions == {}

    def test_exporter_noop(self):
        opts = DownloadConfigExportOptions(exporter="noop")
        assert opts.exporter == "noop"

    def test_invalid_exporter(self):
        with pytest.raises(ValidationError):
            DownloadConfigExportOptions(exporter="unknown")

    def test_with_extensions(self):
        opts = DownloadConfigExportOptions(
            extensions={"epub3": {"page_direction": "horizontal"}}
        )
        assert isinstance(opts.extensions["epub3"], Epub3ExtensionDetail)
        assert opts.extensions["epub3"].page_direction == "horizontal"

    def test_unknown_extension(self):
        """Unknown extension keys should be accepted (silently skipped)."""
        opts = DownloadConfigExportOptions(
            extensions={"noop": "some-value"}
        )
        assert opts.extensions["noop"] == "some-value"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            DownloadConfigExportOptions(unknown_field=42)

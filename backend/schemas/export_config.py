"""Export configuration schema — download config format options."""
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Epub3ExtensionDetail(BaseModel):
    """EPUB3 extension-specific options."""

    page_direction: Literal["vertical", "horizontal"] = "vertical"


class DownloadConfigExportOptions(BaseModel):
    """Per-exporter options for the download-config output format.

    未知扩展会被跳过（不报错），仅校验已知扩展的结构是否正确。
    """

    exporter: Literal["download_config", "noop"] = "download_config"
    extensions: dict[str, Epub3ExtensionDetail | Any] = Field(
        default_factory=dict,
        description="各扩展的详细选项。已知扩展会按 schema 校验，未知的静默保留原值。",
    )

    @field_validator("extensions", mode="before")
    @classmethod
    def _skip_unknown_keys(cls, v: Any) -> Any:
        """Validate known extension keys, pass unknown keys through as-is."""
        if not isinstance(v, dict):
            return v
        known = {"epub3"}
        result: dict[str, Any] = {}
        for key, val in v.items():
            if key in known and isinstance(val, dict):
                result[key] = Epub3ExtensionDetail(**val)
            else:
                result[key] = val
        return result

    model_config = {"extra": "forbid"}

"""Export configuration schema — download config format options."""
from typing import Any, Literal

import pydantic
from pydantic import BaseModel, Field

# Android APK（Chaquopy）装不了 pydantic v2：其核心 pydantic-core 是 Rust 扩展，
# PyPI 无 Android wheel，Chaquopy 官方建议装 pydantic<2（纯 Python v1）。
# 这里做 v1/v2 双兼容，桌面端行为不变。
_PYDANTIC_V2 = pydantic.VERSION.startswith("2")

if _PYDANTIC_V2:
    from pydantic import field_validator
else:
    from pydantic import validator as field_validator


class Epub3ExtensionDetail(BaseModel):
    """EPUB3 extension-specific options."""

    page_direction: Literal["vertical", "horizontal"] = "vertical"


def _skip_unknown_keys_impl(v: Any) -> Any:
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


class DownloadConfigExportOptions(BaseModel):
    """Per-exporter options for the download-config output format.

    未知扩展会被跳过（不报错），仅校验已知扩展的结构是否正确。
    """

    exporter: Literal["download_config", "noop"] = "download_config"
    extensions: dict[str, Epub3ExtensionDetail | Any] = Field(
        default_factory=dict,
        description="各扩展的详细选项。已知扩展会按 schema 校验，未知的静默保留原值。",
    )

    if _PYDANTIC_V2:

        @field_validator("extensions", mode="before")
        @classmethod
        def _skip_unknown_keys(cls, v: Any) -> Any:
            return _skip_unknown_keys_impl(v)

        model_config = {"extra": "forbid"}

    else:  # pydantic v1：validator 不接受 mode/classmethod，配置走 class Config

        @field_validator("extensions", pre=True)
        def _skip_unknown_keys(cls, v: Any) -> Any:
            return _skip_unknown_keys_impl(v)

        class Config:
            extra = "forbid"

"""封面编码工具。"""
from base64 import b64encode


def encode_cover(cover) -> dict | None:
    if not cover:
        return None
    if not cover.raw_data:
        return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": cover.image_format}

    fmt = cover.image_format
    if fmt in ("heic", "heif"):
        converted = cover.convert("jpeg", quality=90)
        if converted.image_format != "jpeg":
            return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": fmt}
        cover = converted
        fmt = "jpeg"

    return {"raw_data": b64encode(cover.raw_data).decode(), "alt": cover.alt, "url": cover.url, "format": fmt}

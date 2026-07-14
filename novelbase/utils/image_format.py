"""图片格式检测工具。"""

IMAGE_SIGNATURES: list[tuple[bytes, str]] = [
    (b'\xff\xd8\xff',       "jpeg"),
    (b'\x89PNG\r\n\x1a\n', "png"),
    (b'GIF87a',             "gif"),
    (b'GIF89a',             "gif"),
    (b'RIFF',               "webp"),   # RIFF....WEBP
    (b'II\x2a\x00',         "tiff"),
    (b'MM\x00\x2a',         "tiff"),
    (b'\x00\x00\x00 ftyp',  "heic"),   # HEIF/HEIC family
    (b'\x00\x00\x00\x0c',   "jp2"),    # JPEG 2000
]


def guess_image_ext(data: bytes, default: str = "jpeg") -> str:
    """根据魔数猜测图片扩展名。"""
    for sig, ext in IMAGE_SIGNATURES:
        if data[:len(sig)] == sig:
            return ext
    return default

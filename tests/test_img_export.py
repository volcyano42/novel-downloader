"""IMG 导出器格式转换测试。"""
import builtins
from io import BytesIO

from PIL import Image

from novelbase.exporters.img import _convert_format


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def test_convert_png_to_jpeg():
    out = _convert_format(_png_bytes(), "jpeg")
    assert out[:2] == b"\xff\xd8"  # JPEG 魔数


def test_convert_png_to_jpeg_without_pillow_heif(monkeypatch):
    """pillow-heif 缺失不应阻断 PNG→JPEG（HEIF 支持是可选的）。"""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pillow_heif" or name.startswith("pillow_heif."):
            raise ImportError("No module named 'pillow_heif'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = _convert_format(_png_bytes(), "jpeg")
    assert out[:2] == b"\xff\xd8"

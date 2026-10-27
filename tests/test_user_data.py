"""shared.user_data 注解可求值——Path 必须导入，否则 Python<3.14 在 import 时 NameError。"""
import typing
from pathlib import Path

from shared import user_data


def test_validate_entry_path_annotation_resolvable():
    hints = typing.get_type_hints(user_data._validate_entry)
    assert hints["path"] is Path


def test_atomic_write_path_annotation_resolvable():
    hints = typing.get_type_hints(user_data._atomic_write)
    assert hints["path"] is Path

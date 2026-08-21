# Exporters: Class → Pure Functions 重构设计

2026-07-29

## 目标

将 `novelbase/exporters/` 下的 TXT / EPUB / IMG 三个导出器从 class 改为纯函数，消除实例级可变状态，确保一次调用、一次导出、无残留。

## 当前问题

三个导出器都是 class，构造函数中初始化可变状态（`_ordered_chapter_dict`、`_file_path`、`_img_counter` 等），虽然所有调用方都创建新实例所以实际不会泄漏，但 API 本身是脆弱的——复用实例会出错。

## 新 API

```python
# novelbase/exporters/txt.py
def export_txt(chapters: Chapters, novel: Novel, options: TXTExportOptions | None = None, **kwargs) -> Path: ...

# novelbase/exporters/epub.py
def export_epub(chapters: Chapters, novel: Novel, options: EPUBExportOptions | None = None, **kwargs) -> Path: ...

# novelbase/exporters/img.py
def export_img(chapters: Chapters, novel: Novel, options: IMGExportOptions | None = None, **kwargs) -> Path: ...
```

- 接收全部章节，一次性完成导出
- 返回输出文件/目录路径
- 内部所有可变状态均为局部变量，函数返回即释放

## 文件结构（不变）

```
novelbase/exporters/
├── __init__.py    # 导出公共函数 + 向后兼容别名
├── base.py        # BaseExportOptions (pydantic model, 纯值对象)
├── txt.py         # export_txt() + helpers
├── epub.py        # export_epub() + helpers
└── img.py         # export_img() + helpers
```

## 关键变化

### TXT

- `TXTExporter.__init__` 中的 `_ordered_chapter_dict`/`_file_path`/`_header_written` 全部删除
- `export_txt()` 内用 `sorted(chapters, key=lambda c: c.order)` 替代 dict 累积
- 文件打开模式从 `"a"`（追加）改为 `"w"`（一次性写入）

### EPUB

- `EPUBExporter.__init__` 中的 `_ordered_chapter_dict`/`_img_list`/`_img_hash_seen`/`_img_name_seen`/`_img_counter`/`_file_path`/`_export_meta` 全部删除
- image dedup 改为 `export_epub()` 内的局部 dict
- `_write_epub_zip(path, novel, chapters, image_registry, options)` 接收所有参数

### IMG

- `IMGExporter.__init__` 中的 `_img_counter`/`_output_base` 全部删除
- counter 改为函数内局部变量

### base.py

- 删除 `BASEExporter` ABC 类
- 保留 `BaseExportOptions` pydantic 模型

## Options 类

`TXTExportOptions`、`EPUBExportOptions`、`IMGExportOptions` 是 pydantic/dataclass 模型，本身就是无状态值对象，**保持不变**。

## 向后兼容

在 `novelbase/exporters/__init__.py` 中保留旧的 class 名作为 deprecated wrapper：

```python
class TXTExporter:
    def __init__(self, *, options=None):
        import warnings
        warnings.warn("TXTExporter is deprecated, use export_txt()", DeprecationWarning)
        self.options = options
    def export(self, chapters, novel, **kw):
        return export_txt(chapters, novel, self.options, **kw)
```

## 调用方变更

| 文件 | 变更 |
|------|------|
| `novelbase/core/downloader.py` | `exporter_cls(options=opt).export(...)` → 直接调用函数 |
| `novelbase/core/engine.py` | `format_map` 从 class 映射改为 function 映射 |
| `app/core.py` | 同上 |
| `app/menus.py` | 同上 |
| `services/backend/routers/export.py` | 同上 |
| `email_downloader.py` | 同上 |

## 不做

- 不合并文件（保持现有文件结构）
- 不修改 Options 类
- 不禁用增量导出（已废弃，改为一次性）
- 不修改测试（测试应继续通过或小修）

## 验证

- `python -m pytest tests/ -v --tb=short` 全部通过（118 passed）
- `python -c "from novelbase import *; print('OK')"` 导入正常
- 各调用方手动验证导出功能正常

# Exporters: Class → Pure Functions 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `novelbase/exporters/` 下 TXT/EPUB/IMG 三个导出器从 class 改为纯函数，消除实例级可变状态。

**Architecture:** 每个导出模块暴露单一函数（`export_txt`/`export_epub`/`export_img`），接收全部章节一次性完成导出。Options 类保留为纯值对象。保留向后兼容 wrapper 类。

**Tech Stack:** Python 3.13, pydantic/dataclass Options, zipfile (EPUB), no new dependencies

## Global Constraints

- 一个方面一条 commit，禁止 `git add -A`
- commit 消息用中文
- 向后兼容：旧 class 名保留为 deprecated wrapper
- 测试必须全部通过（118 passed）
- 工作目录：D:\Linux\novel-downloader

---

### Task 1: Refactor TXTExporter → export_txt

**Files:**
- Modify: `novelbase/exporters/txt.py`

**Interfaces:**
- Produces: `export_txt(chapters: Chapters, novel: Novel, options: TXTExportOptions | None = None, **kwargs) -> Path`
- Internal helpers become module-level: `_build_path()`, `_write_header()`, `_write_chapter()`

- [ ] **Step 1: 读取当前文件，确认所有方法**

读取 `novelbase/exporters/txt.py` 完整内容。

- [ ] **Step 2: 重写为纯函数**

删除类定义，将 `__init__` 属性改为局部变量，`export()` 改为模块级函数。

```python
# novelbase/exporters/txt.py — 完整重写

from pathlib import Path

from novelbase.models.novel import Novel, Chapters
from .base import BaseExportOptions


class TXTExportOptions(BaseExportOptions):
    """TXT 导出选项（纯值对象，不变）"""
    encoding: str = "utf-8"
    # ... 保持现有字段不变


def _build_path(novel: Novel, options: TXTExportOptions) -> Path:
    """计算输出文件路径（从原 _build_file_path 改为模块级函数）。"""
    from datetime import date
    file_name_template = getattr(options, "file_name_template", "{title}")
    variables = {
        "title": novel.title, "author": novel.author,
        "novel_id": novel.id, "total_chapters": novel.serial,
        "date": date.today().isoformat(),
    }
    filename = file_name_template.format(**variables)
    # 过滤非法文件名字符
    import re
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    ext = getattr(options, "extension", ".txt")
    if not str(filename).endswith(ext):
        filename = f"{filename}{ext}"
    out = Path(options.output_path) if options.output_path else Path(".")
    return out / filename


def _write_header(f, novel: Novel, options: TXTExportOptions):
    """写入书名和作者头（从原 _write_header 改为模块级函数）。"""
    header_template = getattr(options, "header_template", None)
    if header_template is None:
        f.write(f"《{novel.title}》\n作者：{novel.author}\n{'=' * 60}\n\n")
    else:
        from datetime import date
        variables = {
            "title": novel.title, "author": novel.author,
            "novel_id": novel.id, "total_chapters": novel.serial,
            "date": date.today().isoformat(),
        }
        f.write(header_template.format_map(SafeDict(**variables)))
        f.write("\n\n")


class SafeDict(dict):
    """支持不完整 format 的字典包装（从原 SafeDict 提到模块级）。"""
    def __missing__(self, key):
        return "{" + key + "}"


def export_txt(
    chapters,
    novel: Novel,
    options: TXTExportOptions | None = None,
    **kwargs,
) -> Path:
    """一次性导出 TXT，返回输出文件路径。"""
    opt = options or TXTExportOptions()
    path = _build_path(novel, opt)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_chapters = sorted(chapters, key=lambda c: c.order)
    encoding = getattr(opt, "encoding", "utf-8")
    with open(path, "w", encoding=encoding) as f:
        _write_header(f, novel, opt)
        for ch in sorted_chapters:
            f.write(f"{ch.title}\n\n")
            f.write((ch.content or "") + "\n\n")
            f.write("─" * 40 + "\n\n")
    return path


# 向后兼容 wrapper
class TXTExporter:
    """Deprecated: use export_txt() instead."""
    def __init__(self, *, options=None):
        import warnings
        warnings.warn("TXTExporter is deprecated, use export_txt()", DeprecationWarning, stacklevel=2)
        self.options = options
    def export(self, chapters, novel, **kw):
        return export_txt(chapters, novel, self.options, **kw)
```

- [ ] **Step 3: 验证导入**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase.exporters.txt import export_txt, TXTExportOptions; print('OK')"
```

- [ ] **Step 4: 运行测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 5: Commit**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/exporters/txt.py; git commit -m "refactor: TXTExporter 改为纯函数 export_txt"
```

---

### Task 2: Refactor EPUBExporter → export_epub

**Files:**
- Modify: `novelbase/exporters/epub.py`

**Interfaces:**
- Produces: `export_epub(chapters: Chapters, novel: Novel, options: EPUBExportOptions | None = None, **kwargs) -> Path`

- [ ] **Step 1: 将 EPUBExporter.export() 提升为模块级函数 export_epub()**

关键变化：
- `__init__` 中的 `_ordered_chapter_dict`, `_img_list`, `_img_hash_seen`, `_img_name_seen`, `_img_counter`, `_file_path`, `_export_meta` → 全部移除
- `export()` 方法 → 模块级 `export_epub()`
- image dedup 移到函数内部的局部 dict
- `_build_epub()` → `_write_epub_zip(path, novel, chapters, image_registry, options)` 接收所有参数而非读 self
- `_file_path` → `_build_file_path(novel, options)` 独立函数
- EPUBExportOptions 类不变
- 文件末尾加 `TXTExporter` wrapper 类似 Task 1

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase.exporters.epub import export_epub, EPUBExportOptions; print('OK')"
```

- [ ] **Step 3: 运行测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/exporters/epub.py; git commit -m "refactor: EPUBExporter 改为纯函数 export_epub"
```

---

### Task 3: Refactor IMGExporter → export_img

**Files:**
- Modify: `novelbase/exporters/img.py`

**Interfaces:**
- Produces: `export_img(chapters: Chapters, novel: Novel, options: IMGExportOptions | None = None, **kwargs) -> Path`

- [ ] **Step 1: 将 IMGExporter.export() 提升为模块级函数 export_img()**

关键变化：
- `__init__` 中的 `_img_counter`, `_output_base` → 全部移除
- `export()` 方法 → 模块级 `export_img()`
- `_img_counter` → 函数内局部变量 `counter = 0`
- `_output_base` → `_build_output_dir(novel, options)` 独立函数
- IMGExportOptions 类不变
- 文件末尾加 wrapper 类

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase.exporters.img import export_img, IMGExportOptions; print('OK')"
```

- [ ] **Step 3: 运行测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/exporters/img.py; git commit -m "refactor: IMGExporter 改为纯函数 export_img"
```

---

### Task 4: 清理 base.py + 更新 registry

**Files:**
- Modify: `novelbase/exporters/base.py`
- Modify: `novelbase/utils/registry.py`
- Modify: `novelbase/exporters/__init__.py`

- [ ] **Step 1: 删除 BASEExporter ABC 类**

`novelbase/exporters/base.py`：删除 `BASEExporter` 类定义。保留 `BaseExportOptions`。

- [ ] **Step 2: 更新 registry.py**

`_hardcoded_exporters()` 改为返回函数：
```python
def _hardcoded_exporters() -> dict[str, Callable]:
    from ..exporters.txt import export_txt
    from ..exporters.epub import export_epub
    from ..exporters.img import export_img
    return {"txt": export_txt, "epub": export_epub, "img": export_img}
```

`_scan_plugins` 的 export 扫描需要更新：`_scan_plugins("exporters", capitalize=False)` 会找类 `TXTExporter`。改为找函数 `export_txt` 或让它自然失败回退到 `_hardcoded_exporters`。

最简单：`_scan_plugins` 会失败（类不存在），自动回退到硬编码——这是已有的执行路径。但为了健壮性，可以在 `register_exporter` 中将 `_scan_plugins` 改为一个新的 `_scan_exporter_functions`：

```python
def _scan_exporter_functions() -> dict[str, Callable]:
    result = {}
    pkg_dir = Path(__file__).parent.parent / "exporters"
    if not pkg_dir.exists():
        return result
    for entry in sorted(os.listdir(pkg_dir)):
        if entry.endswith(".py") and entry not in ("__init__.py", "base.py"):
            module_name = entry[:-3]
            try:
                from importlib import import_module
                module = import_module(f"..exporters.{module_name}", __package__)
                func_name = f"export_{module_name}"
                if hasattr(module, func_name):
                    result[module_name] = getattr(module, func_name)
            except (ImportError, AttributeError):
                pass
    return result
```

`register_exporter()` 改用 `_scan_exporter_functions()` 替代 `_scan_plugins("exporters", capitalize=False)`。

`register_exporter` 返回类型从 `dict[str, type[BASEExporter]]` 改为 `dict[str, Callable]`。

- [ ] **Step 3: 更新 __init__.py**

```python
from novelbase.exporters.txt import export_txt, TXTExportOptions
from novelbase.exporters.epub import export_epub, EPUBExportOptions
from novelbase.exporters.img import export_img, IMGExportOptions
```

- [ ] **Step 4: 验证导入**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase import *; print('OK')"
```

- [ ] **Step 5: 运行测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

- [ ] **Step 6: Commit**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/exporters/base.py novelbase/utils/registry.py novelbase/exporters/__init__.py; git commit -m "refactor: 删除 BASEExporter，registry 改为返回纯函数"
```

---

### Task 5: 更新 downloader.py (export + get_exporters)

**Files:**
- Modify: `novelbase/core/downloader.py`
- Modify: `novelbase/__init__.py`

- [ ] **Step 1: 修改 get_exporters 返回类型**

```python
def get_exporters() -> dict[str, Callable]:
    """返回所有已注册的导出函数（{format: export_func}）。"""
    from ..utils.registry import register_exporter
    return register_exporter()
```

- [ ] **Step 2: 修改 export() 函数调用方式**

`export()` 函数中 `exporter_cls = register_exporter().get(fmt)` → `export_func = register_exporter().get(fmt)`，然后：

```python
export_func = register_exporter().get(fmt)
if export_func is None:
    return

result = export_func(novel.chapters, novel, options=opt, **kwargs)
return result
```

`export()` 返回值从 `None` 改为 `Path | None`。

- [ ] **Step 3: 更新 novelbase/__init__.py 导出**

确保 `export`, `get_exporters`, `get_exporter_options` 仍在 `__all__` 中。检查 import 路径是否正确。

- [ ] **Step 4: 验证导入**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase import export, get_exporters; print(get_exporters()); print('OK')"
```

- [ ] **Step 5: 运行测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

- [ ] **Step 6: Commit**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/core/downloader.py novelbase/__init__.py; git commit -m "refactor: downloader.export() 改为调用纯函数，get_exporters 返回函数"
```

---

### Task 6: 更新所有调用方

**Files:**
- Modify: `app/core.py`
- Modify: `app/menus.py`
- Modify: `services/backend/routers/export.py`
- Modify: `email_downloader.py`
- Modify: `tests/check_imports.py`（如有需要）

- [ ] **Step 1: 更新 CLI — app/core.py**

`export(novel, opts, fmt)` 调用方式在当前代码中已经是通过 `novelbase.export()` 调用，签名不变。验证调用正确。检查 line 277-288 区域。

- [ ] **Step 2: 更新菜单 — app/menus.py**

同 `app/core.py`，`export(novel, opts, fmt)` 调用签名不变。检查 line 303-320 区域。

- [ ] **Step 3: 更新后端 — services/backend/routers/export.py**

当前代码：
```python
from novelbase import export as do_export
...
do_export(novel, options=opt)
```

`do_export` 调用方式不变（`export(novel, options=opt)` 签名兼容）。

- [ ] **Step 4: 更新邮箱下载器 — email_downloader.py**

当前代码已使用 `TXTExporter(options=...).export(...)`，改为直接调用 `export_txt(chapters, novel, options=...)` 和 `export_epub(chapters, novel, options=...)`：

```python
from novelbase.exporters.txt import export_txt, TXTExportOptions
from novelbase.exporters.epub import export_epub, EPUBExportOptions

txt_opt = TXTExportOptions(output_path=str(txt_dir), enabled=True)
path = export_txt(novel.chapters, novel, options=txt_opt)

epub_opt = EPUBExportOptions(output_path=str(epub_dir), enabled=True)
path = export_epub(novel.chapters, novel, options=epub_opt)
```

- [ ] **Step 5: 更新 check_imports.py**

`tests/check_imports.py` import 检查 `get_exporters` — 签名不变只是返回类型变了，`.keys()` 调用仍然有效。

- [ ] **Step 6: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 7: Commit**

```powershell
cd D:\Linux\novel-downloader; git add app/core.py app/menus.py services/backend/routers/export.py email_downloader.py tests/check_imports.py; git commit -m "refactor: 调用方改用纯函数导出"
```

---

### Task 7: 最终清理 + 验证

**Files:**
- 检查是否有残留引用

- [ ] **Step 1: 搜索残留的 Exporter 类引用**

```powershell
cd D:\Linux\novel-downloader; Get-ChildItem -Recurse -Include *.py -Path novelbase,app,services,tests | Select-String -Pattern "TXTExporter|EPUBExporter|IMGExporter|BASEExporter" | Where-Object { $_ -notmatch "wrapper|deprecated|warn" }
```

预期：只在 backward compat wrapper 和 deprecated warning 中出现。

- [ ] **Step 2: 最终全量验证**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase import *; print('OK')"
```

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 3: 功能验证**

```powershell
cd D:\Linux\novel-downloader; python -c "
from novelbase.exporters.txt import export_txt, TXTExportOptions
from novelbase.exporters.epub import export_epub, EPUBExportOptions
from novelbase.exporters.img import export_img, IMGExportOptions
from novelbase import get_exporters
print('exporters:', list(get_exporters().keys()))
print('All OK')
"
```

- [ ] **Step 4: Commit**

```powershell
cd D:\Linux\novel-downloader; git add -u; git commit -m "chore: 最终清理，移除残留引用"
```

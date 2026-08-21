# fetchers → sources 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `novelbase/fetchers/` 重命名为 `novelbase/sources/`，重命名底层文件（去除 `fetch_` 前缀），清理所有向后兼容代码。

**Architecture:** 分 5 步提交：目录重命名 → 文件重命名 → 引用更新 → 兼容代码清理 → FUNC_FILE_MAP 更新。每步独立 commit，可单独验证。

**Tech Stack:** Python 3.13, git

## Global Constraints

- 不兼容旧代码，删除所有向后兼容别名
- 底层文件名去除 `fetch_` 前缀：`fetch_novel.py` → `novel_info.py`，`fetch_chapter_list.py` → `chapter_list.py`，`fetch_chapter.py` → `chapter_content.py`
- 每步后验证：`python -c "from novelbase import *; print('OK')"` 和 `python -m pytest tests/ -v --tb=short`
- 一个方面一条 commit，禁止 `git add -A`

---

### Task 1: 目录重命名 fetchers → sources

**Files:**
- Rename: `novelbase/fetchers/` → `novelbase/sources/`

**Interfaces:**
- Produces: `novelbase/sources/` 目录结构不变，仅路径变化

- [ ] **Step 1: 重命名目录**

```powershell
cd D:\Linux\novel-downloader
git mv novelbase/fetchers novelbase/sources
```

- [ ] **Step 2: 验证目录结构**

```powershell
Get-ChildItem -Path novelbase\sources -Name
```

Expected: 看到 fanqie、qidian、qimao 等目录

- [ ] **Step 3: 提交**

```powershell
git add novelbase/
git commit -m "refactor: 重命名 novelbase/fetchers → novelbase/sources"
```

---

### Task 2: 重命名底层文件和函数

**Files:**
- Rename: `novelbase/sources/*/{mode}/{provider}/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/sources/*/{mode}/{provider}/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/sources/*/{mode}/{provider}/fetch_chapter.py` → `chapter_content.py`
- Modify: 每个重命名文件内的函数名

**Interfaces:**
- Produces: 文件名和函数名去除 `fetch_` 前缀

- [ ] **Step 1: 重命名 fanqie 的文件**

```powershell
# fanqie/browser/
git mv novelbase/sources/fanqie/browser/fetch_novel.py novelbase/sources/fanqie/browser/novel_info.py
git mv novelbase/sources/fanqie/browser/fetch_chapter_list.py novelbase/sources/fanqie/browser/chapter_list.py
git mv novelbase/sources/fanqie/browser/fetch_chapter.py novelbase/sources/fanqie/browser/chapter_content.py

# fanqie/requests/
git mv novelbase/sources/fanqie/requests/fetch_novel.py novelbase/sources/fanqie/requests/novel_info.py
git mv novelbase/sources/fanqie/requests/fetch_chapter_list.py novelbase/sources/fanqie/requests/chapter_list.py
git mv novelbase/sources/fanqie/requests/fetch_chapter.py novelbase/sources/fanqie/requests/chapter_content.py

# fanqie/api/oiapi/
git mv novelbase/sources/fanqie/api/oiapi/fetch_novel.py novelbase/sources/fanqie/api/oiapi/novel_info.py
git mv novelbase/sources/fanqie/api/oiapi/fetch_chapter_list.py novelbase/sources/fanqie/api/oiapi/chapter_list.py
git mv novelbase/sources/fanqie/api/oiapi/fetch_chapter.py novelbase/sources/fanqie/api/oiapi/chapter_content.py

# fanqie/api/rain/
git mv novelbase/sources/fanqie/api/rain/fetch_novel.py novelbase/sources/fanqie/api/rain/novel_info.py
git mv novelbase/sources/fanqie/api/rain/fetch_chapter_list.py novelbase/sources/fanqie/api/rain/chapter_list.py
git mv novelbase/sources/fanqie/api/rain/fetch_chapter.py novelbase/sources/fanqie/api/rain/chapter_content.py
```

- [ ] **Step 2: 重命名 qidian 的文件**

```powershell
# qidian/browser/
git mv novelbase/sources/qidian/browser/fetch_novel.py novelbase/sources/qidian/browser/novel_info.py
git mv novelbase/sources/qidian/browser/fetch_chapter_list.py novelbase/sources/qidian/browser/chapter_list.py
git mv novelbase/sources/qidian/browser/fetch_chapter.py novelbase/sources/qidian/browser/chapter_content.py

# qidian/requests/
git mv novelbase/sources/qidian/requests/fetch_novel.py novelbase/sources/qidian/requests/novel_info.py
git mv novelbase/sources/qidian/requests/fetch_chapter_list.py novelbase/sources/qidian/requests/chapter_list.py
git mv novelbase/sources/qidian/requests/fetch_chapter.py novelbase/sources/qidian/requests/chapter_content.py
```

- [ ] **Step 3: 重命名 qimao 的文件**

```powershell
# qimao/browser/
git mv novelbase/sources/qimao/browser/fetch_novel.py novelbase/sources/qimao/browser/novel_info.py
git mv novelbase/sources/qimao/browser/fetch_chapter_list.py novelbase/sources/qimao/browser/chapter_list.py
git mv novelbase/sources/qimao/browser/fetch_chapter.py novelbase/sources/qimao/browser/chapter_content.py

# qimao/requests/
git mv novelbase/sources/qimao/requests/fetch_novel.py novelbase/sources/qimao/requests/novel_info.py
git mv novelbase/sources/qimao/requests/fetch_chapter_list.py novelbase/sources/qimao/requests/chapter_list.py
git mv novelbase/sources/qimao/requests/fetch_chapter.py novelbase/sources/qimao/requests/chapter_content.py

# qimao/api/rain/
git mv novelbase/sources/qimao/api/rain/fetch_novel.py novelbase/sources/qimao/api/rain/novel_info.py
git mv novelbase/sources/qimao/api/rain/fetch_chapter_list.py novelbase/sources/qimao/api/rain/chapter_list.py
git mv novelbase/sources/qimao/api/rain/fetch_chapter.py novelbase/sources/qimao/api/rain/chapter_content.py
```

- [ ] **Step 4: 更新文件内的函数名**

对每个重命名的文件，替换函数定义：
- `def fetch_novel(` → `def novel_info(`
- `def fetch_chapter_list(` → `def chapter_list(`
- `def fetch_chapter(` → `def chapter_content(`

使用 PowerShell 批量替换：
```powershell
# novel_info.py 文件
Get-ChildItem -Path novelbase\sources -Recurse -Filter novel_info.py | ForEach-Object {
    (Get-Content $_.FullName) -replace 'def fetch_novel\(', 'def novel_info(' | Set-Content $_.FullName
}

# chapter_list.py 文件
Get-ChildItem -Path novelbase\sources -Recurse -Filter chapter_list.py | ForEach-Object {
    (Get-Content $_.FullName) -replace 'def fetch_chapter_list\(', 'def chapter_list(' | Set-Content $_.FullName
}

# chapter_content.py 文件
Get-ChildItem -Path novelbase\sources -Recurse -Filter chapter_content.py | ForEach-Object {
    (Get-Content $_.FullName) -replace 'def fetch_chapter\(', 'def chapter_content(' | Set-Content $_.FullName
}
```

- [ ] **Step 5: 验证函数名已更新**

```powershell
Select-String -Path novelbase\sources\*\*\*.py -Pattern "def fetch_" -Recurse
```

Expected: 无输出（没有以 `def fetch_` 开头的函数）

- [ ] **Step 6: 提交**

```powershell
git add novelbase/sources/
git commit -m "refactor: 重命名底层文件 fetch_novel→novel_info, fetch_chapter_list→chapter_list, fetch_chapter→chapter_content"
```

---

### Task 3: 更新所有 Python 引用

**Files:**
- Modify: `novelbase/utils/registry.py` — 6 处 `fetchers` → `sources`
- Modify: `novelbase/utils/registry.py` — FUNC_FILE_MAP 更新
- Modify: `novelbase/sources/*/__init__.py` — logger 名称
- Modify: `novelbase/sources/*/_common.py` — logger 名称
- Modify: `cli.py` — 脚手架路径
- Rename: `scripts/debug_fetcher.py` → `scripts/debug_source.py`
- Modify: `scripts/debug_source.py` — 更新所有引用
- Modify: `tests/check_imports.py` — 删除 get_fetchers 引用

**Interfaces:**
- Produces: 所有 Python 引用指向 `novelbase.sources`

- [ ] **Step 1: 更新 registry.py 中的路径引用**

编辑 `novelbase/utils/registry.py`，替换以下内容：
- 第 18 行: `"""扫描 fetchers/ 目录` → `"""扫描 sources/ 目录`
- 第 21 行: `- 单文件：fetchers/fanqie.py` → `- 单文件：sources/fanqie.py`
- 第 22 行: `- 目录包：fetchers/fanqie/__init__.py` → `- 目录包：sources/fanqie/__init__.py`
- 第 28 行: `pkg_dir = Path(__file__).parent.parent / "fetchers"` → `pkg_dir = Path(__file__).parent.parent / "sources"`
- 第 45 行: `module = import_module(f"..fetchers.{module_name}", __package__)` → `module = import_module(f"..sources.{module_name}", __package__)`
- 第 204 行: `"""扫描 fetchers/{name}/ 目录` → `"""扫描 sources/{name}/ 目录`
- 第 216 行: `pkg_dir = Path(__file__).parent.parent / "fetchers" / name` → `pkg_dir = Path(__file__).parent.parent / "sources" / name`
- 第 271 行: `module_path = f"novelbase.fetchers.{name}.{mode}.{provider}.{file_stem}"` → `module_path = f"novelbase.sources.{name}.{mode}.{provider}.{file_stem}"`
- 第 276 行: `module_path = f"novelbase.fetchers.{name}.{mode}.{file_stem}"` → `module_path = f"novelbase.sources.{name}.{mode}.{file_stem}"`
- 第 287 行: `pkg_dir = Path(__file__).parent.parent / "fetchers"` → `pkg_dir = Path(__file__).parent.parent / "sources"`

- [ ] **Step 2: 更新 FUNC_FILE_MAP**

编辑 `novelbase/utils/registry.py` 第 194-200 行：
```python
FUNC_FILE_MAP = {
    "search": "search",
    "novel_info": "novel_info",
    "chapter_list": "chapter_list",
    "chapter_content": "chapter_content",
    "login": "login",
}
```

- [ ] **Step 3: 更新 logger 名称**

```powershell
# qidian/browser/login.py
(Get-Content novelbase\sources\qidian\browser\login.py) -replace 'novelbase\.fetchers\.qidian', 'novelbase.sources.qidian' | Set-Content novelbase\sources\qidian\browser\login.py

# qimao/_common.py
(Get-Content novelbase\sources\qimao\_common.py) -replace 'novelbase\.fetchers\.qimao', 'novelbase.sources.qimao' | Set-Content novelbase\sources\qimao\_common.py

# qimao/browser/login.py
(Get-Content novelbase\sources\qimao\browser\login.py) -replace 'novelbase\.fetchers\.qimao', 'novelbase.sources.qimao' | Set-Content novelbase\sources\qimao\browser\login.py
```

- [ ] **Step 4: 更新 cli.py 脚手架路径**

编辑 `cli.py` 第 222-244 行，替换 `fetchers` → `sources`：
- 第 222 行: `fetcher_dir = Path(__file__).parent / "novelbase" / "fetchers" / name` → `source_dir = Path(__file__).parent / "novelbase" / "sources" / name`
- 第 223 行: `fetcher_dir.mkdir(parents=True, exist_ok=True)` → `source_dir.mkdir(parents=True, exist_ok=True)`
- 第 225 行: `(fetcher_dir / "__init__.py").write_text(` → `(source_dir / "__init__.py").write_text(`
- 第 227 行: `(fetcher_dir / "_common.py").write_text(` → `(source_dir / "_common.py").write_text(`
- 第 232 行: `mode_dir = fetcher_dir / mode` → `mode_dir = source_dir / mode`
- 第 244 行: `print(f"书源脚手架已创建: novelbase/fetchers/{name}/")` → `print(f"书源脚手架已创建: novelbase/sources/{name}/")`

- [ ] **Step 5: 重命名 debug_fetcher.py**

```powershell
git mv scripts/debug_fetcher.py scripts/debug_source.py
```

- [ ] **Step 6: 更新 debug_source.py 内容**

编辑 `scripts/debug_source.py`：
- 第 2 行: `"""Fetcher 调试工具` → `"""Source 调试工具`
- 第 45 行: `module_name = f"novelbase.fetchers.{platform}"` → `module_name = f"novelbase.sources.{platform}"`
- 第 56 行: `module_name = f"novelbase.fetchers.{platform}"` → `module_name = f"novelbase.sources.{platform}"`
- 第 249 行: `description="Fetcher 调试工具",` → `description="Source 调试工具",`

- [ ] **Step 7: 更新 tests/check_imports.py**

编辑 `tests/check_imports.py`：
- 删除第 14 行的 `get_fetchers,` 导入
- 第 31 行: `print("  注册的 Fetcher: " + str(list(get_fetchers().keys())))` → `print("  注册的 Source: " + str(list_sources()))`

- [ ] **Step 8: 验证导入**

```powershell
python -c "from novelbase import *; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: 提交**

```powershell
git add novelbase/utils/registry.py novelbase/sources/ cli.py scripts/debug_source.py tests/check_imports.py
git commit -m "refactor: 更新所有 fetchers→sources 引用，FUNC_FILE_MAP 对齐新文件名"
```

---

### Task 4: 清理向后兼容代码

**Files:**
- Modify: `novelbase/__init__.py` — 删除向后兼容别名和函数
- Modify: `novelbase/core/downloader.py` — 删除 fetcher 废弃参数

**Interfaces:**
- Produces: 干净的公共 API，无废弃别名

- [ ] **Step 1: 清理 novelbase/__init__.py**

编辑 `novelbase/__init__.py`，删除以下内容：
- 第 45-46 行: `fetch_meta = resolve_meta` 和 `fetch_chapter_list = resolve_chapter_list`
- 第 49-52 行: `get_fetchers()` 函数
- 第 55-62 行: `get_fetcher_for_url()` 函数
- 第 65-72 行: `get_fetcher_for_id()` 函数
- `__all__` 中的对应条目：`"fetch_meta"`, `"fetch_chapter_list"`, `"get_fetcher_for_url"`, `"get_fetcher_for_id"`, `"get_fetchers"`

- [ ] **Step 2: 清理 downloader.py 中的废弃参数**

编辑 `novelbase/core/downloader.py` 第 181 行：
```python
# 原来
def resolve_chapter(chapter: Chapter, engine, fetcher=None, skip_delay: bool = False, **kwargs) -> Chapter | None:
# 改为
def resolve_chapter(chapter: Chapter, engine, skip_delay: bool = False, **kwargs) -> Chapter | None:
```

同时删除 docstring 中关于 `fetcher` 的说明（第 187 行）。

- [ ] **Step 3: 验证**

```powershell
python -c "from novelbase import *; print('OK')"
python -m pytest tests/ -v --tb=short
```

Expected: 导入成功，118 tests passed

- [ ] **Step 4: 提交**

```powershell
git add novelbase/__init__.py novelbase/core/downloader.py
git commit -m "refactor: 删除向后兼容别名（get_fetchers/get_fetcher_for_url/get_fetcher_for_id/fetch_meta/fetch_chapter_list）"
```

---

### Task 5: 最终验证

**Files:**
- None (验证步骤)

- [ ] **Step 1: 运行完整测试**

```powershell
python -c "from novelbase import *; print('OK')"
python -m pytest tests/ -v --tb=short
```

Expected: `OK` 和 118 tests passed

- [ ] **Step 2: 验证无残留 fetcher 引用**

```powershell
Select-String -Path *.py,novelbase\*.py,novelbase\**\*.py,tests\*.py,services\**\*.py -Pattern "fetcher|Fetcher|fetchers" -Recurse -Exclude *.pyc | Where-Object { $_.Path -notmatch "__pycache__|\.pyc" }
```

Expected: 仅在 docs/ 和 scripts/bookshelf_fetch.py 中有引用（文档和独立脚本），核心代码中无残留

- [ ] **Step 3: 验证目录结构**

```powershell
Get-ChildItem -Path novelbase -Name
```

Expected: 看到 `sources`（不是 `fetchers`）

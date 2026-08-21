# fetchers → sources 重构设计

## 概述

将 `novelbase/fetchers/` 目录重命名为 `novelbase/sources/`，同时重命名底层函数文件（去除 `fetch_` 前缀），清理所有向后兼容代码。这是一次不兼容旧代码的彻底重构。

## 动机

1. **命名一致性**：代码中已广泛使用 "source" 术语（`register_source`、`get_source`、`SourceNotFoundError`），但目录仍叫 `fetchers`
2. **去除冗余前缀**：底层文件名 `fetch_novel.py` 在 `FUNC_FILE_MAP` 中已有映射，文件名本身不需要 `fetch_` 前缀
3. **清理技术债务**：删除向后兼容别名（`get_fetchers`、`get_fetcher_for_url` 等），简化公共 API

## 分步计划

### 步骤 1：目录重命名

```bash
git mv novelbase/fetchers novelbase/sources
```

仅移动目录，不改文件内容。

### 步骤 2：底层文件重命名

每个平台的每个 mode/provider 下重命名文件：

| 原文件名 | 新文件名 |
|----------|----------|
| `fetch_novel.py` | `novel_info.py` |
| `fetch_chapter_list.py` | `chapter_list.py` |
| `fetch_chapter.py` | `chapter_content.py` |

同时更新文件内的函数名：
- `def fetch_novel(` → `def novel_info(`
- `def fetch_chapter_list(` → `def chapter_list(`
- `def fetch_chapter(` → `def chapter_content(`

涉及目录：
- `sources/fanqie/{browser,requests}/`
- `sources/fanqie/api/{oiapi,rain}/`
- `sources/qidian/{browser,requests}/`
- `sources/qimao/{browser,requests}/`
- `sources/qimao/api/rain/`

### 步骤 3：更新所有 Python 引用

| 文件 | 变更 |
|------|------|
| `novelbase/utils/registry.py` | 路径 `fetchers` → `sources`（6 处） |
| `novelbase/__init__.py` | 删除向后兼容别名和函数 |
| `novelbase/core/downloader.py` | 删除 `fetcher` 废弃参数 |
| `novelbase/sources/*/` | logger 名称 `novelbase.fetchers.*` → `novelbase.sources.*` |
| `cli.py` | 脚手架路径 `fetchers` → `sources` |
| `scripts/debug_fetcher.py` | 重命名为 `debug_source.py`，更新引用 |
| `tests/check_imports.py` | 删除 `get_fetchers` 引用，改用 `list_sources` |

### 步骤 4：清理向后兼容代码

从 `novelbase/__init__.py` 删除：
- `fetch_meta = resolve_meta`
- `fetch_chapter_list = resolve_chapter_list`
- `get_fetchers()` 函数
- `get_fetcher_for_url()` 函数
- `get_fetcher_for_id()` 函数
- `__all__` 中对应的条目

### 步骤 5：更新 FUNC_FILE_MAP

```python
FUNC_FILE_MAP = {
    "search": "search",
    "novel_info": "novel_info",
    "chapter_list": "chapter_list",
    "chapter_content": "chapter_content",
    "login": "login",
}
```

## 验证

每步后运行：
```powershell
python -c "from novelbase import *; print('OK')"
python -m pytest tests/ -v --tb=short
```

## 影响范围

- **核心库**：`novelbase/` 下的 registry、downloader、__init__
- **CLI**：`cli.py` 的脚手架功能
- **脚本**：`scripts/debug_fetcher.py` → `scripts/debug_source.py`
- **测试**：`tests/check_imports.py`
- **无前端影响**：`services/` 下无 fetcher 引用
- **无配置影响**：`app_data/config/` 下无 fetcher 引用

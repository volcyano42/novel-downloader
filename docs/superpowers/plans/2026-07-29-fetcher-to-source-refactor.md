# Fetcher → Source 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 Fetcher 中间类，重构为 source 驱动架构 — 底层函数通过 registry.resolve() 直接调用，统一命名字段。

**Architecture:** 删除 FanqieFetcher/QidianFetcher/QimaoFetcher + JsonSourceFetcher 四个类，用 registry.capabilities() + resolve() 替代。所有 fetcher 命名改为 source，fetch_* 改为 resolve_*，底层函数名对齐 capabilities 功能名。

**Tech Stack:** Python 3.13, FastAPI, pytest

## Global Constraints

- 路由 API 签名不变，前端不感知变化
- 所有测试保持通过
- `novelbase/__init__.py` 的公开接口保持向后兼容（重命名但保留旧名作为别名或直接替换）
- 提交用中文消息，一个方面一条 commit

---

### Task 1: 删除 JSON 书源体系

**Files:**
- Delete: `novelbase/utils/json_loader.py`
- Delete: `app_data/sources/example.json`
- Delete: `app_data/sources/`（空目录也删）
- Modify: `docs/session-prompt.md`

**Interfaces:**
- Consumes: nothing
- Produces: JSON 书源相关代码彻底移除

- [ ] **Step 1: 删除 json_loader.py**

```powershell
Remove-Item "D:\Linux\novel-downloader\novelbase\utils\json_loader.py"
```

- [ ] **Step 2: 删除 app_data/sources/ 目录**

```powershell
Remove-Item -Recurse -Force "D:\Linux\novel-downloader\app_data\sources"
```

- [ ] **Step 3: 更新 session-prompt.md — 从架构速览移除 json_loader.py**

```powershell
cd D:\Linux\novel-downloader
```

修改 `docs/session-prompt.md` 第 15 行：

old: `  utils/              logger.py, registry.py, hooks.py, json_loader.py, template_utils.py`

new: `  utils/              logger.py, registry.py, hooks.py, template_utils.py`

- [ ] **Step 4: 验证后端导入不受影响**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase import *; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: 运行全量测试确认无回归**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

Expected: 全部通过

- [ ] **Step 6: 提交**

```powershell
cd D:\Linux\novel-downloader; git add -A; git commit -m "chore: 删除 JSON 书源体系（json_loader.py + app_data/sources/）"
```

---

### Task 2: 重命名 FetcherNotFoundError → SourceNotFoundError

**Files:**
- Modify: `novelbase/core/exceptions.py`
- Modify: `novelbase/core/downloader.py`（所有 `FetcherNotFoundError` 引用）
- Modify: `novelbase/__init__.py`
- Modify: `docs/session-prompt.md`
- Modify: all files that import `FetcherNotFoundError`

**Interfaces:**
- Consumes: nothing
- Produces: `SourceNotFoundError` 替代 `FetcherNotFoundError`

- [ ] **Step 1: 修改 exceptions.py**

In `novelbase/core/exceptions.py`，将类名和默认消息从 `FetcherNotFoundError` 改为 `SourceNotFoundError`：

```python
class SourceNotFoundError(NovelDownloaderError):
    """未找到数据源。"""

    def __init__(self, message: str = "Source not found"):
        super().__init__(message)
```

- [ ] **Step 2: 查找所有引用**

```powershell
cd D:\Linux\novel-downloader; python -c "import os; [print(f) for f in os.popen('python -m grep \"FetcherNotFoundError\" --recursive --include=\"*.py\" .').read().splitlines()]"
```

Or use the grep tool:
```powershell
Select-String -Path "D:\Linux\novel-downloader" -Pattern "FetcherNotFoundError" -Include "*.py" -Recurse
```

Expected locations: `novelbase/core/downloader.py`, `novelbase/__init__.py`, `novelbase/core/exceptions.py`

- [ ] **Step 3: 替换 downloader.py 中的引用**

In `novelbase/core/downloader.py`，将第 4 行 import 和所有 raise/except 中的 `FetcherNotFoundError` 替换为 `SourceNotFoundError`：

```python
# line 4
from .exceptions import SourceNotFoundError

# lines 90, 108, 125, 142, 163: replace FetcherNotFoundError(...) with SourceNotFoundError(...)
```

- [ ] **Step 4: 更新 novelbase/__init__.py**

将 `FetcherNotFoundError` 改为 `SourceNotFoundError`（import 和 `__all__` 两处）。

- [ ] **Step 5: 更新 session-prompt.md 中的异常名称引用**

- [ ] **Step 6: 运行测试确认**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

Expected: 全部通过

- [ ] **Step 7: 提交**

```powershell
cd D:\Linux\novel-downloader; git add -A; git commit -m "refactor: 重命名 FetcherNotFoundError → SourceNotFoundError"
```

---

### Task 3: 删除 Fetcher 类 + 改为模块级常量

**Files:**
- Modify: `novelbase/fetchers/fanqie/__init__.py`
- Modify: `novelbase/fetchers/qidian/__init__.py`
- Modify: `novelbase/fetchers/qimao/__init__.py`
- Modify: `docs/session-prompt.md`

**Interfaces:**
- Consumes: nothing
- Produces: 每个 `fetchers/{name}/__init__.py` 导出 `NAME`, `HOSTS`, `ID_PATTERN` 三个模块级常量

- [ ] **Step 1: 重写 fanqie/__init__.py**

替换为：

```python
import re

NAME = "fanqie"
HOSTS = ("fanqienovel.com", "changdunovel.com")
ID_PATTERN = re.compile(r"^(?:book_id=?)?(\d{19})$")
```

删除 `_use_fetcher()` 函数和 `FanqieFetcher` 类。

- [ ] **Step 2: 重写 qidian/__init__.py**

替换为：

```python
import re

NAME = "qidian"
HOSTS = ("www.qidian.com", "book.qidian.com")
ID_PATTERN = re.compile(r"^(?:/(book|info)/?)?(\d{10})/?$")
```

- [ ] **Step 3: 重写 qimao/__init__.py**

替换为：

```python
import re

NAME = "qimao"
HOSTS = ("www.qimao.com", "qimao.com")
ID_PATTERN = re.compile(r"^(?:/shuku/?)?(\d+)$")
```

- [ ] **Step 4: 验证 backend import**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase import *; print('OK')"
```

Note: 当前会失败因为 `novelbase/__init__.py` 仍导入 `get_fetchers` 等（依赖被删的类）。暂时手动测试：

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase.fetchers.fanqie import NAME, HOSTS, ID_PATTERN; print(NAME, HOSTS, ID_PATTERN)"
cd D:\Linux\novel-downloader; python -c "from novelbase.fetchers.qidian import NAME, HOSTS, ID_PATTERN; print(NAME, HOSTS, ID_PATTERN)"
cd D:\Linux\novel-downloader; python -c "from novelbase.fetchers.qimao import NAME, HOSTS, ID_PATTERN; print(NAME, HOSTS, ID_PATTERN)"
```

Expected: 三个平台分别输出各自的 NAME / HOSTS / ID_PATTERN

- [ ] **Step 5: 提交**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/fetchers/fanqie/__init__.py novelbase/fetchers/qidian/__init__.py novelbase/fetchers/qimao/__init__.py; git commit -m "refactor: 删除 Fetcher 中间类，改为模块级常量"
```

---

### Task 4: 重命名底层函数文件 + 函数名对齐 capabilities

**Files:**
- Rename: `novelbase/fetchers/fanqie/browser/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/fanqie/browser/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/fanqie/browser/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/fanqie/requests/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/fanqie/requests/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/fanqie/requests/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/fanqie/api/oiapi/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/fanqie/api/oiapi/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/fanqie/api/oiapi/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/fanqie/api/rain/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/fanqie/api/rain/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/fanqie/api/rain/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/qidian/browser/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/qidian/browser/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/qidian/browser/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/qidian/requests/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/qidian/requests/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/qidian/requests/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/qimao/browser/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/qimao/browser/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/qimao/browser/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/qimao/requests/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/qimao/requests/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/qimao/requests/fetch_chapter.py` → `chapter_content.py`
- Rename: `novelbase/fetchers/qimao/api/rain/fetch_novel.py` → `novel_info.py`
- Rename: `novelbase/fetchers/qimao/api/rain/fetch_chapter_list.py` → `chapter_list.py`
- Rename: `novelbase/fetchers/qimao/api/rain/fetch_chapter.py` → `chapter_content.py`
- Modify: 所有 mode 目录下的 `__init__.py`（更新 import）

**Interfaces:**
- Consumes: nothing
- Produces: 底层函数统一命名为 `search`, `novel_info`, `chapter_list`, `chapter_content`, `login`

- [ ] **Step 1: 批量重命名文件**

```powershell
cd D:\Linux\novel-downloader\novelbase\fetchers

# fanqie
Rename-Item fanqie\browser\fetch_novel.py novel_info.py
Rename-Item fanqie\browser\fetch_chapter_list.py chapter_list.py
Rename-Item fanqie\browser\fetch_chapter.py chapter_content.py
Rename-Item fanqie\requests\fetch_novel.py novel_info.py
Rename-Item fanqie\requests\fetch_chapter_list.py chapter_list.py
Rename-Item fanqie\requests\fetch_chapter.py chapter_content.py
Rename-Item fanqie\api\oiapi\fetch_novel.py novel_info.py
Rename-Item fanqie\api\oiapi\fetch_chapter_list.py chapter_list.py
Rename-Item fanqie\api\oiapi\fetch_chapter.py chapter_content.py
Rename-Item fanqie\api\rain\fetch_novel.py novel_info.py
Rename-Item fanqie\api\rain\fetch_chapter_list.py chapter_list.py
Rename-Item fanqie\api\rain\fetch_chapter.py chapter_content.py

# qidian
Rename-Item qidian\browser\fetch_novel.py novel_info.py
Rename-Item qidian\browser\fetch_chapter_list.py chapter_list.py
Rename-Item qidian\browser\fetch_chapter.py chapter_content.py
Rename-Item qidian\requests\fetch_novel.py novel_info.py
Rename-Item qidian\requests\fetch_chapter_list.py chapter_list.py
Rename-Item qidian\requests\fetch_chapter.py chapter_content.py

# qimao
Rename-Item qimao\browser\fetch_novel.py novel_info.py
Rename-Item qimao\browser\fetch_chapter_list.py chapter_list.py
Rename-Item qimao\browser\fetch_chapter.py chapter_content.py
Rename-Item qimao\requests\fetch_novel.py novel_info.py
Rename-Item qimao\requests\fetch_chapter_list.py chapter_list.py
Rename-Item qimao\requests\fetch_chapter.py chapter_content.py
Rename-Item qimao\api\rain\fetch_novel.py novel_info.py
Rename-Item qimao\api\rain\fetch_chapter_list.py chapter_list.py
Rename-Item qimao\api\rain\fetch_chapter.py chapter_content.py
```

- [ ] **Step 2: 修改每个文件内的函数名**

对每个重命名后的文件，将函数名从旧名改为新名。例如 `novel_info.py`：

```python
# old
def fetch_novel(url: str, engine, **kwargs) -> Novel:

# new
def novel_info(url: str, engine, **kwargs) -> Novel:
```

`chapter_list.py`：`def fetch_chapter_list(...)` → `def chapter_list(...)`

`chapter_content.py`：`def fetch_chapter(...)` → `def chapter_content(...)`

`search.py` 和 `login.py`：文件名不变，函数名也不变。

- [ ] **Step 3: 更新所有 mode __init__.py 的 import**

每个 `{mode}/__init__.py` 更新为：

```python
# browser 有 login
from .search import search
from .novel_info import novel_info
from .chapter_list import chapter_list
from .chapter_content import chapter_content
from .login import login

# requests / api provider 无 login
from .search import search
from .novel_info import novel_info
from .chapter_list import chapter_list
from .chapter_content import chapter_content
```

受影响的 `__init__.py` 列表：
- `fanqie/browser/__init__.py`
- `fanqie/requests/__init__.py`
- `fanqie/api/oiapi/__init__.py`
- `fanqie/api/rain/__init__.py`
- `qidian/browser/__init__.py`
- `qidian/requests/__init__.py`
- `qimao/browser/__init__.py`
- `qimao/requests/__init__.py`
- `qimao/api/rain/__init__.py`

- [ ] **Step 4: 更新 api/__init__.py**

`fanqie/api/__init__.py` 和 `qimao/api/__init__.py` 无需修改（它们目前为空或只有 basic imports，检查确认）。

- [ ] **Step 5: 提交**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/fetchers/; git commit -m "refactor: 重命名底层函数文件对齐 capabilities（fetch_novel→novel_info 等）"
```

---

### Task 5: 重构 registry.py — 注册表改名 + capabilities 扩展

**Files:**
- Modify: `novelbase/utils/registry.py`

**Interfaces:**
- Consumes: Task 3（模块级常量就位）, Task 4（函数命名就位）
- Produces: `register_source()` 返回 `{name: {NAME, HOSTS, ID_PATTERN}}`；`capabilities()` 返回新格式；`resolve()` 适配新函数名

- [ ] **Step 1: 重写 register_source（原 register_fetcher）**

不再扫描类，改为扫描目录名 + import 模块级常量：

```python
_cache_source: dict[str, dict] | None = None


def _scan_sources() -> dict[str, dict]:
    """扫描 fetchers/ 目录，收集每个 source 的 NAME / HOSTS / ID_PATTERN。"""
    result = {}
    pkg_dir = Path(__file__).parent.parent / "fetchers"
    if not pkg_dir.exists():
        return result

    for entry in sorted(os.listdir(pkg_dir)):
        entry_path = pkg_dir / entry
        if entry.startswith("_") or entry == "__pycache__":
            continue
        # 单文件：fanqie.py → import novelbase.fetchers.fanqie
        if entry.endswith(".py") and entry not in ("__init__.py", "base.py"):
            module_name = entry[:-3]
        # 目录包：fanqie/__init__.py
        elif entry_path.is_dir() and (entry_path / "__init__.py").exists():
            module_name = entry
        else:
            continue
        try:
            module = import_module(f"..fetchers.{module_name}", __package__)
            result[module_name] = {
                "name": getattr(module, "NAME", module_name),
                "hosts": getattr(module, "HOSTS", ()),
                "id_pattern": getattr(module, "ID_PATTERN", None),
            }
        except ImportError as e:
            print(f"load source failed {module_name} reason: {e}")

    return result


def register_source() -> dict[str, dict]:
    global _cache_source
    if _cache_source is not None:
        return _cache_source
    with _lock:
        if _cache_source is not None:
            return _cache_source
        result = _scan_sources()
        if not result:
            result = _hardcoded_sources()
        _cache_source = result
    return _cache_source


def _hardcoded_sources() -> dict[str, dict]:
    """exe 环境兜底。"""
    return {
        "fanqie": {"name": "fanqie", "hosts": ("fanqienovel.com", "changdunovel.com"),
                   "id_pattern": re.compile(r"^(?:book_id=?)?(\d{19})$")},
        "qidian": {"name": "qidian", "hosts": ("www.qidian.com", "book.qidian.com"),
                   "id_pattern": re.compile(r"^(?:/(book|info)/?)?(\d{10})/?$")},
        "qimao": {"name": "qimao", "hosts": ("www.qimao.com", "qimao.com"),
                  "id_pattern": re.compile(r"^(?:/shuku/?)?(\d+)$")},
    }
```

在文件顶部添加 `import re`。

- [ ] **Step 2: 扩展 capabilities()**

改为返回 `{mode: {provider: [functions]}}` 或 `{mode: [functions]}`：

```python
def capabilities(name: str) -> dict[str, list[str]] | dict[str, dict[str, list[str]]]:
    """扫描 fetchers/{name}/ 目录，返回可用能力矩阵。

    >>> capabilities("fanqie")
    {"api": {"oiapi": ["search", "novel_info", "chapter_list", "chapter_content"],
             "rain": ["search", "novel_info", "chapter_list", "chapter_content"]},
     "browser": ["search", "novel_info", "chapter_list", "chapter_content", "login"],
     "requests": ["search", "novel_info", "chapter_list", "chapter_content"]}
    """
    pkg_dir = Path(__file__).parent.parent / "fetchers" / name
    if not pkg_dir.is_dir():
        return {}

    # 功能名 → 文件名映射
    FUNC_FILE_MAP = {
        "search": "search",
        "novel_info": "novel_info",
        "chapter_list": "chapter_list",
        "chapter_content": "chapter_content",
        "login": "login",
    }

    result: dict[str, list[str] | dict[str, list[str]]] = {}
    for mode_dir in sorted(pkg_dir.iterdir()):
        if not mode_dir.is_dir() or mode_dir.name.startswith("_") or mode_dir.name == "__pycache__":
            continue
        mode = mode_dir.name

        providers: dict[str, list[str]] = {}
        for sub in sorted(mode_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_") and sub.name != "__pycache__":
                funcs: list[str] = []
                for func_name, file_stem in FUNC_FILE_MAP.items():
                    if (sub / f"{file_stem}.py").exists():
                        funcs.append(func_name)
                if funcs:
                    providers[sub.name] = funcs

        # 检查 mode 目录自身是否有 .py 文件（无 provider 模式）
        direct_funcs: list[str] = []
        for func_name, file_stem in FUNC_FILE_MAP.items():
            if (mode_dir / f"{file_stem}.py").exists():
                direct_funcs.append(func_name)

        if providers:
            result[mode] = providers
        elif direct_funcs:
            result[mode] = direct_funcs

    return result
```

- [ ] **Step 3: 更新 resolve() 适配新函数名**

`resolve()` 已经使用 `function` 参数动态 import，只需确保 provider 路径正确。当前逻辑已支持，无需修改。但确认 `module_path` 组装时不需要特殊映射——因为 Task 4 已将文件名和函数名对齐。

- [ ] **Step 4: 删除旧的 _scan_plugins 和 _hardcoded_fetchers**

删除 `_scan_plugins()` 函数和 `_hardcoded_fetchers()` 函数。保留 `register_exporter` 和 `register_export_options` 不变（它们不走这个重构）。

- [ ] **Step 5: 验证 registry**

```powershell
cd D:\Linux\novel-downloader
python -c "from novelbase.utils.registry import register_source, capabilities, resolve; print(register_source()); print(capabilities('fanqie')); fn = resolve('fanqie', 'browser', 'search'); print(fn)"
```

Expected: 输出 source 字典、fanqie 能力矩阵、search 函数对象

- [ ] **Step 6: 提交**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/utils/registry.py; git commit -m "refactor: 重构 registry — register_source + capabilities 扩展功能字段"
```

---

### Task 6: 重构 downloader.py — 重命名 + 改用 resolve

**Files:**
- Modify: `novelbase/core/downloader.py`

**Interfaces:**
- Consumes: Task 2 (`SourceNotFoundError`), Task 3 (模块常量), Task 5 (`register_source`, `capabilities`, `resolve`)
- Produces: `resolve_meta`, `resolve_chapter_list`, `resolve_chapter`, `get_source`, `get_source_for_id`, `list_sources`

- [ ] **Step 1: 重写 downloader.py 头部 import 和辅助函数**

```python
from typing import Sequence, TypeVar

from .engine import BrowserEngine
from .exceptions import SourceNotFoundError
from .options import ExportOptions
from ..exporters.base import BASEExporter
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, Chapters, SearchResult
from ..utils.logger import get_logger

_T = TypeVar('_T')

_log = get_logger("novelbase.core.downloader")


def get_source(url: str) -> str | None:
    """根据 URL 查找匹配的 source 名称。"""
    from ..utils.registry import register_source
    from yarl import URL
    parsed = URL(url)
    for name, info in register_source().items():
        if parsed.host in info["hosts"]:
            return name
    return None


def get_source_for_id(novel_id: str) -> str | None:
    """根据 novel_id 查找匹配的 source 名称。"""
    from ..utils.registry import register_source
    import re as _re
    for name, info in register_source().items():
        pat = info.get("id_pattern")
        if pat and pat.match(novel_id):
            return name
    return None


def list_sources() -> list[str]:
    """返回所有已注册的 source 名称。"""
    from ..utils.registry import register_source
    return sorted(register_source().keys())
```

- [ ] **Step 2: 重写 search() — 改用 resolve**

```python
def search(platform: str,
           query: str,
           engine,
           skip_delay: bool = False,
           **kwargs) -> tuple[SearchResult, ...]:
    """搜索小说。"""
    from ..utils.registry import resolve as _resolve

    mode = engine.mode if hasattr(engine, 'mode') else engine.name
    provider = getattr(getattr(engine, 'options', None), 'name', None) if mode == 'api' else None

    if platform == "all":
        all_results: list[SearchResult] = []
        for name in list_sources():
            try:
                fn = _resolve(name, mode, "search", provider=provider)
                kwargs["skip_delay"] = skip_delay
                results = fn(query=query, engine=engine, **kwargs)
                for r in results:
                    r.platform = name
                all_results.extend(results)
            except Exception:
                pass
        return tuple(all_results)

    try:
        fn = _resolve(platform, mode, "search", provider=provider)
    except (ValueError, ImportError):
        raise SourceNotFoundError(f"source not found: {platform}")
    kwargs["skip_delay"] = skip_delay
    results = fn(query=query, engine=engine, **kwargs)
    for r in results:
        r.platform = platform
    return results
```

- [ ] **Step 3: 重写 login()**

```python
def login(platform: str, engine: BrowserEngine) -> AuthCredential:
    from ..utils.registry import resolve as _resolve

    mode = engine.mode if hasattr(engine, 'mode') else engine.name
    try:
        fn = _resolve(platform, mode, "login")
    except (ValueError, ImportError):
        raise SourceNotFoundError(f"source not found: {platform}")
    return fn(engine=engine)
```

- [ ] **Step 4: 重写 resolve_meta（原 fetch_meta）**

```python
def resolve_meta(url: str, engine, skip_delay: bool = False, **kwargs) -> Novel:
    from ..utils.registry import resolve as _resolve

    name = get_source(url)
    if name is None:
        raise SourceNotFoundError(f"source not found for: {url}")

    mode = engine.mode if hasattr(engine, 'mode') else engine.name
    provider = getattr(getattr(engine, 'options', None), 'name', None) if mode == 'api' else None
    kwargs["skip_delay"] = skip_delay
    fn = _resolve(name, mode, "novel_info", provider=provider)
    return fn(url=url, engine=engine, **kwargs)
```

- [ ] **Step 5: 重写 resolve_chapter_list（原 fetch_chapter_list）**

```python
def resolve_chapter_list(url: str, engine, skip_delay: bool = False, **kwargs) -> Chapters:
    from ..utils.registry import resolve as _resolve

    name = get_source(url)
    if name is None:
        raise SourceNotFoundError(f"source not found for: {url}")

    mode = engine.mode if hasattr(engine, 'mode') else engine.name
    provider = getattr(getattr(engine, 'options', None), 'name', None) if mode == 'api' else None
    kwargs["skip_delay"] = skip_delay
    fn = _resolve(name, mode, "chapter_list", provider=provider)
    return fn(url=url, engine=engine, **kwargs)
```

- [ ] **Step 6: 重写 resolve_chapter**

```python
def resolve_chapter(chapter: Chapter, engine, fetcher=None, skip_delay: bool = False, **kwargs) -> Chapter | None:
    """下载单个章节。

    Args:
        fetcher: DEPRECATED — 保留兼容旧调用，实际不使用。
    """
    from ..utils.registry import resolve as _resolve

    name = get_source_for_id(chapter.novel_id)
    if name is None:
        raise SourceNotFoundError(f"source not found for novel_id: {chapter.novel_id}")

    mode = engine.mode if hasattr(engine, 'mode') else engine.name
    provider = getattr(getattr(engine, 'options', None), 'name', None) if mode == 'api' else None
    kwargs["skip_delay"] = skip_delay
    fn = _resolve(name, mode, "chapter_content", provider=provider)
    return fn(chapter=chapter, engine=engine, **kwargs)
```

- [ ] **Step 7: 保留其他函数不变**

`get_exporters()`, `get_exporter_options()`, `split_into_groups()`, `export()` 不做任何修改。

删除 `get_fetcher_for_url`, `get_fetcher_for_id`, `get_fetchers`，替换为 `get_source`, `get_source_for_id`, `list_sources`。

`fetch_meta` 和 `fetch_chapter_list` 改为别名指向新函数名以保持向后兼容：

```python
# 向后兼容别名
fetch_meta = resolve_meta
fetch_chapter_list = resolve_chapter_list
```

- [ ] **Step 8: 验证 downloader 模块可导入**

```powershell
cd D:\Linux\novel-downloader; python -c "from novelbase.core.downloader import resolve_meta, resolve_chapter_list, resolve_chapter, get_source, get_source_for_id, list_sources, search, login; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: 提交**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/core/downloader.py; git commit -m "refactor: 重命名 downloader 函数 + 内部改用 registry.resolve()"
```

---

### Task 7: 更新 novelbase/__init__.py

**Files:**
- Modify: `novelbase/__init__.py`

**Interfaces:**
- Consumes: Task 6（新函数名就位）
- Produces: 公开接口更新

- [ ] **Step 1: 更新 import 和 __all__**

```python
from .core.downloader import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    export,
    get_source,
    get_source_for_id,
    list_sources as _list_sources_from_dl,
    get_exporters,
    get_exporter_options,
    split_into_groups,
    search,
    login,
)
# 向后兼容别名
fetch_meta = resolve_meta
fetch_chapter_list = resolve_chapter_list
get_fetcher_for_url = get_source
get_fetcher_for_id = get_source_for_id
get_fetchers = lambda: {k: type(k, (), {}) for k in _list_sources_from_dl()}  # 返回 dict 兼容旧代码
```

等等，这样太 hacky 了。简化：保留旧 `get_fetchers` 作为别名返回 dict（旧代码如 `app/ui.py` 需要 `dict` 格式），但既然我们改了调用方，直接在 Task 9 改调用方即可。

实际方案：

```python
from .core.downloader import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    export,
    get_source,
    get_source_for_id,
    list_sources as _list_sources_from_dl,
    get_exporters,
    get_exporter_options,
    split_into_groups,
    search,
    login,
)
from .core.exceptions import (
    ...
    SourceNotFoundError,
    ...
)
from .utils.registry import capabilities, resolve, list_sources
```

`__all__` 更新：

```python
__all__ = [
    "resolve_meta",
    "resolve_chapter_list",
    "resolve_chapter",
    # 向后兼容别名
    "fetch_meta",
    "fetch_chapter_list",
    "get_fetcher_for_url",
    "get_fetcher_for_id",
    "get_fetchers",
    # 新名
    "get_source",
    "get_source_for_id",
    "list_sources",
    ...
    "SourceNotFoundError",
    ...
]
```

加上向后兼容别名：

```python
fetch_meta = resolve_meta
fetch_chapter_list = resolve_chapter_list


def get_fetchers() -> dict:
    """DEPRECATED: use list_sources() instead."""
    return {k: type(k, (), {}) for k in _list_sources_from_dl()}


def get_fetcher_for_url(url: str):
    """DEPRECATED: use get_source() instead."""
    name = get_source(url)
    if name is None:
        return None
    from ..utils.registry import register_source
    return register_source().get(name)


def get_fetcher_for_id(novel_id: str):
    """DEPRECATED: use get_source_for_id() instead."""
    name = get_source_for_id(novel_id)
    if name is None:
        return None
    from ..utils.registry import register_source
    return register_source().get(name)
```

...实际上这太复杂了。Task 9 会更新所有调用方，所以直接删除旧名，不需要向后兼容别名。只在 Task 7 改 `__init__.py`，Task 9 同步改所有调用方。

简化方案：

```python
from .core.downloader import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    export,
    get_source,
    get_source_for_id,
    get_exporters,
    get_exporter_options,
    split_into_groups,
    search,
    login,
)
from .core.exceptions import (
    ...
    SourceNotFoundError,
    ...
)
from .utils.registry import capabilities, resolve, list_sources as list_registry_sources
```

在模块级别合并 list_sources：

```python
# downloader 和 registry 都有 list_sources，取 downloader 的（它调用 registry）
```

实际上 downloader 的 `list_sources()` 包装了 registry 的 `register_source()`，功能一样。用 downloader 的即可。但 registry 也有 `list_sources`（返回目录名列表）。我们需要统一。

OK，简化设计：`novelbase/__init__.py` 中只保留 downloader 的 `list_sources`（它返回 source name 列表）。

- [ ] **Step 1: 修改 novelbase/__init__.py**

```python
from .core.downloader import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    export,
    get_source,
    get_source_for_id,
    list_sources,
    get_exporters,
    get_exporter_options,
    split_into_groups,
    search,
    login,
)
from .core.engine import create_engine
from .core.exceptions import (
    NovelDownloaderError,
    NetworkError,
    AuthenticationError,
    NovelNotFoundError,
    ChapterNotFoundError,
    ParseError,
    SourceNotFoundError,
    FeatureNotSupportedError,
    StorageError,
    AntiCrawlError,
)
from .core.options import (
    Options,
    APIOptions,
    BrowserOptions,
    RequestsOptions,
    StorageOptions,
    ExportOptions,
)
from .core.storage import LocalStorage
from .exporters.base import BASEExporter
from .models.novel import Novel, Chapter, Chapters, Illustration, SearchResult
from .utils.registry import capabilities, resolve
from .utils.hooks import SourceHooks
```

`__all__` 对应更新：`resolve_meta`, `resolve_chapter_list`, ... `get_source`, `get_source_for_id`, `list_sources`, `SourceNotFoundError`。

删除 `FetcherNotFoundError`（已在 Task 2 改为 `SourceNotFoundError`）。删除 `fetch_meta`, `fetch_chapter_list`, `get_fetcher_for_url`, `get_fetcher_for_id`, `get_fetchers`。

- [ ] **Step 2: 提交**

```powershell
cd D:\Linux\novel-downloader; git add novelbase/__init__.py; git commit -m "refactor: 更新 novelbase/__init__.py 公开接口"
```

---

### Task 8: 更新 app/ 和 cli.py 引用

**Files:**
- Modify: `app/core.py`
- Modify: `app/ui.py`
- Modify: `cli.py`

**Interfaces:**
- Consumes: Task 6, Task 7

- [ ] **Step 1: 修改 app/core.py**

`app/core.py` 第 17-19 行：

```python
# old
from novelbase import (
    fetch_meta, fetch_chapter_list, resolve_chapter, export,
    create_engine, search, login,
)

# new
from novelbase import (
    resolve_meta, resolve_chapter_list, resolve_chapter, export,
    create_engine, search, login,
)
```

然后全局替换文件内的 `fetch_meta(` → `resolve_meta(`，`fetch_chapter_list(` → `resolve_chapter_list(`。

涉及行：81, 145, 154, 186（`cmd_info` 在 cli.py 中）, 342。

- [ ] **Step 2: 修改 app/ui.py**

`app/ui.py` 第 102-103 行：

```python
# old
from novelbase import get_fetchers
fetchers = get_fetchers()

# new
from novelbase import list_sources
sources = list_sources()
```

将变量 `fetchers` 改为 `sources`。

- [ ] **Step 3: 修改 cli.py**

`cli.py` 第 26 行：

```python
# old
from novelbase import create_engine, fetch_meta, get_fetcher_for_url

# new
from novelbase import create_engine, resolve_meta, get_source
```

第 186 行 `fetch_meta(args.url, engine)` → `resolve_meta(args.url, engine)`

第 204-219 行：删除 `from novelbase.utils.json_loader import list_json_sources as _ls_json` 及所有 JSON 源相关逻辑，简化为：

```python
def cmd_dev(args):
    """开发工具。"""
    if args.dev_command == "list-sources":
        from novelbase.utils.registry import list_sources as _ls_py
        if args.json:
            print("JSON 规则源已移除")
            return
        py_sources = _ls_py()
        print(f"Python 源 ({len(py_sources)}):")
        for s in py_sources:
            print(f"  - {s}")
```

第 245-246 行：`_scaffold_source` 中生成的脚手架文件名更新：

```python
# old
for fn in ("search", "fetch_novel", "fetch_chapter_list", "fetch_chapter"):

# new
for fn in ("search", "novel_info", "chapter_list", "chapter_content"):
```

第 255 行也更新：

```python
# old
print(f"  {mode}/  search.py, fetch_novel.py, fetch_chapter_list.py, fetch_chapter.py")

# new
print(f"  {mode}/  search.py, novel_info.py, chapter_list.py, chapter_content.py")
```

- [ ] **Step 4: 提交**

```powershell
cd D:\Linux\novel-downloader; git add app/core.py app/ui.py cli.py; git commit -m "refactor: 更新 app/ 和 cli.py 的 fetcher→source 引用"
```

---

### Task 9: 更新后端路由 + services

**Files:**
- Modify: `services/backend/routers/download.py`
- Modify: `services/backend/services/task_manager.py`

**Interfaces:**
- Consumes: Task 6, Task 7
- Produces: 新增 `GET /api/v2/sources`，现有路由改用新函数名

- [ ] **Step 1: 修改 download.py 路由**

`services/backend/routers/download.py`：

第 10 行 import：

```python
# old
from novelbase import fetch_meta, fetch_chapter_list, get_fetchers, search

# new
from novelbase import resolve_meta, resolve_chapter_list, list_sources, search
```

第 34 行：删除 `from novelbase.core.downloader import get_fetcher_for_url, get_fetcher_for_id`

第 41-42 行：`get_fetcher_for_url(query)` → `get_source(query)` 并调整逻辑（不再需要 fetcher_cls，直接用 resolve_meta）

第 44 行：`fetch_meta(query, engine)` → `resolve_meta(query, engine)`

第 52-58 行：同理，`get_fetcher_for_id(query)` → 简化为直接用 `resolve_meta`（通过 novel_id 构建 URL）

第 82 行：`fetch_meta` → `resolve_meta`
第 100 行：`fetch_meta` → `resolve_meta`
第 117 行：`fetch_chapter_list` → `resolve_chapter_list`

第 162-165 行 `list_platforms`：

```python
# old
@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": cls.__name__ if hasattr(cls, "__name__") else name}
            for name, cls in get_fetchers().items()]

# new
@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": name} for name in list_sources()]
```

- [ ] **Step 2: 新增 GET /api/v2/sources**

在 `download.py` 末尾添加：

```python
@router.get("/sources")
async def list_all_sources():
    """返回所有 source 及其完整能力矩阵。"""
    from novelbase.utils.registry import register_source, capabilities as _caps
    sources = register_source()
    result = {}
    for name, info in sources.items():
        caps = _caps(name)
        id_pat = info.get("id_pattern")
        result[name] = {
            "hosts": list(info.get("hosts", ())),
            "id_pattern": id_pat.pattern if id_pat else None,
            "capabilities": caps,
        }
    return result
```

注意路由前缀是 `/api/v2/download`，但 `/sources` 路由放在此不太合适。改为直接放 `/api/v2` 下，需新增一个 router。

实际上可以直接在 download.py 里加（prefix 是 `/api/v2/download` → 最终路径 `/api/v2/download/sources`），或者另建 `source.py`。考虑到变更最小化，放在 download.py 即可，路径是 `/api/v2/download/sources`。

- [ ] **Step 3: 修改 task_manager.py**

`services/backend/services/task_manager.py` 第 21 行：

```python
# old
from novelbase import fetch_meta, resolve_chapter

# new
from novelbase import resolve_meta, resolve_chapter
```

第 36 行：`fetch_meta(novel_url, engine)` → `resolve_meta(novel_url, engine)`

- [ ] **Step 4: 提交**

```powershell
cd D:\Linux\novel-downloader; git add services/; git commit -m "refactor: 更新后端路由 — 新增 /sources + 改用新函数名"
```

---

### Task 10: 更新测试

**Files:**
- Modify: `tests/test_downloader.py`

**Interfaces:**
- Consumes: Task 6

- [ ] **Step 1: 重写 test_downloader.py**

由于 `resolve_chapter` 不再需要 `fetcher` 参数，且内部改用 `registry.resolve()`，测试需要更新 mock 策略：

```python
"""Downloader 层测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from novelbase.core.downloader import resolve_meta, resolve_chapter_list, resolve_chapter, get_source, get_source_for_id
from novelbase.core.options import Options, StorageOptions
from novelbase.models.novel import Novel, Chapter, Chapters


def _make_chapter(chapter_id: str = "ch1", order: int = 1,
                  content: str | None = None) -> Chapter:
    return Chapter(
        id=chapter_id,
        url=f"https://example.com/{chapter_id}",
        novel_id="novel-1", title=f"第{order}章",
        order=order,
        content=content,
    )


def _make_engine():
    eng = MagicMock()
    eng.mode = "browser"
    return eng


class TestResolveChapter:
    def test_returns_chapter_when_content_available(self):
        """registry.resolve 返回填充后的 Chapter → resolve_chapter 原样返回"""
        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source_for_id", return_value="fanqie"):
            with patch("novelbase.utils.registry.resolve") as mock_resolve:
                mock_resolve.return_value = lambda chapter, engine, **kw: ch

                result = resolve_chapter(ch, engine)

        assert result is ch

    def test_returns_none_when_chapter_unavailable(self):
        """底层返回 None → resolve_chapter 透传 None"""
        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source_for_id", return_value="fanqie"):
            with patch("novelbase.utils.registry.resolve") as mock_resolve:
                mock_resolve.return_value = lambda chapter, engine, **kw: None

                result = resolve_chapter(ch, engine)

        assert result is None

    def test_raises_when_no_source_found(self):
        """get_source_for_id 返回 None → SourceNotFoundError"""
        from novelbase.core.exceptions import SourceNotFoundError

        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source_for_id", return_value=None):
            with pytest.raises(SourceNotFoundError, match="source not found"):
                resolve_chapter(ch, engine)


class TestResolveMeta:
    def test_delegates_to_resolve(self):
        """resolve_meta 通过 registry.resolve 调用底层 novel_info"""
        expected = Novel(
            id="n1", title="测试", url="https://fanqienovel.com/novel",
            author="作者", serial=1, description="",
        )
        engine = _make_engine()

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.utils.registry.resolve") as mock_resolve:
                mock_resolve.return_value = lambda url, engine, **kw: expected

                result = resolve_meta("https://fanqienovel.com/novel", engine)

        assert result is expected
```

- [ ] **Step 2: 运行测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/test_downloader.py -v --tb=short 2>&1
```

Expected: 全部通过

- [ ] **Step 3: 提交**

```powershell
cd D:\Linux\novel-downloader; git add tests/test_downloader.py; git commit -m "test: 更新 test_downloader.py 适配 source 重构"
```

---

### Task 11: 全量测试 + 文档更新

**Files:**
- Modify: `docs/session-prompt.md`

- [ ] **Step 1: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

Expected: 全部通过

- [ ] **Step 2: 更新 session-prompt.md**

更新架构速览：`json_loader.py` 已删除。

更新关键约定，反映所有命名变更。

更新验证命令（确保仍然有效）。

- [ ] **Step 3: 最终提交**

```powershell
cd D:\Linux\novel-downloader; git add docs/session-prompt.md; git commit -m "docs: 更新 session-prompt 反映 source 重构"
```

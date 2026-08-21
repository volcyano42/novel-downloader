# Web 后端 frozen 模式配置路径修复 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Web 后端在 Nuitka frozen 模式下配置路径解析错误，使 groups.yaml 修改持久化、database_url 正确解析。

**Architecture:** 在 `config_service.py` 中参照 CLI `app/config.py` 实现 frozen 感知路径解析（NLD_APP_DATA → sys.executable.parent → __file__），首次运行从 `_MEIPASS` 复制默认配置。其余文件将 hardcoded `database_url` 替换为 `config_service.get_database_url()`。

**Tech Stack:** Python 3.13, Nuitka, FastAPI

## Global Constraints

- 不改动 CLI 体系（app/config.py）
- 不修改前端
- 不修改构建脚本
- 提交用中文消息，一个方面一条 commit
- 每步后验证导入：`python -c "from services.backend.services.config_service import *; print('OK')"`
- 全量测试：`python -m pytest tests/ -v --tb=short` 保持 118 passed

---

### Task 1: config_service.py — 添加 frozen 路径解析

**Files:**
- Modify: `services/backend/services/config_service.py`

**Interfaces:**
- Consumes: nothing (第一个任务)
- Produces: `APP_DATA: Path`, `CONFIG_DIR: Path`, `get_database_url() -> str`, `_get_app_data_dir()`, `_copy_dir()`
- 内部替换：所有 `_config_dir` 引用 → `CONFIG_DIR`

- [ ] **Step 1: 在文件顶部添加 import 和路径解析函数**

在 `"""配置服务 — YAML 读写..."""` docstring 之后、`from pathlib import Path` 之前插入：

```python
import os
import shutil
import sys
```

在 `from pathlib import Path` 和 `import yaml` 之后、`_config_dir = ...` 之前插入：

```python
def _copy_dir(src: Path, dst: Path) -> None:
    """递归复制目录，保留已有文件（不覆盖）。"""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_dir(item, target)
        elif not target.exists():
            shutil.copy2(item, target)


def _get_app_data_dir() -> Path:
    """获取 app_data 目录。
    
    Priority: NLD_APP_DATA env > executable dir (frozen) > __file__ relative (dev).
    """
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        app_data = exe_dir / "app_data"
        if not app_data.exists():
            # 首次运行，从 _MEIPASS 复制默认配置
            meipass = Path(sys._MEIPASS)
            src = meipass / "app_data"
            if src.exists():
                _copy_dir(src, app_data)
            else:
                app_data.mkdir(parents=True, exist_ok=True)
        return app_data
    # 开发模式
    return Path(__file__).parent.parent.parent.parent / "app_data"


APP_DATA = _get_app_data_dir()
CONFIG_DIR = APP_DATA / "config"
```

- [ ] **Step 2: 替换旧的 `_config_dir` 为 `CONFIG_DIR`**

将第 5 行：
```python
_config_dir = Path(__file__).parent.parent.parent.parent / "app_data" / "config"
```
替换为：
```python
# CONFIG_DIR 已在上面通过 _get_app_data_dir() 初始化（支持 frozen 模式）
```

然后全文将所有 `_config_dir` 替换为 `CONFIG_DIR`（共约 10 处，分布在各函数中）。

- [ ] **Step 3: 修复 `user_data_dir` 默认值**

将第 16 行：
```python
        "user_data_dir": "app_data/browser/Chromium/User Data",
```
替换为：
```python
        "user_data_dir": str(APP_DATA / "browser" / "Chromium" / "User Data"),
```

- [ ] **Step 4: 添加 `get_database_url()` 工具函数**

在 `save_format_config` 函数之后（文件末尾）添加：

```python
def get_database_url() -> str:
    """返回 SQLite 数据库连接 URL（基于 APP_DATA 解析的绝对路径）。"""
    return f"sqlite:///{APP_DATA / 'storage' / 'novels.db'}"
```

- [ ] **Step 5: 验证导入**

```powershell
cd D:\Linux\novel-downloader
python -c "from services.backend.services.config_service import APP_DATA, CONFIG_DIR, get_database_url; print('APP_DATA:', APP_DATA); print('CONFIG_DIR:', CONFIG_DIR); print('DB_URL:', get_database_url()); print('OK')"
```

预期：OK，且路径指向项目根目录的 `app_data/`

- [ ] **Step 6: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

预期：118 passed

- [ ] **Step 7: 提交**

```powershell
cd D:\Linux\novel-downloader
git add services/backend/services/config_service.py
git commit -m "fix: config_service 添加 frozen 模式路径解析，持久化 groups.yaml 修改"
```

---

### Task 2: routers/storage.py — 替换 database_url

**Files:**
- Modify: `services/backend/routers/storage.py:16-22`

**Interfaces:**
- Consumes: `config_service.get_database_url()` (from Task 1)
- Produces: 无新接口

- [ ] **Step 1: 添加 import，替换 database_url**

在文件顶部 `from services.backend.schemas import ...` 之后添加：

```python
from services.backend.services.config_service import get_database_url
```

将 `_get_storage()` 函数（第 16-23 行）中的：
```python
def _get_storage():
    global _storage
    if _storage is None:
        _storage = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))
    return _storage
```
改为：
```python
def _get_storage():
    global _storage
    if _storage is None:
        _storage = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))
    return _storage
```

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader
python -c "from services.backend.routers.storage import router; print('OK')"
```

预期：OK

- [ ] **Step 3: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

预期：118 passed

- [ ] **Step 4: 提交**

```powershell
cd D:\Linux\novel-downloader
git add services/backend/routers/storage.py
git commit -m "fix: storage 路由使用 config_service.get_database_url()"
```

---

### Task 3: routers/export.py — 替换 database_url

**Files:**
- Modify: `services/backend/routers/export.py:35-38`

**Interfaces:**
- Consumes: `config_service.get_database_url()` (from Task 1)
- Produces: 无新接口

- [ ] **Step 1: 添加 import，替换 database_url**

在文件顶部 `from services.backend.schemas import ...` 之后添加：

```python
from services.backend.services.config_service import get_database_url
```

将 `trigger_export` 函数中（第 35-38 行）的：
```python
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))
```
改为：
```python
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))
```

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader
python -c "from services.backend.routers.export import router; print('OK')"
```

预期：OK

- [ ] **Step 3: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

预期：118 passed

- [ ] **Step 4: 提交**

```powershell
cd D:\Linux\novel-downloader
git add services/backend/routers/export.py
git commit -m "fix: export 路由使用 config_service.get_database_url()"
```

---

### Task 4: services/task_manager.py — 替换 database_url

**Files:**
- Modify: `services/backend/services/task_manager.py:28-31`

**Interfaces:**
- Consumes: `config_service.get_database_url()` (from Task 1)
- Produces: 无新接口

- [ ] **Step 1: 替换 import 行和 database_url**

将第 8 行：
```python
from services.backend.services.config_service import load_config
```
改为：
```python
from services.backend.services.config_service import load_config, get_database_url
```

将 `_run_download` 函数中（第 28-31 行）的：
```python
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))
```
改为：
```python
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))
```

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader
python -c "from services.backend.services.task_manager import create_task; print('OK')"
```

预期：OK

- [ ] **Step 3: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

预期：118 passed

- [ ] **Step 4: 提交**

```powershell
cd D:\Linux\novel-downloader
git add services/backend/services/task_manager.py
git commit -m "fix: task_manager 使用 config_service.get_database_url()"
```

---

### Task 5: routers/config.py — 切换到 CONFIG_DIR

**Files:**
- Modify: `services/backend/routers/config.py:9`

**Interfaces:**
- Consumes: `config_service.CONFIG_DIR` (from Task 1)
- Produces: 无新接口

- [ ] **Step 1: 替换 `_cfg_dir` 引用**

将第 9 行：
```python
_cfg_dir = config_service._config_dir  # noqa: SLF001
```
改为：
```python
_cfg_dir = config_service.CONFIG_DIR
```

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader
python -c "from services.backend.routers.config import router; print('OK')"
```

预期：OK

- [ ] **Step 3: 运行全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

预期：118 passed

- [ ] **Step 4: 提交**

```powershell
cd D:\Linux\novel-downloader
git add services/backend/routers/config.py
git commit -m "fix: config 路由使用 CONFIG_DIR 替代私有 _config_dir"
```

---

### Task 6: 最终验证

- [ ] **Step 1: 全量导入验证**

```powershell
cd D:\Linux\novel-downloader
python -c "from novelbase import *; print('OK')"
python -c "from services.backend.services.config_service import APP_DATA, CONFIG_DIR, get_database_url; print('OK')"
python -c "from services.backend.routers.storage import router; print('OK')"
python -c "from services.backend.routers.export import router; print('OK')"
python -c "from services.backend.services.task_manager import create_task; print('OK')"
python -c "from services.backend.routers.config import router; print('OK')"
```

- [ ] **Step 2: 全量测试**

```powershell
cd D:\Linux\novel-downloader; python -m pytest tests/ -v --tb=short 2>&1
```

预期：118 passed

- [ ] **Step 3: 验证 groups.yaml 读写（可选手动测试）**

```powershell
cd D:\Linux\novel-downloader; python -c "
from services.backend.services.config_service import CONFIG_DIR, load_yaml, save_yaml
path = CONFIG_DIR / 'groups.yaml'
print('groups.yaml path:', path)
print('exists:', path.exists())
data = load_yaml(path)
print('groups:', list(data.keys()))
print('OK')
"
```

# Web 后端 frozen 模式配置路径修复

2026-07-31

## 问题

Web 后端 (`services/backend/services/config_service.py`) 在 Nuitka frozen 模式下配置路径解析错误，导致：

1. **groups.yaml 修改丢失**：通过 WebUI 保存的分组写入 `_MEIPASS` 临时目录，exe 退出时清理，下次启动恢复为打包时的原始配置
2. **database_url 路径错误**：三处 hardcoded 的相对路径 `sqlite:///app_data/storage/novels.db` 在 frozen 下工作目录不可靠
3. **user_data_dir 路径错误**：浏览器用户数据目录的默认值 `app_data/browser/...` 是相对路径，在 frozen 下不会被解析到 exe 目录

### 根因

项目存在两套平行的配置路径体系：

| 体系 | frozen 处理 | 状态 |
|------|------------|------|
| CLI (`app/config.py`) | `NLD_APP_DATA` → `sys.executable.parent` → `__file__` + 首次复制 | ✅ |
| Web (`services/backend/services/config_service.py`) | `__file__` only | ❌ |

## 修复方案

在 `config_service.py` 中独立实现 frozen 感知的路径解析，不改动 CLI 体系。

### 改动文件

| 文件 | 变更 |
|------|------|
| `services/backend/services/config_service.py` | 核心修复：添加 frozen 路径解析 + 首次复制 + user_data_dir 解析 + get_database_url() |
| `services/backend/routers/storage.py` | 将 hardcoded `database_url` 替换为 `get_database_url()` |
| `services/backend/routers/export.py` | 同上 |
| `services/backend/services/task_manager.py` | 同上 |

### config_service.py 改动细节

#### 1. 添加 `_get_app_data_dir()` 函数

```python
def _get_app_data_dir() -> Path:
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        app_data = exe_dir / "app_data"
        if not app_data.exists():
            meipass = Path(sys._MEIPASS)
            src = meipass / "app_data"
            if src.exists():
                _copy_dir(src, app_data)
            else:
                app_data.mkdir(parents=True, exist_ok=True)
        return app_data
    return Path(__file__).parent.parent.parent.parent / "app_data"
```

优先级：`NLD_APP_DATA` 环境变量 > exe 目录（frozen）> `__file__` 相对路径（dev）

#### 2. 添加 `_copy_dir()` 辅助函数

递归复制目录，保留已有文件（不覆盖）。

#### 3. 模块级初始化

```python
APP_DATA = _get_app_data_dir()
CONFIG_DIR = APP_DATA / "config"
```

原 `_config_dir` 废弃，替换为 `CONFIG_DIR`。

#### 4. 修复 `user_data_dir` 默认值

```python
"user_data_dir": str(APP_DATA / "browser" / "Chromium" / "User Data"),
```

#### 5. 添加 `get_database_url()` 工具函数

```python
def get_database_url() -> str:
    return f"sqlite:///{APP_DATA / 'storage' / 'novels.db'}"
```

### 调用方改动

三处 hardcoded 的 `database_url="sqlite:///app_data/storage/novels.db"` 替换为：

```python
from services.backend.services.config_service import get_database_url
database_url = get_database_url()
```

位置：
- `services/backend/routers/storage.py:21`
- `services/backend/routers/export.py:37`
- `services/backend/services/task_manager.py:30`

### config.py 路由

`services/backend/routers/config.py:9` 通过 `config_service._config_dir` 访问路径，修改为导入 `CONFIG_DIR` 后自动修复。

## 不在范围

- `novelbase/utils/registry.py` 的 `__file__` 扫描 — 有硬编码兜底，风险可控
- `services/backend/main.py` 的 `_project_root` — 已有 frozen 分支保护
- `app/config.py` 的 `user_data_dir` 解析 — CLI 体系，不在此次修复范围
- `services/backend/schemas/export.py` 的 `output_path` — 实际使用 tempfile，影响极小
- 构建脚本 `build-web.ps1` — 打包内容无需变更

## 验证

```powershell
# 导入验证
python -c "from services.backend.services.config_service import APP_DATA, CONFIG_DIR, get_database_url; print('OK')"

# 全量测试
python -m pytest tests/ -v --tb=short
```

# init_config 重构：职责分离 + 启动接入

2026-07-31

## 目标

将 `app/init_config.py` 从 CLI 专属目录移到项目根，成为跨 CLI/WebUI 共用的独立模块。重构为**检查 + 初始化**分离的 API，并接入启动流程。

## 动机

1. 当前 `init_config(force)` 是一个粗粒度递归复制，无法按需初始化特定配置
2. 目前没有接入任何启动流程，是完全独立的脚本
3. 缺乏检查机制——不知道哪些配置缺失

## 设计

### API

```python
# ── 检查 ──

def check_config() -> dict:
    """检查 app_data/config/ 配置完整性。
    Returns: {
        'missing': ['sites/fanqie.yaml', 'formats/epub.yaml', ...],
        'all_missing': True,   # 全部配置都缺失时为 True
    }
    """

# ── 初始化（不检查，直接复制）──

def init_main_config() -> list[str]:
    """初始化 config.yaml + groups.yaml → app_data/config/"""

def init_site_config(platform: str) -> list[str]:
    """初始化 sites/{platform}.yaml → app_data/config/sites/
    platform="all" 初始化全部平台。"""

def init_export_config(format: str) -> list[str]:
    """初始化 formats/{format}.yaml → app_data/config/formats/
    format="all" 初始化全部格式。"""

def init_all_config() -> list[str]:
    """初始化全部（main + all sites + all formats）"""
```

### 模板源 → 运行时目标

模板目录：`template/config/`（随代码版本，跨 CLI/WebUI 共用）  
运行时目录：`app_data/config/`（用户可修改，gitignored）

**Frozen 模式路径解析**：`init_config.py` 内置 frozen 感知：

| 模式 | 模板源 (`_template_dir()`) | 目标 (`_target_dir()`) |
|------|--------------------------|------------------------|
| dev | `<项目根>/template/config/` | `<项目根>/app_data/config/` |
| frozen exe | `sys._MEIPASS/template/config/`（内嵌） | `sys.executable.parent/app_data/config/`（可写） |

| 函数 | 源 | 目标 |
|------|-----|------|
| `init_main_config()` | `template/config/config.yaml`, `groups.yaml` | `app_data/config/` |
| `init_site_config("fanqie")` | `template/config/sites/fanqie.yaml` | `app_data/config/sites/` |
| `init_site_config("all")` | `template/config/sites/*.yaml` | `app_data/config/sites/` |
| `init_export_config("epub")` | `template/config/formats/epub.yaml` | `app_data/config/formats/` |
| `init_export_config("all")` | `template/config/formats/*.yaml` | `app_data/config/formats/` |

### 接入点

| 入口 | 位置 | 调用 |
|------|------|------|
| CLI | `app/core.py:main()` 启动时 | `check_config()` → 有缺失则 `init_all_config()` + print 提示 |
| WebUI | `services/backend/main.py` lifespan startup | 同上 |

### 行为

- `check_config()` 只读，不写文件
- 所有 `init_*` 函数强制覆盖（不做存在性检查，调用方负责先 `check_config`）
- `init_site_config("all")` / `init_export_config("all")` 基于 `template/config/sites/` / `template/config/formats/` 下的实际文件列表初始化

### 目录移动

```
app/config/ → template/config/
```

`app/config/` 在 `app/`（CLI 专属）下不合理，移到 `template/` 作为跨 CLI/WebUI 共用的默认配置模板。

### 构建脚本

所有 6 个 `build-*` 脚本新增一行，将模板目录打包进 exe：

```powershell
--include-data-dir=template/config=template/config
```

同时保留已有的 `--include-data-dir=app_data/config=app_data/config`（运行时配置作为默认值打包）。

### 删除

- 旧的 `init_config(force)` 函数
- `main()` + `if __name__ == "__main__"` 块（独立脚本入口）

### 保留

- `_project_root()` 内部辅助函数
- `shutil.copy2` 复制方式

## 不在范围

- 不修改 `config_service.py` 的 frozen 首次复制逻辑（与 init_config 互补，不冲突）
- 不修改 `app/config.py` 的配置加载逻辑
- 不修改 `app_data/config/` 的现有文件

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 移动目录 | `app/config/` → `template/config/` |
| 移动文件 | `app/init_config.py` → `init_config.py`（项目根） |
| 重写 | `init_config.py`（检查+初始化分离 + frozen 感知） |
| 修改 | `app/core.py`（启动时调用 `check_config` + `init_all_config`） |
| 修改 | `services/backend/main.py`（lifespan 中同上） |
| 修改 | 6 个 `build-*.ps1` / `build-*.sh`（新增 `--include-data-dir=template/config`） |

## 验证

```powershell
python -c "from init_config import check_config, init_main_config, init_site_config, init_export_config; print('OK')"
python -m pytest tests/ -v --tb=short  # 118 passed
```

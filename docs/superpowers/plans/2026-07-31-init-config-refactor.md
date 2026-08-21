# init_config 重构 + template 目录 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `app/init_config.py` 移到项目根并重构为检查+初始化分离 API，`app/config/` 移到 `template/config/`，接入 CLI 和 WebUI 启动流程，构建脚本打包模板目录。

**Architecture:** `init_config.py` 内置 frozen 感知路径解析（dev: `__file__` 相对，frozen: `_MEIPASS` / `sys.executable.parent`），CLI 和 WebUI 启动时调用 `check_config()` → `init_all_config()`。

**Tech Stack:** Python 3.13, Nuitka

## Global Constraints

- 提交用中文消息，一个方面一条 commit
- 每步后验证 `python -m pytest tests/ -v --tb=short` 保持 118 passed
- 不修改 `config_service.py`、`app/config.py`、`app_data/config/` 现有文件

---

### Task 1: 移动 app/config/ → template/config/

**Files:**
- Rename: `app/config/` → `template/config/`

- [ ] **Step 1: git mv 移动目录**

```powershell
cd D:\Linux\novel-downloader
git mv app/config template/config
```

- [ ] **Step 2: 验证目录结构**

```powershell
Get-ChildItem template/config -Recurse -Name
```

预期：看到 config.yaml, groups.yaml, sites/fanqie.yaml, sites/qidian.yaml, sites/qimao.yaml, sites/92xs.yaml, formats/txt.yaml, formats/epub.yaml, formats/img.yaml

- [ ] **Step 3: 验证导入不受影响**

```powershell
python -c "from novelbase import *; print('OK')"
python -m pytest tests/ -v --tb=short
```

预期：OK + 118 passed（template/ 不是 Python 模块，不影响导入）

- [ ] **Step 4: 提交**

```powershell
git add template/config/ app/config/
git commit -m "refactor: 移动 app/config/ → template/config/（默认配置模板独立于 CLI）"
```

---

### Task 2: 创建 init_config.py（项目根）

**Files:**
- Create: `init_config.py`

- [ ] **Step 1: 创建文件**

```python
"""配置初始化 — 从 template/config/（默认）复制到 app_data/config/（运行时）。

设计：
  template/config/  ← 默认配置模板，跟随代码版本（跨 CLI/WebUI 共用）
  app_data/config/  ← 运行时配置，用户可修改，gitignored
"""
import shutil
import sys
from pathlib import Path


def _template_dir() -> Path:
    """模板源目录。frozen → _MEIPASS, dev → __file__ 上溯。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "template" / "config"
    return Path(__file__).resolve().parent / "template" / "config"


def _target_dir() -> Path:
    """运行时目标目录。frozen → exe 同目录, dev → 项目根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "app_data" / "config"
    return Path(__file__).resolve().parent / "app_data" / "config"


# ═══════════════════════════════════════════════════
# 检查
# ═══════════════════════════════════════════════════

def check_config() -> dict:
    """检查 app_data/config/ 配置完整性。

    Returns:
        {'missing': ['sites/fanqie.yaml', ...], 'all_missing': True/False}
    """
    template = _template_dir()
    target = _target_dir()
    missing: list[str] = []

    # 主配置
    for name in ("config.yaml", "groups.yaml"):
        if not (target / name).exists() and (template / name).exists():
            missing.append(name)

    # 站点配置
    tmpl_sites = template / "sites"
    tgt_sites = target / "sites"
    if tmpl_sites.is_dir():
        for f in tmpl_sites.glob("*.yaml"):
            rel = f" sites/{f.name}"
            if not (tgt_sites / f.name).exists():
                missing.append(rel.strip())

    # 格式配置
    tmpl_fmts = template / "formats"
    tgt_fmts = target / "formats"
    if tmpl_fmts.is_dir():
        for f in tmpl_fmts.glob("*.yaml"):
            rel = f" formats/{f.name}"
            if not (tgt_fmts / f.name).exists():
                missing.append(rel.strip())

    # 统计模板文件总数判断是否全部缺失
    total_tmpl = sum(1 for _ in template.rglob("*.yaml"))
    all_missing = total_tmpl > 0 and len(missing) == total_tmpl

    return {"missing": missing, "all_missing": all_missing}


# ═══════════════════════════════════════════════════
# 初始化（不检查，直接复制）
# ═══════════════════════════════════════════════════

def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def init_main_config() -> list[str]:
    """初始化 config.yaml + groups.yaml。"""
    template = _template_dir()
    target = _target_dir()
    initialized: list[str] = []
    for name in ("config.yaml", "groups.yaml"):
        src = template / name
        dst = target / name
        if src.exists():
            _copy_file(src, dst)
            initialized.append(str(dst))
    return initialized


def init_site_config(platform: str) -> list[str]:
    """初始化 sites/{platform}.yaml。platform="all" 初始化全部。"""
    template = _template_dir() / "sites"
    target = _target_dir() / "sites"
    initialized: list[str] = []
    if not template.is_dir():
        return initialized
    files = list(template.glob("*.yaml")) if platform == "all" else [template / f"{platform}.yaml"]
    for src in files:
        if src.exists():
            _copy_file(src, target / src.name)
            initialized.append(str(target / src.name))
    return initialized


def init_export_config(format: str) -> list[str]:
    """初始化 formats/{format}.yaml。format="all" 初始化全部。"""
    template = _template_dir() / "formats"
    target = _target_dir() / "formats"
    initialized: list[str] = []
    if not template.is_dir():
        return initialized
    files = list(template.glob("*.yaml")) if format == "all" else [template / f"{format}.yaml"]
    for src in files:
        if src.exists():
            _copy_file(src, target / src.name)
            initialized.append(str(target / src.name))
    return initialized


def init_all_config() -> list[str]:
    """初始化全部（main + all sites + all formats）。"""
    result: list[str] = []
    result.extend(init_main_config())
    result.extend(init_site_config("all"))
    result.extend(init_export_config("all"))
    return result
```

- [ ] **Step 2: 验证导入**

```powershell
cd D:\Linux\novel-downloader
python -c "from init_config import check_config, init_main_config, init_site_config, init_export_config, init_all_config; print('OK')"
```

- [ ] **Step 3: 验证 check_config 在现有环境返回空（配置已存在）**

```powershell
python -c "from init_config import check_config; r = check_config(); print(r); assert r['missing'] == []"
```

- [ ] **Step 4: 运行全量测试**

```powershell
python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 5: 提交**

```powershell
git add init_config.py
git commit -m "feat: 添加 init_config.py（检查+初始化分离 + frozen 感知）"
```

---

### Task 3: CLI 接入 — app/core.py

**Files:**
- Modify: `app/core.py`

- [ ] **Step 1: 在 main() 函数开头添加初始化调用**

在 `app/core.py:main()` 中，`print("Novel下载器 启动中...")` 之后、`while True:` 之前插入：

```python
        from init_config import check_config, init_all_config
        result = check_config()
        if result["missing"]:
            if result["all_missing"]:
                print("首次运行，正在从默认模板初始化配置...")
            init_all_config()
            print(f"已初始化 {len(result['missing'])} 个配置文件")
```

- [ ] **Step 2: 验证导入**

```powershell
python -c "from app.core import main; print('OK')"
```

- [ ] **Step 3: 运行全量测试**

```powershell
python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 4: 提交**

```powershell
git add app/core.py
git commit -m "feat: CLI 启动时自动检查和初始化配置"
```

---

### Task 4: WebUI 接入 — services/backend/main.py

**Files:**
- Modify: `services/backend/main.py`

- [ ] **Step 1: 在 lifespan startup 中添加初始化调用**

在 `services/backend/main.py` 的 `lifespan` 函数 startup 部分（`@asynccontextmanager` 内 `yield` 之前）添加：

```python
    # startup — 检查并初始化配置
    from init_config import check_config, init_all_config
    result = check_config()
    if result["missing"]:
        if result["all_missing"]:
            print("首次运行，正在从默认模板初始化配置...")
        init_all_config()
        print(f"已初始化 {len(result['missing'])} 个配置文件")
```

- [ ] **Step 2: 验证导入**

```powershell
python -c "from services.backend.main import app; print('OK')"
```

- [ ] **Step 3: 运行全量测试**

```powershell
python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 4: 提交**

```powershell
git add services/backend/main.py
git commit -m "feat: WebUI 启动时自动检查和初始化配置"
```

---

### Task 5: 更新 PowerShell 构建脚本

**Files:**
- Modify: `build-web.ps1`, `build-main.ps1`, `build-cli.ps1`

- [ ] **Step 1: build-web.ps1 — 第 41 行后插入**

在 `--include-data-dir=app_data/config=app_data/config` 之后新增一行：

```powershell
    --include-data-dir=template/config=template/config `
```

- [ ] **Step 2: build-main.ps1 — 第 30 行后插入**

同上。

- [ ] **Step 3: build-cli.ps1 — 第 30 行后插入**

同上。

- [ ] **Step 4: 提交**

```powershell
git add build-web.ps1 build-main.ps1 build-cli.ps1
git commit -m "build: 打包 template/config 目录到 exe（支持 init_config frozen 模式）"
```

---

### Task 6: 更新 Shell 构建脚本

**Files:**
- Modify: `build-web.sh`, `build-main.sh`, `build-cli.sh`

- [ ] **Step 1: 三个 .sh 文件，各在 `--include-data-dir=app_data/config=app_data/config \` 后插入**

```bash
    --include-data-dir=template/config=template/config \
```

- [ ] **Step 2: 提交**

```powershell
git add build-web.sh build-main.sh build-cli.sh
git commit -m "build: 打包 template/config 目录到 exe（Shell 脚本同步）"
```

---

### Task 7: 删除旧 app/init_config.py

**Files:**
- Delete: `app/init_config.py`

- [ ] **Step 1: 删除**

```powershell
git rm app/init_config.py
```

- [ ] **Step 2: 验证无残留引用**

```powershell
python -c "from novelbase import *; print('OK')"
python -m pytest tests/ -v --tb=short
```

预期：OK + 118 passed

- [ ] **Step 3: 提交**

```powershell
git commit -m "chore: 删除旧的 app/init_config.py（已迁移到根目录）"
```

---

### Task 8: 最终验证

- [ ] **Step 1: 全量导入验证**

```powershell
cd D:\Linux\novel-downloader
python -c "from novelbase import *; print('OK')"
python -c "from init_config import check_config, init_main_config, init_site_config, init_export_config, init_all_config; print('OK')"
python -c "from app.core import main; print('OK')"
python -c "from services.backend.main import app; print('OK')"
```

- [ ] **Step 2: 全量测试**

```powershell
python -m pytest tests/ -v --tb=short
```

预期：118 passed

- [ ] **Step 3: 验证 check_config 判断全部缺失场景（手动模拟）**

```powershell
# 备份现有 groups.yaml，测试全部缺失检测
python -c "
from init_config import check_config
result = check_config()
print('check_config:', result)
assert isinstance(result['missing'], list)
assert isinstance(result['all_missing'], bool)
print('OK')
"
```

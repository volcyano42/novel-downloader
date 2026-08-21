# novel-downloader 目录结构重构设计

**日期**: 2026-08-12
**状态**: 已确认，待实施

---

## 一、动机

现有目录结构存在三个问题：

1. **默认值三处重复**：`services/backend/services/config_service.py` 硬编码 `ENGINE_DEFAULTS/GLOBAL_DEFAULTS/FMT_DEFAULTS`，与 `novelbase/core/options.py` 的 dataclass 默认值、`template/config/*.yaml` 三处重复。新增字段需同步改三处，易漏易错。

2. **跨层调用**：`services/backend/routers/config.py` 直接 `import cli_lib.user_db`，后端反向依赖 CLI 层，违反分层单向依赖。

3. **目录名别扭**：`services/backend/` + `services/frontend/` 嵌套无意义；`cli_lib/` 是半共享半客户端的模糊层；`template/`（配置模板）与 `services/`（代码）同层并列。

参考 `golang-standards/project-layout`（Go 标准布局）与 `.refer/DeepSeek-Reasonix` 的多客户端架构：`cmd/` 薄入口 + `internal/` 共享核心 + 各客户端薄壳，客户端之间互不依赖。

---

## 二、目标结构

```
novel-downloader/
├── novelbase/           # 纯核心库（引擎/书源/存储/模型/导出），零应用层文件
│   ├── core/
│   ├── models/
│   ├── sources/
│   ├── exporters/
│   └── utils/
│
├── shared/              # ★ 新增：共享应用层（cli 和 backend 都依赖）
│   ├── __init__.py
│   ├── config.py        # 配置加载（合并原 cli_lib/config.py + backend/config_service.py）
│   └── user_data.py     # 用户数据（原 cli_lib/user_db.py）
│
├── backend/             # Web 后端（原 services/backend 上提）
│   ├── main.py
│   ├── api/             # 原 routers/
│   ├── schemas/
│   └── services/        # engine_manager / task_manager
│
├── cli/                 # CLI（原 cli.py + cli_lib 合并，保留分组功能）
│   ├── __init__.py
│   ├── main.py          # 原 cli.py
│   ├── config.py        # 原 cli_lib/config.py（薄，代理 shared）
│   └── core.py          # 原 cli_lib/core.py
│
├── frontend/            # React（原 services/frontend 上提）
│
├── scripts/             # ★ 新增：构建 + 迁移 + 维护脚本
│   ├── build-nuitka.ps1
│   ├── build-portable.ps1
│   ├── build-portable.sh
│   ├── build-pypi.ps1
│   ├── build-pypi.sh
│   └── migrate_storage.py   # storage 分层迁移（一次性）
│
├── template/            # 配置模板（保持，被 shared/config.py 读取）
├── app_data/            # 运行时数据（git 未跟踪，保持）
│   ├── config/
│   └── storage/
│       ├── novels/      # ★ 小说库（每本一个 .db，全局共享）
│       └── users/       # ★ 用户数据（按 user_id 隔离）
│           └── default/
│               └── user_data.db
│
├── tests/
├── docs/
├── pyproject.toml
└── app.py               # 统一启动器（顶层入口，非脚本）
```

---

## 三、分层与依赖方向

依赖必须**单向、无环、无跨层**：

```
frontend ──HTTP──▶ backend ──▶ shared ──▶ novelbase
                        ▲
                        cli ──▶ shared ──▶ novelbase
```

规则：

- `novelbase` 零依赖应用层，只依赖第三方库（requests/httpx/bs4/yaml/DrissionPage）
- `shared` 依赖 `novelbase`（config 默认值从 novelbase 的 options.py 派生）
- `backend` 依赖 `shared` + `novelbase`
- `cli` 依赖 `shared` + `novelbase`
- `backend` 与 `cli` **互不 import**
- `frontend` 只通过 HTTP 与 `backend` 通信

---

## 四、默认值单一数据源

删除 `shared/config.py` 中硬编码的默认值，改为从 `novelbase/core/options.py` 的 dataclass 字段默认值自动派生。

### 方案

利用 Python `dataclasses.fields()` 读取 dataclass 字段默认值：

```python
# shared/config.py
from dataclasses import fields, MISSING
from novelbase.core.options import BrowserOptions, RequestsOptions

def _dataclass_defaults(cls) -> dict:
    """从 dataclass 字段默认值派生默认配置 dict。"""
    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:
            result[f.name] = f.default_factory()
    return result

ENGINE_DEFAULTS = {
    "browser": _dataclass_defaults(BrowserOptions),
    "requests": _dataclass_defaults(RequestsOptions),
    "api": {},   # API 是 variant 容器，无固定默认值
}
```

### 收益

- 新增字段**只改 `novelbase/core/options.py` 一处**，`shared/config.py` 自动跟随
- `template/config/*.yaml` 只放"用户可覆盖的示例"，不重复默认值

### 注意点

- `BrowserOptions.user_data_dir` 默认是 `None`，而 config_service 现有默认值是 `str(APP_DATA/browser/Chromium/User Data)` —— 这类"依赖运行时路径的动态默认值"不能用 dataclass 静态默认值表达，需在 `shared/config.py` 里保留少量路径相关的覆盖逻辑（仅路径类，非字段默认值）。
- `delay` 默认是 `(3.0, 5.0)` tuple，YAML 序列化时需转 list，读回时转 tuple。

---

## 五、storage 分层

### 5.1 目录结构

```
app_data/storage/
├── novels/              # 小说库，全局共享
│   ├── fanqie_xxx.db
│   └── ...
└── users/               # 用户数据，按 user_id 隔离
    └── default/
        └── user_data.db
```

### 5.2 路径变更点

| 文件（重构后位置） | 现状 | 改为 |
|------|------|------|
| `shared/user_data.py` | `DB_PATH = ROOT/app_data/storage/user_data.db` | `ROOT/app_data/storage/users/default/user_data.db` |
| `shared/config.py` 的 `get_database_url()` | `sqlite:///{APP_DATA}/storage/novels.db` | `sqlite:///{APP_DATA}/storage/novels/catalog.db` |
| `novelbase/core/storage.py`（SQLiteStorage base_dir） | 由 database_url 的 parent 定位 | 跟随 database_url，无代码改动 |

> **注意 database_url 的语义**：`SQLiteStorage.__init__` 用 `_parse_sqlite_url(url).parent` 定位 `base_dir`（因为小说是"一小说一库"，`database_url` 实际充当"目录定位器"，其 parent 才是真正的库目录）。因此必须返回一个**文件名**（如 `catalog.db`），让 parent 精确落在 `storage/novels/`。不能返回以 `/` 结尾的目录路径，否则 parent 会退回 `storage/`。

### 5.3 多用户设计

- 当前只有 `default` 用户，`user_data.py` 内部通过 `user_id` 参数（默认 `"default"`）定位 `users/{user_id}/user_data.db`
- 未来加用户 = 新建 `users/{user_id}/user_data.db`，现有代码零改动
- 小说库暂不按用户隔离（一本小说下载一次全局可用）；若未来需要，下沉为 `users/{user_id}/novels/`

### 5.4 迁移

一次性迁移脚本 `scripts/migrate_storage.py`：

1. `storage/*.db`（排除 `user_data.db` 与 `sync.ffs_db`）→ `storage/novels/`
2. `storage/user_data.db` → `storage/users/default/user_data.db`
3. 迁移前打印清单，迁移后校验文件数一致
4. 幂等：已迁移则跳过

---

## 六、cli 改造

### 6.1 保留分组功能

`groups` 表是 cli 与 WebUI 共享的功能，**保留**。`user_data.db` 归 `shared/`，cli 通过 `shared.user_data` 访问，不再有 `cli_lib.user_db`。

### 6.2 入口形式

`cli.py` → `cli/main.py`，调用方式从 `python cli.py` 变为 `python -m cli`（或 `python -m cli.main`）。

- `cli/__init__.py` 提供 `main()` 入口
- 构建脚本中的 CLI 相关引用同步更新

---

## 七、需要同步更新的引用

| 引用位置 | 变更 |
|---------|------|
| `app.py` | `services.backend.main:app` → `backend.main:app`；`services/frontend` → `frontend` |
| `build-nuitka.ps1` | `--include-package=services.backend` → `backend`；`services/frontend/dist` → `frontend/dist` |
| `build-portable.sh` | `services/frontend` → `frontend`；`services.backend.main:app` → `backend.main:app` |
| `services/backend/*.py` 内部 import | `services.backend.*` → `backend.*` |
| `cli_lib/*.py` 内部 import | `cli_lib.*` → `cli.*` |
| `init_config.py` | template 路径不变（`template/` 保持顶层） |
| `pyproject.toml` | 如有包路径配置，同步 |
| `tests/` | import 路径同步更新 |

---

## 八、不做的

- ❌ 不拆分 novelbase（它是纯核心库，保持完整）
- ❌ 不引入 Pydantic Settings（项目已有 Options dataclass 体系，额外依赖无必要）
- ❌ 不把 config/user_data 塞进 novelbase（保持核心层纯净）
- ❌ 不删除 `groups` 表（cli 与 WebUI 共享）
- ❌ 不把 `app.py` 移入 scripts/（它是启动入口，不是脚本）
- ❌ 不迁移小说库到按用户隔离（多用户场景未到）

---

## 九、风险与缓解

| 风险 | 缓解 |
|------|------|
| import 路径大面积改动引入错误 | 分步实施，每步跑 pytest + 导入验证 |
| storage 迁移误删数据 | 迁移脚本先打印清单、幂等、校验文件数，不删除源文件（先 copy 后人工确认再删） |
| Nuitka 打包路径失效 | build-nuitka.ps1 同步更新，打包后验证 exe 启动 |
| cli 入口从 `cli.py` 变 `python -m cli` 影响习惯 | 文档同步更新；保留顶层薄 `cli.py` 转调 `cli.main`（可选） |

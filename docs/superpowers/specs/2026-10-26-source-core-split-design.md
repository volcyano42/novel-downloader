# 书源与 core 结构分离 — 设计

> **状态**：已实施（2026-10-26）。结构层与合规层**同日均已落地**。
> **性质**：A1「core / 源分离」的**结构层**实现。它只搬骨架、不动契约。
> **合规层（同日追加）**：7 个红名单源已由 `scripts/migrate_private_sources_out.py` 搬出仓库到
> `<APP_DATA>/sources/`（不进 git），`novelbase/sources/builtin/` 只剩 3 个可公开源。
> **仍不在范围**：`docs/source-plugin.md` 的子进程 JSON-RPC 插件、合规示范源（I2）。

## 1. 背景与目标

`novelbase/sources/` 这个包**同时装着两种东西**：core 代码（`manifest.py` / `contracts.py`）与 10 个书源目录（站点数据 + 站点逻辑）。两者平级混装，导致：

- 源只有待在 `novelbase/sources/` 包内才能被 `import_module` 加载 → 想分发/隔离只能动包树
- `pyproject.toml` 的 `package-data` 以包名为键 → 源被硬绑进 wheel
- 「内置 vs 私有」这个身份概念真实存在于代码里（`is_builtin` 决定走哪条加载路径）

**目标**：让「源在哪个根」与「core 怎么加载它」解耦。官方源与用户源走同一条代码路径，包内包外无差别。

**非目标**：不改 `list_sources` / `get_manifest` / `capabilities` / `resolve` / `resolve_book_url` 的签名与语义；不改 `source.json` 格式；不改 backend / cli / frontend。

## 2. 决定性事实（本设计的前提）

10 个源对 core 的全部依赖只有两个面（已用 grep 核实，无例外）：

```python
from novelbase.core.exceptions import ...
from novelbase.models.novel import ...
```

没有任何源 import 过 `engine` / `storage` / `options` / `downloader` / `source` / `manifest` —— engine 是**参数注入**的。所以分离不需要重构源，只需要改「从哪找到它」。

## 3. 目录布局

```
novelbase/sources/
├── __init__.py
├── contracts.py          core：CAPABILITY_META / required_params
├── manifest.py           core：load_manifest / check_capability_files / scan_source_names
└── builtin/              官方源（随 wheel 发行）
    ├── __init__.py
    └── fanqie_requests_default/ ... （10 个，本次全部迁入）

<APP_DATA>/sources/       用户源（不进任何仓库，由 shared 层接线）
└── my_source/{__init__.py, source.json, *.py}
```

分界线：`contracts.py` + `manifest.py` 是**机制**（core）；`builtin/` 是**官方随附的数据**。官方源与用户源在加载路径上完全平等。

## 4. 源根（有序）

```python
def _source_roots() -> list[Path]:
    return [
        *env_roots("NLD_SOURCE_ROOTS"),   # os.pathsep 分隔，多根
        env_root("NLD_PRIVATE_SOURCES"),  # 旧变量，保留为追加根（兼容）
        *explicit_roots(),                # add_source_root() 注入（shared 用它加 APP_DATA/sources）
        _SOURCES_DIR / "builtin",         # 官方根，可不存在
    ]  # 过滤掉不存在的目录
```

- **顺序不改变语义**：撞名一律抛 `DuplicateSourceNameError`，不退化成一占先得。顺序只影响报错消息里的「先占者」。
- **`novelbase` 不认识 `app_data`**：它是可 `pip install` 的纯库，不能反向 import `shared`（会成环）。用户根由 `shared.config` 在 import 时 `add_source_root(APP_DATA / "sources")` 注入。直接用 novelbase 的第三方用户拿到的就是「builtin + env 根」——符合纯库定位。
- 环境变量必须**在函数体内**读取（多个测试依赖 `monkeypatch.setattr(source, "_PRIVATE_SOURCES_ROOT", ...)` 生效）。

## 5. 统一加载路径

非编译模式下所有源一律 `spec_from_file_location`，删除 `_resolve_import`（`import_module` 依赖包路径，源出包即失效）。

**模块名必须带根标识**（现存缺陷）：现在模块名是 `novelbase_private.sources.{dirname}.{capability}`，不含根标识。多根之后若两个根下都有 `mysource/` 目录（不同 `source_name`），会命中同一个 `sys.modules` key → 后加载的静默覆盖前者。改为：

```python
tag = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]
module_name = f"nld_src_{tag}.{dirname}.{capability}"
```

**编译模式是已知特例**：Nuitka 产物里 `builtin/` 下的 `.py` 已编译、文件系统无源文件，只能靠 `utils/_manifest.py` 静态表 + `import_module`。因此编译模式下 `builtin` 根走静态表，其余根照常走文件系统。该特例仅存在于编译产物，非编译路径完全统一。

## 6. 打包

```toml
[tool.setuptools.package-data]
"novelbase.sources.builtin" = ["*/source.json"]
```

这行是 wheel 不丢源的唯一护栏（不声明则 `pip install .` 后 `list_sources()` 静默返回空，见 `docs/project/updates.md:631`）。`tests/check_imports.py` 与 `novelbase/utils/build_manifest.py` 扫描的根同步改为 `builtin/`。

## 7. 迁移脚本

`scripts/migrate_sources_to_builtin.py`，与既有迁移脚本（`migrate_user_data.py` / `migrate_storage.py`）同风格：

- 默认 **dry-run**，`--apply` 才动盘
- 幂等：已在 `builtin/` 的跳过；`builtin` 已存在同名目录 → 报错不自作主张覆盖
- 逐个移动 `novelbase/sources/{dir}` → `novelbase/sources/builtin/{dir}`，清理 `__pycache__`
- 用 `git mv`（文件被跟踪时保留历史），失败回退 `shutil.move`

## 8. 兼容性与破坏面

| 项 | 影响 |
|---|---|
| `NLD_PRIVATE_SOURCES` | 保留为追加根，语义不变 → 现有测试与本机用法全部继续有效 |
| `monkeypatch.setattr(source, "_PRIVATE_SOURCES_ROOT", ...)` 共 7 处 | 保留该模块级变量即可全绿 |
| `source.json` / 配置 / 书架 / API | **零影响**，一切按 `source_name` 索引 |
| `_manifest.py`（Nuitka） | 生成内容不变，扫描根改 `builtin/` |
| 目录名 | 源目录名不变，只多一层 `builtin/` |

## 9. 验证

- `python -m pytest tests/ -q` → 595 passed 基线不降
- `tests/check_imports.py` 通过（它校验「包内源清单 ⇔ 实际目录」）
- 手工：`NLD_SOURCE_ROOTS=/tmp/x:/tmp/y python -c "from novelbase import list_sources; print(list_sources())"` 多根合并、撞名报错
- 手工：两个根各放一个同名目录、不同 `source_name` → 各自 `resolve()` 拿到自己的函数（模块名隔离）
- 出仓后两环境实测：**有源** 617 passed / 1 failed（已知 `test_detect_encoding_gbk`）；**无源**（模拟新机器/公开子集）479 passed / **136 skipped** / 1 failed —— 缺源由 `tests/conftest.py` 整模块 skip，不是红
- 闸门：`scripts/check_public.py` 对 7 个红名单源 **0 误报**，白名单只剩 3 个可公开源

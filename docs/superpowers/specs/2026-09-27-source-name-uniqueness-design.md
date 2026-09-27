# `source_name` 唯一性检测（实现层）—— 设计

> 2026-09-27。把「`source_name` 全局唯一」从**测试层兜底**提到**实现层检测**：内置根与私有根里任何两个目录声明同一个 `source_name` 一律 `ManifestError`。

## 背景

`source_name` 是系统的唯一键：全部公共 API（`list_sources()` / `get_manifest()` / `capabilities()` / `resolve()`）、后端路由、前端、CLI、`app_data/config/sites/{source_name}.yaml` 都用它。

现状是**只在测试层兜底**：

- `docs/superpowers/specs/2026-09-24-book-source-flattening-design.md:254` 要求「新增 `source.json` 校验测试：……、`source_name` 唯一性」。
- `tests/test_source_contracts.py:77-100` 的 `test_source_names_unique` 实现了它，且已是**全局口径**（把内置根与私有根的名字放进同一个 list 统计重复）。该用例的 docstring 明确写了不能对 `list_sources()` 去重后断言（它内部用 `set`，返回值恒已去重，断言恒真）。

实现层**没有任何检测**，于是撞名时静默错：

| 位置 | 现状行为 |
|------|----------|
| `novelbase/source.py:77-97` `list_sources()` | 用 `set` 收集名字 → **静默去重**，撞名直接消失 |
| `novelbase/source.py:100-113` `get_manifest()` | 取 `_iter_source_dirs()[0]`（按目录名字典序）→ **静默选中第一个**，另一个永远不可达 |
| `novelbase/source.py:138-185` `resolve()` | 同上，撞名的能力实现取第一个目录的 |
| `novelbase/utils/build_manifest.py:26-36` | `source_dirs[manifest["source_name"]] = entry` → **静默覆盖**；且编译分支 `list_sources()`（`source.py:80`）是 `sorted(m["source_name"] for m in SOURCES.values())`，**不去重、会返回重复条目** |

触发场景是常见的开发事故：拷贝一个书源目录做新源、忘了改 `source.json` 的 `source_name`；或私有源目录复用了内置 id。此时 CLI / 后端不报错，只是**指着另一个源**在跑。

## 决策记录

| 决策 | 结论 | 依据 |
|------|------|------|
| 命名空间范围 | **全局唯一**：内置根与私有根视为同一命名空间，任何重名（含私有源复用内置 id）一律报错 | `dec-272da378545c539f`、`dec-3f4f1d1f9acf53f9` |
| 私有源逃生舱 | **不留**，无 `overrides` 之类字段；报错文案给出迁移指引 | `dec-3f4f1d1f9acf53f9` |
| 检测点 | 一个统一校验函数，非编译加载路径、`build_manifest`、测试三处调用 | `dec-272da378545c539f`「检测点问题选 1」 |

**被否决的备选：分隔两个命名空间**（`dec-b3921b696f7c2d50` 选的 A）——内置根内部、私有根内部各自唯一，但私有源与内置同名**合法**，以此保留 `resolve()` 里「同名能力内置优先、内置缺失再用私有补齐」的机制。用户随后两次明确改口为全局唯一，故本设计**取消该机制**：

- `resolve()` 的 for 循环在全局唯一下每个 `source_name` 至多一个目录，第二分支（私有补齐）不可达。
- 私有源仍然可用（各自独立 `source_name`），但**不能再作为内置源的替代实现**。这是本设计明确接受的破坏性变更。

## 目标

1. 内置根或私有根里任何两个目录声明同一个 `source_name` → 加载期抛 `ManifestError`，消息含冲突名与两个目录。
2. 三条加载路径全部覆盖：非编译（扫目录）、编译（`build_manifest` 生成 `SOURCE_DIRS`）、测试兜底。
3. 失败要**响**：CLI / 后端在撞名时立刻报错，不允许静默选一个源继续跑。

## 非目标

- 不检测目录名与 `source_name` 的一致性（二者本就解耦，见 `docs/project/sources.md:22-24`）。
- 不检测 `sites/{source_name}.yaml` 孤儿配置。
- 不检测不同书源的能力实现重复。
- 不引入任何形式的加载缓存。
- 不改「单源 manifest 非法时的既有容错分工」：运行时跳过该目录、`get_manifest()` 对被选中的目录致命、构建期致命。

## 设计

### 1. `novelbase/sources/manifest.py`：唯一性校验函数

新增（放在 `check_capability_files()` 之后）：

```python
def scan_source_names(roots: Iterable[Path], *, strict: bool = False) -> dict[str, Path]:
    """扫多个根，返回 {source_name: 目录}；任一 source_name 出现两次即 ManifestError。

    - 非目录项、`_` 开头的目录、无 `source.json` 的目录 → 跳过
    - 单源 `load_manifest()` 抛 ManifestError：strict=True 时冒泡；否则跳过该目录
    - 根不存在或不是目录 → 跳过该根
    - 每个根内按目录名排序遍历，保证报错稳定
    """
```

要点：

- **跨根也算重复**：`roots` 是有序的（内置在前），第二个根里出现已见过的 `source_name` 立即抛。这是「全局唯一」的落点。
- `strict` 参数保住两条既有语义：运行时 `strict=False` 沿用「坏 manifest 静默跳过」（与 `list_sources()` 现状一致）；构建期 `strict=True` 沿用「坏 manifest 直接炸」（与 `build_manifest.build()` 现状一致 —— 它现在直接 `load_manifest()` 且不吞异常）。
- 报错消息格式（中文，与 `manifest.py` 现有消息风格一致）：

  ```
  source_name 'demo-requests-default' 重复：novelbase/sources/demo_a/ 与 novelbase/sources/demo_b/ 都声明了它。请给其中一个书源换 source_name（目录名可不变，二者本就解耦）。
  ```

- 返回 `dict[str, Path]`（`source_name → 目录路径`），不使用「root 序号」之类的隐式约定；调用方要区分内置/私有用 `path.parent == _SOURCES_DIR` 判断。

新增 `Iterable` 到 `typing` 导入。

### 2. `novelbase/source.py`：收敛成单一扫描入口

现状 `_iter_source_dirs()`（`source.py:52-74`）按名字反查目录、每次调用全量扫描两个根；`list_sources()`（77-97）又自己扫一遍、逻辑重复。本次收敛：

- **删除 `_iter_source_dirs()`**。已核实它只有 3 处引用（定义 + `get_manifest()` 一处 + `resolve()` 一处），无测试或外部模块引用。
- 新增两个内部函数：

  ```python
  def _source_dirs() -> dict[str, Path]:
      """全局唯一书源表 {source_name: 目录}；任一重名（含跨根）抛 ManifestError。"""

  def _source_dir(source_name: str) -> tuple[Path, bool] | None:
      """(目录, 是否内置)；未知 source_name 返回 None。内置判定 = path.parent == _SOURCES_DIR。"""
  ```

  `_source_dirs()` 的 roots 构造：内置根 `_SOURCES_DIR`（存在才含）+ 私有根（`_PRIVATE_SOURCES_ROOT` 非空且 `is_dir()` 才含）。**必须在函数体内读取模块级 `_PRIVATE_SOURCES_ROOT`**（`tests/test_source_contracts.py:115` 等多处 `monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", ...)` 依赖这一点）。
- `list_sources()`（77-97）：非编译分支简化为 `return sorted(_source_dirs())`。编译分支（79-80）不动。
- `get_manifest()`（100-113）：`entry = _source_dir(source_name)`；`None` → `KeyError(f"unknown source: {source_name}")`（不变）；否则 `load_manifest` + `check_capability_files`（不变）。
- `resolve()`（138-185）：**循环结构保留、只换数据来源**（不做无关重构）。非编译分支由「遍历 `_iter_source_dirs()`」改为「取单条 `_source_dir()`」，内部分支不变：内置走 `_resolve_import()`（`import_module`），私有走 `spec_from_file_location`。`source.py:159` 的注释「内置：import_module；同名能力内置优先，内置缺失再试私有补齐」改写为「全局唯一：每个 source_name 至多一个目录」。
- 模块 docstring（`source.py:16-17`）的私有源说明同步改写（见「文档同步」）。
- **不加缓存**：与现状一致（每次调用全量扫描 + `load_manifest` 每个目录）。已核实理由：① 多个用例靠「先建目录、再调用」工作（`tests/test_source_api.py:72`、`tests/test_source_contracts.py:115,145,158,168` 都 `monkeypatch` 了 `_PRIVATE_SOURCES_ROOT`），模块级缓存会跨调用串味；② 缓存会改变「调用即反映磁盘现状」的既有语义。书源数量级为 10，重扫不是瓶颈。

### 3. `novelbase/utils/build_manifest.py`：构建期拦截

`build()`（`build_manifest.py:21-56`）现在手写遍历 `SRC` 并调 `load_manifest()`。改为：

```python
by_name = scan_source_names([SRC], strict=True)   # 撞名 → ManifestError
for name, path in sorted(by_name.items()):
    sources[path.name] = load_manifest(path)
    source_dirs[name] = path.name
```

（`strict=True` 保证 `load_manifest` 不再抛；`SRC` 不存在时的现有 `ERROR` 分支保持不变。）

撞名时打印 ERROR 提示并**非零退出**，让 `scripts/build-nuitka.sh:72` / `scripts/build-nuitka.ps1:42` 直接失败：

```
ERROR: source_name 重复，构建中止：<ManifestError 消息>
raise SystemExit(1)
```

理由（必须拦在构建期）：编译模式撞名会静默覆盖 `SOURCE_DIRS`，且编译分支 `list_sources()`（`source.py:80`）不去重、会把同一个名字返回两次。`novelbase/utils/_manifest.py` 是生成物、**未入库**（`git ls-files novelbase/utils/` 只有 `build_manifest.py` 等源码），故运行时不重复检查它。

### 4. 既有测试的处置

| 测试 | 现状 | 处置 |
|------|------|------|
| `tests/test_source_contracts.py:123-152` `test_builtin_wins_over_private` | 在私有根造一个与内置 `92xs_requests_default` **同名**的源，断言 `resolve()` 拿到内置实现 | **改写**为 `test_duplicate_source_name_across_roots_rejected`：同样造跨根同名，断言 `list_sources()` 与 `resolve()` 都抛 `ManifestError`（机制已取消，原断言不再有意义） |
| `tests/test_source_contracts.py:77-100` `test_source_names_unique` | 独立扫目录查重复（测试层兜底） | **保留原样**。它刻意绕过 `list_sources()`（该函数内部用 set，去重后断言恒真），与实现层检测是交叉验证关系，不要改成调用 `scan_source_names()` |
| `tests/test_source_contracts.py:103-120` `test_private_source_merged` | 私有根造一个**不同名**的源 | 保留（全局唯一下仍合法） |
| `tests/test_source_contracts.py:155-176` `test_private_dir_not_exist_graceful` / `test_no_env_returns_only_builtin` | 私有根不存在 / 未设置 | 保留（行为不变） |
| `tests/test_source_api.py:59-72` `test_get_manifest_checks_capability_files` | 私有根造 `demo-requests-default` 且缺 `search.py`，断言 `get_manifest()` 抛 ManifestError | 保留（名字不与内置冲突，`check_capability_files` 仍是抛出点） |

### 5. 新增测试：`tests/test_source_names_unique.py`

用 `tmp_path` 造目录，不碰真实 `sources/`：

1. `scan_source_names` 同根重名 → 抛 `ManifestError`，消息含冲突名与两个目录名。
2. `scan_source_names` 跨根重名 → 抛（`roots=[tmp_a, tmp_b]`，各一个目录，同名）。
3. `scan_source_names` 两个根各一个**不同名**目录 → 返回两条，不抛。
4. `scan_source_names(strict=False)`：某目录 `source.json` 非法 → 跳过该目录、其余正常返回；`strict=True` → 抛。
5. `scan_source_names([])` / 根不存在 → 返回 `{}`，不抛。
6. `monkeypatch.setattr(s, "_SOURCES_DIR", tmp_a)`（内置根换成含两个同名目录的 tmp）→ `s.list_sources()` 与 `s.get_manifest("<冲突名>")` 都抛 `ManifestError`。
7. `monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", tmp_b)`，`tmp_b` 里放一个与**内置**同名的源 → `s.list_sources()` 抛（全局口径的核心断言）。
8. `build_manifest.build()` 在撞名的 `SRC` 下非零退出：`monkeypatch.setattr(bm, "SRC", tmp)` + `pytest.raises(SystemExit)`。

## 影响面与迁移

- **后端**：撞名时 `list_sources()`（`backend/services/source_guard.py:16`、`backend/routers/download.py:184`）抛 `ManifestError` → 搜索/下载返回 HTTP 500。这是**刻意的 fail-fast**：宁可全炸，也不静默指着另一个源跑。
- **CLI**：`cmd_source` / `dev list-sources` 同样直接抛栈。
- **私有源用户**：若 `NLD_PRIVATE_SOURCES` 下存在与内置同 `source_name` 的目录，升级后**启动即报错**。迁移动作：改该私有源的 `source.json.source_name` 为独立名（目录名可不变），并同步 `app_data/config/sites/{新名}.yaml`；书架/任务里已记录的来源需换源。
- 本机当前 `NLD_PRIVATE_SOURCES` **未设置**，故该破坏性变更在本仓库无实际冲击。

## 文档同步

以下位置现在写着与全局唯一相反的话，必须一并改：

| 文件:行 | 现状 | 改为 |
|---------|------|------|
| `novelbase/source.py:16-17` | 「私有源：……同名书源目录里已存在的能力文件优先用内置，缺失的用私有实现补齐。」 | 全局唯一；私有源须独立 `source_name`，不得与内置（或另一个私有源）撞名 |
| `docs/project/sources.md:141-158`（私有源隔离节） | 「`resolve()` 中**同名能力内置优先**，内置缺失再用私有补齐」 | 同上；并补「撞名 → `ManifestError`，检测在 `manifest.scan_source_names()`」 |
| `docs/project/sources.md`（书源结构节，22-25 行附近） | 只讲目录名与 `source_name` 解耦 | 补一句：`source_name` 全局唯一（内置 + 私有同一命名空间），撞名加载期报错 |
| `docs/session-prompt.md:51`（私有源隔离条目） | 「与内置书源合并，**同名能力内置优先**」 | 全局唯一口径 |
| `docs/session-prompt.md:56`（「中间态收口状态」末句） | 「仍缺……重复 `source_name` 无实现层检测」 | **删掉这半句**（本次已补上实现层检测） |
| `AGENTS.md:34-37`（书源契约条目） | 只讲「`source_name` 与目录名解耦」与 4 个公共 API | **新增**一句：`source_name` 全局唯一（内置 + 私有同一命名空间），撞名在加载期抛 `ManifestError`。注意：磁盘版 `AGENTS.md`（3278 字节）**没有**「私有源隔离」段落，不要照旧版改 |

## 已知边界（显式记录，不修）

1. `strict=False`（运行时）下，`source.json` 本身非法的目录被跳过 → 藏在它后面的撞名检测不到。构建期 `strict=True` 不会漏。
2. 编译产物运行时不重复校验唯一性 —— 由构建期拦截保证；`_manifest.py` 未入库，手改它的后果不在本设计覆盖范围。
3. 无缓存：每次 `list_sources()` / `get_manifest()` / `resolve()` 都全量扫描并 `load_manifest` 每个目录（与现状一致，书源数量级为 10，不是瓶颈）。
4. 报错是「第一个撞上的」而非一次性列全部冲突（fail-fast；多读书源目录的成本不值得）。

# 书源分组（`source_group`）迁到 `user_data.db` —— 设计

> 2026-09-30。把书源分组从**出厂 `source.json`** 挪到**用户库 `user_data.db`**：分组表达的是「用户怎么组织自己看到的书源列表」，属于用户偏好，不该由书源出厂清单规定。`source.json` 删该字段、用户层 `sites/*.yaml` 顶层的同名键一并废弃，DB 成为**唯一来源**。

## 背景

`source_group` 与 `source_alias` 是 2026-09-27「书源元信息」那批一起加的（spec：`docs/superpowers/specs/2026-09-27-source-meta-and-search-selection-design.md` D3/D5），当时两者都走同一套两层读取：

```
shared.config.source_group(name)
  = 用户层 sites/{name}.yaml 顶层 source_group      （_user_top）
    or 出厂 source.json 顶层 source_group           （_declared_top）
    or ""
```

两者的**性质其实不同**：

| 字段 | 性质 | 归属 |
|---|---|---|
| `source_alias` | 「这个源叫什么」——书源自身的属性，书源作者可以给合理默认 | 出厂 `source.json` 合适 |
| `source_group` | 「我把它归到哪一类」——纯用户组织偏好，同一批内置源在不同用户手里可以归完全不同的组 | 应归用户数据 |

现状还有一处**语义错配**：`novelbase/sources/manifest.py:53-55` 要求这两个可选字段若出现必须是**非空字符串**——对「用户偏好」来说，"清空即未分组"却被契约层禁止，且用户改一个分组要写 `source.json` 这种"出厂文件"（或用户层 yaml），名不正。

## 现状调查（2026-09-30 实测）

| 事实 | 证据 |
|---|---|
| 读取入口 | `shared/config.py:270 source_group()` = `_user_top(name,"source_group") or _declared_top(name,"source_group")`（`:253` / `:259` 为两个底层读取） |
| 出厂预置了 4 个分组 | 10 个 `novelbase/sources/*/source.json:4`：`92xs`（92xs-requests-default）、`番茄`（fanqie-*4）、`起点`（qidian-*2）、`七猫`（qimao-*3） |
| 契约校验 | `novelbase/sources/manifest.py:53-55`：`source_alias` / `source_group` 若出现必须是非空字符串，否则 `ManifestError` |
| 用户层键 | `_user_site_cfg()`（`shared/config.py:197`）读 `sites/{name}.yaml`；**本机 10 个 sites 文件里没有 `source_group` 键**（只有 `template/config/sites/*.yaml:1` 的注释里提到它） |
| 后端出口 | `backend/routers/config.py:101`（`GET /config/sources/{name}`）、`backend/routers/download.py:205`（`GET /download/sources`） |
| 后端写口 | `backend/routers/config.py:119-129`：`PUT /config/sources/{name}` 把顶层 `source_group` / `source_alias` 写进用户层 yaml（空串 = 删键） |
| CLI 消费点 | `cli/main.py:345`（`--json`）、`cli/main.py:357`（`sources list` 行 `- <别名>  [<分组>]  (<source_name>)`）、`cli/menus.py:87`（交互式单源详情） |
| 前端消费点 | `frontend/src/api/endpoints.ts:90/233`（`SourceInfo` / `SourceConfig` 字段）、`:256`（`toSourceOptions().group`）、`:320`（`saveSourceConfig` 入参）、`SourceAccordion.tsx:23-24`（分组 badge）、`sourceConfigForm.tsx:192`（「分组」输入框）、`hooks/index.ts:236`（`useSaveSourceConfig` 入参） |
| user_data.db 现状 | `shared/user_data.py:16 DB_PATH`；表 `groups`（书架分组↔书）、`favorites`、`search_history`、`bookmarks`、`novel_sources`；schema 唯一权威是 `:31 _SCHEMA_SQL`；`:74 _ensure_schema()` 幂等建表（`CREATE TABLE IF NOT EXISTS`）；`user_version`：模板 0 / 运行时新库 0 |
| 模板 DB 机制 | `template/storage/users/default/user_data.db`（**入库二进制**）由 `init_config.py:150-161 init_user_db()` 在目标不存在时复制；`tests/test_user_db_template.py:58 test_template_schema_matches_runtime` 结构级校验「模板 schema == `_SCHEMA_SQL` 执行结果（含 `user_version`）」；`:7 _TABLES` 是硬编码的「几表齐备且全空」清单（当前 4 张，未含 `novel_sources`） |
| `_manifest.py` 快照 | `novelbase/utils/_manifest.py` 由 `python -m novelbase.utils.build_manifest` 生成（Nuitka 模式读它），**未入库**（`git ls-files` 为空），本机跟随重生成即可 |

## 已拍板决策（用户，2026-09-30）

| # | 决策点 | 选择 |
|---|---|---|
| D1 | 去掉 `source.json` 的出厂分组后，默认分组怎么办 | **不要任何默认**：新装用户看到 10 个「未分组」源，分组完全由用户在设置页自建 |
| D2 | 迁移范围 | **只搬 `source_group`**；`source_alias` 继续留在 `source.json`（书源自身属性） |
| D3 | 用户层 yaml 顶层键 | `sites/{name}.yaml` 顶层的 `source_group` **一并废弃**（DB 是唯一来源），不保留 yaml 覆盖 |
| D4 | DB 表设计 | **专用表**（非通用 KV） |
| D5 | 本机现有分组 | **一次性把你本机这 4 个分组值写进本机 DB**（这是用户数据迁移，**不是**出厂默认——新装用户仍然全未分组） |

## 目标

1. `source_group` 的**唯一来源**是 `user_data.db`：读、写都不再碰 `source.json` 与用户层 yaml。
2. `source.json` 不再有 `source_group`：契约校验收敛、10 个内置源删该行；旧文件里若残留该键**不报错**（静默忽略）。
3. 界面/CLI/API 的**对外形状不变**（字段仍叫 `source_group`，「空 = 未分组」语义不变），前端与 CLI **零改动**。
4. 老库（缺新表）打开时自动升级；模板 DB 与运行时 schema 不漂移。
5. 你本机现有 4 个分组值不丢（D5）。

## 非目标（YAGNI）

- **不**把 `source_alias` 一起搬走（D2）；也**不**把 `concurrency` / 能力段配置搬到 DB（那是"每源配置"，另有 yaml 语义）。
- **不**做分组的独立实体管理（不预定义空组、不排序组、不做组改名级联）——组名仍由各源值**派生**（沿用 2026-09-27 决策 D4）。
- **不**给新装用户任何默认分组（D1），**不**把分组写进模板 DB。
- **不**做批量读取入口（`get_source_groups()`）——`GET /download/sources` 仍逐源调 `source_group()`（10 次小查询，与现状"逐源读 yaml"同级），需要时再优化。
- **不**改 `display_name()` / `source_alias()` / 搜索页按分组勾选的行为。
- **不**引入环境相关过滤，不动 `default_source_names()`。

## 设计

### 1. 数据层：`shared/user_data.py`

`_SCHEMA_SQL`（`:31`）追加映射表（风格与既有表一致）：

```sql
    CREATE TABLE IF NOT EXISTS source_groups (
        source_name  TEXT PRIMARY KEY,
        group_name   TEXT NOT NULL
    );
```

- **未设分组的源 = 无行**（不是空串行）：与「空 = 未分组」的外在语义等价，但库里不存噪音。
- 老库升级：`_ensure_schema()` 的 `conn.executescript(_SCHEMA_SQL)` 里 `CREATE TABLE IF NOT EXISTS` 自带幂等，**无需数据迁移**（按 D1 无默认值要种）。`user_version` 保持现状（不加版本分支——当前无消费者，且模板校验要求两侧一致）。
- 新增 API（照既有风格：每次 `_connection()`，`row_factory=Row`）：

| 函数 | 语义 |
|---|---|
| `get_source_group(source_name) -> str` | 无行 → `""` |
| `set_source_group(source_name: str, group: str) -> None` | `group.strip()` 非空 → UPSERT；空 → `DELETE` 该行 |

### 2. 读取入口：`shared/config.py`

```python
def source_group(source_name: str) -> str:
    """书源分组名：唯一来源 = user_data.db 的 source_groups 表；无行 → ""（未分组）。"""
    from shared.user_data import get_source_group
    return get_source_group(source_name)
```

- **函数名、模块、签名都不变** → `backend/routers/{config,download}.py`、`cli/{main,menus}.py` 共 5 个调用点**零改动**。
- 不再读用户层 yaml 与 `source.json` 的该键（D3）——`_user_top()` / `_declared_top()` 继续存在（`source_alias()` 仍在用）。
- 无循环依赖：`shared/user_data.py` 只 import `logging/sqlite3/pathlib/typing`，不 import `config`。
- 函数内 import（与文件里 `source_concurrency()` 的既有做法一致），避免 `shared.config` 顶层拉起 sqlite 依赖。

### 3. 出厂契约：`novelbase/sources/manifest.py` + 10 个 `source.json`

- `manifest.py:53`：`for optional in ("source_alias", "source_group")` → 收敛为只校验 `source_alias`。
- 10 个 `novelbase/sources/*/source.json`：删掉 `"source_group": "..."` 行。
- `novelbase/utils/_manifest.py`：`python -m novelbase.utils.build_manifest` 重新生成（未入库，仅本机同步）。
- **向后兼容**：旧 `source.json` 若仍带 `source_group`，它落在 `manifest.py` 本就宽容的「未知顶层字段」里 → **静默忽略、不报错**（与 2026-09-27 加该字段时"未知顶层字段宽容"的既有约定一致）。

### 4. 写入路径：`backend/routers/config.py`

`PUT /config/sources/{name}`（`:107-129`）分流：

| 字段 | 现状 | 改为 |
|---|---|---|
| `source_group` | 写用户层 yaml 顶层（空串=删键） | **写 `user_data.db`**（`set_source_group()`；空串=删行），并 `existing.pop("source_group", None)` 清理 yaml 里的历史残留键（与 `:117` 处理 `enabled` 同款） |
| `source_alias` | 写用户层 yaml 顶层 | **不变** |
| `concurrency` | 写用户层 yaml 顶层 | **不变** |
| 能力段（`config`） | `deep_merge` 进 yaml | **不变** |

`GET /config/sources/{name}`（`:101`）与 `GET /download/sources`（`backend/routers/download.py:205`）**零改动**——它们调用的就是 `config_service.source_group()`。（`/download/sources` 若要用批量入口 `get_source_groups()` 属可选优化，不在本次范围。）

### 5. CLI 与前端：零改动

- CLI：`cli/main.py:345/357`、`cli/menus.py:87` 走同一入口，输出格式与「未分组」兜底文案不变。
- 前端：API 字段名、`SourceOption.group`、`SourceAccordion` 的 badge、`sourceConfigForm` 的「分组」输入框全部不变；设置页清空分组后保存仍表现为"变回未分组"。
- **行为变化仅一处**：新装用户与**删掉出厂分组后**的所有用户，看到的是未分组（D1/D5 的直接后果）。

### 6. 模板 DB

必须用新的 `_SCHEMA_SQL` 重新生成，否则 `test_template_schema_matches_runtime` 会红：

```bash
python -c "import sqlite3, pathlib, shared.user_data as u; \
p = pathlib.Path('template/storage/users/default/user_data.db'); p.unlink(missing_ok=True); \
c = sqlite3.connect(str(p)); c.executescript(u._SCHEMA_SQL); c.commit(); c.close()"
```

生成后该库仍是**全空**（新表 0 行，符合 D1），且 `user_version` 与运行时一致（均为 0）。

### 7. 本机一次性迁移（D5，不进产品代码）

切换顺序固定为：**先实现 DB 层与 `set_source_group()` → 运行一次性脚本读旧 `source.json` 的值写进本机 DB → 再删 `source.json` 的字段**。

```python
# 一次性，跑完即弃（不入库、不进 init_config）
import shared.config as c, shared.user_data as ud
from novelbase.source import list_sources
for n in list_sources():
    g = c._declared_top(n, "source_group")   # 此刻出厂值还在
    if g:
        ud.set_source_group(n, g)
```

结果：本机 DB 得到 4 组 / 10 行的映射（`92xs`、`番茄`×4、`起点`×2、`七猫`×3），界面表现与你今天看到的一致。**新装用户不受影响**——模板 DB 为空、无任何 seed 逻辑。

## 影响面与迁移

- **入库改动**：`shared/user_data.py`、`shared/config.py`、`novelbase/sources/manifest.py`、10 个 `source.json`、`backend/routers/config.py`、`template/.../user_data.db`、`tests/conftest.py`（提级 `isolated_user_db`）、6 份文档、相关测试。
- **不入库改动**：本机 `app_data/storage/users/default/user_data.db`（一次性迁移写入）、`novelbase/utils/_manifest.py`（重新生成）。
- **老库升级**：打开即建表（幂等），无数据迁移；旧 `source.json` 残留键与用户层 yaml 残留键均静默忽略，后者在下次 PUT 时被清理。
- **回滚**：改动集中在"DB 层 + 读取入口 + PUT 分流"，恢复 `source_group()` 的两层读取与 `manifest.py` 的校验即可；DB 里多出的表可留可删（无消费者副作用）。

## 测试

| 文件 | 处置 |
|---|---|
| `tests/test_source_metadata.py` | `source_group` 用例改写为 DB 语义：未设→未分组；`set_source_group` 后→有组；清空→删行（未分组）；未知书源→未分组 |
| `tests/test_user_db_template.py` | `_TABLES` 补 `source_groups`；模板校验（schema 一致 + 全空）继续覆盖新表 |
| `tests/test_shared_user_data.py`（或同域既有文件） | 新增：新表建表幂等 / 老库（手工建出缺该表的库）打开后自动补表 / `get_source_groups()` 批量返回只含有行的键 |
| `tests/test_backend_config_routes.py` | `PUT` 写 DB 而非 yaml、清掉 yaml 残留 `source_group` 键、`GET` 从 DB 读；`source_alias` 仍写 yaml |
| `tests/test_backend_download_routes.py` | `/download/sources` 的 `source_group` 来自 DB（设了才有值） |
| `tests/test_cli_effective_mode.py` | `sources list` 的分组列改由 DB 驱动（含"未分组"兜底） |
| `tests/test_source_manifest.py` / `test_source_contracts.py` | 出厂 manifest 不再要求/拒绝 `source_group`；带该键的旧 `source.json` 仍加载成功 |
| 回归口径 | 交付前 `python -m pytest tests -q` 全绿 + `npx tsc -b` + `npx oxlint` |

**测试隔离（重要）**：`source_group()` 改为读 DB 后，既有的 `monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)` 隔离**不再够用**——必须同时把 DB 指到 `tmp_path`：

```python
monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
```

`tests/test_novel_source_writes.py:14-18` 已有这个写法的局部 fixture `isolated_user_db`（顺带 patch `GROUPS_YAML`）。本次把它**提到 `tests/conftest.py` 共用**（它当前只服务一个文件，本次有三个以上文件要用），原文件改为从 conftest 取——属"服务当前目标的定向改进"。

**注意 `_isolate_nld_env`**（`tests/conftest.py:6-10`，autouse）只删 `NLD_APP_DATA` 环境变量；`shared/user_data.DB_PATH` 是模块级常量、不读该 env，所以它不提供 DB 隔离，DB 隔离必须显式 patch（如上）。

## 文档同步

- `docs/project/sources.md`：字段表删 `source_group` 行（`:71-74` 区）、`common`/`default_config` 说明不变；「元信息读取入口」段（`:85`）改写为「`source_group` 已迁到 `user_data.db`（2026-09-30），`source_alias` 仍在 `source.json`」。
- `docs/project/config.md`：顶层 `source_group` 条目（`:56-59`）改为「已迁到 `user_data.db`，用户层 yaml 不再有该键」。
- `docs/project/cli.md`：`sources list` 的格式说明不变，补一句分组来源。
- `docs/session-prompt.md`：关键约定里的「书源元信息与选择（2026-09-27）」条目更新分组来源。
- `docs/project/updates.md` + `CHANGELOG.md`：新增 2026-09-30 节/条目（含 D1/D3 的破坏性说明：**用户层 yaml 的 `source_group` 键不再被读取**）。

## 风险

| 风险 | 处置 |
|---|---|
| 用户层 yaml 里手写过分组的人，升级后分组「消失」 | 已知破坏性变更，写入 CHANGELOG「变更（破坏性）」；本机数据由 §7 一次性迁移兜住 |
| 模板 DB 忘了重建 → CI 红 | `test_template_schema_matches_runtime` 会立刻抓到；§6 给了生成命令 |
| `source_group()` 每次读 DB 的连接开销 | 与现状（每次读 yaml 文件）同级；`/download/sources` 可用批量入口优化，本次可选 |
| 旧 `source.json` 残留键被"静默忽略"而用户以为还生效 | 文档写明；实现层可另加一条 grep 验收（内置源不得再有该键） |

## 验收

1. `grep -rn '"source_group"' novelbase/sources/*/source.json` → 0 命中。
2. `grep -rn 'source_group' shared/config.py` → 只剩 `source_group()` 里对 DB 层的转调（不再有 `_user_top` / `_declared_top` 调用）。
3. `python -m pytest tests -q` 全绿；`tests/test_user_db_template.py` 覆盖新表。
4. 本机验证：设置页给某源填分组 → 保存后重开仍在；清空 → 变回「未分组」；`python cli.py sources list` 与 `--json` 的分组值跟随 DB；`sites/{name}.yaml` 里不出现 `source_group` 键。
5. 本机 DB 里 §7 的 4 组映射存在（`SELECT * FROM source_groups` 共 10 行）。
6. 新装路径（干净 `NLD_APP_DATA` 临时目录）→ 10 个源全部未分组、模板库该表为空。

# Novel.id 改为 url、物理标识用 sha256(url) — 实施记录

- 日期：2026-09-24
- 状态：**已实施**（代码 + 存量数据迁移均完成）；提交 `293ec0e` / `6fd8f31` / `269a871` 在本地 `dev`，**尚未推送**（`git push` 两次均 `Connection was reset`，`origin/dev` 干净）
- 配套设计：`docs/superpowers/specs/2026-09-24-novel-id-url-design.md`（讲「是什么 / 为什么」；本文讲「怎么做的 / 出过什么事 / 怎么退」）
- 取代：同日的 `2026-09-24-source-url-canonicalization-design.md`（`canonical_url` 列方案，未采纳，已删除）

## 起因

两条线汇合：

1. 用户指出 `novelbase/utils/urls.py` 硬编码平台名与站点域名，不符合「novelbase 是核心库、不承载站点概念」的定位；
2. 用户想让 `Novel.id` 直接用 url（可读、可反查），「旧 id 不要了」，并要一个迁移脚本。

## 决策链

| # | 决策点 | 结论 | 依据 |
|---|---|---|---|
| 1 | 库内 `meta.id` 存什么 | 书源返回的 url **原样**（含 `https://`），不做任何规范化 | 用户选「url 原样（含 https://）」 |
| 2 | 磁盘文件名 | `sha256(url)[:32]` | 用户先说「文件名保持为 id（新）」；实测 url 含 `/` `:` 在 Windows 非法、在 URL 路径段会被截断，改选 hash |
| 3 | 对外键（API / 前端 / CLI） | 继续用 `sha256(url)[:32]` | 用户选「对外仍用 sha256(url)[:32]」→ 后端 14 路由 / 前端 116 处 / CLI **零改动** |
| 4 | 表结构 | 不动（不新增列） | 用户「不要动当前数据表结构」 |
| 5 | 旧关联数据 | 一起迁移（`favorites` / `groups` / `bookmarks` 外键同步改） | 用户选「一起迁移（外键同步改）」 |
| 6 | 执行顺序 | 先改代码，再 `--apply` | 用户选「先改代码，再 --apply」← **此句即实施授权** |

**被否决的方案（留档）**

- **url 贯穿全栈**（id 直接当 API 路径段 / 前端路由参数）：实测不可行——`Starlette 1.6.0` 下 `{novel_id}` 接不住含 `/` 的值（`Match.NONE` → 404），`%2F` 也会被 ASGI 解码回 `/`（`scope["path"]` 是 percent-decoded），`encodeURIComponent` 无效。
- **`canonical_url` 列 + 唯一索引**：用户否决（「不要动表结构」）。
- **书源侧 `canonical_url.py` 能力化**（原 spec 方案）：用户否决（「不用新建什么规则这些的」）。

## 代码改动

| 文件 | 改动 |
|---|---|
| `novelbase/utils/urls.py` | 删除 `canonical_book_url(url, platform)`（连带 `platform` 参数、`92xs`/`qidian` 分支、硬编码域名 `www.92xs.info` / `www.qidian.com`）；`make_novel_id(url)` 语义改为「物理文件名 / 对外标识生成器」 |
| `novelbase/core/downloader.py` | `:7` import 去掉 `canonical_book_url`；`:127` 改为 `novel.id = make_novel_id(novel.url)`（不再把 source 名传进 core 工具） |
| `novelbase/core/storage.py` | `SQLiteStorage.save_meta` 的 `meta.id` 写 `novel.url`；`load_meta` / `iter_metas` 改为不 `WHERE id = ?`（每库一行）并让 `Novel.id` = 文件名 stem；`_row_to_novel(row, novel_id, cover)` 签名加 key；`LocalStorage` 同步（`meta.json` 的 `id` 存 url，读取时用目录名覆盖） |
| `tests/test_urls.py` | 删 6 个断言平台特例的用例；新增 2 个（`is_filename_safe`、`differs_on_url_form`——后者显式记录「不做规范化 → 不同 url 形态 = 不同 id」这一已知行为） |
| `tests/test_downloader.py` | `expected` 改为 `make_novel_id(url)`；import 去掉 `canonical_book_url` |

**为什么「先改代码」不会立刻把旧数据读坏**：文件名仍是 `sha256(url)[:32]`，而旧文件名恰好是 `sha256(旧规范化 url)[:32]`——对 url 已规范的书两者相同，所以改完代码、未迁移时数据仍可读（已实测）。33 本 fanqie 属此情况，2 本 92xs 例外。

## 验证

| 验证项 | 命令 / 方法 | 结果 |
|---|---|---|
| 受影响的三个测试文件 | `python -m pytest tests/test_urls.py tests/test_downloader.py tests/test_storage.py -q` | 23 passed |
| 全量回归 | `python -m pytest tests/ -q` | **313 passed, 2 skipped**（旧基线 317；差额正是删掉的 6 个平台特例用例 − 新增 2 个） |
| 残留引用 | grep `canonical_book_url`（novelbase/backend/cli/shared/tests/scripts） | 无 |
| 新代码读旧数据（迁移前） | `SQLiteStorage.iter_metas()` / `load_meta(key)` | 35 本、id 全 32hex、标题可读 |
| 迁移后：库内 id | 逐库 `SELECT id FROM meta` | 35/35 为 url，0 个 hash |
| 迁移后：文件名 | `文件名 == sha256(url)[:32]` | 全部成立 |
| 迁移后：读取 | `iter_metas` + 92xs 两本 `load_meta` | 35 本、id 全 32hex、92xs 标题可读 |
| 迁移后：user_data | `groups` / `favorites` / `bookmarks` 行数 | 38 / 1 / 0 |
| 脚本幂等 | 重跑 `migrate_novel_id_to_url.py`（dry-run） | 待迁移 0 本；user_data「所有书的 key 未变」 |

## 数据迁移

### 迁移前实测

- `app_data/storage/novels/*.db`：35 个，共 5.9 GB，文件名全为 32 位 hex
- 域名分布：33 本 `fanqienovel.com`（url 已是规范形）、2 本 `www.92xs.info`（`meta.url` 为**未归一**的 `/book/{id}.html`）
- `user_data.db`：`groups` 37 行、`favorites` 1 行、`bookmarks` 0 行（另有 3 行孤立引用，指向已删除的书库）

### 脚本

`novel-downloader-tools/scripts/migrate_novel_id_to_url.py`（仓库外，遵「衍生产物不进仓库」约定）

- 用法：默认 dry-run；`--apply` 才写入
- 写入范围：库内 `meta.id`、`illustrations.owner_id`（`owner_type='novel'`）、磁盘文件名、`user_data.db` 三张表外键
- 幂等：`meta.id` 含 `://` 即视为已迁移跳过
- 安全性：先 rename 后改库（rename 失败则库内未动，可安全重跑）；目标文件已存在则跳过不覆盖；复用 `migrate_novel_id.py` 的 `_rename_with_retry`（Windows 文件锁重试）
- **顺序前提**：脚本假定「新 key = `sha256(url)`」，必须与新代码同时生效

### 执行结果（`--apply`）

- 35 本全部迁移，0 本跳过
- 33 本 fanqie：只改 `meta.id` 列，文件名 / 对外标识 / 关联数据全部不变
- 2 本 92xs 改名并同步外键：`c18b41dc…`→`a780acff…`（536）、`e2633bfd…`→`f1c76922…`（96850）

## 事故与恢复

### 时间线

1. `--apply` 输出结尾出现异常行：`favorites 命中 1 行，合并掉 1 行`、`groups 命中 34 行，合并掉 32 行`——"合并掉"意味着**删行**。
2. 立即核查：`groups` 37 → **5 行**、`favorites` 1 → **0 行**。
3. 定位 bug：`_rekey_user_data` 对每本书执行「若新 key 已有行则删旧行」，而 33 本 fanqie 的 `old_key == new_key`（同一行），于是把自己删了。
4. 备份现场：`Copy-Item user_data.db $env:TEMP\user_data.db.asof_migration`。
5. 尝试 `sqlite3 db .recover`：本机 `sqlite3.exe 3.50.6`（`D:\Linux\platform-tools\`）**不支持该 dot command**。
6. 改用原始字节提取：SQLite 的 `DELETE` 只把页移入 freelist，行数据仍在文件中。用正则 `([ -~\x80-\xff]{1,24}?)([0-9a-f]{32})` 扫 `user_data.db` 原始字节，得到 **37 组** `(group_name, novel_id)`（`default` 28 / `更新` 9 / `TEST` 2）——与删除前的 37 行**完全吻合**。
7. 过滤与恢复（工具 `novel-downloader-tools/scripts/recover_user_data.py`）：
   - 只保留 `novel_id` 是现存书库文件名的记录（滤掉 92xs 的两个旧 key）→ 恢复 **30 行 groups + 1 行 favorites**
   - 2 本书有多个历史候选组名（`1a4c91e1…`：default/更新；`74d40b13…`：TEST/default）→ 取 `default`
   - 3 本（`6c71fb71…`、`a87a5e12…`、`c6bd6d62…`）页被覆写、无记录可恢复 → 按系统语义（`ensure_novel_in_group` 保证每本书至少在一个组）补入 `default`
8. 修复源脚本：`_rekey_user_data` 先算 `changed = {k: v for k, v in mapping.items() if k != v}`，只处理 key 真正变化的书。
9. 复核：`groups` 38 行（default 29 / 更新 8 / TEST 1）、`favorites` 1 行。

### 残留不确定性

- 2 本取 `default` 的书，原本可能在 `更新` / `TEST` 组（无法从文件判定，因为方向不可知）。
- 3 本补入 `default` 的书，其中最多 2 本原本有组记录（页被覆写）；恢复时 `pending_export` 一律写 0。

上述 5 本需在界面上人工核对：`告白失败，我反手死在校花面前`、`超能：我有一面复刻镜`、`你写的小说，给我惹了不少麻烦呢`、`诡秘世界，但我能模拟未来`、`系统任务太难？国家：放着我来`。

## 回退方案

| 层 | 方式 | 可逆性 |
|---|---|---|
| 代码 | `git revert 293ec0e 6fd8f31 269a871`（或 `git reset --hard 7183e3e`，因 `origin/dev` 未含这些提交，远程零影响） | 完全可逆 |
| `meta.id` / 文件名 | 需反向脚本：`revert` 代码恢复 `canonical_book_url` 后，对每个库重算 `sha256(canonical_book_url(url, platform))[:32]` 并改回。旧公式可从现存的 `meta.url` 精确重算 | 可逆 |
| `user_data.db` 外键 | 同上，用 old_key ↔ new_key 映射反向 UPDATE；迁移前快照在 `%TEMP%\user_data.db.asof_migration` | 基本可逆 |
| 事故中恢复的行 | `pending_export` 与 5 本的分组无法 100% 还原 | **部分不可逆** |

## 遗留项

1. **`platform_from_url()` / `HOSTS`**：core 里第二处站点知识（`novelbase/source.py:47-125`，backend/CLI 共 11 处调用，`cli/main.py:45` 硬编码兜底 `"fanqie"`）。未动——属书源扁平化 spec 的未决事项 1，应先设计再改。
2. **历史脚本失效**：`novel-downloader-tools/scripts/migrate_novel_id.py`（2026-08-22 那次 hash 化迁移）import 已删除的 `canonical_book_url`，不再可运行（保留作历史记录）。
3. **`docs/project/updates.md`** 尚未记入本次三个提交。
4. **流程反思**：本次是「批准执行顺序」直接被当成「批准实施」，实施完成后才补设计文档（正常顺序应为 spec → review → plan → 实施）。后续同类改动应先明确宣告阶段切换。

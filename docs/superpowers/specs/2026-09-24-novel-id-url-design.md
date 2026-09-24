# Novel.id = url、物理标识 = sha256(url) — 设计

- 日期：2026-09-24
- 状态：**已实施**（代码改动 + 存量迁移 + 事故恢复均已完成）
- 范围：`novelbase/utils/urls.py`、`novelbase/core/downloader.py`、`novelbase/core/storage.py`、`tests/`、`novel-downloader-tools/scripts/`（仓库外）
- 取代：`2026-09-24-source-url-canonicalization-design.md`（同日提出的 `canonical_url` 列方案，未采纳）

## 背景

`novelbase` 的定位是核心库（不该承载站点/应用概念），但 `canonical_book_url(url, platform)` 把三样站点知识塞进了 core：

| 位置 | 内容 |
|---|---|
| `utils/urls.py` 函数签名 | 接收 `platform` 参数 |
| `utils/urls.py` 分支 | 硬编码平台名 `92xs` / `qidian` |
| `utils/urls.py` 分支体 | 硬编码站点域名 `http://www.92xs.info/html/{id}/`、`https://www.qidian.com/book/{id}` |
| `core/downloader.py:127` | core 把 **source 名**传进 core 的 urls 工具 |

这两个特例实际只是在替「没做 url 归一」的书源补漏——fanqie 的 4 个 variant 早就自己产出 `https://fanqienovel.com/page/{id}`，qimao 用页面 `link[rel=canonical]`；只有 92xs（`novel_info.py:52` 原样透传）和 qidian（`_common.py:100` 原样透传）依赖 core 兜底。

## 决策

1. **库内 `meta.id` = 书源返回的 url 原样**（含 `https://`），可按 url 查书，**不做任何规范化/归一**。
2. **`Novel.id`（模型字段 / 磁盘文件名 / API / 前端 / CLI 用的标识）= `sha256(url)[:32]`**。
   - url 含 `/` `:`：不能直接作文件名（Windows 非法）；也不能作 URL 路径段——实测 Starlette 1.6.0 下 `{novel_id}` 接不住含 `/` 的值，而 `%2F` 也会被 ASGI 解码回 `/`（`scope["path"]` 是 percent-decoded），所以 `encodeURIComponent` 同样救不了。
   - 保持 hash 作对外标识 → 后端 14 个以 `novel_id` 为路径段的路由、前端 116 处 `novelId`、CLI 全部零改动。
3. **删除 `canonical_book_url()`**：平台参数、平台分支、硬编码域名一并消失，core 不再承载站点知识。
4. **不做 url 规范化**：同一本书的不同 url 形态会得到不同 id（如 92xs 的 `/book/{id}.html` 与 `/html/{id}/`）。归一责任归书源——书源返回什么 url，就入什么 url。

## 代码改动

| 文件 | 改动 |
|---|---|
| `novelbase/utils/urls.py` | 删 `canonical_book_url`；`make_novel_id(url)` 保留，语义改为「物理文件名 / 对外标识生成器」 |
| `novelbase/core/downloader.py:127` | `novel.id = make_novel_id(novel.url)`——不再把 source 名传进 core 工具 |
| `novelbase/core/storage.py` | `save_meta` 的 `meta.id` 写 `novel.url`；`load_meta` / `iter_metas` 让 `Novel.id` = 文件名 key（不再 `WHERE id = ?`，因为每库只有一行 meta）；`LocalStorage` 同步（`meta.json` 的 `id` 存 url，读取时用目录名覆盖） |
| `tests/test_urls.py` | 删 6 个断言平台特例的用例，新增 2 个（文件名安全、不同 url 形态得到不同 id） |
| `tests/test_downloader.py` | `expected` 改为 `make_novel_id(url)` |

验证：`python -m pytest tests/ -q` → **313 passed, 2 skipped**（旧基线 317，差的 4 个正是删掉的平台特例用例）。

## 存量迁移

脚本：`novel-downloader-tools/scripts/migrate_novel_id_to_url.py`（dry-run 默认，`--apply` 才写入；幂等：`meta.id` 含 `://` 即跳过）。

写入范围：库内 `meta.id`、`illustrations.owner_id`（novel 行）、磁盘文件名、`user_data.db` 的 `favorites`/`groups`/`bookmarks` 外键。

实测（35 本，5.9 GB）：

| 分组 | 数量 | 动作 |
|---|---|---|
| fanqie（`meta.url` 已是规范形） | 33 | 只改 `meta.id` 列；文件名（`sha256(url)[:32]` 恰好等于原名）、对外标识、关联数据全部不变 |
| 92xs（`meta.url` 为未归一的 `/book/{id}.html`） | 2 | 文件名改名（`c18b41dc…`→`a780acff…`、`e2633bfd…`→`f1c76922…`）+ `illustrations.owner_id` + user_data 外键同步 |

**执行顺序：先改代码，再 `--apply`。** 新代码按「文件名 = `sha256(url)`」定位，而旧文件名恰好就是 `sha256(旧规范化 url)`——对 url 已规范的书两者相同，所以改完代码、未迁移时数据仍能读（已实测），切换窗口为零。

## 已知取舍

- **不做规范化**：同一本书的多种 url 形态 = 两个 id。入库与后续使用必须保持同一形态（92xs 现有 2 本存的是 `/book/{id}.html` 形态）。
- **`platform_from_url()` / `HOSTS` 未动**：core 里还有第二处站点知识（host→platform 表，`novelbase/source.py:47-125`，backend/CLI 共 11 处调用，`cli/main.py:45` 硬编码兜底 `"fanqie"`）。本次不在范围内。
- **历史脚本失效**：`novel-downloader-tools/scripts/migrate_novel_id.py`（2026-08-22 那次 hash 化迁移）import 已删除的 `canonical_book_url`，不再可运行（仅作历史记录保留）。

## 中途事故与恢复（如实记录）

迁移脚本初版在 `_rekey_user_data` 里把 `old_key == new_key`（33 本 fanqie 属此情况）误判为「新 key 已存在」，于是删掉了 `groups` 32 行 + `favorites` 1 行。

恢复过程：

1. SQLite 的 `DELETE` 只把页移入 freelist，行数据仍在文件中 → 从 `user_data.db` 原始字节提取 `(group_name, novel_id)` 对，与现存行比对
2. 提取到 37 组（`default` 28 / `更新` 9 / `TEST` 2），与删除前的 37 行完全吻合；按「`novel_id` 必须是现存书库文件名」过滤掉 92xs 的两个旧 key，恢复 30 行
3. 2 本书有多个候选组名（历史移动痕迹）取 `default`；3 本页已被覆写无记录可恢复，按系统语义（`ensure_novel_in_group` 保证每本书至少在一个组）补入 `default`
4. 结果：`groups` 38 行、`favorites` 1 行（工具：`novel-downloader-tools/scripts/recover_user_data.py`）

脚本已修：`_rekey_user_data` 只处理 key 真正变化的书（`changed = {k: v for k, v in mapping.items() if k != v}`）。

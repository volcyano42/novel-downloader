# 换源弹窗按钮常驻 + CLI `config init`（含 CLI 规范微修）—— 设计

> 2026-09-27。两件独立的小改动合为一篇：**A** 详情页换源弹窗的取消/确定按钮常驻；**B** CLI 新增 `config init` 子命令，并顺手修 5 条低风险规范问题。

## A. 换源弹窗按钮常驻

### 现状与根因

`frontend/src/features/detail/SourcePickerDialog.tsx:36` 的容器同时承担「限高」与「滚动」两件事：

```
w-[400px] max-h-[80vh] overflow-y-auto rounded-2xl … p-6
```

标题、书源列表、取消/确定按钮**同处一个滚动区** → 书源多时（本站 10 个内置源 + 私有源）必须滚到底才能点到按钮。

### 改法（单文件，不动任何交互逻辑）

| 区域 | 改动 |
|---|---|
| 外层容器 | 去掉 `overflow-y-auto`，改为 `flex max-h-[80vh] flex-col`（保留 `max-h-[80vh]`、圆角、内边距、动画类） |
| 标题区（`<h2>` + 书名 `<p>`） | 加 `shrink-0` |
| 列表区（当前 `space-y-2 mb-4`） | 加 `flex-1 min-h-0 overflow-y-auto pr-1` —— **只有它滚动**（`pr-1` 让滚动条不压住条目） |
| 按钮区（当前 `flex gap-2`） | 加 `shrink-0` |

选中态、`当前` 标记、`submitting` 文案、空态提示、`onClick` 行为**一律不变**。

### 验收

`cd frontend && npx tsc -b` 0 错、`npm run lint` 0 告警；手工：书源列表很长时按钮始终可见、只有列表滚动。

## B. CLI `config init` + 规范微修

### B1 新子命令

`init_config.py` 已具备全部能力（`init_main_config` / `init_site_config(name)` / `init_export_config(fmt)` / `init_user_db` / `init_all_config`），但 CLI 未暴露 —— 现在只能 `python -c` 或删配置目录。本期把它接出来：

```
python cli.py config init [--all] [--main] [--sites NAME] [--formats FMT] [--user-db]
```

| 用法 | 行为 | 对应函数 |
|---|---|---|
| `config init`（无参） | 等价 `--all` | `init_all_config()` |
| `config init --all` | 补全所有缺失配置 | `init_all_config()` |
| `config init --main` | 只补 `config.yaml` | `init_main_config()` |
| `config init --sites NAME` | 只补 `sites/{NAME}.yaml`；`NAME=all` 表示全部 | `init_site_config(NAME)` |
| `config init --formats FMT` | 只补 `formats/{FMT}.yaml`；`FMT=all` 表示全部 | `init_export_config(FMT)` |
| `config init --user-db` | 只补 `user_data.db` | `init_user_db()` |

- **只补缺失、不覆盖已有**（沿用 `init_config.py` 现有语义；不新增 `--force`）。
- `--main` / `--sites` / `--formats` / `--user-db` **互斥**：同时给多个 → `stderr` 提示 + 退出码 2。
- 输出：有新建时 `已初始化 N 个配置项：` + 逐行 `  - <路径>`；无缺失时 `配置已完整，无需初始化。`
- 一期**只做 `init`**；`config check`（对应已有的 `check_config()`）留作后续。

### B2 顺带修的 5 条低风险规范问题

1. `cli.py` docstring：「novel-crawler 非交互 CLI 入口」→「novel-downloader …」（项目名混用：`cli.py` 写 novel-crawler、`cli/main.py` 写 novelbase）
2. `cli/main.py` 的 `delete --id` help 示例过时：`fanqie_7123456789012345678` → 现为 `sha256(url)[:32]`
3. `cli/main.py` 的 `dev list-sources --json` help 文案错误：「仅列出 JSON 规则源」→「以 JSON 输出」
4. `cli/main.py` 的 `dev` 子命令补 `required=True`（与 `novel`/`sources` 一致；现在 `python cli.py dev` 静默无输出）
5. `cli/main.py` 的用法 docstring 补齐漏掉的命令（`delete` / `novel list` / `sources list` / `dev` / `config init`）

### B3 明确不做（留作后续任务）

`--version`；统一各命令输出排版（标题/缩进/分隔）；`dp2`/`sp` 等复用变量改名；`prog` 名统一；`config check`。

### 验收

- `python cli.py config init --help`（参数与 help 正常）
- `python cli.py config init`（本机配置齐全 → 输出「配置已完整，无需初始化。」）
- `python cli.py config init --main --user-db`（互斥 → stderr 提示 + 退出码 2）
- `python cli.py dev`（缺子命令 → argparse 报错，退出码 2）
- `python cli.py sources list` 回归（输出格式不变）
- 定向 pytest 用例保持通过（本机 `tmp_path` 用例约 60s/例，全量待 CI）

## 非目标

- 不改 `init_config.py` 的既有语义（只补缺失、路径解析、模板复制）。
- 不改换源弹窗的交互、数据结构与调用方（`DetailPage.tsx` 不受影响）。
- 不引入任何环境/可用性相关概念（沿用 v4.5.1 后的单一环境假设）。

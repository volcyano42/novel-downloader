# CLI dev new-variant — 新建书源变体设计

- 日期：2026-08-26
- 状态：已批准（方案 A）
- 范围：`cli/main.py` + `docs/project/cli.md` + `tests/test_cli_dev_new_variant.py`

## 背景

书源变体（variant）架构：`novelbase/sources/{name}/{mode}/{variant}/` 代码 +
`app_data/config/sites/{name}.yaml` 中 `{mode}: {variant}: {...}` 配置
（如 fanqie 的 `api/oiapi`、`api/rain`、`requests/default`）。
`novelbase/source.py` 的 `capabilities()`/`resolve()` 按 `{mode: {variant: [functions]}}` 分发，
mode 必须用 variant 子目录组织。

现有 `dev new-source` 生成无 variant 层级的脚手架（`sources/{name}/{mode}/` 直接放函数），
与现行 variant 架构不兼容。`dev new-variant` 补齐缺口：为已有书源的某 mode 新建 variant。

## 目标

`python cli.py dev new-variant --source <书源名> --mode <mode> --variant <新变体名>`

一次完成两件事（缺一不可，引擎才能工作）：

1. 代码脚手架：`novelbase/sources/{source}/{mode}/{variant}/` 下生成
   `__init__.py` + `search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`
2. 站点配置：`app_data/config/sites/{source}.yaml` 的 `{mode}:` 下新增 `{variant}:` 配置块

## CLI 语法

```
python cli.py dev new-variant --source <name> --mode <mode> --variant <name>
```

- `--source`：书源名，必填
- `--mode`：模式（api / browser / requests），必填
- `--variant`：新变体名，必填

三个参数缺一即 argparse 报错退出。

## 校验链（按序，任一失败即报错退出，不产生任何文件）

1. 书源代码目录 `novelbase/sources/{source}/` 不存在 → 报错并提示
   `书源 {source} 不存在，请先运行 dev new-source --name {source}`
2. 站点配置 `app_data/config/sites/{source}.yaml` 不存在 → 同上提示
3. `--mode` 不在站点配置顶层 keys（api/browser/requests）→ 报错并列出可用 mode
4. variant 已存在（代码目录 `{source}/{mode}/{variant}/` 存在 **或** 配置 `{mode}:` 已有该 key）
   → 报错 `variant '{variant}' 已存在（代码或配置）`，绝不覆盖
5. 该 mode 下没有已有 variant 可作模板（`{mode}:` 为空 dict 或缺失）→ 报错
   `mode '{mode}' 下没有可复制的 variant，请先手动添加一个`

## 代码脚手架

目录：`novelbase/sources/{source}/{mode}/{variant}/`（`mkdir(parents=True, exist_ok=True)`）

文件内容与 `_scaffold_source` 的模板一致（`cli/main.py` 现有实现）：

- `__init__.py`：空文件（`touch`）
- `search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`：
  `"""TODO: implement {fn} for {source}/{variant}."""` +
  `from novelbase.core.exceptions import FeatureNotSupportedError` +
  `async def {fn}(*args, **kwargs): raise FeatureNotSupportedError("TODO")`
  （**必须 `async def`**：`novelbase/core/downloader.py` 以 `await fn(...)` 调用书源函数，
  同步函数会在调用时直接报错；现有 10 个书源函数均为 `async def`）

不生成 source 根的 `_common.py`（书源已存在，跳过）。

## 配置写入

- 读取 `app_data/config/sites/{source}.yaml`（复用 `cli.config.load_site_config`）
- 取 `site_cfg[mode]` 中第一个 dict 值（按插入顺序）作为模板，整体复制
- `site_cfg[mode][variant] = 复制内容`，用 `cli.config.save_site_config` 写回
- 不修改模板 variant 本身

## 输出

成功时打印：

```
书源变体已创建: novelbase/sources/{source}/{mode}/{variant}/
  search.py, novel_info.py, chapter_list.py, chapter_content.py
站点配置已更新: app_data/config/sites/{source}.yaml → {mode}.{variant}
```

## 错误处理

全部走校验链提前退出（`print(..., file=sys.stderr)` + `sys.exit(1)`），
与 `cmd_dev` 现有风格一致；argparse 缺参由其自带报错（exit 2）。

## 实现位置（方案 A）

`cli/main.py`：

- `_parse_args()` 的 dev 分支新增：
  ```python
  nv = dv_sub.add_parser("new-variant", help="为书源新建变体脚手架")
  nv.add_argument("--source", required=True, help="书源名称")
  nv.add_argument("--mode", required=True, help="模式 (api/browser/requests)")
  nv.add_argument("--variant", required=True, help="新变体名称")
  ```
- `cmd_dev` 新增分支 `elif args.dev_command == "new-variant":` 调用 `_scaffold_variant(...)`
- 新增函数 `_scaffold_variant(source: str, mode: str, variant: str)`，
  与 `_scaffold_source` 并列；文件模板字符串提取为模块级常量或局部复用，
  避免与 `_scaffold_source` 重复（最小做法：局部常量 `_TMPL = """..."""`，两函数共用）。
- **顺带修正**：`_scaffold_source` 的同步 `def` 模板改为 `async def`
  （`cli/main.py` 现有实现第 399 行附近），与 `_scaffold_variant` 共用同一 `async` 模板常量。

## 测试

`tests/test_cli_dev_new_variant.py`，直接调用 `cli.main._scaffold_variant`，
用 `tmp_path` 构造书源目录与站点配置，`monkeypatch` 重定向 `cli.main` 中
sources 根与 sites 配置路径（将 `_scaffold_variant` 的路径解析改为
`cli.config` 可注入或模块常量可 monkeypatch 的形式）。

用例：

1. `test_new_variant_success`：代码目录 + 配置块均生成，模板配置被复制
2. `test_new_variant_source_missing`：书源不存在 → `SystemExit(1)`
3. `test_new_variant_mode_missing`：mode 不在配置 → `SystemExit(1)`，列出可用 mode
4. `test_new_variant_variant_exists`：代码或配置已存在 → `SystemExit(1)`，不覆盖
5. `test_new_variant_no_template`：mode 下无 variant → `SystemExit(1)`
6. `test_new_source_template_async`：`_scaffold_source` 生成的函数文件为
   `async def`（顺带修正回归保护）

## 文档同步

`docs/project/cli.md` 命令表：

- `| dev | 开发工具（new-source / list-sources） |` →
  `| dev | 开发工具（new-source / new-variant / list-sources） |`
- 在 new-source 行附近补一行 `dev new-variant` 用法说明。

## 范围外

- 不改 `novelbase/source.py` / `shared/config.py` 的分发逻辑
- 不重构 `_scaffold_source` 的目录结构（仅将同步模板改为 `async def`，已纳入本次范围）
- 不做交互式入口（`cli/interactive.py` 无 dev 命令，不涉及）

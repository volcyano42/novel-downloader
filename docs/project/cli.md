# CLI 命令

## 非交互入口（`python cli.py`）

| 命令 | 用途 |
|------|------|
| `search "关键词" [--source <source_name>] [--page N]` | 搜索（省略 `--source` = 并发全部启用书源） |
| `download --source <source_name> --url <URL> [--group g] [--workers n]` | 下载小说（全量，非交互） |
| `update [--group g] [--workers n]` | 更新全部已下载小说 |
| `export --group default --format epub` | 导出组内小说（直接导出，无交互菜单） |
| `delete --id <novel_id>` | 删除小说（含章节/封面，移出分组） |
| `novel list [--group g]` | 列出已下载小说（书架） |
| `sources list [--json]` | 列出可用书源 |
| `info --source <source_name> --url <URL>` | 查看小说信息 |
| `dev new-source --name <source_name> [--modes requests,browser,api] [--no-config]` | 创建新书源脚手架 |
| `dev list-sources` | 列出全部可用书源 |

### 书源与模式

- `--source/-s`：书源名 `source_name`（如 `fanqie-requests-default`）。
- **mode 由书源自己在 `source.json` 里声明，用户不再选**——旧的 `--platform/-p`、
  `--mode/-m`、`--variant` 参数与「模式与 variant」选择规则**已全部删除**。
- `search` 省略 `--source` 时**并发全部启用书源**（`shared.config.enabled_source_names()`）；
  单个源失败静默跳过，并在结果里标注来源 `source_name`。
- `download` / `info` 的 `--source` 必填：core 已删 URL→书源推断，无法自动识别 URL 归属。
- `dev new-source` 生成**一层结构**（`__init__.py` + `source.json` + 4 能力文件），默认同时写
  `app_data/config/sites/{source_name}.yaml`（`--no-config` 跳过）；`dev new-variant` 已删除。

示例：

```bash
python cli.py search "斗破苍穹"                            # 并发全部启用书源
python cli.py search "斗破苍穹" --source fanqie-requests-default
python cli.py download --source fanqie-browser-default --url "https://..."
python cli.py info --source 92xs-requests-default --url "https://..."
```

## 交互式入口（`python main.py`）

主菜单搜索/下载的选书源行为：

- **搜索**：输入关键词 → 并发全部启用书源，结果标注来源后由用户选择；输入 URL →
  由用户从全部书源中**手选书源**（core 无 URL→书源推断）。
- **下载**：由用户**手选书源**。
- 交互式入口**不再有 mode/variant 选择菜单**（旧的「按当前 mode 解析 variant」逻辑已删除）。

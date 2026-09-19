# CLI 命令

## 非交互入口（python cli.py）

| 命令 | 用途 |
|------|------|
| `search "关键词" --platform fanqie` | 搜索 |
| `download --url <URL>` | 下载小说（全量，非交互） |
| `update` | 更新全部已下载小说 |
| `export --group default --format epub` | 导出组内小说（直接导出，无交互菜单） |
| `delete --id <novel_id>` | 删除小说（含章节/封面，移出分组） |
| `novel list [--group g]` | 列出已下载小说（书架） |
| `sources list [--json]` | 列出可用书源 |
| `info --url <URL>` | 查看小说信息 |
| `dev` | 开发工具（new-source / list-sources） |

### 模式与 variant

`search` / `download` / `update` / `info` 支持：

- `--platform/-p`：平台（fanqie/qidian/qimao/92xs；`download`/`info` 可从 URL 自动推断）
- `--mode/-m`：requests / browser / api（默认 requests）
- `--variant`：指定 variant 名（见下方选择规则）

variant 选择规则（对所有模式一致）：

- 某模式只有一个 variant 时自动使用；browser/requests 未指定时默认 `default`
- 某模式多于一个 variant 时（如 fanqie 的 api 有 `oiapi`/`rain`）：
  - 显式指定 `--variant`：使用指定项，不存在则报错并列出可用项
  - 未指定 `--variant`：提示需显式指定，列出所有 variant 名称后以退出码 2 退出

示例：

```bash
python cli.py search "斗破苍穹" --platform fanqie --mode api --variant rain
python cli.py download --url "https://..." --mode browser
```

## 交互式入口（python main.py）

主菜单执行搜索/下载/更新时按当前 mode 解析 variant：

- 只有一个 variant：直接使用（browser/requests 默认 `default`）
- 多于一个 variant：弹出选择菜单询问用户，选择结果在本次会话内记住（同一平台不再重复询问），取消则回退第一个 variant 并提示

# CLI 命令（python cli.py）

| 命令 | 用途 |
|------|------|
| `search "关键词" --platform fanqie` | 搜索 |
| `download --url <URL>` | 下载小说（全量，非交互） |
| `update` | 更新全部已下载小说 |
| `export --group default --format epub` | 导出组内小说（直接导出，无交互菜单） |
| `delete --id <novel_id>` | 删除小说（含章节/封面，移出分组） |
| `novel list [--group g]` | 列出已下载小说（书架） |
| `source list [--json]`（source/sources 均可） | 列出可用书源 |
| `info --url <URL>` | 查看小说信息 |
| `dev` | 开发工具（new-source / list-sources） |

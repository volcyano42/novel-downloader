"""novel-crawler 非交互 CLI 入口 — 委托到 cli.main。

用法:
    python cli.py search --platform fanqie "关键词"
    python cli.py download --mode requests --url "https://..."
    python cli.py update --platform fanqie --group default
    python cli.py export --group default --format epub
    python cli.py delete --id <novel_id>
    python cli.py novel list [--group <g>]
    python cli.py sources list [--json]
    python cli.py info --url "https://fanqienovel.com/page/7123456789012345678"
    python cli.py dev new-source --name <name> / dev list-sources

子命令定义与实现见 cli/main.py，命令一览见 docs/project/cli.md。
"""

from cli.main import main

if __name__ == "__main__":
    main()

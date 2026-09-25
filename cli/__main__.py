"""允许 `python -m cli ...` 运行非交互 CLI（等价于 `python cli.py ...`）。

子命令定义与实现见 cli/main.py，命令一览见 docs/project/cli.md。
"""

from cli.main import main

if __name__ == "__main__":
    main()

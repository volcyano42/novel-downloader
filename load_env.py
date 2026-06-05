"""
load_env.py — 从 .env 文件加载环境变量

用法:
    import load_env          # 自动加载项目根目录的 .env
    import load_env as _     # 只需要副作用

    # 或指定路径:
    load_env.load(".env.production")

加载后通过 os.getenv("OIAPI_API_KEY") 读取变量。
"""
import os
import re
from pathlib import Path


def load(path: str | Path | None = None) -> None:
    """加载 .env 文件中的 KEY=VALUE 到 os.environ。

    Args:
        path: .env 文件路径。为 None 时自动查找调用者目录及上级目录。
    """
    if path is None:
        path = _find_dotenv()
    else:
        path = Path(path)

    if not path or not path.exists():
        return

    content = path.read_text(encoding="utf-8")

    for line in content.splitlines():
        line = line.strip()
        # 跳过空行和注释
        if not line or line.startswith("#"):
            continue

        # 只匹配 KEY=VALUE 或 KEY="VALUE" 格式
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if not m:
            continue

        key, value = m.group(1), m.group(2).strip()
        # 去除可选的引号
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        # 只在变量未设置时写入（不覆盖已存在的环境变量）
        if key not in os.environ:
            os.environ[key] = value


def _find_dotenv() -> Path | None:
    """从当前目录向上查找第一个 .env 文件。"""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


# ── 作为模块导入时自动加载 ──
load()
print("press any key to exit")
os.popen("pause")
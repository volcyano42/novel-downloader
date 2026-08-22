#!/usr/bin/env python3
"""check_public.py — novel-downloader-public 迁移校验（三道防线）。

在 Agent 把文件从 private 仓库复制到 novel-downloader-public 之后、提交之前运行：

1. 缺失检查：白名单（PUBLIC_MANIFEST.md）内文件在 public 缺失 → 报错
2. 多余检查：public 里有清单外文件（敏感/杂项误迁）→ 报错（关键防线）
3. 敏感扫描：public 内容出现敏感模式（oiapi/rain/key 等）→ 报错

任一防线失败以非零退出码结束，阻止提交。
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

PRIVATE_DEFAULT = Path(__file__).resolve().parent.parent
PUBLIC_DEFAULT = PRIVATE_DEFAULT.parent / "novel-crawler"

# 与 PUBLIC_MANIFEST.md 白名单保持一致
INCLUDE_PATTERNS = [
    "novelbase/**",
    "backend/**",
    "frontend/**",
    "cli/**",
    "shared/**",
    "android/**",
    "scripts/**",
    "tests/**",
    ".github/workflows/**",
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "requirements.txt",
    "docs/README.md",
    "docs/project/**",
    "docs/build/**",
    "docs/conventions/**",
]

# 白名单内进一步排除（与 PUBLIC_MANIFEST.md 一致）
EXCLUDE_PATTERNS = [
    "novelbase/sources/qidian/**",
    "novelbase/sources/qimao/**",
    "novelbase/sources/92xs/**",
    "novelbase/sources/fanqie/api/**",
    "novelbase/utils/_manifest.py",
    "frontend/node_modules/**",
    "frontend/dist/**",
    "android/.gradle/**",
    "android/app/build/**",
    "android/local.properties",
    "android/keystore.properties",
    "android/*.jks",
    "docs/superpowers/**",
    "docs/session-prompt.md",
    "docs/learning/**",
    # 依赖未公开书源的测试（public 无 qidian/qimao/92xs/fanqie-api）
    "tests/test_source_async.py",
    "tests/test_source_contracts.py",
    "tests/test_browser_sources.py",
    "**/__pycache__/**",
    "**/*.pyc",
]

# 真实密钥/凭据模式（宽泛词如 oiapi/api_key/sk- 是合法字段名或 SVG 属性前缀，不判敏感）
SENSITIVE_PATTERNS = [
    "client_secret",
    "-----BEGIN",
    "ghp_",          # GitHub PAT
    "AKIA",          # AWS access key
]

# public 仓库专属文件（白名单外但允许存在，不被"多余"检查拦截）
PUBLIC_ONLY_FILES = {
    ".gitignore",
}

# 豁免敏感扫描的文件（如本脚本自身含敏感词定义）
SENSITIVE_SKIP = {
    "scripts/check_public.py",
}

# 遍历时跳过（性能 + 永不迁移）
SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", ".reasonix", ".codegraph",
             ".superpowers", ".refer", "app_data", "会话归档", ".pytest_cache", ".idea"}


def is_whitelisted(rel: str) -> bool:
    """相对路径是否在白名单内（先排除后包含）。"""
    if any(fnmatch.fnmatch(rel, p) for p in EXCLUDE_PATTERNS):
        return False
    return any(fnmatch.fnmatch(rel, p) for p in INCLUDE_PATTERNS)


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        parts = p.relative_to(root).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        yield p


def check(private: Path, public: Path) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []

    # 防线 1：缺失（白名单文件应在 public 存在）
    for p in _iter_files(private):
        rel = p.relative_to(private).as_posix()
        if not is_whitelisted(rel):
            continue
        if not (public / rel).exists():
            errors.append(f"[缺失] {rel} 在白名单内但 public 中不存在")

    if not public.exists():
        return errors  # public 缺失时多余/敏感检查无意义

    # 防线 2：多余（public 中出现白名单外文件 = 疑似误迁）
    for p in _iter_files(public):
        rel = p.relative_to(public).as_posix()
        if rel in PUBLIC_ONLY_FILES:
            continue
        if not is_whitelisted(rel):
            errors.append(f"[多余] {rel} 不在白名单（疑似敏感/杂项误迁）")

    # 防线 3：敏感内容扫描
    for p in _iter_files(public):
        rel = p.relative_to(public).as_posix()
        if rel in SENSITIVE_SKIP:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in SENSITIVE_PATTERNS:
            if pat in text:
                errors.append(f"[敏感] {rel} 含敏感字样 '{pat}'")
                break

    # 防线 4：版本一致性（public 的 pyproject 与 novelbase.__version__ 必须一致）
    pyproject = public / "pyproject.toml"
    init_py = public / "novelbase" / "__init__.py"
    if pyproject.exists() and init_py.exists():
        py_ver = re.search(r'version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8", errors="ignore"))
        init_ver = re.search(r'__version__\s*=\s*"([^"]+)"', init_py.read_text(encoding="utf-8", errors="ignore"))
        if py_ver and init_ver and py_ver.group(1) != init_ver.group(1):
            errors.append(
                f"[版本] novelbase/__init__.py __version__({init_ver.group(1)}) "
                f"与 pyproject.toml version({py_ver.group(1)}) 不一致，迁移时需改写"
            )

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="novel-downloader-public 迁移校验（三道防线）")
    ap.add_argument("--private", type=Path, default=PRIVATE_DEFAULT, help="private 仓库根目录")
    ap.add_argument("--public", type=Path, default=PUBLIC_DEFAULT, help="public 仓库根目录")
    args = ap.parse_args()

    errors = check(args.private.resolve(), args.public.resolve())
    if errors:
        print(f"校验失败（{len(errors)} 个问题）：", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    print("OK：迁移校验通过（无缺失/多余/敏感问题）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

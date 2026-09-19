#!/usr/bin/env python3
"""check_public.py — novel-downloader-public 迁移校验（三道防线）。

在 Agent 把文件从 private 仓库复制到 novel-downloader-public 之后、提交之前运行：

1. 缺失检查：白名单（PUBLIC_MANIFEST.md）内文件在 public 缺失 → 报错
2. 多余检查：public 里有清单外文件（敏感/杂项误迁）→ 报错（关键防线）
3. 敏感扫描：public 内容出现敏感模式（rain/key 等）→ 报错

任一防线失败以非零退出码结束，阻止提交。

非迁移文件清单（白名单内排除项）的单一数据源是 private 仓库
pyproject.toml 的 `[tool.novel-downloader.migration] exclude`（与
PUBLIC_MANIFEST.md「白名单内排除」保持一致），本脚本不再硬编码。
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
    "requirements.txt",
    "docs/README.md",
    "docs/project/**",
    "docs/build/**",
    "docs/conventions/**",
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

# 豁免敏感扫描的文件（如本脚本自身及测试敏感扫描的测试，均含敏感词定义）
SENSITIVE_SKIP = {
    "scripts/check_public.py",
    "tests/test_check_public.py",  # 测试敏感检测需构造 client_secret 等敏感词
}

# 遍历时跳过（性能 + 永不迁移）
SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", ".reasonix", ".codegraph",
             ".superpowers", ".refer", "app_data", "会话归档", ".pytest_cache", ".idea"}


def load_exclude_patterns(private_root: Path) -> list[str]:
    """从 pyproject.toml 的 `[tool.novel-downloader.migration] exclude` 读取非迁移文件清单。

    该段是排除清单的唯一数据源（与 PUBLIC_MANIFEST.md「白名单内排除」一致）。
    用正则提取字符串数组（避免运行时依赖 tomllib/tomli，Python 3.10 无内置 tomllib）。
    """
    pyproject = private_root / "pyproject.toml"
    if not pyproject.exists():
        raise SystemExit(f"缺少 {pyproject}，无法读取非迁移文件清单")
    text = pyproject.read_text(encoding="utf-8")
    m = re.search(
        r"\[tool\.novel-downloader\.migration\][^\[]*?"
        r"exclude\s*=\s*(\[[^\]]*\])",
        text,
        re.S,
    )
    if not m:
        raise SystemExit(
            "pyproject.toml 缺少 [tool.novel-downloader.migration] 的 exclude 清单，"
            "无法进行迁移校验（非迁移清单的唯一数据源）"
        )
    return re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))


def is_whitelisted(rel: str, exclude_patterns: list[str]) -> bool:
    """相对路径是否在白名单内（先排除后包含）。"""
    if any(fnmatch.fnmatch(rel, p) for p in exclude_patterns):
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
    exclude_patterns = load_exclude_patterns(private)

    # 防线 1：缺失（白名单文件应在 public 存在）
    for p in _iter_files(private):
        rel = p.relative_to(private).as_posix()
        if not is_whitelisted(rel, exclude_patterns):
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
        if not is_whitelisted(rel, exclude_patterns):
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

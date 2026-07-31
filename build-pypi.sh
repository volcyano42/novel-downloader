#!/usr/bin/env bash
# Build & upload novelbase to PyPI
# Usage: ./build-pypi.sh [--token <pypi-token>] [--skip-build] [--repository <pypi|testpypi>]
#
#   --token        PyPI API token（默认读取 $PYPI_TOKEN；推荐用环境变量，勿硬编码）
#   --skip-build   跳过构建，仅上传 dist/ 下已有产物
#   --repository   上传目标（默认 pypi，测试用 testpypi）
#
# 前置依赖：
#   pip install build twine

set -euo pipefail
cd "$(dirname "$0")"

# ── 参数解析 ────────────────────────────────────────────
TOKEN="${PYPI_TOKEN:-}"
SKIP_BUILD=false
REPOSITORY="pypi"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --token)       TOKEN="$2"; shift 2 ;;
        --skip-build)  SKIP_BUILD=true; shift ;;
        --repository)  REPOSITORY="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,11p' "$0"
            exit 0
            ;;
        *) echo "未知参数: $1（用 --help 查看用法）"; exit 1 ;;
    esac
done

# ── 并行构建锁（与 Nuitka 脚本共用，防 dist/ 冲突）──
LOCK_DIR="$(dirname "$0")/.build.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo -e "\033[31mERROR: 另一个构建正在进行（$LOCK_DIR 存在），请等待其完成\033[0m"
    exit 1
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

# ── Token 检查 ────────────────────────────────────────────
if [ -z "$TOKEN" ]; then
    echo -e "\033[31mERROR: 未提供 PyPI token\033[0m"
    echo -e "\033[33m  方式1: 设置环境变量 PYPI_TOKEN\033[0m"
    echo -e "\033[33m  方式2: 运行参数 --token <token>\033[0m"
    exit 1
fi

# ── 依赖检查 ──────────────────────────────────────────────
for mod in build twine; do
    if ! python -m pip show "$mod" >/dev/null 2>&1; then
        echo -e "\033[33m安装 $mod ...\033[0m"
        python -m pip install "$mod"
    fi
done

# ── 构建 ──────────────────────────────────────────────────
if [ "$SKIP_BUILD" != true ]; then
    echo -e "\033[36m--- python -m build --no-isolation ---\033[0m"
    python -m build --no-isolation
fi

# ── 产物检查 ──────────────────────────────────────────────
shopt -s nullglob
ARTIFACTS=(dist/*.whl dist/*.tar.gz)
if [ ${#ARTIFACTS[@]} -eq 0 ]; then
    echo -e "\033[31mERROR: dist/ 下没有 .whl / .tar.gz 产物\033[0m"
    exit 1
fi
echo -e "\033[36m待上传产物:\033[0m"
for f in "${ARTIFACTS[@]}"; do
    echo "  $(basename "$f") ($(du -h "$f" | cut -f1))"
done

# ── 上传 ──────────────────────────────────────────────────
echo -e "\033[36m--- twine upload (repository: $REPOSITORY) ---\033[0m"
python -m twine upload --repository "$REPOSITORY" \
    --username __token__ \
    --password "$TOKEN" \
    "${ARTIFACTS[@]}"

echo -e "\033[32mDone: 已上传 ${#ARTIFACTS[@]} 个产物到 $REPOSITORY\033[0m"

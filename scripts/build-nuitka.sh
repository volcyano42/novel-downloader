#!/usr/bin/env bash
# Build Nuitka onefile: novel-downloader-web-{version}-{platform}
# 合并历史 build-web.sh（Linux）+ build-termux.sh（Termux）
# Usage: ./build-nuitka.sh [-v <version>] [-r <retries>]
# Requires: Python 3.10+, npm, C 编译器（Linux: gcc/clang；Termux: clang）
set -e
cd "$(dirname "$0")/.."

VERSION=""
MAX_RETRIES=20
while [ $# -gt 0 ]; do
    case "$1" in
        -v|--version) shift; VERSION="$1" ;;
        -v=*|--version=*) VERSION="${1#*=}" ;;
        -r|--max-retries) shift; MAX_RETRIES="$1" ;;
        -r=*|--max-retries=*) MAX_RETRIES="${1#*=}" ;;
        *) echo "未知参数: $1"; echo "用法: $0 [-v <version>] [-r <retries>]"; exit 1 ;;
    esac
    shift
done

# ── 平台检测 ──
ARCH=$(uname -m)
if [ -n "$PREFIX" ] && [ -d "$PREFIX" ]; then
    PLATFORM="termux"
else
    case "$ARCH" in
        x86_64|amd64) PLATFORM="linux-x64" ;;
        aarch64|arm64) PLATFORM="linux-arm64" ;;
        *) echo "错误: 不支持的架构 $ARCH"; exit 1 ;;
    esac
fi
echo "平台: $PLATFORM | 架构: $ARCH"

# ── Python 解释器（排除 WindowsApps stub）──
PYTHON=""
for cand in python3 python; do
    p="$(command -v "$cand" 2>/dev/null || true)"
    case "$p" in
        *WindowsApps*|"") continue ;;
    esac
    PYTHON="$p"
    break
done
if [ -z "$PYTHON" ]; then
    echo "错误: 找不到可用的 python3/python"
    exit 1
fi

# ── 版本号 ──
if [ -z "$VERSION" ]; then
    VERSION=$("$PYTHON" -c "import re;print(re.search(r'version = \"([^\"]+)\"', open('pyproject.toml', encoding='utf-8').read()).group(1))")
fi
echo "=== Nuitka build v$VERSION ($(date +%H:%M:%S)) ==="

DIST_DIR="dist"
EXE_NAME="novel-downloader-web-$VERSION-$PLATFORM"
EXE_PATH="$DIST_DIR/$EXE_NAME"

# ── 0. Termux 编译依赖（幂等；Linux 假设 gcc/clang 已装）──
if [ "$PLATFORM" = "termux" ]; then
    echo "--- Termux 编译依赖 ---"
    pkg install -y clang binutils patchelf termux-elf-cleaner
    # Nuitka 依赖检测需要 ldd：优先 llvm-ldd（Termux llvm 包提供）
    if command -v llvm-ldd >/dev/null 2>&1; then
        ln -sf "$(command -v llvm-ldd)" "$PREFIX/bin/ldd" 2>/dev/null || true
        echo "ldd -> llvm-ldd"
    else
        echo "警告: 无 ldd 替代（llvm-ldd），Nuitka 依赖检测可能失败"
    fi
fi

# ── 1. 构建前端 ──
echo "--- 构建前端 ($(date +%H:%M:%S)) ---"
( cd frontend
  if [ ! -d node_modules ]; then
      npm install --registry=https://registry.npmmirror.com || npm install
  fi
  npm run build
)
echo "--- 前端完成 ($(date +%H:%M:%S)) ---"

# ── 2. 生成书源 manifest（Nuitka onefile 无法扫描文件系统）──
echo "--- 生成书源 manifest ($(date +%H:%M:%S)) ---"
"$PYTHON" -m novelbase.utils.build_manifest

# ── 3. 安装 Nuitka ──
echo "--- 安装 Nuitka ---"
"$PYTHON" -m pip install nuitka

# ── 4. Nuitka 编译（自动重试）──
NUITKA_ARGS=(
    -m nuitka
    --standalone
    --onefile
    --assume-yes-for-downloads
    --jobs="$(nproc)"
    --include-package=novelbase
    --include-package=novelbase.sources
    --include-package=backend
    --include-module=init_config
    --include-data-dir=template=template
    --include-data-dir=frontend/dist=frontend/dist
    --output-dir="$DIST_DIR"
    --output-filename="$EXE_NAME"
)

# 平台差异：Termux 无静态 libpython；browser 模式（DrissionPage→psutil）不支持 Android
if [ "$PLATFORM" = "termux" ]; then
    NUITKA_ARGS+=(--static-libpython=no)
    NUITKA_ARGS+=(--nofollow-import-to=DrissionPage)
else
    NUITKA_ARGS+=(--static-libpython=yes)
fi
NUITKA_ARGS+=(backend/main.py)

START_TIME=$(date +%s)
for attempt in $(seq 1 "$MAX_RETRIES"); do
    ATTEMPT_START=$(date +%s)
    echo "--- Nuitka 尝试 $attempt / $MAX_RETRIES ($(date +%H:%M:%S)) ---"

    # 清理上次失败残留
    rm -f "$EXE_PATH"

    "$PYTHON" "${NUITKA_ARGS[@]}"
    EXIT_CODE=$?
    ELAPSED=$(( ( $(date +%s) - ATTEMPT_START + 30 ) / 60 ))

    if [ "$EXIT_CODE" -eq 0 ] && [ -f "$EXE_PATH" ]; then
        # Termux onefile 产物需 elf-cleaner 清理（Android linker 必需）
        if [ "$PLATFORM" = "termux" ]; then
            termux-elf-cleaner "$EXE_PATH" 2>/dev/null || true
        fi
        TOTAL_ELAPSED=$(( ( $(date +%s) - START_TIME + 30 ) / 60 ))
        SIZE_MB=$(du -m "$EXE_PATH" | cut -f1)
        echo "=== 构建完成: $EXE_NAME (${SIZE_MB}MB) 耗时 ${TOTAL_ELAPSED}min ($(date +%H:%M:%S)) ==="
        exit 0
    fi

    echo "--- 尝试 $attempt 失败 (exit $EXIT_CODE, ${ELAPSED}min) ---"
    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
        WAIT_SECONDS=$((30 * 2 ** (attempt - 1)))
        if [ "$WAIT_SECONDS" -gt 480 ]; then WAIT_SECONDS=480; fi
        WAIT_MIN=$(( (WAIT_SECONDS + 30) / 60 ))
        echo "等待 ${WAIT_MIN}min 后重试... (Ctrl+C 终止)"
        sleep "$WAIT_SECONDS"
    else
        TOTAL_ELAPSED=$(( ( $(date +%s) - START_TIME + 30 ) / 60 ))
        echo "Nuitka 编译失败：已达最大重试次数 $MAX_RETRIES（总耗时 ${TOTAL_ELAPSED}min）"
        exit 1
    fi
done

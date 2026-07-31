#!/usr/bin/env bash
# Build interactive CLI (menu): novel-downloader
# Usage: ./build-main.sh
set -e
cd "$(dirname "$0")"

# ── 并行构建锁（防止多个 Nuitka 脚本同时运行互删 dist/）──
LOCK_DIR="$(dirname "$0")/.build.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo -e "\033[31mERROR: 另一个构建正在进行（$LOCK_DIR 存在），请等待其完成\033[0m"
    exit 1
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

echo -e "\033[36m--- Nuitka: interactive CLI (3-5 min) ---\033[0m"
rm -rf dist/*.build dist/*.dist
python -m nuitka --standalone --onefile --jobs=$(nproc) \
    --include-package=novelbase \
    --include-package=novelbase.sources.fanqie \
    --include-package=novelbase.sources.fanqie.browser \
    --include-package=novelbase.sources.fanqie.requests \
    --include-package=novelbase.sources.fanqie.api.oiapi \
    --include-package=novelbase.sources.fanqie.api.rain \
    --include-package=novelbase.sources.qidian \
    --include-package=novelbase.sources.qidian.browser \
    --include-package=novelbase.sources.qidian.requests \
    --include-package=novelbase.sources.qimao \
    --include-package=novelbase.sources.qimao.browser \
    --include-package=novelbase.sources.qimao.requests \
    --include-package=novelbase.sources.qimao.api.rain \
    --include-package=novelbase.sources.92xs \
    --include-package=novelbase.sources.92xs.requests \
    --include-package=app \
    --include-data-dir=app_data/config=app_data/config \
    --include-data-dir=template/config=template/config \
    --output-dir=dist \
    --output-filename=novel-downloader \
    main.py

rm -rf build
echo -e "\033[32mDone: dist/novel-downloader\033[0m"

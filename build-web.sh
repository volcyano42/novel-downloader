#!/usr/bin/env bash
# Build Web UI: novel-downloader-web (backend + frontend)
# Usage: ./build-web.sh
set -e
cd "$(dirname "$0")"

# ── 并行构建锁（防止多个 Nuitka 脚本同时运行互删 dist/）──
LOCK_DIR="$(dirname "$0")/.build.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo -e "\033[31mERROR: 另一个构建正在进行（$LOCK_DIR 存在），请等待其完成\033[0m"
    exit 1
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

echo -e "\033[36m--- Building frontend ---\033[0m"
cd services/frontend
if [ ! -d "node_modules" ]; then
    echo -e "\033[33mnpm install...\033[0m"
    npm install
fi
echo "npm run build..."
npm run build
cd ../..

echo -e "\033[36m--- Nuitka: web backend (5-10 min) ---\033[0m"
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
    --include-package=services \
    --include-data-dir=app_data/config=app_data/config \
    --include-data-dir=template/config=template/config \
    --include-data-dir=services/frontend/dist=services/frontend/dist \
    --output-dir=dist \
    --output-filename=novel-downloader-web \
    services/backend/main.py

rm -rf build
echo -e "\033[32mDone: dist/novel-downloader-web\033[0m"

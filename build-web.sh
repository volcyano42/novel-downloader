#!/usr/bin/env bash
# Build Web UI: novel-downloader-web (backend + frontend)
# Usage: ./build-web.sh
set -e
cd "$(dirname "$0")"

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

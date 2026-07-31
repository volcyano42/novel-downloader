#!/usr/bin/env bash
# Build interactive CLI (menu): novel-downloader
# Usage: ./build-main.sh
set -e
cd "$(dirname "$0")"

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
    --output-dir=dist \
    --output-filename=novel-downloader \
    main.py

rm -rf build
echo -e "\033[32mDone: dist/novel-downloader\033[0m"

#!/usr/bin/env bash
# Build Web UI for Termux (bionic libc) — 产物真机 Termux 可直接运行
# 用法: ./build-termux.sh [--skip-frontend] [--deps-only]
#   在 termux-docker 容器或真机 Termux 中运行
#   --deps-only 只安装依赖不编译（验证用）
set -e
cd "$(dirname "$0")"

SKIP_FRONTEND=false
DEPS_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --skip-frontend) SKIP_FRONTEND=true ;;
        --deps-only) DEPS_ONLY=true ;;
        *) echo "未知参数: $arg"; exit 1 ;;
    esac
done

# ── 并行构建锁（与其他构建脚本互斥，防 dist/ 互删）──
LOCK_DIR="$(dirname "$0")/.build.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo -e "\033[31mERROR: 另一个构建正在进行（$LOCK_DIR 存在），请等待其完成\033[0m"
    exit 1
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

# ── 1. Termux 系统包 ──
# 预编译 python 扩展用 pkg 装（python-pillow/python-lxml）；其余源码编译所需工具链
echo -e "\033[36m--- Termux 系统包 ---\033[0m"
pkg set-mirror https://packages-cf.termux.dev/apt/termux-main >/dev/null 2>&1 || true
pkg update -y >/dev/null 2>&1 || true
pkg install -y python clang binutils patchelf rust \
    libheif libjpeg-turbo zlib libffi openssl libyaml \
    python-pillow python-lxml termux-elf-cleaner llvm

# Nuitka 依赖检测需要 ldd：优先用 llvm-ldd（Termux llvm 包提供），否则用 readelf wrapper
if command -v llvm-ldd >/dev/null 2>&1; then
    ln -sf "$(command -v llvm-ldd)" "$PREFIX/bin/ldd"
    echo "ldd -> llvm-ldd"
elif [ -f /src/scripts/termux-ldd.sh ]; then
    ln -sf /src/scripts/termux-ldd.sh "$PREFIX/bin/ldd"
    echo "ldd -> termux-ldd.sh (readelf wrapper)"
else
    echo "警告: 无 ldd 替代，Nuitka 依赖检测可能失败"
fi
which ldd

# ── 2. pip 依赖（C 扩展在 Termux 源码编译，需 rust/clang/libheif）──
echo -e "\033[36m--- pip 依赖 ---\033[0m"
# maturin 构建 Rust 扩展（pydantic-core 等）需要 Android API level
export ANDROID_API_LEVEL=24
# Termux 排除 browser 模式依赖：drissionpage→psutil 不支持 Android（platform android is not supported）
# browser 模式在 Termux 产物中不可用（requests/api 模式完整可用）
grep -v '^drissionpage' requirements.txt > req-termux.txt
pip install --break-system-packages -r req-termux.txt nuitka

# ── 3. 前端（CI 中由 host 构建后跳过）──
if [ "$SKIP_FRONTEND" != true ]; then
    echo -e "\033[36m--- 前端构建（需 nodejs: pkg install nodejs）---\033[0m"
    cd services/frontend
    npm install >/dev/null 2>&1
    npm run build
    cd ../..
fi

# ── 4. Nuitka 编译（Termux bionic 环境，产物真机可跑）──
if [ "$DEPS_ONLY" = true ]; then
    echo -e "\033[32mDEPS ONLY: 依赖已就绪，跳过编译\033[0m"
    python -c "import fastapi, uvicorn, yarl, pydantic, PIL, lxml, pillow_heif, psutil; print('IMPORT OK')"
    exit 0
fi

echo -e "\033[36m--- Nuitka: web backend (Termux, 15-30 min) ---\033[0m"
rm -rf dist/*.build dist/*.dist
# Termux 的 Python 无静态 libpython（--static-libpython=yes 报 not supported）；动态链接在 onefile 下由 Nuitka 打包 libpython
python -m nuitka --standalone --onefile --static-libpython=no --assume-yes-for-downloads --jobs=$(nproc) \
    --nofollow-import-to=DrissionPage \
    --include-package=novelbase \
    --include-package=novelbase.sources.fanqie \
    --include-package=novelbase.sources.fanqie.requests \
    --include-package=novelbase.sources.fanqie.api.oiapi \
    --include-package=novelbase.sources.fanqie.api.rain \
    --include-package=novelbase.sources.qidian \
    --include-package=novelbase.sources.qidian.requests \
    --include-package=novelbase.sources.qimao \
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
echo -e "\033[32mDone: dist/novel-downloader-web (Termux/bionic)\033[0m"

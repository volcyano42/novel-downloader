#!/usr/bin/env bash
# Build portable package: novel-downloader-web-portable-v{version}-{platform}.tar.gz
# 参考 build-portable.ps1（Windows 用 embedded python），本脚本覆盖 Linux x64/arm64 + Termux
# 平台解释器：
#   linux-x64 / linux-arm64 : python-build-standalone（独立 Python，无需系统安装）
#   termux                  : 内置 Python pyroot/（PYTHONHOME 重定位）或 pkg python
# Usage: ./build-portable.sh --platform <linux-x64|linux-arm64|termux> [--version <v>] [--deps-dir <dir>] [--pyroot-dir <dir>]
set -e
cd "$(dirname "$0")/.."

PLATFORM=""
VERSION=""
DEPS_DIR=""
PYROOT_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --platform=*) PLATFORM="${1#*=}" ;;
        --platform) shift; PLATFORM="$1" ;;
        --version=*) VERSION="${1#*=}" ;;
        --version) shift; VERSION="$1" ;;
        --deps-dir=*) DEPS_DIR="${1#*=}" ;;
        --deps-dir) shift; DEPS_DIR="$1" ;;
        --pyroot-dir=*) PYROOT_DIR="${1#*=}" ;;
        --pyroot-dir) shift; PYROOT_DIR="$1" ;;
        *) echo "未知参数: $1"; echo "用法: $0 --platform <linux-x64|linux-arm64|termux> [--version <v>] [--deps-dir <dir>] [--pyroot-dir <dir>]"; exit 1 ;;
    esac
    shift
done

if [ -z "$PLATFORM" ]; then
    echo "错误: 缺少 --platform 参数（linux-x64 | linux-arm64 | termux）"
    exit 1
fi

# 构建机解释器（排除 WindowsApps Store stub；Git Bash 无 python3 时用 python）
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
echo "版本: $VERSION | 平台: $PLATFORM"

DIST_DIR="dist/portable"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# ── 1. 构建前端 ──
echo "--- 构建前端 ($(date +%H:%M:%S)) ---"
( cd frontend
  if [ ! -d node_modules ]; then
      npm install --registry=https://registry.npmmirror.com || npm install
  fi
  npm run build
)
echo "--- 前端完成 ($(date +%H:%M:%S)) ---"

# ── 2. Python 解释器 ──
case "$PLATFORM" in
    linux-x64)
        PY_TARGET="x86_64-unknown-linux-gnu"
        ;;
    linux-arm64)
        PY_TARGET="aarch64-unknown-linux-gnu"
        ;;
    termux)
        PY_TARGET=""   # 内置 pyroot/ 或 Termux pkg python
        ;;
    *)
        echo "错误: 不支持的平台 $PLATFORM（linux-x64 | linux-arm64 | termux）"
        exit 1
        ;;
esac

if [ -n "$PY_TARGET" ]; then
    echo "--- 下载 python-build-standalone ($PY_TARGET) ---"
    ASSET=$(PY_TARGET="$PY_TARGET" "$PYTHON" - <<'EOF'
import json, os, re, urllib.request
req = urllib.request.Request(
    "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest",
    headers={"User-Agent": "novel-downloader-build", "Accept": "application/vnd.github+json"},
)
data = json.load(urllib.request.urlopen(req, timeout=30))
tag = data["tag_name"]
pat = re.compile(r"^cpython-3\.13\.[0-9]+\+" + re.escape(tag) + r"-" + os.environ["PY_TARGET"] + r"-install_only\.tar\.gz$")
for a in data["assets"]:
    if pat.match(a["name"]):
        print(a["browser_download_url"])
        break
EOF
)
    if [ -z "$ASSET" ]; then
        echo "错误: 找不到 $PY_TARGET 的 cpython-3.13 install_only 资产"
        exit 1
    fi
    echo "下载: $ASSET"
    curl -L --fail --retry 3 --ssl-no-revoke -o dist/python-standalone.tar.gz "$ASSET"
    mkdir -p "$DIST_DIR/python"
    tar -xzf dist/python-standalone.tar.gz -C "$DIST_DIR/python" --strip-components=1
    rm -f dist/python-standalone.tar.gz
    "$DIST_DIR/python/bin/python3" --version

    # ── 3. 安装依赖（standalone python 直接用 manylinux wheel，无需编译）──
    echo "--- 安装依赖 ---"
    "$DIST_DIR/python/bin/python3" -m pip install --no-warn-script-location -r requirements.txt
fi

# ── 4. 复制项目文件 ──
echo "--- 复制项目文件 ---"
cp -r novelbase "$DIST_DIR/novelbase"
# 注意：目标目录不预建（cp -r 会嵌套复制成 backend/backend）
cp -r backend "$DIST_DIR/backend"
# 共享配置层（backend 的 routers/services 依赖 shared.config/user_data）
cp -r shared "$DIST_DIR/shared"
mkdir -p "$DIST_DIR/frontend"
cp -r frontend/dist "$DIST_DIR/frontend/dist"
# 配置模板（不含用户数据 app_data，避免泄露 API key 等敏感字段；首次运行由 init_config 初始化）
cp -r template "$DIST_DIR/template"
# 依赖清单（裸包 fallback 自举 pip install 用）
cp requirements.txt "$DIST_DIR/requirements.txt"
# 根目录模块（backend/main.py lifespan 引用），缺失则构建失败（防静默漏包）
cp init_config.py "$DIST_DIR/init_config.py"

# Termux 开箱即用：复制 CI 容器预装的 site-packages（PYTHONPATH 引用，用户不跑 pip）
if [ "$PLATFORM" = "termux" ] && [ -n "$DEPS_DIR" ] && [ -d "$DEPS_DIR" ]; then
    echo "--- 复制预装依赖 (--deps-dir) ---"
    mkdir -p "$DIST_DIR/python-deps"
    cp -r "$DEPS_DIR"/. "$DIST_DIR/python-deps/"
fi
# Termux 全内置：复制 CI 容器打包的 Python 本体（PYTHONHOME 重定位，无需 pkg install python）
if [ "$PLATFORM" = "termux" ] && [ -n "$PYROOT_DIR" ] && [ -d "$PYROOT_DIR" ]; then
    echo "--- 复制内置 Python (--pyroot-dir) ---"
    mkdir -p "$DIST_DIR/pyroot"
    cp -r "$PYROOT_DIR"/. "$DIST_DIR/pyroot/"
fi
find "$DIST_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ── 5. 生成启动脚本 ──
if [ "$PLATFORM" = "termux" ]; then
    cat > "$DIST_DIR/start.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Termux 启动脚本（开箱即用：优先用内置 Python pyroot/，否则 pkg install python + python-deps/）
cd "$(dirname "$0")"

# 优先：内置 Python（PYTHONHOME 重定位）
if [ -d "$PWD/pyroot" ]; then
    export PYTHONHOME="$PWD/pyroot"
    export LD_LIBRARY_PATH="$PWD/pyroot/lib:$LD_LIBRARY_PATH"
    export PATH="$PWD/pyroot/bin:$PATH"
    PY="$PWD/pyroot/bin/python"
    echo "使用内置 Python (pyroot/)"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    echo "[首次运行] 需要 Termux Python，正在安装..."
    pkg update -y
    pkg install -y python
    PY="python"
fi

# 使用预装依赖（CI 容器中按同版本 Python 编译的 site-packages）
if [ -d "$PWD/python-deps" ]; then
    export PYTHONPATH="$PWD/python-deps:$PYTHONPATH"
    echo "使用预装依赖 (python-deps/)"
elif ! "$PY" -c "import uvicorn" >/dev/null 2>&1; then
    # 裸包（无 pyroot 无 python-deps）：系统 python 无依赖，自举安装
    echo "[首次运行] 安装项目依赖（需联网，约 10-20 分钟）..."
    export ANDROID_API_LEVEL=24
    grep -v '^drissionpage' requirements.txt > req-termux.txt
    "$PY" -m pip install -r req-termux.txt
fi

echo "启动 novel-downloader-web (http://127.0.0.1:8000)..."
SERVER_PID=""
cleanup() { [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null; exit 0; }
trap cleanup INT TERM
"$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# 等待服务就绪后打开浏览器
for i in $(seq 1 30); do
    if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000')" >/dev/null 2>&1; then
        termux-open-url http://127.0.0.1:8000 2>/dev/null || true
        break
    fi
    sleep 1
done

wait $SERVER_PID
EOF
else
    cat > "$DIST_DIR/start.sh" <<'EOF'
#!/usr/bin/env bash
# 启动脚本（Linux）：使用打包的独立 Python
cd "$(dirname "$0")"
export PYTHONHOME="$PWD/python"
export PATH="$PWD/python/bin:$PATH"

echo "启动 novel-downloader-web (http://127.0.0.1:8000)..."
SERVER_PID=""
cleanup() { [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null; exit 0; }
trap cleanup INT TERM
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# 等待服务就绪后打开浏览器
for i in $(seq 1 30); do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000')" >/dev/null 2>&1; then
        (xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 || true) &
        break
    fi
    sleep 1
done

wait $SERVER_PID
EOF
fi
chmod +x "$DIST_DIR/start.sh"

# ── 6. 说明文档 ──
cat > "$DIST_DIR/启动说明.txt" <<EOF
=== novel-downloader-web 便携版 (v$VERSION, $PLATFORM) ===

使用方法：
  1. 解压到任意目录
  2. 运行 ./start.sh
  3. 浏览器自动打开 http://127.0.0.1:8000

数据存储位置：
  下载的小说数据保存在 app_data/storage/
  配置文件在 app_data/config/config.yaml

停止服务：Ctrl+C 或关闭终端。

说明：
  - browser 模式（DrissionPage）需要系统已安装 Chrome；Termux 版不含 browser 模式
  - Linux 版自带 Python 与依赖，开箱即用
  - Termux 版内置 Python (pyroot/) 与依赖，完全开箱即用（无需 pkg install python）
EOF

# ── 7. 打包 ──
echo "--- 打包 ($(date +%H:%M:%S)) ---"
ARCHIVE="dist/novel-downloader-web-portable-${VERSION}-${PLATFORM}.tar.gz"
tar -czf "$ARCHIVE" -C dist portable
SIZE_MB=$(du -m "$ARCHIVE" | cut -f1)
echo "完成: $ARCHIVE ($SIZE_MB MB)"

#!/usr/bin/env bash
# 验证 psutil<6 在 Termux Python 3.14 可用性
set -e
pkg set-mirror https://packages-cf.termux.dev/apt/termux-main >/dev/null 2>&1 || true
pkg update -y >/dev/null 2>&1 || true
pkg install -y python >/dev/null 2>&1 || true
echo "PYTHON: $(python --version 2>&1)"
echo "=== psutil<6 安装 ==="
pip install --break-system-packages "psutil<6" 2>&1 | tail -5
python -c "import psutil; print('PSUTIL', psutil.__version__)"

#!/usr/bin/env bash
# termux-docker 预装依赖：导出 deps/（site-packages）+ pyroot/（Python 本体+依赖库）
# 复用 build-linux-arm64-termux.yml 的预装逻辑
set -e
cd "$(dirname "$0")/.."

# Git Bash 下 $PWD 是 /d/... 形式，Docker Desktop 需要 Windows 路径
WIN_DIR="$(pwd -W 2>/dev/null || echo "$PWD")"
echo "挂载目录: $WIN_DIR"

echo "=== 清理旧副产物 ==="
rm -rf deps pyroot .req-termux.txt

echo "=== 拉取镜像 termux/termux-docker:aarch64 ==="
docker pull termux/termux-docker:aarch64 || true

for attempt in 1 2 3; do
  echo "=== 预装尝试 $attempt/3 ==="
  # MSYS_NO_PATHCONV=1：禁用 Git Bash 的路径转换，避免 -w /src 被转成 D:/Git/src
  if MSYS_NO_PATHCONV=1 docker run --rm \
    -v "$WIN_DIR":/src -w /src \
    --security-opt seccomp:unconfined \
    termux/termux-docker:aarch64 bash -c '
      set -e
      pkg set-mirror https://packages-cf.termux.dev/apt/termux-main >/dev/null 2>&1 || true
      for u in 1 2 3; do
        pkg update -y && break
        echo "pkg update 第 $u 次失败，重试..." && sleep 15
      done
      for i in 1 2 3 4 5; do
        if pkg install -y python rust clang binutils patchelf \
          libheif libjpeg-turbo zlib libffi openssl libyaml \
          python-pillow python-lxml; then
          break
        fi
        echo "pkg install 第 $i 次失败，重试..."
        sleep 20
      done
      export ANDROID_API_LEVEL=24
      # Termux 排除 browser 模式依赖（psutil 不支持 Android）；容器无 /tmp，用挂载卷
      grep -v "^playwright" /src/requirements.txt > /src/.req-termux.txt
      # 本地 qemu 容器：清华镜像返回 403，改用阿里云镜像
      pip install --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ -r /src/.req-termux.txt
      # 导出依赖 site-packages
      mkdir -p /src/deps
      cp -r "$PREFIX"/lib/python*/site-packages/. /src/deps/
      # 导出 Python 本体（bin + 标准库 + 依赖 .so，供 PYTHONHOME 重定位）
      mkdir -p /src/pyroot/bin /src/pyroot/lib
      cp "$PREFIX"/bin/python* /src/pyroot/bin/ 2>/dev/null || true
      cp -r "$PREFIX"/lib/python*/ /src/pyroot/lib/ 2>/dev/null || true
      cp "$PREFIX"/lib/libpython* /src/pyroot/lib/ 2>/dev/null || true
      cp "$PREFIX"/lib/lib*.so* /src/pyroot/lib/ 2>/dev/null || true
      chmod -R a+rwX /src/deps /src/pyroot
      echo "预装完成: deps $(ls /src/deps | wc -l) 项, pyroot $(du -sh /src/pyroot | cut -f1)"
    '; then
    echo "=== 预装成功（第 $attempt 次）==="
    exit 0
  else
    echo "=== 预装第 $attempt 次失败，重试... ==="
    sleep 15
  fi
done

echo "=== 预装 3 次均失败 ==="
exit 1

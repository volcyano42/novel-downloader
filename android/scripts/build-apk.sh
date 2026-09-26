#!/usr/bin/env bash
# 一键构建 Android APK（CI 专用；本机无 Android SDK 时不执行）
set -euo pipefail
# 脚本位于 android/scripts/build-apk.sh；cd 到 android/ 项目根
cd "$(dirname "$0")/.."

# 1. 构建前端（frontend 在仓库根下，android/ 的上一级）
(cd ../frontend && npm ci && npm run build)

# 1b. 生成 Android 依赖清单：Chaquopy 的 pip 块只有 install/options（没有 exclude API），
#     故安装「预过滤 + 版本固定」的清单：
#       - 排除 playwright（需下载浏览器内核）、psutil（C 扩展）、pillow-heif（Chaquopy 仓库无 wheel）
#       - pin 到 chaquo.com/pypi-13.1 里存在 cp311/arm64 wheel 的版本（否则 pip 取 PyPI sdist 编译失败）
#       - uvicorn[standard] 的 C/Rust extras（httptools/uvloop/watchfiles）不可用 → 用纯 uvicorn
#       - pin fastapi：0.121+ 起要求 pydantic>=2.9，与 pydantic<2 冲突（0.115-0.120 的约束仍是 pydantic<3）
#       - 追加 pydantic<2：pydantic-core 是 Rust 扩展、无 Android wheel（Chaquopy 官方建议 v1）
grep -v -E "^(playwright|psutil|pillow-heif)" ../requirements.txt \
  | sed -E 's/^uvicorn\[standard\].*/uvicorn/; s/^fastapi.*/fastapi==0.120.0/; s/^lxml$/lxml==5.3.0/; s/^Pillow$/Pillow==11.0.0/; s/^yarl$/yarl==1.9.3/; s/^PyYAML$/PyYAML==6.0.3/' \
  > .req-android.txt
echo "pydantic<2" >> .req-android.txt
echo "--- Android 依赖清单 ---"; cat .req-android.txt

# 2. 复制 Python 运行时模块进 Chaquopy 打包目录（app/src/main/python/，构建产物不提交 git）
#    server.py 运行时 import 链：backend.* / shared.* / init_config / template / 前端资源 zip
#    novelbase 通过 build.gradle.kts 的 install("file:../..") 以 pip 包安装，不在此复制
rm -rf app/src/main/python/backend app/src/main/python/shared \
       app/src/main/python/init_config.py \
       app/src/main/python/template app/src/main/python/frontend.zip
mkdir -p app/src/main/python
cp -r ../backend app/src/main/python/backend
cp -r ../shared app/src/main/python/shared
find app/src/main/python/backend app/src/main/python/shared \
     -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
cp ../init_config.py app/src/main/python/init_config.py
cp -r ../template app/src/main/python/template

# 2b. 前端产物打成单个 zip 随 APK 资产分发。
#     Chaquopy 把 src/main/python/ 打成 APK 资产，其中的数据文件不是真实目录
#     （os.listdir/os.scandir 不可用），StaticFiles 的「真实目录」假设不成立 ——
#     故改为 zip 交付，由 server.py 启动时解压到可写目录、再交给 SPA fallback 服务。
#     zip 成员路径相对 frontend/dist 根（index.html 在 zip 根，不带 dist/ 前缀），只打文件。
python3 - <<'PY'
import os, zipfile
src = os.path.join("..", "frontend", "dist")
dst = os.path.join("app", "src", "main", "python", "frontend.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _dirs, files in os.walk(src):
        for name in files:
            full = os.path.join(root, name)
            zf.write(full, os.path.relpath(full, src))
print(f"已生成前端资源 zip：{dst}")
PY

# 3. 生成 Gradle wrapper（若缺失；CI 由 setup-gradle action 提供 gradle 命令）
if [ ! -f gradle/wrapper/gradle-wrapper.jar ]; then
  gradle wrapper --gradle-version 8.7
fi

# 4. 构建 release APK
./gradlew :app:assembleRelease

# 5. 输出路径
ls -lh app/build/outputs/apk/release/

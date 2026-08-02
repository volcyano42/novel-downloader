#!/usr/bin/env bash
# 一键构建 Android APK（CI 专用；本机无 Android SDK 时不执行）
set -euo pipefail
# 脚本位于 android/scripts/build-apk.sh；cd 到 android/ 项目根
cd "$(dirname "$0")/.."

# 1. 构建前端（services/frontend 在仓库根下，android/ 的上一级）
(cd ../services/frontend && npm ci && npm run build)

# 2. 复制 Python 运行时模块进 Chaquopy 打包目录（app/src/main/python/，构建产物不提交 git）
#    server.py 运行时 import 链：services.backend.* / init_config / template / 前端静态文件
rm -rf app/src/main/python/services app/src/main/python/init_config.py \
       app/src/main/python/template app/src/main/python/frontend
mkdir -p app/src/main/python/services
cp -r ../services/__init__.py ../services/backend app/src/main/python/services/
find app/src/main/python/services -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
cp ../init_config.py app/src/main/python/init_config.py
cp -r ../template app/src/main/python/template
mkdir -p app/src/main/python/frontend
cp -r ../services/frontend/dist/* app/src/main/python/frontend/

# 3. 生成 Gradle wrapper（若缺失；CI 由 setup-gradle action 提供 gradle 命令）
if [ ! -f gradle/wrapper/gradle-wrapper.jar ]; then
  gradle wrapper --gradle-version 8.7
fi

# 4. 构建 release APK
./gradlew :app:assembleRelease

# 5. 输出路径
ls -lh app/build/outputs/apk/release/

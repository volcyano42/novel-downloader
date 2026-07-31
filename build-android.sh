#!/usr/bin/env bash
# Build novel-downloader-android APK
# Usage: ./build-android.sh [--project-path <path>] [--sign] [--keystore <path>] [--key-alias <name>]
#
#   --project-path  Android 项目根目录（默认：./android）
#   --sign          签名 release APK（需配置 keystore/key-alias）
#   --keystore      签名密钥库路径（默认：$PROJECT_PATH/release.keystore）
#   --key-alias     密钥别名
#
# 环境要求：Java 17+, Android SDK (ANDROID_HOME 或 ANDROID_SDK_ROOT)

set -euo pipefail
cd "$(dirname "$0")"

# ── 参数解析 ────────────────────────────────────────────
PROJECT_PATH=""
DO_SIGN=false
KEYSTORE=""
KEY_ALIAS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-path) PROJECT_PATH="$2"; shift 2 ;;
        --sign)         DO_SIGN=true; shift ;;
        --keystore)     KEYSTORE="$2"; shift 2 ;;
        --key-alias)    KEY_ALIAS="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,11p' "$0"
            exit 0
            ;;
        *) echo "未知参数: $1（用 --help 查看用法）"; exit 1 ;;
    esac
done

# ── 项目路径 ────────────────────────────────────────────
if [ -z "$PROJECT_PATH" ]; then
    candidate="$(dirname "$0")/android"
    if [ -d "$candidate" ]; then
        PROJECT_PATH="$(cd "$candidate" && pwd)"
    else
        echo -e "\033[31mERROR: 未找到 Android 项目。请用 --project-path 指定路径\033[0m"
        echo -e "\033[33m  期望: ./android\033[0m"
        exit 1
    fi
fi

if [ ! -f "$PROJECT_PATH/gradlew" ]; then
    echo -e "\033[31mERROR: $PROJECT_PATH 不是 Android 项目根目录（缺少 gradlew）\033[0m"
    exit 1
fi

echo -e "\033[36mProject: $PROJECT_PATH\033[0m"

# ── 环境检查 ────────────────────────────────────────────
echo -e "\033[36m--- 环境检查 ---\033[0m"

# Java
if ! command -v java &>/dev/null; then
    echo -e "\033[31mERROR: 未找到 java。请安装 JDK 17+\033[0m"
    exit 1
fi
java_ver=$(java -version 2>&1 | head -1)
echo -e "\033[32m  Java : $java_ver\033[0m"

# Android SDK
SDK_ROOT="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
if [ -z "$SDK_ROOT" ]; then
    for candidate in \
        "$HOME/Android/Sdk" \
        "$HOME/Library/Android/sdk" \
        "/usr/local/lib/android/sdk" \
        "/opt/android-sdk"; do
        if [ -d "$candidate" ]; then SDK_ROOT="$candidate"; break; fi
    done
fi
if [ -z "$SDK_ROOT" ]; then
    echo -e "\033[31mERROR: 未找到 Android SDK。请设置 ANDROID_HOME 或 ANDROID_SDK_ROOT\033[0m"
    exit 1
fi
export ANDROID_HOME="$SDK_ROOT"
echo -e "\033[32m  SDK  : $SDK_ROOT\033[0m"

# local.properties
if [ ! -f "$PROJECT_PATH/local.properties" ] || ! grep -q "^sdk.dir=" "$PROJECT_PATH/local.properties" 2>/dev/null; then
    echo -e "\033[33m  写入 local.properties（sdk.dir）...\033[0m"
    echo "sdk.dir=$SDK_ROOT" > "$PROJECT_PATH/local.properties"
fi

# ── 签名配置 ────────────────────────────────────────────
SIGNING_ARGS=""
if [ "$DO_SIGN" = true ]; then
    if [ -z "$KEYSTORE" ]; then
        KEYSTORE="$PROJECT_PATH/release.keystore"
    fi
    if [ ! -f "$KEYSTORE" ]; then
        echo -e "\033[36m--- 生成签名密钥库 ---\033[0m"
        if [ -z "$KEY_ALIAS" ]; then KEY_ALIAS="novel-downloader"; fi
        read -rsp "密钥库密码（至少 6 位）: " KS_PASS
        echo
        keytool -genkey -v \
            -keystore "$KEYSTORE" \
            -alias "$KEY_ALIAS" \
            -keyalg RSA -keysize 2048 -validity 10000 \
            -storepass "$KS_PASS" \
            -keypass "$KS_PASS" \
            -dname "CN=novel-downloader, OU=Dev, O=novel-downloader, L=Unknown, S=Unknown, C=CN"
        echo -e "\033[32m  密钥库已生成: $KEYSTORE\033[0m"
    fi
    if [ -z "$KEY_ALIAS" ]; then
        echo -e "\033[31mERROR: --sign 需要 --key-alias\033[0m"
        exit 1
    fi
    read -rsp "密钥库密码: " KS_PASS
    echo
    SIGNING_ARGS="-Pandroid.injected.signing.store.file=$KEYSTORE -Pandroid.injected.signing.store.password=$KS_PASS -Pandroid.injected.signing.key.alias=$KEY_ALIAS -Pandroid.injected.signing.key.password=$KS_PASS"
fi

# ── 构建 ────────────────────────────────────────────────
echo -e "\033[36m--- Gradle assembleRelease (3-5 min) ---\033[0m"
cd "$PROJECT_PATH"
chmod +x gradlew 2>/dev/null || true

# shellcheck disable=SC2086
./gradlew assembleRelease $SIGNING_ARGS

# ── 输出 ────────────────────────────────────────────────
APK_PATH=$(find app/build/outputs/apk/release -name "*.apk" ! -name "*unsigned*" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
if [ -z "$APK_PATH" ]; then
    APK_PATH=$(find app/build/outputs/apk/debug -name "*.apk" 2>/dev/null | head -1)
fi

if [ -n "$APK_PATH" ]; then
    DIST_DIR="$PROJECT_PATH/dist"
    mkdir -p "$DIST_DIR"

    VERSION="1.0.0"
    if [ -f app/build.gradle.kts ]; then
        ver=$(grep -oP 'versionName\s*=\s*"\K[^"]+' app/build.gradle.kts 2>/dev/null || true)
        if [ -n "$ver" ]; then VERSION="$ver"; fi
    fi

    OUT_NAME="novel-downloader-v${VERSION}.apk"
    cp "$APK_PATH" "$DIST_DIR/$OUT_NAME"

    SIZE=$(du -h "$APK_PATH" | cut -f1 2>/dev/null || ls -lh "$APK_PATH" | awk '{print $5}')
    echo -e "\033[32mDone: dist/$OUT_NAME ($SIZE)\033[0m"
else
    echo -e "\033[33mWARN: 未找到 APK\033[0m"
fi

cd "$(dirname "$0")"

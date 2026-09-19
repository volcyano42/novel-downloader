import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.novel.downloader"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.novel.downloader"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (rootProject.file("keystore.properties").exists()) {
                // 必须 import java.util.Properties：KTS 里 `java` 是 Project.java 扩展（JavaPluginExtension），
                // 写 java.util.Properties() 会报 `Unresolved reference: util`
                val props = Properties().apply {
                    load(rootProject.file("keystore.properties").inputStream())
                }
                signingConfigs.create("release") {
                    storeFile = rootProject.file(props["storeFile"] as String)
                    storePassword = props["storePassword"] as String
                    keyAlias = props["keyAlias"] as String
                    keyPassword = props["keyPassword"] as String
                }
            } else null
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            // 依赖清单由 android/scripts/build-apk.sh 生成：已过滤 playwright/psutil
            // （Chaquopy 的 pip 块只有 install/options，没有 exclude，无法在此排除包）
            install("-r", "../.req-android.txt")
            // novelbase 有 pyproject.toml，按 pip 包安装（public 无 pyproject，改由脚本复制源码）
            install("file:../..")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.11.0")
}

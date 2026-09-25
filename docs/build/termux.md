# Termux 构建方案（termux-docker，pyroot 内置 Python）

- 镜像：`termux/termux-docker:aarch64`（官方，bionic libc，包管理器 = Termux 的 pkg/apt）
- 预装依赖在容器内完成：`pkg install python rust clang binutils patchelf libheif libjpeg-turbo zlib libffi openssl libyaml python-pillow python-lxml` + `pip install -r requirements.txt`（排除 playwright——browser 模式在 Termux 不可用，psutil 不支持 Android）
- **导出**：`deps/`（site-packages）+ `pyroot/`（Python 本体 bin/lib + 依赖 .so，PYTHONHOME 重定位）
- **健壮性**：pkg update/install 带重试（5 次）+ **整个容器预装流程重试 3 次**（每次全新容器，规避 CI 并发/网络偶发失败）；容器无 `/tmp`（用挂载卷）；`ANDROID_API_LEVEL=24`（maturin 构建 pydantic-core 需要）
- **容器权限陷阱**：容器内创建的文件属主为容器 root，runner 无法 chmod（Operation not permitted）——runner 侧 chmod 加 `|| true`，容器内 root 有全部权限
- **workflow 注册陷阱**：GitHub 只注册默认分支（main）的 workflow，dev 分支的新 workflow 在 Actions 不显示/无法 dispatch，需合并 main

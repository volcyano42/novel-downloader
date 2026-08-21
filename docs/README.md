# novel-downloader 文档导航

外层容器 `D:\Linux\novel-downloader\docs\`(非 git 仓库,被 .gitignore 忽略,不入版本库)。核心仓库在 `D:\Linux\novel-downloader\novel-downloader\`。

## 会话速览(必读)

| 文档 | 内容 |
|------|------|
| [session-prompt.md](session-prompt.md) | 会话上下文速览:项目概述 + 关键约定(行为约束)+ 目录结构 + 文档索引。**新会话从这篇开始** |

## 项目基础(project/)

| 文档 | 内容 |
|------|------|
| [project/overview.md](project/overview.md) | 项目概述、目录结构、架构速览、CI 测试状态 |
| [project/updates.md](project/updates.md) | 更新记录：v4.2.3（9a51b561）之后各提交的变更摘要 |
| [project/cli.md](project/cli.md) | CLI 命令一览 |
| [project/sources.md](project/sources.md) | 平台 source 状态表 + Source 注册机制 |
| [project/config.md](project/config.md) | 配置文件说明(config.yaml / sites/*.yaml / groups.yaml) |
| [project/development.md](project/development.md) | 验证命令、开发环境、衍生产物(novel-downloader-tools/) |

## 项目约定(conventions/)

| 文档 | 内容 |
|------|------|
| [conventions/git.md](conventions/git.md) | Git 提交纪律、分支管理、workflow 触发、版本号更新约定 |

## 学习笔记(learning/)

| 文档 | 内容 |
|------|------|
| [learning/asyncio.md](learning/asyncio.md) | asyncio 异步 API 详解（async/await、gather、Semaphore、Event、to_thread、httpx.AsyncClient），基于 novelbase 全异步化改造实战 |

## 构建与发布(build/)

| 文档 | 内容 |
|------|------|
| [build/packaging.md](build/packaging.md) | 打包方案:pip 安装、portable 便携版、CI 构建产物矩阵 |
| [build/termux.md](build/termux.md) | Termux 构建方案(termux-docker,pyroot 内置 Python) |
| [build/android-apk.md](build/android-apk.md) | Android APK 方案(Chaquopy 嵌入 Python + WebView) |
| [build/pitfalls.md](build/pitfalls.md) | CI 构建经验(踩坑记录,改参数前先看) |

## 设计文档与实施计划(superpowers/)

| 目录 | 内容 |
|------|------|
| [superpowers/specs/](superpowers/specs/) | 功能设计文档(按日期命名,`-design.md` 后缀) |
| [superpowers/plans/](superpowers/plans/) | 实施计划(按日期命名) |

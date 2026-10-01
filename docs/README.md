# novel-downloader 文档导航

本文档目录随核心仓库入库（`novel-downloader/docs/`）。外层容器 `D:\Linux\novel-downloader\docs` 仅存一份指向本目录的指针。核心仓库根：`D:\Linux\novel-downloader\novel-downloader`。

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
| [project/sources.md](project/sources.md) | 书源机制（source.json + 4 个公共 API + 能力声明） |
| [project/config.md](project/config.md) | 配置文件说明(config.yaml / sites/{source_name}.yaml / formats/*.yaml) |
| [project/development.md](project/development.md) | 验证命令、开发环境、衍生产物(novel-downloader-tools/) |
| [project/legacy-migration.md](project/legacy-migration.md) | 旧版本数据迁移总结(I:\NOVEL → 当前项目):方案、脚本、结果、遗留与次日续跑命令、踩坑记录 |

## 项目约定(conventions/)

| 文档 | 内容 |
|------|------|
| [conventions/git.md](conventions/git.md) | Git 提交纪律、分支管理、workflow 触发、版本号更新约定 |

## 构建与发布(build/)

| 文档 | 内容 |
|------|------|
| [build/packaging.md](build/packaging.md) | 打包方案:pip 安装、portable 便携版、CI 构建产物矩阵 |
| [build/termux.md](build/termux.md) | Termux 构建方案(termux-docker,pyroot 内置 Python) |
| [build/pitfalls.md](build/pitfalls.md) | CI 构建经验(踩坑记录,改参数前先看) |

## 规划(planning/)

| 文档 | 内容 |
|------|------|
| [planning/roadmap.md](planning/roadmap.md) | 发展方向分析:实勘现状(仓库可见性/规模/合规风险)+ 十个维度的方向表 + Top 5 + 3/6/12 个月路线图 + MVP + 不建议做 |

## 设计文档与实施计划(superpowers/)

| 目录 | 内容 |
|------|------|
| [superpowers/specs/](superpowers/specs/) | 功能设计文档(按日期命名,`-design.md` 后缀) |
| [superpowers/plans/](superpowers/plans/) | 实施计划(按日期命名) |

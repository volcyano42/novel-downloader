# novel-downloader-public 公开仓库设计 — 设计文档

> 日期：2026-08-20 ｜ 状态：已批准，进入实施

## 背景与目标

在私有仓库 `novel-downloader` 之外新建同级公开仓库 `novel-downloader-public`，公开一部分源码：

- **规避敏感源码**：api 书源（oiapi/rain，逆向/破解）、私有配置、内部设计文档不公开
- **GitHub Actions 额度**：公开仓库 Actions 免费额度不受限，CI 跑公开子集
- **迁移即修改**：private 仓库可继续踩坑，public 是干净的历史

核心难点：**Agent 迁移文件容易混乱**（把敏感/杂项文件迁进 public 并提交）。方案：**白名单迁移清单（.gitignore 的反面）+ 校验脚本**（Agent 迁移后必跑，三道防线）+ AGENTS.md 系统级约定。

## 目录与 Git 形态

```
D:\Linux\novel-downloader\            ← 外层容器（非 git 仓库）
├── novel-downloader\                ← private 仓库（现状）
├── novel-downloader-public\         ← 新公开仓库（独立 .git，同级）
└── .reasonix\ ...
```

- 两仓库完全独立；Agent 迁移 = 按清单**复制**文件进 public → 在 public 内 commit + push
- private 的 `.gitignore` 与 public 互不相干

## 公开范围（白名单）

| 类别 | 内容 | 排除 |
|---|---|---|
| 核心库 | `novelbase/**` | `sources/qidian`、`sources/qimao`、`sources/92xs`、`sources/fanqie/api` |
| WebUI | `backend/**`、`frontend/**` | — |
| 其他源码 | `cli/**`、`shared/**`、`android/**`、`scripts/**`、`tests/**` | — |
| workflow | `.github/workflows/**` | — |
| 根文件 | `README.md`、`LICENSE`、`pyproject.toml`、`requirements.txt`、`CHANGELOG.md` | — |
| 文档 | `docs/README.md`、`docs/project/**`、`docs/build/**`、`docs/conventions/**` | `docs/superpowers/**`、`docs/session-prompt.md`、`docs/learning/**` |

**红名单（双保险，进清单底部）**：`app_data/**`、`.env`、`会话归档/**`、`AGENTS.md`、`*.log`、`docs/superpowers/**` 等。

## 迁移清单 `PUBLIC_MANIFEST.md`

提交 private git（版本化），Agent 迁移的**全局静态规则**：白名单（允许复制）+ 红名单（禁止）。

## 每次迁移的动态清单

除全局 `PUBLIC_MANIFEST.md` 外，**每次迁移操作 Agent 必须输出一份简短的本次迁移清单**（面向用户可审查的中间产物），包含：

- 本次迁移的文件/目录列表（明确列出，含来源→目标）
- 依据的清单条目
- 确认无红名单内容

格式示例：

```markdown
## 本次迁移清单（2026-08-20）
- novelbase/core/engine.py → novelbase/core/engine.py
- novelbase/sources/fanqie/requests/** → novelbase/sources/fanqie/requests/**
- backend/routers/history.py → backend/routers/history.py
- 依据：PUBLIC_MANIFEST.md 白名单「novelbase/**（排除 api）」「backend/**」
- 红名单检查：无（已排除 sources/fanqie/api、app_data 等）
```

作用：用户可在 Agent 复制前审查迁移范围；与 `check_public.py` 的"复制后校验"形成**事前（清单）＋事后（脚本）**双保险。

## 校验脚本 `scripts/check_public.py`

Agent 复制后、commit 前**必跑**，三道防线（任一失败 → 非零退出 → 阻止提交）：

1. **缺失检查**：清单白名单内文件在 public 缺失 → 报错
2. **多余检查**：public 中有清单外文件（敏感/杂项误迁）→ 报错（**关键防线**）
3. **敏感扫描**：public 内容出现敏感模式（`sources/*/api` 目录、`app_data`、`.env`、`oiapi`/`rain` 引用、key 字样等）→ 报错

## 系统级提示词（AGENTS.md 增补「公开迁移约定」）

- 迁移前必须读 `PUBLIC_MANIFEST.md`；只复制清单内文件
- **每次迁移必须先输出「本次迁移清单」**（本次复制的文件/目录列表 + 依据条目 + 红名单确认），供用户审查
- 复制完必须跑 `scripts/check_public.py`，通过才允许在 public 提交
- public 仓库独立提交/推送（不混入 private 的 commit 习惯）
- 敏感判定：`api` 书源、`app_data`、私有配置、`docs/superpowers` 一律不进 public

## 文档隔离

- docs/ 整体仍不提交 private git（现状）；可公开子集走清单白名单复制
- superpowers/session-prompt/learning 红名单排除

## 实施范围（writing-plans 拆分）

1. `PUBLIC_MANIFEST.md`（private 仓库根，提交 git）
2. `scripts/check_public.py` + 单元测试（缺/多/敏感三类）
3. AGENTS.md 增补「公开迁移约定」
4. 初始化 `novel-downloader-public` 仓库（同级）：README、LICENSE、`.gitignore`、`ci.yml`（公开子集 pytest）
5. 首次迁移演练：按清单复制 + check_public 通过 + public commit/push

## 验证

- `scripts/check_public.py` 单元测试通过（三类防线用例）
- 首次迁移后 `check_public.py` 零报错，public 仓库 CI 转绿

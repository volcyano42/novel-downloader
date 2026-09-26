# Git 与协作约定

> 会话速览（session-prompt.md「关键约定」）含完整清单；本文档为 git/分支/workflow/版本 专项。

- **Git 提交** 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式指定文件）；提交前自查这四个规则。**dev 分支的提交与推送可自动执行**（无需逐次请示，2026-08-02 用户授权），但 main 分支例外（见下）
- **分支管理** **dev 分支可自动提交/推送**（2026-08-02 用户授权）；**main 分支的合并与推送必须用户临时同意**（用户明确指示后才执行）：不自动 `git merge` 到 main、不自动 `git push origin main`（含 fast-forward 同步）。已授权的合并/推送：2026-07-31（v4.2.1）、2026-08-01（v4.2.3-dev 多次）、2026-08-02（v4.2.3 发布 + 目录重组后推送 dev/main）、2026-08-02（Android APK 功能完成，用户选择推送 dev，commit 6023f3a）
- **CI**（2026-09-26 起）**`main` 与 `dev` 的 push / PR 都触发**（`.github/workflows/ci.yml`，Linux × Python 3.10/3.11/3.12 三档：语法检查 + 导入验证 + 单元测试）。此前它只写了 `branches: [main]` —— **dev 上的提交从未经过 CI**，文档里的「CI 全部通过」实为本机实测（这也是「CI 全绿、真机白页」能长期共存的原因之一）。**合并 main 之前先确认 dev 的 CI 已绿**：CI 覆盖 dev 后，这个前置检查是免费的
- **远程凭证** origin 使用 Git Credential Manager（Windows 凭据库存 token），URL 不含 token；中文 commit 消息用 `-F <file>` 传入（cmd 引号会吞中文）。**agent 调 GitHub API 复用这份凭据，不要请用户在对话里粘贴 PAT**：

  ```bash
  TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
  curl -H "Authorization: Bearer $TOKEN" https://api.github.com/...
  ```

  GCM 存的是 `gho_` OAuth token（scope `gist, repo, workflow`，足够 dispatch workflow 与查 run）；token 只活在 shell 变量里 —— **不进对话、不落盘、不入 git**。⚠️ Windows 上 `curl` 走 schannel 会因吊销检查失败报 `CRYPT_E_NO_REVOCATION_CHECK`（`HTTP 000`），加 `--ssl-no-revoke` 即可
- **手动触发** 手动构建 workflow 由用户自行在 GitHub 界面触发；**例外**：用户在"构建目标产物"类任务中明确授权时，agent 可自行 dispatch（2026-07-31 起多次授权，含 build-dist / release / 单平台 build-*.yml），但重试前先取消旧 run 保证单 run 运行。**workflow yml 配置支持使用 dev 分支的**：dispatch 用 `ref=dev` 即运行 dev 分支的 yml/构建脚本（workflow 文件本体从默认分支 main 解析注册；已存在的 workflow 文件在 dev 上的修改无需合并 main 即可生效——2026-08-02 build-windows 实测，run 30746855971）。⚠️ **但「新」workflow 文件必须先合并 main 才能 dispatch**（2026-09-26 实测：`build-windows-nuitka.yml` 在 dev 上拆出、尚未上 main 时 dispatch 返回 `404 Not Found` —— GitHub 只认默认分支上的 workflow；判断依据是 `GET /repos/{owner}/{repo}/actions/workflows` 的已注册列表里有没有它）
- **版本号更新** 用户明确要求更新版本时，同步更新 `CHANGELOG.md`（新增 `## v{版本}` 段落）与项目版本号（`pyproject.toml` + `novelbase/__init__.py`）；若版本号不确定，先询问用户

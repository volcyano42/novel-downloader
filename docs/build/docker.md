# Docker 构建与运行

仓库根的 `Dockerfile` 提供「单容器自托管」形态：一个 8000 端口同时提供 API 与前端页面。

## 形态

| 项 | 取值 |
|----|------|
| 阶段 1 | `node:24-slim` → `npm ci && npm run build`，产物仅 `frontend/dist` 进入下一阶段 |
| 阶段 2 | `python:3.12-slim` + `requirements.txt` + Chromium（`playwright install --with-deps chromium`） |
| 端口 | `8000`（uvicorn，`app.py` 默认 `-a 0.0.0.0 -p 8000`） |
| 数据卷 | `/data`（`NLD_APP_DATA=/data`）：`config/`、`storage/`（SQLite）、导出文件、浏览器 profile |
| 运行用户 | `app`（uid 1000，非 root） |
| 入口 | `CMD ["python", "app.py"]` |

## 构建

在**核心仓库目录**内执行（构建上下文 = `novel-downloader/`，不是外层容器目录）：

```bash
cd novel-downloader
docker build -t novel-downloader .
```

## 运行

```bash
docker run -d --name novel-downloader -p 8000:8000 -v novel-data:/data novel-downloader
# 访问 http://localhost:8000
```

带参数（`app.py` 支持 `-a/--host`、`-p/--port`）：

```bash
docker run --rm -p 9000:9000 novel-downloader python app.py -p 9000
```

传 API key（`.env` 不进镜像，用 `--env-file`）：

```bash
docker run -d -p 8000:8000 -v novel-data:/data --env-file .env novel-downloader
```

## 验证

```bash
docker run --rm novel-downloader python -c "from novelbase import *; print('OK')"   # 依赖完整性
curl -fsS http://localhost:8000/api/v2/health                                       # {"ok":true,...}
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/                   # 200（index.html）
```

实测（Docker Desktop / linux-amd64，2026-10-14）：

| 项 | 值 |
|----|----|
| 镜像大小 | 1.57 GB（其中 `/opt/ms-playwright` 658 MB、`/app` 5 MB） |
| 首次构建 | 主要耗时在 Chromium 下载（约 300 MB，见下方踩坑） |
| 启动 | `docker stop` 1.5 s 优雅退出（`app.py` 的 SIGTERM 清理生效，exit 0） |
| 容器内 | `/`、`/assets/*.js`、`/assets/*.css`、`/api/v2/health`、SPA fallback 全部 200；Chromium 153 以 uid 1000 成功启动 |

## 与源码运行的三处差异（改 Dockerfile 前先看）

1. **前端不再由 Vite dev server 提供**：运行时镜像里没有 Node，`app.py` 找不到 `npm`
   时不退出，只启动后端；前端由 `backend.main` 的 SPA fallback 托管 `frontend/dist`。
   本机（有 npm）行为不变：仍会同时拉起 5173 的 Vite dev server。
   因此**容器里不存在 5173**，只有 8000。
2. **浏览器能力强制无头**：书源出厂默认 `headless: false`，而容器没有 X11，headful
   Chromium 启动即失败。构建阶段初始化 `/data/config` 后，为每个 `browser` 能力段写入
   `headless: true`（见 Dockerfile 的 `RUN python <<'PY'`）。用户仍可在 WebUI 里改回。
   注意：**挂载一份本机已有配置到 `/data` 时会带回 `headless: false`**，需要手动改成无头，
   或改用 named volume 让镜像内预置配置生效。注入是幂等的：文件里已有 `headless:` 键就跳过，
   不会覆盖用户的手动设置。
3. **Chromium 的 sandbox**：`backend/services/engine_manager.py::_linux_default_browser_args()`
   在 Linux 上默认追加 `--no-sandbox --disable-gpu --disable-dev-shm-usage`，容器内以
   root/普通用户运行均可用。

## 常见问题

- **8000 打开是「前端未构建」提示页**：说明镜像里没有 `frontend/dist`（构建阶段 1 失败或
  被 `.dockerignore` 误排除）。已构建的镜像不会出现该页。
- **挂载宿主目录到 `/data` 后写入失败**：容器以 uid 1000 运行，bind mount 的宿主目录需
  属于 uid 1000（`chown -R 1000:1000 <dir>`）；named volume 会自动继承镜像内 `/data` 的属主。
- **构建上下文过大 / 传输缓慢**：确认 `.dockerignore` 仍在（本地 `app_data/` 约 8G、
  `dist/` 约 2.4G、根目录的 `*.exe` 均必须排除；漏掉 `*.exe` 会让镜像多背 60 MB 构建产物）。
- **首次构建卡在 Chromium 下载**：`playwright install --with-deps` 会拉
  Chrome for Testing（约 187 MB）+ Chromium Headless Shell（约 114 MB）并 apt 安装约 200 个包，
  网络慢时这一步要十几分钟；依赖层有缓存，改代码后重建只需几秒。

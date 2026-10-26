# syntax=docker/dockerfile:1
#
# novel-downloader —— 多阶段构建。
#   阶段 1 `node:24-slim`：构建前端静态产物（Node 不进运行时镜像）
#   阶段 2 `python:3.12-slim` + Chromium：运行 app.py（后端 + 托管前端产物）
#
# 构建（在 novel-downloader/ 目录内执行，构建上下文即本目录）：
#   docker build -t novel-downloader .
# 运行（单端口 8000 即完整 WebUI）：
#   docker run -d --name novel-downloader -p 8000:8000 -v novel-data:/data novel-downloader
# 访问：http://localhost:8000
#
# 参数透传（app.py 的 -a/-p）：
#   docker run --rm -p 9000:9000 novel-downloader python app.py -p 9000

# ═══════════════════════════════════════════════════════════════
# 阶段 1：前端产物构建
# ═══════════════════════════════════════════════════════════════
FROM node:24-slim AS frontend-build
WORKDIR /build/frontend
# 先只拷清单，命中依赖层缓存（改业务代码不必重装 node_modules）
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ═══════════════════════════════════════════════════════════════
# 阶段 2：运行时
# ═══════════════════════════════════════════════════════════════
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    NLD_APP_DATA=/data

WORKDIR /app

# Python 依赖 + Chromium 及其系统依赖（--with-deps 负责 apt 安装 libnss3/libgbm1 等）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# 项目源码；前端产物取自阶段 1（backend.main 的 SPA fallback 从 frontend/dist 托管）
COPY . .
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# 预置运行时配置到数据卷：容器内没有 X11，浏览器能力保持 headless:false 会启动即失败，
# 故首次初始化后为每个 browser 能力段写入 headless: true（用户仍可在 WebUI 中改）。
RUN python <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")
os.environ.setdefault("NLD_APP_DATA", "/data")

from init_config import init_all_config

init_all_config()

from novelbase.source import capabilities, list_sources

for name in list_sources():
    targets = [cap for cap, mode in capabilities(name).items() if mode == "browser"]
    if not targets:
        continue
    path = Path("/data/config/sources") / f"{name}.yaml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if "headless:" in text:
        continue
    path.write_text(
        text.rstrip("\n") + "\n\n# Docker 运行时：容器无 X11，浏览器能力强制无头\n"
        + "".join(f"{cap}:\n  headless: true\n" for cap in targets),
        encoding="utf-8",
    )
PY

# 非 root 运行；/data 为数据卷（配置 / SQLite / 导出文件 / 浏览器 profile）
RUN useradd --create-home --uid 1000 app \
 && chown -R app:app /app /data

USER app
VOLUME ["/data"]
EXPOSE 8000
CMD ["python", "app.py"]

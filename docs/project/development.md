# 验证命令、开发环境与衍生产物

## 验证命令

```powershell
# 后端导入
python -c "from novelbase import *; print('OK')"

# CLI 冒烟
python cli.py sources list
python cli.py novel list

# 前端编译（按 tsconfig.app.json 单项目检查）
cd frontend
npx tsc --noEmit --project tsconfig.app.json

# 整仓类型检查：根 tsconfig.json 是 solution 风格，`tsc --noEmit` 会空转，须用 -b
npx tsc -b

# 运行测试（567 passed / 1 failed，2026-10-25 实测；
# 失败项为 tests/test_encoding.py::test_detect_encoding_gbk —— chardet 对短样本的编码误判，与业务无关）
python -m pytest tests/ -v --tb=short
```

## 开发环境

- Windows 10/11 (PowerShell) 或 Linux（含 Termux）
- Python 3.10+（3.13 开发环境）
- Node 24.15, npm 11.14
- Playwright Chromium 可用（`playwright install chromium`，桌面端）
- pip 依赖见 requirements.txt / pyproject.toml

### 常见坑

- **改后端代码必须重启**：`app.py` 拉 uvicorn 时**没带 `--reload`**（`app.py:44-48`），改完不重启就还是老代码。典型表现：新加的接口报 **405**（见下一条）。
- **未注册路径的 POST 返回 405 而不是 404**：`backend/main.py:118` 的 SPA fallback 是 `@app.get("/{full_path:path}")`——路径能匹配任意字符串但只接受 GET，所以 POST 一个不存在的接口得到的是 405。看到 405 先怀疑“这个进程没有这条路由”，别去查方法名。
- **vite proxy 端口是写死的**：`frontend/vite.config.ts:16,20` 硬编码 `http://127.0.0.1:8000`。用 `python app.py -p 8001` 改端口启动时，前端请求**仍然打 8000**；那个端口上如果还挂着旧实例，就会出现“代码改了却没生效”。排查：`pgrep -af uvicorn` 看有没有残留进程。
- **同步单实例测不了**：同步是“本机拉对端”，自己拉自己差集永远是空。需起两个实例，见下。

## 同步功能验证（两实例）

同步需要两个独立实例（不同端口 + 不同数据目录），同端口或同 `NLD_APP_DATA` 都验证不了：

```bash
# 对端（8001）：先得有一本书，不然没东西可拉
NLD_APP_DATA=/tmp/peer python -m uvicorn backend.main:app --port 8001

# 本机（8000）
NLD_APP_DATA=/tmp/local python -m uvicorn backend.main:app --port 8000

# 触发（本机 → 对端），然后查进度
curl -X POST http://127.0.0.1:8000/api/v2/sync/start \
  -H 'Content-Type: application/json' -d '{"peer":"127.0.0.1:8001"}'
curl http://127.0.0.1:8000/api/v2/sync/status
```

也可以用 UI：本机 WebUI → 设置 → 同步 → 填对端地址（`192.168.x.x:8001`）→ 开始同步。

验证要点：首次应报「新增 N 本 · 补 M 章」；**直接重跑应报「补 0 章 · 跳过 M 章」**（幂等）；把本地某本书的 `order` 改乱后重跑，应报「跳过 1 本（章节序号不一致）」。

## 衍生产物（novel-downloader-tools/）

- **email_downloader.py**：番茄小说邮件下载脚本（仅 API rain 模式）——只接受 URL、异步下载、前 3 章测速发提醒邮件、导出全格式打包发邮件；通过 `NLD_CORE_DIR`（默认兄弟目录 novel-downloader/）定位核心库与配置，`NLD_CONFIG_DIR` 可覆盖
- **scripts/**：调试/工具脚本（debug_source / debug_exporter / debug_parser / cloud_sync / recover_db / archive）；debug_source/debug_exporter 通过 `NLD_CORE_DIR` sys.path 引导 import 核心

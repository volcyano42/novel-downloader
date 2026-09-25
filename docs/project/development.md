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

# 运行测试（444 passed / 1 skipped，2026-09-25 实测）
python -m pytest tests/ -v --tb=short
```

## 开发环境

- Windows 10/11 (PowerShell) 或 Linux（含 Termux）
- Python 3.10+（3.13 开发环境）
- Node 24.15, npm 11.14
- Playwright Chromium 可用（`playwright install chromium`，桌面端）
- pip 依赖见 requirements.txt / pyproject.toml

## 衍生产物（novel-downloader-tools/）

- **email_downloader.py**：番茄小说邮件下载脚本（仅 API rain 模式）——只接受 URL、异步下载、前 3 章测速发提醒邮件、导出全格式打包发邮件；通过 `NLD_CORE_DIR`（默认兄弟目录 novel-downloader/）定位核心库与配置，`NLD_CONFIG_DIR` 可覆盖
- **scripts/**：调试/工具脚本（debug_source / debug_exporter / debug_parser / cloud_sync / recover_db / archive）；debug_source/debug_exporter 通过 `NLD_CORE_DIR` sys.path 引导 import 核心

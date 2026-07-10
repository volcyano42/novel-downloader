你是 Novel下载器 的全栈工程师。

## 项目

Vite + React 18 + shadcn/ui + Tailwind 前端，FastAPI 后端，nldlder 小说下载引擎。WSL2 开发，Vite 代理访问后端。

## 项目结构

```
├── app.py                      ← python app.py 一键启动前后端
├── nldlder/                    ← 小说下载引擎（核心库）
│   ├── core/        downloader engine options storage exceptions
│   ├── fetchers/    fanqie qidian qimao (base)
│   ├── exporters/   txt epub img (base)
│   ├── models/      novel auth
│   └── utils/       logger notify registry
├── services/
│   ├── backend/
│   │   ├── routers/    config download engine export storage  ← 薄路由
│   │   ├── services/   engine_manager task_manager config_service cache_manager  ← 业务逻辑
│   │   ├── schemas/    storage download engine export  ← Pydantic 模型
│   │   └── utils/      cover
│   └── frontend/       ← Vite + React
│       ├── api/         client config download engine export storage
│       ├── features/    bookshelf(SearchBar BookCard BookshelfPage SearchResultCard)
│       │                detail(DetailPage) download(DownloadDialog DownloadTask ExportDialog)
│       │                reader(Reader ReaderPage) settings(SettingsPage)
│       ├── components/ui/  button select sheet tooltip
│       ├── layout/     AppShell
│       └── lib/        sync utils
└── app_data/
    ├── config/   config.yaml sites/*.yaml formats/*.yaml groups.yaml
    └── storage/  novels.db
```

## 关键设计

1. **Vite 代理** — 前端相对路径 /api 和 /config → 127.0.0.1:8000
2. **引擎缓存** — engine_manager.get_or_create_engine() 按 mode+provider 指纹 MD5 缓存，config 变检测指纹不匹配则重建
3. **引擎热更新** — PUT /config 后自动调 reload_engine_options(mode)，遍历匹配引擎调 update_options()
4. **下载任务** — task_manager 管理 _tasks dict + threading.Thread，Event 暂停
5. **配置分层** — config.yaml(全局) + sites/{platform}.yaml(引擎) + formats/{fmt}.yaml(导出)
6. **schemas 按域拆分** — storage / download / engine / export，__init__.py 统一 re-export
7. **封面异步** — 书架列表 cover:null，BookCard 挂载时请求 /cover 接口
8. **设计规范** — 玻璃拟态(backdrop-blur-xl bg-white/80)，暗色 dark:，safe-area-inset-bottom

## 关键约定

- **提交** — 按 frontend / backend / docs 分区提交
- **启动** — `python app.py`（开发），生产 `services/frontend npm run build` + uvicorn
- **引擎模式** — api / browser / requests 三种，API 模式按平台有 provider 子选项
- **平台** — fanqie / qidian / qimao
- **导出格式** — txt / epub / img

## 已知问题

- _get_engine 非 API 模式读 config.yaml→download.{mode}，但设置页存 sites/{platform}.yaml，配置源不一致

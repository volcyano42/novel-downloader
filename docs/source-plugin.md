# 书源独立打包插件 — 设计草案

> **状态**：设计草案，未实现。Phase 1 已完成硬编码兜底移除 + manifest 机制，Phase 2 将在适当时机实现。
>
> *（2026-09-25 注）API 名称已按书源扁平化后的 `novelbase/source.py` 对齐：入口是 `source.resolve(source_name, capability) -> (fn, mode)`，旧 `registry.resolve(name, mode, function)` / `register_source()` 已随扁平化删除。*


## 目标

书源可以独立打包成 exe（Nuitka onefile），主程序通过子进程 + stdio JSON-RPC 调用书源函数。新增书源只需编译插件并放到指定目录，无需重新编译主程序。

## 架构

```
┌─────────────────────────┐
│  主程序 (novel-downloader)  │
│                         │
│  source.resolve()       │
│       ↓                 │
│  本地内置源 → import_module  │
│  插件源     → RPC 代理函数   │
│       ↓                 │
│  ┌─────────────────┐    │
│  │ 插件管理器         │    │
│  │ plugin_dir 扫描    │    │
│  │ 进程生命周期       │    │
│  │ 崩溃隔离 + 重试    │    │
│  └────────┬────────┘    │
└───────────┼─────────────┘
            │ stdio JSON-RPC
    ┌───────┴───────┐
    │  plugin_xxx.exe │  ← Nuitka onefile
    │  search()       │
    │  novel_info()   │
    │  chapter_list() │
    │  chapter_content│
    └─────────────────┘
```

## 协议

主程序与插件通过 stdio 通信，每行一个 JSON-RPC 请求/响应：

### 请求

```json
{"jsonrpc": "2.0", "id": 1, "method": "search", "params": {"query": "关键词", "engine_config": {...}}}
```

### 响应

```json
{"jsonrpc": "2.0", "id": 1, "result": [{"title": "...", "url": "...", ...}]}
{"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "..."}}
```

### 四个 RPC 方法

| method | 参数 | 返回 |
|--------|------|------|
| `search` | query, engine_config | SearchResult[] |
| `novel_info` | url, engine_config | NovelMeta |
| `chapter_list` | url, engine_config | ChapterBrief[] |
| `chapter_content` | url, engine_config | ChapterData |

`engine_config` 为引擎配置 dict（headers, cookies, timeout 等），插件自己创建轻量 HTTP 引擎。

## 限制：browser 模式不可插件化

**核心原因**：browser 模式引擎（DrissionPage Chromium 实例）在主进程缓存并持有浏览器进程句柄，无法序列化跨进程传递。

| 模式 | 可插件化 | 说明 |
|------|:--:|------|
| requests | ✅ | HTTP 引擎无状态，插件进程自建 |
| api | ✅ | 同上 |
| browser | ❌ | 浏览器进程在主进程，跨进程不可传递 |

**处理**：`resolve(source_name, capability)` 对 browser 模式的插件书源抛出明确错误："browser 模式不支持插件源，请使用内置源或切换到 requests/api 模式"。

## 进程生命周期

1. **按需启动**：首次 `resolve(source_name, capability)` 时启动插件进程，缓存进程句柄。
2. **空闲回收**：插件进程 30 分钟无调用则自动退出。
3. **主程序退出**：主进程退出时发送 `{"jsonrpc":"2.0","method":"shutdown"}` 并等待 3 秒，超时则强制 kill。
4. **崩溃恢复**：插件进程意外退出时，下一次调用自动重启（最多 3 次重启，超过则标记插件不可用）。

## 超时与重试

- 单次 RPC 调用超时：30 秒
- 超时后主程序发送 cancel 通知（不保证生效），然后 kill 进程并重启
- 3 次连续超时/崩溃 → 插件标记为不可用，后续调用直接报错

## 插件目录

```
app_data/plugins/
├── fanqie_requests.exe
├── qidian_requests.exe
└── ...
```

插件命名约定：`{source_name}.exe`（`source_name` 已含模式，如 `fanqie-requests-default.exe`）。`list_sources()` 扫描插件目录自动发现插件源，合并到内置源列表。

## 实现要点

1. **proxy 函数**：`SourceProxy(source_name, capability)` 类，实现与内置源函数相同签名，内部用 `subprocess.Popen` + stdin/stdout JSON-RPC 通信。
2. **插件编译**：每个书源编译时生成独立的 `plugin_main.py`（只含该源 + 轻量 HTTP 引擎，不含 DrissionPage/浏览器），Nuitka onefile 打包。
3. **engine_config 序列化**：只传 dict（headers/cookies/timeout），不传 Engine 对象。插件内部 `create_engine(engine_config)` 创建自己的引擎实例。
4. **发现扩展**：扩展 `novelbase/source.py` 的 `list_sources()` / `resolve()`，扫描 `app_data/plugins/` 目录，将发现的插件源合并进返回结果（旧 `register_source()` 已随扁平化删除）。

## 未解决的问题

- 插件版本的兼容性（主程序 API 变化后旧插件怎么办）
- 插件间共享 HTTP 连接池（目前各自独立）
- 多插件并发时 stdio 管道性能（替代方案：TCP socket）

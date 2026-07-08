# API 路由文档

前缀 `/api/v1`，共 32 条路由。

---

## Storage — 书架 / 存储

```
/api/v1/storage/
├── backend                              GET / PUT
├── novel/
│   ├──                                  GET
│   └── {novel_id}/
│       ├── cover                        GET
│       ├── meta                         GET / PUT
│       ├──                              DELETE
│       ├── chapters/                    GET / PUT
│       └── chapter/{chapter_id}         GET / DELETE
```

### 路由明细

#### `GET /storage/backend`
列出可用存储后端 + 当前使用的。

返回：
```json
{"backends": ["local", "sqlite"], "current": "sqlite"}
```

#### `PUT /storage/backend`
切换存储后端（通知前端重载）。

Body：
```json
{"backend": "sqlite"}
```

返回：
```json
{"backend": "sqlite", "status": "switched"}
```

#### `GET /storage/novel`
书架列表，**不含封面 base64**（减少响应体积）。

返回：`NovelMeta[]`，其中 `cover` 始终为 `null`。

```json
[{
  "title": "书名", "url": "https://...", "id": "...", "serial": 3,
  "author": "作者", "description": "简介",
  "tags": ["标签1"], "count": 100000, "cover": null
}]
```

#### `GET /storage/novel/{novel_id}/cover`
单本封面（异步加载），只读 illustrations 表不加载整本 meta。

返回：
```json
{"raw_data": "base64...", "alt": "封面", "url": "https://...", "format": "jpeg"}
```
- HEIC 自动转 JPEG；PIL 缺失时 `raw_data` 为 `null`
- 404 `{"detail":"小说不存在"}`

#### `GET /storage/novel/{novel_id}/meta`
小说详情（含封面）。

返回：`NovelMeta`，封面为完整 `CoverData`。
404 `{"detail":"小说不存在"}`

#### `PUT /storage/novel/{novel_id}/meta`
保存小说元数据。

Body：`NovelMeta`

返回：
```json
{"status": "ok", "novel_id": "..."}
```

#### `DELETE /storage/novel/{novel_id}`
删除小说及全部章节 + 插图（级联）。

返回：
```json
{"status": "deleted", "novel_id": "..."}
```
404 `{"detail":"小说不存在"}`

#### `GET /storage/novel/{novel_id}/chapters`
章节列表，分页 + 筛选。

Query：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `order` | `str?` | — | 范围：`1-100` / `50-` / `-50` |
| `volume` | `str?` | — | 卷名精确匹配 |
| `status` | `str?` | — | （暂为 no-op） |
| `page` | `int` | `1` | ≥1 |
| `size` | `int` | `100` | 1–20000 |

返回：`ChapterBrief[]`

```json
[{
  "id": "ch1", "url": "https://...", "novel_id": "...",
  "title": "第一章", "order": 1, "volume": "正文", "count": 1200,
  "downloaded": true
}]
```
- `downloaded` = `content is not None`

#### `PUT /storage/novel/{novel_id}/chapters`
批量保存章节。

Body：`ChapterData[]`

返回：
```json
{"status": "ok", "count": 50}
```

#### `GET /storage/novel/{novel_id}/chapter/{chapter_id}`
单章完整内容（含插图 base64）。

返回：`ChapterData`
```json
{
  "id": "ch1", "url": "https://...", "novel_id": "...",
  "title": "第一章", "order": 1, "volume": "正文",
  "content": "正文内容...", "time": 1000.0, "count": 1200,
  "images": [
    {"raw_data": "base64...", "alt": "插图1", "insert": 5, "url": "https://..."}
  ]
}
```
404 `{"detail":"章节不存在"}`

#### `DELETE /storage/novel/{novel_id}/chapter/{chapter_id}`
删除单章 + 关联插图。

返回：
```json
{"status": "deleted"}
```

---

## Download — 搜索 / 下载 / 任务

```
/api/v1/download/
├── search                               GET
├── novel                                POST
├── novel/{novel_id}                     GET
│   ├── chapters                         GET
│   └── chapter                          POST
├── tasks                                GET
├── task/{task_id}/
│   ├── pause                            POST
│   ├── resume                           POST
│   └──                                  DELETE
└── platform                             GET
```

### 路由明细

#### `GET /download/search`
搜索小说 — 支持关键词、URL 直搜、纯数字 ID。

Query：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `platform` | `str` | 必填 | 平台标识：`fanqie` / `qidian` / `qimao` |
| `query` | `str` | 必填 | 关键词 / URL / 数字 ID |
| `page` | `int` | `1` | 关键词搜索时才生效 |
| `mode` | `str?` | — | `api` / `browser` / `requests` |
| `provider` | `str?` | — | API 模式下的 provider 名（如 `rain`） |
| `engine_id` | `str` | `"default"` | 引擎实例 ID |

行为：
- `query` 以 `http` 开头 → 按 URL 直搜 `fetch_meta`
- `query` 为纯数字 → 走 `get_fetcher_for_id`
- 其他 → 关键词搜索

返回：`SearchResultData[]`
```json
[{
  "title": "书名", "author": "作者",
  "url": "https://...", "description": "简介"
}]
```
500 `{"detail":"..."}`

#### `POST /download/novel`
获取远程小说 meta + 封面。

Body：`FetchMetaRequest`
```json
{"url": "https://...", "engine_id": "default"}
```

Query：`?mode=api&provider=rain`

返回：
```json
{
  "title": "书名", "url": "https://...", "id": "...", "serial": 3,
  "author": "作者", "description": "简介",
  "tags": ["标签1"], "count": 100000,
  "cover": {"raw_data": "base64...", "alt": "封面", "url": "https://...", "format": "jpeg"}
}
```

#### `GET /download/novel/{novel_id}`
获取远程小说详情（**不含**封面）。

Query：`?url=https://...&engine_id=default&mode=api&provider=rain`

返回：同 `POST /download/novel`，但无 `cover` 字段。

#### `GET /download/novel/{novel_id}/chapters`
获取远程章节列表。

Query：`?url=https://...&engine_id=default&mode=api&provider=rain`

返回：`ChapterBrief[]`
```json
[{
  "id": "ch1", "url": "https://...", "novel_id": "...",
  "title": "第一章", "order": 1, "volume": "正文", "count": 1200,
  "downloaded": false
}]
```
- `count` 为远程字数，非本地字数
- `downloaded` 始终为 `false`（远程列表不判断本地状态）

#### `POST /download/novel/{novel_id}/chapter`
提交下载任务（异步后台执行）。

Query：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `title` | `str` | `""` | 书名（任务追踪用） |
| `engine_id` | `str` | `"default"` | 引擎实例 ID |
| `mode` | `str?` | — | `api` / `browser` / `requests` |
| `provider` | `str?` | — | API provider 名 |
| `novel_url` | `str` | `""` | 小说 URL（用于保存 meta） |

Body：`DownloadChapterRequest[]`
```json
[{
  "id": "ch1", "url": "https://...", "novel_id": "...",
  "title": "第一章", "order": 1, "volume": "正文"
}]
```

返回：
```json
{"task_id": "a1b2c3d4e5f6", "total": 100}
```

#### `GET /download/tasks`
所有下载任务列表。

返回：
```json
[{
  "task_id": "a1b2c3d4e5f6", "novel_id": "...", "title": "书名",
  "total": 100, "progress": 42, "status": "downloading",
  "error": null, "errors": [], "current_title": "第42章", "detail": ""
}]
```

字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | `str` | 12 位 hex |
| `novel_id` | `str` | 小说 ID |
| `title` | `str` | 书名 |
| `total` | `int` | 总章节数 |
| `progress` | `int` | 已处理章节数 |
| `status` | `str` | `downloading` / `paused` / `completed` / `failed` |
| `error` | `str?` | 失败/错误摘要，最多 3 条 |
| `errors` | `str[]` | 逐章错误详情 |
| `current_title` | `str` | 当前正在下载的章节名 |
| `detail` | `str` | 最近一条错误/提示 |

#### `POST /download/task/{task_id}/pause`
暂停下载任务。

返回：
```json
{"status": "ok"}
```
404 `{"detail":"任务不存在"}`

#### `POST /download/task/{task_id}/resume`
恢复下载任务。

返回：
```json
{"status": "ok"}
```
404 `{"detail":"任务不存在"}`

#### `DELETE /download/task/{task_id}`
删除下载任务（不删除已下载内容）。

返回：
```json
{"status": "ok"}
```
404 `{"detail":"任务不存在"}`

#### `GET /download/platform`
可用搜索平台列表。

返回：
```json
[{"id": "fanqie", "label": "FanqieBrowserFetcher"}, ...]
```

---

## Export — 导出

```
/api/v1/export/
├── format                               GET
├──                                      POST
├── task/{task_id}                       GET
└── download/{task_id}                   GET
```

### 路由明细

#### `GET /export/format`
可用导出格式列表。

返回：
```json
[{"id": "txt", "label": "TXT"}, {"id": "epub", "label": "EPUB"}, {"id": "img", "label": "IMG"}]
```

#### `POST /export`
触发导出任务。

Body：`ExportRequest`
```json
{
  "novel_id": "7143038691944959011",
  "chapter_id": null,
  "txt": {
    "enabled": true, "encoding": "utf-8",
    "output_path": "", "file_name_template": ""
  },
  "epub": {
    "enabled": true, "compression": "deflate", "compresslevel": 9,
    "include_toc": true, "optimize_images": true,
    "jpeg_quality": 85, "max_image_width": 0
  },
  "img": {"enabled": false}
}
```

行为：
- `chapter_id` 为 `null` 时导出全部章节
- 单格式 → 直接下载源文件
- 多格式 → ZIP 打包

返回：
```json
{"task_id": "a1b2c3d4"}
```
400 `{"detail":"没有启用任何导出格式"}`

#### `GET /export/task/{task_id}`
查询导出任务状态。

返回：`ExportTaskStatus`
```json
{
  "task_id": "a1b2c3d4", "status": "completed",
  "progress": 1.0,
  "formats": ["txt", "epub"],
  "path": "/tmp/nld_export_xxx/书名.zip"
}
```

状态枚举：`pending` → `downloading` → `completed` / `failed`

404 `{"detail":"任务不存在"}`

#### `GET /export/download/{task_id}`
下载导出文件。

返回：`FileResponse`（浏览器触发下载）。
- `.zip` → `application/zip`
- 单文件 → `application/octet-stream`

400 `{"detail":"导出尚未完成"}` — 任务状态不是 `completed`
404 `{"detail":"任务不存在"}` / `{"detail":"导出文件已被清理"}`

---

## Config — 配置

```
/api/v1/config/
├──                                      GET
└──                                      PUT
```

### 路由明细

#### `GET /config`
返回全部配置（全局 + 平台引擎 + 格式 + 分组）。

返回：
```json
{
  "name": "Novel下载器",
  "mode": "browser",
  "max_workers": 3,
  "log_level": "INFO",
  "notify": {
    "on_complete": true,
    "on_incomplete": true,
    "sound": "bell",
    "on_chapter_unavailable": true,
    "chapter_unavailable_sound": "bell"
  },
  "platforms": {
    "fanqie": {
      "browser": {"headless": true, "browser_type": "chromium", "delay": [3, 5], ...},
      "requests": {"delay": [3, 5], "timeout": 30, ...},
      "api": {"rain": {"enabled": true, "key": "...", ...}}
    },
    "qidian": {...},
    "qimao": {...}
  },
  "txt": {"enabled": true, "encoding": "utf-8", ...},
  "epub": {"enabled": true, "compression": "deflate", ...},
  "img": {"enabled": false, "output_format": "original", ...},
  "browser": {...},
  "requests": {...},
  "api": {...},
  "api_providers": {"fanqie": ["rain"]},
  "groups": {"default": {"novel_id_1": {}}, ...}
}
```

- `platforms` — 来自 `sites/*.yaml`，按平台分组
- `txt` / `epub` / `img` — 来自 `formats/*.yaml`
- `browser` / `requests` / `api` — 兼容旧版，取首个平台的配置
- `groups` — 来自 `groups.yaml`

#### `PUT /config`
写入配置（按需传部分字段）。

Body：
```json
{
  "mode": "browser",
  "max_workers": 3,
  "notify": {"on_complete": true, "on_incomplete": true, "sound": "bell"},
  "platforms": {
    "fanqie": {
      "browser": {"headless": false, "delay": [3, 5]},
      "requests": {"delay": [3, 5]}
    }
  },
  "txt": {"enabled": true, "encoding": "utf-8"},
  "epub": {"enabled": true, "compression": "deflate"},
  "img": {"enabled": false}
}
```

写入规则：

| 请求 key | 落地文件 |
|----------|---------|
| `platforms.{plat}.{mode}.{key}` | `sites/{plat}.yaml`（合并写入） |
| `mode` / `name` / `max_workers` / `notify` / `log_level` | `config.yaml` |
| `txt` / `epub` / `img` | `formats/{fmt}.yaml` |

---

## Engine — 引擎管理

```
/api/v1/engine/
├──                                      GET
├── create                               POST
├── {engine_id}                          GET / DELETE
└── type/list                            GET
```

### 路由明细

#### `GET /engine`
引擎实例列表。

返回：
```json
[{"id": "a1b2c3d4", "mode": "browser"}, ...]
```

#### `POST /engine/create`
创建引擎实例。

Body：`CreateEngineRequest`
```json
{
  "mode": "api",
  "api": {
    "name": "rain", "enabled": true,
    "delay": [3, 5], "timeout": 30,
    "retry_times": 3, "backoff_factor": 2,
    "key": "...", "params": null
  }
}
```
- `mode` 为 `browser` 时传 `browser` 字段；为 `requests` 时传 `requests` 字段

返回：
```json
{"engine_id": "a1b2c3d4", "mode": "api"}
```

#### `GET /engine/{engine_id}`
查看引擎详情。

返回：
```json
{"id": "a1b2c3d4", "mode": "api"}
```
404 `{"detail":"引擎不存在"}`

#### `DELETE /engine/{engine_id}`
删除引擎实例（自动 `close()`）。

返回：
```json
{"status": "deleted", "engine_id": "a1b2c3d4"}
```

#### `GET /engine/type/list`
可用引擎类型。

返回：
```json
{"types": ["api", "browser", "requests"]}
```

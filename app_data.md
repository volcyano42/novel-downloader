# `app_data/` — 数据目录结构

`app_data/` 位于项目根目录，由 CLI 入口 `main.py:17` 和 Web 服务 `service/config.py:10` 自动解析（`<project_root>/app_data/`）。库包 `nldlder/` 不硬编码此路径，通过参数接收。

```
{app_data}/
├── config/                    # 用户配置 (YAML)
│   ├── config.yaml            # 主配置 — 下载模式、并发数、分组标签
│   ├── sites/                 # 各网站独立配置 — 浏览器/API/HTTP 参数
│   │   ├── fanqie.yaml
│   │   └── qidian.yaml
│   └── formats/               # 导出格式配置
│       ├── txt.yaml
│       ├── epub.yaml
│       ├── img.yaml
│       └── sqlite.yaml
├── storage/                   # 断点续传数据 (JSON)
│   └── {novel_id}/
│       ├── meta.json          # 小说元数据
│       └── chapters/
│           ├── 00001.json     # 每章独立存储，按 order 编号
│           └── ...
├── exports/                   # 最终导出文件
│   └── {group}/
│       └── {novel_title}/
│           ├── {title} - {author}.txt
│           ├── {title} - {author}.epub
│           ├── img/           # IMG 格式导出图片
│           │   ├── 0.jpg      # 封面
│           │   ├── 1.jpg
│           │   └── ...
│           └── {title}.db     # SQLite 数据库
└── browser/                   # Playwright 浏览器用户数据
    └── Chromium/
        └── User Data/         # browser cookie/缓存（site YAML 中配置路径）
```

---

## `config/config.yaml` — 主配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `mode` | `browser` | 下载模式：`browser` / `api` / `requests` |
| `group` | `default` | 导出分组标签，对应 `exports/{group}/` 子目录 |
| `download.max_workers` | `3` | 章节下载并发数 |

---

## `config/sites/{fanqie,qidian}.yaml` — 网站配置

每个网站按模式分三节，部分字段可选：

| 模式 | 主要字段 | 说明 |
|------|----------|------|
| `browser` | `browser_type`, `headless`, `user_data_dir`, `viewport`, `timeout`, `retry_times`, `backoff_factor`, `delay` | Playwright 浏览器自动化参数。`user_data_dir` 默认指向 `app_data/browser/Chromium/User Data` |
| `api` | `oiapi.key`, `batch_size`, `timeout`, `retry_times`, `backoff_factor`, `delay`, `params` | 内部 API 直连 |
| `requests` | `headers.User-Agent`, `cookies`, `proxies`, `timeout`, `retry_times`, `backoff_factor`, `delay` | 纯 HTTP 请求。登录成功后的 cookies 会写回此处 (`main.py:121-127`, `service/routes/api.py:179-185`) |

---

## `config/formats/{txt,epub,img,sqlite}.yaml` — 导出格式配置

每个文件以格式名为顶级键，公共字段如下：

| 字段 | 适用格式 | 说明 |
|------|----------|------|
| `enabled` | 全部 | `true` / `false`，是否导出此格式 |
| `output_path` | 全部 | 路径模板，占位符：`{group}`, `{title}`, `{file_name_template}`。默认：`app_data/exports/{group}/{title}/{file_name_template}` |
| `file_name_template` | 全部 | 文件名模板，占位符：`{title}`, `{author}`, `{novel_id}`, `{total_chapters}`, `{date}`。默认 `{title}` |
| `extension` | 全部 | `.txt` / `.epub` / `.jpg` / `.db` |

各格式特有字段：

| 格式 | 字段 | 说明 |
|------|------|------|
| epub | `css_style` | CSS 主题名或原始 CSS 字符串 |
| epub | `include_toc` | 是否生成 EPUB3 导航 |
| epub | `compression` | `deflate` / `bzip2` / `stored` |
| epub | `compresslevel` | 0–9 deflate 压缩级别 |
| epub | `optimize_images` | 是否用 Pillow 重压缩 JPEG/PNG |
| epub | `jpeg_quality` | JPEG 质量 1–100 |
| epub | `max_image_width` | 图片最大宽度，0 = 不缩放 |

---

## `storage/{novel_id}/` — 存储结构

由 `nldlder/core/storage.py` 的 `Storage` 类管理。

### `meta.json` — `storage.py:63-74`

```json
{
  "title": "十日终焉",
  "url": "https://fanqienovel.com/page/7143038691944959011",
  "id": "7143038691944959011",
  "serial": 1496,
  "author": "杀虫队队员",
  "description": "简介...",
  "tags": ["已完结", "悬疑脑洞"],
  "count": 3201288,
  "rating": null,
  "cover": {
    "raw_data": "<base64 图片数据>",
    "alt": "十日终焉",
    "insert": null,
    "url": "https://p3-novel-sign.byteimg.com/..."
  }
}
```

### `chapters/{chapter_id}.json` — `storage.py:100-113`

```json
{
  "id": "7193686613892563516",
  "url": "https://fanqienovel.com/reader/7193686613892563516",
  "title": "第109章 熟人",
  "order": 109,
  "volume": "第二卷：我看到了你们",
  "content": "还不等乔家劲反应...",
  "time": 1674910709.0,
  "count": "2063",
  "is_complete": true,
  "images": []
}
```

---

## `exports/{group}/{novel_title}/` — 导出文件

四种导出格式由对应的 Exporter 类处理，按 `order` 排序并去重：

| 格式 | 扩展名 | Exporter 类 | 输出文件 |
|------|--------|-------------|----------|
| TXT | `.txt` | `TXTExporter` (`exporters/txt.py`) | 单文件，含标题头和所有章节 |
| EPUB | `.epub` | `EPUBExporter` (`exporters/epub.py`) | EPUB3 ZIP，含 CSS/TOC/封面/图片 |
| IMG | `.jpg` | `IMGExporter` (`exporters/img.py`) | `img/0.jpg`（封面）, `img/1.jpg` ... |
| SQLite | `.db` | `SQLITEExporter` (`exporters/sqlite.py`) | 单文件，含 `novel_meta` + `chapters` 表 |

**命名规则**：`file_name_template` + `extension` 替换 `output_path` 中的 `{file_name_template}`，再将完整路径用 `{title}`, `{author}`, `{novel_id}`, `{total_chapters}`, `{date}` 格式化。

---

## 日志

日志由 `nldlder/utils/logger.py` 管理，默认输出到系统临时目录 `{tempdir}/novel-downloader/{timestamp}.log`（格式：`%Y%m%d_%H%M%S`），不自动轮转。

- **格式**：`%(asctime)s [%(levelname)-5s] %(name)s: %(message)s` (`%H:%M:%S` 时间格式)
- **级别**：默认 `DEBUG`，通过 `LogOptions.level` 配置

> `app_data/logs/` 目录默认不存在。如需输出到 app_data 下，需在 `Options` 中显式设置日志路径。

---

## 浏览器用户数据

`app_data/browser/Chromium/User Data/` 由 浏览器模式使用，存储登录会话和 cookies。路径在 `config/sites/{fanqie,qidian}.yaml` 的 `browser.user_data_dir` 中配置，默认指向此目录。

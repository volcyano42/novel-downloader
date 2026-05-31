# novel-downloader

番茄小说 / 起点 / 笔趣阁 小说下载器，支持交互式 CLI 和命令行参数两种使用方式。

## 功能

- **登录** — 打开浏览器手动登录，自动保存 Cookie
- **搜索** — 关键词搜索小说，上下键选择结果
- **下载** — 多线程并发下载章节正文和插图，Rich 进度条
- **更新** — 扫描已下载小说，自动检查并下载新章节
- **导出** — 支持 TXT、EPUB、IMG（图片）三种格式

## 安装

```bash
git clone https://github.com/volcyano42/novel-downloader.git
cd novel-downloader
pip install -r requirements.txt
```

## 快速开始

```bash
python main.py
```

启动后进入交互菜单：

```
当前分组: default  |  模式: browser
> 🔑 登录
  🔍 搜索 & 下载
  🔄 更新已下载
  📥 直接下载 (输入 URL)
  退出
```

## 配置

所有配置位于 `app_data/config/`，YAML 格式。

### 主配置 `config.yaml`

```yaml
version: 1.0.0
mode: browser          # browser | api | requests
group: default         # 分组名，影响导出路径
download:
  max_workers: 3       # 并发下载线程数
```

### 站点配置 `sites/fanqie.yaml`

```yaml
# 浏览器模式
browser:
  headless: false
  user_data_dir: ""           # Chrome 用户数据目录（留空则新建）
  timeout: 30
  retry_times: 3
  delay: [3, 5]              # 请求间隔范围（秒）

# API 模式（通过 oiapi.net 第三方 API）
api:
  oiapi:
    enabled: true
    key: ""                   # API 密钥
    batch_size: 3

# Requests 模式（纯 HTTP）
requests:
  headers:
    User-Agent: "Mozilla/5.0 ..."
  cookies: {}
```

### 导出格式配置 `formats/*.yaml`

**TXT：**
```yaml
txt:
  enabled: true
  output_path: "app_data/export/{group}/{file_name_template}"
  file_name_template: "{title}"       # 可用变量: {title} {author} {novel_id} {total_chapters} {date}
  encoding: "utf-8"
  extension: ".txt"
```

**EPUB：**
```yaml
epub:
  enabled: true
  output_path: "app_data/export/{group}/{file_name_template}"
  file_name_template: "{title}"
  extension: ".epub"
  css_style: "default"
  include_toc: true
```

**IMG：**
```yaml
img:
  enabled: true
  output_path: "app_data/export/{group}/img/{file_name_template}"
  file_name_template: "{n}"          # {n} 为图片全局序号，0=封面
  extension: ".jpg"
```

默认导出路径：`app_data/export/{group}/{书名}.txt`（分组为 `default` 时 → `app_data/export/default/`）。

## 命令行参数

支持直接传入 URL 跳过交互菜单：

```bash
python main.py --url https://fanqienovel.com/page/1234567890123456789
```

完整参数：

| 参数 | 说明 |
|------|------|
| `--url` | 小说页面 URL |
| `--mode` | 下载模式（browser / api / requests） |
| `--group` | 分组名 |
| `--threads` | 并发线程数 |
| `--range` | 下载范围，如 `1-100`、`last:50`、`all` |
| `--not-update` | 跳过更新，仅下载新小说 |
| `--headless` | 浏览器无头模式 |
| `--delay` | 请求延迟范围，如 `3-5` |
| `--timeout` | 请求超时（秒） |
| `--save-format` | 导出格式（txt / epub / img） |
| `--save-file-path` | 自定义导出路径 |

## 目录结构

```
novel-downloader/
├── main.py                    # 入口（交互式 CLI）
├── nldlder/                   # 核心库
│   ├── core/
│   │   ├── downloader.py      # NovelDownloader 编排器
│   │   ├── engine.py          # 网络层（Browser / API / Requests）
│   │   ├── options.py         # 配置模型（Builder 模式）
│   │   ├── storage.py         # 持久化存储（JSON）
│   │   ├── progress.py        # 下载进度追踪
│   │   └── exceptions.py      # 异常体系
│   ├── parsers/
│   │   ├── base.py            # 解析器抽象基类
│   │   └── fanqie.py          # 番茄小说解析器（HTML/Browser/API/Requests）
│   ├── exporters/
│   │   ├── base.py            # 导出器抽象基类
│   │   ├── txt.py             # TXT 导出
│   │   ├── epub.py            # EPUB3 导出
│   │   └── img.py             # 图片导出
│   ├── models/
│   │   ├── novel.py           # Novel / Chapter / SearchResult 模型
│   │   └── auth.py            # 认证凭证模型
│   └── utils/
│       ├── logger.py          # 日志模块
│       └── registry.py        # 动态加载解析器/导出器
└── app_data/
    ├── config/                # YAML 配置文件
    │   ├── config.yaml
    │   ├── sites/
    │   └── formats/
    ├── storage/               # 断点续传数据
    │   └── {novel_id}/
    │       ├── meta.json
    │       └── chapters/
    └── export/                # 导出文件
        └── {group}/
```

## 依赖

| 包 | 用途 |
|----|------|
| `DrissionPage` | 浏览器自动化（Browser 模式） |
| `beautifulsoup4` | HTML 解析 |
| `Requests` | HTTP 请求（API / Requests 模式） |
| `rich` | 终端进度条 |

| `pyyaml` | YAML 配置解析 |
| `python-box` | 字典点号访问 |

## License

MIT

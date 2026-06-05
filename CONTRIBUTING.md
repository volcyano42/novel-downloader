# 为 novel-downloader 做贡献

欢迎！本文档帮助快速上手开发。

## 目录

- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [依赖方向](#依赖方向)
- [开发工作流](#开发工作流)
- [测试](#测试)
- [PR 流程](#pr-流程)

---

## 前置条件

- **Python 3.9+** — 运行和开发的基础
- **git** — 版本控制
- **Chromium**（可选）— 浏览器模式需要，`drissionpage` 会自动管理

## 快速开始

```bash
# 克隆
git clone https://github.com/volcyano42/novel-downloader.git
cd novel-downloader

# 安装依赖
pip install -r requirements.txt
```

## 项目结构

```
novel-downloader/
├── main.py                       # CLI 入口（交互式菜单）
├── load_env.py                   # .env 加载工具
├── requirements.txt              # 运行时依赖
│
├── nldlder/                      # 核心库
│   ├── __init__.py               # 公开 API + 版本号
│   │
│   ├── core/                     # 核心功能
│   │   ├── downloader.py         # NovelDownloader 编排器
│   │   ├── engine.py             # 三种下载引擎 (API / Browser / Requests)
│   │   ├── exceptions.py         # 自定义异常体系
│   │   ├── options.py            # 配置数据类 (Options / APIOptions / ...)
│   │   ├── progress.py           # 下载进度追踪
│   │   └── storage.py            # 本地存储管理 (meta + chapters)
│   │
│   ├── models/                   # 纯数据模型（零内部依赖）
│   │   ├── novel.py              # Novel / Chapter / Chapters / Illustration
│   │   └── auth.py               # AuthCredential
│   │
│   ├── parsers/                  # 站点解析器
│   │   ├── base.py               # BaseParser 基类
│   │   ├── fanqie.py             # 番茄小说解析器
│   │   └── qidian.py             # 起点中文网解析器
│   │
│   ├── exporters/                # 格式导出器
│   │   ├── base.py               # BaseExporter 基类
│   │   ├── txt.py                # TXT 导出
│   │   ├── epub.py               # EPUB 导出（含图片优化）
│   │   ├── img.py                # 图片导出
│   │   └── sqlite.py             # SQLite 导出
│   │
│   └── utils/                    # 工具模块
│       ├── logger.py             # 日志系统（LogOptions + configure_logging）
│       └── registry.py           # 插件注册（自动发现 parsers/exporters）
│
├── app_data/                     # 用户数据目录（gitignore 建议忽略）
│   ├── config/
│   │   ├── config.yaml           # 主配置
│   │   ├── sites/                # 各站点配置（fanqie.yaml / qidian.yaml）
│   │   └── formats/              # 导出格式配置（txt.yaml / epub.yaml / ...）
│   ├── storage/                  # 断点续传数据 (JSON)
│   └── exports/                  # 最终导出文件
│
├── tests/
│   ├── conftest.py               # 共享 fixtures
│   ├── test_models.py            # 数据模型测试（51 项）
│   ├── test_options.py           # 配置测试（24 项）
│   └── test_exceptions.py        # 异常测试（23 项）
│
├── .github/workflows/ci.yml      # GitHub CI
├── CONTRIBUTING.md               # 本文件
└── .env                          # 环境变量（不提交到仓库）
```

## 依赖方向

项目遵循 **严格单向依赖**，无循环导入：

```
models/          ← 纯数据类，不依赖项目内任何模块
   ↓
core/exceptions  ← 纯异常定义，零依赖
utils/           ← 工具函数，零内部依赖
   ↓
core/options.py  → utils/logger.py
core/engine.py   → core/exceptions.py, core/options.py
core/progress.py → models/novel.py
core/storage.py  → models/novel.py
   ↓
parsers/         → core/engine.py, core/exceptions.py, models/
exporters/       → core/options.py, models/
   ↓
core/downloader.py  → 汇聚所有下层模块
   ↓
nldlder/__init__.py  → 常用 API
   ↓
main.py
```

**新增模块时**请遵循此方向，勿引入反向依赖。

## 开发工作流

### 1. 配置

```bash
# 复制默认配置
# 按需修改 app_data/config/config.yaml 中的 mode / platform 等
```

### 2. 运行

```bash
python main.py
```

三种模式通过 `config.yaml` 的 `mode` 切换：

| mode | 描述 | 需配置 |
|---|---|---|
| `api` | API 接口（最快） | `sites/fanqie.yaml` 中的 `api.oiapi.key` |
| `browser` | 浏览器模拟（兼容最好） | Chromium 用户数据目录 |
| `requests` | 纯 HTTP（轻量） | 需先登录获取 cookies |

### 3. 调试

```bash
# 控制台日志级别在 config.yaml 的 log.level 中设置
# 日志文件输出到 config.yaml 的 log.output_dir
```

## 测试

```bash
pytest tests/ -v
```

### 添加新测试

在测试之前，请检查pytest是否已经通过pip安装：

测试文件放在 `tests/` 目录，按 `test_{模块名}.py` 命名

### 环境变量

API key 优先从环境变量读取（`{PROVIDER}_API_KEY`），回退到 YAML

也可用 `load_env.py` 从 `.env` 文件加载

```bash
export OIAPI_API_KEY=oiapi-xxxxx
```

### 新解析器

1. 在 `nldlder/parsers/` 下新建文件
2. 继承 `BaseParser`，实现抽象方法
3. 必须有`{Name}Parser`，`registry.py` 发现它并自动注册

### 新导出器

1. 在 `nldlder/exporters/` 下新建文件
2. 继承 `ExportOptions`，设置 `format` 字段，定义 `{Name}ExportOptions` 数据类
3. 定义 `{Name}Exporter` 类（继承 `BaseExporter`，实现 `export()`）
4. `registry.py` 会自动注册
5. 在 `app_data/config/formats/` 下添加对应的 `{name}.yaml`

## PR 流程

1. Fork 仓库，创建功能分支
2. 改动后确保 `pytest tests/ -v` 全部通过
3. CI 自动跑语法检查 + 导入验证 + 测试
4. PR 到 `main` 分支
5. 维护者 review 后合并

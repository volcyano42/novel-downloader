# 为 novel-downloader 做贡献

感谢您对为novel-downloader做出贡献的兴趣！本文档帮助快速上手开发。

## 目录

- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [依赖方向](#依赖方向)
- [测试](#测试)
- [PR 流程](#pr-流程)

---

## 前置条件

- **Python 3.10+** — 运行和开发的基础
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
├── main.py
├── requirements.txt
│
├── novelbase/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── downloader.py         # NovelDownloader
│   │   ├── engine.py             # 三种下载引擎
│   │   ├── exceptions.py
│   │   ├── options.py            # 配置数据类 (Options / APIOptions / ...)
│   │   ├── progress.py           # 下载进度追踪
│   │   └── storage.py            # 本地存储管理 (meta + chapters)
│   │
│   ├── models/                   # 纯数据模型
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
│   │
│   └── utils/                    # 工具模块
│       ├── logger.py             # 日志系统（LogOptions + configure_logging）
│       └── registry.py           # 插件注册（自动发现 parsers/exporters）
│
├── app_data/                     # 用户数据目录
│   ├── config/
│   │   ├── config.yaml           # 主配置
│   │   ├── sites/                # 各站点配置（fanqie.yaml / qidian.yaml）
│   │   └── formats/              # 导出格式配置（txt.yaml / epub.yaml / ...）
│   ├── storage/                  # 断点续传数据
│   └── exports/                  # 最终导出文件
│
├── tests/
│   ├── conftest.py               # 共享 fixtures
│   ├── test_models.py            # 数据模型测试（51 项）
│   ├── test_options.py           # 配置测试（24 项）
│   └── test_exceptions.py        # 异常测试（23 项）
```

## 依赖方向

项目遵循 **严格单向依赖**：

```
models/
   ↓
core/exceptions
utils/
   ↓
core/options.py  → utils/logger.py
core/engine.py   → core/exceptions.py, core/options.py
core/progress.py → models/novel.py
core/storage.py  → models/novel.py
   ↓
parsers/         → core/engine.py, core/exceptions.py, models/
exporters/       → core/options.py, models/
   ↓
core/downloader.py
   ↓
novelbase/__init__.py
   ↓
main.py
```

**新增模块时**请遵循此方向，勿引入反向依赖。

## 测试

```bash
pytest tests/ -v
```

### 添加新测试

在测试之前，请检查pytest是否已经通过pip安装

测试文件放在 `tests/` 目录，按 `test_{模块名}.py` 命名

### 环境变量

API key 优先从环境变量读取（`{PROVIDER}_API_KEY`），回退到 YAML  
例如： `OIAPI_API_KEY=oiapi-xxxxx`  

## 插件

此项目预留了两个接口：sources(数据源)、exporters(导出器)，它们将会被 `registry.py`发现并自动注册，让您轻松满足您的需求。

### 新数据源

1. 在 `novelbase/sources/` 下新建目录 `{name}/`
2. 在 `{name}/__init__.py` 中定义 `NAME`、`HOSTS`、`ID_PATTERN` 常量
3. 按引擎模式创建子目录：`browser/`、`requests/`、`api/`
4. 在每个模式目录下实现函数：`search.py`、`novel_info.py`、`chapter_list.py`、`chapter_content.py`
5. 在 `app_data/config/sites/` 下添加对应的 `{name}.yaml`,模板可以复制其他的

### 新导出器

1. 在 `novelbase/exporters/` 下新建文件
2. 继承 `ExportOptions`，设置 `format` 字段，定义 `{Name}ExportOptions` 数据类
3. 定义 `{Name}Exporter` 类（继承 `BASEExporter`，实现 `export()`）
4. 在 `app_data/config/formats/` 下添加对应的 `{name}.yaml`，模板可以使用

### 新引擎

1. 在`novelbase/core/engine.py`创建类 `{Name}Engine`
2. 继承 `Engine`，实现所有抽象方法
3. 在 `create_engine`的 `mode_map` 字典中，添加字段

## PR 流程

1. Fork 仓库，创建功能分支
2. 改动后确保 `pytest tests/ -v` 全部通过
3. CI 自动跑语法检查 + 导入验证 + 测试
4. PR 到 `main` 分支
5. 维护者 review 后合并

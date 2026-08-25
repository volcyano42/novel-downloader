# 添加书源

## 前置条件

1. 了解 Python 知识，当然您可以使用其他语言，但是最终还是需要 Python 接入并运行
2. 了解项目结构、Engine 公开函数、书源的结构

## 开始前首先了解

1. Engine 译为"引擎"，是获取数据的渠道之一，例如 `requests.get()`。目前有 `BrowserEngine`、`APIEngine`、`RequestsEngine` 三个类，对应三种模式（browser / api / requests）。每个 Engine 提供同步（`fetch_text` / `fetch_json`）与异步（`async_fetch_text` / `async_fetch_json`）两组接口；书源函数中使用异步接口
2. Engine 支持的参数详情请看 `novelbase/core/options.py`
3. 书源函数签名不可改变：程序运行时扫描 `novelbase/sources` 下所有书源和函数，并了解能力（如某种模式/变体是否支持搜索等），`novelbase/source.py` 的 `resolve()` 会通过 `inspect.signature` 校验必需参数名
4. 书源只支持异步函数，不支持同步（见下方"函数签名约定"）

## 创建步骤

### 新建书源脚手架

执行以下指令创建新书源的脚手架：

```bash
python cli.py dev new-source --name {NAME}
```

在 `novelbase/sources/{NAME}/` 下生成 `__init__.py`、`_common.py` 与 `requests/`（默认模式，可用 `--modes` 指定多个）目录，模式目录内含四个函数的 `async def` TODO 模板文件。

> 注意：`new-source` 生成的脚手架在 `{mode}/` 根下直接放函数文件，而运行时按
> `{mode}/{variant}/` 组织（见下），新建书源后需为每个模式补建 variant 子目录。
> 可手动调整；也可先为书源创建站点配置 `app_data/config/sites/{NAME}.yaml`
> （含对应 mode 块），再对**已有书源**使用 `dev new-variant` 生成代码脚手架。
> `new-variant` 只把新变体追加到已存在的站点配置中，不会创建配置本身——新建
> 书源若直接运行 `new-variant` 会因站点配置缺失而报"书源不存在"。

### 为已有书源新建变体

当书源已存在、需要为某个模式新增一种实现时：

```bash
python cli.py dev new-variant --source {NAME} --mode {MODE} --variant {VARIANT}
```

三个参数均必填：

- `--source`：书源名（如 `fanqie`）
- `--mode`：模式（`api` / `browser` / `requests`）
- `--variant`：新变体名（如 `oiapi`）

该命令一次完成两件事（缺一不可，引擎才能工作）：

1. **代码脚手架**：在 `novelbase/sources/{NAME}/{MODE}/{VARIANT}/` 下生成
   `__init__.py` + `search.py` / `novel_info.py` / `chapter_list.py` /
   `chapter_content.py` 四个 `async def` TODO 模板文件
2. **站点配置**：在 `app_data/config/sites/{NAME}.yaml` 的 `{MODE}:` 下新增
   `{VARIANT}:` 配置块（参数复制自该 mode 第一个已有 variant，之后可自行调整）

任一校验失败（书源代码目录/站点配置缺失、mode 不存在、variant 已存在、
该 mode 下无模板 variant）均报错退出，**不产生任何文件**。

## 书源目录结构

```
novelbase/sources/{name}/
├── __init__.py              ← NAME / SHOW_NAME / HOSTS（运行时仅读取这三个字段）
├── _common.py               ← 平台共享逻辑（签名、解析）
├── browser/{variant}/       ← 浏览器模式实现（如 fanqie/browser/default/）
├── requests/{variant}/      ← requests 模式实现（如 fanqie/requests/default/）
└── api/{variant}/           ← API 模式，每个 variant 一个子目录（如 fanqie/api/oiapi/、fanqie/api/rain/）
```

每个 variant 目录内含四个函数文件：

```
{name}/{mode}/{variant}/
├── search.py            ← async def search(...)
├── novel_info.py        ← async def novel_info(...)
├── chapter_list.py      ← async def chapter_list(...)
└── chapter_content.py   ← async def chapter_content(...)
```

- 单 variant 模式用 `default` 作为 variant 名（如 `requests/default/`）
- 某 variant 缺失某个函数文件即表示该变体不支持对应能力

## 函数签名约定

四个函数**必须为 `async def`**，且形参名不可改变（`resolve()` 用
`inspect.signature` 校验 `required_params`）。`novelbase/core/downloader.py`
以 `await fn(...)` 调用书源函数，同步函数会在调用时直接报错。

| 函数 | 签名 | 说明 |
|------|------|------|
| `search` | `async def search(query: str, engine, **kwargs) -> list` | 搜索，返回 `SearchResult` 列表 |
| `novel_info` | `async def novel_info(url: str, engine, **kwargs) -> Novel` | 小说元数据 |
| `chapter_list` | `async def chapter_list(url: str, engine, **kwargs) -> list` | 章节列表 |
| `chapter_content` | `async def chapter_content(chapter, engine, **kwargs) -> Chapter \| None` | 单章正文，失败返回 `None` |

- 前三个函数通过 `engine.async_fetch_text` / `engine.async_fetch_json` 等异步
  接口获取数据；`engine.options` 携带站点配置（如 `key`、`params` 等）
- 返回类型参考 `novelbase/models/novel.py` 与 `novelbase/sources/contracts.py`
- 具体实现可参考现有书源，如 `novelbase/sources/fanqie/api/oiapi/search.py`

## 站点配置

`app_data/config/sites/{NAME}.yaml` 定义书源各模式的运行参数，结构为
`{mode}: {variant}: {参数字段}`：

```yaml
# app_data/config/sites/fanqie.yaml
api:
  oiapi:
    key: ''
    timeout: 30
    retry_times: 3
    backoff_factor: 2
    delay: [3, 5]
    params: {}
  rain:
    ...
browser:
  default:
    browser_type: chromium
    headless: false
    ...
requests:
  default:
    headers: {...}
    ...
```

- `dev new-variant` 会把 `{MODE}:` 下第一个已有 variant 的参数块复制给新 variant
- 参数含义与默认值见 `novelbase/core/options.py` 与 `docs/project/config.md`

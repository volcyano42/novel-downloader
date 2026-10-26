# 配置文件说明

配置目录 `app_data/config/`（首次运行从 `template/config/` 初始化）。

## config.yaml（全局）

```yaml
download:
  max_workers: 3            # 最多同时运行的下载任务数（超额任务排队）
  notify:                   # 完成/未完成通知
    on_complete: true
    on_incomplete: true
    sound: bell
storage:                    # ⚠️ 遗留死配置，见下
  backend: sqlite
  database_url: sqlite:///app_data/storage/novels/.dir
```

- `download.max_workers`：**最多同时运行的下载任务数**（默认 3；后端 `/api/v2/config` 可写）。
  超出的任务以 `status="queued"`（前端显示「排队中」）等待，拿到额度才转「下载中」；
  **不再是「任务内章节并发」**。排队中的任务被暂停**不占任务槽**，`resume` 后才重新抢额度；
  下调该值仅影响之后排队/启动的任务（已在跑的不受影响），最多 1 秒后生效（读取带 1s TTL 缓存）。
- `download.notify`：下载完成/未完成通知。
- **全局 `mode` 已删除**（2026-09-25）：mode 由书源在 `source.json` 里声明；用户层可**顶层覆盖**
  （`sources/{source_name}.yaml` 的顶层 `mode`，见下；2026-10-25 起不再逐能力覆盖）；旧 `config.yaml` 里遗留的 `mode:` 键不再被读取。
- ⚠️ **`storage` 段已不可配置（死配置）**：实现恒取 `shared.config.get_database_url()`
  （= `{APP_DATA}/storage/novels/`），backend 与 CLI 统一，与 `config.yaml` 内容无关。
  修改该段的 `backend` / `database_url` **不生效**；保留仅为兼容旧文件，新配置可省略。

## sources/{source_name}.yaml（逐书源）

文件名是书源的 `source_name`（如 `fanqie-requests-default.yaml`）。配置**三层合并**后生效：

```
系统默认（ENGINE_DEFAULTS[mode]，来自 novelbase/core/options.py 的 dataclass）
  → source.json 顶层字段（书源出厂）
    → sources/{source_name}.yaml 顶层字段（用户层，只写差异）
```

> **2026-10-25 起一个书源只有一个 `mode` 和一套参数**（不再按能力分化）。用户层是**顶层一套字段**，
> 没有 `common` 段，也没有逐能力段。

```yaml
source_group: 番茄         # 顶层元信息：分组名（留空 / 删键 = 未分组，回落出厂）
source_alias: 番茄·直连    # 顶层元信息：显示别名（留空 / 删键 = 回落出厂 / source_name）
concurrency: 1             # 顶层元信息：书源级并发额度（跨任务共享）
mode: requests             # 引擎模式（browser/requests/api）；删键 = 恢复书源声明
timeout: 30                # ↓ 以下为引擎字段，随 mode 而定
retry_times: 3
delay: [0, 0]              # 每请求前随机等待（[0, 0] = 不限速，出厂默认）
backoff_factor: 2
headers: {User-Agent: "..."}
cookies: {}
proxies: {}
```

- **顶层 `source_group` / `source_alias`**：书源的分组名与显示别名；用户层覆盖出厂 `source.json` 的同名字段。
  空串（或删除该键）= 回落出厂值 / `source_name`。读取入口 `shared.config.source_group()` /
  `source_alias()` / `display_name()`。**`enabled` 已废弃**（2026-09-27）：书源不再有启用概念，
  搜索时由用户勾选参与的书源（默认全选），默认参与集 = `shared.config.default_source_names()`。
- **顶层 `concurrency`**：**书源级并发额度**（同一书源同时最多几个请求在飞，**跨任务共享**）；
  用户层顶层覆盖出厂 `source.json` 顶层，缺省 **1**；非正整数忽略回退 1。读取入口
  `shared.config.source_concurrency()`，机制详见 [sources.md](sources.md)。
- **引擎字段**：随**有效 mode** 而定（requests / browser / api 三套，见 [sources.md](sources.md)）。
- **`delay`**：每个请求前的随机等待（`asyncio.sleep(random.uniform(delay))`，语义不变）；
  **出厂默认改为 `[0, 0]`（不设置 = 不限速；旧出厂值为 `[3,5]`）**。生效优先级：
  `dataclass 默认 → source.json 顶层 → 用户层 sources yaml 顶层`。
  ⚠️ **历史写入过 `delay` 的老用户**（旧版曾在 `sites/*.yaml` 落过 `delay: [3,5]`）会因三层合并语义继续以用户层为准，
  如要提速需在设置页把相应书源的 `delay` 调下来或清掉该键。**当前出厂/模板已不再写 `delay`**（只保留 api 源的顶层 `key`），新用户不受影响。
- **用户层覆盖 mode**：顶层 `mode`（合法值 `browser`/`requests`/`api`）优先于 `source.json` 声明；
  写 `null`（或删除该键）= 恢复声明；非法值忽略回退声明。**一个 mode 对四类能力全部生效**。
  唯一入口 `shared.config.effective_capabilities()`；`shared.config.merged_source_config()` 按有效 mode
  取 `ENGINE_DEFAULTS[mode]` 作基底，输出的 `mode` 恒为有效值
  （后端 `PUT /api/v2/config/sources/{name}` 传 `{"mode": null}` 即删除覆盖）。
- 已知限制：不同 mode 的接口/参数互不通用，覆盖后不保证可用。
- **旧 `sites/{platform}.yaml`（`fanqie.yaml` / `qidian.yaml` / `qimao.yaml` / `92xs.yaml`）不迁移**，
  用户需按新书源名重配。

## `library/` —— 书维度账本与搜索历史

两个**运行时账本**（程序写、也能手改），与配置分开放在 `library/` 子目录：

```
app_data/config/library/
├── books.yaml              # 书维度：分组 / 收藏 / 来源 / 书名
└── search_history.jsonl    # 搜索历史（append-only）
```

### books.yaml

key 是 `novel_id`（`sha256(url)[:32]`），默认值一律省略：

```yaml
"037507eea3ae924dc1b506189e6535d9":
  title: 时间循环：我成了杀害青梅的凶手
  groups:
    default: {}
  favorite: true
  favorited_at: "2026-09-20 10:00:00"
  source: fanqie-api-rain

"680fced7a0cef16dc19f37b1c191d75b":
  groups:
    TEST:
      pending_export: true
    default: {}
```

| 字段 | 缺省含义 |
|---|---|
| `title` | 未知书名 |
| `groups` | 不属于任何组；**一本书可属多个组** |
| `groups.<组名>.pending_export` | `false`（**组级**属性，不是书级） |
| `favorite` | 未收藏 |
| `favorited_at` | 未知收藏时间 |
| `source` | 未知来源 |

要点：

- `title` 是**派生字段**：每次 `set_novel_source()`（下载 / 同步路径必经）从
  `storage/novels/<id>.db` 的 `meta.title` 同步，**手改会被覆盖**
- `groups` 是 **dict 不是列表** —— `pending_export` 属于 `(组, 书)` 这一对
- **未知字段原样保留**：你可以自己加 `note:` 之类的备注字段，程序不会吃掉它
- 写入走「临时文件 + fsync + `os.replace`」，写前把上一版留成 `books.yaml.bak`
- **YAML 写坏（语法错 / 顶层不是映射）时程序报错而不会覆盖**：书架接口会报错，
  错误信息带文件路径。修好文件或从 `.bak` 恢复即可 —— 程序绝不会用空数据盖掉它
- 注释会被抹掉（PyYAML 不保留），但文件头注释每次重写都会重新注入

### search_history.jsonl

一行一条，只追加：

```jsonl
{"id": 1, "source_name": "fanqie-requests-default", "keyword": "斗罗", "searched_at": "2026-10-25 19:31:02"}
```

- 写入 O(1)，不需要读-改-写整个文件
- 读取时按 `(source_name, keyword)` 去重保留最新，再按时间倒序（字符串序 = 时间序）
- 超过 **250** 行自动压缩到最近 **200** 行
- 由程序维护；**手改请保证每行有整数 `id`**，否则该行会被跳过

### 已知边界

- 并发保护是**进程内** `threading.Lock`（backend 单进程，`uvicorn.run(app)` 无
  workers）。backend 与 `cli.py` 同时写会后者覆盖前者 —— 单人项目接受这个代价
- `app_data/storage/` 下只剩 `novels/`（每本书一个 `<id>.db`）
- 从旧版升级：`python scripts/migrate_user_data.py`（默认 dry-run，`--apply` 才写）

## formats/*.yaml

导出格式配置（`txt` / `epub` / `img`），顶层以格式名包裹一段配置。

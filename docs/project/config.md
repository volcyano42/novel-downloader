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
- **全局 `mode` 已删除**（2026-09-25）：mode **默认**由书源在 `source.json` 里声明，用户可**逐能力覆盖**
  （`sites/{source_name}.yaml` 的 `{cap}.mode`，见下）；旧 `config.yaml` 里遗留的 `mode:` 键不再被读取。
- ⚠️ **`storage` 段已不可配置（死配置）**：实现恒取 `shared.config.get_database_url()`
  （= `{APP_DATA}/storage/novels/`），backend 与 CLI 统一，与 `config.yaml` 内容无关。
  修改该段的 `backend` / `database_url` **不生效**；保留仅为兼容旧文件，新配置可省略。

## sites/{source_name}.yaml（逐书源）

文件名是书源的 `source_name`（如 `fanqie-requests-default.yaml`）。配置**三层合并**后生效：

```
系统默认（ENGINE_DEFAULTS[mode]，来自 novelbase/core/options.py 的 dataclass）
  → source.json 的 default_config（书源出厂，已合并 common）
    → sites/{source_name}.yaml（用户层，只写差异）
```

```yaml
enabled: true              # 顶层：启用状态，覆盖 source.json 的出厂值
concurrency: 1             # 顶层：书源级并发额度（同一书源同时最多几个请求在飞，跨任务共享）
search:                    # 逐能力段：search / novel_info / chapter_list / chapter_content
  mode: requests           # 逐能力覆盖：合法值 browser/requests/api；不写则继承声明；null = 恢复声明
  timeout: 30
  retry_times: 3
  delay: [0, 0]            # 每请求前随机等待（[0, 0] = 不限速，出厂默认）
  backoff_factor: 2
  headers: {User-Agent: "..."}
  cookies: {}
  proxies: {}
# novel_info / chapter_list / chapter_content 同上
```

- **顶层 `enabled`**：覆盖出厂启用状态（`shared.config.is_source_enabled`）。
  书源是否「启用」= 读 `sites/{source_name}.yaml` 顶层 `enabled`，无则回落到 `source.json.enabled`。
- **顶层 `concurrency`**：**书源级并发额度**（同一书源同时最多几个请求在飞，**跨任务共享**）；
  用户层顶层覆盖出厂 `source.json` 顶层，缺省 **1**；非正整数忽略回退 1。读取入口
  `shared.config.source_concurrency()`，机制详见 [sources.md](sources.md)。
- **逐能力 `delay`**：每个请求前的随机等待（`asyncio.sleep(random.uniform(delay))`，语义不变）；
  **出厂默认改为 `[0, 0]`（不设置 = 不限速；旧出厂值为 `[3,5]`）**。生效优先级：
  `dataclass 默认 → source.json 的 common → 能力段自身 → 用户层 sites yaml`。
  ⚠️ **历史写入过 `delay` 的老用户**（旧版曾在 `sites/*.yaml` 落过 `delay: [3,5]`）会因三层合并语义继续以用户层为准，
  如要提速需在设置页把相应书源的 `delay` 调下来或清掉该键。**当前出厂/模板已不再写 `delay`**（只保留 `enabled` / api 源的能力段 `key`），新用户不受影响。
- **逐能力段**：字段随该能力的**有效 mode** 而定（requests / browser / api 三套，见 [sources.md](sources.md)）。
- **用户层可逐能力覆盖 mode**：`{cap}.mode`（合法值 `browser`/`requests`/`api`）优先于 `source.json` 声明；
  写 `null`（或删除该键）= 恢复声明；非法值忽略回退声明。唯一入口 `shared.config.effective_capabilities()`；
  `shared.config.merged_source_config()` 按有效 mode 取 `ENGINE_DEFAULTS[mode]` 作基底，输出的 `mode` 恒为有效值
  （后端 `PUT /api/v2/config/sources/{name}` 传 `config[cap].mode = null` 即删除覆盖）。
- 已知限制：不同 mode 的接口/参数互不通用，覆盖后不保证可用。
- **旧 `sites/{platform}.yaml`（`fanqie.yaml` / `qidian.yaml` / `qimao.yaml` / `92xs.yaml`）不迁移**，
  用户需按新书源名重配。

## groups.yaml / 收藏

分组与收藏已迁移到 SQLite（`app_data/storage/users/.../user_data.db`）：
`shared.user_data` 提供读写，后端 `/api/v2/config/groups`、`/api/v2/config/favorites` 暴露。
`groups.yaml` 为遗留文件，不再作为分组数据源。

## formats/*.yaml

导出格式配置（`txt` / `epub` / `img`），顶层以格式名包裹一段配置。

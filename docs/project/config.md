# 配置文件说明

配置目录 `app_data/config/`（首次运行从 `template/config/` 初始化）。

## config.yaml（全局）

```yaml
download:
  max_workers: 3            # 下载并发数
  notify:                   # 完成/未完成通知
    on_complete: true
    on_incomplete: true
    sound: bell
storage:                    # ⚠️ 遗留死配置，见下
  backend: sqlite
  database_url: sqlite:///app_data/storage/novels/.dir
```

- `download.max_workers`：下载并发数（后端 `/api/v2/config` 可写）。
- `download.notify`：下载完成/未完成通知。
- **全局 `mode` 已删除**（2026-09-25）：mode 由书源自己在 `source.json` 里声明，
  用户不再选；旧 `config.yaml` 里遗留的 `mode:` 键不再被读取。
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
search:                    # 逐能力段：search / novel_info / chapter_list / chapter_content
  mode: requests           # 用户层的 mode 键被忽略——mode 恒取书源声明
  timeout: 30
  retry_times: 3
  delay: [3, 5]
  backoff_factor: 2
  headers: {User-Agent: "..."}
  cookies: {}
  proxies: {}
# novel_info / chapter_list / chapter_content 同上
```

- **顶层 `enabled`**：覆盖出厂启用状态（`shared.config.is_source_enabled`）。
  书源是否「启用」= 读 `sites/{source_name}.yaml` 顶层 `enabled`，无则回落到 `source.json.enabled`。
- **逐能力段**：字段随该能力的 mode 而定（requests / browser / api 三套，见 [sources.md](sources.md)）。
- 用户层**不决定 mode**：合并前会从用户层段剔除 `mode` 键，mode 恒取书源声明
  （`shared.config.merged_source_config()`）。
- **旧 `sites/{platform}.yaml`（`fanqie.yaml` / `qidian.yaml` / `qimao.yaml` / `92xs.yaml`）不迁移**，
  用户需按新书源名重配。

## groups.yaml / 收藏

分组与收藏已迁移到 SQLite（`app_data/storage/users/.../user_data.db`）：
`shared.user_data` 提供读写，后端 `/api/v2/config/groups`、`/api/v2/config/favorites` 暴露。
`groups.yaml` 为遗留文件，不再作为分组数据源。

## formats/*.yaml

导出格式配置（`txt` / `epub` / `img`），顶层以格式名包裹一段配置。

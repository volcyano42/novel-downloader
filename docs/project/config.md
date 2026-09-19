# 配置文件说明

## config.yaml

```yaml
download.max_workers: 3     # 下载并发数
download.notify.on_complete: true
mode: api                   # 默认下载模式
storage.backend: sqlite
storage.database_url: sqlite:///app_data/storage/novels.db
export.formats: [epub]
```

## sites/*.yaml

每个平台三个引擎段的配置（api/browser/requests）。api 为 variant 容器（如 `api.oiapi`/`api.rain`）；
browser/requests 也嵌套一层 variant（当前唯一 `default`，如 `browser.default.headless`）。
字段含 delay、retry_times、timeout、backoff_factor。fanqie 的 `api.oiapi.enabled` 设为 false。

## groups.yaml

分组管理，格式 `{group_name: {novel_id: {}}}`，当前为空：`default: {}`。

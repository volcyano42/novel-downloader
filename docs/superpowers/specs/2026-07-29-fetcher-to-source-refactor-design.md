# 删除 Fetcher 中间类 + 重构为 source 驱动架构

## 动机

当前 fetcher 体系有三层：

```
downloader.search() → FanqieFetcher.fetch_search_result() → _use_fetcher() → fanqie/browser/search.py::search()
```

中间的 `FanqieFetcher` / `QidianFetcher` / `QimaoFetcher` 只做一件事：根据 engine 类型 dispatch 到底层函数。`registry.py` 已有的 `capabilities()` + `resolve()` 可以完全替代这一层。

同时删除 JSON 声明式书源（`json_loader.py` + `JsonSourceFetcher`），它是旧设计的遗留，和新体系不兼容。

## 目标

1. 删除三个 `*Fetcher` 中间类，下载逻辑直接用 `registry.resolve()` 调用底层函数
2. `capabilities()` 返回每个 mode/provider 支持的功能列表
3. 统一命名：`fetcher` → `source`，`fetch_*` → `resolve_*`，底层函数名对齐 capabilities
4. 新增 `GET /api/v2/sources` 路由，重构现有路由使用新体系
5. 删除 JSON 书源体系

## 数据结构

### capabilities() 新返回格式

```python
# fanqie 示例
{
  "api": {
    "oiapi": ["search", "novel_info", "chapter_list", "chapter_content"],
    "rain":  ["search", "novel_info", "chapter_list", "chapter_content"]
  },
  "browser": ["search", "novel_info", "chapter_list", "chapter_content", "login"],
  "requests": ["search", "novel_info", "chapter_list", "chapter_content"]
}
```

- 多 provider 的 mode（api）→ `{provider: [functions]}`
- 单 provider 的 mode（browser/requests）→ `[functions]`
- 功能名：`search`、`novel_info`、`chapter_list`、`chapter_content`、`login`

### GET /api/v2/sources 响应格式

```json
{
  "ok": true,
  "data": {
    "fanqie": {
      "hosts": ["fanqienovel.com", "changdunovel.com"],
      "id_pattern": "^(?:book_id=?)?(\\d{19})$",
      "capabilities": {
        "api": {"oiapi": ["search", "novel_info", "chapter_list", "chapter_content"], "rain": [...]},
        "browser": ["search", "novel_info", "chapter_list", "chapter_content", "login"],
        "requests": ["search", "novel_info", "chapter_list", "chapter_content"]
      }
    }
  }
}
```

## 重命名表

| 旧名 | 新名 | 位置 |
|------|------|------|
| `get_fetcher_for_url` | `get_source` | `downloader.py` |
| `get_fetcher_for_id` | `get_source_for_id` | `downloader.py` |
| `get_fetchers` | `list_sources` | `downloader.py` |
| `register_fetcher` | `register_source` | `registry.py` |
| `FetcherNotFoundError` | `SourceNotFoundError` | `exceptions.py` |
| `fetch_meta` | `resolve_meta` | `downloader.py` |
| `fetch_chapter_list` | `resolve_chapter_list` | `downloader.py` |
| `fetch_novel` → `novel_info` | 底层函数对齐 | `fetchers/*/{mode}/` |
| `fetch_chapter_list` → `chapter_list` | 底层函数对齐 | `fetchers/*/{mode}/` |
| `fetch_chapter` → `chapter_content` | 底层函数对齐 | `fetchers/*/{mode}/` |

## 架构变更

### 删除前（三层）

```
downloader.search("fanqie", query, engine)
  → FanqieFetcher.fetch_search_result(query, engine)
    → _use_fetcher(engine)
      → fanqie/browser/search.py::search(query, engine)
```

### 删除后（两层）

```
downloader.search("fanqie", query, engine)
  → registry.resolve("fanqie", engine.mode, "search", provider=engine.api_name)
  → fanqie/browser/search.py::search(query, engine)
```

`downloader.py` 的便捷函数保留 API 不变，内部改用 `registry.resolve()`。路由层不感知变化。

### Source 元数据

每个 `fetchers/{name}/__init__.py` 保留模块级常量替代原来的类属性：

```python
NAME = "fanqie"
HOSTS = ("fanqienovel.com", "changdunovel.com")
ID_PATTERN = re.compile(r"^(?:book_id=?)?(\d{19})$")
```

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 删除类 + 保留常量 | `novelbase/fetchers/fanqie/__init__.py` |
| 删除类 + 保留常量 | `novelbase/fetchers/qidian/__init__.py` |
| 删除类 + 保留常量 | `novelbase/fetchers/qimao/__init__.py` |
| 重命名底层函数 | `novelbase/fetchers/*/{mode}/{provider}/` 下 `fetch_novel.py → novel_info.py` 等 |
| 重命名 + 重构 | `novelbase/core/downloader.py` |
| 重命名 + 扩展 capabilities | `novelbase/utils/registry.py` |
| 重命名异常 | `novelbase/core/exceptions.py` |
| 新增+重构路由 | `services/backend/routers/download.py` |
| 🗑️ 删除 | `novelbase/utils/json_loader.py` |
| 🗑️ 删除 | `app_data/sources/` |
| 清理引用 | `cli.py` |
| 更新导出 | `novelbase/__init__.py` |
| 更新引用 | `app/core.py`, `app/ui.py`, `services/backend/services/task_manager.py` |
| 更新测试 | `tests/test_downloader.py` |
| 更新文档 | `docs/session-prompt.md` |

## 测试

- `tests/test_downloader.py`：更新 mock 调用，`get_fetcher_for_id` → `get_source_for_id` 等
- 运行全量测试确认无回归

## 不在范围内

- 不改变 API v2 响应格式
- 不改变前端
- 不改变 SS E/存储/导出/配置体系

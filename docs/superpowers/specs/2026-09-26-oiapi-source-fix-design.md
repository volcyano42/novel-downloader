# oiapi 书源修复 + 选源列表标注未启用 —— 设计

> 2026-09-26。修复 `fanqie-api-oiapi` 与实际 API 契约不符的三处实现；并在「换源 / 选源」列表里标注未启用的书源。

## 背景

用户贴出后端日志：下载某书时 `fetch_meta failed`、`fanqie_api_oiapi/novel_info.py:35 raise NovelNotFoundError()`，而该书的来源记录正是 `fanqie-api-oiapi`（一个出厂 `enabled: false` 的源）。

实测（见下表）表明**该源的实现与实际 API 契约多处不符**（`search` 与 `chapter_list` 经复核原本正确）：`novel_info` 用错 method、`chapter_content` 在错误结构上取值。因此它「取不到 meta / 拉不到目录 / 拿不到正文」，只是被 `task_manager` 的容错吞成了 warning（章节能入库是历史用其它源下的）。

顺带暴露一个既有 UX 缺口：**「换源」弹窗列出的是全部书源（含 `enabled: false`）**，用户因此把这本书换到了这个坏源上——下载任务不检查 `enabled`，于是一路失败。

## 实测 API 契约（2026-09-26，`https://oiapi.net/api/FqRead`，POST form + `key`/`type=json`）

| 能力 | 请求 | 成功响应 |
|---|---|---|
| `search` | `method=search` + `keyword` + `page` | `code=1`，`data` = `list[dict]`，字段 `thumb/id/title/author/serial/word_number/read_count/docs/tags` |
| `novel_info` | `method=**ids**` + `id` | `code=1`，`data` = `dict{thumb,id,title,author,serial,word_number,read_count,docs}` |
| `chapter_list` | `method=chapters` + `id` | `code=1`，`data` = **分卷嵌套 `list[list[dict]]`**（8 卷 / 718 章），叶节点字段 `chapter_id/title/index/volume/volume_name/time/pay` |
| `chapter_content` | `method=chapter` + `id` + `chapter`(=order) | `code=1`，`data` = **`list`**（首项含 `content`/`word_number`/`chapter_id`/`chapter_title`/`volume_name`…）；`message` 另有「标题+正文」纯文本 |

- 未知 method（如 `detail`/`list`/`info`）→ `code=-5`，`message="default method: search, ids, chapter"`
- 章节越界 → `code=-3`，`message="请检测章节选择是否正确"`
- 频控异常（既有特判保留）→ `message` 含 `实例化失败：Trying to access array offset on value of type bool line 197 in api.php`

## 现状对照（哪些是错的）

| 文件 | 现状 | 问题 |
|---|---|---|
| `search.py` | `method=search` + `keyword`，读 `data[]` 的 `id/title/author/docs/thumb` | ✅ 正确，不动 |
| `novel_info.py:28` | `method="detail"` | ✗ 应为 `ids` |
| `novel_info.py:39` | `data.get('cover')` | ✗ 应为 `thumb` |
| `novel_info.py:48-56` | 再调 `chapters` 并 `sum(len(vol) for vol in data)` 求 serial | △ 求和结果其实正确（`data` 是分卷嵌套），但多一次请求；`ids` 已直接返回 `serial`，改为直接取 |
| `chapter_list.py:30-32` | `for chapter_items in data: for item in chapter_items:`（分卷嵌套） | ✅ **原本正确**（初稿误判；实现改为兼容两种形态） |
| `chapter_content.py:38-42` | `data_list.values() if isinstance(data_list, dict)` | ✗ `data` 是 `list` → 循环为空 → `content` 从未被赋值 |

## 目标

1. `fanqie-api-oiapi` 的 4 个能力都按实测契约工作（真实 API 逐能力验证通过）
2. 「换源」与「URL 直达选源」列表里，`enabled: false` 的源标注「未启用」
3. 用单测（mock 实测响应结构）把契约钉住，避免再次悄悄坏掉

## 非目标

- 不改其它书源
- 不改下载/并发/来源记录逻辑
- 不改该源的出厂 `enabled: false`（它仍是需要自己配 key 的第三方 API 源）
- 不为该源加「自动重试/退避」等新能力
- 不做「检测书源可用性」的通用机制（本次只修这一处 + 标注）

## 设计

### 1. 源实现修复（`novelbase/sources/fanqie_api_oiapi/`）

**`novel_info.py`**
```python
post_data = {"id": novel_id, "key": engine.options.key, "method": "ids", "type": "json"}
json_data = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)
data = json_data.get("data")
if not data or json_data.get("code") not in (1, "1"):
    raise NovelNotFoundError()

url = f"https://fanqienovel.com/page/{data.get('id')}"
book_cover_url = data.get("thumb")                       # 原为 'cover'
...
serial = int(data.get("serial") or 0)                    # 直接取，删掉二次 chapters 请求
count  = int(data.get("word_number") or 0)
description = data.get("docs")
```
（保留原有的 `Novel(url=..., id=f"fanqie_{novel_id}", ...)` 形态 —— **注意 `id` 前缀不可改**：`tests/test_novel_id_stability.py` 对书源 URL 做 AST 快照，且已有书籍 id 不能漂移。）

**`chapter_list.py`**：保持分卷嵌套解析（实测契约如此），并兼容扁平形态

```python
data = json_data.get("data")
if not data:
    raise ChapterNotFoundError("OIAPI returned empty chapter list")
for group in data:                                  # 真实是 list[list[dict]]
    items = group if isinstance(group, list) else [group]
    for item in items:
        chapter_id = item.get("chapter_id")
        ...
        order = item["index"]; time = item["time"]; volume = item["volume_name"]
```

**`chapter_content.py`**：按 `list` 解析
```python
data_list = response.get("data")
if not data_list:
    message = response.get("message", "")
    if message == "请检测章节选择是否正确":
        raise ChapterNotFoundError(message=f"Invalid chapter order: {chapter.order}")
    elif "Trying to access array offset" in message:      # 频控特判（保留）
        raise AntiCrawlError("OIAPI request frequency too high, PHP backend rejected")
    else:
        raise ChapterNotFoundError(message=f"OIAPI unexpected response: {message}")

first = data_list[0] if isinstance(data_list, list) else next(iter(data_list.values()), {})
chapter.content = (first.get("content") or "").replace(f"{first.get('chapter_title','')}\n\n", "")
chapter.count = int(first.get("word_number") or 0)
```
（`message` 里也有正文，可作为 `content` 为空时的兜底——实现者自行判断是否加。）

### 2. 前端：选源列表标注「未启用」

- `frontend/src/features/detail/SourcePickerDialog.tsx`（换源弹窗）：把 `sources: string[]` 改为可拿到 `enabled` 的数据（如 `{name, enabled}[]`，或额外传入 `enabledNames: Set<string>`）；`enabled === false` 的源在名字后加灰色小字/小片「未启用」（沿用既有小字风格 `text-[10px] text-slate-400`）
- `frontend/src/features/bookshelf/SearchBar.tsx`（URL 直达的选源下拉）：同样标注（`Select` 的选项 label 加后缀，如 `fanqie-api-oiapi（未启用）`）
- 数据来源：`useSources()` 已返回 `{source_name: {capabilities, enabled}}`
- **仍可选**（不禁用），只做提示

## 错误处理

- `novel_info`：`code != 1` 或 `data` 为空 → `NovelNotFoundError`（沿用既有异常语义）
- `chapter_list`：`data` 为空 → `ChapterNotFoundError`
- `chapter_content`：改判 `data` 为空/非预期，保留两条既有特判；越界（`code=-3` + `请检测章节选择是否正确`）→ `ChapterNotFoundError`
- 响应结构再变时：单测会红（见下）

## 测试

- `tests/`（新增或并入既有源测试文件）：用 **mock 的 `engine.async_fetch_json`** 返回上表实测结构，断言：
  - `novel_info`：`title/author/count/description` 映射正确，`serial` 取自 `ids` 的 `serial`，封面取自 `thumb`，且**不再发起第二次 `chapters` 请求**（可断言调用次数）
  - `chapter_list`：分卷嵌套能解析出 N 章（另有扁平形态兼容用例），`order/index`、`volume_name`、`chapter_id → url` 正确
  - `chapter_content`：`data` 为 `list` 时能取到 `content` 与 `word_number`；越界 message → `ChapterNotFoundError`
- **真实 API 验收**（写入报告）：用本机用户层的 key，依次跑 `novel_info` / `chapter_list` / `chapter_content`（取某一章），打印成功结果（标题、章节数、正文字数）；失败则报告实际响应
- 既有测试：`python -m pytest tests -q` 基线 **471 passed, 1 skipped** → 0 failed
- 前端：`npx tsc -b` 0 错、`npm run lint` 无新增告警

## 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 第三方 API 契约再变 | oiapi.net 非本项目控制，字段/方法可能再次调整 | 单测钉住实测结构；源实现注释里记录「契约实测日期」；坏掉时症状是 `NovelNotFoundError`/`ChapterNotFoundError`，日志可辨 |
| 该源是别人维护的服务 | key 有效性、额度、可用性都不由本项目保证 | 保持出厂 `enabled: false`；文档说明需自备 key |
| 前端「未启用」标注被误读为不可用 | 实际上仍可选（下载不检查 enabled） | 文案用「未启用」（不是「不可用」），并在 tooltip/说明里点明 |

## 验收（手工）

1. 详情页「换源」弹窗：`fanqie-api-oiapi` 等禁用源后面显示「未启用」
2. 换到 `fanqie-api-oiapi` 后下载同一本书：「检查更新」能拉到目录、章节能下正文（此前会失败）
3. 该书来源仍是 `fanqie-api-oiapi` 时点「检查更新」不再报 `NovelNotFoundError`

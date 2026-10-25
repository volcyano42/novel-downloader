# 终端对终端小说数据同步 — 设计文档

> 日期：2026-10-14 ｜ **修订：2026-10-25（第 5 稿，最终）** ｜ 状态：待 review
> 定位：局域网内两台运行本项目的终端，由 **CLI** 触发，从对端拉取缺失的书籍数据。
> 原则：**不新增 `/sync` 层**——直接用现有 `/api/v2/storage/*`，只按同步需要给它加参数与字段。不做鉴权（个人项目、仅局域网）。

## 0. 修订记录

2026-10-25 经过六轮讨论定稿。**前几稿的 `/sync/*` 数据面整个删除**——它和 storage 做的是同一件事，属于重复造轮子。

### `/sync` 层为什么被删

每一稿保住它的理由，都依赖一个本可以解除的约束：

| 曾经的理由 | 现在为什么不成立 |
|---|---|
| 「storage 的 `ChapterBrief` 没有 `time`，判定冲突需要它」 | **给它加 `time` 字段**即可（1 行 + 1 处赋值） |
| 「storage 的 GET 总是带封面 base64，太占带宽」 | **加 `include_images=false` 参数**即可 |
| 「`iter_chapters` 会把整本正文读进内存」 | **加 `include_content` 参数**即可 |
| 「storage 侧完全不变」 | 该约束已解除（2026-10-25 决定允许改 storage） |

三条都能用"给现有接口加参数/字段"解决，且**天然向后兼容**（默认值保持现有行为）。于是 `/sync` router、`/sync/*` 端点、sync 专用数据结构、`sync` 配置段**全部不需要**。

### 已被推翻的前稿决定（不要按旧稿实现）

| 旧稿说法 | 现状 |
|---|---|
| 新增 `backend/routers/sync.py`，`/api/v2/sync/*` 四个端点 | **删除**，直接复用 `/api/v2/storage/*` |
| sync 侧自定义 `ChapterBrief`（带 `time`、砍掉 `url`/`image_count`） | **删除**，改为给 storage 的 `ChapterBrief` 加 `time` |
| `sync` 配置段（`include_images` / `page_size`） | **删除**，走 CLI 参数 |
| 配对握手、`Bearer` token、`AuthMiddleware`、`sync.enabled`、分级只读、cookie 登录 | **全部删除**，不做任何访问控制（§7） |

## 1. 背景与目标

多设备用户希望把「已下载的书」在几台机器之间搬一次，而不是各自重新下载。项目数据全在本地 SQLite（`docs/planning/roadmap.md` §F4 明确「云端同步：建议不做」）。本设计走**局域网 P2P**：无账号、无云中转、点对点直连，不触碰 F4 的结论。

**真正驱动这个功能的场景**：某些章节只有某一台能拿到——番茄的登录门槛章（`isChapterLock=true`）需真机扫码登录的登录态，源站下架、限速同理。那台拿到内容的机器，是唯一能补齐另一台的来源。

### 同步对象

| 数据 | 是否同步 | 说明 |
|---|---|---|
| `meta`（书名/作者/简介/封面/`serial`） | ✅ | 每本书一个 `.db` |
| `chapters`（正文） | ✅ | 增量主体 |
| `novel_sources`（来源映射） | ✅ | 随书单一起给（`source_name` 已在 `GET /storage/novel` 返回里）；不同步会导致换源/更新时报"未知书源" |
| `illustrations`（插图） | ⚙️ 可选，**默认不传** | 体积可达 GB 级，CLI 开关控制 |
| `groups` / `favorites` / `search_history` / `bookmarks` | ❌ | 跨设备一致性另有冲突语义 |
| 阅读进度 | ❌ | **项目当前没有这个功能**（`progress` 仅存在于下载任务进度条），要做是独立工作 |

### 非目标

云端中转 / 公网穿透 / 账号体系 / **任何形式的鉴权与访问控制** / TLS / push 与 both / 「以对方为准覆盖」/ 自动定时同步 / 删除传播 / 内容自愈。

## 2. 对 storage 的改动（本设计的全部后端改动）

全部是**加参数 / 加字段**，默认值保持现有行为，前端零改动。

| # | 位置 | 改动 | 向后兼容性 |
|---|---|---|---|
| **M1** | `backend/schemas/storage.py:54-63` | `ChapterBrief` 加 `time: float \| None = None` | 新字段，前端忽略即可 |
| **M2** | `backend/routers/storage.py:70-74` | `_chapter_to_brief(ch, *, downloaded: bool)` 增加 `time=ch.time`，`downloaded` 改由调用方传入 | 见下方「M2 的必要性」 |
| **M3** | `backend/routers/storage.py:90-107` `GET /novel` | 加 `include_images: bool = Query(True)`；为 `False` 时 `cover` 返回 `None` | 默认 `True`，前端不变 |
| **M4** | `backend/routers/storage.py:117-121` `GET /novel/{id}/meta` | 同上（`_novel_to_meta` 加 `include_images` 参数） | 默认 `True` |
| **M5** | `backend/routers/storage.py:160-171` `GET /novel/{id}/chapters` | 加 `include_images`、`include_content`（均默认 `True`）；`downloaded` 改由 `list_downloaded_ids()` 判定 | 默认 `True`，返回值与现在一致 |
| **M6** | `backend/routers/storage.py:194-198` `GET /novel/{id}/chapter/{cid}` | 加 `include_images: bool = Query(True)`；为 `False` 时 `images=[]` | 默认 `True` |
| **M7** | `novelbase/core/storage.py:111-114`（`BaseStorage`）、`:233`（`LocalStorage`）、`:517`（`SQLiteStorage`）、`:231,515`（`load_chapters` 转发） | `iter_chapters` / `load_chapters` 加 `include_content: bool = True` | 默认 `True`，6 个现有调用点行为不变 |

**M7 实现要点**：`SQLiteStorage.iter_chapters` 在 `include_content=False` 时把 SELECT 的 content 位置换成 `NULL`，**8 列位置不变** → `_row_to_chapter`（`storage.py:531-540`）无需改动，因为 `Chapter.content` 本就是 `str | None`。`LocalStorage` 读 JSON 后剥掉 `content`（与它现有剥 `images` 的写法一致）。

### M2 的必要性（不是可选项）

现有 `_chapter_to_brief` 用 `downloaded=ch.content is not None`。一旦 `include_content=False`，`content` 恒为 `None` → **`downloaded` 恒为 `False`**，同步的差集会把远端所有章节都当成"未下载"，行为完全错误。

因此 `list_chapters` 改为：

```python
downloaded_ids = store.list_downloaded_ids(novel_id)   # SELECT id … WHERE content IS NOT NULL AND content != ''
result = [_chapter_to_brief(ch, downloaded=ch.id in downloaded_ids) for ch in chapters]
```

**一个极窄的行为变化**：内容为空字符串 `""` 的章节，原来算 `downloaded=True`（`"" is not None`），现在算 `False`。新语义与 `list_downloaded_ids`（断点续传用）一致，也更正确。**前端目前没有依赖这个边界**。

### 带宽效果

| 调用 | 效果 |
|---|---|
| `GET /storage/novel?include_images=false` | 不返回封面 base64（原本几百本书可达几十 MB） |
| `GET /storage/novel/{id}/chapters?include_images=false&include_content=false&size=20000` | 不读正文、不读插图，只回 brief |
| `GET /storage/novel/{id}/chapter/{cid}?include_images=false` | 正文不带插图 |

`size` 上限是 20000（`storage.py:162` 的 `le=20000`），对任何实际的书都够，**同步一次取完，不分页**。原因：单条 brief ≈ 150–180 字节，3000 章 ≈ 500KB，百兆局域网 ≈ 0.04 秒；而同一本书的正文是 15MB 量级。storage 的分页是为**前端渲染**服务的（一次渲染几千个 DOM 会卡），CLI 没有这个约束。

## 3. 同步算法

### 3.1 调用链

```
[本机 CLI]                                          [对端 /api/v2/storage/*]
  GET /storage/novel?include_images=false           → 书单（含 source_name，无封面）
  对比本地 iter_metas() → 按 novel_id 分类：远端独有 / 双方都有 / 本地独有(忽略)
  for 每本要同步的书：
    GET /storage/novel/{id}/chapters?include_images=false&include_content=false&size=20000
    ◄──────── [ChapterBrief: id,title,order,volume,count,time,downloaded, …]
    本地 list_downloaded_ids(novel_id) → 差集 → 待拉章节 id
    若本地没有这本书：
      GET /storage/novel/{id}/meta?include_images=…   → save_meta() 建库
      来源取书单的 source_name                         → set_novel_source()
    for cid in 差集（串行，分批）：
      GET /storage/novel/{id}/chapter/{cid}?include_images=…
      ◄──────── ChapterData ──────────────────────────
      save_chapter(novel, ch)                        ← 进程内，不走 HTTP
  打印报告
```

本机写入是进程内调用（`save_meta` / `save_chapter` / `set_novel_source`），与下载任务落库同一条代码路径。`save_chapter(novel, chapters)` 只用 `novel.id`（`storage.py:488`），传 `store.load_meta(id)` 即可；CLI 侧已有现成的 `_get_storage()`（`cli/core.py:46-55`）。

**注意**：`ChapterData.images[].raw_data` 可能为 `None`（`storage.py:80`），而 `Illustration.image_format` 会对 `None` 调 `startswith` 崩溃 → 重建 `Chapter` 时**必须跳过 `raw_data` 为空的插图**。

### 3.2 增量判定

- **书级**：按 `meta.id`（= `sha256(url)[:32]`，`novelbase/utils/urls.py:17`）匹配
- **章节级**：远端 `downloaded == true` 的 id 集合 − 本地 `list_downloaded_ids(novel_id)`（`storage.py:575`）= 待拉章节
- **两侧都有正文**：比 `(time, count)`
  - 相同 → 跳过
  - 不同 → **保留本地**，计入报告（"N 章两侧不同，已保留本地"）
- **不做全文比对**：内容不参与判定，只比 id 与 `(time, count)`

### 3.3 `order` 兼容性校验

章节 id 是同一空间，按 id 匹配安全。**风险在 `order`**：

| 书源 | order 来源 |
|---|---|
| `fanqie_api_rain` | `enumerate(item_data_list, start=1)` —— 位置序号 |
| `fanqie_api_oiapi` | 接口返回的 `index` |
| `fanqie_requests_default` / `fanqie_browser_default` | 页面 `realChapterOrder` |

混合场景（本地已有部分章节、其余从对端补）会导致 `order` 错乱；更严重的是 **`oiapi` 的 `chapter_content` 按 `chapter.order` 拉正文**（`chapter_content.py:28` `"chapter": str(chapter.order)`），order 一旦错位，后续更新会**拉到错误的正文**。

**判据**：
1. 比对远端书单的 `source_name` 与本地 `get_novel_source(novel_id)`；不同 → **仅告警，不跳过**（本地 requests、远端 rain 同属番茄组，书可正常互补）
2. **每本书首次同步前抽样**：取对端章节列表的首、中、末各 1 条，比对 `(order, title)` 与本地是否一致；**不一致 → 该本跳过，报告「章节序号不一致」，不写库**

## 4. 冲突与覆盖

**统一原则：只补缺，不覆盖。**

- 两侧都有正文且 `(time, count)` 不同 → 保留本地，计入报告（不中断）
- `novel_sources`：本地已有 → 不动；本地没有才写入远端的
- **幂等**：全部按 id 匹配，重复执行不产生重复数据、不覆盖
- 报告：`新增 X 本 · 补 Y 章 · 跳过 Z 章（其中 N 章两侧不同，已保留本地）· 跳过 M 本（正在下载）· 跳过 K 本（章节序号不一致）`

## 5. 触发方式与实现分层

### 5.1 UI：设置 → 同步（`/settings/sync`）

`SettingsLayout` 的 `ITEMS` 第 5 项，页面 `frontend/src/features/settings/pages/SyncPage.tsx`：

- 对端地址输入（`localStorage` 记忆为 `sync-peer-url`）
- 「连封面和插图一起拉」勾选框
- 「开始同步」/「取消」按钮
- 状态卡片：阶段文案、进度条、当前书/章、结果摘要、错误、序号不一致清单
- 轮询：`useSyncStatus` 仅在 `running` 时每 800ms 拉一次，停下就停（`refetchInterval` 用函数形式）

### 5.2 API

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/v2/sync/start` | `{peer, novel_ids?, include_images?}` → 启动后台任务；已有任务在跑返回 409 |
| GET | `/api/v2/sync/status` | 当前/最近一次状态；从未同步过时 `data` 为 `null` |
| POST | `/api/v2/sync/cancel` | 置停止标志（已写入的章节保留） |

### 5.3 分层

| 层 | 文件 | 职责 |
|---|---|---|
| 核心 | `novelbase/core/sync.py` | `RemoteClient`（只读对端）、`diff_chapters` / `order_consistent`（纯函数，可单测）、`build_plan` / `execute_plan` / `sync_from` |
| 任务 | `backend/services/sync_task.py` | 单例任务状态机；`start` 用 `loop.create_task` 调度，进度回调写进模块级 dict |
| 路由 | `backend/routers/sync.py` | 薄封装，挂在 `/api/v2/sync` |
| 页面 | `frontend/src/features/settings/pages/SyncPage.tsx` | 上述 UI |

**为什么同步在后端跑而不是浏览器**：项目原本就没有「写入任意章节」的 HTTP 接口，前端执行并不能省掉后端改动；反而正文要多走一趟（对端 → 浏览器 → 本机后端），流量翻倍。后端执行时正文只走一趟，且进度能放进后端状态里。

**CLI 未实现**：本版只有 UI 触发。核心逻辑在 `novelbase/core/sync.py`，后续加 `python -m cli sync` 只需薄封装。

## 6. 边界与错误处理

| 场景 | 处理 |
|---|---|
| 对端未启动 / 连不上 | 报错退出（`1`），提示检查 IP 与端口 |
| **`POST /api/v2/sync/start` 返回 405** | **不是路由写错**：该进程没有 sync 路由（旧代码未重启），请求落到了 `main.py:118` 的 SPA fallback（`@app.get("/{full_path:path}")` 只接受 GET）。重启后端即可。排查见 `docs/project/development.md`「常见坑」 |
| **`order` 不一致** | 该本跳过，报告「章节序号不一致」（§3.3） |
| **碰到本地正在下载的书** | CLI 经**回环** `GET /api/v2/download/tasks` 查询；后端未运行 → 告警并继续（此时不可能有下载任务在写库） |
| 网络中断 | 已写入的保留；**直接重跑**即续传（幂等） |
| 半途取消（Ctrl+C） | 已写入数据**保留**（"只补缺"语义，不滚回） |
| 大书（上千章） | 摘要一次取完（3000 章 ≈ 500KB）；正文逐章拉取 |
| 磁盘写满 / 写库失败 | 中止 + 报告已传数量，可重跑 |
| 对端书源本机未配置 | 正文照传；`source_name` 本地不存在 → 报告「该书来源未在本机配置」 |
| 插图 `raw_data` 为空 | 跳过该插图（§3.1） |
| SQLite 锁 | 已有 `timeout=15`；与下载任务并发写同一本书靠上一条检查规避 |

## 7. 已知限制

1. **完全没有访问控制**：同一局域网内任何设备都能读取全部小说数据，也能调用本产品其他所有 API（含 `DELETE /novel/{id}`）。
2. **这不是本设计引入的**：后端本来就监听 `0.0.0.0:8000`（`backend/main.py:157`、`app.py:27`）且 `/api/v2/*` 零鉴权。本设计只是**没有改变这个现状**。
3. **不可上公网**：没有鉴权、没有 TLS、明文 HTTP。若将来要暴露到公网，必须先补访问控制与传输加密。
4. **同步只在本机发起**：UI 上对外提供服务的那一台，只是一个被读取的 `/api/v2/storage/*`；没有“对方主动推给我”的入口（需要就自己在本机点一次）。
5. **M2 的极窄行为变化**：空字符串正文的章节不再算 `downloaded`（§2）。
6. **同一本书 url 形态不同会被视为两本**：项目不做 url 规范化（`Novel.id = sha256(url)[:32]`），沿用。
7. **`order` 校验靠抽样**（§3.3）：启发式，不能 100% 保证；判为不一致宁可跳过。
8. **不做**「以对方为准覆盖」：两侧内容不同时永远保留本地。

## 8. 测试策略

1. **单元层（主力）**：增量比对（两侧 brief/id 集合 → 待拉章列表，纯函数）；`(time,count)` 冲突判定与计数；幂等（同输入重跑 → 空计划）；`order` 抽样校验（一致 / 不一致）
2. **存储层（M7）**：`iter_chapters(include_content=False)` 返回的章节 `content` 为 `None`；`include_content=True`（默认）结果与改动前完全一致
3. **接口层（M1–M6）**：沿用既有做法（不启 lifespan/TestClient，`asyncio.run` 直调路由函数，见 `tests/test_backend_download_routes.py`）→
   - `include_images=false` 时 `cover` 为 `None`、章节 `images` 为空，`true`/缺省时与改动前一致
   - **`include_content=false` 时 `downloaded` 仍准确**（回归 M2 的 bug）
   - `ChapterBrief` 带 `time` 值
   - 空书库 / 单章 / 上千章一次返回
4. **双实例端到端（可跳过）**：本机起两个实例（不同端口 + 不同 `NLD_APP_DATA`），`A sync --peer B` → 断言书/章节/来源到位且内容一致。`@pytest.mark.e2e` 默认不跑
5. **不测**：网络波动、ARP 环境（手工验收）

## 9. 分期（均已实现）

| 阶段 | 内容 | 验收形态 |
|---|---|---|
| 1 | 后端改动 M1–M7（`ChapterBrief` 加 `time`、`include_images` / `include_content` 参数、M2 的 `downloaded` 修正） | 本机前端行为零变化；不加参数时响应与改动前一致 |
| 2 | `novelbase/core/sync.py` + `backend/services/sync_task.py` + `/api/v2/sync/*` | `curl` 能触发同步并看到进度 |
| 3 | `/settings/sync` 页面 | 设置第 5 栏可见、能触发、能看进度与结果 |

**已做的端到端验证**（两个实例、不同 `NLD_APP_DATA`）：首次 `新增 1 本 · 补 3 章`；重跑 `补 0 章 · 跳过 3 章`（幂等）；人为把本地 `order` +10 后 `跳过 1 本（章节序号不一致）`。

## 10. 后续工作（本次不做）

- **CLI `sync` 子命令**（核心逻辑已就绪，只需薄封装）
- 访问控制与传输加密（若要暴露到公网，这是前置条件）
- 分组 / 收藏 / 历史 / 书签 同步与冲突合并
- 阅读进度功能本身
- `push` / `both` 作为独立模式
- 「以对方为准覆盖」（需破坏性写入二次确认）
- 删除传播与内容自愈

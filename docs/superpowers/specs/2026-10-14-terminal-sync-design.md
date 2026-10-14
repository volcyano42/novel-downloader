# 终端对终端小说数据同步 — 设计文档

> 日期：2026-10-14 ｜ 状态：待 review
> 依赖：`2026-10-14-settings-sidebar-design.md`（提供 `/settings/sync` 与二级导航）
> 定位：局域网内两台运行本项目的终端互相同步**书籍数据**，不引入账号、不依赖云端

## 1. 背景与目标

多设备用户希望把「已下载的书」在几台机器之间搬一次，而不是各自重新下载。本项目数据全在本地 SQLite（`docs/planning/roadmap.md` §F4 明确「云端同步：建议不做」，理由是它与「自包含、数据在本地」的定位冲突并引入账号与隐私面）。

本设计走**局域网 P2P** 路线：无账号、无云中转、点对点直连，因此不触碰 F4 的结论。**目标**：把 A 端已有、B 端没有的**书籍数据**补齐到另一端。

### 同步对象（范围内的全部内容）

| 数据 | 是否同步 | 说明 |
|---|---|---|
| `meta`（书名/作者/简介/封面/`serial`） | ✅ | 每本书一个 `.db` |
| `chapters`（正文） | ✅ | 增量传输主体 |
| `illustrations`（插图） | ⚙️ 可选，**默认不传** | 体积可达 GB 级，同步页开关控制 |
| `novel_sources`（该书来源映射） | ✅ | 不同步会导致同步过去的书失去来源、无法换源/更新 |
| `groups` / `favorites` / `search_history` / `bookmarks` | ❌ | 本次不做（多设备一致性另有冲突语义） |

### 非目标

云端中转 / 公网穿透 / 账号体系 / TLS 传输加密 / 全局 API 认证 / 「以对方为准覆盖」/ 多会话并发。

## 2. 认证与信任模型

### 威胁与缓解

| 威胁 | 现状评估 | 本设计的缓解 |
|---|---|---|
| 同网段扫描 → 未授权读写书库 | **已存在**：后端监听 `0.0.0.0:8000` 且【无任何认证】 | 同步**数据面**端点强制 `Authorization: Bearer <peer_token>` |
| 恶意网页 CSRF | CORS 仅放行 `localhost:5173`，`Content-Type: application/json` 会触发预检 → 简单 CSRF 被挡；但不作为唯一防线 | 数据面要求自定义 `Authorization` 头（同样触发预检） |
| 误连陌生设备 | — | **配对码**：接收方界面显示 6 位随机码（默认 120s 有效；同一个连接请求内最多尝试 5 次，配对成功后该码立即作废，重新发起会生成新码） |
| 局域网嗅探 / ARP 欺骗 | 全部 API 明文 HTTP | **不引入 TLS**，列为已知限制 |
| 他人远程打开我的同步窗口 | 管理端点未鉴权（见下） | 默认关闭 + 需配对码 + 需人工批准 |

### 接收方限时开放窗口（默认关闭）

- 配置持久默认 `sync.allow_default: false`；**运行时开关不写回配置**，进程重启即回到关闭状态（"开放"永远是临时的）
- 打开 → 进入开放窗口（默认 300s，可配），界面显示倒计时 + 「等待连接…」
- 窗口内收到连接请求才弹批准框；窗口到期或被手动关闭 → **新请求一律拒绝**（已建立的会话不受影响）
- 语义：窗口只管「能否发起新请求」，不管已进行的会话

### 信任建立与凭证

1. A → `POST /api/v2/sync/request`（`client_label`）→ B 返回 `request_id`，B 界面出现待批准项
2. A → `POST /api/v2/sync/pair`（`request_id` + 配对码）→ B 校验 → 返回 `peer_token`
3. 双方把凭证落库：`user_data.db` 新表

```sql
CREATE TABLE IF NOT EXISTS sync_peers (
    peer_id    TEXT PRIMARY KEY,   -- 对端标识（首次由对端生成，随请求带来）
    label      TEXT NOT NULL,      -- 显示名，如「我的笔记本」
    token_hash TEXT NOT NULL,      -- sha256(peer_token)，明文 token 不落库
    created_at REAL NOT NULL,
    last_seen  REAL
);
```

- 该表双向使用：既存「我信任的对端」，也存「我持有的对方凭证」
- 撤销：同步页列出已信任设备，可解除（各自可撤销自己这一侧）
- 配对码与 `request_id` / `session_id` 均为**内存态**（重启即失效，符合"临时"语义）
- 生成：`secrets.randbelow(10**6)` 补零 6 位；`peer_token = secrets.token_urlsafe(32)`

## 3. 同步会话与批准流程

### 模式（三值，语义互斥）

| 模式 | 语义 |
|---|---|
| `pull` | 以对方为源：把对方有、我没有的补齐到我这边 |
| `push` | 以对方为目标：把我有的补到对方 |
| `both` | 一次会话内两侧都补齐（= 两次单向，不是互相覆盖） |

### 生命周期（接收方始终是"被连接方"）

1. `POST /sync/request` → 待批准（接收方界面弹「<label> 请求同步」+ 配对码）
2. `POST /sync/pair` → 换 `peer_token`（已信任的设备跳过 1-2，直接 3）
3. `POST /sync/session`（`mode`）→ `session_id`；接收方界面显示「正在与 X 同步」
4. 数据面交互（见 §4）：拉书单摘要 → 逐本比对 → 逐章拉取 → 落库
5. `POST /sync/session/{id}/close`；任一侧可 `DELETE` 取消；接收方在会话空闲超时后回收

### 并发与超时

- **同时只允许 1 个会话**；第二个请求返回明确错误（"已有同步进行中"）
- 会话空闲超时（默认 300s 无请求）→ 接收方回收该会话
- **与会话无关的另一条约束**：同步不访问外部站点，因此**不占用书源额度**（`source_concurrency` 无关）

## 4. 数据范围与增量算法

### 增量判定（零新增字段，复用现有数据）

- **书级**：按 `meta.id`（= `sha256(url)[:32]`）匹配
  - 对端有、本地无 → 整本拉（建 `meta` + 章节 + `novel_sources` 行）
  - 两侧都有 → 进章节级
- **章节级**：拉对端的 `ChapterBrief` 列表（`id` / `title` / `order` / `volume` / `count` / `time`），按 `id` 与本地比对
  - 本地缺失 → 拉该章正文
  - 两侧都有且 `(time, count)` 相同 → 跳过
  - 两侧都有但 `(time, count)` 不同 → **保留本地**，计入"冲突"报告（见 §5）
- **插图**：仅当开关 `sync.illustrations=true` 时，按 `illustrations` 表逐张拉取（沿用同一套"只补缺"语义）

### 传输形态

- 书单与章节摘要**分页**（`?page=&size=`），默认 `size=200`（上千章的书不会一次返回）
- 正文逐章拉取走数据面端点 `GET /sync/novel/{novel_id}/chapter/{chapter_id}`，其返回**数据结构与现有 `GET /api/v2/storage/novel/{id}/chapter/{cid}` 一致**（`ChapterData`），但只挂在 `/sync/*` 下以复用同一条 `peer_token` 鉴权链（不改动、也不暴露原 storage 端点）
- 落库：拉取方**直接调本地 storage 层**（`novelbase.core.storage`），与下载任务落库同一条代码路径，不走自身 HTTP

### 断点续传

天然支持：中断后重跑，比对结果只剩没传完的部分（幂等，见 §5）。

## 5. 冲突与覆盖策略

**统一原则：只补缺，不覆盖。**

- 两侧都有且内容不同 → 保留本地，计入结果报告（「N 章两侧不同，已保留本地」）
- `novel_sources`：本地已有该书记录 → 不动；本地没有才写入对端的
- **幂等**：全部按 `id` 匹配，同一同步可重复执行而不产生重复数据或覆盖
- 结果报告（同步页展示）：`新增 X 本 · 补 Y 章 · 跳过 Z 章（其中 N 章两侧不同，已保留本地）· 跳过 M 本（正在下载）`

## 6. API 面

新增 `backend/routers/sync.py`，前缀 `/api/v2/sync`（响应由既有 `V2ResponseMiddleware` 包成 `{ok,message,data}`）。

### 数据面（被对端调用，要求 `Authorization: Bearer <peer_token>`）

| 方法 | 路径 | 作用 | 鉴权 |
|---|---|---|---|
| POST | `/sync/request` | 发起连接（`client_label`, `peer_id`, `protocol_version`）→ `request_id` | 不要求 token（要求开放窗口开启） |
| POST | `/sync/pair` | 提交配对码 → `peer_token` | 用 `request_id` |
| POST | `/sync/session` | 开始会话（`mode`）→ `session_id` | Bearer |
| GET | `/sync/session/{id}` | 会话状态 | Bearer |
| DELETE | `/sync/session/{id}` | 取消会话 | Bearer |
| GET | `/sync/novels` | 书单摘要（分页） | Bearer |
| GET | `/sync/novel/{novel_id}/chapters` | 章节摘要（分页，`ChapterBrief`） | Bearer |
| GET | `/sync/novel/{novel_id}/chapter/{chapter_id}` | 单章正文 | Bearer |
| GET | `/sync/novel/{novel_id}/illustrations` | 插图（开关开启时） | Bearer |

### 管理面与本端发起（本机或手机浏览器打开的 UI 调用）

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/sync/status` | 开关状态、窗口剩余秒数、进行中的会话 |
| PUT | `/sync/allow` | 打开/关闭开放窗口（`{enabled, ttl_seconds}`） |
| GET | `/sync/requests/pending` | 待批准请求（供 UI 轮询或订阅 SSE） |
| POST | `/sync/requests/{id}/approve` · `/deny` | 批准 / 拒绝 |
| GET | `/sync/peers` · DELETE `/sync/peers/{peer_id}` | 已信任设备 / 解除信任 |
| POST | `/sync/start` | **发起**同步（`{host, port, mode, with_illustrations}`）→ 后台任务 |
| GET | `/sync/progress` | SSE 进度流（复用 `chapters/stream` 的 `text/event-stream` 先例） |

**管理面不鉴权**（与现有全部 API 一致，保持手机浏览器访问后端的使用方式不破）。缓解：同步窗口默认关闭、配对码限 5 次尝试、信任建立必须由接收方在界面上人工批准。

### 配置（`app_data/config/config.yaml` 新增 `sync:` 段）

```yaml
sync:
  allow_default: false        # 持久默认：不同步窗口关闭
  window_ttl_seconds: 300     # 开放窗口时长
  code_ttl_seconds: 120       # 配对码有效期
  max_attempts: 5             # 配对码尝试上限
  illustrations: false        # 是否同步插图（UI 开关的持久默认）
```

## 7. UI 面

### `/settings/sync` 页面（六块）

1. **本机状态**：「允许同步」开关 + 开放窗口倒计时 + 立即关闭
2. **发起同步**：`IP:端口` 输入 + 模式选择（pull/push/both）+ 插图开关 → 「连接」
3. **已信任设备**：列表（label / 最后同步时间）+ 解除信任
4. **上次结果**：§5 的结果报告
5. **进行中**：进度（书 i/n、章 j/m、当前书名）+ 取消按钮
6. **配对弹窗**：需要配对码时输入（6 位数字）

### 全局浮层（跨页面可见）

- **待批准请求**：「<设备名> 请求同步」+ 配对码 + 同意 / 拒绝 —— 必须做成全局浮层：对方发起时用户可能停在书架页，只在设置页显示会导致请求被忽略
- **同步进度**：轻量进度条（可展开到同步页）
- 实现参照现有 `components/Toast.tsx` + `toast-context.ts` 的模式（Context + 顶部/右侧浮层）

## 8. 边界与错误处理

| 场景 | 处理 |
|---|---|
| 对方未开窗口 / 窗口过期 | `request` 返回 403 + 明确 message（"对方未开启同步"/"对方的同步窗口已关闭"）→ 发起端 toast |
| 配对码错误 | 计入尝试次数；达上限（5）作废该 `request_id`，接收方界面提示"有设备反复尝试配对" |
| 配对码过期 | 拒绝并要求重新发起 |
| 协议版本不匹配 | `request` 携带 `protocol_version`，不兼容直接拒绝并提示（避免半途同步） |
| 网络中断 | 接收方空闲超时回收；发起方报"连接中断"，**直接重跑**即续传 |
| 半途取消 | 已写入数据**保留**（"只补缺"语义，不滚回） |
| **碰到正在下载的书** | **跳过并在报告中列出**（"M 本跳过：正在下载"）—— 依据 `task_manager` 的任务状态判定，避免与下载任务写同一本书 |
| 大书（上千章） | 摘要分页 + 逐章拉取；进度事件节流（每 N 章或每 3 秒推一次） |
| 磁盘写满 / 写库失败 | 中止会话 + 报告已传数量，可重跑 |
| 对端书源本机未配置 | 正文照传；`novel_sources` 里的 `source_name` 本地不存在 → 结果报告提示"该书来源未在本机配置"（更新/换源时会报未知书源） |

## 9. 测试策略

1. **单元层（主力）**：配对码生成/校验/过期/尝试上限；`peer_token` 签发与撤销；**增量比对**（给定两侧 `ChapterBrief` 列表 → 期望的"待拉章列表"，纯函数）；冲突判定与报告计数；幂等（同输入重跑 → 空计划）；开放窗口状态机（默认关 → 打开 → 过期 → 拒新请求）
2. **接口层**：沿用项目既有做法（**不启 lifespan/TestClient**，`asyncio.run` 直调路由函数，见 `tests/test_backend_download_routes.py`）→ 覆盖鉴权（无/错 token → 401，窗口关 → 403）、分页边界（空书库 / 单章 / 上千章）、会话并发拒绝、`sync_peers` 落库
3. **双实例端到端（可跳过）**：本机起两个实例（不同端口 + 不同 `NLD_APP_DATA`），`A pull B` → 断言 A 侧书/章节/`novel_sources` 到位且内容一致。标记 `@pytest.mark.e2e` 默认不跑，或作为手工脚本
4. **不测**：真实 WiFi 波动、ARP 环境、手机浏览器兼容（手工验收）

## 10. 分期

| 阶段 | 内容 | 可验收的形态 |
|---|---|---|
| 2a | 信任与握手：开放窗口、`request`/`pair`/批准、`sync_peers`、`/settings/sync` 页的 1/3/6 块 | 两端能连上、配对成功、信任列表可见 |
| 2b | 数据传输：书单/章节摘要、增量比对、正文拉取与落库、`novel_sources`、进度与结果报告、插图开关 | 一端能把另一端的书补齐并读出正文 |

阶段 2 依赖阶段 1（设置侧边栏）提供的 `/settings/sync` 位置；但后端部分（`routers/sync.py`）可并行开发。

## 11. 已知限制

- **明文 HTTP**：局域网内（ARP 欺骗/嗅探）可读取传输内容 —— 本设计不引入 TLS
- **管理端点未鉴权**：同网段设备可开关同步窗口、查看待批准请求；但建立信任仍需配对码 + 接收方人工批准
- **同一本书 url 形态不同会被视为两本**：项目不做 url 规范化（`Novel.id = sha256(url)[:32]`），本设计沿用
- **不做**「以对方为准覆盖」：两侧内容不同时永远保留本地

## 12. 后续工作（本次不做）

- 分组 / 收藏 / 历史 / 书签 的同步与冲突合并规则
- 传输加密（自签证书或预共享密钥）与全局 API 认证
- 「以对方为准覆盖」的交互（需破坏性写入的二次确认）
- 多会话并发、跨公网中转

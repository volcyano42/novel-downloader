# 书源「常规」配置段（跨能力共享字段）— 设计文档

> 日期：2026-10-14 ｜ 状态：**已被取代（2026-10-25）**
>
> ⚠️ **本文档描述的 `common` 段机制已删除**，不要再按它实现。
> 取代方案见 `docs/project/sources.md`「`source.json` 规范」：一个书源**只有一个 `mode` 和一套字段**，
> 不再有 `common` / `default_config` 能力段——既然不按能力分化，就不需要"跨能力共享字段"这一层。
> 相关内容（`_user_common` / `_user_overrides` / `_converge_candidates` / converge 端点）已全部移除。
> 保留本文档仅为记录当时的取舍过程。
> 动机：设置 API Key 这类**跨能力共享**的字段时，现在要在 4 个能力段里各填一遍

## 1. 背景与目标

**用户诉求**：设置页里每个书源的配置，增加一个「常规」段，各能力段默认收起 —— 目的是设置 API Key 时不必重复填四份。

**目标**：

1. 跨能力共享的字段（`key` / `params` / `delay` / `timeout` / `retry_times` / `backoff_factor` / `headers` …）在**数据层只存一份**（用户层新增 `common` 段），界面只填一次、四段生效
2. 各能力段在 UI 上**默认收起**，点开才编辑
3. 保留「逐能力覆盖」的既有能力：某个能力要单独用不同的 `delay`，仍能在该能力段里覆盖

## 2. 现状（实测）

| 事实 | 位置 |
|---|---|
| 字段按**模式**定义：`ENGINE_FIELDS[browser/requests/api]`，其中 `delay`/`timeout`/`retry_times`/`backoff_factor` 三处各写一遍；`key`/`params` 只在 `api`，`headers`/`cookies`/`proxies` 只在 `requests` | `frontend/src/features/sources/sourceConfigFields.ts` |
| 书源展开后先渲染 `分组/别名/并发数`，随后 `caps.map(...)` 把 **4 个能力段全部平铺**（标题 + mode 下拉 + 该模式全部字段），**无折叠** | `frontend/src/features/sources/sourceConfigForm.tsx:210-274` |
| **用户层 yaml 就是「四份」**：`search/novel_info/chapter_list/chapter_content` 每段各自重复 `timeout/retry_times/delay/backoff_factor`（api 源还各有一份 `key`） | `app_data/config/sites/fanqie-api-oiapi.yaml` |
| 合并只有三层：`ENGINE_DEFAULTS[mode]` → `source.json.default_config[cap]`（构建 manifest 时已并入 `source.json.common`）→ 用户层 `[cap]`。**没有「用户层 common」这一层** | `shared/config.py::merged_source_config`（226-252） |
| `PUT /config/sources/{name}` 只认：顶层 `concurrency`/`source_group`/`source_alias` + 逐能力段 `deep_merge` | `backend/routers/config.py:107+` |

## 3. 数据模型与合并优先级

用户层 `sites/{name}.yaml` 新增**可选**顶层 `common:` 段（与 `source.json` 的 `common` 同名同义：一为出厂、一为用户覆盖）：

```yaml
common:              # ← 新增：跨能力共享字段，只存一份
  timeout: 30
  retry_times: 3
  key: oiapi-xxxx
search:              # ← 能力段：只保留"与常规不同"的部分
  mode: api
novel_info:
  mode: api
```

合并链插入一层：

```
ENGINE_DEFAULTS[mode]
  → source.json.default_config[cap]      （构建 manifest 时已并入 source.json.common）
  → 用户层 common                        ← 新增这一层
  → 用户层 [cap]
```

**不变量**：

1. **用户层能力段始终覆盖用户层 common** —— 「逐能力覆盖」完好。想给 `chapter_content` 单独 5 秒 delay，就在那个能力段写 `delay`，它压过常规。
2. **`common` 不含 `mode`** —— `mode` 是「逐能力可覆盖」语义的核心（`effective_capabilities()` 的职责），拖进 common 会与其纠缠，且本需求不涉及它。故常规段字段集 = 各能力段 mode 的共有字段 **减去 `mode` 自身**。

## 4. 写入语义与旧值收敛

`PUT /api/v2/config/sources/{name}` 扩展（已有字段行为不变）：

| body | 行为 |
|---|---|
| `{common: {timeout: 30}}` | 用户层 `common.timeout` **deep_merge** 写入 |
| `{common: {key: null}}` | **删除** `common.key`（与现有 `{cap}.mode: null` 的特判一致） |
| `{common: {key: "x"}}` | 写入 common 的同时，**从各能力段删除同名键** |

第三条是必需的：否则用户层能力段里的旧值优先级更高，会出现「改了常规但不生效」。语义自洽 —— 「常规」管统一值；要某能力特殊，**之后再在该能力段里写**，此时它优先级更高、照常生效。

**已知副作用（明确接受）**：这条清理是「统一」语义 —— 若某能力段此前被单独设过不同的值，改常规会**覆盖**它（删除该段的值 → 改为继承常规）。UI 为此在常规段的字段旁提示：`该字段在「章节内容」中被单独设置过，修改将统一为常规值`（依据 `GET` 的 `user_overrides`）。

**显式收敛入口**（同一 router）：

```
POST /api/v2/config/sources/{name}/converge
```

扫描用户层各能力段：仅当某键**出现在全部能力段、且各段取值完全相同**时，才搬到 `common` 并从各段删除（搬完不改变任何能力的生效值）；其余键（有的段没有、或各段取值不同）**一律原样保留**，并在响应里列出（"这几项各能力不同或不全，已保留"）。

⚠️ 收紧到「全部能力段」是必要的：若某键只出现在部分能力段，搬到 `common` 后**其余段会从「继承出厂值」变成「继承 common 值」**，等于悄悄改了它们的生效值。

## 5. 字段集算法

- **前端**：`常规字段 = ⋂ ENGINE_FIELDS[各能力段 mode]`，排除 `mode`。4 段都是 `api` → 含 `key`/`params`/`delay`/`timeout`/`retry_times`/`backoff_factor`；某段改成 `requests` → 交集自动收窄（`key` 从常规段消失，只留在 api 那个能力段）
- **后端收敛接口不依赖前端字段元数据**：只看**用户层 yaml 里实际出现的键**（出现在 ≥2 个能力段且取值全相同 → 可收敛）。这样收敛逻辑对自定义字段与未来模式都成立，前后端不会因两份元数据漂移

## 6. UI 形态

书源展开后的结构（`分组/别名/并发数` 三个顶层级字段保持原位）：

```
分组 [番茄]        别名 [番茄·oiapi]        并发数 [1]

▼ 常规                        ← 默认展开
    API Key    [________________]
    请求延迟   [0] ~ [0] 秒
    超时 [30] 秒   重试 [3]   退避 [2]

▶ 搜索        API ▾            ← 默认收起
▶ 书籍信息     API ▾
▶ 章节列表     API ▾
▶ 章节内容     API ▾
```

- **常规段默认展开**；**能力段默认收起**，点标题展开后显示 `mode` 下拉 + 该模式全部字段
- 能力段里的共享字段带来源标注：该键在用户层能力段中**未被覆盖 → 「继承常规」**；**被覆盖过 → 「已覆盖」**
- 顶部收敛提示：`GET` 返回的 `converge_candidates` 非空时，显示「这 N 项在多个能力段重复，可一键收敛」+ 按钮
- 能力段展开状态**不持久化**（每次展开书源均收起）

## 7. API 变更

| 方法 | 路径 | 变更 |
|---|---|---|
| `GET` | `/config/sources/{source_name}` | 响应新增 `user_overrides: {cap: [键名]}`（区分「继承」/「覆盖」）与 `converge_candidates: [{key, value}]` |
| `PUT` | `/config/sources/{source_name}` | body 支持顶层 `common`（deep_merge；`null` 删除键；写键时清理各能力段同名键） |
| `POST` | `/config/sources/{source_name}/converge` | 新增：把各段取值相同的键收敛到 `common` |

已有响应/请求字段（`concurrency`、`source_group`、`source_alias`、逐能力段）**不变**。

## 8. 兼容与边界

| 项 | 处理 |
|---|---|
| 老用户层 yaml（无 `common` 段） | 完全不变：`common` 缺失按空处理，合并结果与改动前逐字一致（回归测试兜底） |
| `source.json` 的 `common` vs 用户层 `common` | 同名不同层：出厂 vs 用户覆盖（文档写明） |
| `enabled` 残留清理 | 现有 PUT 会 `pop("enabled")` —— 处理 `common` 前保持该行为 |
| `concurrency` / `source_group` / `source_alias` | 顶层级字段，不属于 `common`（语义是书源级而非引擎级），位置不变 |
| 各能力段 mode 不同 | 常规段字段交集自动收窄；`converge` 只会收敛各段一致的那些键 |
| CLI | 不改：CLI 读三层合并结果，`common` 层对其自动生效 |

## 9. 测试策略

**后端（pytest 主力）**

- 单元：`merged_source_config` 新层生效 + **能力段覆盖 common**（common 设 `delay=1`、`chapter_content` 设 `delay=9` → 该段取 9，其余取 1）
- 路由（沿用既有做法：不启 lifespan，`asyncio.run` 直调路由函数）：写 `common` → 用户层 yaml 出现该键**且各能力段同名键被删除**；`common: {k: null}` → 键被删；老 yaml（无 common）→ 合并结果不变；`enabled` 残留仍被清理
- `converge`：各段全相同 → 搬到 common 并从各段删除；各段不同 → 原样保留且在响应里列出
- 契约：`GET` 新增 `user_overrides` / `converge_candidates` 的形状

**前端冒烟（`scripts/ui_smoke.py` 扩展）**

- 打开一个 api 书源 → 常规段可见且含「API Key」；**4 个能力段默认收起**（其字段文本不可见），点击某能力段标题后才可见
- ⚠️ 断言一律用 `data-testid` 锚定到具体容器，**不用页面级通用文案** —— 2026-10-14 的设置页 review 中，5 条断言因取「书源/通知」这类与导航同字的文案而恒真

## 10. 非目标与后续工作

**非目标**：`common` 支持 `mode`（需同步改 `effective_capabilities`）；常规字段的「恢复默认」入口；能力段展开状态持久化；同步/导出等功能。

**后续工作**：常规段单字段的清空入口（当前靠能力段覆盖或手改 yaml）；把 `concurrency` 也纳入常规段（语义不同，需单独论证）。

# 详情页换源 —— 设计

> 2026-09-25。在书籍详情页把「novelId」换成书源名并加「换源」按钮；「检查更新 / 下载选中」直接沿用该书书源，不再要求用户手选。

## 背景

上一轮（《来源读点 + 用户可选 mode + 设置/书源整合》）已让来源（`source_name`）可从 API 读到、在书架卡片与详情页显示，并让详情页的「检查更新 / 下载选中」**默认选中**该书来源。但详情页元信息区仍留着 `novel.id`（sha256 前 32 位）那一行，来源是另起一行显示的；两处都不可操作，用户既看不出「这本书当前用的哪个书源」的直接操作入口，也仍要在对话框里确认一次书源。

本轮把那一行换成「书源名 + 换源按钮」，并让两个操作直接沿用书源。

## 现状调查（2026-09-25 实测）

| 事实 | 证据 |
|---|---|
| 详情页仍显示 `novel.id` | `frontend/src/features/detail/DetailPage.tsx:315` `<p className="text-xs text-slate-400 font-mono">{novel.id}</p>` |
| 来源另起一行（上一轮加的） | `DetailPage.tsx:317` `{bookSource && <p ...>来源：{bookSource}</p>}`，`bookSource` 定义在 `:49`（`localMeta?.source_name ?? st?.source`） |
| 两个操作都要弹窗 | `DetailPage.tsx:267-284`：`handleCheckUpdate` / `handleDownloadClick` 只 `setDialogVariant(...)`，再由 `handleDialogConfirm` 分派 `runCheckUpdate` / `runDownload` / `runDownloadLocal` |
| 弹窗样式模板 | `frontend/src/features/download/DownloadDialog.tsx`（居中卡片 + `bg-black/40 backdrop-blur-sm` + 书源列表 + 取消/确定），详情页是它的唯一使用处（`DetailPage.tsx:450`） |
| 后端**没有**写来源的端点 | `set_novel_source` 仅被 `backend/services/task_manager.py:73` 与 `cli/core.py:142` 内部调用；`backend/routers/storage.py` 只 import 了 `delete_novel_source` |
| 读写来源的既有函数 | `shared/user_data.py:295` `set_novel_source(novel_id, source_name)`（UPSERT，空值跳过） |
| 未知书源的统一边界 | `backend/services/source_guard.py::require_known_source`（HTTP 边界 404 的唯一校验点） |
| 小说不存在的既有语义 | `backend/routers/storage.py:134-139` 的 `delete_novel` 用 `store.load_meta` 判 404 |

## 目标

1. 详情页那一行显示**书源名**（不再是 `novel.id`），旁边一个**「换源」按钮**
2. 点「换源」弹出**选择书源**的窗口（样式同既有对话框），当前书源标「**当前**」
3. 换源**持久化**到 `user_data.novel_sources`；之后这本书一直用新书源
4. 「检查更新 / 下载选中」**直接沿用**该书书源执行，**不再弹窗**
5. 没有来源记录时**不弹窗**，提示用户先换源
6. 未下载的书（刚搜到）也能**先换源、再下载**

## 非目标（YAGNI）

- 不做「源失效自动探测 / 自动换源」
- 换源**不动**已下载章节（只改来源标记；旧源内容保留，是否重下由用户决定）
- 不改书架卡片、不改 CLI 的换源能力（CLI 侧本次不动）
- 不引入「多个候选源」概念；`novel_sources` 仍是「一书一源」

## 设计

### 1. 后端：新增写来源端点

`backend/routers/storage.py`：

```python
class SetSourceRequest(BaseModel):
    source_name: str


@router.put("/novel/{novel_id}/source")
async def set_novel_source_route(novel_id: str, body: SetSourceRequest):
    """换源：把该书的来源标记改写为给定书源（持久化到 user_data.novel_sources）。

    不校验小说是否已入库：来源记录独立于 storage，且「先换源、再下载」是合法场景
    （未下载的书没有 meta，但 `novel_id = sha256(url)` 与下载后一致）。
    """
    source_name = require_known_source(body.source_name)
    set_novel_source(novel_id, source_name)
    return {"status": "ok", "novel_id": novel_id, "source_name": source_name}
```

- `require_known_source`（`backend/services/source_guard.py`）是未知书源的**唯一**校验点 → 未知书源 404
- **不校验小说是否已入库**（2026-09-25 用户裁决）：「先换源、再下载」是合法场景，未下载的书也能写入来源
- `SetSourceRequest` 放进 `backend/schemas/storage.py`（与 `NovelMeta` 同处）并由 `backend/schemas/__init__.py` 导出

### 2. 前端：换源弹窗

新建 `frontend/src/features/detail/SourcePickerDialog.tsx`（结构照搬 `DownloadDialog`）：

```tsx
interface SourcePickerDialogProps {
  open: boolean; onClose: () => void;
  novelTitle: string;
  sources: string[];            // 全部书源名（来自 useSources()）
  current?: string;             // 当前书源（有效来源）
  onPick: (source: string) => void;
}
```

- 标题「选择书源」，副标题显示书名
- 列表项：书源名；**当前书源**那一项右侧标「当前」（`rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500`）
- 选中态沿用既有对话框的高亮（`border-indigo-300 bg-indigo-50`）
- 底部「取消 / 确定」；确定调用 `onPick(selected)`
- 「当前」标签与「换源」按钮配色按用户要求：**深灰文字 + 浅灰背景**

### 3. 前端：详情页那一行

`DetailPage.tsx:315` 的 `novel.id` 行改为「书源名 + 换源按钮」，并删掉 `:317` 的 `来源：` 行（同一信息不占两行）：

```tsx
<div className="flex items-center gap-2 pt-0.5">
  <p className="truncate text-xs text-slate-500">{bookSource || "未记录书源"}</p>
  <button onClick={() => setShowSourcePicker(true)}
    className="shrink-0 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-200">
    换源
  </button>
</div>
```

- 列表来源：`useSources()` 的 `Object.keys(...)`（与 `DownloadDialog` 的 `sources` 同口径，含未启用书源）

### 4. 前端：两个操作不再弹窗

```tsx
const handleCheckUpdate = useCallback(() => {
  if (!bookSource) { toast("请先点旁边「换源」选定书源", "error"); return; }
  runCheckUpdate(bookSource);
}, [bookSource, runCheckUpdate, toast]);

const handleDownloadClick = useCallback(() => {
  if (!bookSource) { toast("请先点旁边「换源」选定书源", "error"); return; }
  if (showCompare) runDownload(bookSource);
  else runDownloadLocal(bookSource);
}, [bookSource, showCompare, runDownload, runDownloadLocal, toast]);
```

随之删除：`dialogVariant` state、`handleDialogConfirm`、`DownloadDialog` 的 import 与用法，以及 `frontend/src/features/download/DownloadDialog.tsx` 文件本身（改造后无使用处）。

### 5. 前端：落库与失效

- `endpoints.ts` 新增：

```ts
export function setNovelSource(novelId: string, sourceName: string) {
  return apiPut<{ status: string; novel_id: string; source_name: string }>(
    `/storage/novel/${novelId}/source`, { source_name: sourceName });
}
```

- `hooks/index.ts` 新增 `useSetNovelSource(novelId)` mutation：成功时失效 `["novel-meta", novelId]` 与 `["novels"]`（书架卡片那行也要跟着变）
- 详情页确定换源后：成功 toast「已换源：<source_name>」并关闭弹窗；失败 toast 错误信息

## 数据流

```
换源：详情页「换源」→ SourcePickerDialog（列出全部书源，标「当前」）
     → PUT /api/v2/storage/novel/{id}/source {source_name}
     → require_known_source（未知源 404；**不校验是否已入库**）
     → user_data.set_novel_source（UPSERT）→ 失效 ["novel-meta", id] / ["novels"]
     → 详情页那一行与书架卡片都显示新书源

检查更新/下载选中：直接用 bookSource（不再经对话框）→ 既有 runCheckUpdate / runDownloadLocal / runDownload
```

## 错误处理

- 未知书源（PUT body 里的 `source_name`）→ 404（`source_guard`，**本端点的唯一校验**）
- **不校验小说是否已入库**：未下载的书换源会先留下来源行，下载时 `task_manager` 用同一 `novel_id` 落库，对账一致
- `bookSource` 为空（老书未回填 / 未记录）→ 前端 toast 提示先换源，不发请求
- 换源请求失败 → toast 展示错误，**不改动**页面上的当前显示（等待下一次成功响应）
- 远端书（未下载）：`bookSource` 取 `location.state.source`；换源同样落库（`novel_id` 是 `sha256(url)`，下载后一致）。换源成功后前端用本地 `sourceOverride` 立即反映新书源——远端书没有 `localMeta` 可刷新，否则界面不会更新

## 测试

- `tests/test_storage_source_write_route.py`（新增）：
  - 换源成功 → `get_novel_source(id)` 返回新值，响应含 `source_name`
  - UPSERT：连续两次换源取后者
  - 未知书源 → 404（`require_known_source` 收窄为已知源）
  - **未入库的 novel_id 也能写入**（不校验存在性；替代原「小说不存在 404」用例）
- 前端：`npx tsc -b` 0 错、`npm run lint` 无新增告警；手测清单见下
- 全量：`python -m pytest tests -q` 基线 **444 passed, 1 skipped** → 目标 0 failed

## 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 换源后旧章节内容与来源不匹配 | 已下载章节来自旧源，标记却已改 | 设计上明确「不动章节」；本设计不自动重下 |
| 弹窗被误关导致状态残留 | 取消时不应写库 | 取消只 `onClose()`，不调 `onPick` |
| 删除 `DownloadDialog` 影响其它入口 | 需确认无其它使用处 | 落地前 `grep -rn "DownloadDialog" frontend/src` 复核（现仅详情页） |
| 无来源时的提示被忽略 | 用户找不到换源按钮 | 按钮就在同一行、紧邻提示文案 |

## 验收（手工）

1. 打开本地已下载的书 → 那一行显示书源名 + 「换源」按钮（深灰字/浅灰底）
2. 点「换源」→ 弹窗样式与「检查更新」一致；当前书源条目右侧有「当前」
3. 选另一个书源 → 确定 → toast 成功、那一行与书架卡片都变
4. 「检查更新」→ 不再弹窗、直接用该书书源；「下载选中」同理
5. 老书（无来源）→ 点两个操作都只弹提示，不发请求
6. 未下载的书（搜到即进详情页）→ 换源成功、那一行**立即**显示新书源（无需刷新）

## 文档

- `docs/project/updates.md` 追加本轮摘要
- 若 `session-prompt.md` 的来源读点条目需补充「详情页可换源」，一并补一句

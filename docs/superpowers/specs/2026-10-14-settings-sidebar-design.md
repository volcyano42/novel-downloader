# 设置页二级侧边栏与子路由 — 设计文档

> 日期：2026-10-14 ｜ 状态：待 review
> 前置：无（可在同步功能之前独立交付）
> 关联：`2026-10-14-terminal-sync-design.md`（2026-10-25 修订后同步改为 CLI 触发、不做 WebUI，**本设计不再为其提供 `/settings/sync` 位置**）

## 背景与目标

设置页目前是**单页纵向 Section**，且由 `BookshelfPage` 按 `pathname` 切换视图渲染：

- `frontend/src/features/settings/SettingsPage.tsx`（120 行）= `SettingsView`，内部 4 个 `<Section>`：书源、导出格式、并发与性能、通知
- `frontend/src/features/bookshelf/BookshelfPage.tsx` 用 `activeNav`（`bookshelf | downloads | settings | search`）按路径切视图：`/downloads`、`/settings`、`/search-tab` 都渲染同一个 `BookshelfPage`
- 路由里 `/sources` 只是 `Navigate → /settings`

目标：把设置拆成**可直达的子路由 + 设置内二级侧边栏**，让每一项设置有稳定的 URL（便于分享/定位），并为后续新增「同步」栏目预留位置。

## 现状（实测）

| 项 | 现状 |
|---|---|
| 全局导航 | 书架 / 下载 / 搜索 / 设置（4 项，`BookshelfPage` 内） |
| 设置内容 | 单页 4 个 Section，全部渲染在 `/settings` |
| 深层链接 | 只能链到 `/settings`（无法直达"通知"） |
| `/sources` | `Navigate → /settings`（历史遗留入口） |

## 设计

### 路由

| 路由 | 内容 | 说明 |
|---|---|---|
| `/settings` | → 重定向 `/settings/sources` | 保持旧链接可用 |
| `/settings/sources` | 书源（每源折叠条：别名 / 分组 / 能力） | 原 `SourceSection` |
| `/settings/download` | 并发与性能（`max_workers` 等） | 原「并发与性能」Section |
| `/settings/export` | 导出格式（TXT / EPUB / IMG 分 tab） | 原 `FormatsSection` |
| `/settings/notify` | 通知 | 原「通知」Section |
| `/sources` | → 重定向 `/settings/sources` | 旧入口指向更具体的位置 |

`/settings/sync` 曾计划由同步功能提供；**2026-10-25 同步方案改为 CLI 触发（见 `2026-10-14-terminal-sync-design.md` §0 R12），该子路由不再需要**。本设计的导航按「已有子路由」渲染，加不加都不影响结构。

### 导航形态：设置内二级侧边栏

- **全局导航保持不变**（书架 / 下载 / 搜索 / 设置）—— 把 5 个设置项塞进一级会让全局导航膨胀到 9 项
- `SettingsLayout` = 左侧二级侧边栏（列出上述子页面，带图标）+ 右侧 `<Outlet />`
- 二级侧边栏项用 `NavLink`（自动高亮当前项）；窄屏（沿用现有 `md:` 断点）下由侧边栏改为顶部横向滚动的标签条

### 组件拆分

```
frontend/src/features/settings/
├─ SettingsLayout.tsx       二级侧边栏 + <Outlet/>
├─ pages/
│   ├─ SourcesPage.tsx      原 SourceSection
│   ├─ DownloadPage.tsx     原「并发与性能」Section
│   ├─ ExportPage.tsx       原 FormatsSection
│   └─ NotifyPage.tsx       原「通知」Section
└─ SettingsPage.tsx         （删除：内容已拆到上述文件）
```

- 拆分是**纯搬迁**：各 Section 的内部实现、`useGlobalConfig` / `useSaveGlobalConfig` / `useFormatConfig` / `useSaveFormatConfig` / `useSources` 等 hooks 与保存逻辑**一律不改**
- `BookshelfPage` 的 `activeNav` 判定改为：`/settings/*` 前缀 → `settings`（当前是 `pathname === "/settings"` 精确匹配，必须同步改，否则深层链接下左侧全局导航不高亮）

### 兼容

- `/settings` 与 `/sources` 都以 `<Navigate replace>` 指向新位置，旧书签不失效
- 设置项的 API（`GET/PUT /api/v2/config`、`/config/sources/{name}`、`/config/formats/{format}`）**完全不变**

## 非目标

- 不改任何设置项的内容、默认值、保存时机
- 不做设置内的搜索 / 收藏
- 不合并全局导航与设置导航；不引入 UI 组件库
- 不做设置项的 URL 参数（如 `?tab=`）

## 验收

- `cd frontend && npx tsc -b` → 0 错；`npm run lint`（oxlint）→ 0 告警
- **UI 冒烟（项目既有做法）**：headless Chromium 依次打开 `/settings`、`/settings/sources`、`/settings/download`、`/settings/export`、`/settings/notify`、`/sources`，断言：
  - 前 5 条分别渲染出对应内容（书源折叠条 / 并发控件 / 格式 tab / 通知开关）
  - `/settings` 与 `/sources` 落地到 `/settings/sources`
  - 截图存 `tmp/nld-ui-<日期>/`（便于人工比对）
- 回归：全局导航在 `/settings/*` 下仍高亮「设置」

## 影响面清单

| 文件 | 改动 |
|---|---|
| `frontend/src/App.tsx` | 新增 5 条 `/settings/*` 路由 + 2 条重定向 |
| `frontend/src/features/settings/SettingsLayout.tsx` | 新增（二级侧边栏） |
| `frontend/src/features/settings/pages/*.tsx` | 新增 4 个页面（内容搬迁自 `SettingsPage.tsx`） |
| `frontend/src/features/settings/SettingsPage.tsx` | 删除 |
| `frontend/src/features/bookshelf/BookshelfPage.tsx` | `activeNav` 用前缀判定；移除 `SettingsView` 引用 |

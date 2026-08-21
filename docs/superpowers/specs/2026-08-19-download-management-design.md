# 下载管理体验优化 — 设计文档

> 日期：2026-08-19 ｜ 来源：16 项待办清单 B 组（#1/#2/#8/#13）
> 状态：已批准，进入实施

## 背景

四项前端优化，均无后端改动。涉及文件：`BookshelfPage.tsx`、`DetailPage.tsx`、`DownloadTask.tsx`。

## #2 任务列表整体逆序渲染

- 位置：`BookshelfPage.tsx` 下载区（258-274 行）
- 方案：`tasks.map(...)` → `[...tasks].reverse().map(...)`（渲染层反转，不动数据源）
- 效果：最新任务在底部，旧任务在上

## #8 下载开始改为纯 toast 通知

- 位置：`DetailPage.tsx` `runDownload`/`runDownloadLocal`（249/267 行）
- 方案：删除 `navigate("/downloads")`，改为 `toast(\`「${title}」已开始下载\`, "success")`
- 其余逻辑（`setSelectedIds` 等）保留；进度接续由现有 `useTasks` 轮询 + BookshelfPage 完成/失败 toast 承担

## #13 completed/partial 条目展开全部章节

- 位置：`DownloadTask.tsx` `visibleChapters`（61-64 行）
- 现状：取「第一个非 downloaded 章节起前 10 个」，completed 任务全部 downloaded → 取不到 → 无法展开
- 方案：`status === "completed" || "partial"` 时返回**全部** `chapters`；downloading/paused 维持现状
- 章节行状态图标（绿勾/红叉/转圈/灰点）已支持，直接复用

## #1 骨架屏（任务列表 + 章节行）

- 任务列表：`useTasks` 解构 `isLoading`，加载中渲染 3 个 `DownloadTaskSkeleton`（仿 `BookCardSkeleton` 的 `animate-pulse`：标题条 + 进度条占位），定义在 `DownloadTask.tsx`
- 章节行：展开面板 `chapters` 为空时渲染 3 行行级骨架（`animate-pulse` 灰条）
- 参照：`BookCard.tsx:247-257` `BookCardSkeleton`

## 验证

- `npx tsc --noEmit --project tsconfig.app.json` 通过
- `npm run build` 通过

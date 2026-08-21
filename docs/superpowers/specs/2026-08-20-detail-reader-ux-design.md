# 书籍详情/阅读体验优化 — 设计文档

> 日期：2026-08-20 ｜ 来源：16 项待办清单 C 组（#1/#3/#5/#6）
> 状态：已批准，进入实施

## 背景

四项前端优化，无后端改动。涉及：`DetailPage.tsx`、`ReaderPage.tsx`、`BookCard.tsx`。

## #1 详情页骨架统一

- 位置：`DetailPage.tsx` L342（本地模式 SSE 流未完成显示"加载中..."文字）
- 方案：本地模式加载提示替换为与远程模式一致的骨架屏（L376-377 的 `animate-pulse` 章节行占位），统一两模式加载视觉
- Reader 正文：沿用现有 `ReaderSkeleton`，不改

## #3 进阅读页回顶强化

- 位置：`ReaderPage.tsx` L17-19
- 方案：回顶 effect 依赖从 `[chapterId]` 改为 `[chapterId, content]`，内容加载完成后再次 `window.scrollTo({ top: 0, behavior: "instant" })`
- 目的：从详情页滚动位置进入、换章后内容撑开页面，均稳定停在顶部

## #5 收藏移入三点菜单

- 位置：`BookCard.tsx`
- 移除封面左上角 Heart 按钮（L132-141）
- 右下角 DropdownMenu 顶部新增菜单项「收藏/取消收藏」：Heart 图标 + 状态文案（已收藏→"取消收藏" 实心 rose；未收藏→"收藏" 空心），onSelect 调 `toggleFavMut`（逻辑不变）

## #6 封面放大恢复半透明 + 纯展示

- 位置：`DetailPage.tsx` coverZoom 层（L445-450）及相关状态（L55、L162-181）
- 遮罩 `bg-black` → `bg-black/70 backdrop-blur-sm`（恢复 git 历史半透明版本）
- 移除 `coverScale` state、`handleCoverWheel`、`onWheel`、`transform: scale`——纯弹窗展示，不支持缩放

## 验证

- `npx tsc --noEmit --project tsconfig.app.json`
- `npm run build`

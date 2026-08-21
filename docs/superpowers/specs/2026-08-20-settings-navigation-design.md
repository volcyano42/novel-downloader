# 设置与全局导航优化 — 设计文档

> 日期：2026-08-20 ｜ 来源：16 项待办清单 E 组（#4/#10/#12/#16）
> 状态：已批准，进入实施

## 背景

四项设置/全局优化。涉及 `App.tsx`、`SettingsPage.tsx`、`BookshelfPage.tsx`。

## #4 导航改 Link/navigate

- 位置：`App.tsx` 侧边栏（L65 附近）/底部导航（L103 附近）原生 `<a href>`
- 方案：改为 `react-router-dom` 的 `<Link to>`，消除整页刷新，保持 SPA 历史（浏览器前进后退顺滑）
- DetailPage/ReaderPage 现有 `navigate(-1)` 不动

## #10 自动保存 + toast

- `SettingsPage.tsx`：移除 sticky 保存按钮（saving/saved 三态）、`SettingsViewProps` 去掉 `saving/saved/onSave`
- `updateGlobal` 的 mutation onSuccess 后 `toast("设置已保存", "success")`
- `BookshelfPage.tsx`：清理 `handleSaveSettings`、`saving/saved` state、`SettingsView` 的 `onSave` 传参

## #12 apikey 输入框样式

- `SettingsPage.tsx:239-248`：删除 `Row` 的 `desc="••••••••"` 说明文字；input 加灰色方框（`border border-slate-200 bg-white` 等）明确输入区域；保留眼睛切换显隐逻辑

## #16 全屏按钮

- grep 全库零残留（f601f3b 已回退），**无需改动**

## 验证

- `npx tsc --noEmit --project tsconfig.app.json`
- `npm run build`

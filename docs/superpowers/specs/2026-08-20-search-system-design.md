# 搜索体系升级 — 设计文档

> 日期：2026-08-20 ｜ 来源：16 项待办清单 A 组（#11/#14/#15）
> 状态：已批准，进入实施

## 背景

搜索体系三项：搜索历史（新后端路由 + 前端 UI）、variant 校验与布局、搜索结果封面图。前后端联动。

## #14 搜索历史

### 后端（新增 `backend/routers/history.py`，挂 `/api/v2/history`）

- `GET /api/v2/history/search`：按天分组返回 `{ok, message, data: [{date_label, items: [{id, platform, keyword, searched_at}]}]}`
  - date_label：今天 / 昨天 / M月D日 / 跨年加年份前缀（YYYY年M月D日）
  - 分组与排序在后端完成
- `POST /api/v2/history/search`：添加一条（body: `{platform, keyword}`），复用 `shared/user_data.py::add_search_history`
- `DELETE /api/v2/history/search/{id}`：删除单条（`shared/user_data.py` 新增 `delete_search_history(id)`）
- 注册到 `backend/main.py`

### 前端

- 搜索 tab 未搜索时，历史区替代现有 tips 占位：单独框一圈、按天分组、日期文字浅色 + 上下浅边框
- 右上角垃圾桶图标 → 进入删除模式（再次点击退出）→ 点某条直接删除
- 点击历史条目：回填 keyword + platform/mode/variant 到搜索框（不自动搜）
- 提交搜索（handleOnlineSearch）时 POST 写入历史
- `endpoints.ts` 新增 `getSearchHistory / addSearchHistory / deleteSearchHistory`
- `hooks/index.ts` 新增 `useSearchHistory`（React Query）

## #11 variant 校验 + 抖动 + 手机端布局

- SearchBar variant 按钮组外包 `<div>`（整体抖动单元）
- api 模式 + `variants.length > 0` + 未选 variant + 点搜索：div 加 `animate-shake`（复用 tailwind shake keyframes，参照 DownloadDialog L85-90）+ 拦截不发起搜索
- 手机端：控件行保持「平台 → 模式 → variant」顺序整体换行，variant 不再错位跑到"选择平台"底下

## #15 搜索结果封面图

- `backend/schemas/download.py::SearchResultData` 加 `cover_url: str | None = None`
- `backend/routers/download.py` 的 `/download/search` 两个分支透传 novelbase 返回的 `cover_url`
- `endpoints.ts::SearchResult` 接口加 `cover_url?: string | null`
- `SearchResultCard`：加 cover prop；有封面渲染缩略图，**无封面降级放大镜图标**（现有 Search 图标）
- 布局调整：书名/作者/简介左对齐；评分徽章从标题行移到作者底下（对齐作者行）

## 验证

- 后端：`python -m pytest tests/`（新增 history 路由测试）
- 前端：`npx tsc --noEmit --project tsconfig.app.json` + `npm run build`

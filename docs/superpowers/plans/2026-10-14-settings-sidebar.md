# 设置页二级侧边栏与子路由 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把设置页从「单页纵向 Section」拆成 `/settings/{sources,download,export,notify}` 四个可达子路由 + 设置内二级侧边栏，全局导航保持不变。

**Architecture:** 新增 `SettingsLayout`（二级侧边栏 + `<Outlet/>`）承载子路由；4 个设置块从 `SettingsPage.tsx` **纯搬迁**为独立页面组件，各自用既有 React Query hooks 取数（`DownloadPage`/`NotifyPage` 改为自取 `useGlobalConfig()`，消掉 `SettingsView` 的 props 历史包袱）；`BookshelfPage` 的 `activeNav` 由精确匹配改前缀判定；`/settings` 与 `/sources` 重定向到 `/settings/sources`。

**Tech Stack:** React 18 + TypeScript + react-router-dom v6（`NavLink`/`Outlet`）+ Tailwind + `@tanstack/react-query`；无前端测试框架 —— 验证依赖 `npx tsc -b`、`npm run lint`（oxlint）与 Python Playwright 的 headless 冒烟脚本。

**Spec:** `docs/superpowers/specs/2026-10-14-settings-sidebar-design.md`

## Global Constraints

- **零后端改动**：设置项的 API（`GET/PUT /api/v2/config`、`/config/sources/{name}`、`/config/formats/{format}`）与 hooks **一律不改**
- **纯搬迁**：各 Section 的内部实现、控件（`Row`/`Toggle`/`Num`/`Range`/`Select`）与保存时机保持不变
- **不引入 UI 组件库**，不合并全局导航与设置导航
- 窄屏沿用现有 `md:` 断点（二级侧边栏 → 顶部横向滚动标签条）
- 全局导航保持 4 项：书架 / 下载 / 搜索 / 设置
- 提交纪律：中文提交消息、一个方面一条 commit、显式指定文件（禁止 `git add -A`）

## Review Focus

以下 5 类情况最容易出问题，每条都在对应任务的冒烟断言里有对应用例：

1. **深层链接直接打开/刷新**（把 `/settings/export` 粘进地址栏并刷新）—— SPA fallback 必须仍然返回页面而不是 404
2. **全局导航高亮**（停在 `/settings/download` 时左侧「设置」必须仍高亮）—— 前缀判定漏改就会失效
3. **窄屏（< `md`）下的二级导航**—— 标签条能横向滚动、四个入口都可点
4. **设置项持久化行为不变**—— 拨动某个 Toggle 后仍走同一 PUT 且出现「设置已保存」toast
5. **书源页空数据态**—— 书源列表未加载/为空时仍显示「暂无书源」而不是空白

---

### Task 1: 建立可复用的 UI 冒烟脚本（对现状跑基线）

**Files:**
- Create: `scripts/ui_smoke.py`
- Create: `tmp/nld-ui-<日期>/`（截图输出目录，运行时生成，不入库）

**Interfaces:**
- Produces: `scripts/ui_smoke.py`，命令行 `python scripts/ui_smoke.py [--base-url http://127.0.0.1:4173] [--out DIR]`；对每个目标路径输出 `完成 <path> -> <截图文件>`，任一断言失败时以非零码退出并打印 `失败 <path>: <原因>`

- [ ] **Step 1: 写冒烟脚本（先只覆盖现状：`/settings` 系列 1 条路径 + 4 个既有入口）**

```python
"""UI 冒烟：headless Chromium 逐路径截图 + 断言。用法见 --help。"""
import argparse, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CHECKS = [
    # (路径, 期望落地的 pathname, 必须可见的文本)
    ("/bookshelf", "/bookshelf", "书架"),
    ("/downloads", "/downloads", "下载"),
    ("/settings", "/settings", "书源"),
    ("/sources", "/settings", "书源"),
    ("/search-tab", "/search-tab", "搜索"),
]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:4173")
    ap.add_argument("--out", default="tmp/nld-ui-smoke")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for path, expect_path, expect_text in CHECKS:
            page.goto(args.base_url + path, wait_until="networkidle")
            name = (path.strip("/") or "root").replace("/", "-") + ".png"
            page.screenshot(path=str(out / name), full_page=True)
            if page.url.split(args.base_url)[-1] != expect_path:
                failures.append(f"失败 {path}: 落地路径 {page.url} != {expect_path}")
            elif page.get_by_text(expect_text, exact=False).first.is_visible() is not True:
                failures.append(f"失败 {path}: 未找到文本 {expect_text!r}")
            else:
                print(f"完成 {path} -> {out / name}")
        browser.close()
    for f in failures:
        print(f, file=sys.stderr)
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 构建前端并起静态服务**

Run:
```bash
cd frontend && npm run build && npx vite preview --port 4173 &
```
Expected: `dist/` 重新生成，preview 监听 4173

- [ ] **Step 3: 跑脚本确认现状全绿（基线）**

Run: `python scripts/ui_smoke.py --out tmp/nld-ui-baseline`
Expected: 5 行 `完成 ...`，退出码 0，`tmp/nld-ui-baseline/` 下 5 张 PNG

- [ ] **Step 4: Commit**

```bash
git add scripts/ui_smoke.py
git commit -m "test(ui): 新增 headless 冒烟脚本（逐路径截图 + 落地路径/关键文本断言）"
```

---

### Task 2: 拆出 4 个设置页面组件（行为不变）

**Files:**
- Create: `frontend/src/features/settings/pages/SourcesPage.tsx`
- Create: `frontend/src/features/settings/pages/DownloadPage.tsx`
- Create: `frontend/src/features/settings/pages/ExportPage.tsx`
- Create: `frontend/src/features/settings/pages/NotifyPage.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`（改为 4 个新页面的聚合视图，暂不删）

**Interfaces:**
- Produces: 4 个默认导出的无参组件 `SourcesPage` / `DownloadPage` / `ExportPage` / `NotifyPage`（内部自取 hooks，不接收 props）
- Consumes: `Section`/`Row`/`Toggle`/`Num`/`Range`/`Select`（`@/features/sources/sourceConfigForm`）、`SourceAccordion`、`useGlobalConfig`/`useSaveGlobalConfig`/`useFormatConfig`/`useSaveFormatConfig`/`useSources`（`@/hooks/index`）、`useToast`

- [ ] **Step 1: 先把冒烟断言改成"新路由必须可达"（故意失败）**

在 `scripts/ui_smoke.py` 的 `CHECKS` 中把设置相关项替换为：

```python
    ("/settings/sources", "/settings/sources", "书源"),
    ("/settings/download", "/settings/download", "并发与性能"),
    ("/settings/export", "/settings/export", "导出格式"),
    ("/settings/notify", "/settings/notify", "通知"),
    ("/settings", "/settings/sources", "书源"),
    ("/sources", "/settings/sources", "书源"),
```

- [ ] **Step 2: 跑脚本确认失败**

Run: `python scripts/ui_smoke.py`
Expected: FAIL —— `/settings/sources` 落地后 pathname 仍是 `/settings`（或 404 文本），退出码非零

- [ ] **Step 3: 搬迁 4 个页面**

`SourcesPage.tsx`：把 `SettingsPage.tsx:14-25` 的 `SourceSection` 整体搬入并改名导出；`ExportPage.tsx`：把 `SettingsPage.tsx:27-75` 的 `FORMAT_TABS` + `FormatsSection` 搬入。
`DownloadPage.tsx` / `NotifyPage.tsx`：把 `SettingsView` 里的「并发与性能」（`SettingsPage.tsx:97-102`）与「通知」（`SettingsPage.tsx:106-117`）两个 `<Section>` 搬出，各自用 `useGlobalConfig()` + `useSaveGlobalConfig()` 取数与保存（逻辑照抄 `updateGlobal`，去掉 `onUpdate` 调用）；并发页用 `Range` 控 `max_workers`，通知页用 2 个 `Toggle` + 1 个 `Select` 控 `notify.on_complete`/`on_incomplete`/`sound`。

- [ ] **Step 4: `SettingsPage.tsx` 改为聚合视图（暂不删）**

`SettingsView` 的 body 改为依次渲染 4 个新页面（保持 props 定义以免 `BookshelfPage` 报错），页面 `div` 容器类名沿用 `mx-auto max-w-[640px] space-y-4`。

- [ ] **Step 5: 类型检查 + lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: 0 错、0 告警

- [ ] **Step 6: 跑脚本（此时仍应失败：路由还没接）**

Run: `python scripts/ui_smoke.py`
Expected: 仍 FAIL（`/settings/sources` 未注册）→ 说明断言确实在测路由

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/settings/pages frontend/src/features/settings/SettingsPage.tsx scripts/ui_smoke.py
git commit -m "refactor(settings): 设置块拆为 4 个独立页面组件（页面自取配置，去掉 SettingsView 的 onUpdate）"
```

---

### Task 3: SettingsLayout + 子路由 + activeNav 前缀判定

**Files:**
- Create: `frontend/src/features/settings/SettingsLayout.tsx`
- Modify: `frontend/src/App.tsx:86-96`（路由段）
- Modify: `frontend/src/features/bookshelf/BookshelfPage.tsx:32-38`（`activeNav`）、`:314`（移除 `SettingsView` 渲染）
- Delete: `frontend/src/features/settings/SettingsPage.tsx`

**Interfaces:**
- Consumes: Task 2 的 4 个页面组件
- Produces: `SettingsLayout`（默认导出，`<Outlet/>` 容器）；路由 `/settings/{sources,download,export,notify}` 可用，`/settings` 与 `/sources` 重定向到 `/settings/sources`

- [ ] **Step 1: 建 `SettingsLayout.tsx`**

左侧二级侧边栏（`NavLink` 列表：书源 → `/settings/sources`、下载与性能 → `/settings/download`、导出格式 → `/settings/export`、通知 → `/settings/notify`），右侧 `<Outlet/>`；容器沿用设置页现有的 `mx-auto max-w-[640px]` 宽度约束，侧边栏在 `< md` 时改为顶部横向滚动标签条（`flex md:block` + `overflow-x-auto md:overflow-visible`，与项目现有 `md:` 断点一致）。

- [ ] **Step 2: 改 `App.tsx` 路由**

```tsx
<Route path="/settings" element={<Navigate to="/settings/sources" replace />} />
<Route path="/settings" element={<SettingsLayout />}>
  <Route path="sources" element={<SourcesPage />} />
  <Route path="download" element={<DownloadPage />} />
  <Route path="export" element={<ExportPage />} />
  <Route path="notify" element={<NotifyPage />} />
</Route>
<Route path="/sources" element={<Navigate to="/settings/sources" replace />} />
```

（父子路由两条都写 `/settings`：父路由只提供布局，index 重定向交给上一条。）

- [ ] **Step 3: 改 `BookshelfPage.tsx` 的 `activeNav`**

```tsx
if (pathname === "/downloads") return "downloads";
if (pathname.startsWith("/settings")) return "settings";
if (pathname === "/search-tab") return "search";
return "bookshelf";
```

同时删除 `:314` 的 `activeNav === "settings"` 分支与 `SettingsView` 的 import。

- [ ] **Step 4: 删除 `SettingsPage.tsx`**

Run: `rm frontend/src/features/settings/SettingsPage.tsx`
Expected: 无残留引用（`grep -rn "SettingsPage\|SettingsView" frontend/src` 只应命中 `SettingsLayout.tsx` 路径字符串，无 import）

- [ ] **Step 5: 类型检查 + lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: 0 错、0 告警

- [ ] **Step 6: 重建 + 跑冒烟（应全绿）**

Run: `cd frontend && npm run build && python ../scripts/ui_smoke.py --out tmp/nld-ui-settings`
Expected: 6 行 `完成 ...`，退出码 0 —— 覆盖 `/settings/sources`、`/settings/download`、`/settings/export`、`/settings/notify`、`/settings`→重定向、`/sources`→重定向

- [ ] **Step 7: 补三条 Review Focus 断言到冒烟脚本**

在同一脚本里追加：① 深层链接直开 —— `page.goto(base + "/settings/export")` 后断言 `导出格式` 可见（等价于刷新后仍可达）；② 全局导航高亮 —— 停在 `/settings/download` 时断言左侧「设置」入口带激活态（按其 class 前缀 `bg-` 判定，写在断言里）；③ 窄屏 —— 用 `viewport={"width": 390, "height": 844}` 重开一页访问 `/settings/sources`，断言四个标签都可见。

- [ ] **Step 8: 跑全量冒烟**

Run: `python scripts/ui_smoke.py --out tmp/nld-ui-settings`
Expected: 全部 `完成`，含新增的三条断言，退出码 0

- [ ] **Step 9: 人工核对「设置项持久化行为不变」（Review Focus #4，不自动化）**

在浏览器里打开 `/settings/notify`，拨动一个 Toggle，确认出现「设置已保存」toast；随后打开 `/settings/download` 拖动 `max_workers` 并确认保存。
**不做成自动断言的原因**：这两步会真实写配置（`PUT /api/v2/config`），冒烟脚本应保持只读；写成自动断言会污染开发机的 `app_data/config/config.yaml`。

- [ ] **Step 10: Commit**

```bash
git add frontend/src/App.tsx frontend/src/features/settings/SettingsLayout.tsx \
        frontend/src/features/bookshelf/BookshelfPage.tsx scripts/ui_smoke.py \
        frontend/src/features/settings/SettingsPage.tsx
git commit -m "feat(settings): 设置页改二级侧边栏与子路由（/settings/{sources,download,export,notify}）"
```

（`git add` 该文件同时记录删除，不要用 `git add -A`。提交后用 `git show --stat HEAD` 确认 `SettingsPage.tsx` 是 `delete mode`。）

---

## Self-Review

**Spec coverage**：路由表 → Task 3 Step 2；二级侧边栏与窄屏 → Task 3 Step 1/7；组件拆分（4 页 + 删除 SettingsPage）→ Task 2/3；`activeNav` 前缀判定 → Task 3 Step 3；兼容重定向（`/settings`、`/sources`）→ Task 3 Step 2；验收（tsc / oxlint / headless 冒烟截图）→ Task 1/2/3 各步；影响面清单 → 已逐文件落到 Task 2/3 的 Files 段。

**未纳入**：spec 中 `/settings/sync` 只是"位置预留"，同步功能本身在另一份 spec，本计划不建该页面。

# 下载器分发层 `engines` 解析器 → 单个 `Engine` 实例 — 设计文档

> 日期：2026-10-14 ｜ 状态：待 review
> 动机：`novelbase` **面向所有开发者**（含第三方），公共函数的参数应当直白可读。当前 4 个公共函数收的是一个**没有类型标注**的「按 mode 取引擎」解析器（`engines(mode) -> Engine`）——这是一条只写在 docstring 里的隐藏契约，读者无法从签名看出该传什么。

## 1. 背景与目标

### 现状（实测）

| 事实 | 位置 |
|---|---|
| 4 个公共函数都收 `engines`（**无类型标注**），内部一律 `engine=engines(mode)` | `novelbase/core/downloader.py:20,40,55,65`（用到：`:34,50,62,72`） |
| `mode` 只用于取引擎：`mode = (mode_overrides or {}).get(cap) or mode` 紧接 `engines(mode)` | `novelbase/core/downloader.py:31-34,45-50,59-62,69-72` |
| 调用方各自造解析器（闭包 / lambda，按 mode 懒建并缓存） | `backend/routers/download.py:32-34`、`backend/services/task_manager.py:298-305`、`cli/core.py:58-74`、`cli/interactive.py:34` |
| **书源侧**能力函数收到的 `engine` 才是**实例** | `novelbase/sources/*/search.py`（`await engine.async_fetch_text(...)`） |
| `Engine` 抽象基类**未导出** | `novelbase/core/engine.py:37`；`novelbase/__init__.py` 只导出 `create_engine` |
| `mode_overrides`（能力名 → mode）由调用方关键字透传，**唯一用途**就是喂给 `engines(mode)` | core 四处 + backend 8 处 + cli 11 处 + task_manager 2 处 |

**关键判断**：`mode` 在 core 内部**除了取引擎没有任何其它用途**；书源能力函数签名是 `(query/url/chapter, engine, **kwargs)`，也不消费 mode。而「有效 mode」本就由调用方（`shared.config.effective_capabilities()`）决定。因此一旦 core 收实例，`mode_overrides` 立刻变成死参数。

### 目标

1. core 4 个公共函数改为收**单个 `Engine` 实例**（`engine`，仍在第 3 位）
2. 删除同时失去意义的 `mode_overrides`
3. `novelbase/source.py` 的 `capabilities()` / `resolve()` **保持不变**（`resolve()` 仍返回 `(fn, mode)`，mode 交由调用方使用）
4. 对传旧解析器的代码**响亮报错**，不产生诡异行为
5. 实际下载 / 搜索 / 更新行为**不变**（纯接口形状与职责归属调整）

### 非目标

- 不改 11 个书源的能力函数签名
- 不在 `novelbase` 增加「按书源 + 能力建引擎」的 helper（见 §8 方案 B）
- 不动版本号（项目约定：版本号由用户明确要求时才更新）

## 2. 决策记录（用户已确认，2026-10-14）

| 编号 | 决策 |
|---|---|
| D1 | `engines` 由解析器改为**单个 `Engine` 实例**（明确接受破坏性变更） |
| D2 | `mode_overrides` **一并删除**，core 不再关心 mode |
| D3 | 调用方各自按 `effective_capabilities()` 选 mode + 建引擎（方案 A），不在 novelbase 加 helper |

## 3. 目标契约

```python
# novelbase/core/downloader.py
async def search(source_name: str, query: str, engine: Engine,
                 skip_delay: bool = False, **kwargs) -> SearchResult | None
async def resolve_meta(url: str, source_name: str, engine: Engine,
                       skip_delay: bool = False, **kwargs) -> Novel
async def resolve_chapter_list(url: str, source_name: str, engine: Engine,
                               skip_delay: bool = False, **kwargs) -> Chapters
async def resolve_chapter(chapter: Chapter, source_name: str, engine: Engine,
                          skip_delay: bool = False, **kwargs) -> Chapter | None
```

- 参数名 `engines` → `engine`（与书源能力函数一致，一个参数只装一个引擎）
- 位置不变：原来传解析器的第 3 位，现在传实例
- `mode_overrides` 整个移除；`skip_delay` / `**kwargs` 语义不变

## 4. core 实现要点

1. 四处 `_resolve(source_name, cap)` 改为 `fn, _ = _resolve(...)`（`source.py` 不动，仍返回 mode，只是 core 不再用它）
2. 删除四处 `mode = (mode_overrides or {}).get(cap) or mode`
3. `engine=engines(mode)` → `engine=engine`
4. 函数体开头加防呆：

```python
if callable(engine):
    raise TypeError(
        "engine 现在必须传入 Engine 实例（原 engines(mode) 解析器已移除）；"
        "请用 shared.config.effective_capabilities(source_name) 选 mode 后自行 create_engine"
    )
```

5. `novelbase/__init__.py`：`from .core.engine import Engine, create_engine`，`__all__` 增加 `"Engine"`（公共签名标注 `engine: Engine` 后，第三方必须能 import）
6. `search()` docstring 的「单源单结果 / 上抛异常 / 由调用方 gather」语义不变，仅去掉 `mode_overrides` 段落

## 5. 调用方改造

| 文件 | 改动 |
|---|---|
| `backend/routers/download.py` | `_engines_for(source_name)` → `_engine_for(source_name, capability)`（内部 `effective_capabilities(source_name).get(capability)` → `get_cached_engine`）；**删除** `_mode_overrides()`；6 处调用改为 `_engine_for(name, "novel_info" / "search" / "chapter_list")` 并去掉 `mode_overrides=` 关键字 |
| `backend/services/task_manager.py` | 删除 `engines_cache` 闭包（`:298-305`）；改为按能力取引擎：`_caps = effective_capabilities(source_name)`，`meta_engine` / `chapter_engine` 各取一次。**保留 `to_thread` 预热**（`:309-315`）并**扩到 `chapter_content`** —— 两个能力的有效 mode 可能都是 browser，若首个章节解析才同步建引擎，会重演「事件循环线程里启 Chromium 阻塞整个 FastAPI」的老问题。`get_cached_engine` 按 `(source_name, mode)` 缓存，两能力同 mode 时天然去重为一个实例 |
| `cli/core.py` | `_make_engines(source_name, options_hook)` → `_make_engine_getter(source_name, options_hook)`：返回 `get(capability) -> Engine`，内部按 capability 缓存并保留 `.cache`（收尾 `close` 用，`cli/core.py:322` 等三处不变）；`_get_engine(source_name, mode, options_hook)` 保留。`_do_download_inner(..., engines=None)` 的参数改名 `engine_getter=None`。5 处调用改为 `get("novel_info" / "chapter_list" / "chapter_content")` |
| `cli/interactive.py` | 同 `cli/core.py`（`_make_engines` → `_make_engine_getter`）；3 处调用同步 |
| `cli/main.py` | `cmd_search`（`:139-153`）与 `cmd_info`（`:249-254`）改用 getter；搜索路径保持「**每源各用自己的引擎**」的既有不变量（`cli/main.py` 与 `cli/interactive.py` 的 `_search_one` / `_one` 各自注释，改造后不得退化为多源共用首个源引擎） |

## 6. 测试

| 文件 | 处置 |
|---|---|
| `tests/test_downloader_mode_overrides.py` | **重命名**为 `tests/test_downloader_engine_injection.py`（`git mv`）并重写：新语义 = core 把注入的实例**原样**传给书源能力函数；不再有任何 mode 解析 |
| `tests/test_backend_download_routes.py` | fake 签名 `engines` → `engine`；4 个 `*_passes_mode_overrides_by_keyword` 测试改为断言「传给 core 的是按**有效 mode** 取到的那个实例」（不再断言关键字透传） |
| `tests/test_cli_effective_mode.py` | 两个「按关键字传 mode_overrides」测试改为「按有效 mode 取到的引擎被传入」 |
| `tests/test_cli_engine_modes.py` | `test_make_engines_builds_per_mode_and_applies_hook` → 测 `_make_engine_getter`：按**能力**建引擎、`options_hook` 生效、`.cache` 收集到实例 |
| `tests/test_novel_source_writes.py:255` | `test_task_manager_passes_mode_overrides_to_core` → `..._passes_engine_instance_to_core`（断言 task_manager 把按有效 mode 取的实例传给 core） |

新增一条 core 单测（放在重命名后的 `tests/test_downloader_engine_injection.py`）：传旧解析器（callable）时抛 `TypeError` 且消息含迁移指引。

## 7. 文档

- `docs/session-prompt.md:48`「下载器 API」条重写为新签名 + 「引擎由调用方按有效 mode 建并注入」
- `docs/project/sources.md:98`（core 分发层 `mode_overrides` 段落）
- `docs/project/cli.md:22`（CLI 按有效 mode 建引擎并透传 `mode_overrides`）
- `docs/project/updates.md` 属历史记录，不改
- `CHANGELOG.md`：随版本号决定（本 spec 不动版本号）

## 8. 被否决方案

| 方案 | 否决理由 |
|---|---|
| B：novelbase 提供 `engine_for(source_name, capability)` | 「三层合并配置」（`ENGINE_DEFAULTS` + `source.json.default_config` + 用户层 yaml）住在 `shared.config`，**不在 novelbase**。该 helper 只能建「纯声明默认」的引擎 → backend 用不上，对第三方价值也有限（YAGNI） |
| C：`engines(capability) -> Engine` | 仍是解析器，没解决「签名看不出契约」的初衷；用户明确要单实例 |
| 保留 `mode_overrides` 作 no-op 兼容占位 | 死参数会误导读者（以为还生效），且文档不得不写「无效果」——不如删除 |
| 过渡期接受「实例或解析器」双形态 | 契约复杂度翻倍，且与 D1 的选择相悖 |

## 9. 影响面与迁移

**破坏性**：第三方若直接调 `novelbase` 的 4 个函数，需把 `engines` 解析器换成实例，并删掉 `mode_overrides=`。

迁移对照：

```python
# 旧
engines = lambda mode: create_engine(Options(mode=mode, ...))
novel = await resolve_meta(url, name, engines, mode_overrides={"novel_info": "browser"})

# 新
from novelbase import capabilities, create_engine, resolve_meta
mode = capabilities(name)["novel_info"]          # 或用 shared.config.effective_capabilities()
novel = await resolve_meta(url, name, create_engine(Options(mode=mode, ...)))
```

防呆 `TypeError`（§4.4）保证旧代码不会静默走错分支。

## 10. 验收标准

1. `python -m pytest tests -q` 全绿（基线 513 passed）
2. `grep -rn "mode_overrides" --include=*.py .`（排除 `__pycache__`）**零命中**
3. `grep -rn "engines" --include=*.py novelbase/` 零命中（书源目录内的 `engine` 单数不动）
4. `python -c "from novelbase import Engine"` 成功；4 个函数可用 `inspect.signature` 看到 `engine: Engine`
5. 传旧解析器 → `TypeError` 且消息含迁移指引
6. CLI 冒烟：`nld info <url> -s fanqie-requests-default`、`nld search <关键词>`、`nld update` 行为与改动前一致（含 `close()` 收尾不报错）
7. Web UI 冒烟：搜索页与 URL 解析（`GET /download/search`、`POST /download/meta`）正常

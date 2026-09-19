# 平台 source 状态与注册机制

## 平台 source 状态

| 平台 | SHOW_NAME | 搜索 | URL 解析 | 章节列表 | 正文 | 模式 | 备注 |
|------|-----------|------|----------|----------|------|------|------|
| fanqie | 番茄 | ✅ | ✅ canonical_book_url | ✅ | ✅ | browser/requests/api(oiapi,rain) | 短链 changdunovel.com/t/ 需重定向 |
| qidian | 起点 | ✅ | ✅ /book/ /info/ | 部分（JS 动态加载） | ✅ | browser/requests | 长 share URL 自动提取 book_id |
| qimao | 七猫 | ✅ | ✅ /shuku/ | ✅ Rain API (4K+章) | ✅ | browser/requests/api(rain) | search 返回 data.books 格式 |
| 92xs | 就爱文学 | ✅ | ✅ /book/{id}.html | ✅ | ✅ | requests | GBK→自动检测编码，无 API |

## Source 注册机制

`source.capabilities(name)` 通过文件系统扫描动态发现能力（`Path.iterdir`）。每个 source 为 `sources/{name}/` 目录（含 `__init__.py`），`capabilities()` 统一返回 `{mode: {variant: [functions]}}`，单 variant mode 用 `"default"` 作为 key。

`source.resolve(name, mode, function, variant=None)` 动态 import 并返回同步函数，`variant=None` 时优先取 `"default"`，无 `"default"` 则取第一个可用 variant。返回前通过 `inspect.signature` 校验必需参数名。

能力元数据定义在 `sources/contracts.py` 的 `CAPABILITY_META`（单一数据源，替代旧 FUNC_FILE_MAP）。

新增源平台只需在 `sources/` 下创建目录+文件，零注册表修改。每个 `sources/{name}/__init__.py` 导出：

```python
NAME = "fanqie"
SHOW_NAME = "番茄"
HOSTS = ("fanqienovel.com", "changdunovel.com")
```

## Novel.id 生成（2026-08-22 起）

`Novel.id` 不再由各 source 拼接平台前缀，而是由 `resolve_meta()` 中心化生成：

```
Novel.id = sha256(canonical_book_url(novel.url, platform))[:32]   # 32 位 hex，无前缀
novel.extra["platform"] = platform                                 # 冗余存平台（hash 不可反推）
```

- `canonical_book_url(url, platform)`（`novelbase/utils/urls.py`）做通用规范化（小写 scheme/host、去 query/fragment、去尾斜杠）+ 平台别名统一（92xs `/book/{id}.html`→`/html/{id}/`、qidian `/info/{id}/`→`/book/{id}/`）
- `ID_PATTERN` / `ORIGIN_ID_PATTERN` / `BOOK_URL_TEMPLATE` / `get_source_for_id` 已退役删除（hash 不可逆，无法从 id 反查）；`resolve_book_url` 仅接受 http(s) 输入；`resolve_chapter` 平台识别走 `get_source(chapter.url)`
- 92xs 章节 id 为 URL 末尾数字段（2026-08-22 起，修复前端路由被 `/` 截断）

## 目录结构

```
sources/{name}/
├── __init__.py           ← NAME/SHOW_NAME/HOSTS（ID_PATTERN 等已退役）
├── _common.py            ← 平台共享逻辑（签名、解析）
├── browser/              ← search/novel_info/chapter_list/chapter_content.py（"default" variant）
├── requests/             ← 同上
└── api/{variant}/        ← 每个 variant 有独立子目录（如 oiapi/、rain/）
```

- **browser/requests** 无 variant 子目录时自动生成 `"default"` key，module_path 不包含 variant 段。
- **api** 可以有多个 variant（不同的第三方 API 服务商），每个 variant 一个子目录。
- 2026-08-05：`provider` 概念重命名为 `variant`（更中性的"变体/实现"语义，能涵盖 API 服务商、browser 驱动、模拟环境等）；单实现占位由 `""` 改为 `"default"`。

## 私有源隔离（NLD_PRIVATE_SOURCES）

2026-08-05 新增。设置环境变量 `NLD_PRIVATE_SOURCES` 指向外部目录，镜像 `sources/{name}/` 结构。`capabilities()` 自动合并内置源与私有源，`resolve()` 从私有目录用 `importlib.util.spec_from_file_location` 动态加载。

```
$NLD_PRIVATE_SOURCES/
└── fanqie/api/oiapi/     ← 敏感实现（不进入公开仓库）
    ├── search.py
    ├── novel_info.py
    ├── chapter_list.py
    └── chapter_content.py
```

- 未设置环境变量时行为完全不变（零退化）。
- 私有目录不存在时静默跳过。
- 同名 variant 私有源追加进 capabilities（允许覆盖/补丁）。
- 用途：公开仓库不含危险的逆向/破解实现，本地开发设好环境变量即可使用全部功能。

## 目录简化 — 保持现状

2026-08-05 评估了三种目录简化方案：合并 browser/requests 实现（A）、只建需要的 mode（B）、单文件 source（C）。结论：**保持现状，不做目录结构简化**。当前多层目录虽增加了新增 source 的文件数量，但每种 mode 独立、隔离清晰，适合三种引擎（browser/requests/api）差异化实现的场景。

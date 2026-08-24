# 番茄小说 web 端 API 逆向与集成（fanqie webapi provider）

日期：2026-08-24
状态：已批准（集成版 + 默认带 cookie）

## 1. 背景与目标

novel-downloader 的 fanqie 书源目前有两条路：第三方中转（`oiapi` / `rain`，依赖外部服务）
与 app 端直连（`appapi`，x-gorgon/x-argus/x-ladon 四件套签名，**任意章节正文未打通**——需要
y 加密头 + 有效设备会话）。

本设计逆向番茄小说 **web 端** API 签名体系（`a_bogus`），并作为新 provider `webapi`
集成进 `novelbase/sources/fanqie/api/`，实现**信息 / 目录 / 正文**全链路直连，正文能力
补上 appapi 的缺口。

成功标准：给定 bookId（如 7499553647647263806，974 章）端到端下载，信息字段完整、
每章转码后无未覆盖私有区字符、TXT 可读。

## 2. 逆向结论（2026-08-24 实测验证）

| 项目 | 结论 |
|---|---|
| 签名库 | **不是** 老 `webmssdk.js`（其 `frontierSign` 生成的是 X-Bogus），而是 **rc-client-security `bdms.js`**（`web/stable/1.0.0.38`），由 `sdk-glue.js`（`web/glue/1.0.0.29`）加载 |
| 签名机制 | `_SdkGlueInit({self:{aid:2503,pageId:24117}, bdms:{aid:2503,pageId:24117, paths:["/api",...]}})` 初始化；bdms hook XHR，对匹配 paths 的请求在 **open 时自动把 `a_bogus` 附加到 URL** |
| a_bogus | 44 字符 base64，绑定 URL 与设备环境指纹（UA 等），**不读 cookie、不依赖登录态**；Node vm 加载原版 SDK 即可生成，**无需 msToken** |
| 信息 API | `GET /api/book/info?bookId=` → 28 字段：bookName/author/abstract/wordNumber/creationStatus/categoryV2/thumbUri/lastChapterTitle 等 |
| 目录 API | `GET /api/reader/directory/detail?bookId=` → `data.allItemIds`(全量 itemId) + `data.chapterListWithVolume`(卷数组，章节含 itemId/title/volume_name/realChapterOrder/needPay/isChapterLock/isPaidPublication/firstPassTime) |
| 正文 API | `GET /api/reader/full?itemId=` → `data.chapterData`(title/content(HTML)/preItemId/nextItemId/bookId/author/chapterWordNumber) |
| 正文混淆 | content 中常用字被替换为私有区字符（U+E3E8–U+E55B，共 362 个），**映射固定**，项目已有 `_common.py` 的 `content_transcoding` + `translate()` 可完整还原（实测 0 未覆盖） |
| 章节 ID 关系 | reader URL 的纯数字 ID **就是当前章 itemId**，可直接用于 `/api/reader/full`；前端还会预加载 preItemId/nextItemId 各一章（抓包可能抓到的就是相邻章） |
| 登录门槛章 | 部分章节 `isChapterLock=true`（`needPay=0`）：无 cookie 只返回约 200 字符试读；**带登录 cookie（sessionid/sid_guard 等）直接返回完整正文**（实测第 114 章 200→3664 字符），无需额外解锁接口 |

## 3. 架构

新增目录：`novelbase/sources/fanqie/api/webapi/`（文件系统自动发现，与 appapi 并列）：

```
webapi/
├── __init__.py        能力说明（参照 appapi/__init__.py 风格）
├── sdk/               原版字节 SDK（private 仓库；按 api 书源敏感约定不进 public）
│   ├── bdms.js        rc-client-security web stable 1.0.0.38
│   └── sdk-glue.js    web glue 1.0.0.29
├── signer.js          Node 签名器（常驻子进程，stdio JSON 协议）
├── _client.py         Python 桥接：子进程生命周期 + web_get_json()
├── novel_info.py      GET /api/book/info
├── chapter_list.py    GET /api/reader/directory/detail
├── chapter_content.py GET /api/reader/full + translate() 转码
└── search.py          web 端搜索接口待探测，先留占位（能力名注册用）
```

### 3.1 Node 签名器（signer.js）

- 加载 `sdk/bdms.js` + `sdk/sdk-glue.js`（原版，Node vm 沙箱，见 §3.2）
- 初始化 `_SdkGlueInit`（aid 2503 / pageId 24117 / paths `["/api"]`）——首次初始化需拉
  `imc.ugsdk.cn` 配置约 8 秒，故**常驻进程**复用
- stdin/stdout 行协议：`{"id":1,"url":"...","headers":{...}}` → 内部 XHR 自动附加 a_bogus
  → 响应 `{"id":1,"status":200,"body":"..."}`（body 为原始文本，含 HTML）
- 就绪握手：启动后输出 `{"ready":true}` 再接受请求；崩溃由 Python 侧重启

### 3.2 浏览器环境模拟（Node vm 沙箱）

Node 侧最小沙箱：自定义 `XMLHttpRequest`（基于 node:http/https）、`document/location/
navigator/localStorage/sessionStorage/performance/crypto/requestAnimationFrame/Image`
等全局桩。bdms.js 通过 UMD 挂到 `self.bdms`，内部为字节码 VM（加密 payload），
环境缺失会导致 `_u`/`Image is not defined` 等错误，已逐项补齐。

### 3.3 Python 桥接（_client.py）

- 启动 `node signer.js`（`shutil.which("node")`，缺失时抛明确错误）
- 生命周期：就绪等待 → 请求/响应按 id 配对 → 超时/崩溃自动重启重试（指数退避）
- `web_get_json(url, headers=None)`：签名器返回 body → `json.loads`
- **Cookie 默认注入**：从 `engine.options.cookie` 读取（优先级：显式 headers > options.cookie >
  无）；无 cookie 时仍可用（免费章），但对 `isChapterLock` 章节仅能拿到试读
- 空响应体（风控 0 字节）视为失败，重试

### 3.4 能力函数

- `novel_info(url, engine)`：`standardize_id` → book/info → 映射 `Novel`（title/author/serial/
  tags/description/count/cover），参照 appapi/novel_info.py 字段映射
- `chapter_list(url, engine)`：`standardize_id` → directory/detail → `Chapters`（保留卷名、
  volume_name、order、needPay、isChapterLock、firstPassTime 到 Chapter）
- `chapter_content(chapter, engine)`：reader/full → content → `translate()` 还原混淆 →
  HTML 段落清洗（`<p>` → 换行）→ 填充 chapter.content/count；`isChapterLock` 且响应
  content 过短（试读）→ 抛 `ChapterNotFoundError`（提示需登录 cookie）

## 4. 数据流

```
URL → standardize_id → bookId
  ├─ GET /api/book/info          → 元信息（Novel）
  ├─ GET /api/reader/directory/detail → 目录（Chapters）
  └─ 并发 GET /api/reader/full（Python 侧限速，如 5 并发）→ translate() → 纯文本
      → 导出 TXT（卷/章结构）+ meta.json
```

## 5. 错误处理与降级

- 风控空响应（200 + 0 字节 / code≠0）→ 指数退避重试；连续失败报错并记录章节号
- Node 进程崩溃 → Python 自动重启；重启后继续未完成请求
- `needPay`/`isChapterLock` 章节：无 cookie 时标记跳过并在结果中统计；有 cookie 正常下载
- 转码：`translate()` 未覆盖的私有区字符记入统计（当前预期为 0）

## 6. 测试计划

本机无 Python（py launcher 无安装），用 Docker（python:3.13 + requirements.txt）执行：

1. **单测**（tests/ 新增，mock 签名器）：ID 提取、目录解析、转码（含私有区字符还原）、
   chapter_content 试读判定
2. **集成测试**：真实 bookId → 信息字段断言 + 目录 974 章断言
3. **端到端**：抽 20 章快速验证 → 全量 974 章下载（成功标准），断言每章转码 0 未覆盖、
   TXT 可读
4. **Node 签名器**：独立验证 a_bogus 出现在请求 URL 且请求成功

## 7. 约定遵守

- 提交：中文消息、一个方面一条 commit、禁止 `git add -A`
- `sdk/` 目录含逆向产物，对照 PUBLIC_MANIFEST 红名单（api 书源敏感）**不进 public**
- 文档：本文件放 `docs/specs/`，可提交 private 仓库

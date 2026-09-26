# 旧版本数据迁移（`I:\NOVEL` → 当前项目）

> 2026-09-26 执行。把 `I:\NOVEL` 下 6 个旧版本项目下载的番茄小说数据迁移进当前版
> `novel-downloader`（SQLite 存储）。
>
> 工具位置：`D:\Linux\novel-downloader\novel-downloader-tools\scripts\legacy_migration\`
> （衍生产物，独立于核心仓库，git 永远管不到）。

## 一、结论速览

| 指标 | 数值 |
|------|------|
| 旧数据规模 | 6 个版本目录、115 本唯一书名、约 11.9 GB |
| 迁移计划 | **114 本**（按归一化书名合并且去重后） |
| 去重跳过 | **26 本**：书名测试「同一本书多个书名」6 组 + 正文与项目已有书相同 23 本 |
| 待迁移 | **88 本** |
| 已定位 | 90 条（含历史轮次） |
| 已入库 | **69 本 / 63 527 章 / 2 367 张章节插图**（其中**本次新建 65 本**，另 4 本是项目原有的同书异名） |
| 分组 | 本次新建的 **65 本已归入「迁移」分组**（`finalize.py --group-only`，按 `meta.created_at` 排除项目原有的书） |
| 完整性校验 | 48 本抽样中 **46 本完整**（1 本缺 1 章、1 本未知） |
| 遗留 | ~~失败章节清单 838 章~~（**2026-09-27 已清零**）、13 本未能迁移 |
| 空章节收尾（2026-09-27） | 补回 **148 章 `content` 为空**的章节（迁移 106 + 项目原有 42）→ 全库 **82199 章 / 空内容 0** |

## 二、数据源盘点（`scan_legacy.py`）

旧数据 6 个版本目录结构各不相同：

| 版本目录 | 结构 | 章节 id | 图片 |
|----------|------|---------|------|
| `1.0.x/{书名}/{书名}.json` | `{info, chapters:{标题:{url,content,img_url[],img_desc[]}}}` | ✓ | 仅 URL |
| `1.0.x/{书名}/{书名}.txt` | 导出文本 | ✗ | 无 |
| `1.1/{书名}.json` | `{小说名,作者,内容简介,标题:正文}` | ✗ | 无 |
| `1.1.x/{书名}.json` | `{version,info,chapters:{标题:{url,content,img_item:{组:dataURI}}}}` | ✓ | **内嵌字节** |
| `1.2.x/{书名}/{书名}.json` | `{info,chapters}` 或 JSON Lines | ✓(JSONL) | 视格式 |
| `1.2.x/{书名}/{书名}.txt` | 导出文本（`小说名：` 头 + `第N章`/`N.标题`） | ✗ | 无（另有 `Img/`） |
| `2.0/{书名}.json` | `{小说名,作者,内容简介,标题:正文}` | ✗ | 无 |
| `2.0.x/storage/{id}/` | `meta.json` + `chapters/{cid}.json`（含 `images[{raw_data,alt,insert,url}]`） | ✓ | **内嵌字节** |
| `2.0.x/exports/{组}/{书名}/` | 旧 SQLite（`novel_meta`+`chapters`）/ txt / epub / img | ✓ | 视文件 |

页面观察：1.2.x 目录下大量 `.json` 是 **0 字节**（数据实际在 `.txt` 与 `Img/`）；
`2.0.x/exports` 里有几个 `.db` 也是 0 字节（已空壳，回落到 txt）。

## 三、迁移方案（2026-09-26 与用户确认）

| 决策点 | 选择 |
|--------|------|
| 迁移方式 | **离线导入旧正文 + 仅缺口走网络**（旧数据能用的直接入库，不重复消耗 API 额度） |
| 迁移范围 | 只迁当前项目里没有的书 |
| 图片章节 | 旧数据线索预判 + 下载后检测兜底（browser 模式取字节） |
| 书名测试 | **正文模糊匹配**识别同一本书的多个书名，只迁一次 |
| API 速率 | 并发 ≤10；browser **单并发 + 每请求 3~5 秒随机间隔** |
| 分组 | 迁移的书统一归入 **「迁移」** 分组 |

## 四、工具与脚本

| 脚本 | 作用 | 联网 |
|------|------|------|
| `scan_legacy.py` | 盘点 6 个版本，识别格式 / 章节数 / 图片线索 / 跨版本同名 | 否 |
| `parse_legacy.py` | 各格式 → 统一缓存（`cache/books/*.json` + `cache/blobs/*.bin`）+ `plan.json` | 否 |
| `dedupe.py` | 正文模糊匹配去重（书名测试 + 与项目已有书比对）→ `dedupe.json` | 否 |
| `migrate.py` | 定位 → 对齐 → 离线导入 → 缺口下载（`--repair` 补缺口 / `--browser-only` 全走浏览器） | 是 |
| `retry_failed.py` | 按 `failed_chapters.json` 的章节 url 直接重下（**不需要章节列表**） | 是 |
| `finalize.py` | 完整性校验（库内 vs 书源章节）+ 归入「迁移」分组 | 是 |
| `rebuild_locates.py` | 从历史报告回填 `locates.json` 定位缓存 | 否 |
| `open_browser.py` | 单独开持久化 profile 浏览器供登录 | 是 |
| `debug_page.py` | 诊断 browser 实际取到的页面（排查「内容为空」） | 是 |
| `fix_empty_chapters.py` | **扫库里 `content` 为空的章节 → 用 rain 逐章重取写回**（不依赖 `locates.json`；在 `scripts/` 而非本目录，2026-09-27 新增） | 是 |

产物：`plan.json`、`dedupe.json`、`locates.json`、`state.json`、`quota.json`、
`failed_chapters.json`、`reports/*.json`。

### 标准流程

```bash
cd D:/Linux/novel-downloader/novel-downloader-tools/scripts/legacy_migration

python scan_legacy.py --root I:/NOVEL      # 1 盘点
python parse_legacy.py --root I:/NOVEL     # 2 解析（大文件流式，不整体 load）
python dedupe.py                           # 3 书名测试去重
python migrate.py --dry-run                # 4 预演（定位/对齐/报缺口）
python migrate.py                          # 5 迁移
python finalize.py                         # 6 校验 + 归入「迁移」分组
python retry_failed.py --login-wait 30     # 7 补失败章节（browser，需登录态）
```

## 五、遗留与继续（2026-09-26 状态 —— 其中 1、2、4 已于 2026-09-27 完成，见「八」）

1. **失败章节清单**：`failed_chapters.json`（启动补缺口时 838 条、10 本书）。
   其中《全民求生：E级天赋的塔之魔女》804 章是大头，正在用 browser 逐章补。
   **清单是累积去重的**，补成功的条目会自动移除，所以直接重跑即可：

   ```bash
   cd D:/Linux/novel-downloader/novel-downloader-tools/scripts/legacy_migration
   python retry_failed.py --login-wait 30 --concurrency 1 --interval-min 3 --interval-max 5
   ```

   剩余的 7 本（补缺口启动时统计，共 31 章）：
   《长得太漂亮，被系统变成了女生》9、《退役当天，捡了个美女总裁当老婆》7、
   《重生后钻进病娇女财阀老婆怀里》6、《转职老板，全国天才替我打工》4、
   《超能力是驾驶魔法少女尸体？》3、《开局地摊卖大力》1、《规则怪谈：知道什么叫黄金裔吗》1。

2. **API 额度**：`fanqie-api-rain` 每日 9700 章（自然日重置，`quota.json` 记录）；
   `fanqie-api-oiapi` 当日也耗尽。次日建议先用 rain 补：

   ```bash
   python migrate.py --repair          # 走章节列表，能顺带补「缺插图的图片章节」
   ```

3. **13 本未能迁移**（`verify-failed`，只记录不处理，用户确认）：
   * 6 本旧数据来源**不是番茄**（起点/笔趣阁）：《吞噬星空》《妖龙古帝》《捞尸人》
     《斗破苍穹》《没钱修什么仙？》《蛊真人》
   * 7 本定位到的书正文校验不通过：《反派恶少才不会变成优雅圣女》《变成白毛萝莉，
     开局跪求校花放过》《崩铁：从翁法罗斯开始的崩三模拟》《崩铁：十连满命，我抽出
     真遐蝶》《拟定推导：我的未婚妻是哥特萝莉》《末日游戏，开局攻略杀人魔校花》
     《疯了吧？绝世女帝竟是我老婆》《转生巨龙：捡到女儿是女帝重生》《退役魔法少女？
     没活就翻后空翻！》《高甜，相亲老公是豪门继承人》
     → 若需要，可人工提供正确的番茄书名/链接后，`migrate.py --books <key>` 重试。

4. **收尾**：补完后跑 `python finalize.py` 复核完整性。
   分组已处理：本次新建的 65 本已归入「**迁移**」分组：

   ```bash
   python finalize.py --group-only        # 按 meta.created_at 只归「本次新建」的书
   python finalize.py --group-only --since 2026-09-26
   ```

   实现要点：靠 `meta.created_at` 区分「本次迁移新建」与「项目原有的同书异名」
   （书名测试会让旧数据里的书名指向项目里已存在的那本，例如《不是，我电子女友咋修成
   剑仙了》≡《让你氪金修仙，没让你包养女剑仙》），后者不动。

## 六、踩坑记录（重要）

1. **中文数字解析**：`cn_to_int("二十")` 早期实现返回 12（把「十」当独立单位）——
   导致 1300+ 章「未匹配」。修复后《玄幻，我顿悟了混沌体》缺口从 1367 章降到 1 章。
   `norm_title()` 现在统一「第一章 ≡ 第1章」、「214.标题 ≡ 第214章标题」。
2. **相似度不能跳过不相似片段**：`dedupe` 早期把 `quick_ratio < 0.5` 的片段
   `continue` 掉，只剩相似片段参与平均 → 两本书只有第 1 章相同也会算出 1.0。
   必须让不相似片段**记 0 分**。
3. **书名测试**：番茄同一本书会有多个书名（旧数据里是旧名，搜索命中的是现用名）。
   例：《万族入侵，我开局驯化圣兽玄武！》→《御兽：我以圣兽镇万族》；
   《世上最强的人，居然是个萝莉？！》→《转生萝莉，我即为神明的终焉》。
   对策：书名变体（简介里的「原名/又名」）+ 搜索前 N 条结果 + **正文/简介校验**裁决。
4. **定位必须校验**：仅按书名/章节数会定位错书（《妖龙古帝》搜到作者不同的
   《逆天龙神》）。`verify_locate()` 用「官方简介相似度 + 远端首章正文比对」把关，
   通过才写库；样本会跳过「扉页/版权/简介」这类电子书排版章节（《异兽迷城》）。
5. **browser 登录态**：`fanqie-browser-default` 的 `user_data_dir` 为空 = 匿名 context，
   窗口里登录**不落盘**，进程一退出就失效 → 表现为「章节内容为空」。
   现统一用持久化 profile：
   `app_data/browser/Chromium/User Data`，脚本用 `--login-wait` 打开登录页等用户登录
   （检测到 cookie 立即继续，同一 Chromium 实例跑完全程）。
   ⚠ 同一 profile 不能被两个进程同时占用。
6. **导出文本夹带元信息**：1.2.x txt 每章首行是 `更新字数：N    更新时间：…`，
   解析时需过滤（`META_LINE_RE`）；txt 头部还有 `链接：` 可用于直接定位，比搜索准。
7. **Windows 大文件写入**：1.8 GB 的 cache JSON 曾因 `os.replace` 报 `WinError 5`
   （杀毒/索引占用）失败 → `dump_json` 加重试与目标清理；图片字节改存
   `cache/blobs/*.bin`（JSON 里记 `off/len`），省 33% 体积、读写更快。
8. **「完整性校验」看不见「内容为空」**（2026-09-27 发现）：`finalize.py` 的完整性是**按章节数量**比对（库内 N / 远端 M），`migrate.py --repair` 的缺口判定也只看**章节记录是否存在**——两者都**不检查 `content` 是否为空**。结果：库里 148 章内容为空，校验却一路报「50 完整 / 2 有遗漏」。**凡以数量当完整性判据的地方，都要补一个「内容非空」的断言。**

## 七、关键参数（可复用）

| 参数 | 默认 | 说明 |
|------|------|------|
| `--concurrency` | 6（browser 建议 1） | 并发上限，硬上限 10 |
| `--interval-rain` | 0.2s | rain 最小请求间隔 |
| `--interval-oiapi` | 1.2s | oiapi 最小请求间隔 |
| `--interval-browser` | 1.0s | browser 最小请求间隔 |
| `--rain-quota` | 9700 | rain 每日章节额度（0=不限） |
| `--rain-fail-threshold` | 5 | rain 连续失败多少次判定「本日无额度」并切 oiapi |
| `--oiapi-keys` | — | 多把 key 逗号分隔，额度类错误自动轮换 |
| `--verify-threshold` | 0.6 | 定位校验的正文相似度阈值 |
| `--verify-desc-threshold` | 0.5 | 简介相似度阈值 |
| `--max-candidates` | 3 | 定位阶段最多尝试的候选书数 |
| `--login-wait` | 0（本次用 30） | 启动后等用户登录的秒数（检测到即继续，最多 3 分钟） |

## 八、补空章节（2026-09-27，迁移真正收尾）

### 现象与真相

迁移收尾时 `failed_chapters.json` 已清零、`finalize.py` 报「50 完整 / 2 有遗漏」，
但**库里实际有 148 章 `content` 为空**：

| 书 | 空章 | `meta.created_at` | 归属 |
|----|------|-------------------|------|
| 转生萝莉，我即为神明的终焉 | 53 | 2026-09-25 17:22 | **迁移新建** |
| 国养灭世耄耋，哈气装傻贴贴 | 45 | 2026-09-25 17:23 | **迁移新建** |
| 待我拼好身体，旧日重临人间 | 8 | 2026-09-25 17:24 | **迁移新建** |
| 我在精神病院学斩神 | 31 | 2026-07-11 | 项目原有 |
| 原神：开局成为璃月阴阳两仪仙君 | 6 | 2026-07-21 | 项目原有 |
| 星穹铁道：揽星河入梦 | 5 | 2026-07-21 | 项目原有 |

**这 148 章不是图片章节**：`illustrations` 里没有它们的记录（那 3 本迁移书的插图总数
只有 1/3/2 张，且都挂在别的章上）。它们就是**正文没取到** —— 迁移时以匿名身份抓取
→ 番茄返回空页（同踩坑 5）。

### 为什么 `--repair` 没补上（两个盲区）

1. `repair_book()` 一进来就要求 `locates.json` 里有该书，没有就直接 `return failed`
   —— 这 3 本**不在定位缓存里**，连迭代都进不去；
2. 即使进去了，它的缺口判定是 `if rid not in existing`（只看章节记录是否存在），
   **认不出「记录在、内容空」的章节**。

### 补法（不依赖定位缓存）

新增 `scripts/fix_empty_chapters.py`：直接扫 `app_data/storage/novels/*.db` 中
`content` 为空的章节 → 用 `fanqie-api-rain` 逐章 `resolve_chapter()` → `save_chapter()` 写回。

```bash
cd D:/Linux/novel-downloader/novel-downloader-tools/scripts
python fix_empty_chapters.py --dry-run                # 只列缺口，不写
python fix_empty_chapters.py --interval 1             # 实补
python fix_empty_chapters.py --books <novel_id,...>    # 限定某几本书
```

**结果：146 章 / 0 失败 / 3 分 7 秒**（另 2 章在试跑时已补）。
复核：`--dry-run` 报「0 章」，全库 **82199 章 / 空内容 0**。

**全程未使用 browser** —— rain API 足够，所以 chromium 登录态那个坑对本次不构成阻塞。

### 仍然遗留

- `failed_chapters.json` 里还留着 35 条失败记录（8 本书），但它们对应的章节**不在「空内容」集合里**（内容都在）→ 属于**过时记录**，可直接清掉。
- **browser 持久化 profile 的问题仍未解决**：脚本运行时既读不到那个 profile 的登录态、也写不回它（`Last Browser` / `Cookies` 时间戳不动；日志 cookie 只有 10 条，而 profile 里有 25 个 fanqie cookie）。当前不需要（无图片章节），但将来若要用登录态章节，这是必须查的点。
- 一个候选根因：`migrate.py` / `retry_failed.py` 的 `--browser-user-data-dir` **默认值是相对路径**（`app_data/browser/Chromium/User Data`），代码按 `Path.cwd() / path` 解析 → 换个目录跑就换了 profile；而 `common.py` 里明明有 `SCRIPT_DIR` 却没用它。
- `common.py::prepare_browser_profile()` 的「杀残留 Chromium」只有 Windows 实现（`wmic` + `taskkill`，且被 `except: pass` 吞掉），**Linux/Termux 上静默失效**（清锁文件那半段是纯文件操作，仍然有效）。

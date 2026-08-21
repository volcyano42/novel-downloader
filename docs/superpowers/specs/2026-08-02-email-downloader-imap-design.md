# email_downloader IMAP 驱动改造

> 日期：2026-08-02
> 状态：设计完成

## 动机

当前 `email_downloader.py` 通过 `--url` CLI 参数获取下载链接，收件人由 `EMAIL_TO` 环境变量硬编码。需要改为：从 IMAP 邮箱轮询未读邮件，提取邮件正文中的 URL 进行下载，完成后将产物回复给发件人。

## 环境变量变更

| 变量 | 变更 |
|---|---|
| `EMAIL_TO` | ❌ 移除 |
| `IMAP_HOST` | 🆕 IMAP 服务器地址 |
| `IMAP_PORT` | 🆕 可选，默认 993（SSL） |
| `SMTP_USER` / `SMTP_PASSWORD` | ➡️ 复用为 IMAP 登录凭据 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | 保留，用于发送回复邮件 |
| `FANQIE_RAIN_KEY` / `RAIN_API_KEY` | 保留，不变 |
| `ALLOWED_SENDERS` | 🆕 发件人白名单，逗号分隔；默认 `259455964@qq.com,1542804683@qq.com` |

## CLI 参数

| 旧 | 新 |
|---|---|
| `--url` / `-u` | ❌ 移除 |
| — | 🆕 `--interval` / `-i`，轮询间隔秒数，默认 60 |

## 核心流程

```
启动 → 加载配置 → 连接 IMAP（SSL）
  → 循环：
      1. 搜索 UNSEEN 邮件
      2. 对每封未读邮件：
         a. 提取发件人地址，校验是否在白名单中
         b. 不在白名单 → 记日志，标记已读，跳过
         c. 提取正文首行，校验是否番茄链接
         d. 不是 → 记日志，标记已读，跳过
         e. 下载 → 导出 → 打包 zip
         f. 发送产物给发件人
         g. 成功/失败均标记已读
      3. sleep(interval)
```

## 错误处理

- 发件人不在白名单 → 静默跳过，记 INFO，标记已读
- URL 无效 → 静默跳过，记 WARNING，标记已读
- 下载失败 → 静默跳过，记 ERROR，标记已读
- 邮件发送失败 → 记 WARNING（不阻塞其他邮件）
- IMAP 连接断开 → 等待 interval 后重连

## 代码改动

### 文件：`novel-downloader-tools/email_downloader.py`

| 函数 | 改动 |
|---|---|
| `main()` | 移除 `--url`，添加 `--interval`；主循环替代单次 `asyncio.run(run(url))` |
| `run(url, reply_to)` | 签名加 `reply_to` 参数；内部 `send_email` 调用传入 `reply_to` |
| `send_email(to_addrs, subject, body, ...)` | `to` 改为参数传入；移除内部 `get_smtp_config()` 调用 |
| `get_smtp_config()` | 移除 `EMAIL_TO` 读取和校验 |
| `get_imap_config()` | 🆕 从环境变量读取 IMAP_HOST / IMAP_PORT（默认 993），账号复用 SMTP |
| `get_allowed_senders()` | 🆕 从 `ALLOWED_SENDERS` 环境变量读取白名单（逗号分隔），默认 `259455964@qq.com,1542804683@qq.com` |
| `check_unseen_emails(imap)` | 🆕 登录 IMAP，搜索 UNSEEN，返回 `[(uid, from_addr, reply_to, body), ...]` |
| `extract_url(body)` | 🆕 提取正文首行非空内容，去除 `<>` 包裹 |
| `mark_seen(imap, uid)` | 🆕 标记邮件已读 |

## 并发

同一批次的多封未读邮件**并行处理**（`asyncio.gather`），每封独立走「下载→导出→打包→回复→标记已读」。标记已读的 IMAP 操作串行化（`asyncio.Lock`），避免 IMAP 连接竞态。

## 不做的

- 发件人不在白名单 → 不处理（不回复）
- 不处理非番茄 URL（包括自动回复错误信息）
- 不支持多 URL（一封邮件只有一个 URL）
- 不处理附件
- 不支持 daemon 化（由 systemd / supervisor 等外部管理）

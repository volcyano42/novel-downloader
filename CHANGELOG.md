v2.1.2 变更日志

相较于[NovelDownloader](https://github.com/canyang2008/NovelDownloader)有了以下变化

## 架构重构

- 900 行巨型类拆分为模块化分层
- Engine 从池化改为单例
- 线程隔离
- 重试策略升级为 urllib3.Retry（API/Requests）+ 指数退避

## 配置系统 

- 双JSON → YAML
- API 密钥支持环境变量 — {PROVIDER}_API_KEY 优先级大于 YAML 中的 key
- 支持多 API 后端切换 — fanqie.yaml  中可配置 oiapi / rain 等多个 API 提供商

# 解析器系统

- 插件化注册 — 自动发现 parsers / exporters，无需手动 import
- BaseParser 接口扩展 — 新增  can_handle（URL 匹配）、 login（登录）、 parse_chapter_list（独立目录获取）
- Fanqie 三引擎模式适配。
- FanqieRainParser — 新增 rain.ink 第三方 API 解析器
- 类型安全 — 新增 8 种异常类，替代泛用异常

# 导出系统

- 移除 HTML / JSON 导出格式，保留 txt / epub / img
- epub 增强 — 配置化CSS、插图去重、魔数识别图片格式、NCX 目录
- output_path 模板化 — 支持  {group}  /  {title}  /  {file_name_template}  等占位符

# CLI / 交互

- 移除 WebUI — 删除  api.py （Flask REST 服务）及前端模板
- 进度条替换成Rich
- 配置热加载

# 修复

- 章节目录顺序 — 上游 API 模式下章节列表为乱序
- API 响应码处理，统一兼容
- WSL 中文输入
- 日志输出
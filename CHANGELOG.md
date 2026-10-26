# 版本记录

## 1.0.1 — 2026-10-25

- 默认来源切换为 23 个海外财经媒体、加密媒体、能源媒体及官方订阅，停用金十、华尔街见闻和 MKTNews。
- 新增 WSJ Markets、Financial Times、Oilprice、BEA，启用 MarketWatch、NPR、Decrypt 等海外来源。
- Reuters 和 Bloomberg 使用 Google News 公开标题索引，逐条校验索引标注的媒体域名，并明确展示非官方推送及全文访问限制。
- 新增按媒体筛选；新闻、搜索、SSE、中文整理和收藏显示仅使用当前启用来源。旧历史与收藏保留但隐藏。
- RSS 改为按原始字节解析，保留媒体声明的字符编码。
- 新增海外来源策略、历史过滤和索引媒体验证回归测试。

## 1.0.0 — 2026-10-20

- 基于 Global Market Newsboard 构建面向 US30、US500、BTC、ETH、XBR、XTI 的全球新闻监控台。
- 接入全球官方 RSS、财经媒体及 NewsNow 中文快讯适配，共 15 个配置来源。
- 新增 SSE 快讯、中文翻译、1 / 3 / 5 分钟主题整理、搜索筛选、收藏与来源状态。
- 保留付费数据升级入口，尚未连接付费服务。
- 修复中文标题去重、采集时翻译阻塞及 SQLite 连接释放问题。
- 提供 Windows 启停脚本、使用说明及回归测试。

上游来源和许可证见 README.zh-CN.md、LICENSE、NOTICE 和 third_party/。

# 全球脉冲 Crossmarket Pulse

面向 US30、US500、BTC、ETH、XBR、XTI 的个人新闻监控台。

## 使用

在本目录运行 `./start.ps1`，打开 http://127.0.0.1:8010 。关闭服务使用 `./stop.ps1`。
后台进程在本机运行，关闭网页后仍采集新闻；电脑休眠、断网、关机或进程停止时会中断。未设置开机自动启动。

首次安装（Python 3.12+）：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./start.ps1
```

## 第一版功能

- 1.0.1 默认采用 23 个海外财经媒体、加密媒体、能源媒体和官方订阅；可用数量以“数据源状态”为准。
- 大型媒体包括 CNBC、WSJ Markets、Financial Times、MarketWatch、BBC、The Guardian、NPR；加密来源包括 CoinDesk、Cointelegraph、Decrypt；能源来源包括 Oilprice、EIA；宏观来源包括美联储、BLS、BEA、ECB。
- Reuters 与 Bloomberg 通过 Google News 的公开标题索引接入，逐条验证索引中的媒体域名。界面始终标明“Google News 索引”，链接经 Google News 跳转；不是官方直连、全文抓取或授权秒级快讯。搜索索引可能延迟、遗漏或跳转失效，原文章可能需要订阅。
- 金十、华尔街见闻和 MKTNews 已停用。旧记录仍保存在本机数据库，但在查询阶段按启用来源过滤，避免旧记录占满列表；旧收藏不删除，只在当前界面隐藏。
- 保留主项目的异步采集、相似标题去重、SQLite 历史记录、SSE 推送。新增 SSE 心跳。
- 默认海外来源均为 RSS，约 60 秒检查一次；检查时间与原始发布时间分别显示。新闻源和标题索引的端到端延迟不保证。
- 中文整理支持 1 / 3 / 5 分钟刷新，按过去 24 小时报道分组，每组选择最多 3 条。使用规则归类和原文 / 机器翻译，未接入付费生成模型。
- 品种关联、重要性、来源类型及指定媒体过滤，标题关键词搜索和 1 / 3 / 7 / 30 天回看（每次最多 600 条）。
- 收藏、翻译开关、更新间隔、升级偏好存储在当前浏览器。历史新闻存储在本机 `data/market_stream.db`。
- 桌面通知需主动点击铃铛并授权，仅对打开页面后新收到的、5 分钟以内且符合当前筛选的重要新闻生效。关闭网页后不发送桌面通知。
- 免费翻译使用 Google 公共翻译端点，可能限流或失效；失败显示原文。只发送标题；中文原文无需翻译。翻译结果存入本机 SQLite。
- 媒体报道不代表已独立核实；关键词关联不代表对持仓或价格影响的确定判断。

## 升级入口

左侧及右上角提供 PRO DATA 入口，可保存升级偏好。目前没有付款、订阅或付费数据连接。
`/api/hedge/integrations` 返回实际连接状态。未来可通过独立采集适配器连接授权新闻推送，并沿用 StreamItem → SQLite → SSE 链路。供应商密钥应仅配置在服务器环境变量，不能写入网页或 Git。
接入有时效承诺的付费快讯需要选定供应商、授权范围和凭据，当前接口不宣称已提供这些服务。

## 来源和复用

主项目：[CWhhhaaha/Global-Market-Newsboard](https://github.com/CWhhhaaha/Global-Market-Newsboard)
基准提交 `7e49fb9504eed692e7062e40964b048583d221c2`，Apache-2.0。保留原始 LICENSE / NOTICE / README / Git 历史。原页面保留于 `/original`。

中文快讯适配：[newsnext/newsnow](https://github.com/newsnext/newsnow)
基准提交 `0560c993b226cd2fd07d8a79875d50551f52c584`，MIT。将金十、华尔街见闻、MKTNews 的适配逻辑移植到 `chinese_sources.py`；保留原适配文件及许可证于 `third_party/`。

本次修改日期：2026-10-20。新增聚焦交易品种的前端、来源健康状态、非阻塞按需翻译、中文去重修复；不采集锁定或会员正文，不绕过来源访问限制。

## 运行与检查

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
node --check src/market_stream/static/dashboard.js
```

`logs/server-error.log` 查看服务日志；`/health` 查看总体状态。来源失败保留历史新闻，逐源错误见界面。
当前仅监听本机 127.0.0.1，没有公网地址。要从手机或其他电脑访问需另行部署带访问控制的长期 Python 服务；本版未把本机端口暴露到公网。

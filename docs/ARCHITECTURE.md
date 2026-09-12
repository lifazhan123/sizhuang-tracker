# 架构说明

本文档说明 `sizhuang-tracker` 的整体设计、数据源选型依据、模块职责与扩展方式。

---

## 1. 设计目标与约束

| 目标 | 设计上的落实 |
| --- | --- |
| 只关注一只股票 | 股票身份收敛到 `StockConfig`，全链路由 `secid` / `secucode` 派生，无硬编码 |
| 数据要「全网 + 东方财富」 | 新闻走东财聚合搜索（覆盖财联社/证券时报/中证网等），行情/资金/公告/研报/股吧走东财原生接口 |
| 每天 12:00 稳定送达 | GitHub Actions 定时 + 跨数据源故障转移 + 单点失败不中断 |
| 部署零成本 | 只用公开 HTTP 接口，无 API Key；邮件走 SMTP；Runner 为 GitHub 免费额度 |
| 依赖尽量少 | 只依赖 `requests` / `PyYAML` / `Jinja2`；技术指标纯 Python 实现，不引入 numpy/pandas |
| 结果可解释 | 每个多空信号都带文字说明与命中值；情绪打分可回溯命中关键词 |

### 明确不做的事

- **不做交易执行**，不接券商接口；
- **不做投资建议**，输出定位是「信息聚合 + 统计」，措辞上保持审慎；
- **不引入浏览器自动化**（Playwright/Selenium）。股吧列表虽为前端渲染，
  但页面内联了 `var article_list={...}`，直接解析即可，省掉整个浏览器依赖。

---

## 2. 分层结构

```
┌─────────────────────────────────────────────────────────────┐
│  cli.py            命令行入口（run / check）                 │
├─────────────────────────────────────────────────────────────┤
│  pipeline.py       编排层：并发调度、错误收集、结果装配       │
├───────────────┬──────────────────┬──────────────────────────┤
│  fetchers/    │  analysis/       │  report/ + notify/       │
│  抓取层        │  分析层           │  输出层                   │
├───────────────┴──────────────────┴──────────────────────────┤
│  http.py + models.py + config.py + logging_setup.py          │
│  基础设施层：HTTP、数据模型、配置、日志                        │
└─────────────────────────────────────────────────────────────┘
```

分层原则：

1. **抓取层只负责「拿到并结构化」**，不做判断，不做格式化。
   统一产出 `models.py` 中的数据结构。
2. **分析层只读数据模型**，不关心数据从哪来，也不关心怎么渲染。
3. **输出层只消费 `DailyBundle` + `TrendAnalysis`**，两者是唯二的输入契约。
4. **配置只在 `config.py` 收口**，其余模块不接受裸字符串参数。

这样换数据源只需改 `fetchers/`，换呈现方式只需改 `report/`。

---

## 3. 数据流

```
                        ┌── collect() ───────────────────────────────┐
                        │                                            │
  AppConfig ──▶ FetchContext ──┬─ 串行：QuoteFetcher  (先拿到交易日)   │
                               ├─ 串行：KlineFetcher  (技术分析基础)   │
                               └─ 并发：ThreadPoolExecutor(max_workers=5)
                                       资金流向 / 融资融券 / 财务指标
                                       全网新闻 / 公司公告 / 机构研报
                                       股吧帖子 / 龙虎榜 / 大盘指数
                                                                     │
  DailyBundle ◀──────────────────────────────────────────────────────┘
        │
        ├─▶ score_items()      新闻情绪统计  ──▶ bundle.news_stats
        ├─▶ score_text()       公告/股吧逐条情绪 ──▶ bundle.guba_stats
        └─▶ analyze_trend()    ──▶ TrendAnalysis
                                    │
  (DailyBundle, TrendAnalysis) ─────┼──▶ render_markdown()  → .md
                                    ├──▶ render_html()      → .html → 邮件正文
                                    └──▶ save_reports()     → output/
```

### 为什么行情/K线串行，其余并发？

- `QuoteFetcher` 和 `KlineFetcher` 决定 `trade_date`（交易日），是报告的时间基准，
  必须最先确定；
- 其余 9 个数据源彼此无依赖，并发抓取把总耗时从「累加」压到「取最慢的一个」。
  受 `HttpClient.min_interval` 限速约束，实测总耗时约 15–25 秒。

### 错误处理策略

`pipeline.guard()` 包住每个抓取器：

```python
def guard(label, fn, default):
    try:
        return fn()
    except FetchError as exc:            # 已知业务失败（接口改版、无数据）
        bundle.errors.append(f"{label}: {exc}")
    except Exception as exc:             # 未知异常
        bundle.errors.append(f"{label}: {type(exc).__name__} {exc}")
    return default
```

原则是 **降级而非中断**：任何一个源挂了，报告照常发出，
缺口会列在邮件底部的「本期数据缺口」区块，绝不用编造数据填补。

---

## 4. 数据源清单

全部为公开接口，无需鉴权。

| # | 模块 | 接口 | 说明 |
| --- | --- | --- | --- |
| 1 | 实时行情 | `push2.eastmoney.com/api/qt/stock/get` | f-code 字段，价格类整数存储需 /100 |
| 2 | 日 K 线 | `push2his.eastmoney.com/api/qt/stock/kline/get` | `fqt=1` 前复权 |
| 3 | 资金流向 | `push2his.eastmoney.com/api/qt/stock/fflow/daykline/get` | 主力=大单+超大单，可自校验 |
| 4 | 大盘指数 | `push2.eastmoney.com/api/qt/ulist.np/get` | 上证/深成/创业板可配置 |
| 5 | 全网新闻 | `search-api-web.eastmoney.com/search/jsonp` | 聚合财联社、证券时报、中证网、上证报、每经等 |
| 6 | 公司公告 | `np-anotice-stock.eastmoney.com/api/security/ann` | 同步交易所披露 |
| 7 | 机构研报 | `reportapi.eastmoney.com/report/list` | 含 PDF 直链 |
| 8 | 股吧帖子 | `guba.eastmoney.com/list,CODE.html` | 解析页面内联 `var article_list` |
| 9 | 龙虎榜 | `datacenter-web.eastmoney.com/api/data/v1/get` | `RPT_DAILYBILLBOARD_DETAILSNEW` |
| 10 | 财务指标 | `datacenter.eastmoney.com/securities/api/data/v1/get` | `RPT_F10_FINANCE_MAINFINADATA` |
| 11 | 融资融券 | `datacenter-web.eastmoney.com/api/data/v1/get` | `RPTA_WEB_RZRQ_GGMX` |
| 12 | 股东户数 | `datacenter-web.eastmoney.com/api/data/v1/get` | `RPT_HOLDERNUMLATEST` |

### 备用源（跨厂商故障转移）

| 用途 | 主源 | 备用源 |
| --- | --- | --- |
| K 线 | 东方财富 | 腾讯 `web.ifzq.gtimg.cn`（前复权日K）→ 新浪 `money.finance.sina.com.cn` |
| 实时行情 | 东方财富 | 腾讯 `qt.gtimg.cn` |
| 大盘指数 | 东方财富 | 腾讯 `qt.gtimg.cn` |

### 三个踩过的坑（已固化在代码里）

**① `fltt=2` / `invt=2` 会改变数值口径。**
东财行情接口默认用整数存储价格（`f43=824` 表示 8.24），但一旦传 `fltt=2`，
就变成直接返回浮点数（`f43=8.24`）。两者混用会让价格**缩小 100 倍**。
本项目的选择是：**统一不传 `fltt`/`invt`，在解析层统一 `/100`**。

**② 镜像域名会返回「HTTP 200 但业务数据为空」。**
`push2delay.eastmoney.com` 对 K 线接口返回 `{"data": {"klines": []}}`，
对资金流接口却只返回最新 1 天。因此 `get_json_with_hosts()` 支持 `validator`，
按业务字段校验后再决定是否采用该镜像：

```python
# K线：必须有 klines
validator=lambda d: bool((d.get("data") or {}).get("klines"))

# 资金流：先要求 ≥5 天（拿完整历史），全失败才退而接受 1 天
rows = self._query(limit, min_days=5) or self._query(limit, min_days=1)
```

**③ 东财搜索接口单页硬上限 10 条，且 `pageIndex` 翻页有效。**
所以召回策略是「公司名 + 股票代码」双关键词 × 2 种内容类型 × 3 页 = 最多 12 次请求，
实测可召回 90+ 条历史稿件。

---

## 5. 分析层设计

### 5.1 技术指标（`analysis/indicators.py`）

纯 Python 实现，无第三方数值库依赖：

| 指标 | 参数 | 实现要点 |
| --- | --- | --- |
| MA | 5/10/20/60/120 | 滑动窗口累加，O(n) |
| EMA | 可配 | 前 n 项简单均值作种子 |
| MACD | 12/26/9 | 柱 = `2 × (DIF - DEA)`，对齐国内软件口径 |
| RSI | 6/14 | Wilder 平滑 |
| KDJ | 9/3/3 | K、D 初值 50 |
| BOLL | 20, 2σ | 总体标准差 |

`summarize_indicators()` 再派生出：均线多头/空头排列判定、量能与 5 日均量之比、
近 20/60 日高低点、当前价在 60 日区间的分位。

### 5.2 趋势研判（`analysis/trend.py`）

把 14 类信号合成为 `TrendAnalysis`：

```
均线系统 · 价格位置 · MACD · MACD柱 · RSI · KDJ · KDJ-J · 布林带
量能 · 区间位置 · 主力资金 · 资金趋势 · 融资余额 · 消息面 · 股吧人气
```

每个信号是 `Signal(name, direction, detail)`，`direction ∈ {bull, bear, neutral}`。

- **多空比** = `bull / (bull + bear) × 100`，`neutral` 不计入分母，
  避免「没数据」被误读成「看空」；
- **支撑位 / 压力位**：从均线、布林轨、区间高低点中筛出候选，
  剔除与现价距离 < 0.3% 的「伪位置」，取下方最接近的 4 个作支撑、上方 4 个作压力。

### 5.3 情绪打分（`analysis/sentiment.py`）

规则式中文财经情感分析，词表分 3 档权重（3 强 / 2 中 / 1 弱）：

- **标题权重 ×2**，正文 ×1 —— 标题是作者最强意图的表达；
- **否定词处理**：命中词前 2 个字符内出现「不 / 未 / 没有 / 无 / 非 / 难以 / 尚未」时极性反转；
- 长词优先匹配（`涨停` 不会被 `涨` 误吞）；
- 输出 `sentiment`（positive/negative/neutral）与整数 `score`，并记录命中词，
  便于在报告里回溯「为什么判成利好」。

情绪指数 = `50 + (正面数 - 负面数) / 总数 × 50`，区间 0–100，50 为中性。

> 选择规则式而非模型的原因：**可解释、零延迟、零成本**，
> 且财经新闻的多空表达高度术语化（涨停/立案/预增/质押），词表命中率足够。

---

## 6. 输出层设计

### 报告结构（9 个板块）

速览 → 行情快照 → 技术研判 → 资金面 → 全网资讯 → 近期重要事件 →
公告/研报/股吧 → 基本面 → 今日观察要点

### 新闻双层窗口

每天只有几条新闻时，纯时间窗口会让报告显得空洞；但放宽窗口又会混入大量旧闻。
解法是**双层结构**：

| 层 | 数据 | 窗口 | 排序 |
| --- | --- | --- | --- |
| 近期资讯 | `bundle.news` | 近 7 天（可配） | 公司新闻优先 → 组内时间倒序 |
| 近期重要公司事件 | `bundle.news_context` | 窗口外，池内 | 仅取标题点名公司的稿件，最多 6 条 |

**相关度分级**：标题含公司名或代码记 `relevance=2`（公司相关），
仅正文提及记 `relevance=1`（行业/榜单提及）。
证券时报的「今日 49 只个股突破半年线」这类统计稿会被正确降级，
不会挤占公司真实新闻的位置。

### HTML 邮件

- 模板在 `report/template.py` 中以内联样式书写（`<style>` 块在多数邮箱客户端会被剥离）；
- 同时输出纯文本版（Markdown 渲染结果）作为 `multipart/alternative` 的降级内容；
- 响应式宽度上限 760px，移动端可读。

---

## 7. 定时与运维

### 时间换算

GitHub Actions 的 cron 使用 **UTC**。北京时间 12:00 = UTC 04:00：

```yaml
on:
  schedule:
    - cron: "0 4 * * *"
```

### 两个已知的 GitHub 特性

| 特性 | 影响 | 应对 |
| --- | --- | --- |
| 定时任务高峰期排队 | 可能延迟 1–15 分钟 | 12:00 是午休时段，延迟不影响使用 |
| 仓库 60 天无提交则禁用定时任务 | 报告会莫名停发 | 附 `keepalive.yml`，每月自动提交一次时间戳 |

### 失败可见性

- 单源失败 → 记入 `bundle.errors` → 报告底部「本期数据缺口」区块；
- 邮件失败 → 退出码 `3`（`EXIT_MAIL_FAILED`），Actions 页面标红；
- K 线完全拿不到 → 退出码 `2`（`EXIT_FETCH_FAILED`），直接终止，不发半成品邮件。

---

## 8. 如何扩展

### 加一个数据源

1. 在 `models.py` 加数据结构（或在 `NewsItem.extra` 里塞轻量字段）；
2. 在 `fetchers/` 新建模块，继承 `Fetcher`，实现 `fetch()`，
   失败时抛 `FetchError`；
3. 在 `pipeline.collect()` 的 `jobs` 字典里注册（会自动进入并发池）；
4. 在 `report/render.py` 加视图模型，在 `template.py` 加板块。

### 加一个技术指标

1. 在 `analysis/indicators.py` 实现函数（输入 `Sequence[float]`，输出等长列表，不足处填 `None`）；
2. 在 `summarize_indicators()` 里调用并写入返回字典；
3. 在 `analysis/trend.py` 里加 `Signal` 判定；
4. 在 `tests/test_indicators.py` 补单元测试。

### 加一个推送渠道（企业微信 / 钉钉 / Server酱）

`notify/` 下新增模块，暴露与 `mailer.send_report()` 相同的签名
`(cfg, subject, html_body, text_body, attachments)`，
在 `cli.cmd_run()` 里按顺序调用。核心逻辑无需改动。

---

## 9. 测试策略

`tests/test_indicators.py` 共 21 项，覆盖：

- **指标正确性**：MA 手算对照、EMA 种子与常数序列、MACD 单边趋势符号与
  `hist = 2(DIF-DEA)` 恒等式、RSI 单调涨跌的 0/100 边界与取值范围、
  KDJ 取值范围与前置 `None`、BOLL 三轨序关系与平盘零宽度；
- **边界安全**：空输入、数据不足、极短序列不抛异常；
- **情绪打分**：正/负/中性三类判定、标题权重高于正文。

不依赖网络，`python -m unittest discover -s tests` 秒级完成。

---

## 10. 目录速查

```
src/sizhuang/
├── __init__.py          版本号
├── __main__.py          支持 python -m sizhuang
├── cli.py               run / check 两个子命令
├── config.py            YAML + 环境变量，优先级 env > yaml > default
├── http.py              HttpClient + 镜像回落 + JSONP/内联JSON解析
├── logging_setup.py     日志与 UTF-8 stdio 强制
├── models.py            全部数据类
├── pipeline.py          编排入口 collect()
├── fetchers/
│   ├── base.py          FetchContext / Fetcher / FetchError
│   ├── providers.py     腾讯、新浪适配器
│   ├── quote.py         行情 + K线 + 分时 + 指数
│   ├── fundflow.py      资金流向 + 融资融券
│   ├── news.py          新闻召回 + split_by_window
│   ├── announcement.py  公告
│   ├── research.py      研报
│   ├── guba.py          股吧
│   ├── dragon.py        龙虎榜
│   └── fundamental.py   财务 + 股东户数
├── analysis/
│   ├── indicators.py    技术指标
│   ├── trend.py         趋势研判
│   └── sentiment.py     情绪打分
├── report/
│   ├── render.py        Markdown + HTML 渲染
│   └── template.py      HTML 模板
└── notify/
    └── mailer.py        SMTP（SSL / STARTTLS）
```

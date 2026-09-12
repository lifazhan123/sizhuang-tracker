# sizhuang-tracker · 合众思壮（002383）个股观察工程

只盯**一只票**：**合众思壮（002383.SZ）**。每天自动抓取东方财富的行情、资金、公告、
研报、龙虎榜、股吧，加上全网财经媒体的相关报道，生成一份可读的走势观察报告，
并在**每天中午 12:00（北京时间）**自动发送到你的邮箱。

---

## 它能给你什么

每封邮件（也可只看仓库里的 HTML/Markdown）包含 9 个部分：

| 板块 | 内容 |
| --- | --- |
| **速览** | 一句话：收盘价、涨跌幅、主力资金、消息面情绪、多空比 |
| **行情快照** | 最新价 / 涨跌幅 / 成交额 / 换手 / 振幅 / 量比 / 市值 / PE / PB / 涨跌停价 + 大盘环境 |
| **技术研判** | 14 项信号逐条给出「偏多 / 偏空 / 中性」判断（均线排列、MACD、RSI、KDJ、布林带、量能、区间分位…） |
| **关键价位** | 自动计算支撑位与压力位，以及当前价在近 60 日区间中的分位 |
| **资金面** | 主力/超大单/大单/中单/小单净额（今日·5日·10日·20日）+ 融资余额变化 |
| **全网相关资讯** | 公司名 + 代码双关键词全网召回，按「公司相关 / 行业提及」分层、按时间倒序，带利好利空标注 |
| **近期重要公司事件** | 时间窗口外但对基本面有参考价值的稿件（中报、股权转让、股东会等） |
| **公司公告 / 机构研报 / 股吧热议** | 公告直达原文链接；研报含 PDF；股吧热帖带阅读/评论数与散户情绪统计 |
| **今日观察要点** | 支撑压力、量能异动、最新公告研报提示、基本面摘要、风险提示 |

配色遵循 A 股习惯：**上涨为红、下跌为绿**。

> ⚠️ 全部内容为公开数据的程序化统计结果，**不构成任何投资建议**。

---

## 架构总览

```
                       ┌──────────────────────────────────────┐
                       │  GitHub Actions（每天 UTC 04:00）     │
                       │  = 北京时间 12:00                     │
                       └───────────────┬──────────────────────┘
                                       ▼
                        src/sizhuang/cli.py  (run)
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  ┌───────────┐                 ┌───────────┐                 ┌───────────┐
  │ fetchers/ │  抓取层          │ analysis/ │  分析层          │ report/   │  报告层
  │           │                 │           │                 │           │
  │ 行情/K线   │                 │ 技术指标   │                 │ Markdown  │
  │ 资金流     │  ──── DailyBundle ──▶ 趋势研判 │  ──── TrendAnalysis ──▶ HTML     │
  │ 新闻/公告  │                 │ 情绪打分   │                 │ (邮件正文) │
  │ 研报/股吧  │                 │           │                 │           │
  │ 龙虎榜     │                 └───────────┘                 └─────┬─────┘
  └───────────┘                                                     │
                                                              ┌─────▼─────┐
                                                              │  notify/  │ SMTP
                                                              │  mailer   │ ──▶ 📧 你的邮箱
                                                              └───────────┘
```

详细的模块职责、数据流、数据源清单与扩展方式见 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

---

## 快速开始

### 1. 本地跑一次（不发邮件）

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml

# Linux / macOS
PYTHONPATH=src python -m sizhuang.cli run --no-mail --preview

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1 -NoMail -Preview
```

报告会生成在 `output/`：`002383_YYYYMMDD_HHMM_report.html` 与 `.md`。

### 2. 检查数据源连通性

```bash
PYTHONPATH=src python -m sizhuang.cli check
```

会逐个打印 10 个数据源的可用状态，方便排查网络问题。

### 3. 跑测试

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

---

## 配置每日 12:00 邮件推送

推荐用 **GitHub Actions**：不用开机、不用服务器、完全免费。

### 第一步：获取邮箱 SMTP 授权码

> ⚠️ 用的是**授权码**，不是邮箱登录密码。

| 邮箱 | SMTP 服务器 | 端口 | 获取授权码 |
| --- | --- | --- | --- |
| QQ 邮箱 | `smtp.qq.com` | 465 (SSL) | 设置 → 账户 → 开启「IMAP/SMTP 服务」→ 生成授权码 |
| 163 邮箱 | `smtp.163.com` | 465 (SSL) | 设置 → POP3/SMTP/IMAP → 开启服务 → 新增授权码 |
| Gmail | `smtp.gmail.com` | 587 (STARTTLS) | 开启两步验证 → 应用专用密码 |
| Outlook | `smtp.office365.com` | 587 (STARTTLS) | 账户安全 → 应用密码 |

### 第二步：在仓库里配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，
逐个添加：

| Secret 名称 | 必填 | 示例值 | 说明 |
| --- | --- | --- | --- |
| `SZ_SMTP_HOST` | ✅ | `smtp.qq.com` | SMTP 服务器 |
| `SZ_SMTP_PORT` | ✅ | `465` | 端口 |
| `SZ_SMTP_USER` | ✅ | `you@qq.com` | 登录账号 |
| `SZ_SMTP_PASSWORD` | ✅ | `abcdxyzabcdefg` | **授权码** |
| `SZ_MAIL_FROM` | ✅ | `you@qq.com` | 发件人（一般同上） |
| `SZ_MAIL_TO` | ✅ | `you@qq.com,other@163.com` | 收件人，多个用逗号分隔 |
| `SZ_MAIL_ENABLED` | ⬜ | `true` | 设为 `false` 可临时停发邮件 |

> 这些值只存在 GitHub 加密存储里，**不会**出现在代码或日志中。

### 第三步：允许 Actions 运行

**Settings → Actions → General → Workflow permissions** 选择
`Read and write permissions`（保活工作流需要）。

### 第四步：验证

**Actions → 每日个股观察报告 → Run workflow**
- 勾选 `no_mail` → 只生成报告不发邮件（先验证抓取是否正常，报告在页面底部 Artifacts 下载）
- 不勾选 → 完整流程，检查邮箱是否收到

确认无误后，定时任务会自动按 **每天 12:00（北京时间）** 运行。

### 关于时间的两点说明

1. **GitHub Actions 的 cron 用 UTC**。北京时间 12:00 = UTC 04:00，工作流里已写成 `cron: "0 4 * * *"`。
2. **可能有几分钟延迟**。GitHub 的定时任务在高峰期会排队，通常延迟 1–15 分钟属正常。
   另外 GitHub 会在仓库连续 60 天无提交时**自动禁用**定时任务 ——
   仓库里已附带 `keepalive.yml`，每月自动提交一次时间戳来防止被停用。

> 12:00 正好是 A 股午间休市（11:30–13:00），所以你收到的是**上午收盘数据**，
> 刚好可以在下午开盘前看完。

---

## 本地定时（备用方案）

不想用 GitHub 的话，可以在自己电脑上注册 Windows 计划任务：

```powershell
# 先装依赖并复制配置
pip install -r requirements.txt
copy config.example.yaml config.yaml

# 注册每天 12:00 的计划任务（管理员权限）
powershell -ExecutionPolicy Bypass -File scripts/register_windows_task.ps1

# 取消
powershell -ExecutionPolicy Bypass -File scripts/register_windows_task.ps1 -Remove
```

本地运行时，把 SMTP 信息写进 `config.yaml` 的 `mail` 段，或设为环境变量
（参见 `.env.example`）。**注意：`config.yaml` 已在 `.gitignore` 中，不会被提交。**

---

## 命令行参数

```bash
python -m sizhuang.cli run [选项]

  --no-mail     只生成报告，不发送邮件
  --preview     在终端打印 Markdown 报告
  --json        额外导出原始抓取数据（便于二次分析）
  --out DIR     指定报告输出目录

python -m sizhuang.cli check
  --json        以 JSON 输出各数据源检查结果
```

---

## 项目结构

```
sizhuang-tracker/
├── src/sizhuang/
│   ├── config.py            配置加载（YAML + 环境变量覆盖）
│   ├── http.py              HTTP 客户端：重试 / 多域名回落 / JSONP 解析
│   ├── models.py            数据模型（Quote / Bar / NewsItem / DailyBundle …）
│   ├── pipeline.py          编排：并发抓取 → 情绪打分 → 趋势研判
│   ├── cli.py               命令行入口
│   ├── fetchers/            抓取层
│   │   ├── quote.py         行情、K线、分时、指数（东财 → 腾讯 → 新浪 三级回落）
│   │   ├── providers.py     腾讯 / 新浪备用源适配器
│   │   ├── fundflow.py      主力资金流向、融资融券
│   │   ├── news.py          全网新闻召回（公司名 + 代码双关键词）
│   │   ├── announcement.py  公司公告
│   │   ├── research.py      机构研报
│   │   ├── guba.py          股吧帖子（解析页面内联 JSON）
│   │   ├── dragon.py        龙虎榜
│   │   └── fundamental.py   财务指标、股东户数
│   ├── analysis/
│   │   ├── indicators.py    MA / EMA / MACD / RSI / KDJ / BOLL（纯 Python）
│   │   ├── trend.py         多空信号合成、支撑压力位、观察要点
│   │   └── sentiment.py     中文财经文本情绪打分
│   ├── report/
│   │   ├── render.py        Markdown + HTML 双渲染
│   │   └── template.py      HTML 邮件模板（内联样式）
│   └── notify/mailer.py     SMTP 发送
├── .github/workflows/
│   ├── daily_report.yml     每天 12:00（北京时间）主任务
│   └── keepalive.yml        防止定时任务被自动禁用
├── scripts/
│   ├── run_local.ps1        本地运行
│   └── register_windows_task.ps1  Windows 计划任务
├── tests/test_indicators.py 21 项单元测试
├── config.example.yaml      配置模板
└── docs/ARCHITECTURE.md     架构与设计说明
```

---

## 换一只股票怎么办

改 `config.yaml` 即可，代码零改动：

```yaml
stock:
  code: "600519"
  name: "贵州茅台"
  market: 1          # 0 = 深市，1 = 沪市
```

`market` 决定 `secid`（沪市 `1.xxxxxx`、深市 `0.xxxxxx`）和腾讯/新浪的
`sh`/`sz` 前缀，改对就行。技术指标、涨跌停幅度（主板 10% / 创业板科创板 20%）会自适应。

---

## 常见问题

**邮件没收到？**
1. 看 Actions 页面该次运行的日志，是否有 `✗ SMTP 认证失败`；
2. 确认用的是**授权码**而不是登录密码；
3. 检查是否被丢进垃圾邮件；
4. 手动 Run workflow 时勾了 `no_mail` 就不会发信。

**报告里出现「本期数据缺口」？**
说明某个数据源当天失败。报告仍会正常发出，只是对应板块缺失，
缺口清单会列在邮件底部。单个源失败不会影响其他部分。

**某项数据一直是空的？**
- 「机构研报」为空很正常，合众思壮属于中小市值，机构覆盖少；
- 「龙虎榜」只有上榜日才有数据；
- 「资金流向」如果只取到 1 天，报告会自动说明「暂不判断趋势」，不会硬凑结论。

**K 线数据源为什么显示腾讯？**
东方财富的 `push2his` 域名在部分网络环境下会限流。程序按
`东财 → 腾讯 → 新浪` 顺序自动切换，并在日志里注明实际来源，无需干预。

---

## 免责声明

本项目仅用于个人学习与信息聚合。所有数据来自东方财富等公开接口，
不保证准确性、完整性与时效性。**输出内容不构成任何投资建议**，
据此操作的风险由使用者自行承担。

"""数据模型：各抓取器统一返回这些结构，报告层只依赖它们。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# --------------------------------------------------------------------------- #
# 行情
# --------------------------------------------------------------------------- #

@dataclass
class Bar:
    """一根 K 线。"""
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: int          # 成交量(手)
    amount: float        # 成交额(元)
    amplitude: float     # 振幅 %
    pct_chg: float       # 涨跌幅 %
    change: float        # 涨跌额
    turnover: float      # 换手率 %


@dataclass
class Quote:
    """实时/最新行情快照。"""
    code: str = ""
    name: str = ""
    price: float | None = None          # 最新价
    pct_chg: float | None = None        # 涨跌幅 %
    change: float | None = None         # 涨跌额
    open: float | None = None
    high: float | None = None
    low: float | None = None
    pre_close: float | None = None
    volume: int | None = None           # 成交量(手)
    amount: float | None = None         # 成交额(元)
    turnover: float | None = None       # 换手率 %
    amplitude: float | None = None      # 振幅 %
    pe_ttm: float | None = None
    pb: float | None = None
    total_mv: float | None = None       # 总市值
    float_mv: float | None = None       # 流通市值
    limit_up: float | None = None
    limit_down: float | None = None
    volume_ratio: float | None = None   # 量比
    updated: str = ""


@dataclass
class KlineData:
    bars: list[Bar] = field(default_factory=list)
    name: str = ""
    code: str = ""

    @property
    def latest(self) -> Bar | None:
        return self.bars[-1] if self.bars else None


# --------------------------------------------------------------------------- #
# 资金
# --------------------------------------------------------------------------- #

@dataclass
class FundFlowDay:
    date: str
    main_net: float = 0.0        # 主力净流入(元)
    small_net: float = 0.0
    medium_net: float = 0.0
    large_net: float = 0.0
    super_large_net: float = 0.0
    main_net_pct: float = 0.0    # 主力净占比 %
    small_net_pct: float = 0.0
    medium_net_pct: float = 0.0
    large_net_pct: float = 0.0
    super_large_net_pct: float = 0.0


@dataclass
class FundFlow:
    days: list[FundFlowDay] = field(default_factory=list)

    def sum_main(self, n: int) -> float:
        return sum(d.main_net for d in self.days[-n:])

    def latest(self) -> FundFlowDay | None:
        return self.days[-1] if self.days else None


@dataclass
class MarginInfo:
    date: str = ""
    financing_balance: float | None = None   # 融资余额
    securities_balance: float | None = None  # 融券余额
    total_balance: float | None = None
    financing_buy: float | None = None       # 融资买入额
    financing_repay: float | None = None     # 融资偿还额
    net_buy: float | None = None             # 融资净买入
    balance_ratio: float | None = None       # 融资余额占流通市值 %


# --------------------------------------------------------------------------- #
# 资讯
# --------------------------------------------------------------------------- #

@dataclass
class NewsItem:
    title: str = ""
    summary: str = ""
    url: str = ""
    source: str = ""
    published: str = ""
    category: str = "news"          # news / announcement / research / guba
    sentiment: str = "neutral"      # positive / negative / neutral
    sentiment_score: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchItem:
    title: str = ""
    org: str = ""
    rating: str = ""
    published: str = ""
    url: str = ""
    eps_this: str = ""
    eps_next: str = ""
    pdf: str = ""


@dataclass
class DragonTigerItem:
    date: str = ""
    reason: str = ""
    buy_amount: float | None = None
    sell_amount: float | None = None
    net_amount: float | None = None
    close_price: float | None = None
    pct_chg: float | None = None


@dataclass
class GubaPost:
    title: str = ""
    author: str = ""
    published: str = ""
    click_count: int = 0
    comment_count: int = 0
    url: str = ""
    sentiment: str = "neutral"
    sentiment_score: int = 0
    is_hot: bool = False


@dataclass
class Fundamental:
    report_name: str = ""
    report_date: str = ""
    revenue: float | None = None          # 营业总收入
    revenue_yoy: float | None = None
    net_profit: float | None = None       # 归母净利润
    net_profit_yoy: float | None = None
    eps: float | None = None
    bps: float | None = None
    roe: float | None = None
    gross_margin: float | None = None     # 销售毛利率 %
    debt_ratio: float | None = None       # 资产负债率 %
    holder_num: int | None = None
    holder_num_change_pct: float | None = None


@dataclass
class IndexQuote:
    name: str = ""
    code: str = ""
    price: float | None = None
    pct_chg: float | None = None
    change: float | None = None


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #

@dataclass
class DailyBundle:
    """一次抓取的全部原始数据。"""
    trade_date: str = ""
    generated_at: str = ""
    quote: Quote = field(default_factory=Quote)
    kline: KlineData = field(default_factory=KlineData)
    fundflow: FundFlow = field(default_factory=FundFlow)
    margin: MarginInfo = field(default_factory=MarginInfo)
    fundamental: Fundamental = field(default_factory=Fundamental)
    news: list[NewsItem] = field(default_factory=list)
    news_context: list[NewsItem] = field(default_factory=list)   # 近期重要公司事件（窗口外的重要新闻）
    announcements: list[NewsItem] = field(default_factory=list)
    research: list[ResearchItem] = field(default_factory=list)
    guba: list[GubaPost] = field(default_factory=list)
    dragon: list[DragonTigerItem] = field(default_factory=list)
    indexes: list[IndexQuote] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    news_stats: dict[str, Any] = field(default_factory=dict)
    guba_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

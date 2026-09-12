"""备用数据源适配器（腾讯 / 新浪）。

东方财富的行情域名在部分网络环境下会限流甚至不可达（push2his 尤其明显），
因此 K 线 / 实时行情 / 指数都准备了跨厂商的备用源，保证定时任务不空跑。

适配器统一输出 models 中的数据结构，调用方无需关心来源差异。
"""

from __future__ import annotations

import json
import logging
import re

from ..http import HttpClient, to_float
from ..models import Bar, IndexQuote, Quote

log = logging.getLogger(__name__)

TX_KLINE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TX_QUOTE = "https://qt.gtimg.cn/q={symbols}"
SINA_KLINE = (
    "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "CN_MarketData.getKLineData"
)
SINA_QUOTE = "https://hq.sinajs.cn/list={symbols}"

INDEX_SYMBOLS = {
    "1.000001": "sh000001",
    "0.399001": "sz399001",
    "0.399006": "sz399006",
    "0.399905": "sz399905",
    "1.000300": "sh000300",
    "1.000688": "sh000688",
}


def _prefix(code: str, market: int) -> str:
    return ("sh" if str(market) == "1" else "sz") + code


def _fill_derived(bars: list[Bar]) -> list[Bar]:
    """腾讯/新浪不提供涨跌幅、振幅，按前收盘价补算。"""
    for i, b in enumerate(bars):
        prev = bars[i - 1].close if i > 0 else None
        if prev:
            b.change = round(b.close - prev, 3)
            b.pct_chg = round(b.close / prev * 100 - 100, 2)
            b.amplitude = round((b.high - b.low) / prev * 100, 2) if prev else 0.0
    return bars


# --------------------------------------------------------------------------- #
# K 线
# --------------------------------------------------------------------------- #

def fetch_kline_tencent(client: HttpClient, code: str, market: int, days: int) -> list[Bar]:
    """腾讯前复权日K。

    返回 [日期, 开, 收, 高, 低, 成交量(手), (成交额)]，注意顺序是 开-收-高-低。
    """
    symbol = _prefix(code, market)
    data = client.get_json(
        TX_KLINE,
        params={"param": f"{symbol},day,,,{days},qfq"},
        headers={"Referer": f"https://gu.qq.com/{symbol}/gp"},
        retries=2,
    )
    node = ((data or {}).get("data") or {}).get(symbol) if isinstance(data, dict) else None
    if not node:
        return []
    rows = node.get("qfqday") or node.get("day") or []
    bars: list[Bar] = []
    for r in rows:
        if not isinstance(r, (list, tuple)) or len(r) < 6:
            continue
        volume = int(to_float(r[5], 0) or 0)
        amount = to_float(r[6], 0.0) or 0.0 if len(r) > 6 else 0.0
        bars.append(Bar(
            date=str(r[0]),
            open=to_float(r[1], 0.0) or 0.0,
            close=to_float(r[2], 0.0) or 0.0,
            high=to_float(r[3], 0.0) or 0.0,
            low=to_float(r[4], 0.0) or 0.0,
            volume=volume,
            amount=amount,
            amplitude=0.0, pct_chg=0.0, change=0.0, turnover=0.0,
        ))
    return _fill_derived(bars)


def fetch_kline_sina(client: HttpClient, code: str, market: int, days: int) -> list[Bar]:
    """新浪日K（成交量单位为股，需换算为手）。"""
    symbol = _prefix(code, market)
    txt = client.get_text(
        SINA_KLINE,
        params={"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(days)},
        headers={"Referer": "https://finance.sina.com.cn/"},
        retries=2,
    )
    if not txt:
        return []
    try:
        rows = json.loads(txt)
    except json.JSONDecodeError:
        return []
    bars: list[Bar] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        bars.append(Bar(
            date=str(r.get("day", ""))[:10],
            open=to_float(r.get("open"), 0.0) or 0.0,
            close=to_float(r.get("close"), 0.0) or 0.0,
            high=to_float(r.get("high"), 0.0) or 0.0,
            low=to_float(r.get("low"), 0.0) or 0.0,
            volume=int((to_float(r.get("volume"), 0.0) or 0.0) / 100),   # 股 -> 手
            amount=0.0,
            amplitude=0.0, pct_chg=0.0, change=0.0, turnover=0.0,
        ))
    return _fill_derived(bars)


# --------------------------------------------------------------------------- #
# 实时行情
# --------------------------------------------------------------------------- #

def fetch_quote_tencent(client: HttpClient, code: str, market: int) -> Quote | None:
    """腾讯实时行情（GBK 编码的 `v_sz002383="51~名称~代码~..."` 文本）。"""
    symbol = _prefix(code, market)
    txt = client.get_text(
        TX_QUOTE.format(symbols=symbol),
        headers={"Referer": f"https://gu.qq.com/{symbol}/gp"},
        retries=2,
    )
    if not txt or "~" not in txt:
        return None
    m = re.search(r'"([^"]+)"', txt)
    if not m:
        return None
    f = m.group(1).split("~")
    if len(f) < 35:
        return None

    def g(i: int) -> float | None:
        return to_float(f[i]) if i < len(f) else None

    price, pre_close = g(3), g(4)
    q = Quote(
        code=f[2] if len(f) > 2 else code,
        name=f[1] if len(f) > 1 else "",
        price=price,
        pre_close=pre_close,
        open=g(5),
        volume=int(g(6) or 0),
        change=g(31),
        pct_chg=g(32),
        high=g(33),
        low=g(34),
        amount=(g(37) or 0) * 1e4 if g(37) is not None else None,   # 万元 -> 元
        turnover=g(38),
        pe_ttm=g(39),
        volume_ratio=None,
    )
    if price is not None and pre_close:
        q.amplitude = round((q.high - q.low) / pre_close * 100, 2) if q.high and q.low else None
        limit = 0.20 if code.startswith(("300", "301", "688", "689")) else 0.10
        q.limit_up = round(pre_close * (1 + limit), 2)
        q.limit_down = round(pre_close * (1 - limit), 2)
    return q


# --------------------------------------------------------------------------- #
# 指数
# --------------------------------------------------------------------------- #

def fetch_index_tencent(client: HttpClient, secids: list[str]) -> list[IndexQuote]:
    """腾讯指数行情。腾讯返回单位：指数点位（无缩放）。"""
    symbols = [INDEX_SYMBOLS[s] for s in secids if s in INDEX_SYMBOLS]
    if not symbols:
        return []
    txt = client.get_text(
        TX_QUOTE.format(symbols=",".join(symbols)),
        headers={"Referer": "https://gu.qq.com/"},
        retries=2,
    )
    if not txt:
        return []
    out: list[IndexQuote] = []
    for line in txt.splitlines():
        m = re.search(r'="([^"]+)"', line)
        if not m:
            continue
        f = m.group(1).split("~")
        if len(f) < 33:
            continue
        out.append(IndexQuote(
            name=f[1],
            code=f[2],
            price=to_float(f[3]),
            change=to_float(f[31]),
            pct_chg=to_float(f[32]),
        ))
    return out

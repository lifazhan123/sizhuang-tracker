"""行情抓取：实时快照、K线、大盘指数。

主源为东方财富 push2 / push2his 公开接口；由于行情域名在部分网络环境下
存在限流，K 线 / 实时行情 / 指数均配有腾讯、新浪的备用源（见 providers.py）。
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..http import FFLOW_HOSTS, KLINE_HOSTS, QUOTE_HOSTS, to_float
from ..models import Bar, IndexQuote, KlineData, Quote
from . import providers
from .base import Fetcher, FetchError

log = logging.getLogger(__name__)

# 实时行情字段含义（东财 f-code）
QUOTE_FIELDS = ",".join([
    "f43",   # 最新价
    "f44",   # 最高
    "f45",   # 最低
    "f46",   # 今开
    "f47",   # 成交量(手)
    "f48",   # 成交额
    "f57",   # 代码
    "f58",   # 名称
    "f60",   # 昨收
    "f116",  # 总市值
    "f117",  # 流通市值
    "f162",  # 市盈率(TTM)
    "f167",  # 市净率
    "f168",  # 换手率
    "f169",  # 涨跌额
    "f170",  # 涨跌幅
    "f171",  # 振幅
    "f177",  # 量比
])

KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"

# 东财价格类字段多为整数存储，需除以 100
SCALE = 100.0


class QuoteFetcher(Fetcher):
    """实时行情快照：东方财富 → 腾讯。"""

    name = "quote"

    def fetch(self) -> Quote:
        q = self._from_eastmoney()
        if q is None:
            log.info("东财行情不可用，回落至腾讯行情")
            q = providers.fetch_quote_tencent(
                self.client, self.ctx.stock.code, self.ctx.stock.market
            )
        if q is None:
            raise FetchError("实时行情接口（东财 / 腾讯）均未返回数据")
        if not q.name:
            q.name = self.ctx.stock.name
        q.updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return q

    def _from_eastmoney(self) -> Quote | None:
        # 注意：不要传 fltt/invt —— 它们会让接口直接返回已格式化的浮点数，
        # 与下面「整数存储 / 100」的解析方式冲突，导致价格缩小 100 倍。
        data = self.client.get_json_with_hosts(
            QUOTE_HOSTS,
            "/api/qt/stock/get",
            params={"secid": self.ctx.stock.secid, "fields": QUOTE_FIELDS},
            validator=lambda d: isinstance(d, dict) and bool((d.get("data") or {}).get("f58")),
        )
        payload = (data or {}).get("data") if isinstance(data, dict) else None
        if not payload:
            return None

        def d(key: str) -> float | None:
            v = to_float(payload.get(key))
            return None if v is None else round(v / SCALE, 4)

        q = Quote(
            code=str(payload.get("f57") or self.ctx.stock.code),
            name=str(payload.get("f58") or self.ctx.stock.name),
            price=d("f43"),
            high=d("f44"),
            low=d("f45"),
            open=d("f46"),
            pre_close=d("f60"),
            volume=int(to_float(payload.get("f47"), 0) or 0),
            amount=to_float(payload.get("f48")),
            total_mv=to_float(payload.get("f116")),
            float_mv=to_float(payload.get("f117")),
            pe_ttm=d("f162"),
            pb=d("f167"),
            turnover=d("f168"),
            change=d("f169"),
            pct_chg=d("f170"),
            amplitude=d("f171"),
            volume_ratio=d("f177"),
        )
        self._apply_limits(q)
        return q

    def _apply_limits(self, q: Quote) -> None:
        if q.pre_close:
            limit = 0.20 if self._is_20pct_board() else 0.10
            q.limit_up = round(q.pre_close * (1 + limit), 2)
            q.limit_down = round(q.pre_close * (1 - limit), 2)

    def _is_20pct_board(self) -> bool:
        return self.ctx.stock.code.startswith(("300", "301", "688", "689"))


class KlineFetcher(Fetcher):
    """日K线：东方财富（前复权）→ 腾讯（前复权）→ 新浪。"""

    name = "kline"

    def fetch(self, days: int | None = None, klt: int = 101) -> KlineData:
        limit = days or self.ctx.report.kline_days
        stock = self.ctx.stock

        bars = self._from_eastmoney(limit, klt)
        source = "东方财富"
        if not bars:
            log.info("东财K线不可用，回落至腾讯")
            bars = providers.fetch_kline_tencent(self.client, stock.code, stock.market, limit)
            source = "腾讯财经"
        if not bars:
            log.info("腾讯K线不可用，回落至新浪")
            bars = providers.fetch_kline_sina(self.client, stock.code, stock.market, limit)
            source = "新浪财经"
        if not bars:
            raise FetchError("K线接口（东财 / 腾讯 / 新浪）均未返回数据")

        log.info("K线数据源：%s（%d 根）", source, len(bars))
        return KlineData(bars=bars, name=stock.name, code=stock.code)

    def _from_eastmoney(self, limit: int, klt: int) -> list[Bar]:
        data = self.client.get_json_with_hosts(
            KLINE_HOSTS,
            "/api/qt/stock/kline/get",
            params={
                "secid": self.ctx.stock.secid,
                "klt": str(klt),
                "fqt": "1",
                "lmt": str(limit),
                "end": "20500101",
                "fields1": KLINE_FIELDS1,
                "fields2": KLINE_FIELDS2,
            },
            # push2delay 会返回 HTTP 200 但 klines 为空，必须校验业务数据
            validator=lambda d: bool(((d.get("data") or {}).get("klines"))) if isinstance(d, dict) else False,
        )
        payload = (data or {}).get("data") if isinstance(data, dict) else None
        if not payload or not payload.get("klines"):
            return []
        bars: list[Bar] = []
        for row in payload["klines"]:
            p = str(row).split(",")
            if len(p) < 11:
                continue
            bars.append(Bar(
                date=p[0],
                open=to_float(p[1], 0.0) or 0.0,
                close=to_float(p[2], 0.0) or 0.0,
                high=to_float(p[3], 0.0) or 0.0,
                low=to_float(p[4], 0.0) or 0.0,
                volume=int(to_float(p[5], 0) or 0),
                amount=to_float(p[6], 0.0) or 0.0,
                amplitude=to_float(p[7], 0.0) or 0.0,
                pct_chg=to_float(p[8], 0.0) or 0.0,
                change=to_float(p[9], 0.0) or 0.0,
                turnover=to_float(p[10], 0.0) or 0.0,
            ))
        return bars


class IntradayFetcher(Fetcher):
    """当日分时（用于日内均价与强弱判断）。仅东财提供，失败不致命。"""

    name = "intraday"

    def fetch(self) -> dict:
        data = self.client.get_json_with_hosts(
            KLINE_HOSTS,
            "/api/qt/stock/trends2/get",
            params={
                "secid": self.ctx.stock.secid,
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "ndays": "1",
                "iscr": "0",
            },
            validator=lambda d: bool(((d.get("data") or {}).get("trends"))) if isinstance(d, dict) else False,
        )
        payload = (data or {}).get("data") if isinstance(data, dict) else None
        if not payload or not payload.get("trends"):
            raise FetchError("分时接口未返回数据")

        rows = [str(r).split(",") for r in payload["trends"]]
        prices = [to_float(r[2]) for r in rows if len(r) > 2 and to_float(r[2]) is not None]
        avg_prices = [to_float(r[7]) for r in rows if len(r) > 7 and to_float(r[7]) is not None]
        vols = [to_float(r[5], 0.0) or 0.0 for r in rows if len(r) > 5]

        return {
            "points": len(rows),
            "pre_close": to_float(payload.get("preClose")),
            "last_time": rows[-1][0] if rows else "",
            "last_price": prices[-1] if prices else None,
            "avg_price": avg_prices[-1] if avg_prices else None,
            "session_high": max(prices) if prices else None,
            "session_low": min(prices) if prices else None,
            "total_volume": sum(vols),
        }


class IndexFetcher(Fetcher):
    """大盘指数：东方财富 → 腾讯。"""

    name = "index"

    def fetch(self) -> list[IndexQuote]:
        secids = [i.secid for i in self.ctx.config.market_index]
        if not secids:
            return []

        out = self._from_eastmoney(secids)
        if not out:
            log.info("东财指数不可用，回落至腾讯")
            out = providers.fetch_index_tencent(self.client, secids)
        if not out:
            raise FetchError("指数接口（东财 / 腾讯）均未返回数据")
        return out

    def _from_eastmoney(self, secids: list[str]) -> list[IndexQuote]:
        # 同样不传 fltt/invt，保持与 /100 解析一致
        data = self.client.get_json_with_hosts(
            QUOTE_HOSTS,
            "/api/qt/ulist.np/get",
            params={"secids": ",".join(secids), "fields": "f2,f3,f4,f12,f14"},
            validator=lambda d: bool(((d.get("data") or {}).get("diff"))) if isinstance(d, dict) else False,
        )
        diff = ((data or {}).get("data") or {}).get("diff") if isinstance(data, dict) else None
        if not diff:
            return []
        out: list[IndexQuote] = []
        for item in diff:
            price, pct, chg = to_float(item.get("f2")), to_float(item.get("f3")), to_float(item.get("f4"))
            out.append(IndexQuote(
                name=str(item.get("f14", "")),
                code=str(item.get("f12", "")),
                price=round(price / SCALE, 2) if price is not None else None,
                pct_chg=round(pct / SCALE, 2) if pct is not None else None,
                change=round(chg / SCALE, 2) if chg is not None else None,
            ))
        return out

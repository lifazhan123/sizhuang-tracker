"""资金面抓取：主力资金流向、融资融券。"""

from __future__ import annotations

import logging

from ..http import FFLOW_HOSTS, to_float
from ..models import FundFlow, FundFlowDay, MarginInfo
from .base import Fetcher, FetchError

log = logging.getLogger(__name__)

FFLOW_FIELDS1 = "f1,f2,f3,f7"
FFLOW_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"

DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"


class FundFlowFetcher(Fetcher):
    """个股主力资金流向（日频）。

    返回行格式：
      日期, 主力净流入, 小单净流入, 中单净流入, 大单净流入, 超大单净流入,
      主力净占比, 小单占比, 中单占比, 大单占比, 超大单占比, 收盘价, 涨跌幅, -, -
    """

    name = "fundflow"

    def fetch(self, days: int | None = None) -> FundFlow:
        limit = days or self.ctx.report.fundflow_days
        # 两轮：先要求拿到足够历史（push2his），全部镜像都只给 1 天时
        # 再退而求其次接受单日数据（push2delay），保证报告不致完全缺失资金面。
        rows = self._query(limit, min_days=5) or self._query(limit, min_days=1)
        if not rows:
            raise FetchError("资金流向接口未返回数据")

        days_out: list[FundFlowDay] = []
        for p in rows:
            if len(p) < 13:
                continue
            days_out.append(FundFlowDay(
                date=p[0],
                main_net=to_float(p[1], 0.0) or 0.0,
                small_net=to_float(p[2], 0.0) or 0.0,
                medium_net=to_float(p[3], 0.0) or 0.0,
                large_net=to_float(p[4], 0.0) or 0.0,
                super_large_net=to_float(p[5], 0.0) or 0.0,
                main_net_pct=to_float(p[6], 0.0) or 0.0,
                small_net_pct=to_float(p[7], 0.0) or 0.0,
                medium_net_pct=to_float(p[8], 0.0) or 0.0,
                large_net_pct=to_float(p[9], 0.0) or 0.0,
                super_large_net_pct=to_float(p[10], 0.0) or 0.0,
            ))
        if not days_out:
            raise FetchError("资金流向解析后为空")
        if len(days_out) < 5:
            log.warning("资金流向仅获取到 %d 天数据，统计口径将随之缩短", len(days_out))
        return FundFlow(days=days_out)

    def _query(self, limit: int, min_days: int) -> list[str]:
        data = self.client.get_json_with_hosts(
            FFLOW_HOSTS,
            "/api/qt/stock/fflow/daykline/get",
            params={
                "secid": self.ctx.stock.secid,
                "lmt": str(limit),
                "klt": "101",
                "fields1": FFLOW_FIELDS1,
                "fields2": FFLOW_FIELDS2,
            },
            validator=lambda d: (
                isinstance(d, dict)
                and len(((d.get("data") or {}).get("klines")) or []) >= min_days
            ),
        )
        payload = (data or {}).get("data") if isinstance(data, dict) else None
        if not payload or not payload.get("klines"):
            return []
        return [str(r).split(",") for r in payload["klines"]]


class MarginFetcher(Fetcher):
    """融资融券明细。融资余额变化是观察杠杆资金态度的重要指标。"""

    name = "margin"

    def fetch(self, page_size: int = 5) -> MarginInfo:
        data = self.client.get_json(
            DATACENTER,
            params={
                "sortColumns": "DATE",
                "sortTypes": "-1",
                "pageSize": str(page_size),
                "pageNumber": "1",
                "reportName": "RPTA_WEB_RZRQ_GGMX",
                "columns": "ALL",
                "source": "WEB",
                "client": "WEB",
                "filter": f'(SCODE="{self.ctx.stock.code}")',
            },
        )
        rows = ((data or {}).get("result") or {}).get("data") if isinstance(data, dict) else None
        if not rows:
            log.info("融资融券数据为空（该股可能非两融标的）")
            return MarginInfo()

        r = rows[0]
        return MarginInfo(
            date=str(r.get("DATE", ""))[:10],
            financing_balance=to_float(r.get("RZYE")),
            securities_balance=to_float(r.get("RQYE")),
            total_balance=to_float(r.get("RZRQYE")),
            financing_buy=to_float(r.get("RZMRE")),
            financing_repay=to_float(r.get("RZCHE")),
            net_buy=to_float(r.get("RZJME")),
            balance_ratio=to_float(r.get("RZYEZB")),
        )

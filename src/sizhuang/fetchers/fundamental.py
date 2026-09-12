"""基本面抓取：主要财务指标 + 股东户数。"""

from __future__ import annotations

import logging

from ..http import to_float
from ..models import Fundamental
from .base import Fetcher

log = logging.getLogger(__name__)

DATACENTER_SEC = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
DATACENTER_WEB = "https://datacenter-web.eastmoney.com/api/data/v1/get"


class FundamentalFetcher(Fetcher):
    """最新一期财报主要指标 + 股东户数变化。"""

    name = "fundamental"

    def fetch(self) -> Fundamental:
        f = Fundamental()
        self._fill_finance(f)
        self._fill_holders(f)
        return f

    def _fill_finance(self, f: Fundamental) -> None:
        data = self.client.get_json(
            DATACENTER_SEC,
            params={
                "reportName": "RPT_F10_FINANCE_MAINFINADATA",
                "columns": "ALL",
                "quoteColumns": "",
                "filter": f'(SECUCODE="{self.ctx.stock.secucode}")',
                "pageNumber": "1",
                "pageSize": "1",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC",
            },
            headers={"Referer": f"https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code={self.ctx.stock.secucode}"},
        )
        rows = ((data or {}).get("result") or {}).get("data") if isinstance(data, dict) else None
        if not rows:
            log.info("财务指标数据为空")
            return
        r = rows[0]
        f.report_name = str(r.get("REPORT_DATE_NAME") or r.get("REPORT_TYPE") or "")
        f.report_date = str(r.get("REPORT_DATE") or "")[:10]
        f.revenue = to_float(r.get("TOTALOPERATEREVE"))
        f.revenue_yoy = to_float(r.get("TOTALOPERATEREVETZ"))
        f.net_profit = to_float(r.get("PARENTNETPROFIT"))
        f.net_profit_yoy = to_float(r.get("PARENTNETPROFITTZ"))
        f.eps = to_float(r.get("EPSJB"))
        f.bps = to_float(r.get("BPS"))
        f.roe = to_float(r.get("ROEJQ"))
        f.gross_margin = to_float(r.get("XSMLL"))
        f.debt_ratio = to_float(r.get("ZCFZL"))

    def _fill_holders(self, f: Fundamental) -> None:
        data = self.client.get_json(
            DATACENTER_WEB,
            params={
                "sortColumns": "END_DATE",
                "sortTypes": "-1",
                "pageSize": "2",
                "pageNumber": "1",
                "reportName": "RPT_HOLDERNUMLATEST",
                "columns": "ALL",
                "source": "WEB",
                "client": "WEB",
                "filter": f'(SECURITY_CODE="{self.ctx.stock.code}")',
            },
            headers={"Referer": "https://data.eastmoney.com/gdhs/"},
        )
        rows = ((data or {}).get("result") or {}).get("data") if isinstance(data, dict) else None
        if not rows:
            return
        r = rows[0]
        f.holder_num = int(to_float(r.get("HOLDER_NUM"), 0) or 0) or None
        cur = to_float(r.get("HOLDER_NUM"))
        prev = to_float(r.get("PRE_HOLDER_NUM"))
        if cur and prev:
            f.holder_num_change_pct = round((cur - prev) / prev * 100, 2)

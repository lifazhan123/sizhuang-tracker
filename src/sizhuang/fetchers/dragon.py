"""龙虎榜抓取：个股上榜记录（游资 / 机构席位动向）。"""

from __future__ import annotations

import logging

from ..http import to_float
from ..models import DragonTigerItem
from .base import Fetcher

log = logging.getLogger(__name__)

DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"


class DragonFetcher(Fetcher):
    """近一年龙虎榜上榜记录。非热门股可能长期不上榜，属正常。"""

    name = "dragon"

    def fetch(self, limit: int = 10) -> list[DragonTigerItem]:
        data = self.client.get_json(
            DATACENTER,
            params={
                "sortColumns": "TRADE_DATE",
                "sortTypes": "-1",
                "pageSize": str(limit),
                "pageNumber": "1",
                "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
                "columns": "ALL",
                "source": "WEB",
                "client": "WEB",
                "filter": f'(SECURITY_CODE="{self.ctx.stock.code}")',
            },
            headers={"Referer": "https://data.eastmoney.com/stock/lhb.html"},
        )
        rows = ((data or {}).get("result") or {}).get("data") if isinstance(data, dict) else None
        if not rows:
            return []

        out: list[DragonTigerItem] = []
        for r in rows:
            out.append(DragonTigerItem(
                date=str(r.get("TRADE_DATE") or "")[:10],
                reason=str(r.get("EXPLANATION") or r.get("EXPLAIN") or ""),
                buy_amount=to_float(r.get("BILLBOARD_BUY_AMT")),
                sell_amount=to_float(r.get("BILLBOARD_SELL_AMT")),
                net_amount=to_float(r.get("BILLBOARD_NET_AMT")),
                close_price=to_float(r.get("CLOSE_PRICE")),
                pct_chg=to_float(r.get("CHANGE_RATE")),
            ))
        return out

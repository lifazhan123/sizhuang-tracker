"""研报抓取：东方财富研报中心。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from ..http import parse_jsonp
from ..models import ResearchItem
from .base import Fetcher

log = logging.getLogger(__name__)

REPORT_API = "https://reportapi.eastmoney.com/report/list"
REPORT_DETAIL = "https://data.eastmoney.com/report/info/{info_code}.html"
REPORT_PDF = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"


class ResearchFetcher(Fetcher):
    """机构研报列表。冷门股研报可能很少甚至为 0，属正常情况。"""

    name = "research"

    def fetch(self, limit: int | None = None, years: int = 3) -> list[ResearchItem]:
        n = limit or self.ctx.report.research_limit
        begin = (datetime.now() - timedelta(days=365 * years)).strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        txt = self.client.get_text(
            REPORT_API,
            params={
                "cb": "cb",
                "industryCode": "*",
                "pageSize": str(n),
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": begin,
                "endTime": end,
                "pageNo": "1",
                "fields": "",
                "qType": "0",
                "orgCode": "",
                "code": self.ctx.stock.code,
                "rcode": "",
                "p": "1",
                "pageNum": "1",
                "pageNumber": "1",
            },
            headers={"Referer": "https://data.eastmoney.com/report/"},
        )
        payload = parse_jsonp(txt)
        rows = (payload or {}).get("data") if isinstance(payload, dict) else None
        if not rows:
            return []

        out: list[ResearchItem] = []
        for r in rows:
            info_code = str(r.get("infoCode") or "")
            out.append(ResearchItem(
                title=str(r.get("title") or "").strip(),
                org=str(r.get("orgSName") or r.get("orgName") or ""),
                rating=str(r.get("emRatingName") or r.get("sRatingName") or ""),
                published=str(r.get("publishDate") or "")[:10],
                url=REPORT_DETAIL.format(info_code=info_code) if info_code else "",
                eps_this=str(r.get("predictThisYearEps") or r.get("predictNextTwoYearEps") or ""),
                eps_next=str(r.get("predictNextYearEps") or ""),
                pdf=REPORT_PDF.format(info_code=info_code) if info_code else "",
            ))
        return out

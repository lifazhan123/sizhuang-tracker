"""公告抓取：东方财富公告接口（同步自交易所披露）。"""

from __future__ import annotations

import logging

from ..models import NewsItem
from .base import Fetcher, FetchError

log = logging.getLogger(__name__)

ANN_API = "https://np-anotice-stock.eastmoney.com/api/security/ann"
ANN_DETAIL = "https://data.eastmoney.com/notices/detail/{code}/{art_code}.html"


def _fmt_time(raw) -> str:
    """公告时间形如 `2026-09-11 20:43:10:775` 或 `2026-09-12 00:00:00`，统一为 `YYYY-MM-DD HH:MM:SS`。"""
    s = str(raw or "").strip()
    if not s:
        return ""
    parts = s.split(":")
    if len(parts) > 3:  # 去掉毫秒段
        s = ":".join(parts[:3])
    return s[:19]


class AnnouncementFetcher(Fetcher):
    """最近公告列表。"""

    name = "announcement"

    def fetch(self, limit: int | None = None) -> list[NewsItem]:
        n = limit or self.ctx.report.announce_limit
        data = self.client.get_json(
            ANN_API,
            params={
                "sr": "-1",
                "page_size": str(n),
                "page_index": "1",
                "ann_type": "A",
                "client_source": "web",
                "stock_list": self.ctx.stock.code,
                "f_node": "0",
                "s_node": "0",
            },
            headers={"Referer": f"https://data.eastmoney.com/notices/stock/{self.ctx.stock.code}.html"},
        )
        rows = ((data or {}).get("data") or {}).get("list") if isinstance(data, dict) else None
        if not rows:
            raise FetchError("公告接口未返回数据")

        out: list[NewsItem] = []
        for r in rows:
            art = str(r.get("art_code") or "")
            cols = r.get("columns") or []
            col_name = cols[0].get("column_name", "") if cols else ""
            out.append(NewsItem(
                title=str(r.get("title") or "").strip(),
                summary="",
                url=ANN_DETAIL.format(code=self.ctx.stock.code, art_code=art) if art else "",
                source="东方财富·公告",
                published=_fmt_time(r.get("display_time") or r.get("notice_date")),
                category="announcement",
                extra={"column": col_name, "art_code": art},
            ))
        return out

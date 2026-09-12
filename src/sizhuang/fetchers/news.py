"""资讯抓取：全网新闻（东方财富聚合搜索）。

东方财富的搜索接口 `search-api-web.eastmoney.com/search/jsonp` 会把
全市场财经媒体的相关报道聚合起来（财联社、证券时报、上海证券报、
中国证券报、每日经济新闻 等），是「全网相关新闻」性价比最高的免费源。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta

from ..http import parse_jsonp
from ..models import NewsItem
from .base import Fetcher, FetchError

log = logging.getLogger(__name__)

SEARCH_API = "https://search-api-web.eastmoney.com/search/jsonp"

# 可用 type：cmsArticleWebOld / cmsArticleWeb（均为全站文章聚合）
SEARCH_TYPES = ["cmsArticleWebOld", "cmsArticleWeb"]

_TAG_RE = re.compile(r"<[^>]+>")
_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def clean_html(text: str | None) -> str:
    """去掉搜索高亮 <em> 等标签并压缩空白。"""
    if not text:
        return ""
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text)).strip()


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(value[: len(fmt) + 2].strip(), fmt)
        except ValueError:
            continue
    return None


def is_within(published: str, cutoff: datetime) -> bool:
    dt = parse_time(published)
    return dt is not None and dt >= cutoff


def split_by_window(
    items: list[NewsItem],
    recent_days: int,
    recent_limit: int,
    context_limit: int,
) -> tuple[list[NewsItem], list[NewsItem]]:
    """把新闻池切成 (近期资讯, 近期重要公司事件)。

    - 近期资讯：窗口内的全部条目，按现有排序（公司新闻优先 + 时间倒序）
    - 近期重要公司事件：窗口之外、标题直接点名公司的重要稿件，用于补足背景
    """
    cutoff = datetime.now() - timedelta(days=recent_days)
    recent = [x for x in items if is_within(x.published, cutoff)]
    older = [x for x in items if not is_within(x.published, cutoff)]
    context = [x for x in older if x.extra.get("relevance") == 2][:context_limit]
    return recent[:recent_limit], context


POOL_MAX = 150


class NewsFetcher(Fetcher):
    """关键词全网新闻搜索。

    东方财富搜索接口单页最多返回 10 条，因此这里用
    「公司名 + 股票代码」双关键词 × 多种内容类型 × 多页 的方式扩大召回。

    `fetch()` 返回的是一个「新闻池」（默认回溯 news_history_days 天），
    由 `split_by_window()` 再切分为「近期资讯」与「近期重要公司事件」。
    """

    name = "news"
    MAX_PAGES = 3

    def fetch(
        self,
        keyword: str | None = None,
        limit: int | None = None,
        days: int | None = None,
    ) -> list[NewsItem]:
        kw = keyword or self.ctx.stock.name
        cap = limit or POOL_MAX
        window_days = days if days is not None else self.ctx.report.news_history_days
        cutoff = datetime.now() - timedelta(days=window_days)

        keywords = [kw, self.ctx.stock.code]
        collected: dict[str, NewsItem] = {}
        for word in keywords:
            for t in SEARCH_TYPES:
                for page in range(1, self.MAX_PAGES + 1):
                    batch = self._search_one(word, t, page_size=10, page_index=page)
                    if not batch:
                        break
                    for it in batch:
                        key = it.url or it.title
                        if key and key not in collected:
                            collected[key] = it
                    if len(batch) < 10:   # 已经到底
                        break

        items = list(collected.values())
        if not items:
            raise FetchError(f"未搜索到「{kw}」相关新闻")

        # 时间倒序；窗口内有数据则收窄到窗口内，否则保留全量（保住可用性）
        items.sort(key=lambda x: x.published or "", reverse=True)
        recent = [x for x in items if self._within(x.published, cutoff)]
        if recent:
            items = recent

        # 只保留与股票相关的
        related = [x for x in items if self._is_related(x, kw)]
        items = related or items

        for it in items:
            it.extra["relevance"] = self._relevance(it, kw)

        # 公司新闻优先，组内按时间倒序（利用稳定排序做两级排序）
        items.sort(key=lambda x: x.published or "", reverse=True)
        items.sort(key=lambda x: int(x.extra.get("relevance", 1)), reverse=True)
        return items[:cap]

    # -- 内部 ------------------------------------------------------------- #
    def _search_one(self, keyword: str, type_: str, page_size: int, page_index: int) -> list[NewsItem]:
        param = {
            "uid": "",
            "keyword": keyword,
            "type": [type_],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                type_: {
                    "searchScope": "default",
                    "sort": "time",
                    "pageIndex": page_index,
                    "pageSize": page_size,
                    "preTag": "",
                    "postTag": "",
                }
            },
        }
        txt = self.client.get_text(
            SEARCH_API,
            params={"cb": "cb", "param": json.dumps(param, ensure_ascii=False)},
            headers={"Referer": "https://so.eastmoney.com/"},
        )
        payload = parse_jsonp(txt)
        if not isinstance(payload, dict):
            return []
        rows = ((payload.get("result") or {}).get(type_)) or []
        out: list[NewsItem] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            out.append(NewsItem(
                title=clean_html(r.get("title")),
                summary=clean_html(r.get("content"))[:400],
                url=str(r.get("url") or ""),
                source=str(r.get("mediaName") or "东方财富"),
                published=str(r.get("date") or ""),
                category="news",
                extra={"article_code": r.get("code", "")},
            ))
        return out

    @staticmethod
    def _within(published: str, cutoff: datetime) -> bool:
        return is_within(published, cutoff)

    def _is_related(self, item: NewsItem, keyword: str) -> bool:
        blob = f"{item.title}{item.summary}"
        return keyword in blob or self.ctx.stock.code in blob

    def _relevance(self, item: NewsItem, keyword: str) -> int:
        """2 = 标题点名公司；1 = 仅在正文（通常是行业/榜单统计稿）中被提及。"""
        title = item.title or ""
        if keyword in title or self.ctx.stock.code in title:
            return 2
        return 1

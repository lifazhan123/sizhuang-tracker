"""股吧抓取：东方财富股吧帖子（人气 / 情绪面）。

股吧列表页是前端渲染的，但页面尾部内联了 `var article_list={...}`，
包含每帖的标题、阅读数、评论数、发布时间、作者，直接解析即可，无需浏览器。
"""

from __future__ import annotations

import logging

from ..http import parse_html_json_var
from ..models import GubaPost
from .base import Fetcher, FetchError

log = logging.getLogger(__name__)

GUBA_LIST = "https://guba.eastmoney.com/list,{code}.html"
GUBA_POST = "https://guba.eastmoney.com/news,{code},{post_id}.html"


class GubaFetcher(Fetcher):
    """股吧帖子列表。"""

    name = "guba"

    def fetch(self, limit: int | None = None) -> list[GubaPost]:
        n = limit or self.ctx.report.guba_limit
        code = self.ctx.stock.code
        html = self.client.get_text(
            GUBA_LIST.format(code=code),
            headers={"Referer": "https://guba.eastmoney.com/", "Accept": "text/html,application/xhtml+xml"},
        )
        payload = parse_html_json_var(html, "var article_list")
        rows = (payload or {}).get("re") if isinstance(payload, dict) else None
        if not rows:
            raise FetchError("股吧页面未解析到帖子数据")

        posts: list[GubaPost] = []
        for r in rows[:n]:
            if not isinstance(r, dict):
                continue
            pid = r.get("post_id")
            posts.append(GubaPost(
                title=str(r.get("post_title") or "").strip(),
                author=str(r.get("user_nickname") or ""),
                published=str(r.get("post_publish_time") or ""),
                click_count=int(r.get("post_click_count") or 0),
                comment_count=int(r.get("post_comment_count") or 0),
                url=GUBA_POST.format(code=code, post_id=pid) if pid else "",
                is_hot=bool(r.get("post_top_status")),
            ))
        if not posts:
            raise FetchError("股吧帖子解析后为空")
        return posts

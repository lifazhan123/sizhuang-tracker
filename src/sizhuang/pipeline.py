"""编排层：调度所有抓取器 → 情绪打分 → 趋势研判 → 产出完整数据包。"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable

from .analysis import analyze_trend, score_items
from .analysis.sentiment import score_text
from .analysis.trend import TrendAnalysis
from .config import AppConfig
from .fetchers.announcement import AnnouncementFetcher
from .fetchers.base import FetchContext, FetchError
from .fetchers.dragon import DragonFetcher
from .fetchers.fundamental import FundamentalFetcher
from .fetchers.fundflow import FundFlowFetcher, MarginFetcher
from .fetchers.guba import GubaFetcher
from .fetchers.news import NewsFetcher, split_by_window
from .fetchers.quote import IndexFetcher, KlineFetcher, QuoteFetcher
from .fetchers.research import ResearchFetcher
from .http import HttpClient
from .models import DailyBundle

log = logging.getLogger(__name__)


def build_context(config: AppConfig) -> FetchContext:
    return FetchContext(config=config, client=HttpClient(referer="https://quote.eastmoney.com/"))


def collect(config: AppConfig) -> tuple[DailyBundle, TrendAnalysis]:
    """执行一次完整抓取与分析。

    任何单个数据源失败都不会中断整体流程，失败信息记录到 `bundle.errors`，
    并在报告中以「数据缺口」形式提示。
    """
    ctx = build_context(config)
    bundle = DailyBundle(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        trade_date=datetime.now().strftime("%Y-%m-%d"),
    )

    def guard(label: str, fn: Callable, default):
        try:
            return fn()
        except FetchError as exc:
            log.warning("[%s] 抓取失败: %s", label, exc)
            bundle.errors.append(f"{label}: {exc}")
        except Exception as exc:  # noqa: BLE001 - 单点失败不应中断整体
            log.exception("[%s] 未预期异常", label)
            bundle.errors.append(f"{label}: {type(exc).__name__} {exc}")
        return default

    # ---- 串行抓取核心行情（后续依赖它确定交易日）----
    bundle.quote = guard("实时行情", QuoteFetcher(ctx).fetch, bundle.quote)
    bundle.kline = guard("K线", KlineFetcher(ctx).fetch, bundle.kline)

    if bundle.kline.bars:
        bundle.trade_date = bundle.kline.bars[-1].date

    # ---- 并发抓取其余数据源 ----
    jobs = {
        "资金流向": lambda: FundFlowFetcher(ctx).fetch(),
        "融资融券": lambda: MarginFetcher(ctx).fetch(),
        "财务指标": lambda: FundamentalFetcher(ctx).fetch(),
        "全网新闻": lambda: NewsFetcher(ctx).fetch(),
        "公司公告": lambda: AnnouncementFetcher(ctx).fetch(),
        "机构研报": lambda: ResearchFetcher(ctx).fetch(),
        "股吧帖子": lambda: GubaFetcher(ctx).fetch(),
        "龙虎榜": lambda: DragonFetcher(ctx).fetch(),
        "大盘指数": lambda: IndexFetcher(ctx).fetch(),
    }

    results: dict[str, object] = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(guard, name, fn, None): name for name, fn in jobs.items()}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

    bundle.fundflow = results.get("资金流向") or bundle.fundflow
    bundle.margin = results.get("融资融券") or bundle.margin
    bundle.fundamental = results.get("财务指标") or bundle.fundamental
    bundle.announcements = results.get("公司公告") or []
    bundle.research = results.get("机构研报") or []
    bundle.guba = results.get("股吧帖子") or []
    bundle.dragon = results.get("龙虎榜") or []
    bundle.indexes = results.get("大盘指数") or []

    # ---- 新闻池切分为「近期资讯」+「近期重要公司事件」----
    pool = results.get("全网新闻") or []
    bundle.news, bundle.news_context = split_by_window(
        pool,
        recent_days=config.report.news_days,
        recent_limit=config.report.news_limit,
        context_limit=config.report.news_context_limit,
    )

    # ---- 情绪打分 ----
    bundle.news_stats = score_items(bundle.news) if bundle.news else {}
    if bundle.announcements:
        for a in bundle.announcements:
            sentiment, score, hits = score_text(a.title)
            a.sentiment, a.sentiment_score = sentiment, score
            if hits:
                a.extra["sentiment_hits"] = hits
    if bundle.guba:
        for p in bundle.guba:
            sentiment, score, hits = score_text(p.title)
            p.sentiment, p.sentiment_score = sentiment, score
        bundle.guba_stats = score_items(bundle.guba)

    # 记录数据缺口
    for label, value in (
        ("全网新闻", bundle.news), ("公司公告", bundle.announcements),
        ("股吧帖子", bundle.guba), ("大盘指数", bundle.indexes),
    ):
        if not value and not any(label in e for e in bundle.errors):
            bundle.errors.append(f"{label}: 无数据")

    # ---- 趋势研判 ----
    trend = analyze_trend(bundle)

    ctx.client.close()
    log.info("抓取完成：新闻 %d 条 / 公告 %d 条 / 股吧 %d 条 / 研报 %d 篇 / 缺口 %d 项",
             len(bundle.news), len(bundle.announcements), len(bundle.guba),
             len(bundle.research), len(bundle.errors))
    return bundle, trend

"""渲染层：把 DailyBundle + TrendAnalysis 渲染为 Markdown / HTML。

配色遵循 A 股习惯：**上涨为红、下跌为绿**。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Template

from ..analysis.trend import TrendAnalysis, _fmt_yi
from ..models import DailyBundle
from .template import HTML_TEMPLATE

UP = "#dc2626"      # 红 —— 涨
DOWN = "#16a34a"    # 绿 —— 跌
FLAT = "#6b7280"    # 灰 —— 平


def _color(v: float | None) -> str:
    if v is None or v == 0:
        return FLAT
    return UP if v > 0 else DOWN


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%"


def _num(v: float | None, nd: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{nd}f}"


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.2f}万亿"
    if a >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if a >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.0f}"


_SENTIMENT_BADGE = {
    "positive": ("利好", "#fee2e2", "#b91c1c"),
    "negative": ("利空", "#dcfce7", "#15803d"),
    "neutral": ("中性", "#f3f4f6", "#4b5563"),
}

_DIRECTION_LABEL = {"bull": "偏多", "bear": "偏空", "neutral": "中性"}


def _badge(sentiment: str) -> tuple[str, str, str]:
    return _SENTIMENT_BADGE.get(sentiment, _SENTIMENT_BADGE["neutral"])


# --------------------------------------------------------------------------- #
# 视图模型
# --------------------------------------------------------------------------- #

def _build_context(bundle: DailyBundle, trend: TrendAnalysis, subject: str) -> dict:
    q, ind = bundle.quote, trend.indicators
    last = bundle.kline.latest
    chg = q.pct_chg if q.pct_chg is not None else (last.pct_chg if last else None)
    chg_color = _color(chg)

    # ---- 速览句 ----
    bits: list[str] = []
    if last:
        verb = "上涨" if (chg or 0) > 0 else ("下跌" if (chg or 0) < 0 else "收平")
        bits.append(f"收盘 <b>{last.close:.2f}</b> 元，{verb} <b>{_pct(chg)}</b>")
        # 腾讯/新浪备用源的日K不含成交额/换手率（为 0），优先取实时快照
        amt = q.amount if q.amount else ((last.amount or None) if last else None)
        tov = q.turnover if q.turnover else ((last.turnover or None) if last else None)
        bits.append(f"成交 {_money(amt)}，换手 {tov:.2f}%" if amt or tov else "成交 —，换手 —")
    if bundle.fundflow.days:
        m = bundle.fundflow.days[-1].main_net
        bits.append(f"主力{'净流入' if m >= 0 else '净流出'} <b>{_fmt_yi(abs(m))}</b>")
    if bundle.news_stats.get("total"):
        bits.append(f"消息面情绪 <b>{bundle.news_stats['index']}</b>（{bundle.news_stats['label']}）")
    headline = "；".join(bits) + f"。技术面多空比 {trend.score}:{100 - trend.score}，短期**{trend.label}**。"

    # ---- 行情快照 ----
    quote_vm = {
        "price": _num(q.price if q.price is not None else (last.close if last else None)),
        "pct_chg_str": _pct(chg),
        "amount_str": _money(q.amount if q.amount else ((last.amount or None) if last else None)),
        "turnover_str": (f"{tov:.2f}%" if (tov := (q.turnover if q.turnover else ((last.turnover or None) if last else None))) is not None else "—"),
        "open": _num(q.open if q.open is not None else (last.open if last else None)),
        "high": _num(q.high if q.high is not None else (last.high if last else None)),
        "low": _num(q.low if q.low is not None else (last.low if last else None)),
        "pre_close": _num(q.pre_close if q.pre_close is not None else (last.open if last else None)),
        "amplitude_str": f"{(q.amplitude or 0):.2f}%" if q.amplitude is not None else "—",
        "volume_ratio_str": _num(q.volume_ratio),
        "total_mv_str": _money(q.total_mv),
        "float_mv_str": _money(q.float_mv),
        "pe_str": _num(q.pe_ttm),
        "pb_str": _num(q.pb),
        "limit_up": _num(q.limit_up),
        "limit_down": _num(q.limit_down),
    }

    signals_vm = [
        {
            "name": s.name,
            "detail": s.detail,
            "label": _DIRECTION_LABEL[s.direction],
            "color": {"bull": UP, "bear": DOWN, "neutral": FLAT}[s.direction],
        }
        for s in trend.signals
    ]

    # ---- 资金面 ----
    def agg(n: int) -> dict | None:
        days = bundle.fundflow.days[-n:] if bundle.fundflow.days else []
        if not days:
            return None
        return {
            "main": sum(d.main_net for d in days),
            "super_large": sum(d.super_large_net for d in days),
            "large": sum(d.large_net for d in days),
            "medium": sum(d.medium_net for d in days),
            "small": sum(d.small_net for d in days),
        }

    fundflow_rows: list[dict] = []
    for label, n in (("今日", 1), ("近5日", 5), ("近10日", 10), ("近20日", 20)):
        a = agg(n)
        if not a:
            continue
        if n > 1 and len(bundle.fundflow.days) < n:
            continue
        fundflow_rows.append({
            "label": label,
            "main": _fmt_yi(a["main"]),
            "color": _color(a["main"]),
            "super_large": _fmt_yi(a["super_large"]),
            "super_color": _color(a["super_large"]),
            "large": _fmt_yi(a["large"]),
            "large_color": _color(a["large"]),
            "medium": _fmt_yi(a["medium"]),
            "medium_color": _color(a["medium"]),
            "small": _fmt_yi(a["small"]),
            "small_color": _color(a["small"]),
        })

    margin_line = ""
    mg = bundle.margin
    if mg.date:
        margin_line = (f"{mg.date} 融资余额 {_fmt_yi(mg.financing_balance)}"
                       f"（占流通市值 {mg.balance_ratio:.2f}%）" if mg.balance_ratio is not None
                       else f"{mg.date} 融资余额 {_fmt_yi(mg.financing_balance)}")
        if mg.net_buy is not None:
            margin_line += f"，当日融资{'净买入' if mg.net_buy >= 0 else '净卖出'} {_fmt_yi(abs(mg.net_buy))}"

    def _news_vm(items):
        out = []
        for n in items:
            label, bg, fg = _badge(n.sentiment)
            direct = n.extra.get("relevance", 1) == 2
            out.append({
                "title": n.title, "summary": n.summary, "url": n.url,
                "source": n.source, "published": n.published,
                "sentiment_label": label, "badge_bg": bg, "badge_fg": fg,
                "scope_label": "公司相关" if direct else "行业提及",
                "scope_bg": "#dbeafe" if direct else "#f3f4f6",
                "scope_fg": "#1d4ed8" if direct else "#6b7280",
            })
        return out

    news_vm = _news_vm(bundle.news)
    news_context_vm = _news_vm(bundle.news_context)

    ann_vm = []
    for a in bundle.announcements:
        label, bg, fg = _badge(a.sentiment)
        ann_vm.append({
            "title": a.title, "url": a.url, "published": a.published,
            "column": a.extra.get("column", ""),
            "sentiment_label": label, "badge_bg": bg, "badge_fg": fg,
        })

    guba_vm = [
        {
            "title": g.title, "url": g.url, "published": g.published,
            "click_count": g.click_count, "comment_count": g.comment_count,
            "color": {"positive": UP, "negative": DOWN, "neutral": FLAT}.get(g.sentiment, FLAT),
        }
        for g in bundle.guba
    ]

    # ---- 基本面 ----
    f = bundle.fundamental
    fundamental_vm = {
        "report_name": f.report_name,
        "revenue_str": _money(f.revenue) + (f"（同比 {_pct(f.revenue_yoy)}）" if f.revenue_yoy is not None else ""),
        "profit_str": _money(f.net_profit) + (f"（同比 {_pct(f.net_profit_yoy)}）" if f.net_profit_yoy is not None else ""),
        "profit_color": _color(f.net_profit),
        "roe_str": f"{f.roe:.2f}%" if f.roe is not None else "—",
        "debt_str": f"{f.debt_ratio:.2f}%" if f.debt_ratio is not None else "—",
        "holder_line": (f"股东户数 {f.holder_num:,} 户，环比 {_pct(f.holder_num_change_pct)}"
                        if f.holder_num and f.holder_num_change_pct is not None else ""),
    }

    indexes_vm = [
        {"name": ix.name, "price": _num(ix.price), "pct_str": _pct(ix.pct_chg), "color": _color(ix.pct_chg)}
        for ix in bundle.indexes
    ]

    score_bg = "#fee2e2" if trend.score >= 65 else ("#dcfce7" if trend.score <= 35 else "#f3f4f6")
    score_color = UP if trend.score >= 65 else (DOWN if trend.score <= 35 else FLAT)

    return {
        "subject": subject,
        "stock": {"name": bundle.quote.name or "合众思壮", "code": bundle.quote.code or "002383"},
        "trade_date": bundle.trade_date,
        "generated_at": bundle.generated_at,
        "headline": headline.replace("**", ""),
        "chg_color": chg_color,
        "score_bg": score_bg,
        "score_color": score_color,
        "trend": trend,
        "quote": quote_vm,
        "signals": signals_vm,
        "supports_str": "、".join(f"{x:.2f}" for x in trend.supports) or "暂无明显支撑位",
        "resistances_str": "、".join(f"{x:.2f}" for x in trend.resistances) or "暂无明显压力位",
        "position_pct": trend.position_pct,
        "fundflow_rows": fundflow_rows,
        "margin_line": margin_line,
        "news": news_vm,
        "news_context": news_context_vm,
        "announcements": ann_vm,
        "research": [r.__dict__ for r in bundle.research],
        "guba": guba_vm,
        "news_stats": bundle.news_stats,
        "guba_stats": bundle.guba_stats,
        "fundamental": fundamental_vm,
        "indexes": indexes_vm,
        "watch_points": trend.watch_points,
        "errors": bundle.errors,
        "errors_str": "；".join(bundle.errors),
    }


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #

def render_html(bundle: DailyBundle, trend: TrendAnalysis, subject: str = "") -> str:
    subj = subject or f"{bundle.quote.name or '合众思壮'} 每日观察报告 · {bundle.trade_date}"
    return Template(HTML_TEMPLATE).render(**_build_context(bundle, trend, subj))


def render_markdown(bundle: DailyBundle, trend: TrendAnalysis) -> str:
    q, ind, last = bundle.quote, trend.indicators, bundle.kline.latest
    chg = q.pct_chg if q.pct_chg is not None else (last.pct_chg if last else None)
    L: list[str] = []

    L.append(f"# {bundle.quote.name or '合众思壮'}（{bundle.quote.code or '002383'}）每日观察报告")
    L.append("")
    L.append(f"- 数据交易日：**{bundle.trade_date}**")
    L.append(f"- 生成时间：{bundle.generated_at}")
    L.append(f"- 综合研判：**{trend.label}**（多空比 {trend.score} : {100 - trend.score}）")
    L.append("")

    # 行情
    L.append("## 一、行情快照")
    L.append("")
    L.append("| 项目 | 数值 | 项目 | 数值 |")
    L.append("| --- | --- | --- | --- |")
    rows = [
        ("最新价", _num(q.price if q.price is not None else (last.close if last else None))),
        ("涨跌幅", _pct(chg)),
        ("涨跌额", _num(q.change)),
        ("今开", _num(q.open if q.open is not None else (last.open if last else None))),
        ("最高", _num(q.high if q.high is not None else (last.high if last else None))),
        ("最低", _num(q.low if q.low is not None else (last.low if last else None))),
        ("昨收", _num(q.pre_close)),
        ("成交量(手)", f"{last.volume:,}" if last else "—"),
        ("成交额", _money(q.amount if q.amount is not None else (last.amount if last else None))),
        ("换手率", f"{(q.turnover or 0):.2f}%" if q.turnover is not None else "—"),
        ("振幅", f"{(q.amplitude or 0):.2f}%" if q.amplitude is not None else "—"),
        ("量比", _num(q.volume_ratio)),
        ("总市值", _money(q.total_mv)),
        ("流通市值", _money(q.float_mv)),
        ("市盈率TTM", _num(q.pe_ttm)),
        ("市净率", _num(q.pb)),
    ]
    for i in range(0, len(rows), 2):
        a = rows[i]
        b = rows[i + 1] if i + 1 < len(rows) else ("", "")
        L.append(f"| {a[0]} | {a[1]} | {b[0]} | {b[1]} |")
    L.append("")

    if bundle.indexes:
        L.append("**大盘环境**：" + "　".join(
            f"{ix.name} {_num(ix.price)}（{_pct(ix.pct_chg)}）" for ix in bundle.indexes))
        L.append("")

    # 技术面
    L.append("## 二、技术研判")
    L.append("")
    L.append("| 指标 | 倾向 | 说明 |")
    L.append("| --- | --- | --- |")
    for s in trend.signals:
        L.append(f"| {s.name} | {_DIRECTION_LABEL[s.direction]} | {s.detail} |")
    L.append("")
    L.append(f"- **支撑位**：{'、'.join(f'{x:.2f}' for x in trend.supports) or '暂无明显支撑位'}")
    L.append(f"- **压力位**：{'、'.join(f'{x:.2f}' for x in trend.resistances) or '暂无明显压力位'}")
    if trend.position_pct is not None:
        L.append(f"- **区间分位**：当前价处于近 60 日波动区间的 {trend.position_pct}% 分位")
    L.append("")
    if ind:
        L.append("关键指标读数：" + "，".join(filter(None, [
            f"MA5={ind.get('ma5')}", f"MA10={ind.get('ma10')}", f"MA20={ind.get('ma20')}",
            f"MA60={ind.get('ma60')}", f"DIF={ind.get('dif')}", f"DEA={ind.get('dea')}",
            f"RSI14={ind.get('rsi14')}", f"K={ind.get('k')}", f"D={ind.get('d')}", f"J={ind.get('j')}",
        ])))
        L.append("")

    # 资金面
    L.append("## 三、资金面")
    L.append("")
    if bundle.fundflow.days:
        L.append("| 周期 | 主力净额 | 超大单 | 大单 | 中单 | 小单 |")
        L.append("| --- | --- | --- | --- | --- | --- |")
        for n in (1, 5, 10, 20):
            days = bundle.fundflow.days[-n:]
            if n > 1 and len(bundle.fundflow.days) < n:
                continue
            label = {1: "今日", 5: "近5日", 10: "近10日", 20: "近20日"}[n]
            L.append("| {} | {} | {} | {} | {} | {} |".format(
                label,
                _fmt_yi(sum(d.main_net for d in days)),
                _fmt_yi(sum(d.super_large_net for d in days)),
                _fmt_yi(sum(d.large_net for d in days)),
                _fmt_yi(sum(d.medium_net for d in days)),
                _fmt_yi(sum(d.small_net for d in days)),
            ))
        L.append("")
    else:
        L.append("_未获取到资金流向数据。_")
        L.append("")
    mg = bundle.margin
    if mg.date:
        line = f"融资余额 **{_fmt_yi(mg.financing_balance)}**（{mg.date}）"
        if mg.balance_ratio is not None:
            line += f"，占流通市值 {mg.balance_ratio:.2f}%"
        if mg.net_buy is not None:
            line += f"，当日融资{'净买入' if mg.net_buy >= 0 else '净卖出'} {_fmt_yi(abs(mg.net_buy))}"
        L.append(line)
        L.append("")

    # 新闻
    L.append(f"## 四、全网相关资讯（{len(bundle.news)} 条）")
    L.append("")
    if bundle.news_stats.get("total"):
        s = bundle.news_stats
        L.append(f"> 情绪统计：利好 {s['positive']} / 利空 {s['negative']} / 中性 {s['neutral']}，"
                 f"情绪指数 **{s['index']}**（{s['label']}）")
        L.append("")
    if bundle.news:
        for i, n in enumerate(bundle.news, 1):
            tag = {"positive": "🔴利好", "negative": "🟢利空", "neutral": "⚪中性"}[n.sentiment]
            scope = "" if n.extra.get("relevance", 1) == 2 else "〔行业/榜单提及〕"
            title = f"[{n.title}]({n.url})" if n.url else f"**{n.title}**"
            L.append(f"{i}. {tag} {scope}{title}")
            L.append(f"   - {n.source} · {n.published}")
            if n.summary:
                L.append(f"   - {n.summary}")
        L.append("")
    else:
        L.append("_本期未获取到相关资讯。_")
        L.append("")

    # 近期重要公司事件（窗口外，补足背景）
    if bundle.news_context:
        L.append(f"### 近期重要公司事件回顾（{len(bundle.news_context)} 条）")
        L.append("")
        for n in bundle.news_context:
            tag = {"positive": "🔴利好", "negative": "🟢利空", "neutral": "⚪中性"}[n.sentiment]
            title = f"[{n.title}]({n.url})" if n.url else f"**{n.title}**"
            L.append(f"- {tag} {title}")
            L.append(f"  - {n.source} · {n.published}")
        L.append("")

    # 公告
    if bundle.announcements:
        L.append(f"## 五、公司公告（{len(bundle.announcements)} 条）")
        L.append("")
        for a in bundle.announcements:
            tag = {"positive": "🔴", "negative": "🟢", "neutral": "⚪"}[a.sentiment]
            title = f"[{a.title}]({a.url})" if a.url else a.title
            col = f"（{a.extra.get('column')}）" if a.extra.get("column") else ""
            L.append(f"- {tag} {title} {col} — {a.published}")
        L.append("")

    # 研报
    if bundle.research:
        L.append("## 六、机构研报")
        L.append("")
        for r in bundle.research:
            title = f"[{r.title}]({r.url})" if r.url else r.title
            rating = f"，评级 {r.rating}" if r.rating else ""
            L.append(f"- {r.org}：{title}（{r.published}{rating}）")
        L.append("")

    # 股吧
    if bundle.guba:
        L.append(f"## 七、股吧热议（取前 {min(len(bundle.guba), 20)} 条）")
        L.append("")
        gs = bundle.guba_stats
        if gs.get("total"):
            L.append(f"> 散户情绪：多 {gs['positive']} / 空 {gs['negative']} / 中性 {gs['neutral']}，"
                     f"人气指数 {gs['index']}（{gs['label']}）")
            L.append("")
        for g in bundle.guba[:20]:
            title = f"[{g.title}]({g.url})" if g.url else g.title
            L.append(f"- {title} — 阅读 {g.click_count} / 评论 {g.comment_count} · {g.published}")
        L.append("")

    # 基本面
    f = bundle.fundamental
    if f.report_name:
        L.append(f"## 八、基本面（{f.report_name}）")
        L.append("")
        if f.revenue is not None:
            L.append(f"- 营业总收入：{_money(f.revenue)}"
                     + (f"（同比 {_pct(f.revenue_yoy)}）" if f.revenue_yoy is not None else ""))
        if f.net_profit is not None:
            L.append(f"- 归母净利润：{_money(f.net_profit)}"
                     + (f"（同比 {_pct(f.net_profit_yoy)}）" if f.net_profit_yoy is not None else ""))
        if f.eps is not None:
            L.append(f"- 每股收益：{f.eps:.4f} 元")
        if f.bps is not None:
            L.append(f"- 每股净资产：{f.bps:.4f} 元")
        if f.roe is not None:
            L.append(f"- 净资产收益率(ROE)：{f.roe:.2f}%")
        if f.gross_margin is not None:
            L.append(f"- 销售毛利率：{f.gross_margin:.2f}%")
        if f.debt_ratio is not None:
            L.append(f"- 资产负债率：{f.debt_ratio:.2f}%")
        if f.holder_num and f.holder_num_change_pct is not None:
            L.append(f"- 股东户数：{f.holder_num:,} 户（环比 {_pct(f.holder_num_change_pct)}）")
        L.append("")

    # 观察要点
    L.append("## 九、今日观察要点")
    L.append("")
    for i, w in enumerate(trend.watch_points, 1):
        L.append(f"{i}. {w}")
    L.append("")

    # 缺口
    if bundle.errors:
        L.append("## 十、本期数据缺口")
        L.append("")
        for e in bundle.errors:
            L.append(f"- {e}")
        L.append("")

    L.append("---")
    L.append("")
    L.append("_本报告由程序自动生成，数据来源于东方财富公开接口，"
             "仅为公开信息统计结果，**不构成任何投资建议**，投资决策及风险请自行承担。_")
    L.append("")
    return "\n".join(L)


def save_reports(
    bundle: DailyBundle,
    trend: TrendAnalysis,
    out_dir: str | Path,
    subject: str = "",
) -> tuple[Path, Path]:
    """落盘 Markdown 与 HTML，返回 (md_path, html_path)。"""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    code = bundle.quote.code or "002383"
    md_path = d / f"{code}_{stamp}_report.md"
    html_path = d / f"{code}_{stamp}_report.html"
    md_path.write_text(render_markdown(bundle, trend), encoding="utf-8")
    html_path.write_text(render_html(bundle, trend, subject), encoding="utf-8")
    return md_path, html_path

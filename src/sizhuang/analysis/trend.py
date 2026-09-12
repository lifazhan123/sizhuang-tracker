"""趋势研判：把技术面 / 资金面 / 消息面合成一份可读的多空研判。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import DailyBundle
from .indicators import summarize_indicators


@dataclass
class Signal:
    name: str
    direction: str      # bull / bear / neutral
    detail: str


@dataclass
class TrendAnalysis:
    score: int = 50                       # 0~100，越高越偏多
    label: str = "中性"
    signals: list[Signal] = field(default_factory=list)
    indicators: dict[str, Any] = field(default_factory=dict)
    supports: list[float] = field(default_factory=list)
    resistances: list[float] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    watch_points: list[str] = field(default_factory=list)
    position_pct: float | None = None      # 当前价在 60 日区间中的分位 %

    @property
    def bulls(self) -> list[Signal]:
        return [s for s in self.signals if s.direction == "bull"]

    @property
    def bears(self) -> list[Signal]:
        return [s for s in self.signals if s.direction == "bear"]


def _fmt_yi(v: float | None) -> str:
    """金额格式化：元 -> 亿元 / 万元。"""
    if v is None:
        return "—"
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e8:
        return f"{sign}{a / 1e8:.2f}亿"
    if a >= 1e4:
        return f"{sign}{a / 1e4:.2f}万"
    return f"{sign}{a:.0f}"


def analyze_trend(bundle: DailyBundle) -> TrendAnalysis:
    """核心研判入口。"""
    ta = TrendAnalysis()
    if not bundle.kline.bars:
        ta.summary.append("未获取到K线数据，无法进行技术研判。")
        return ta

    closes = [b.close for b in bundle.kline.bars]
    highs = [b.high for b in bundle.kline.bars]
    lows = [b.low for b in bundle.kline.bars]
    volumes = [float(b.volume) for b in bundle.kline.bars]

    ind = summarize_indicators(closes, highs, lows, volumes)
    ta.indicators = ind
    price = ind.get("price") or closes[-1]

    signals: list[Signal] = []

    # ---------------- 1. 均线排列 ----------------
    align = ind.get("ma_alignment")
    ma5, ma10, ma20, ma60 = ind.get("ma5"), ind.get("ma10"), ind.get("ma20"), ind.get("ma60")
    if align == "bullish":
        signals.append(Signal("均线系统", "bull", "MA5>MA10>MA20>MA60，多头排列，中期趋势向上"))
    elif align == "bearish":
        signals.append(Signal("均线系统", "bear", "MA5<MA10<MA20<MA60，空头排列，中期趋势向下"))
    else:
        signals.append(Signal("均线系统", "neutral", "均线交织，方向未明，处于震荡整理阶段"))

    # 价格与各均线关系
    above, below = [], []
    for label, val in (("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60), ("MA120", ind.get("ma120"))):
        if val is None:
            continue
        (above if price >= val else below).append(label)
    if above and not below:
        signals.append(Signal("价格位置", "bull", f"股价站上全部主要均线（{'/'.join(above)}）"))
    elif below and not above:
        signals.append(Signal("价格位置", "bear", f"股价跌破全部主要均线（{'/'.join(below)}）"))
    else:
        signals.append(Signal("价格位置", "neutral",
                              f"站上 {'/'.join(above) or '无'}，仍受制于 {'/'.join(below) or '无'}"))

    # ---------------- 2. MACD ----------------
    dif, dea, hist = ind.get("dif"), ind.get("dea"), ind.get("macd_hist")
    dif_p, dea_p = ind.get("dif_prev"), ind.get("dea_prev")
    hist_p = ind.get("macd_hist_prev")
    if None not in (dif, dea, dif_p, dea_p):
        crossed_up = dif_p <= dea_p and dif > dea
        crossed_dn = dif_p >= dea_p and dif < dea
        if crossed_up:
            signals.append(Signal("MACD", "bull", f"DIF 上穿 DEA 形成金叉（DIF={dif}，DEA={dea}）"))
        elif crossed_dn:
            signals.append(Signal("MACD", "bear", f"DIF 下穿 DEA 形成死叉（DIF={dif}，DEA={dea}）"))
        elif dif > dea:
            signals.append(Signal("MACD", "bull", f"DIF 位于 DEA 上方，多头动能延续（DIF={dif}，DEA={dea}）"))
        else:
            signals.append(Signal("MACD", "bear", f"DIF 位于 DEA 下方，空头动能延续（DIF={dif}，DEA={dea}）"))
        if hist is not None and hist_p is not None:
            if hist > 0 and hist > hist_p:
                signals.append(Signal("MACD柱", "bull", f"红柱放大（{hist_p} → {hist}），上攻动能增强"))
            elif hist > 0 and hist < hist_p:
                signals.append(Signal("MACD柱", "neutral", f"红柱收窄（{hist_p} → {hist}），上攻动能减弱"))
            elif hist < 0 and hist < hist_p:
                signals.append(Signal("MACD柱", "bear", f"绿柱放大（{hist_p} → {hist}），下杀动能增强"))
            else:
                signals.append(Signal("MACD柱", "neutral", f"绿柱收窄（{hist_p} → {hist}），跌势有缓和迹象"))

    # ---------------- 3. RSI ----------------
    rsi6, rsi14 = ind.get("rsi6"), ind.get("rsi14")
    if rsi14 is not None:
        if rsi14 >= 80:
            signals.append(Signal("RSI", "bear", f"RSI14={rsi14}，严重超买，短线回调风险大"))
        elif rsi14 >= 70:
            signals.append(Signal("RSI", "neutral", f"RSI14={rsi14}，进入超买区，注意获利回吐"))
        elif rsi14 <= 20:
            signals.append(Signal("RSI", "bull", f"RSI14={rsi14}，严重超卖，存在超跌反弹机会"))
        elif rsi14 <= 30:
            signals.append(Signal("RSI", "neutral", f"RSI14={rsi14}，进入超卖区，跌势或趋缓"))
        elif rsi14 >= 50:
            signals.append(Signal("RSI", "bull", f"RSI14={rsi14}，位于强势区"))
        else:
            signals.append(Signal("RSI", "bear", f"RSI14={rsi14}，位于弱势区"))

    # ---------------- 4. KDJ ----------------
    k, d, j = ind.get("k"), ind.get("d"), ind.get("j")
    if None not in (k, d):
        if k > d and k < 30:
            signals.append(Signal("KDJ", "bull", f"K={k}、D={d}，低位金叉，短线转强"))
        elif k < d and k > 70:
            signals.append(Signal("KDJ", "bear", f"K={k}、D={d}，高位死叉，短线转弱"))
        elif k > d:
            signals.append(Signal("KDJ", "bull", f"K={k} > D={d}，短线偏多"))
        else:
            signals.append(Signal("KDJ", "bear", f"K={k} < D={d}，短线偏弱"))
        if j is not None and j > 100:
            signals.append(Signal("KDJ-J", "bear", f"J 值={j} 超过 100，极度超买"))
        elif j is not None and j < 0:
            signals.append(Signal("KDJ-J", "bull", f"J 值={j} 低于 0，极度超卖"))

    # ---------------- 5. BOLL ----------------
    bu, bm, bl = ind.get("boll_up"), ind.get("boll_mid"), ind.get("boll_low")
    if None not in (bu, bm, bl) and bu > bl:
        pos = (price - bl) / (bu - bl) * 100
        if pos >= 95:
            signals.append(Signal("布林带", "bear", f"股价贴近上轨（分位 {pos:.0f}%），短线超买"))
        elif pos >= 70:
            signals.append(Signal("布林带", "bull", f"股价运行于上轨区（分位 {pos:.0f}%），强势特征"))
        elif pos <= 5:
            signals.append(Signal("布林带", "bull", f"股价贴近下轨（分位 {pos:.0f}%），超跌"))
        elif pos <= 30:
            signals.append(Signal("布林带", "bear", f"股价运行于下轨区（分位 {pos:.0f}%），弱势特征"))
        else:
            signals.append(Signal("布林带", "neutral", f"股价位于中轨附近（分位 {pos:.0f}%），震荡格局"))

    # ---------------- 6. 量能 ----------------
    vr = ind.get("vol_ratio_vs_ma5")
    last_bar = bundle.kline.latest
    if vr is not None:
        pct = last_bar.pct_chg if last_bar else 0.0
        if vr >= 1.5 and pct > 0:
            signals.append(Signal("量能", "bull", f"放量上涨（量为5日均量的 {vr:.2f} 倍），买盘积极"))
        elif vr >= 1.5 and pct < 0:
            signals.append(Signal("量能", "bear", f"放量下跌（量为5日均量的 {vr:.2f} 倍），抛压沉重"))
        elif vr <= 0.6 and pct > 0:
            signals.append(Signal("量能", "neutral", f"缩量上涨（量仅为5日均量的 {vr:.2f} 倍），追高需谨慎"))
        elif vr <= 0.6 and pct < 0:
            signals.append(Signal("量能", "neutral", f"缩量下跌（量仅为5日均量的 {vr:.2f} 倍），抛压趋缓"))
        else:
            signals.append(Signal("量能", "neutral", f"成交量为5日均量的 {vr:.2f} 倍，量能平稳"))

    # ---------------- 7. 价格区间分位 ----------------
    hi60, lo60 = ind.get("high60"), ind.get("low60")
    if hi60 and lo60 and hi60 > lo60:
        pos60 = (price - lo60) / (hi60 - lo60) * 100
        ta.position_pct = round(pos60, 1)
        if pos60 >= 85:
            signals.append(Signal("区间位置", "bear", f"处于近60日高位区（{pos60:.0f}% 分位），追高风险上升"))
        elif pos60 >= 60:
            signals.append(Signal("区间位置", "bull", f"处于近60日偏上区间（{pos60:.0f}% 分位）"))
        elif pos60 >= 40:
            signals.append(Signal("区间位置", "neutral", f"处于近60日中间区间（{pos60:.0f}% 分位）"))
        elif pos60 >= 15:
            signals.append(Signal("区间位置", "bear", f"处于近60日偏下区间（{pos60:.0f}% 分位）"))
        else:
            signals.append(Signal("区间位置", "bull", f"处于近60日低位区（{pos60:.0f}% 分位），下探空间有限"))

    # ---------------- 8. 资金面 ----------------
    ff = bundle.fundflow
    if ff.days:
        n_days = len(ff.days)
        today_main = ff.days[-1].main_net
        conc = ""
        if bundle.quote.amount and abs(today_main) > 0:
            conc = f"（占成交额 {abs(today_main) / bundle.quote.amount * 100:.1f}%）"
        if today_main > 0:
            signals.append(Signal("主力资金", "bull", f"今日主力净流入 {_fmt_yi(today_main)}{conc}"))
        elif today_main < 0:
            signals.append(Signal("主力资金", "bear", f"今日主力净流出 {_fmt_yi(today_main)}{conc}"))
        else:
            signals.append(Signal("主力资金", "neutral", "今日主力资金基本持平"))

        # 只在真的拿到足够历史时才谈「趋势」，避免单日数据被误读成持续性
        if n_days >= 5:
            window = min(n_days, 10)
            total = sum(d.main_net for d in ff.days[-window:])
            ups = sum(1 for d in ff.days[-window:] if d.main_net > 0)
            trend_txt = ("多数交易日净流入" if ups > window / 2 else
                         ("多数交易日净流出" if ups < window / 2 else "流入流出交替"))
            direction = "bull" if total > 0 else ("bear" if total < 0 else "neutral")
            signals.append(Signal(
                "资金趋势", direction,
                f"近{window}个交易日主力累计 {_fmt_yi(total)}（{ups}/{window} 日为净流入），{trend_txt}"
            ))
        else:
            signals.append(Signal("资金趋势", "neutral",
                                  f"仅获取到 {n_days} 个交易日资金数据，暂不判断趋势"))

    # ---------------- 9. 融资融券 ----------------
    mg = bundle.margin
    if mg.date and mg.net_buy is not None:
        if mg.net_buy > 0:
            signals.append(Signal("融资余额", "bull", f"{mg.date} 融资净买入 {_fmt_yi(mg.net_buy)}，杠杆资金加仓"))
        else:
            signals.append(Signal("融资余额", "bear", f"{mg.date} 融资净卖出 {_fmt_yi(abs(mg.net_buy))}，杠杆资金减仓"))

    # ---------------- 10. 消息面 / 股吧情绪 ----------------
    news_stats = bundle.news_stats or {}
    if news_stats.get("total"):
        idx = news_stats.get("index", 50)
        direction = "bull" if idx >= 60 else ("bear" if idx <= 40 else "neutral")
        signals.append(Signal("消息面", direction,
                              f"近{len(bundle.news)}条相关资讯情绪指数 {idx}（{news_stats.get('label')}），"
                              f"正面 {news_stats.get('positive')} / 负面 {news_stats.get('negative')}"))
    guba_stats = bundle.guba_stats or {}
    if guba_stats.get("total"):
        signals.append(Signal("股吧人气", "neutral",
                              f"股吧热帖 {guba_stats.get('total')} 条，人气指数 {guba_stats.get('index')}"
                              f"（{guba_stats.get('label')}），散户情绪为反向参考指标"))

    ta.signals = signals

    # ---------------- 综合评分 ----------------
    bull_n = len([s for s in signals if s.direction == "bull"])
    bear_n = len([s for s in signals if s.direction == "bear"])
    total_n = bull_n + bear_n
    if total_n:
        ta.score = int(round(bull_n / total_n * 100))
    ta.label = "偏多" if ta.score >= 65 else ("偏空" if ta.score <= 35 else "中性")

    # ---------------- 支撑 / 压力 ----------------
    ta.supports, ta.resistances = _levels(price, ind)

    # ---------------- 文字结论 ----------------
    ta.summary = _build_summary(bundle, ta, ind, news_stats, guba_stats)
    ta.watch_points = _build_watch_points(bundle, ta, ind)
    return ta


def _levels(price: float, ind: dict) -> tuple[list[float], list[float]]:
    """从均线 / 布林 / 区间高低点中挑出有意义的支撑与压力位。"""
    cands = {
        "MA5": ind.get("ma5"), "MA10": ind.get("ma10"), "MA20": ind.get("ma20"),
        "MA60": ind.get("ma60"), "MA120": ind.get("ma120"),
        "布林上轨": ind.get("boll_up"), "布林中轨": ind.get("boll_mid"), "布林下轨": ind.get("boll_low"),
        "20日高": ind.get("high20"), "20日低": ind.get("low20"),
        "60日高": ind.get("high60"), "60日低": ind.get("low60"),
    }
    supports, resistances = [], []
    for label, v in cands.items():
        if v is None:
            continue
        # 距离过近（0.3% 内）不算独立位置
        if abs(v - price) / price < 0.003:
            continue
        (supports if v < price else resistances).append(v)
    supports = sorted(set(round(x, 2) for x in supports), reverse=True)[:4]
    resistances = sorted(set(round(x, 2) for x in resistances))[:4]
    return supports, resistances


def _build_summary(bundle, ta, ind, news_stats, guba_stats) -> list[str]:
    out: list[str] = []
    q = bundle.quote
    last = bundle.kline.latest

    if last:
        direction = "上涨" if (q.pct_chg or 0) > 0 else ("下跌" if (q.pct_chg or 0) < 0 else "收平")
        out.append(
            f"{last.date} 收盘 {last.close:.2f} 元，{direction} {(q.pct_chg if q.pct_chg is not None else last.pct_chg):.2f}%，"
            f"成交 {last.volume:,} 手 / {last.amount / 1e8:.2f} 亿元，换手率 {last.turnover:.2f}%，振幅 {last.amplitude:.2f}%。"
        )

    if ta.indicators:
        ma_txt = "、".join(
            f"{k} {v}" for k, v in (("MA5", ind.get("ma5")), ("MA10", ind.get("ma10")),
                                    ("MA20", ind.get("ma20")), ("MA60", ind.get("ma60"))) if v is not None
        )
        out.append(f"技术面：{ma_txt}；MACD DIF={ind.get('dif')} DEA={ind.get('dea')}；"
                   f"RSI14={ind.get('rsi14')}；KDJ K={ind.get('k')} D={ind.get('d')} J={ind.get('j')}。")

    if bundle.fundflow.days:
        ff = bundle.fundflow
        parts = [f"今日主力净额 {_fmt_yi(ff.days[-1].main_net)}"]
        if len(ff.days) >= 5:
            parts.append(f"近5日累计 {_fmt_yi(ff.sum_main(5))}")
        if len(ff.days) >= 10:
            parts.append(f"近10日累计 {_fmt_yi(ff.sum_main(10))}")
        out.append("资金面：" + "，".join(parts) + "。")

    if news_stats.get("total"):
        out.append(f"消息面：近{len(bundle.news)}条相关资讯中，正面 {news_stats.get('positive')} 条、"
                   f"负面 {news_stats.get('negative')} 条、中性 {news_stats.get('neutral')} 条，"
                   f"情绪指数 {news_stats.get('index')}（{news_stats.get('label')}）。")

    out.append(f"综合研判：多空信号比 {ta.score} : {100 - ta.score}，短期定性为「{ta.label}」。"
               f"该结论由 {len(ta.signals)} 个技术/资金/情绪指标加权得出，仅供观察参考。")
    return out


def _build_watch_points(bundle, ta, ind) -> list[str]:
    pts: list[str] = []
    if ta.supports:
        pts.append("下方支撑关注：" + "、".join(f"{x:.2f}" for x in ta.supports) +
                   "，跌破则技术形态转弱。")
    if ta.resistances:
        pts.append("上方压力关注：" + "、".join(f"{x:.2f}" for x in ta.resistances) +
                   "，有效放量突破则打开上行空间。")

    vr = ind.get("vol_ratio_vs_ma5")
    if vr is not None and vr >= 1.5:
        pts.append(f"今日成交显著放大（{vr:.2f} 倍），需关注后续量能能否延续——"
                   "放量滞涨往往是短线见顶信号。")
    elif vr is not None and vr <= 0.6:
        pts.append(f"今日明显缩量（{vr:.2f} 倍），方向选择前不宜重仓追入。")

    # 公告 / 研报 / 龙虎榜 提示
    if bundle.announcements:
        pts.append(f"最新公告：{bundle.announcements[0].title}（{bundle.announcements[0].published}），建议阅读原文。")
    if bundle.dragon:
        d = bundle.dragon[0]
        pts.append(f"最近一次龙虎榜：{d.date}，{d.reason}，净额 {_fmt_yi(d.net_amount)}。")
    if bundle.research:
        r = bundle.research[0]
        pts.append(f"最近研报：{r.org}《{r.title}》（{r.published}）"
                   f"{'，评级 ' + r.rating if r.rating else ''}。")

    # 基本面提示
    f = bundle.fundamental
    if f.report_name:
        parts = [f"{f.report_name}"]
        if f.revenue is not None:
            parts.append(f"营收 {f.revenue / 1e8:.2f} 亿"
                         f"（同比 {f.revenue_yoy:+.2f}%）" if f.revenue_yoy is not None else "")
        if f.net_profit is not None:
            parts.append(f"归母净利 {f.net_profit / 1e8:.2f} 亿"
                         f"（同比 {f.net_profit_yoy:+.2f}%）" if f.net_profit_yoy is not None else "")
        if f.roe is not None:
            parts.append(f"ROE {f.roe:.2f}%")
        pts.append("基本面：" + "，".join(p for p in parts if p) + "。")
    if f.holder_num and f.holder_num_change_pct is not None:
        trend = "筹码趋于集中（利好）" if f.holder_num_change_pct < 0 else "筹码趋于分散（需警惕）"
        pts.append(f"股东户数 {f.holder_num:,} 户，环比 {f.holder_num_change_pct:+.2f}%，{trend}。")

    pts.append("风险提示：以上为公开数据程序化统计结果，不构成任何投资建议，"
               "据此操作风险自负。")
    return pts

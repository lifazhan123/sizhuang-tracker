"""纯 Python 技术指标实现（不依赖 numpy/pandas，便于在 Actions 里秒级运行）。

包含：MA / EMA / MACD / RSI / KDJ / BOLL / 量能对比 / 支撑压力位。
所有函数接受 float 列表，返回等长或短于输入的列表（前置 None 表示数据不足）。
"""

from __future__ import annotations

from typing import Sequence


def _f(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values]


# --------------------------------------------------------------------------- #
# 均线
# --------------------------------------------------------------------------- #

def ma(values: Sequence[float], period: int) -> list[float | None]:
    """简单移动平均，前 period-1 位为 None。"""
    v = _f(values)
    out: list[float | None] = [None] * len(v)
    if period <= 0 or len(v) < period:
        return out
    window = sum(v[:period])
    out[period - 1] = window / period
    for i in range(period, len(v)):
        window += v[i] - v[i - period]
        out[i] = window / period
    return out


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """指数移动平均。"""
    v = _f(values)
    out: list[float | None] = [None] * len(v)
    if not v or period <= 0:
        return out
    k = 2.0 / (period + 1)
    prev: float | None = None
    # 以前 period 个值的简单均值作为种子
    if len(v) >= period:
        prev = sum(v[:period]) / period
        out[period - 1] = prev
        for i in range(period, len(v)):
            prev = v[i] * k + prev * (1 - k)
            out[i] = prev
    else:
        prev = v[0]
        out[0] = prev
        for i in range(1, len(v)):
            prev = v[i] * k + prev * (1 - k)
            out[i] = prev
    return out


# --------------------------------------------------------------------------- #
# MACD
# --------------------------------------------------------------------------- #

def macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """返回 (DIF, DEA, MACD柱)。A股常用 12/26/9。

    注意：国内软件的 MACD 柱 = 2 × (DIF - DEA)。
    """
    e_fast = ema(values, fast)
    e_slow = ema(values, slow)
    dif: list[float | None] = []
    for a, b in zip(e_fast, e_slow):
        dif.append(None if a is None or b is None else a - b)

    valid = [x for x in dif if x is not None]
    dea_partial = ema(valid, signal)
    dea: list[float | None] = [None] * len(dif)
    offset = len(dif) - len(valid)
    for i, val in enumerate(dea_partial):
        dea[offset + i] = val

    hist: list[float | None] = []
    for d, s in zip(dif, dea):
        hist.append(None if d is None or s is None else 2 * (d - s))
    return dif, dea, hist


# --------------------------------------------------------------------------- #
# RSI
# --------------------------------------------------------------------------- #

def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    """Wilder RSI。"""
    v = _f(values)
    out: list[float | None] = [None] * len(v)
    if len(v) <= period:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        delta = v[i] - v[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(v)):
        delta = v[i] - v[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


# --------------------------------------------------------------------------- #
# KDJ
# --------------------------------------------------------------------------- #

def kdj(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """经典 KDJ(9,3,3)。"""
    h, l, c = _f(highs), _f(lows), _f(closes)
    size = len(c)
    k_out: list[float | None] = [None] * size
    d_out: list[float | None] = [None] * size
    j_out: list[float | None] = [None] * size
    if size < n:
        return k_out, d_out, j_out

    k_prev, d_prev = 50.0, 50.0
    for i in range(n - 1, size):
        hh = max(h[i - n + 1: i + 1])
        ll = min(l[i - n + 1: i + 1])
        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
        k_prev = (m1 - 1) / m1 * k_prev + 1 / m1 * rsv
        d_prev = (m2 - 1) / m2 * d_prev + 1 / m2 * k_prev
        k_out[i] = round(k_prev, 2)
        d_out[i] = round(d_prev, 2)
        j_out[i] = round(3 * k_prev - 2 * d_prev, 2)
    return k_out, d_out, j_out


# --------------------------------------------------------------------------- #
# BOLL
# --------------------------------------------------------------------------- #

def boll(
    values: Sequence[float],
    period: int = 20,
    mult: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """布林带，返回 (上轨, 中轨, 下轨)。"""
    v = _f(values)
    mid = ma(v, period)
    upper: list[float | None] = [None] * len(v)
    lower: list[float | None] = [None] * len(v)
    for i in range(period - 1, len(v)):
        window = v[i - period + 1: i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        sd = var ** 0.5
        upper[i] = round(mean + mult * sd, 2)
        lower[i] = round(mean - mult * sd, 2)
    return upper, mid, lower


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #

def _last(lst: Sequence[float | None], offset: int = 0) -> float | None:
    if not lst:
        return None
    idx = len(lst) - 1 - offset
    if idx < 0:
        return None
    val = lst[idx]
    return None if val is None else round(float(val), 3)


def summarize_indicators(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
) -> dict:
    """把常用的技术指标一次性算好，供趋势研判与报告渲染使用。"""
    c = _f(closes)
    if not c:
        return {}

    ma5, ma10, ma20, ma60, ma120 = (ma(c, p) for p in (5, 10, 20, 60, 120))
    dif, dea, hist = macd(c)
    rsi6, rsi14 = rsi(c, 6), rsi(c, 14)
    k, d, j = kdj(highs, lows, c)
    up, mid, low = boll(c, 20, 2.0)

    price = c[-1]
    vol = _f(volumes) if volumes else []
    vol_ma5 = _last(ma(vol, 5)) if vol else None
    vol_ma10 = _last(ma(vol, 10)) if vol else None
    vol_ratio_vs_ma5 = round(vol[-1] / vol_ma5, 2) if vol and vol_ma5 else None

    # 近 20 / 60 日高低点
    hi20 = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    lo20 = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    hi60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    lo60 = min(lows[-60:]) if len(lows) >= 60 else min(lows)

    # 年线/半年线等长期均线
    hi_all = max(highs)
    lo_all = min(lows)

    res = {
        "price": round(price, 2),
        "ma5": _last(ma5), "ma10": _last(ma10), "ma20": _last(ma20),
        "ma60": _last(ma60), "ma120": _last(ma120),
        "dif": _last(dif), "dea": _last(dea), "macd_hist": _last(hist),
        "macd_hist_prev": _last(hist, 1),
        "dif_prev": _last(dif, 1), "dea_prev": _last(dea, 1),
        "rsi6": _last(rsi6), "rsi14": _last(rsi14),
        "k": _last(k), "d": _last(d), "j": _last(j),
        "boll_up": _last(up), "boll_mid": _last(mid), "boll_low": _last(low),
        "vol_ma5": int(vol_ma5) if vol_ma5 else None,
        "vol_ma10": int(vol_ma10) if vol_ma10 else None,
        "vol_ratio_vs_ma5": vol_ratio_vs_ma5,
        "high20": round(hi20, 2), "low20": round(lo20, 2),
        "high60": round(hi60, 2), "low60": round(lo60, 2),
        "high_all": round(hi_all, 2), "low_all": round(lo_all, 2),
        "bars": len(c),
    }

    # 均线多头 / 空头排列判定
    ma_seq = [res["ma5"], res["ma10"], res["ma20"], res["ma60"]]
    res["ma_alignment"] = "unknown"
    if all(x is not None for x in ma_seq):
        if ma_seq[0] > ma_seq[1] > ma_seq[2] > ma_seq[3]:
            res["ma_alignment"] = "bullish"   # 多头排列
        elif ma_seq[0] < ma_seq[1] < ma_seq[2] < ma_seq[3]:
            res["ma_alignment"] = "bearish"   # 空头排列
        else:
            res["ma_alignment"] = "mixed"     # 交织
    return res

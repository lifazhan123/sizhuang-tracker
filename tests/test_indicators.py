"""技术指标单元测试（纯标准库 unittest，无需额外依赖）。

运行：
    PYTHONPATH=src python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

from sizhuang.analysis.indicators import boll, ema, kdj, ma, macd, rsi, summarize_indicators
from sizhuang.analysis.sentiment import score_text


class TestMA(unittest.TestCase):
    def test_basic(self):
        out = ma([1, 2, 3, 4, 5], 3)
        self.assertIsNone(out[0])
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[2], 2.0)   # (1+2+3)/3
        self.assertAlmostEqual(out[3], 3.0)
        self.assertAlmostEqual(out[4], 4.0)

    def test_insufficient_data(self):
        out = ma([1, 2], 5)
        self.assertEqual(len(out), 2)
        self.assertTrue(all(v is None for v in out))

    def test_empty(self):
        self.assertEqual(ma([], 3), [])


class TestEMA(unittest.TestCase):
    def test_seed_and_length(self):
        out = ema([1, 2, 3, 4, 5], 3)
        self.assertEqual(len(out), 5)
        self.assertIsNone(out[0])
        self.assertAlmostEqual(out[2], 2.0)          # 种子 = 前三项均值
        # 下一项 = 4*k + prev*(1-k)，k = 2/(3+1) = 0.5
        self.assertAlmostEqual(out[3], 3.0)

    def test_constant_series(self):
        out = ema([5.0] * 10, 4)
        self.assertAlmostEqual(out[-1], 5.0)


class TestMACD(unittest.TestCase):
    def test_uptrend_is_positive(self):
        closes = [float(i) for i in range(1, 60)]
        dif, dea, hist = macd(closes)
        self.assertEqual(len(dif), len(closes))
        self.assertIsNotNone(dif[-1])
        self.assertGreater(dif[-1], 0)

    def test_downtrend_is_negative(self):
        closes = [float(i) for i in range(60, 1, -1)]
        dif, _, _ = macd(closes)
        self.assertLess(dif[-1], 0)

    def test_hist_equals_twice_gap(self):
        closes = [1 + (i % 7) * 0.3 for i in range(80)]
        dif, dea, hist = macd(closes)
        self.assertIsNotNone(hist[-1])
        self.assertAlmostEqual(hist[-1], 2 * (dif[-1] - dea[-1]), places=6)


class TestRSI(unittest.TestCase):
    def test_monotonic_rise_is_100(self):
        out = rsi([float(i) for i in range(1, 40)], 14)
        self.assertAlmostEqual(out[-1], 100.0)

    def test_monotonic_fall_is_zero(self):
        out = rsi([float(i) for i in range(40, 1, -1)], 14)
        self.assertAlmostEqual(out[-1], 0.0)

    def test_bounds(self):
        closes = [10, 11, 10.5, 12, 11.2, 13, 12.4, 14, 13.1, 15,
                  14.2, 16, 15.1, 17, 16.3, 18, 17.2, 19, 18.1, 20]
        out = rsi(closes, 6)
        for v in out:
            if v is not None:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 100.0)


class TestKDJ(unittest.TestCase):
    def test_ranges_and_length(self):
        highs = [10 + i * 0.5 for i in range(30)]
        lows = [9 + i * 0.5 for i in range(30)]
        closes = [9.5 + i * 0.5 for i in range(30)]
        k, d, j = kdj(highs, lows, closes)
        self.assertEqual(len(k), 30)
        self.assertTrue(all(v is None for v in k[:8]))
        for v in k[8:]:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 100.0)

    def test_insufficient(self):
        k, d, j = kdj([1, 2], [0, 1], [0.5, 1.5])
        self.assertTrue(all(v is None for v in k))


class TestBOLL(unittest.TestCase):
    def test_bands_ordering(self):
        closes = [10, 11, 10.5, 12, 11.5, 13, 12.5, 14, 13.5, 15,
                  14.5, 16, 15.5, 17, 16.5, 18, 17.5, 19, 18.5, 20]
        up, mid, low = boll(closes, 20, 2.0)
        self.assertAlmostEqual(mid[-1], sum(closes) / 20)
        self.assertGreater(up[-1], mid[-1])
        self.assertLess(low[-1], mid[-1])

    def test_flat_series_zero_width(self):
        up, mid, low = boll([10.0] * 25, 20, 2.0)
        self.assertAlmostEqual(up[-1], 10.0)
        self.assertAlmostEqual(low[-1], 10.0)


class TestSummarize(unittest.TestCase):
    def test_full_summary_uptrend(self):
        n = 150
        closes = [5 + i * 0.05 for i in range(n)]
        highs = [c + 0.1 for c in closes]
        lows = [c - 0.1 for c in closes]
        vols = [10000 + i * 10 for i in range(n)]
        s = summarize_indicators(closes, highs, lows, vols)
        self.assertEqual(s["ma_alignment"], "bullish")
        self.assertIsNotNone(s["ma5"])
        self.assertIsNotNone(s["rsi14"])
        self.assertGreater(s["rsi14"], 70)     # 单边上涨必然超买
        self.assertAlmostEqual(s["price"], round(closes[-1], 2))

    def test_short_series_is_safe(self):
        s = summarize_indicators([1.0, 2.0], [2.0, 3.0], [0.5, 1.0], [100.0, 200.0])
        self.assertEqual(s["ma_alignment"], "unknown")
        self.assertIsNone(s["ma20"])


class TestSentiment(unittest.TestCase):
    def test_positive(self):
        sentiment, score, hits = score_text("公司中标重大合同，业绩预增", "重大利好")
        self.assertEqual(sentiment, "positive")
        self.assertGreater(score, 0)
        self.assertTrue(hits)

    def test_negative(self):
        sentiment, score, _ = score_text("公司收到证监会立案告知书", "涉嫌违规被立案")
        self.assertEqual(sentiment, "negative")
        self.assertLess(score, 0)

    def test_neutral(self):
        sentiment, score, _ = score_text("公司发布日常经营公告", "关于会议的通知")
        self.assertEqual(sentiment, "neutral")

    def test_title_weighted_higher(self):
        _, s_title, _ = score_text("", "涨停")
        _, s_body, _ = score_text("涨停", "")
        self.assertGreater(s_title, s_body)


if __name__ == "__main__":
    unittest.main(verbosity=2)

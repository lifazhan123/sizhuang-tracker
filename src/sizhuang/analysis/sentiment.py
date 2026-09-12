"""舆情情绪打分：基于中文财经关键词的轻量情感分析。

不依赖任何模型，规则透明、可解释、可在报告中展示命中的关键词。
适合对新闻标题 / 公告标题 / 股吧帖子做粗粒度多空倾向标注。
"""

from __future__ import annotations

import re
from typing import Iterable

# 权重：3 = 强信号，2 = 中信号，1 = 弱信号
POSITIVE: dict[str, int] = {
    # 强
    "涨停": 3, "大涨": 3, "暴涨": 3, "扭亏": 3, "获批": 3, "中标": 3, "重大合同": 3,
    "重组": 3, "并购": 3, "要约收购": 3, "业绩预增": 3, "翻倍": 3, "超预期": 3,
    "历史新高": 3, "举牌": 3, "国资入主": 3, "摘帽": 3,
    # 中
    "上涨": 2, "利好": 2, "增长": 2, "签约": 2, "合作": 2, "订单": 2, "回购": 2,
    "增持": 2, "突破": 2, "扩产": 2, "产能": 2, "专利": 2, "创新高": 2, "盈利": 2,
    "政策支持": 2, "补贴": 2, "降本增效": 2, "毛利率提升": 2, "净利增长": 2,
    "战略合作": 2, "技术突破": 2, "放量上涨": 2, "资金流入": 2, "主力净流入": 2,
    # 弱
    "反弹": 1, "企稳": 1, "回暖": 1, "改善": 1, "受益": 1, "推进": 1, "落地": 1,
    "看好": 1, "买入": 1, "增持评级": 1, "推荐": 1, "低估": 1, "企稳回升": 1,
    "询价": 1, "进展": 1,
}

NEGATIVE: dict[str, int] = {
    # 强
    "跌停": 3, "大跌": 3, "暴跌": 3, "亏损": 3, "退市": 3, "立案": 3, "被查": 3,
    "处罚": 3, "违法": 3, "违规": 3, "商誉减值": 3, "业绩预亏": 3, "终止": 3,
    "失败": 3, "破产": 3, "债务违约": 3, "控制权变更风险": 3, "历史新低": 3,
    "大幅下修": 3, "被约谈": 3, "风险警示": 3,
    # 中
    "下跌": 2, "利空": 2, "下滑": 2, "下降": 2, "减持": 2, "质押": 2, "诉讼": 2,
    "问询": 2, "关注函": 2, "解禁": 2, "低于预期": 2, "缩水": 2, "净利下降": 2,
    "亏损扩大": 2, "资金流出": 2, "主力净流出": 2, "折价": 2, "计提": 2,
    "担保": 2, "逾期": 2, "停牌": 2, "澄清": 2, "风险提示": 2,
    # 弱
    "承压": 1, "回落": 1, "走弱": 1, "谨慎": 1, "中性": 1, "观望": 1, "放缓": 1,
    "汇兑损失": 1, "成本上升": 1, "不确定": 1,
}

_NEGATORS = ("不", "未", "没有", "无", "非", "难以", "尚未")

_WORD_RE = re.compile("|".join(map(re.escape, sorted(set(POSITIVE) | set(NEGATIVE), key=len, reverse=True))))


def score_text(text: str, title: str = "") -> tuple[str, int, list[str]]:
    """对一段文本打分。

    标题命中权重 ×2（标题是作者最强意图的表达）。

    返回 (sentiment, score, hit_words)：
        sentiment ∈ {positive, negative, neutral}
    """
    if not text and not title:
        return "neutral", 0, []

    score = 0
    hits: list[str] = []

    def scan(chunk: str, weight: int) -> int:
        sub = 0
        for m in _WORD_RE.finditer(chunk):
            word = m.group()
            # 前置否定词反转极性
            prefix = chunk[max(0, m.start() - 2): m.start()]
            negated = any(n in prefix for n in _NEGATORS)
            w = POSITIVE.get(word, 0) * weight - NEGATIVE.get(word, 0) * weight
            if negated:
                w = -w
            if w:
                sub += w
                hits.append(("!" if negated else "") + word)
        return sub

    score += scan(title, 2)
    score += scan(text, 1)

    if score >= 2:
        sentiment = "positive"
    elif score <= -2:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    # 去重保序
    seen, uniq = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    return sentiment, score, uniq[:8]


def score_items(items: Iterable, title_attr: str = "title", text_attr: str = "summary") -> dict:
    """批量打分并原地写回 sentiment / sentiment_score，返回统计摘要。"""
    positive = negative = neutral = 0
    total = 0
    for it in items:
        title = getattr(it, title_attr, "") or ""
        text = getattr(it, text_attr, "") or ""
        sentiment, score, hits = score_text(text, title)
        it.sentiment = sentiment
        it.sentiment_score = score
        if hasattr(it, "extra") and isinstance(getattr(it, "extra"), dict) and hits:
            it.extra["sentiment_hits"] = hits
        total += 1
        if sentiment == "positive":
            positive += 1
        elif sentiment == "negative":
            negative += 1
        else:
            neutral += 1

    # 情绪指数：0~100，50 为中性
    weighted = positive - negative
    index = 50 + (weighted / total * 50 if total else 0)
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "index": round(index, 1),
        "label": "偏多" if index >= 60 else ("偏空" if index <= 40 else "中性"),
    }
